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
