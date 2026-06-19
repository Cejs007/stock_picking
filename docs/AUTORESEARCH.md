# AutoResearch: tuning the valuation ensemble

This document describes how the project tunes *which* valuation models matter and
*how much* they count, per sector — using a Karpathy-style AutoResearch loop
(propose → evaluate → keep-if-better → revert) driven by a single validation
metric.

## Why this exists

The composite fair value is a weighted average of four models (Graham, P/E
relative, EV/EBITDA relative, DCF). The original weights were tuned on a 3-ticker
benchmark (AAPL, MSFT, CEZ.PR) — two thirds big tech. Weights tuned on that slice
overfit tech and travel badly to banks, utilities, or cyclicals, where different
models are structurally meaningful:

- **Graham Number** leans on book value → useful for asset-heavy / financial
  names, near-useless for capital-light tech (tiny BVPS turns it into an outlier
  that drags the composite down).
- **EV/EBITDA** needs a real EBITDA → meaningless for banks and insurers.
- **DCF** rewards durable free cash flow → strong for stable cash compounders,
  noisy for deep cyclicals caught at the wrong point in the cycle.
- **P/E relative** tracks the stock's own historical multiple → broadly useful.

So instead of one global weight vector, the system keeps **one ensemble template
per sector**, with a **default fallback** for sectors that have too little data to
tune reliably.

## The loop (how AutoResearch works here)

For each sector (and once more for the pooled default):

1. **Split** the sector's companies into a train set and a held-out validation
   set (`val_frac`, default 35%).
2. **Propose** a neighbour of the current weight vector — randomly change one
   model's weight to a value on a small grid `{0, 0.5, 1, 1.5, 2}` (0 = drop the
   model). The empty ensemble is never proposed.
3. **Evaluate** the candidate's objective on both train and validation.
4. **Keep-if-better:** accept the candidate *only if it improves the validation
   objective and does not regress on train*; otherwise revert. This is the
   overfit guard — the validation split, not the training split, decides what
   survives.
5. Repeat for `iterations` steps, with several random restarts to avoid local
   minima. Report train and validation MAPE side by side.

The single scalar the loop minimises (see `research/metrics.py`):

```
objective = MAPE% + COVERAGE_PENALTY * (1 - coverage) * 100
```

`MAPE` is the mean absolute percentage error between the composite fair value and
the market price. `coverage` is the fraction of companies the weight vector can
actually value (a config that disables models until only the easy names remain is
penalised, so it can't "win" by shrinking the sample).

### Important caveat about the metric

MAPE-vs-price treats the **market price as ground truth**, so minimising it
rewards models that *track price*, not models that *find mispricings*. It is a
**calibration** metric, not a proof of alpha. It was chosen for simplicity and
continuity with the prior run. The objective is intentionally swappable: replace
`objective()` in `research/metrics.py` with, e.g., a forward-return rank
correlation (rank companies by master score at a past date, measure whether
high-score names actually outperformed) to optimise for stock-picking skill
instead of calibration.

## Running it

```bash
# 1. Fetch the multi-sector universe from the live data provider (needs network).
python -m stock_picking.research.autoresearch collect --out research/dataset.json

# 2. Tune per-sector + default weights from that dataset (offline, reproducible).
python -m stock_picking.research.autoresearch tune \
    --dataset research/dataset.json \
    --out research/tuned_weights.json \
    --log research/autoresearch_log.jsonl \
    --iterations 200 --seed 0

# Or do both in one go:
python -m stock_picking.research.autoresearch run
```

`collect` and `tune` are deliberately separate so tuning is fast, offline and
reproducible once the data is on disk. `tune` with the same `--seed` is
deterministic.

`collect` fetches the universe in parallel (`fetch_all` uses a thread pool), and
every worker shares one on-disk SQLite cache. That shared connection is guarded
by a lock in `data/cache.py`, so concurrent reads/writes are serialized — without
it, sqlite raises `InterfaceError: bad parameter or other API misuse` partway
through a run.

## Using the tuned weights

The tuner writes `tuned_weights.json`:

```json
{
  "sector_weights": { "Technology": {"graham": 0.0, "pe_relative": 2.0, ...}, ... },
  "default_weights": { "graham": 0.0, "pe_relative": 1.5, ... },
  "report": { ... train/val MAPE per sector ... }
}
```

Point the app at it via an environment variable (or `.env`):

```bash
export TUNED_WEIGHTS_PATH=research/tuned_weights.json
```

`Settings` loads that file on startup and replaces the built-in priors. With
nothing set, the app uses the theory-based priors in `settings.DEFAULT_SECTOR_WEIGHTS`,
so it always runs out of the box.

## Reading the report

```
sector                  tuned n       val   equal   prior  weights
------------------------------------------------------------------
Financial Services      Y     8       0.0     7.8     9.3  graham=2 pe=0 ev=0 dcf=0
Technology              Y     8       5.0    70.5    68.2  graham=0 pe=2 ev=0 dcf=0
Energy                  n     3      81.6     ...    81.6  graham=0.5 pe=0.5 ev=1.5 dcf=0.5
(default fallback)      Y     16     10.6    28.3    27.9  graham=0 pe=1.5 ev=0 dcf=0
```

- `val` — tuned weights' MAPE on the held-out validation split (lower is better).
- `equal` / `prior` — baselines (equal weights, and the starting prior template)
  on the **same** validation split, so improvement is honest.
- `tuned = n` — the sector had fewer than `MIN_SECTOR_SAMPLES` (6) usable names,
  so it was left on its prior template (the fallback rule). Add more tickers to
  that sector in `research/universe.py` to enable tuning.

## A known data gap

The P/E-relative and EV/EBITDA models need historical multiple series
(`pe_history`, `ev_ebitda_history`). The current fetcher does not populate these
from yfinance, so on live data those two models return N/A for most tickers and
the harness will report lower coverage for them. To get full value from the
ensemble, populate `pe_history` / `ev_ebitda_history` in the fetcher (e.g. via the
optional FMP source) — the harness already reports coverage so this gap is
visible in the output rather than silent.

## Files

- `research/universe.py` — the multi-sector benchmark (edit to add names).
- `research/metrics.py` — samples, MAPE, coverage, and the swappable objective.
- `research/autoresearch.py` — data collection, the search loop, CLI, output.
- `settings.py` — `DEFAULT_SECTOR_WEIGHTS` priors, `weights_for(sector)`, and
  `tuned_weights_path` loading.
