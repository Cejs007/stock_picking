import math

import pytest

from stock_picking.data.models import FinancialData, ModelConfig
from stock_picking.models.graham import calculate


def test_happy_path(fin: FinancialData, cfg: ModelConfig) -> None:
    result, warnings = calculate(fin, cfg)
    assert result == pytest.approx(math.sqrt(22.5 * 5.0 * 40.0), rel=1e-6)
    assert warnings == []


def test_eps_zero_returns_none(fin: FinancialData, cfg: ModelConfig) -> None:
    result, warnings = calculate(fin.model_copy(update={"eps_ttm": 0.0}), cfg)
    assert result is None
    assert any("EPS" in w for w in warnings)


def test_eps_negative_returns_none(fin: FinancialData, cfg: ModelConfig) -> None:
    result, warnings = calculate(fin.model_copy(update={"eps_ttm": -1.0}), cfg)
    assert result is None
    assert any("EPS" in w for w in warnings)


def test_bvps_zero_returns_none(fin: FinancialData, cfg: ModelConfig) -> None:
    result, warnings = calculate(fin.model_copy(update={"bvps": 0.0}), cfg)
    assert result is None
    assert any("BVPS" in w for w in warnings)


def test_bvps_negative_returns_none(fin: FinancialData, cfg: ModelConfig) -> None:
    result, warnings = calculate(fin.model_copy(update={"bvps": -5.0}), cfg)
    assert result is None
    assert any("BVPS" in w for w in warnings)


def test_eps_none_returns_none(fin: FinancialData, cfg: ModelConfig) -> None:
    result, warnings = calculate(fin.model_copy(update={"eps_ttm": None}), cfg)
    assert result is None


def test_bvps_none_returns_none(fin: FinancialData, cfg: ModelConfig) -> None:
    result, warnings = calculate(fin.model_copy(update={"bvps": None}), cfg)
    assert result is None
