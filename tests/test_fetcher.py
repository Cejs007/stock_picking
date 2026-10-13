from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from stock_picking.data.fetcher import FetchError, fetch, fetch_fx_rate
from stock_picking.data.models import FinancialData

_SAMPLE_INFO: dict = {
    "currentPrice": 150.0,
    "longName": "Apple Inc.",
    "currency": "USD",
    "trailingEps": 6.0,
    "bookValue": 4.0,
    "sharesOutstanding": 1_000_000.0,
    "ebitda": 50_000.0,
    "enterpriseValue": 200_000.0,
    "totalDebt": 30_000.0,
    "totalCash": 10_000.0,
}


def _make_ticker(info: dict = _SAMPLE_INFO, cashflow: pd.DataFrame = pd.DataFrame()) -> MagicMock:
    t = MagicMock()
    t.info = info
    t.cashflow = cashflow
    return t


def test_valid_ticker_maps_scalar_fields() -> None:
    with patch("stock_picking.data.fetcher.yf.Ticker", return_value=_make_ticker()):
        result = fetch("AAPL")

    assert result.ticker == "AAPL"
    assert result.current_price == 150.0
    assert result.company_name == "Apple Inc."
    assert result.currency == "USD"
    assert result.eps_ttm == 6.0
    assert result.bvps == 4.0
    assert result.shares_outstanding == 1_000_000.0
    assert result.ebitda == 50_000.0
    assert result.ev == 200_000.0
    assert result.total_debt == 30_000.0
    assert result.cash == 10_000.0


def test_missing_optional_field_is_none() -> None:
    info = {**_SAMPLE_INFO}
    del info["trailingEps"]
    with patch("stock_picking.data.fetcher.yf.Ticker", return_value=_make_ticker(info=info)):
        result = fetch("AAPL")

    assert result.eps_ttm is None


def test_current_price_fallback_to_regular_market_price() -> None:
    info = {k: v for k, v in _SAMPLE_INFO.items() if k != "currentPrice"}
    info["regularMarketPrice"] = 148.5
    with patch("stock_picking.data.fetcher.yf.Ticker", return_value=_make_ticker(info=info)):
        result = fetch("AAPL")

    assert result.current_price == 148.5


def test_no_price_raises_fetch_error() -> None:
    info = {k: v for k, v in _SAMPLE_INFO.items() if k != "currentPrice"}
    with patch("stock_picking.data.fetcher.yf.Ticker", return_value=_make_ticker(info=info)):
        with pytest.raises(FetchError):
            fetch("AAPL")


def _make_cashflow(free_cash_flows: list[float]) -> pd.DataFrame:
    """Build a cashflow DataFrame as yfinance returns it: columns newest-first."""
    import pandas as pd
    dates = pd.date_range("2023", periods=len(free_cash_flows), freq="-1YS")
    return pd.DataFrame(
        {"Free Cash Flow": free_cash_flows},
        index=dates,
    ).T


def test_cashflow_fills_fcf_history_oldest_first() -> None:
    # yfinance returns newest first: [100, 90, 80] → oldest-first: [80, 90, 100]
    cf = _make_cashflow([100.0, 90.0, 80.0])
    with patch("stock_picking.data.fetcher.yf.Ticker", return_value=_make_ticker(cashflow=cf)):
        result = fetch("AAPL")

    assert result.fcf_history == [80.0, 90.0, 100.0]


def test_cashflow_capped_at_five_years() -> None:
    cf = _make_cashflow([60.0, 50.0, 40.0, 30.0, 20.0, 10.0])
    with patch("stock_picking.data.fetcher.yf.Ticker", return_value=_make_ticker(cashflow=cf)):
        result = fetch("AAPL")

    assert len(result.fcf_history) == 5
    assert result.fcf_history == [20.0, 30.0, 40.0, 50.0, 60.0]


def test_missing_cashflow_gives_empty_fcf_history() -> None:
    with patch("stock_picking.data.fetcher.yf.Ticker", return_value=_make_ticker()):
        result = fetch("AAPL")

    assert result.fcf_history == []


def test_bad_ticker_raises_fetch_error() -> None:
    with patch("stock_picking.data.fetcher.yf.Ticker", return_value=_make_ticker(info={})):
        with pytest.raises(FetchError):
            fetch("NOTASTOCK")


def test_financial_currency_mapped_from_info() -> None:
    # ADR-style: quote in USD, statements in TWD.
    info = {**_SAMPLE_INFO, "financialCurrency": "TWD"}
    with patch("stock_picking.data.fetcher.yf.Ticker", return_value=_make_ticker(info=info)):
        result = fetch("TSM")

    assert result.currency == "USD"
    assert result.financial_currency == "TWD"


def test_missing_financial_currency_is_none() -> None:
    with patch("stock_picking.data.fetcher.yf.Ticker", return_value=_make_ticker()):
        result = fetch("AAPL")

    assert result.financial_currency is None


def _fx_ticker(price: object) -> MagicMock:
    t = MagicMock()
    t.info = {"regularMarketPrice": price, "currency": "USD", "quoteType": "CURRENCY"}
    return t


def test_fetch_fx_rate_requests_yahoo_pair_ticker() -> None:
    with patch("stock_picking.data.fetcher.yf.Ticker", return_value=_fx_ticker(1.12)) as yt:
        rate = fetch_fx_rate("EUR", "USD")

    yt.assert_called_once_with("EURUSD=X")
    assert rate == 1.12


def test_fetch_fx_rate_retries_with_backoff_then_succeeds() -> None:
    sleeps: list[float] = []
    side_effect = [TimeoutError("timed out"), TimeoutError("timed out"), _fx_ticker(21.7)]
    with patch("stock_picking.data.fetcher.yf.Ticker", side_effect=side_effect) as yt:
        rate = fetch_fx_rate("USD", "CZK", _sleep=sleeps.append)

    assert rate == 21.7
    assert yt.call_count == 3
    assert sleeps == [0.5, 1.0]


def test_fetch_fx_rate_returns_none_after_all_attempts_fail() -> None:
    sleeps: list[float] = []
    with patch("stock_picking.data.fetcher.yf.Ticker", side_effect=TimeoutError("timed out")) as yt:
        rate = fetch_fx_rate("EUR", "USD", _sleep=sleeps.append)

    assert rate is None
    assert yt.call_count == 3


@pytest.mark.parametrize("price", [None, 0.0, -1.0, float("nan"), "garbage"])
def test_fetch_fx_rate_invalid_price_returns_none(price: object) -> None:
    with patch("stock_picking.data.fetcher.yf.Ticker", return_value=_fx_ticker(price)):
        assert fetch_fx_rate("EUR", "USD") is None


def test_old_cache_payload_without_financial_currency_still_loads() -> None:
    old_payload = {"ticker": "AAPL", "currency": "USD", "current_price": 150.0}
    fin = FinancialData.model_validate(old_payload)
    assert fin.financial_currency is None
