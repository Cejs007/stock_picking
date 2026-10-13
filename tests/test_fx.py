import pytest

from stock_picking.data.models import FinancialData
from stock_picking.fx import convert_to_quote_currency


@pytest.fixture
def twd_statements_usd_quote() -> FinancialData:
    # Shaped like TSM on yfinance: statement totals in TWD, but the per-share
    # `info` fields (trailingEps, bookValue) already in the USD quote currency.
    return FinancialData(
        ticker="TSM",
        currency="USD",
        financial_currency="TWD",
        current_price=200.0,
        eps_ttm=8.0,
        bvps=40.0,
        fcf_history=[3000.0, 6000.0],
        ebitda=3200.0,
        ev=16000.0,
        total_debt=1000.0,
        cash=3500.0,
        shares_outstanding=1000.0,
        pe_history=[15.0, 16.0],
        ev_ebitda_history=[8.0, 9.0],
    )


def test_converts_statement_currency_totals_by_rate(twd_statements_usd_quote: FinancialData) -> None:
    # TWDUSD = 1/32 = 0.03125 USD per 1 TWD, so every statement total / 32:
    #   FCF [3000, 6000] -> [93.75, 187.5], EBITDA 3200 -> 100, EV 16000 -> 500,
    #   debt 1000 -> 31.25, cash 3500 -> 109.375
    out = convert_to_quote_currency(twd_statements_usd_quote, 0.03125)

    assert out.fcf_history == pytest.approx([93.75, 187.5])
    assert out.ebitda == pytest.approx(100.0)
    assert out.ev == pytest.approx(500.0)
    assert out.total_debt == pytest.approx(31.25)
    assert out.cash == pytest.approx(109.375)
    assert out.financial_currency == "USD"


def test_quote_currency_per_share_fields_are_not_converted(
    twd_statements_usd_quote: FinancialData,
) -> None:
    # yfinance trailingEps / bookValue are already in the quote currency
    # (TSM: price / trailingEps == trailingPE), so converting them again
    # would make EPS 32x too small.
    out = convert_to_quote_currency(twd_statements_usd_quote, 0.03125)

    assert out.eps_ttm == 8.0
    assert out.bvps == 40.0


def test_does_not_convert_price_share_count_or_ratios(
    twd_statements_usd_quote: FinancialData,
) -> None:
    out = convert_to_quote_currency(twd_statements_usd_quote, 0.03125)

    assert out.current_price == 200.0
    assert out.currency == "USD"
    assert out.shares_outstanding == 1000.0
    assert out.pe_history == [15.0, 16.0]
    assert out.ev_ebitda_history == [8.0, 9.0]


def test_missing_monetary_fields_stay_none() -> None:
    fin = FinancialData(ticker="X", currency="USD", financial_currency="EUR", current_price=10.0)
    out = convert_to_quote_currency(fin, 1.1)

    assert out.eps_ttm is None
    assert out.bvps is None
    assert out.ebitda is None
    assert out.ev is None
    assert out.fcf_history == []


def test_same_currency_is_noop(twd_statements_usd_quote: FinancialData) -> None:
    same = twd_statements_usd_quote.model_copy(update={"financial_currency": "USD"})
    assert convert_to_quote_currency(same, 1.1) == same


def test_unknown_financial_currency_is_noop(twd_statements_usd_quote: FinancialData) -> None:
    unknown = twd_statements_usd_quote.model_copy(update={"financial_currency": None})
    assert convert_to_quote_currency(unknown, 1.1) == unknown
