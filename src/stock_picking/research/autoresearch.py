"""AutoResearch loop for the valuation ensemble.

Karpathy-style autonomous loop: propose a weight vector, evaluate it, KEEP it
only if it improves the held-out *validation* objective (and does not regress on
train), otherwise REVERT. A single scalar objective (fair-value MAPE + coverage
penalty, see metrics.py) drives every accept/reject decision.

Two phases, deliberately decoupled so tuning is reproducible and offline:

    collect : fetch the multi-sector universe via the live data provider and
              dump it to a JSON dataset (needs network; run locally).
    tune    : read the dataset, search per-sector + default weights with a
              train/validation split, and write tuned_weights.json + a log.

Usage:
    python -m stock_picking.research.autoresearch collect --out research/dataset.json
    python -m stock_picking.research.autoresearch tune    --dataset research/dataset.json
    python -m stock_picking.research.autoresearch run     # collect then tune
"""

from __future__ import annotations

import argparse
import json
import random
from dataclasses import asdict, dataclass, field
from pathlib import Path

from stock_picking.data.models import FinancialData
from stock_picking.research.metrics import Sample, build_samples, mape_coverage, objective
from stock_picking.research.universe import UNIVERSE, all_tickers
from stock_picking.settings import DEFAULT_SECTOR_WEIGHTS, MODEL_NAMES, _w

# Discrete weight values a model can take. Keeps results human-readable and the
# search space finite.
WEIGHT_GRID = (0.0, 0.5, 1.0, 1.5, 2.0)

# Sectors with fewer usable names than this are left on their prior template
# (the "with fallback" rule) — too little data to tune without overfitting.
MIN_SECTOR_SAMPLES = 6

EQUAL_WEIGHTS = dict.fromkeys(MODEL_NAMES, 1.0)


# --------------------------------------------------------------------------- #
# Data collection (network)
# --------------------------------------------------------------------------- #
def collect_dataset(out_path: str | Path, tickers: list[str] | None = None) -> int:
    """Fetch the universe and persist it as JSON. Returns count fetched."""
    from stock_picking.data.cache import Cache
    from stock_picking.data.fetcher import fetch_all

    tickers = tickers or all_tickers()
    cache = Cache(db_path="autoresearch_cache.db", ttl_hours=24.0)

    def _progress(done: int, total: int) -> None:
        print(f"  fetched {done}/{total}", end="\r", flush=True)

    fins = fetch_all(tickers, cache, status_callback=_progress)
    print()
    payload = [f.model_dump() for f in fins.values()]
    Path(out_path).write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"Wrote {len(payload)} companies to {out_path}")
    return len(payload)


def load_dataset(path: str | Path) -> list[FinancialData]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    return [FinancialData.model_validate(row) for row in payload]


# --------------------------------------------------------------------------- #
# Search
# --------------------------------------------------------------------------- #
@dataclass
class SectorResult:
    sector: str
    tuned: bool
    weights: dict[str, float]
    n_total: int
    n_train: int
    n_val: int
    train_mape: float
    val_mape: float
    val_coverage: float
    baseline_equal_val_mape: float
    baseline_prior_val_mape: float
    note: str = ""


@dataclass
class Report:
    sectors: list[SectorResult] = field(default_factory=list)
    default: SectorResult | None = None
    iterations: int = 0
    log: list[dict] = field(default_factory=list)

    def sector_weights(self) -> dict[str, dict[str, float]]:
        return {s.sector: s.weights for s in self.sectors}


def _split(samples: list[Sample], rng: random.Random, val_frac: float) -> tuple[list[Sample], list[Sample]]:
    items = list(samples)
    rng.shuffle(items)
    n_val = max(1, round(len(items) * val_frac))
    # Guarantee at least one training sample.
    n_val = min(n_val, len(items) - 1) if len(items) > 1 else 0
    return items[n_val:], items[:n_val]


def _mutate(weights: dict[str, float], rng: random.Random) -> dict[str, float]:
    cand = dict(weights)
    model = rng.choice(MODEL_NAMES)
    cand[model] = rng.choice(WEIGHT_GRID)
    if all(v == 0.0 for v in cand.values()):  # never propose the empty ensemble
        cand[rng.choice(MODEL_NAMES)] = 1.0
    return cand


