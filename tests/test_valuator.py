import math
from datetime import UTC, datetime, tzinfo
from unittest.mock import patch

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
    dcf_fv = result.fair_values["dcf"]
    assert dcf_fv is not None
    pe_fv, ev_fv = 85.0, 18.0
    total = w["graham"] * 0 + w["pe_relative"] + w["ev_ebitda"] + w["dcf"]
    expected = (pe_fv * w["pe_relative"] + ev_fv * w["ev_ebitda"]
                + dcf_fv * w["dcf"]) / total
    assert result.fair_value_composite == pytest.approx(expected, rel=1e-6)


def test_fair_value_range_and_disagreement(fin: FinancialData) -> None:
    # Only Graham and P/E active (weights 1:1, no sector -> model_weights).
    #   Graham = sqrt(22.5 * 5 * 40) = 67.0820, P/E = 85.0
    #   mean = 76.0410, population std = (85 - 67.0820) / 2 = 8.9590
    #   CV = 8.9590 / 76.0410 = 0.117818
    result = valuate(fin, Settings(model_weights={"graham": 1.0, "pe_relative": 1.0}))
    assert result.fair_value_low == pytest.approx(67.0820, rel=1e-5)
    assert result.fair_value_high == pytest.approx(85.0)
    assert result.fair_value_cv == pytest.approx(0.117818, rel=1e-5)


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
    assert result_default.fair_values["dcf"] is not None
    assert result_high_wacc.fair_values["dcf"] is not None
    assert result_high_wacc.fair_values["dcf"] < result_default.fair_values["dcf"]


def test_growth_rate_override_flows_into_dcf(fin: FinancialData) -> None:
    # g=0% < auto CAGR ≈ 5.74% → lower DCF
    result_auto = valuate(fin, Settings())
    result_zero_g = valuate(fin, Settings(), TickerOverrides(dcf_growth_override=0.0))
    assert result_auto.fair_values["dcf"] is not None
    assert result_zero_g.fair_values["dcf"] is not None
    assert result_zero_g.fair_values["dcf"] < result_auto.fair_values["dcf"]


def test_unset_terminal_g_and_years_fall_back_to_settings(fin: FinancialData) -> None:
    # Base FCF = avg(90, 95, 100) = 95, g0 = 0, WACC 10%, terminal g 5% (settings),
    # 1 year (settings) so year-1 growth is already terminal 5%:
    #   FCF1 = 95*1.05 = 99.75; TV = 99.75*1.05/0.05 = 2094.75
    #   EV = (99.75 + 2094.75)/1.1 = 1995; minus net debt 20 → 1975/10 shares = 197.5
    settings = Settings(default_terminal_g=0.05, default_projection_years=1)
    result = valuate(fin, settings, TickerOverrides(dcf_growth_override=0.0))
    assert result.fair_values["dcf"] == pytest.approx(197.5)


def test_explicit_terminal_g_and_years_override_settings(fin: FinancialData) -> None:
    # g0 = 0, WACC 10%, terminal g 5% (override), 2 years (override), growth [0%, 5%]:
    #   FCF1 = 95; FCF2 = 99.75; TV = 2094.75
    #   EV = (95*1.1 + 99.75 + 2094.75)/1.21 = 2299/1.21 = 1900; (1900 - 20)/10 = 188.0
    settings = Settings(default_terminal_g=0.0, default_projection_years=10)
    overrides = TickerOverrides(dcf_growth_override=0.0, dcf_terminal_g=0.05, dcf_years=2)
    result = valuate(fin, settings, overrides)
    assert result.fair_values["dcf"] == pytest.approx(188.0)


def test_terminal_g_override_alone_keeps_settings_years(fin: FinancialData) -> None:
    # terminal g 5% from override, 2 years from settings -> 188.0 (as above)
    settings = Settings(default_terminal_g=0.0, default_projection_years=2)
    overrides = TickerOverrides(dcf_growth_override=0.0, dcf_terminal_g=0.05)
    result = valuate(fin, settings, overrides)
    assert result.fair_values["dcf"] == pytest.approx(188.0)


def test_zero_terminal_g_override_is_applied_not_treated_as_unset(fin: FinancialData) -> None:
    # terminal g 0% from override (settings say 5%), 2 years, growth [0%, 0%]:
    #   EV = (95*1.1 + 95 + 95/0.10)/1.21 = 1149.5/1.21 = 950; (950 - 20)/10 = 93.0
    #   (settings' 5% would give 188.0)
    settings = Settings(default_terminal_g=0.05, default_projection_years=2)
    overrides = TickerOverrides(dcf_growth_override=0.0, dcf_terminal_g=0.0)
    result = valuate(fin, settings, overrides)
    assert result.fair_values["dcf"] == pytest.approx(93.0)


def test_years_override_alone_keeps_settings_terminal_g(fin: FinancialData) -> None:
    # 1 year from override, terminal g 5% from settings -> 197.5 (as in the first case)
    settings = Settings(default_terminal_g=0.05, default_projection_years=10)
    overrides = TickerOverrides(dcf_growth_override=0.0, dcf_years=1)
    result = valuate(fin, settings, overrides)
    assert result.fair_values["dcf"] == pytest.approx(197.5)


def test_one_model_unavailable_composite_from_remaining(fin: FinancialData) -> None:
    # eps_ttm=None → Graham and P/E both N/A; composite uses only EV/EBITDA + DCF
    no_eps = fin.model_copy(update={"eps_ttm": None})
    result = valuate(no_eps, Settings())
    assert result.fair_values["graham"] is None
    assert result.fair_values["pe_relative"] is None
    assert result.fair_value_composite is not None
    # composite = (ev_ebitda + dcf) / 2  (equal weights renormalized)
    assert result.fair_values["ev_ebitda"] is not None
    assert result.fair_values["dcf"] is not None
    expected = (result.fair_values["ev_ebitda"] + result.fair_values["dcf"]) / 2
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
    assert result.fair_value_low is None
    assert result.fair_value_high is None
    assert result.fair_value_cv is None
    assert result.master_score is None
    assert result.buy_target is None
    assert result.signal == "N/A"


def test_each_valuation_gets_its_own_calculation_time(fin: FinancialData) -> None:
    # Fake clock: each datetime.now() call returns the next tick, so the two
    # valuations are "created at different times" without sleeping.
    ticks = iter([
        datetime(2026, 1, 1, 9, 0, tzinfo=UTC),
        datetime(2026, 1, 1, 9, 5, tzinfo=UTC),
    ])

    class _FakeClock(datetime):
        @classmethod
        def now(cls, tz: tzinfo | None = None) -> datetime:  # type: ignore[override]
            return next(ticks)

    with patch("stock_picking.watchlist.datetime", _FakeClock):
        first = valuate(fin, Settings())
        second = valuate(fin, Settings())

    assert first.calculated_at == datetime(2026, 1, 1, 9, 0, tzinfo=UTC)
    assert second.calculated_at == datetime(2026, 1, 1, 9, 5, tzinfo=UTC)
