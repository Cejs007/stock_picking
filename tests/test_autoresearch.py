import math
import random

import pytest

from stock_picking.data.models import FinancialData
from stock_picking.research import autoresearch as ar
from stock_picking.research.metrics import (
    Sample,
    build_samples,
    mape_coverage,
    objective,
)


# --------------------------------------------------------------------------- #
# Metric
# --------------------------------------------------------------------------- #
def _sample(price, fvs, sector="X"):
    return Sample(ticker="T", sector=sector, price=price, fair_values=fvs)


def test_mape_zero_when_composite_equals_price() -> None:
    s = [_sample(100.0, {"graham": 100.0, "pe_relative": None,
                         "ev_ebitda": None, "dcf": None})]
    mape, cov = mape_coverage(s, {"graham": 1.0})
    assert mape == pytest.approx(0.0)
    assert cov == pytest.approx(1.0)


def test_mape_known_value() -> None:
    # composite=120 vs price=100 -> 20% error
    s = [_sample(100.0, {"graham": 120.0, "pe_relative": None,
                         "ev_ebitda": None, "dcf": None})]
    mape, _ = mape_coverage(s, {"graham": 1.0})
    assert mape == pytest.approx(20.0)


def test_coverage_drops_when_models_unavailable() -> None:
    s = [
        _sample(100.0, {"graham": 100.0, "pe_relative": None, "ev_ebitda": None, "dcf": None}),
        _sample(100.0, {"graham": None, "pe_relative": None, "ev_ebitda": None, "dcf": None}),
    ]
    mape, cov = mape_coverage(s, {"graham": 1.0})
    assert cov == pytest.approx(0.5)


def test_objective_infinite_for_empty_ensemble() -> None:
    s = [_sample(100.0, {"graham": 100.0, "pe_relative": None, "ev_ebitda": None, "dcf": None})]
    assert math.isinf(objective(s, {"graham": 0.0, "pe_relative": 0.0,
                                    "ev_ebitda": 0.0, "dcf": 0.0}))


def test_objective_penalises_low_coverage() -> None:
    # Perfect MAPE but only 50% coverage should beat a worse-MAPE full-coverage
    # config only if the penalty is small; here we just check the penalty bites.
    half = [
        _sample(100.0, {"graham": 100.0, "pe_relative": None, "ev_ebitda": None, "dcf": None}),
        _sample(100.0, {"graham": None, "pe_relative": None, "ev_ebitda": None, "dcf": None}),
    ]
    obj = objective(half, {"graham": 1.0})
    assert obj > 0.0  # 0 MAPE + penalty for the uncovered half


# --------------------------------------------------------------------------- #
# Search loop
# --------------------------------------------------------------------------- #
def test_hill_climb_keeps_only_improvements() -> None:
    # pe_relative is a perfect predictor; graham is way off.
    samples = [
        Sample(ticker=f"T{i}", sector="X", price=10.0 * (i + 1),
               fair_values={"graham": 999.0, "pe_relative": 10.0 * (i + 1),
                            "ev_ebitda": None, "dcf": None})
        for i in range(10)
    ]
    rng = random.Random(0)
    start = {"graham": 1.0, "pe_relative": 0.0, "ev_ebitda": 0.0, "dcf": 0.0}
    log: list[dict] = []
    weights, best_val = ar._hill_climb(samples, samples, start, rng,
                                       iterations=200, log=log, log_tag="t")
    assert best_val <= objective(samples, start) + 1e-9   # never worse than start
    assert weights["pe_relative"] > 0                     # found the good signal
    assert any(row["kept"] for row in log)


def _synthetic_dataset() -> list[FinancialData]:
    def mk(t, sector, price, eps, bvps, pe_hist, ebitda, ev_hist, shares, fcf):
        return FinancialData(ticker=t, sector=sector, current_price=price, eps_ttm=eps,
                             bvps=bvps, pe_history=pe_hist, ebitda=ebitda,
                             ev_ebitda_history=ev_hist, shares_outstanding=shares,
                             fcf_history=fcf)
    ds = []
    for i in range(8):  # Tech: price == P/E fair value
        eps = 5 + i
        ds.append(mk(f"T{i}", "Technology", 20 * eps, eps, 2.0, [18, 19, 20],
                     10 + i, [5, 5, 5], 100, [50, 55, 60, 65, 70]))
    for i in range(8):  # Financials: price == Graham number
        eps, bvps = 4 + i, 30 + i
        g = math.sqrt(22.5 * eps * bvps)
        ds.append(mk(f"F{i}", "Financial Services", g, eps, bvps, [10, 11, 12],
                     None, [], 100, []))
    for i in range(3):  # Energy: too few -> fallback
        ds.append(mk(f"E{i}", "Energy", 100.0, 5, 20, [8, 9, 10], 50, [6, 7, 8], 100, [40, 42, 44]))
    return ds


def test_run_autoresearch_tunes_and_falls_back() -> None:
    rep = ar.run_autoresearch(_synthetic_dataset(), seed=1, iterations=150)
    by = {s.sector: s for s in rep.sectors}

    assert by["Technology"].tuned is True
    assert by["Financial Services"].tuned is True
    # Tuning never regresses vs the prior template on the validation split.
    assert by["Technology"].val_mape <= by["Technology"].baseline_prior_val_mape + 1e-6
    assert by["Financial Services"].val_mape <= by["Financial Services"].baseline_prior_val_mape + 1e-6

    # Energy has only 3 samples -> fallback, weights left as prior.
    energy = by["Energy"]
    assert energy.tuned is False
    assert "fallback" in energy.note

    assert rep.default is not None
    assert rep.default.tuned is True


def test_run_autoresearch_is_deterministic() -> None:
    ds = _synthetic_dataset()
    r1 = ar.run_autoresearch(ds, seed=1, iterations=120)
    r2 = ar.run_autoresearch(ds, seed=1, iterations=120)
    assert r1.sector_weights() == r2.sector_weights()


def test_write_and_reload_round_trip(tmp_path) -> None:
    from stock_picking.settings import Settings
    rep = ar.run_autoresearch(_synthetic_dataset(), seed=1, iterations=120)
    out = tmp_path / "tuned.json"
    ar.write_outputs(rep, out, tmp_path / "log.jsonl")
    s = Settings(tuned_weights_path=str(out))
    assert s.weights_for("Technology") == rep.sector_weights()["Technology"]


def test_load_dataset_round_trip(tmp_path) -> None:
    ds = _synthetic_dataset()
    p = tmp_path / "ds.json"
    import json
    p.write_text(json.dumps([f.model_dump() for f in ds]), encoding="utf-8")
    loaded = ar.load_dataset(p)
    assert len(loaded) == len(ds)
    assert loaded[0].sector == ds[0].sector
