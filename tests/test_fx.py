import pytest

from stock_picking.data.models import FinancialData
from stock_picking.fx import convert_to_quote_currency


@pytest.fixture
def eur_statements_usd_quote() -> FinancialData:
    return FinancialData(
        ticker="ADR",
        currency="USD",
        financial_currency="EUR",
        current_price=25.0,
        eps_ttm=2.0,
        bvps=10.0,
        fcf_history=[100.0, 200.0],
        ebitda=50.0,
        ev=400.0,
        total_debt=30.0,
        cash=20.0,
        shares_outstanding=1000.0,
        pe_history=[15.0, 16.0],
        ev_ebitda_history=[8.0, 9.0],
    )


def test_converts_monetary_fields_by_rate(eur_statements_usd_quote: FinancialData) -> None:
    # EURUSD = 1.1 USD per 1 EUR, every monetary field x 1.1:
    #   EPS 2.0 -> 2.2, BVPS 10 -> 11, FCF [100, 200] -> [110, 220],
    #   EBITDA 50 -> 55, EV 400 -> 440, debt 30 -> 33, cash 20 -> 22
    out = convert_to_quote_currency(eur_statements_usd_quote, 1.1)

    assert out.eps_ttm == pytest.approx(2.2)
    assert out.bvps == pytest.approx(11.0)
    assert out.fcf_history == pytest.approx([110.0, 220.0])
    assert out.ebitda == pytest.approx(55.0)
    assert out.ev == pytest.approx(440.0)
    assert out.total_debt == pytest.approx(33.0)
    assert out.cash == pytest.approx(22.0)
    assert out.financial_currency == "USD"


def test_does_not_convert_price_share_count_or_ratios(
    eur_statements_usd_quote: FinancialData,
) -> None:
    out = convert_to_quote_currency(eur_statements_usd_quote, 1.1)

    assert out.current_price == 25.0
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


def test_same_currency_is_noop(eur_statements_usd_quote: FinancialData) -> None:
    same = eur_statements_usd_quote.model_copy(update={"financial_currency": "USD"})
    assert convert_to_quote_currency(same, 1.1) == same


def test_unknown_financial_currency_is_noop(eur_statements_usd_quote: FinancialData) -> None:
    unknown = eur_statements_usd_quote.model_copy(update={"financial_currency": None})
    assert convert_to_quote_currency(unknown, 1.1) == unknown
