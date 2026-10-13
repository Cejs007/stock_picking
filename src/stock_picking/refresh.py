from collections.abc import Callable

from stock_picking.data.cache import Cache
from stock_picking.data.fetcher import fetch_all
from stock_picking.settings import Settings
from stock_picking.valuator import valuate
from stock_picking.watchlist import Watchlist


def refresh_valuations(
    tickers: list[str],
    watchlist: Watchlist,
    cache: Cache,
    settings: Settings,
    force_refresh: bool = False,
    status_callback: Callable[[int, int], None] | None = None,
) -> list[str]:
    """Fetch, valuate and save each ticker; return the tickers that could not be fetched."""
    financials = fetch_all(
        tickers, cache, force_refresh=force_refresh, status_callback=status_callback
    )
    skipped: list[str] = []
    for ticker in tickers:
        fin = financials.get(ticker)
        if fin is None:
            skipped.append(ticker)
            continue
        result = valuate(fin, settings, watchlist.get_overrides(ticker))
        watchlist.save_valuation(result)
    return skipped
