import pytest

from stock_picking.data.models import FinancialData, ModelConfig
from stock_picking.models.pe_relative import calculate


def test_happy_path(fin: FinancialData, cfg: ModelConfig) -> None:
    result, warnings = calculate(fin, cfg)
    assert result == pytest.approx(85.0)
    assert warnings == []


def test_eps_none_returns_none(fin: FinancialData, cfg: ModelConfig) -> None:
    result, warnings = calculate(fin.model_copy(update={"eps_ttm": None}), cfg)
    assert result is None
    assert any("EPS" in w for w in warnings)


def test_eps_zero_returns_none(fin: FinancialData, cfg: ModelConfig) -> None:
    result, warnings = calculate(fin.model_copy(update={"eps_ttm": 0.0}), cfg)
    assert result is None
    assert any("EPS" in w for w in warnings)


def test_insufficient_history_returns_none(fin: FinancialData, cfg: ModelConfig) -> None:
    result, warnings = calculate(fin.model_copy(update={"pe_history": [15.0, 16.0]}), cfg)
    assert result is None
    assert any("history" in w.lower() for w in warnings)


def test_empty_history_returns_none(fin: FinancialData, cfg: ModelConfig) -> None:
    result, warnings = calculate(fin.model_copy(update={"pe_history": []}), cfg)
    assert result is None


def test_uses_median_not_mean(fin: FinancialData, cfg: ModelConfig) -> None:
    # [10, 10, 10, 10, 100] — mean=28, median=10
    result, warnings = calculate(
        fin.model_copy(update={"pe_history": [10.0, 10.0, 10.0, 10.0, 100.0], "eps_ttm": 2.0}),
        cfg,
    )
    assert result == pytest.approx(10.0 * 2.0)
