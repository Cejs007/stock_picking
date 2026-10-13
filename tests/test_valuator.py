import math

import pytest

from stock_picking.data.models import FinancialData, ModelConfig
from stock_picking.settings import Settings
from stock_picking.valuator import valuate
from stock_picking.watchlist import TickerOverrides, ValuationResult


def test_returns_valuation_result(fin: FinancialData) -> None:
    result = valuate(fin, Settings())
    assert isinstance(result, ValuationResult)
    assert result.ticker == "TEST"
    assert result.current_price == 100.0


def test_composite_uses_default_fallback_weights(fin: FinancialData) -> None:
    # fin has no sector -> valuator uses the default fallback weights
    # {graham: 0, pe_relative: 1.5, ev_ebitda: 1.0, dcf: 1.0}.
    #   P/E = median([15..19]) * 5 = 85.0
    #   EV/EBITDA = (median([8..12])*20 - 30 + 10) / 10 = 18.0
    #   DCF (CAGR auto, WACC 10%, terminal 3%, 10yr)
    settings = Settings()
    w = settings.weights_for(None)
    result = valuate(fin, settings)
    dcf_fv = result.fair_value_dcf
    assert dcf_fv is not None
    pe_fv, ev_fv = 85.0, 18.0
    total = w["graham"] * 0 + w["pe_relative"] + w["ev_ebitda"] + w["dcf"]
    expected = (pe_fv * w["pe_relative"] + ev_fv * w["ev_ebitda"]
                + dcf_fv * w["dcf"]) / total
    assert result.fair_value_composite == pytest.approx(expected, rel=1e-6)


def test_master_score_is_upside_percent(fin: FinancialData) -> None:
    result = valuate(fin, Settings())
    assert result.fair_value_composite is not None
    assert result.master_score is not None
    expected = (result.fair_value_composite - fin.current_price) / fin.current_price * 100
    assert result.master_score == pytest.approx(expected, rel=1e-6)


def test_buy_target_applies_mos(fin: FinancialData) -> None:
    settings = Settings()
    result = valuate(fin, settings)
    assert result.fair_value_composite is not None
    assert result.buy_target == pytest.approx(result.fair_value_composite * (1 - settings.default_mos))


def test_signal_wait_when_price_above_buy_target(fin: FinancialData) -> None:
    # current_price=100, composite≈87.5, buy_target≈65.6 → WAIT
    result = valuate(fin, Settings())
    assert result.signal == "WAIT"


def test_signal_buy_when_price_at_or_below_buy_target(fin: FinancialData) -> None:
    # current_price=50 < buy_target (composite stays same, target≈65.6) → BUY
    cheap = fin.model_copy(update={"current_price": 50.0})
    result = valuate(cheap, Settings())
    assert result.signal == "BUY"


def test_mos_override_changes_buy_target(fin: FinancialData) -> None:
    # MoS 0% → buy_target = composite; MoS 50% → buy_target = composite * 0.5
    result_no_mos = valuate(fin, Settings(), TickerOverrides(mos_override=0.0))
    result_half_mos = valuate(fin, Settings(), TickerOverrides(mos_override=0.5))
    assert result_no_mos.buy_target is not None
    assert result_half_mos.buy_target is not None
    assert result_no_mos.buy_target == pytest.approx(result_no_mos.fair_value_composite)
    assert result_half_mos.buy_target == pytest.approx(result_half_mos.fair_value_composite * 0.5)  # type: ignore[operator]


def test_wacc_override_lowers_dcf_when_increased(fin: FinancialData) -> None:
    # Higher WACC → lower DCF fair value
    result_default = valuate(fin, Settings())
    result_high_wacc = valuate(fin, Settings(), TickerOverrides(dcf_wacc_override=0.20))
    assert result_default.fair_value_dcf is not None
    assert result_high_wacc.fair_value_dcf is not None
    assert result_high_wacc.fair_value_dcf < result_default.fair_value_dcf


