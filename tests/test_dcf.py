import pytest

from stock_picking.data.models import FinancialData, ModelConfig
from stock_picking.models.dcf import calculate, growth_path


def test_happy_path(fin: FinancialData, cfg: ModelConfig) -> None:
    result, warnings = calculate(fin, cfg)
    # Base = avg(90, 95, 100)/10 shares = 9.5/share; g0 = CAGR(80→100, 4 steps) = 5.737%
    # fading by -0.304 pp/yr to 3.0% in year 10; WACC 10%, terminal 3%
    # EV/share = 156.367; net debt (30 - 10)/10 = 2.0 → 154.367
    assert result == pytest.approx(154.367, rel=1e-4)
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
    # Base 9.5/share; g fades 0% → 3% by +0.333 pp/yr over 10 years; WACC 10%, terminal 3%
    # EV/share = 123.467; minus net debt 2.0/share → 121.467
    result, warnings = calculate(fin, cfg.model_copy(update={"growth_rate_override": 0.0}))
    assert result == pytest.approx(121.467, rel=1e-4)
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
def two_year_cfg(cfg: ModelConfig) -> ModelConfig:
    # 2 projection years: growth g0 in year 1, terminal 3% in year 2, so DCF collapses
    # to Gordon on year 1: FCF1/1.1 + FCF1*1.03/0.07/1.1 = FCF1/1.1 * 1.1/0.07 = FCF1/0.07
    return cfg.model_copy(update={"projection_years": 2})


@pytest.fixture
def debt_free(fin: FinancialData) -> FinancialData:
    return fin.model_copy(update={"total_debt": 0.0, "cash": 0.0, "shares_outstanding": 1.0})


def test_auto_growth_above_max_is_clamped(
    debt_free: FinancialData, two_year_cfg: ModelConfig
) -> None:
    # CAGR(10→30, 2 steps) = sqrt(3) - 1 = 73.2% → clamped to 15%; base = avg = 20
    # 20 * 1.15 / 0.07 = 23 / 0.07 = 328.571
    data = debt_free.model_copy(update={"fcf_history": [10.0, 20.0, 30.0]})
    result, warnings = calculate(data, two_year_cfg)
    assert result == pytest.approx(328.571, rel=1e-4)
    assert len(warnings) == 1
    assert "73.2%" in warnings[0] and "15.0%" in warnings[0]


def test_auto_growth_below_min_is_clamped(
    debt_free: FinancialData, two_year_cfg: ModelConfig
) -> None:
    # CAGR(30→10, 2 steps) = sqrt(1/3) - 1 = -42.3% → clamped to -5%; base = avg = 20
    # 20 * 0.95 / 0.07 = 19 / 0.07 = 271.429
    data = debt_free.model_copy(update={"fcf_history": [30.0, 20.0, 10.0]})
    result, warnings = calculate(data, two_year_cfg)
    assert result == pytest.approx(271.429, rel=1e-4)
    assert len(warnings) == 1
    assert "-42.3%" in warnings[0] and "-5.0%" in warnings[0]


def test_growth_override_outside_bounds_is_not_clamped(
    debt_free: FinancialData, two_year_cfg: ModelConfig
) -> None:
    # Override 50% used as-is; base = avg(90, 95, 100) = 95
    # 95 * 1.5 / 0.07 = 142.5 / 0.07 = 2035.714
    result, warnings = calculate(
        debt_free, two_year_cfg.model_copy(update={"growth_rate_override": 0.50})
    )
    assert result == pytest.approx(2035.714, rel=1e-4)
    assert warnings == []


def test_auto_growth_bounds_are_configurable(
    debt_free: FinancialData, two_year_cfg: ModelConfig
) -> None:
    # CAGR 73.2% → clamped to configured max 30%; base = 20
    # 20 * 1.3 / 0.07 = 26 / 0.07 = 371.429
    data = debt_free.model_copy(update={"fcf_history": [10.0, 20.0, 30.0]})
    result, warnings = calculate(
        data, two_year_cfg.model_copy(update={"auto_growth_max": 0.30})
    )
    assert result == pytest.approx(371.429, rel=1e-4)
    assert "30.0%" in warnings[0]


def test_auto_growth_min_is_configurable(
    debt_free: FinancialData, two_year_cfg: ModelConfig
) -> None:
    # CAGR -42.3% → clamped to configured min -20%; base = avg(30, 20, 10) = 20
    # 20 * 0.8 / 0.07 = 16 / 0.07 = 228.571
    data = debt_free.model_copy(update={"fcf_history": [30.0, 20.0, 10.0]})
    result, warnings = calculate(
        data, two_year_cfg.model_copy(update={"auto_growth_min": -0.20})
    )
    assert result == pytest.approx(228.571, rel=1e-4)
    assert "-20.0%" in warnings[0]


@pytest.fixture
def v2_fin(fin: FinancialData) -> FinancialData:
    # Base FCF = avg(90, 100, 110) = 100 (total); debt 300, cash 100, 10 shares
    return fin.model_copy(
        update={
            "fcf_history": [90.0, 100.0, 110.0],
            "total_debt": 300.0,
            "cash": 100.0,
            "shares_outstanding": 10.0,
        }
    )


