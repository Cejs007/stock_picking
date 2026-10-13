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
        return CompositeResult(
            fair_value=None, low=None, high=None, cv=None, active=[], warnings=all_warnings
        )

    total_weight = sum(w for _, w in active.values())
    fair_value = sum(v * w / total_weight for v, w in active.values())
    values = [v for v, _ in active.values()]
    cv = _cv(values)
    if cv is None:
        all_warnings.append("Model disagreement N/A: a fair value is non-positive")
    return CompositeResult(
        fair_value=fair_value,
        low=min(values),
        high=max(values),
        cv=cv,
        active=list(active.keys()),
        warnings=all_warnings,
    )


def _cv(values: list[float]) -> float | None:
    # Coefficient of variation = population std / mean, unweighted over active
    # models. Population (not sample) std: the active models are the whole set
    # being described, not a sample, and it gives a finite 0 for one model.
    # Only meaningful on a ratio scale: one negative value (e.g. EV/EBITDA for a
    # heavily indebted company) pulls the mean toward 0 and inflates CV.
    if any(v <= 0 for v in values):
        return None
    return statistics.pstdev(values) / statistics.fmean(values)
