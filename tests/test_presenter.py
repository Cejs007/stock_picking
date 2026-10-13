import pytest

from stock_picking.ui.presenter import build_dashboard_rows, format_currency, format_percent
from stock_picking.watchlist import ValuationResult


def test_format_currency_usd() -> None:
    assert format_currency(123.45, "USD") == "$123.45"


def test_format_currency_none_returns_na() -> None:
    assert format_currency(None, "USD") == "N/A"


def test_format_currency_eur() -> None:
    assert format_currency(50.0, "EUR") == "€50.00"


def test_format_currency_unknown_currency_uses_code_prefix() -> None:
    assert format_currency(99.99, "CZK") == "CZK 99.99"


def test_format_percent_positive() -> None:
    assert format_percent(12.3) == "+12.3%"


def test_format_percent_negative() -> None:
    assert format_percent(-5.0) == "-5.0%"


def test_format_percent_zero() -> None:
    assert format_percent(0.0) == "+0.0%"


def test_format_percent_none_returns_na() -> None:
    assert format_percent(None) == "N/A"


@pytest.fixture
def result() -> ValuationResult:
    return ValuationResult(
        ticker="AAPL",
        fair_values={"graham": 130.0, "pe_relative": 150.0, "ev_ebitda": 140.0, "dcf": 160.0},
        fair_value_composite=145.0,
        current_price=100.0,
        master_score=45.0,
        buy_target=108.75,
        signal="BUY",
        warnings=[],
    )


def test_build_dashboard_rows_empty_list() -> None:
    assert build_dashboard_rows([]) == []


def test_build_dashboard_rows_single_result_has_expected_keys(result: ValuationResult) -> None:
    rows = build_dashboard_rows([result])
    assert len(rows) == 1
    row = rows[0]
    expected_keys = {"Ticker", "Price", "Fair Value", "Upside", "Buy Target", "Signal",
                     "Graham", "P/E", "EV/EBITDA", "DCF"}
    assert expected_keys.issubset(row.keys())


def test_build_dashboard_rows_sorted_by_upside_descending(result: ValuationResult) -> None:
    low = result.model_copy(update={"ticker": "LOW", "master_score": 10.0})
    high = result.model_copy(update={"ticker": "HIGH", "master_score": 80.0})
    no_score = result.model_copy(update={"ticker": "NA", "master_score": None, "signal": "N/A"})
    rows = build_dashboard_rows([low, no_score, high])
    assert [r["Ticker"] for r in rows] == ["HIGH", "LOW", "NA"]


def test_build_dashboard_rows_none_composite_shows_na(result: ValuationResult) -> None:
    no_composite = result.model_copy(update={
        "fair_value_composite": None,
        "master_score": None,
        "buy_target": None,
        "signal": "N/A",
    })
    row = build_dashboard_rows([no_composite])[0]
    assert row["Fair Value"] == "N/A"
    assert row["Upside"] == "N/A"
    assert row["Buy Target"] == "N/A"
    assert row["Signal"] == "N/A"


def test_build_dashboard_rows_formats_values(result: ValuationResult) -> None:
    row = build_dashboard_rows([result])[0]
    assert row["Ticker"] == "AAPL"
    assert row["Price"] == "$100.00"
    assert row["Fair Value"] == "$145.00"
    assert row["Upside"] == "+45.0%"
    assert row["Buy Target"] == "$108.75"
    assert row["Signal"] == "BUY"
    assert row["Graham"] == "$130.00"
    assert row["P/E"] == "$150.00"
    assert row["EV/EBITDA"] == "$140.00"
    assert row["DCF"] == "$160.00"
