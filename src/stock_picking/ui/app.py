import streamlit as st

from stock_picking.data.cache import Cache
from stock_picking.refresh import refresh_valuations
from stock_picking.settings import Settings
from stock_picking.ui.presenter import build_dashboard_rows
from stock_picking.watchlist import Watchlist

_DB_PATH = "stock_picking.db"


@st.cache_resource
def _get_services() -> tuple[Watchlist, Cache, Settings]:
    settings = Settings()
    watchlist = Watchlist(db_path=_DB_PATH)
    cache = Cache(db_path=_DB_PATH, ttl_hours=settings.cache_ttl_hours)
    return watchlist, cache, settings


def _run_refresh(
    watchlist: Watchlist, cache: Cache, settings: Settings, force_refresh: bool
) -> None:
    tickers = watchlist.tickers()
    if not tickers:
        st.warning("Watchlist is empty. Add tickers below first.")
        return

    progress = st.progress(0.0, text="Fetching data…")

    def _on_progress(done: int, total: int) -> None:
        progress.progress(done / total, text=f"Fetched {done}/{total}")

    skipped = refresh_valuations(
        tickers, watchlist, cache, settings,
        force_refresh=force_refresh, status_callback=_on_progress,
    )
    progress.empty()

    for ticker in skipped:
        st.warning(f"Could not fetch data for {ticker} — skipping.")

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
            _run_refresh(watchlist, cache, settings, force_refresh=False)
            st.rerun()
        if st.button(
            "Force refresh",
            use_container_width=True,
            help="Ignore cached data and re-download everything.",
        ):
            _run_refresh(watchlist, cache, settings, force_refresh=True)
            st.rerun()

    valuations = watchlist.get_valuations()
    if not valuations:
        st.info("No valuations yet. Add tickers and click **Refresh all**.")
        return

    rows = build_dashboard_rows(valuations)
    st.dataframe(rows, use_container_width=True)


if __name__ == "__main__":
    main()
