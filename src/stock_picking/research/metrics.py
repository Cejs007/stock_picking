"""Validation metric for AutoResearch.

The single scalar the loop optimises is the fair-value MAPE: the mean absolute
percentage error between the composite fair value and the market price, over the
companies a given weight vector can actually value.

    objective = MAPE% + COVERAGE_PENALTY * (1 - coverage) * 100

The coverage penalty stops a config from "winning" by disabling models until it
only values the handful of easy names (which would shrink MAPE artificially).
A config that values nobody scores INF and is always rejected.

Caveat (documented in docs/AUTORESEARCH.md): MAPE-vs-price treats the market
price as ground truth, so minimising it rewards models that track price rather
than ones that find genuine mispricings. It is a calibration metric, not a
proof of alpha. The objective is intentionally swappable (see `objective`).
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from stock_picking.data.models import FinancialData, ModelConfig
from stock_picking.models.composite import calculate_composite
from stock_picking.models.registry import MODEL_REGISTRY

# Penalty weight on missing coverage, in MAPE percentage points per unit of
# missing coverage. 10.0 means "dropping 10% of names costs 1 MAPE point".
COVERAGE_PENALTY = 10.0


@dataclass(frozen=True)
class Sample:
    """A company with each model's fair value pre-computed once."""

    ticker: str
    sector: str | None
    price: float
    fair_values: dict[str, float | None]


def build_samples(
    dataset: list[FinancialData], config: ModelConfig | None = None
) -> list[Sample]:
    """Run every composite model once per company; reused across every weight config."""
    cfg = config or ModelConfig()
    samples: list[Sample] = []
    for fin in dataset:
        fvs = {
            name: model.calculate(fin, cfg)[0]
            for name, model in MODEL_REGISTRY.items()
            if model.in_composite
        }
        samples.append(
            Sample(
                ticker=fin.ticker,
                sector=fin.sector,
                price=fin.current_price,
                fair_values=fvs,
            )
        )
    return samples


def composite_value(sample: Sample, weights: dict[str, float]) -> float | None:
    results: dict[str, tuple[float | None, list[str]]] = {
        name: (fv, []) for name, fv in sample.fair_values.items()
    }
    return calculate_composite(results, weights).fair_value


def mape_coverage(
    samples: list[Sample], weights: dict[str, float]
) -> tuple[float, float]:
    """Return (MAPE%, coverage fraction) for a weight vector over samples."""
    if not samples:
        return math.inf, 0.0
    errors: list[float] = []
    for s in samples:
        c = composite_value(s, weights)
        if c is None or s.price <= 0:
            continue
        errors.append(abs(c - s.price) / s.price)
    coverage = len(errors) / len(samples)
    if not errors:
        return math.inf, 0.0
    return (sum(errors) / len(errors)) * 100.0, coverage


def objective(samples: list[Sample], weights: dict[str, float]) -> float:
    """Single scalar the loop minimises: MAPE plus a coverage penalty."""
    mape, coverage = mape_coverage(samples, weights)
    if math.isinf(mape):
        return math.inf
    return mape + COVERAGE_PENALTY * (1.0 - coverage) * 100.0
