from unittest.mock import MagicMock, patch

import pytest

from stock_picking.data.cache import Cache
from stock_picking.data.fetcher import FetchError, fetch_all
from stock_picking.data.models import FinancialData
from stock_picking.settings import Settings
from stock_picking.valuator import valuate


def _make_fin(ticker: str) -> FinancialData:
    return FinancialData(ticker=ticker, current_price=100.0)


def test_cache_miss_calls_fetch_and_returns_data() -> None:
    cache = Cache(db_path=":memory:")
    fin = _make_fin("AAPL")
    with patch("stock_picking.data.fetcher.fetch", return_value=fin) as mock_fetch:
        result = fetch_all(["AAPL"], cache)
    mock_fetch.assert_called_once_with("AAPL")
    assert "AAPL" in result
    assert result["AAPL"].ticker == "AAPL"


def test_cache_hit_returns_cached_data_without_calling_fetch() -> None:
    cache = Cache(db_path=":memory:")
    fin = _make_fin("AAPL")
    cache.set("AAPL", "financials", fin.model_dump())
    with patch("stock_picking.data.fetcher.fetch") as mock_fetch:
        result = fetch_all(["AAPL"], cache)
    mock_fetch.assert_not_called()
    assert result["AAPL"].ticker == "AAPL"


def test_force_refresh_bypasses_cache() -> None:
    cache = Cache(db_path=":memory:")
    cached_fin = _make_fin("AAPL")
    fresh_fin = FinancialData(ticker="AAPL", current_price=999.0)
    cache.set("AAPL", "financials", cached_fin.model_dump())
    with patch("stock_picking.data.fetcher.fetch", return_value=fresh_fin):
        result = fetch_all(["AAPL"], cache, force_refresh=True)
    assert result["AAPL"].current_price == 999.0


def test_fetch_error_excludes_ticker_others_returned() -> None:
    cache = Cache(db_path=":memory:")
    msft_fin = _make_fin("MSFT")

    def side_effect(ticker: str) -> FinancialData:
        if ticker == "BAD":
            raise FetchError("no data")
        return msft_fin

    with patch("stock_picking.data.fetcher.fetch", side_effect=side_effect):
        result = fetch_all(["BAD", "MSFT"], cache)

    assert "BAD" not in result
    assert "MSFT" in result


def _eur_reported(ticker: str = "ASML") -> FinancialData:
    return FinancialData(
        ticker=ticker,
        currency="USD",
        financial_currency="EUR",
        current_price=700.0,
        eps_ttm=2.0,
        cash=100.0,
    )


def _fx_ticker(price: float) -> MagicMock:
    t = MagicMock()
    t.info = {"regularMarketPrice": price}
    return t


def test_fundamentals_in_other_currency_are_converted_to_quote_currency() -> None:
    cache = Cache(db_path=":memory:")
    with (
        patch("stock_picking.data.fetcher.fetch", return_value=_eur_reported()),
        patch("stock_picking.data.fetcher.yf.Ticker", return_value=_fx_ticker(1.1)) as yt,
    ):
        result = fetch_all(["ASML"], cache)

    yt.assert_called_once_with("EURUSD=X")
    fin = result["ASML"]
    # EUR -> USD at 1.1: cash 100 * 1.1 = 110; EPS is already in the quote
    # currency and price is the quote itself, so both stay untouched.
    assert fin.eps_ttm == 2.0
    assert fin.cash == pytest.approx(110.0)
    assert fin.current_price == 700.0
    assert fin.financial_currency == "USD"


def test_cache_keeps_raw_statement_currency_values() -> None:
    cache = Cache(db_path=":memory:")
    with (
        patch("stock_picking.data.fetcher.fetch", return_value=_eur_reported()),
        patch("stock_picking.data.fetcher.yf.Ticker", return_value=_fx_ticker(1.1)),
    ):
        fetch_all(["ASML"], cache)

    cached = cache.get("ASML", "financials")
    assert cached is not None
    assert cached["eps_ttm"] == 2.0
    assert cached["financial_currency"] == "EUR"


def test_same_currency_makes_no_fx_request() -> None:
    cache = Cache(db_path=":memory:")
    czk = FinancialData(ticker="CEZ.PR", currency="CZK", financial_currency="CZK", current_price=1000.0)
    with (
        patch("stock_picking.data.fetcher.fetch", return_value=czk),
        patch("stock_picking.data.fetcher.yf.Ticker") as yt,
    ):
        result = fetch_all(["CEZ.PR"], cache)

    yt.assert_not_called()
    assert result["CEZ.PR"] == czk