def _hill_climb(
    train: list[Sample],
    val: list[Sample],
    start: dict[str, float],
    rng: random.Random,
    iterations: int,
    log: list[dict],
    log_tag: str,
) -> tuple[dict[str, float], float]:
    """Propose neighbours; keep only those that improve val without regressing train."""
    current = dict(start)
    best_val = objective(val, current)
    cur_train = objective(train, current)
    for i in range(iterations):
        cand = _mutate(current, rng)
        cand_train = objective(train, cand)
        cand_val = objective(val, cand)
        keep = cand_val < best_val - 1e-9 and cand_train <= cur_train + 1e-9
        log.append(
            {
                "scope": log_tag,
                "iter": i,
                "candidate": cand,
                "train_obj": _round(cand_train),
                "val_obj": _round(cand_val),
                "kept": keep,
            }
        )
        if keep:
            current, best_val, cur_train = cand, cand_val, cand_train
    return current, best_val


def _tune_group(
    samples: list[Sample],
    prior: dict[str, float],
    *,
    seed: int,
    iterations: int,
    val_frac: float,
    restarts: int,
    log: list[dict],
    log_tag: str,
) -> tuple[dict[str, float], list[Sample], list[Sample]]:
    """Tune one group (a sector or the pooled default) with random restarts."""
    rng = random.Random(seed)
    train, val = _split(samples, rng, val_frac)
    starts = [dict(prior), dict(EQUAL_WEIGHTS)]
    for _ in range(restarts):
        starts.append({m: rng.choice(WEIGHT_GRID) for m in MODEL_NAMES})

    best_weights = dict(prior)
    best_val = objective(val, best_weights)
    for start in starts:
        w, v = _hill_climb(train, val, start, rng, iterations, log, log_tag)
        if v < best_val - 1e-9:
            best_weights, best_val = w, v
    return best_weights, train, val


def run_autoresearch(
    dataset: list[FinancialData],
    *,
    seed: int = 0,
    iterations: int = 200,
    val_frac: float = 0.35,
    restarts: int = 4,
) -> Report:
    """Tune per-sector + default ensemble weights on a held-out validation split."""
    samples = build_samples(dataset)
    by_sector: dict[str, list[Sample]] = {}
    for s in samples:
        by_sector.setdefault(s.sector or "Unknown", []).append(s)

    report = Report(iterations=iterations)

    for sector in sorted(by_sector):
        group = by_sector[sector]
        prior = DEFAULT_SECTOR_WEIGHTS.get(sector, _w(0.0, 1.5, 1.0, 1.0))
        if len(group) < MIN_SECTOR_SAMPLES:
            v_mape, v_cov = mape_coverage(group, prior)
            report.sectors.append(
                SectorResult(
                    sector=sector, tuned=False, weights=prior, n_total=len(group),
                    n_train=0, n_val=len(group), train_mape=float("nan"),
                    val_mape=v_mape, val_coverage=v_cov,
                    baseline_equal_val_mape=mape_coverage(group, EQUAL_WEIGHTS)[0],
                    baseline_prior_val_mape=v_mape,
                    note=f"fallback: only {len(group)} samples (< {MIN_SECTOR_SAMPLES})",
                )
            )
            continue

        weights, train, val = _tune_group(
            group, prior, seed=seed + (sum(ord(c) for c in sector) % 1000),
            iterations=iterations, val_frac=val_frac, restarts=restarts,
            log=report.log, log_tag=f"sector:{sector}",
        )
        report.sectors.append(
            SectorResult(
                sector=sector, tuned=True, weights=weights, n_total=len(group),
                n_train=len(train), n_val=len(val),
                train_mape=mape_coverage(train, weights)[0],
                val_mape=mape_coverage(val, weights)[0],
                val_coverage=mape_coverage(val, weights)[1],
                baseline_equal_val_mape=mape_coverage(val, EQUAL_WEIGHTS)[0],
                baseline_prior_val_mape=mape_coverage(val, prior)[0],
            )
        )

    # Default / fallback weights: tuned on the whole pooled universe.
    prior_default = _w(0.0, 1.5, 1.0, 1.0)
    weights, train, val = _tune_group(
        samples, prior_default, seed=seed + 7, iterations=iterations,
        val_frac=val_frac, restarts=restarts, log=report.log, log_tag="default",
    )
    report.default = SectorResult(
        sector="(default fallback)", tuned=True, weights=weights,
        n_total=len(samples), n_train=len(train), n_val=len(val),
        train_mape=mape_coverage(train, weights)[0],
        val_mape=mape_coverage(val, weights)[0],
        val_coverage=mape_coverage(val, weights)[1],
        baseline_equal_val_mape=mape_coverage(val, EQUAL_WEIGHTS)[0],
        baseline_prior_val_mape=mape_coverage(val, prior_default)[0],
    )
    return report


