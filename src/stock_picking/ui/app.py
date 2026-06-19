import streamlit as st

from stock_picking.data.cache import Cache
from stock_picking.data.fetcher import fetch_all
from stock_picking.settings import Settings
from stock_picking.ui.presenter import build_dashboard_rows
from stock_picking.valuator import valuate
from stock_picking.watchlist import Watchlist

_DB_PATH = "stock_picking.db"


@st.cache_resource
def _get_services() -> tuple[Watchlist, Cache, Settings]:
    settings = Settings()
    watchlist = Watchlist(db_path=_DB_PATH)
    cache = Cache(db_path=_DB_PATH, ttl_hours=settings.cache_ttl_hours)
    return watchlist, cache, settings


def _run_refresh(watchlist: Watchlist, cache: Cache, settings: Settings) -> None:
    tickers = watchlist.tickers()
    if not tickers:
        st.warning("Watchlist is empty. Add tickers below first.")
        return

    progress = st.progress(0.0, text="Fetching data…")

    def _on_progress(done: int, total: int) -> None:
        progress.progress(done / total, text=f"Fetched {done}/{total}")

    financials = fetch_all(tickers, cache, force_refresh=True, status_callback=_on_progress)
    progress.empty()

    for ticker in tickers:
        fin = financials.get(ticker)
        if fin is None:
            st.warning(f"Could not fetch data for {ticker} — skipping.")
            continue
        overrides = watchlist.get_overrides(ticker)
        result = valuate(fin, settings, overrides)
        watchlist.save_valuation(result)

    st.success("Refresh complete.")


def main() -> None:
    st.set_page_config(page_title="Stock Picker", layout="wide")
    st.title("Stock Picker — Dashboard")

    watchlist, cache, settings = _get_services()

    with st.sidebar:
        st.header("Watchlist")
        new_ticker = st.text_input("Add ticker", placeholder="e.g. AAPL").strip().upper()
        if st.button("Add") and new_ticker:
            watchlist.add(new_ticker)
            st.rerun()

        tickers = watchlist.tickers()
        for ticker in tickers:
            col1, col2 = st.columns([3, 1])
            col1.write(ticker)
            if col2.button("✕", key=f"rm_{ticker}"):
                watchlist.remove(ticker)
                st.rerun()

        st.divider()
        if st.button("Refresh all", type="primary", use_container_width=True):
            _run_refresh(watchlist, cache, settings)
            st.rerun()

    valuations = watchlist.get_valuations()
    if not valuations:
        st.info("No valuations yet. Add tickers and click **Refresh all**.")
        return

    rows = build_dashboard_rows(valuations)
    st.dataframe(rows, use_container_width=True)


if __name__ == "__main__":
    main()
