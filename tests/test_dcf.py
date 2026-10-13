import pytest

from stock_picking.data.models import FinancialData, ModelConfig
from stock_picking.models.dcf import calculate


def test_happy_path(fin: FinancialData, cfg: ModelConfig) -> None:
    result, warnings = calculate(fin, cfg)
    # CAGR(80→100 over 4 steps) ≈ 5.74%; DCF with WACC=10%, terminal_g=3%, 10 years ≈ 180
    assert result == pytest.approx(180, rel=0.01)
    assert warnings == []


def test_all_negative_fcf_returns_none(fin: FinancialData, cfg: ModelConfig) -> None:
    result, warnings = calculate(
        fin.model_copy(update={"fcf_history": [-80.0, -85.0, -90.0]}), cfg
    )
    assert result is None
    assert any("FCF" in w for w in warnings)


def test_empty_fcf_history_returns_none(fin: FinancialData, cfg: ModelConfig) -> None:
    result, warnings = calculate(fin.model_copy(update={"fcf_history": []}), cfg)
    assert result is None
    assert any("FCF" in w for w in warnings)


def test_no_shares_returns_none(fin: FinancialData, cfg: ModelConfig) -> None:
    result, warnings = calculate(fin.model_copy(update={"shares_outstanding": None}), cfg)
    assert result is None
    assert any("shares" in w.lower() for w in warnings)


def test_growth_rate_override_lowers_value(fin: FinancialData, cfg: ModelConfig) -> None:
    # g=0% < auto CAGR ≈ 5.74% → lower DCF value
    result_auto, _ = calculate(fin, cfg)
    result_zero, _ = calculate(fin, cfg.model_copy(update={"growth_rate_override": 0.0}))
    assert result_zero is not None
    assert result_auto is not None
    assert result_zero < result_auto


def test_growth_rate_override_zero(fin: FinancialData, cfg: ModelConfig) -> None:
    # With g=0: PV_FCFs ≈ 61.45, PV_TV ≈ 56.73 → ≈ 118.18
    result, warnings = calculate(fin, cfg.model_copy(update={"growth_rate_override": 0.0}))
    assert result == pytest.approx(118, rel=0.01)
    assert warnings == []


@pytest.mark.parametrize("terminal_g", [0.10, 0.12])
def test_wacc_not_above_terminal_growth_returns_none(
    fin: FinancialData, cfg: ModelConfig, terminal_g: float
) -> None:
    # WACC=10%: g=10% divides by zero, g=12% gives a negative terminal value
    result, warnings = calculate(
        fin, cfg.model_copy(update={"terminal_growth_rate": terminal_g})
    )
    assert result is None
    assert any("WACC" in w for w in warnings)


@pytest.fixture
def one_year_cfg(cfg: ModelConfig) -> ModelConfig:
    # With 1 projection year DCF collapses to Gordon: FCF1 / (WACC - g_t)
    # (FCF1/1.1 + FCF1*1.03/0.07/1.1 = FCF1/1.1 * 1.1/0.07 = FCF1/0.07)
    return cfg.model_copy(update={"projection_years": 1})


def test_auto_growth_above_max_is_clamped(
    fin: FinancialData, one_year_cfg: ModelConfig
) -> None:
    # CAGR(10→20, 1 step) = 100% → clamped to 15%; base FCF/share = 20/1
    # 20 * 1.15 / 0.07 = 23 / 0.07 = 328.571
    data = fin.model_copy(update={"fcf_history": [10.0, 20.0], "shares_outstanding": 1.0})
    result, warnings = calculate(data, one_year_cfg)
    assert result == pytest.approx(328.571, rel=1e-4)
    assert len(warnings) == 1
    assert "100.0%" in warnings[0] and "15.0%" in warnings[0]


def test_auto_growth_below_min_is_clamped(
    fin: FinancialData, one_year_cfg: ModelConfig
) -> None:
    # CAGR(20→10, 1 step) = -50% → clamped to -5%; base FCF/share = 10/1
    # 10 * 0.95 / 0.07 = 9.5 / 0.07 = 135.714
    data = fin.model_copy(update={"fcf_history": [20.0, 10.0], "shares_outstanding": 1.0})
    result, warnings = calculate(data, one_year_cfg)
    assert result == pytest.approx(135.714, rel=1e-4)
    assert len(warnings) == 1
    assert "-50.0%" in warnings[0] and "-5.0%" in warnings[0]


def test_growth_override_outside_bounds_is_not_clamped(
    fin: FinancialData, one_year_cfg: ModelConfig
) -> None:
    # Override 50% used as-is; base FCF/share = 100/10 = 10
    # 10 * 1.5 / 0.07 = 15 / 0.07 = 214.286
    result, warnings = calculate(
        fin, one_year_cfg.model_copy(update={"growth_rate_override": 0.50})
    )
    assert result == pytest.approx(214.286, rel=1e-4)
    assert warnings == []


def test_auto_growth_bounds_are_configurable(
    fin: FinancialData, one_year_cfg: ModelConfig
) -> None:
    # CAGR 100% → clamped to configured max 30%; base FCF/share = 20
    # 20 * 1.3 / 0.07 = 26 / 0.07 = 371.429
    data = fin.model_copy(update={"fcf_history": [10.0, 20.0], "shares_outstanding": 1.0})
    result, warnings = calculate(
        data, one_year_cfg.model_copy(update={"auto_growth_max": 0.30})
    )
    assert result == pytest.approx(371.429, rel=1e-4)
    assert "30.0%" in warnings[0]


def test_auto_growth_min_is_configurable(
    fin: FinancialData, one_year_cfg: ModelConfig
) -> None:
    # CAGR -50% → clamped to configured min -20%; base FCF/share = 10
    # 10 * 0.8 / 0.07 = 8 / 0.07 = 114.286
    data = fin.model_copy(update={"fcf_history": [20.0, 10.0], "shares_outstanding": 1.0})
    result, warnings = calculate(
        data, one_year_cfg.model_copy(update={"auto_growth_min": -0.20})
    )
    assert result == pytest.approx(114.286, rel=1e-4)
    assert "-20.0%" in warnings[0]
