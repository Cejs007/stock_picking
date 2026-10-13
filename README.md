# stock_picking

A personal stock-valuation dashboard. You keep a **watchlist** of tickers; the
app pulls each company's fundamentals, runs four independent valuation models,
blends them into a single **fair value** tuned to the company's sector, and tells
you whether the current price is a **BUY** or a **WAIT** given your margin of
safety.

It is a decision-support tool for your own research — not investment advice, and
not an automated trader. Nothing here places orders.

---

## What it does, in one pass

For every ticker on your watchlist:

1. **Fetch** fundamentals (price, EPS, book value, FCF history, EBITDA, debt,
   cash, …) from Yahoo Finance via `yfinance`.
2. **Value** the company with four models (see [Valuation models](#valuation-models)).
3. **Blend** the models into a *composite fair value*, using a weight template
   chosen by the company's **sector** (a bank and a software firm are valued
   differently).
4. **Score & signal**: compute the upside vs. today's price, derive a discounted
   buy target, and flag **BUY** / **WAIT** / **N/A**.

Results are stored locally in SQLite, so they persist between runs.

---

## Requirements

- Python **3.11+**
- Network access (Yahoo Finance) when you refresh data.

## Install

Using [uv](https://github.com/astral-sh/uv) (recommended):

```bash
uv venv
uv pip install -e .
```

Or with plain pip:

```bash
python -m venv .venv
# Windows PowerShell:
.venv\Scripts\Activate.ps1
# macOS/Linux:
# source .venv/bin/activate
pip install -e .
```

---

## Run the dashboard

The app is a [Streamlit](https://streamlit.io) web UI:

```bash
streamlit run src/stock_picking/ui/app.py
```

This opens a browser tab. From there:

| Action | How |
| --- | --- |
| **Add a ticker** | Type a symbol (e.g. `AAPL`, `CEZ.PR`) in the sidebar and click **Add**. |
| **Remove a ticker** | Click the **✕** next to it in the sidebar. |
| **Fetch / recompute** | Click **Refresh all**. This recomputes every valuation, reusing cached data younger than `CACHE_TTL_HOURS` and downloading the rest. Click **Force refresh** to ignore the cache and re-download everything. |

Tickers follow Yahoo Finance conventions — US tickers are bare (`MSFT`),
non-US tickers carry an exchange suffix (`CEZ.PR`, `SAP.DE`, `7203.T`).

### Reading the dashboard table

Rows are sorted by **Upside**, best first.

| Column | Meaning |
| --- | --- |
| **Price** | Latest market price. |
| **Fair Value** | The composite (sector-weighted blend) of the models that could be computed. |
| **Upside** | `(Fair Value − Price) / Price`. Positive = the model thinks the stock is cheap. |
| **Buy Target** | `Fair Value × (1 − margin of safety)`. The price you'd want before buying. |
| **Signal** | **BUY** if Price ≤ Buy Target, **WAIT** if above it, **N/A** if no model could value the company. |
| **Graham / P/E / EV/EBITDA / DCF** | Each model's individual fair value, so you can see *why* the composite landed where it did. |

`N/A` in a single model column is normal — see
[When a model shows N/A](#when-a-model-shows-na).

---

## Valuation models

Each model produces an independent estimate of fair value per share. They
disagree on purpose; the composite reconciles them.

- **Graham Number** — a conservative floor based on earnings and book value.
  Most meaningful for asset-heavy and financial names; near-useless for
  capital-light tech (tiny book value turns it into an outlier).
- **P/E relative** — values the stock against *its own* historical P/E multiple.
  Broadly useful.
- **EV/EBITDA relative** — values the enterprise against its historical
  EV/EBITDA multiple. Meaningless for banks/insurers (no real EBITDA).
- **DCF** (discounted cash flow) — discounts projected free cash flow back to
  today. Strong for stable cash compounders, noisy for deep cyclicals. If you
  don't supply a growth rate it is derived from the company's FCF history.

### How the composite is built

The composite is a **weighted average of the models that returned a value**,
using a weight template selected by the company's sector. A model with weight
`0`, or one that couldn't be computed, simply drops out and the remaining
weights are renormalised. If *no* model can be computed, the composite is `N/A`.

The per-sector weight templates live in
[`settings.py`](src/stock_picking/settings.py) (`DEFAULT_SECTOR_WEIGHTS`). They
are theory-based defaults that ship working out of the box. Improving them
empirically is a developer task — see [AutoResearch](docs/AUTORESEARCH.md).

### When a model shows N/A

A model returns `N/A` when the data it needs is missing:

- **P/E relative** and **EV/EBITDA relative** need *historical* multiple series.
  The built-in Yahoo Finance fetcher does **not** populate these yet, so on live
  data these two columns are `N/A` for most tickers. The composite still works
  from the remaining models. (This gap is known and documented; it does not
  indicate an error.)
- **DCF** needs free-cash-flow history; **Graham** needs positive earnings and
  book value.

---

## Configuration

Settings are read from environment variables or a `.env` file in the project
root. All have sensible defaults — you can run with no configuration at all.

| Variable | Default | What it controls |
| --- | --- | --- |
| `DEFAULT_MOS` | `0.25` | Margin of safety. `0.25` = require a 25% discount to fair value before signalling BUY. |
| `DEFAULT_WACC` | `0.10` | Discount rate used by the DCF model. |
| `DEFAULT_TERMINAL_G` | `0.03` | DCF terminal growth rate. |
| `DEFAULT_PROJECTION_YEARS` | `10` | DCF projection horizon. |
| `CACHE_TTL_HOURS` | `24` | How long fetched data is reused before re-downloading. |
| `FMP_API_KEY` | _(unset)_ | Optional key for an alternative data source. |
| `TUNED_WEIGHTS_PATH` | _(unset)_ | Path to developer-tuned sector weights (see [AutoResearch](docs/AUTORESEARCH.md)). When unset, the built-in priors are used. |

Example `.env`:

```dotenv
DEFAULT_MOS=0.30
CACHE_TTL_HOURS=12
```

---

## Where your data lives

Everything is stored in a single local SQLite file, `stock_picking.db`, created
in the directory you run the app from:

- **watchlist** — your tickers and any per-ticker overrides.
- **valuations** — the latest computed result per ticker.
- a **cache** of fetched fundamentals (honouring `CACHE_TTL_HOURS`), so a refresh
  within the TTL window is fast and avoids hammering the data provider.

To start clean, stop the app and delete `stock_picking.db`.

---

## Power-user features (library API)

These are available in the codebase but are **not yet wired into the dashboard
UI** — use them from Python if you need them:

- **Per-ticker overrides** ([`watchlist.py`](src/stock_picking/watchlist.py)):
  override the margin of safety or the DCF growth / WACC / terminal-growth /
  horizon for an individual ticker, instead of the global defaults.
- **Decision journal** ([`journal.py`](src/stock_picking/journal.py)): snapshot
  the ranked watchlist, log a purchase against that snapshot, and later run a
  retrospective — "how did the stock I bought do versus the alternatives I
  passed on at the time?"

---

## Running the tests

```bash
uv pip install -e ".[dev]"   # or: pip install -e ".[dev]"
pytest
```

---

## For developers

- [`docs/AUTORESEARCH.md`](docs/AUTORESEARCH.md) — how the per-sector ensemble
  weights are tuned empirically (the AutoResearch loop). This is a developer/
  research workflow, not part of normal app usage.
- [`docs/PRD.md`](docs/PRD.md), [`docs/PLAN.md`](docs/PLAN.md) — product
  requirements and implementation plan.
