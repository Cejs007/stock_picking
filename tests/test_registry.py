import pytest

from stock_picking.data.models import FinancialData, ModelConfig
from stock_picking.models.registry import MODEL_REGISTRY, RegisteredModel
from stock_picking.settings import DEFAULT_SECTOR_WEIGHTS, Settings
from stock_picking.ui.presenter import build_dashboard_rows
from stock_picking.valuator import valuate


def _fake_calculate(data: FinancialData, config: ModelConfig) -> tuple[float | None, list[str]]:
    return 500.0, ["fake model warning"]


def _only_pe_and_fake() -> Settings:
    # fin has no sector -> model_weights apply. P/E relative (hand-computed in
    # conftest: median([15..19]) * 5 = 85.0) and the fake model share weight 1:1.
    return Settings(model_weights={"pe_relative": 1.0, "fake": 1.0})


def test_registered_model_appears_in_result_and_dashboard_row(
    monkeypatch: pytest.MonkeyPatch, fin: FinancialData
) -> None:
    monkeypatch.setitem(MODEL_REGISTRY, "fake", RegisteredModel(_fake_calculate, "Fake"))

    result = valuate(fin, _only_pe_and_fake())

    assert result.fair_values["fake"] == pytest.approx(500.0)
    # (85.0 * 1 + 500.0 * 1) / 2 = 292.5
    assert result.fair_value_composite == pytest.approx(292.5)
    assert "fake model warning" in result.warnings
    row = build_dashboard_rows([result])[0]
    assert row["Fake"] == "$500.00"


def test_non_composite_model_is_computed_and_shown_but_not_in_composite(
    monkeypatch: pytest.MonkeyPatch, fin: FinancialData
) -> None:
    monkeypatch.setitem(
        MODEL_REGISTRY, "fake", RegisteredModel(_fake_calculate, "Fake", in_composite=False)
    )

    result = valuate(fin, _only_pe_and_fake())

    assert result.fair_values["fake"] == pytest.approx(500.0)
    # Fake is excluded despite its weight of 1 -> composite = P/E alone = 85.0
    assert result.fair_value_composite == pytest.approx(85.0)
    assert "fake model warning" in result.warnings
    assert build_dashboard_rows([result])[0]["Fake"] == "$500.00"


def test_registered_model_without_weight_does_not_move_composite(
    monkeypatch: pytest.MonkeyPatch, fin: FinancialData
) -> None:
    monkeypatch.setitem(MODEL_REGISTRY, "fake", RegisteredModel(_fake_calculate, "Fake"))

    result = valuate(fin, Settings(model_weights={"pe_relative": 1.0}))

    assert result.fair_values["fake"] == pytest.approx(500.0)
    # Missing weight counts as 0 -> composite = P/E alone = 85.0
    assert result.fair_value_composite == pytest.approx(85.0)


def test_sector_templates_cover_every_composite_model() -> None:
    composite_models = {name for name, m in MODEL_REGISTRY.items() if m.in_composite}
    for sector, weights in DEFAULT_SECTOR_WEIGHTS.items():
        assert set(weights) == composite_models, sector
