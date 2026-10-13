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
        fair_values={"dcf": 180.0, "graham": 67.0, "pe_relative": 85.0, "ev_ebitda": 18.0},
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


def test_fair_values_roundtrip_including_na_and_any_model_name(
    wl: Watchlist, valuation: ValuationResult
) -> None:
    fvs = {"graham": None, "dcf": 180.0, "some_new_model": 42.0}
    wl.save_valuation(valuation.model_copy(update={"fair_values": fvs}))
    assert wl.get_valuations()[0].fair_values == fvs


def test_non_finite_fair_values_are_stored_as_na(
    wl: Watchlist, valuation: ValuationResult
) -> None:
    # A REAL column stored NaN as NULL; the JSON column must keep showing N/A, not "nan"
    fvs = {"graham": float("nan"), "dcf": float("inf"), "pe_relative": 85.0}
    wl.save_valuation(valuation.model_copy(update={"fair_values": fvs}))
    assert wl.get_valuations()[0].fair_values == {
        "graham": None,
        "dcf": None,
        "pe_relative": 85.0,
    }


def test_legacy_valuations_table_is_migrated_to_fair_values(tmp_path) -> None:
    db = tmp_path / "legacy.db"
    conn = sqlite3.connect(db)
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
        "INSERT INTO valuations VALUES"
        " ('AAPL', 180.0, NULL, 85.0, 18.0, 87.5, 100.0, -12.5, 65.6, 'WAIT', '[]',"
        " '2026-01-01T00:00:00+00:00')"
    )
    conn.commit()
    conn.close()

    r = Watchlist(db_path=str(db)).get_valuations()[0]

    assert r.fair_values == {"graham": None, "pe_relative": 85.0, "ev_ebitda": 18.0, "dcf": 180.0}
    assert r.fair_value_composite == pytest.approx(87.5)


def test_fair_value_range_and_cv_roundtrip(wl: Watchlist, valuation: ValuationResult) -> None:
    ranged = valuation.model_copy(
        update={"fair_value_low": 18.0, "fair_value_high": 180.0, "fair_value_cv": 0.75}
    )
    wl.save_valuation(ranged)
    r = wl.get_valuations()[0]
    assert r.fair_value_low == pytest.approx(18.0)
    assert r.fair_value_high == pytest.approx(180.0)
    assert r.fair_value_cv == pytest.approx(0.75)


def test_valuations_table_without_range_columns_is_migrated(tmp_path) -> None:
    db = tmp_path / "pre_range.db"
    conn = sqlite3.connect(db)
    conn.execute("""
        CREATE TABLE valuations (
            ticker TEXT PRIMARY KEY,
            fair_values TEXT NOT NULL DEFAULT '{}',
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
        "INSERT INTO valuations VALUES"
        " ('AAPL', '{\"dcf\": 180.0}', 87.5, 100.0, -12.5, 65.6, 'WAIT', '[]',"
        " '2026-01-01T00:00:00+00:00')"
    )
    conn.commit()
    conn.close()

    wl = Watchlist(db_path=str(db))
    old = wl.get_valuations()[0]
    assert old.fair_value_composite == pytest.approx(87.5)
    assert (old.fair_value_low, old.fair_value_high, old.fair_value_cv) == (None, None, None)

    wl.save_valuation(old.model_copy(update={"fair_value_low": 18.0, "fair_value_cv": 0.5}))
    new = wl.get_valuations()[0]
    assert new.fair_value_low == pytest.approx(18.0)
    assert new.fair_value_cv == pytest.approx(0.5)


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
    assert result.dcf_terminal_g is None  # not set -> valuator uses Settings


def test_added_ticker_has_unset_terminal_g_and_years(wl: Watchlist) -> None:
    wl.add("AAPL")
    result = wl.get_overrides("AAPL")
    assert result is not None
    assert result.dcf_terminal_g is None
    assert result.dcf_years is None


def test_explicit_terminal_g_and_years_roundtrip(wl: Watchlist) -> None:
    wl.add("AAPL")
    wl.set_overrides("AAPL", TickerOverrides(dcf_terminal_g=0.025, dcf_years=7))
    result = wl.get_overrides("AAPL")
    assert result is not None
    assert result.dcf_terminal_g == pytest.approx(0.025)
    assert result.dcf_years == 7


def _create_legacy_watchlist_db(path: str) -> None:
    # Schema as it shipped before #18: NOT NULL columns with hardcoded defaults.
    conn = sqlite3.connect(path)
    conn.execute("""
        CREATE TABLE watchlist (
            ticker TEXT PRIMARY KEY,
            company_name TEXT,
            currency TEXT,
            mos_override REAL,
            dcf_growth_override REAL,
            dcf_wacc_override REAL,
            dcf_terminal_g REAL NOT NULL DEFAULT 0.03,
            dcf_years INTEGER NOT NULL DEFAULT 10,
            added_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.execute("INSERT INTO watchlist (ticker, company_name, currency) VALUES ('AAPL', 'Apple Inc.', 'USD')")
    conn.execute(
        "INSERT INTO watchlist (ticker, mos_override, dcf_terminal_g, dcf_years)"
        " VALUES ('CEZ.PR', 0.30, 0.02, 5)"
    )
    conn.commit()
    conn.close()


def test_legacy_db_loads_and_column_defaults_become_unset(tmp_path: Path) -> None:
    db = str(tmp_path / "legacy.db")
    _create_legacy_watchlist_db(db)

    wl = Watchlist(db_path=db)

    aapl = wl.get_overrides("AAPL")
    assert aapl is not None
    assert aapl.dcf_terminal_g is None
    assert aapl.dcf_years is None
    entries = {e.ticker: e for e in wl.get_all_entries()}
    assert entries["AAPL"].company_name == "Apple Inc."
    assert entries["AAPL"].currency == "USD"


def test_legacy_db_keeps_explicit_values(tmp_path: Path) -> None:
    db = str(tmp_path / "legacy.db")
    _create_legacy_watchlist_db(db)

    cez = Watchlist(db_path=db).get_overrides("CEZ.PR")
    assert cez is not None
    assert cez.mos_override == pytest.approx(0.30)
    assert cez.dcf_terminal_g == pytest.approx(0.02)
    assert cez.dcf_years == 5


def test_legacy_db_accepts_unset_overrides_after_load(tmp_path: Path) -> None:
    db = str(tmp_path / "legacy.db")
    _create_legacy_watchlist_db(db)

    wl = Watchlist(db_path=db)
    wl.set_overrides("CEZ.PR", TickerOverrides(mos_override=0.30))
    cez = wl.get_overrides("CEZ.PR")
    assert cez is not None
    assert cez.dcf_terminal_g is None
    assert cez.dcf_years is None
    # reopening an already-migrated DB is a no-op
    reopened = Watchlist(db_path=db)
    assert reopened.tickers() == wl.tickers()
    assert reopened.get_overrides("CEZ.PR") == cez


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


def test_every_valuation_column_roundtrips_to_its_own_field(wl: Watchlist) -> None:
    # get_valuations reads columns by position; distinct values catch a shifted index.
    saved = ValuationResult(
        ticker="ASML",
        fair_values={"dcf": 610.0, "graham": None},
        fair_value_composite=650.0,
        fair_value_low=600.0,
        fair_value_high=700.0,
        fair_value_cv=0.07,
        current_price=640.0,
        currency="EUR",
        master_score=1.5,
        buy_target=520.0,
        signal="WAIT",
        warnings=["w"],
    )
    wl.save_valuation(saved)
    assert wl.get_valuations() == [saved]