# --------------------------------------------------------------------------- #
# Output
# --------------------------------------------------------------------------- #
def _round(x: float) -> float:
    return round(x, 4) if x == x and abs(x) != float("inf") else x  # NaN/inf safe


def write_outputs(report: Report, out_path: str | Path, log_path: str | Path | None) -> None:
    payload = {
        "sector_weights": report.sector_weights(),
        "default_weights": report.default.weights if report.default else None,
        "report": {
            "iterations": report.iterations,
            "sectors": [asdict(s) for s in report.sectors],
            "default": asdict(report.default) if report.default else None,
        },
    }
    Path(out_path).write_text(json.dumps(payload, indent=2), encoding="utf-8")
    if log_path:
        with Path(log_path).open("w", encoding="utf-8") as fh:
            for row in report.log:
                fh.write(json.dumps(row) + "\n")


def print_report(report: Report) -> None:
    print("\n=== AutoResearch: per-sector ensemble (validation MAPE%) ===")
    hdr = f"{'sector':<24}{'tuned':<6}{'n':<4}{'val':>7}{'equal':>8}{'prior':>8}  weights"
    print(hdr)
    print("-" * len(hdr))
    rows = list(report.sectors) + ([report.default] if report.default else [])
    for s in rows:
        w = " ".join(f"{k.split('_')[0]}={s.weights.get(k, 0.0):g}" for k in MODEL_NAMES)
        print(
            f"{s.sector:<24}{'Y' if s.tuned else 'n':<6}{s.n_total:<4}"
            f"{_fmt(s.val_mape):>7}{_fmt(s.baseline_equal_val_mape):>8}"
            f"{_fmt(s.baseline_prior_val_mape):>8}  {w}"
        )
    print("\nLower val MAPE is better. 'equal'/'prior' are baselines on the same")
    print("validation split. Sectors marked 'n' fell back to their prior template.")


def _fmt(x: float) -> str:
    return "n/a" if x != x or abs(x) == float("inf") else f"{x:.1f}"


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="AutoResearch ensemble tuner")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_collect = sub.add_parser("collect", help="fetch universe -> dataset JSON")
    p_collect.add_argument("--out", default="research/dataset.json")

    p_tune = sub.add_parser("tune", help="tune weights from a dataset JSON")
    p_tune.add_argument("--dataset", default="research/dataset.json")
    p_tune.add_argument("--out", default="research/tuned_weights.json")
    p_tune.add_argument("--log", default="research/autoresearch_log.jsonl")
    p_tune.add_argument("--seed", type=int, default=0)
    p_tune.add_argument("--iterations", type=int, default=200)

    p_run = sub.add_parser("run", help="collect then tune")
    p_run.add_argument("--dataset", default="research/dataset.json")
    p_run.add_argument("--out", default="research/tuned_weights.json")
    p_run.add_argument("--log", default="research/autoresearch_log.jsonl")
    p_run.add_argument("--seed", type=int, default=0)
    p_run.add_argument("--iterations", type=int, default=200)

    args = parser.parse_args(argv)

    if args.cmd == "collect":
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        collect_dataset(args.out)
        return 0

    if args.cmd == "run":
        Path(args.dataset).parent.mkdir(parents=True, exist_ok=True)
        collect_dataset(args.dataset)

    dataset = load_dataset(args.dataset)
    if len(dataset) < 2:
        print("Dataset too small to tune.")
        return 1
    report = run_autoresearch(dataset, seed=args.seed, iterations=args.iterations)
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    write_outputs(report, args.out, args.log)
    print_report(report)
    print(f"\nWrote tuned weights to {args.out}")
    print("Point the app at them with:  export TUNED_WEIGHTS_PATH=" + str(args.out))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
