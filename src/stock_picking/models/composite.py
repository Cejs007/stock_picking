import statistics
from dataclasses import dataclass


@dataclass(frozen=True)
class CompositeResult:
    fair_value: float | None
    low: float | None
    high: float | None
    cv: float | None
    active: list[str]
    warnings: list[str]


def calculate_composite(
    results: dict[str, tuple[float | None, list[str]]],
    weights: dict[str, float],
) -> CompositeResult:
    all_warnings: list[str] = []
    for _, w in results.values():
        all_warnings.extend(w)

    active = {
        name: (value, weights.get(name, 0.0))
        for name, (value, _) in results.items()
        if value is not None and weights.get(name, 0.0) > 0
    }

    if not active:
        return CompositeResult(None, None, None, None, [], all_warnings)

    total_weight = sum(w for _, w in active.values())
    fair_value = sum(v * w / total_weight for v, w in active.values())
    values = [v for v, _ in active.values()]
    return CompositeResult(
        fair_value, min(values), max(values), _cv(values), list(active.keys()), all_warnings
    )


def _cv(values: list[float]) -> float | None:
    # Coefficient of variation = population std / mean, unweighted over active
    # models. Population (not sample) std: the active models are the whole set
    # being described, not a sample, and it gives a finite 0 for one model.
    mean = statistics.fmean(values)
    if mean <= 0:
        return None
    return statistics.pstdev(values) / mean
