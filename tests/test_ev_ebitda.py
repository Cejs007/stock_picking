import pytest

from stock_picking.data.models import FinancialData, ModelConfig
from stock_picking.models.ev_ebitda import calculate


def test_happy_path(fin: FinancialData, cfg: ModelConfig) -> None:
    result, warnings = calculate(fin, cfg)
    assert result == pytest.approx(18.0)
    assert warnings == []


def test_ebitda_none_returns_none(fin: FinancialData, cfg: ModelConfig) -> None:
    result, warnings = calculate(fin.model_copy(update={"ebitda": None}), cfg)
    assert result is None
    assert any("EBITDA" in w for w in warnings)


def test_ebitda_zero_returns_none(fin: FinancialData, cfg: ModelConfig) -> None:
    result, warnings = calculate(fin.model_copy(update={"ebitda": 0.0}), cfg)
    assert result is None
    assert any("EBITDA" in w for w in warnings)


def test_shares_none_returns_none(fin: FinancialData, cfg: ModelConfig) -> None:
    result, warnings = calculate(fin.model_copy(update={"shares_outstanding": None}), cfg)
    assert result is None
    assert any("shares" in w.lower() for w in warnings)


def test_shares_zero_returns_none(fin: FinancialData, cfg: ModelConfig) -> None:
    result, warnings = calculate(fin.model_copy(update={"shares_outstanding": 0.0}), cfg)
    assert result is None


def test_insufficient_history_returns_none(fin: FinancialData, cfg: ModelConfig) -> None:
    result, warnings = calculate(fin.model_copy(update={"ev_ebitda_history": [8.0]}), cfg)
    assert result is None
    assert any("history" in w.lower() for w in warnings)


def test_uses_median_not_mean(fin: FinancialData, cfg: ModelConfig) -> None:
    # median([5,5,5,5,100]) = 5; fair_ev=5*20=100; equity=100-30+10=80; price=80/10=8
    result, _ = calculate(
        fin.model_copy(update={"ev_ebitda_history": [5.0, 5.0, 5.0, 5.0, 100.0]}),
        cfg,
    )
    assert result == pytest.approx(8.0)
