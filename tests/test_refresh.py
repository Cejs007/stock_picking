from unittest.mock import patch

from stock_picking.data.cache import Cache
from stock_picking.data.fetcher import FetchError
from stock_picking.data.models import FinancialData
from stock_picking.refresh import refresh_valuations
from stock_picking.settings import Settings
from stock_picking.watchlist import Watchlist


def _cached_setup(
    fin: FinancialData, clock: list[float] | None = None
) -> tuple[Watchlist, Cache]:
    # Cache clock is injected (seconds); entries are written at t = clock[0].
    now = clock if clock is not None else [0.0]
    watchlist = Watchlist(db_path=":memory:")
    watchlist.add(fin.ticker)
    cache = Cache(db_path=":memory:", ttl_hours=24, _now=lambda: now[0])
    cache.set(fin.ticker, "financials", fin.model_dump())
    return watchlist, cache


def test_normal_refresh_uses_fresh_cache_without_fetching(fin: FinancialData) -> None:
    watchlist, cache = _cached_setup(fin)
    with patch("stock_picking.data.fetcher.fetch") as mock_fetch:
        refresh_valuations([fin.ticker], watchlist, cache, Settings())
    mock_fetch.assert_not_called()
    [saved] = watchlist.get_valuations()
    assert saved.ticker == "TEST"
    assert saved.current_price == 100.0


def test_normal_refresh_refetches_once_cache_is_stale(fin: FinancialData) -> None:
    clock = [0.0]
    watchlist, cache = _cached_setup(fin, clock)
    clock[0] = 25 * 3600  # 25 h after caching, past the 24 h TTL
    fresh = fin.model_copy(update={"current_price": 50.0})
    with patch("stock_picking.data.fetcher.fetch", return_value=fresh) as mock_fetch:
        refresh_valuations([fin.ticker], watchlist, cache, Settings())
    mock_fetch.assert_called_once_with("TEST")
    [saved] = watchlist.get_valuations()
    assert saved.current_price == 50.0


def test_force_refresh_bypasses_cache(fin: FinancialData) -> None:
    watchlist, cache = _cached_setup(fin)
    fresh = fin.model_copy(update={"current_price": 50.0})
    with patch("stock_picking.data.fetcher.fetch", return_value=fresh) as mock_fetch:
        refresh_valuations([fin.ticker], watchlist, cache, Settings(), force_refresh=True)
    mock_fetch.assert_called_once_with("TEST")
    [saved] = watchlist.get_valuations()
    assert saved.current_price == 50.0


def test_refresh_returns_tickers_that_could_not_be_fetched(fin: FinancialData) -> None:
    watchlist, cache = _cached_setup(fin)
    with patch("stock_picking.data.fetcher.fetch", side_effect=FetchError("no data")):
        skipped = refresh_valuations(["TEST", "MISSING"], watchlist, cache, Settings())
    assert skipped == ["MISSING"]
    assert [v.ticker for v in watchlist.get_valuations()] == ["TEST"]


def test_refresh_reports_progress_through_callback(fin: FinancialData) -> None:
    watchlist, cache = _cached_setup(fin)
    calls: list[tuple[int, int]] = []
    refresh_valuations(
        [fin.ticker], watchlist, cache, Settings(),
        status_callback=lambda done, total: calls.append((done, total)),
    )
    assert calls == [(1, 1)]