def test_fx_rate_is_cached_and_reused() -> None:
    cache = Cache(db_path=":memory:")
    with (
        patch("stock_picking.data.fetcher.fetch", side_effect=_eur_reported),
        patch("stock_picking.data.fetcher.yf.Ticker", return_value=_fx_ticker(1.1)) as yt,
    ):
        fetch_all(["ASML"], cache)
        second = fetch_all(["ASML", "SAP"], cache)

    assert yt.call_count == 1
    # cash 100 EUR * 1.1 = 110 USD
    assert second["SAP"].cash == pytest.approx(110.0)


def test_fx_rate_expires_on_its_own_ttl_before_financials() -> None:
    t = 1_000_000.0
    cache = Cache(db_path=":memory:", ttl_hours=24.0, _now=lambda: t)
    with (
        patch("stock_picking.data.fetcher.fetch", return_value=_eur_reported()) as mock_fetch,
        patch("stock_picking.data.fetcher.yf.Ticker", side_effect=[_fx_ticker(1.1), _fx_ticker(1.2)]),
    ):
        fetch_all(["ASML"], cache)
        # 13 h later: financials (24 h TTL) still cached, FX rate (12 h TTL) stale.
        cache._now = lambda: t + 13 * 3600
        result = fetch_all(["ASML"], cache)

    assert mock_fetch.call_count == 1
    # Fresh rate 1.2: cash 100 * 1.2 = 120
    assert result["ASML"].cash == pytest.approx(120.0)


def test_fx_unavailable_returns_unconverted_and_valuation_warns() -> None:
    cache = Cache(db_path=":memory:")
    with (
        patch("stock_picking.data.fetcher.fetch", return_value=_eur_reported()),
        patch("stock_picking.data.fetcher.yf.Ticker", side_effect=TimeoutError("timed out")),
        patch("stock_picking.data.fetcher.time.sleep"),
    ):
        result = fetch_all(["ASML"], cache)

    fin = result["ASML"]
    assert fin.cash == 100.0
    assert fin.financial_currency == "EUR"
    assert cache.get("EURUSD=X", "fx_rate") is None

    valuation = valuate(fin, Settings())
    assert valuation.currency == "USD"
    assert any("EUR" in w and "not converted" in w for w in valuation.warnings)


def test_cached_payload_without_statement_currency_warns_instead_of_valuing() -> None:
    # Written by a version before financial_currency existed.
    cache = Cache(db_path=":memory:")
    cache.set("TSM", "financials", {"ticker": "TSM", "currency": "USD",
                                    "current_price": 1.0, "eps_ttm": 8.0, "cash": 3500.0})
    with (
        patch("stock_picking.data.fetcher.fetch") as mock_fetch,
        patch("stock_picking.data.fetcher.yf.Ticker") as yt,
    ):
        fin = fetch_all(["TSM"], cache)["TSM"]

    mock_fetch.assert_not_called()
    yt.assert_not_called()
    valuation = valuate(fin, Settings())
    assert valuation.signal == "N/A"
    assert any("Statement currency unknown" in w for w in valuation.warnings)


def test_usd_statements_with_pence_quote_are_converted_into_pence() -> None:
    # SHEL.L: statements in USD, quoted in GBp. Yahoo's USDGBp=X returns pounds,
    # so the boundary must fetch USDGBP=X and scale into pence itself.
    cache = Cache(db_path=":memory:")
    shel = FinancialData(ticker="SHEL.L", currency="GBp", financial_currency="USD",
                         current_price=3800.0, cash=100.0)
    with (
        patch("stock_picking.data.fetcher.fetch", return_value=shel),
        patch("stock_picking.data.fetcher.yf.Ticker", return_value=_fx_ticker(0.75)) as yt,
    ):
        result = fetch_all(["SHEL.L"], cache)

    yt.assert_called_once_with("USDGBP=X")
    # 100 USD * 0.75 GBP/USD * 100 GBp/GBP = 7500 GBp
    assert result["SHEL.L"].cash == pytest.approx(7500.0)
    assert result["SHEL.L"].financial_currency == "GBp"


def test_gbp_statements_with_pence_quote_scale_without_fx_request() -> None:
    cache = Cache(db_path=":memory:")
    tsco = FinancialData(ticker="TSCO.L", currency="GBp", financial_currency="GBP",
                         current_price=500.0, cash=100.0)
    with (
        patch("stock_picking.data.fetcher.fetch", return_value=tsco),
        patch("stock_picking.data.fetcher.yf.Ticker") as yt,
    ):
        result = fetch_all(["TSCO.L"], cache)

    yt.assert_not_called()
    # 100 GBP * 100 GBp/GBP = 10000 GBp
    assert result["TSCO.L"].cash == pytest.approx(10000.0)
