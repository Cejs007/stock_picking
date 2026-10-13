import sqlite3
from pathlib import Path

import pytest

from stock_picking.watchlist import TickerOverrides, ValuationResult, Watchlist


@pytest.fixture
def wl() -> Watchlist:
    return Watchlist(db_path=":memory:")


@pytest.fixture
def valuation() -> ValuationResult:
    return ValuationResult(
        ticker="AAPL",
        fair_value_dcf=180.0,
        fair_value_graham=67.0,
        fair_value_pe=85.0,
        fair_value_ev_ebitda=18.0,
        fair_value_composite=87.5,
        current_price=100.0,
        master_score=-12.5,
        buy_target=65.6,
        signal="WAIT",
        warnings=["EV/EBITDA history short"],
    )


def test_add_ticker_appears_in_tickers(wl: Watchlist) -> None:
    wl.add("AAPL")
    assert "AAPL" in wl.tickers()


def test_remove_ticker_disappears_from_tickers(wl: Watchlist) -> None:
    wl.add("AAPL")
    wl.remove("AAPL")
    assert "AAPL" not in wl.tickers()


def test_duplicate_add_is_idempotent(wl: Watchlist) -> None:
    wl.add("AAPL")
    wl.add("AAPL")
    assert wl.tickers().count("AAPL") == 1


def test_remove_nonexistent_ticker_is_silent(wl: Watchlist) -> None:
    wl.remove("NONEXISTENT")  # must not raise


def test_get_overrides_unknown_ticker_returns_none(wl: Watchlist) -> None:
    assert wl.get_overrides("AAPL") is None


def test_set_overrides_raises_for_unknown_ticker(wl: Watchlist) -> None:
    from stock_picking.watchlist import TickerOverrides

    with pytest.raises(KeyError):
        wl.set_overrides("AAPL", TickerOverrides())


def test_get_valuations_empty_returns_empty_list(wl: Watchlist) -> None:
    assert wl.get_valuations() == []


def test_save_valuation_appears_in_get_valuations(wl: Watchlist, valuation: ValuationResult) -> None:
    wl.save_valuation(valuation)
    results = wl.get_valuations()
    assert len(results) == 1
    r = results[0]
    assert r.ticker == "AAPL"
    assert r.fair_value_composite == pytest.approx(87.5)
    assert r.signal == "WAIT"
    assert r.warnings == ["EV/EBITDA history short"]


def test_save_valuation_overwrites_previous(wl: Watchlist, valuation: ValuationResult) -> None:
    wl.save_valuation(valuation)
    updated = valuation.model_copy(update={"fair_value_composite": 120.0, "signal": "BUY"})
    wl.save_valuation(updated)
    results = wl.get_valuations()
    assert len(results) == 1
    assert results[0].fair_value_composite == pytest.approx(120.0)
    assert results[0].signal == "BUY"


def test_add_stores_metadata_in_get_all_entries(wl: Watchlist) -> None:
    from stock_picking.watchlist import WatchlistEntry

    wl.add("AAPL", company_name="Apple Inc.", currency="USD")
    entries = wl.get_all_entries()
    assert len(entries) == 1
    e = entries[0]
    assert isinstance(e, WatchlistEntry)
    assert e.ticker == "AAPL"
    assert e.company_name == "Apple Inc."
    assert e.currency == "USD"


def test_set_overrides_roundtrip(wl: Watchlist) -> None:
    from stock_picking.watchlist import TickerOverrides

    wl.add("AAPL")
    overrides = TickerOverrides(mos_override=0.30, dcf_wacc_override=0.08, dcf_years=5)
    wl.set_overrides("AAPL", overrides)

    result = wl.get_overrides("AAPL")
    assert result is not None
    assert result.mos_override == pytest.approx(0.30)
    assert result.dcf_wacc_override == pytest.approx(0.08)
    assert result.dcf_years == 5
    assert result.dcf_growth_override is None  # not set, stays None
    assert result.dcf_terminal_g == pytest.approx(0.03)  # default


def test_save_valuation_roundtrips_currency(wl: Watchlist, valuation: ValuationResult) -> None:
    wl.save_valuation(valuation.model_copy(update={"ticker": "CEZ.PR", "currency": "CZK"}))
    [loaded] = wl.get_valuations()
    assert loaded.currency == "CZK"


def test_existing_db_without_currency_column_is_migrated(tmp_path: Path) -> None:
    db = str(tmp_path / "old.db")
    conn = sqlite3.connect(db)
    # valuations schema as shipped in v1, before the currency column.
    conn.execute("""
        CREATE TABLE valuations (
            ticker TEXT PRIMARY KEY,
            fair_value_dcf REAL,
            fair_value_graham REAL,
            fair_value_pe REAL,
            fair_value_ev_ebitda REAL,
            fair_value_composite REAL,
            current_price REAL NOT NULL,
            master_score REAL,
            buy_target REAL,
            signal TEXT NOT NULL,
            warnings TEXT NOT NULL DEFAULT '[]',
            calculated_at TEXT NOT NULL
        )
    """)
    conn.execute(
        "INSERT INTO valuations (ticker, current_price, signal, calculated_at)"
        " VALUES ('OLD', 50.0, 'WAIT', '2026-06-01T00:00:00+00:00')"
    )
    conn.commit()
    conn.close()

    wl = Watchlist(db_path=db)

    [old] = wl.get_valuations()
    assert old.ticker == "OLD"
    assert old.current_price == 50.0
    assert old.currency is None

    wl.save_valuation(ValuationResult(ticker="NEW", current_price=1.0, signal="N/A", currency="EUR"))
    by_ticker = {v.ticker: v for v in wl.get_valuations()}
    assert by_ticker["NEW"].currency == "EUR"


def test_reopening_migrated_db_is_idempotent(tmp_path: Path) -> None:
    db = str(tmp_path / "wl.db")
    Watchlist(db_path=db).save_valuation(
        ValuationResult(ticker="X", current_price=1.0, signal="N/A", currency="USD")
    )
    [reloaded] = Watchlist(db_path=db).get_valuations()
    assert reloaded.currency == "USD"
