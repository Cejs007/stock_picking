from unittest.mock import patch

import pytest

from stock_picking.data.cache import Cache
from stock_picking.data.fetcher import FetchError, fetch_all
from stock_picking.data.models import FinancialData


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