@pytest.fixture
def v2_cfg(cfg: ModelConfig) -> ModelConfig:
    # g0 = 9% fading linearly to terminal 3% over 3 years: 9%, 6%, 3%; WACC 10%
    return cfg.model_copy(update={"projection_years": 3, "growth_rate_override": 0.09})


def test_two_stage_hand_worked_example(v2_fin: FinancialData, v2_cfg: ModelConfig) -> None:
    # FCF1 = 100*1.09 = 109        PV = 109/1.1       =   99.0909
    # FCF2 = 109*1.06 = 115.54     PV = 115.54/1.21   =   95.4876
    # FCF3 = 115.54*1.03 = 119.0062 PV = 119.0062/1.331 = 89.4111
    # TV = 119.0062*1.03/0.07 = 1751.0912 PV = 1751.0912/1.331 = 1315.6208
    # EV = 1599.6104; equity = 1599.6104 - (300 - 100) = 1399.6104; /10 = 139.961
    result, warnings = calculate(v2_fin, v2_cfg)
    assert result == pytest.approx(139.961, rel=1e-4)
    assert warnings == []


def test_growth_path_reaches_terminal_in_last_year() -> None:
    assert growth_path(0.09, 0.03, 3) == pytest.approx([0.09, 0.06, 0.03])
    assert growth_path(0.15, 0.03, 10)[-1] == pytest.approx(0.03)
    assert growth_path(0.15, 0.03, 1) == pytest.approx([0.03])


@pytest.mark.parametrize(
    ("debt", "cash", "expected"),
    [
        (0.0, 0.0, 159.961),  # EV 1599.6104 / 10
        (0.0, 200.0, 179.961),  # (1599.6104 + 200) / 10: net cash raises value
        (500.0, 100.0, 119.961),  # (1599.6104 - 400) / 10: more net debt lowers it
    ],
)
def test_net_debt_is_subtracted_from_enterprise_value(
    v2_fin: FinancialData, v2_cfg: ModelConfig, debt: float, cash: float, expected: float
) -> None:
    data = v2_fin.model_copy(update={"total_debt": debt, "cash": cash})
    result, _ = calculate(data, v2_cfg)
    assert result == pytest.approx(expected, rel=1e-4)


def test_base_averages_only_last_three_years(
    v2_fin: FinancialData, v2_cfg: ModelConfig
) -> None:
    # avg(90, 100, 110) = 100 regardless of the older 10, 20 → same as hand example 139.961
    data = v2_fin.model_copy(update={"fcf_history": [10.0, 20.0, 90.0, 100.0, 110.0]})
    result, warnings = calculate(data, v2_cfg)
    assert result == pytest.approx(139.961, rel=1e-4)
    assert warnings == []


def test_short_history_averages_available_years_with_warning(
    v2_fin: FinancialData, v2_cfg: ModelConfig
) -> None:
    # avg(90, 110) = 100 → same as hand example 139.961, plus a warning
    data = v2_fin.model_copy(update={"fcf_history": [90.0, 110.0]})
    result, warnings = calculate(data, v2_cfg)
    assert result == pytest.approx(139.961, rel=1e-4)
    assert len(warnings) == 1
    assert "2 year" in warnings[0]


def test_non_positive_average_fcf_returns_none(
    fin: FinancialData, cfg: ModelConfig
) -> None:
    # avg(100, -50, -80) = -10
    result, warnings = calculate(fin.model_copy(update={"fcf_history": [100.0, -50.0, -80.0]}), cfg)
    assert result is None
    assert any("FCF" in w for w in warnings)


def test_zero_average_fcf_returns_none(debt_free: FinancialData, cfg: ModelConfig) -> None:
    # avg(100, -50, -50) = 0 exactly → N/A at the FCF guard, not later at the equity guard
    data = debt_free.model_copy(update={"fcf_history": [100.0, -50.0, -50.0]})
    result, warnings = calculate(data, cfg)
    assert result is None
    assert "Average FCF" in warnings[0]


def test_underivable_growth_falls_back_to_zero_with_warning(
    debt_free: FinancialData, two_year_cfg: ModelConfig
) -> None:
    # Last FCF -10 → no CAGR, g0 = 0%; base = avg(100, 120, -10) = 70
    # 70 * 1.0 / 0.07 = 1000
    data = debt_free.model_copy(update={"fcf_history": [100.0, 120.0, -10.0]})
    result, warnings = calculate(data, two_year_cfg)
    assert result == pytest.approx(1000.0, rel=1e-4)
    assert len(warnings) == 1
    assert "growth" in warnings[0] and "0.0%" in warnings[0]


def test_debt_exceeding_enterprise_value_returns_none(
    v2_fin: FinancialData, v2_cfg: ModelConfig
) -> None:
    # EV 1599.6104 - net debt (2000 - 100) = -300.39 → N/A
    data = v2_fin.model_copy(update={"total_debt": 2000.0})
    result, warnings = calculate(data, v2_cfg)
    assert result is None
    assert any("net debt" in w for w in warnings)