def test_growth_rate_override_flows_into_dcf(fin: FinancialData) -> None:
    # g=0% < auto CAGR ≈ 5.74% → lower DCF
    result_auto = valuate(fin, Settings())
    result_zero_g = valuate(fin, Settings(), TickerOverrides(dcf_growth_override=0.0))
    assert result_auto.fair_value_dcf is not None
    assert result_zero_g.fair_value_dcf is not None
    assert result_zero_g.fair_value_dcf < result_auto.fair_value_dcf


def test_one_model_unavailable_composite_from_remaining(fin: FinancialData) -> None:
    # eps_ttm=None → Graham and P/E both N/A; composite uses only EV/EBITDA + DCF
    no_eps = fin.model_copy(update={"eps_ttm": None})
    result = valuate(no_eps, Settings())
    assert result.fair_value_graham is None
    assert result.fair_value_pe is None
    assert result.fair_value_composite is not None
    # composite = (ev_ebitda + dcf) / 2  (equal weights renormalized)
    assert result.fair_value_ev_ebitda is not None
    assert result.fair_value_dcf is not None
    expected = (result.fair_value_ev_ebitda + result.fair_value_dcf) / 2
    assert result.fair_value_composite == pytest.approx(expected, rel=1e-6)
    assert any("EPS" in w for w in result.warnings)


def test_all_models_unavailable_returns_none_composite_and_na_signal(fin: FinancialData) -> None:
    # Strip everything that every model needs
    broken = fin.model_copy(update={
        "eps_ttm": None,       # kills Graham + P/E
        "bvps": None,
        "ebitda": None,        # kills EV/EBITDA
        "shares_outstanding": None,  # kills EV/EBITDA + DCF
        "fcf_history": [],     # kills DCF
    })
    result = valuate(broken, Settings())
    assert result.fair_value_composite is None
    assert result.master_score is None
    assert result.buy_target is None
    assert result.signal == "N/A"


def test_result_carries_quote_currency(fin: FinancialData) -> None:
    czk = fin.model_copy(update={"currency": "CZK", "financial_currency": "CZK"})
    result = valuate(czk, Settings())
    assert result.currency == "CZK"


def test_unconverted_fundamentals_give_na_signal_with_reason(fin: FinancialData) -> None:
    # Price 1.0 is far below every model's fair value (P/E alone = 85), so with
    # matching currencies this is a BUY.
    cheap = fin.model_copy(update={"current_price": 1.0, "financial_currency": "USD"})
    assert valuate(cheap, Settings()).signal == "BUY"

    # FX rate was unavailable upstream: statements still in EUR, quote in USD.
    # The fair values would mix EUR totals with a USD price, so nothing is
    # valued or ranked.
    mismatched = cheap.model_copy(update={"financial_currency": "EUR"})
    result = valuate(mismatched, Settings())

    assert result.signal == "N/A"
    assert result.fair_value_composite is None
    assert result.master_score is None
    assert result.buy_target is None
    assert result.fair_value_dcf is None
    assert result.fair_value_ev_ebitda is None
    assert result.fair_value_graham is None
    assert result.fair_value_pe is None
    assert result.currency == "USD"
    assert any("EUR" in w and "USD" in w and "not converted" in w for w in result.warnings)


def test_unknown_statement_currency_gives_na_signal_with_reason(fin: FinancialData) -> None:
    # Cache entries written before financial_currency existed load with None:
    # we can't tell whether the totals are in the quote currency.
    cheap = fin.model_copy(update={"current_price": 1.0, "financial_currency": None})
    result = valuate(cheap, Settings())

    assert result.signal == "N/A"
    assert result.fair_value_composite is None
    assert result.master_score is None
    assert any("Statement currency unknown" in w for w in result.warnings)


def test_matching_currencies_produce_no_currency_warning(fin: FinancialData) -> None:
    matched = fin.model_copy(update={"currency": "USD", "financial_currency": "USD"})
    result = valuate(matched, Settings())
    assert not any("currency" in w.lower() for w in result.warnings)
