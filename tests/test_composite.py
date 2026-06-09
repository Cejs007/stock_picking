import pytest

from stock_picking.models.composite import calculate_composite


def test_equal_weights_averages_active_models() -> None:
    results = {"a": (100.0, []), "b": (200.0, []), "c": (300.0, [])}
    weights = {"a": 1.0, "b": 1.0, "c": 1.0}
    fair_value, active, warnings = calculate_composite(results, weights)
    assert fair_value == pytest.approx(200.0)
    assert set(active) == {"a", "b", "c"}
    assert warnings == []


def test_unequal_weights_used() -> None:
    results = {"a": (100.0, []), "b": (200.0, [])}
    weights = {"a": 3.0, "b": 1.0}
    fair_value, active, warnings = calculate_composite(results, weights)
    # 3/4 * 100 + 1/4 * 200 = 75 + 50 = 125
    assert fair_value == pytest.approx(125.0)


def test_none_model_excluded_and_weights_renormalized() -> None:
    results = {"a": (100.0, []), "b": (None, ["b is N/A"])}
    weights = {"a": 1.0, "b": 1.0}
    fair_value, active, warnings = calculate_composite(results, weights)
    assert fair_value == pytest.approx(100.0)
    assert active == ["a"]
    assert "b is N/A" in warnings


def test_all_none_returns_none() -> None:
    results = {"a": (None, ["warn_a"]), "b": (None, ["warn_b"])}
    weights = {"a": 1.0, "b": 1.0}
    fair_value, active, warnings = calculate_composite(results, weights)
    assert fair_value is None
    assert active == []
    assert set(warnings) == {"warn_a", "warn_b"}


def test_zero_weight_model_excluded() -> None:
    results = {"a": (100.0, []), "b": (999.0, [])}
    weights = {"a": 1.0, "b": 0.0}
    fair_value, active, warnings = calculate_composite(results, weights)
    assert fair_value == pytest.approx(100.0)
    assert "a" in active
    assert "b" not in active


def test_warnings_aggregated_from_all_models() -> None:
    results = {"a": (100.0, ["warn_a"]), "b": (None, ["warn_b"])}
    weights = {"a": 1.0, "b": 1.0}
    _, _, warnings = calculate_composite(results, weights)
    assert "warn_a" in warnings
    assert "warn_b" in warnings
