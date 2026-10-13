import pytest

from stock_picking.models.composite import calculate_composite


def test_equal_weights_averages_active_models() -> None:
    results = {"a": (100.0, []), "b": (200.0, []), "c": (300.0, [])}
    weights = {"a": 1.0, "b": 1.0, "c": 1.0}
    c = calculate_composite(results, weights)
    assert c.fair_value == pytest.approx(200.0)
    assert set(c.active) == {"a", "b", "c"}
    assert c.warnings == []


def test_unequal_weights_used() -> None:
    results = {"a": (100.0, []), "b": (200.0, [])}
    weights = {"a": 3.0, "b": 1.0}
    c = calculate_composite(results, weights)
    # 3/4 * 100 + 1/4 * 200 = 75 + 50 = 125
    assert c.fair_value == pytest.approx(125.0)


def test_none_model_excluded_and_weights_renormalized() -> None:
    results = {"a": (100.0, []), "b": (None, ["b is N/A"])}
    weights = {"a": 1.0, "b": 1.0}
    c = calculate_composite(results, weights)
    assert c.fair_value == pytest.approx(100.0)
    assert c.active == ["a"]
    assert "b is N/A" in c.warnings


def test_all_none_returns_none() -> None:
    results = {"a": (None, ["warn_a"]), "b": (None, ["warn_b"])}
    weights = {"a": 1.0, "b": 1.0}
    c = calculate_composite(results, weights)
    assert c.fair_value is None
    assert c.low is None
    assert c.high is None
    assert c.cv is None
    assert c.active == []
    assert set(c.warnings) == {"warn_a", "warn_b"}


def test_zero_weight_model_excluded() -> None:
    results = {"a": (100.0, []), "b": (999.0, [])}
    weights = {"a": 1.0, "b": 0.0}
    c = calculate_composite(results, weights)
    assert c.fair_value == pytest.approx(100.0)
    assert "a" in c.active
    assert "b" not in c.active


def test_warnings_aggregated_from_all_models() -> None:
    results = {"a": (100.0, ["warn_a"]), "b": (None, ["warn_b"])}
    weights = {"a": 1.0, "b": 1.0}
    c = calculate_composite(results, weights)
    assert "warn_a" in c.warnings
    assert "warn_b" in c.warnings


def test_range_and_cv_of_active_models() -> None:
    results = {"a": (100.0, []), "b": (200.0, []), "c": (300.0, [])}
    weights = {"a": 1.0, "b": 1.0, "c": 1.0}
    c = calculate_composite(results, weights)
    assert c.low == pytest.approx(100.0)
    assert c.high == pytest.approx(300.0)
    # mean = 200; population var = (100² + 0² + 100²) / 3 = 6666.67
    # std = 81.6497; CV = 81.6497 / 200 = 0.408248
    # (sample std would be 100 -> CV 0.5)
    assert c.cv == pytest.approx(0.408248, rel=1e-5)


def test_cv_is_unweighted_spread_of_active_models() -> None:
    results = {"a": (100.0, []), "b": (200.0, [])}
    weights = {"a": 3.0, "b": 1.0}
    c = calculate_composite(results, weights)
    # Weights move the composite (125) but not the spread:
    # mean = 150; population std = 50; CV = 50 / 150 = 0.333333
    assert c.fair_value == pytest.approx(125.0)
    assert (c.low, c.high) == (pytest.approx(100.0), pytest.approx(200.0))
    assert c.cv == pytest.approx(0.333333, rel=1e-5)


def test_zero_weight_and_na_models_excluded_from_range_and_cv() -> None:
    results = {"a": (100.0, []), "b": (200.0, []), "zero": (999.0, []), "na": (None, ["na"])}
    weights = {"a": 1.0, "b": 1.0, "zero": 0.0, "na": 1.0}
    c = calculate_composite(results, weights)
    # Only a and b count: mean = 150, population std = 50, CV = 1/3
    assert c.low == pytest.approx(100.0)
    assert c.high == pytest.approx(200.0)
    assert c.cv == pytest.approx(0.333333, rel=1e-5)


def test_single_active_model_has_zero_cv_and_collapsed_range() -> None:
    results = {"a": (120.0, []), "b": (999.0, []), "c": (None, [])}
    weights = {"a": 1.0, "b": 0.0, "c": 1.0}
    c = calculate_composite(results, weights)
    assert c.low == pytest.approx(120.0)
    assert c.high == pytest.approx(120.0)
    assert c.cv == 0.0


def test_cv_undefined_when_mean_not_positive() -> None:
    # mean = (-50 + 30) / 2 = -10 -> std/mean is meaningless -> None
    results = {"a": (-50.0, []), "b": (30.0, [])}
    weights = {"a": 1.0, "b": 1.0}
    c = calculate_composite(results, weights)
    assert c.low == pytest.approx(-50.0)
    assert c.high == pytest.approx(30.0)
    assert c.cv is None
