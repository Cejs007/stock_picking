import pytest

from stock_picking.data.models import FinancialData
from stock_picking.fx import convert_to_quote_currency, fx_pair, quote_rate


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


@pytest.mark.parametrize(
    ("from_ccy", "to_ccy", "pair"),
    [
        ("EUR", "USD", ("EUR", "USD")),
        # Minor-unit quotes are normalised to their major currency; Yahoo
        # returns USDGBp=X in pounds and has no ILA=X pair at all.
        ("USD", "GBp", ("USD", "GBP")),
        ("USD", "GBX", ("USD", "GBP")),
        ("USD", "ZAc", ("USD", "ZAR")),
        ("USD", "ILA", ("USD", "ILS")),
    ],
)
def test_fx_pair_uses_major_currencies(from_ccy: str, to_ccy: str, pair: tuple[str, str]) -> None:
    assert fx_pair(from_ccy, to_ccy) == pair


@pytest.mark.parametrize(("from_ccy", "to_ccy"), [("GBP", "GBp"), ("ZAR", "ZAc"), ("CZK", "CZK")])
def test_fx_pair_is_none_when_currencies_differ_only_by_unit(from_ccy: str, to_ccy: str) -> None:
    assert fx_pair(from_ccy, to_ccy) is None


@pytest.mark.parametrize(
    ("from_ccy", "to_ccy", "major_rate", "expected"),
    [
        # 0.75 GBP per USD * 100 pence per GBP = 75 GBp per USD
        ("USD", "GBp", 0.75, 75.0),
        # 16.5 ZAR per USD * 100 cents per ZAR = 1650 ZAc per USD
        ("USD", "ZAc", 16.5, 1650.0),
        # GBP statements, GBp quote: no market rate, 1 GBP = 100 GBp
        ("GBP", "GBp", 1.0, 100.0),
        # Plain major pair passes the market rate through
        ("EUR", "USD", 1.1, 1.1),
        ("CZK", "CZK", 1.0, 1.0),
    ],
)
def test_quote_rate_scales_into_minor_unit(
    from_ccy: str, to_ccy: str, major_rate: float, expected: float
) -> None:
    assert quote_rate(from_ccy, to_ccy, major_rate) == pytest.approx(expected)
