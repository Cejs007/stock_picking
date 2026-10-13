# CLAUDE.md — Stock Picking

## Project overview

A personal stock-valuation dashboard for value investing. The user keeps a
**watchlist**. For each ticker the app does the following:

1. Fetches fundamentals: yfinance today, FMP planned in v2.
2. Values the company with several independent models (DCF, Graham, P/E relative, EV/EBITDA relative and others).
3. Blends them into a sector-weighted **composite fair value**.
4. Applies a **margin of safety** (MoS) to get a buy target and a **BUY / WAIT / N/A** signal.

A **decision journal** snapshots the ranking at purchase time so past decisions can be scored against the alternatives.

It is decision support for the user's own research, not an automated trader. Nothing here places orders.

**Start here:**
- [README.md](README.md) is the user guide.
- [docs/PRD.md](docs/PRD.md) has v1 and the **v2** section (GitHub #17), the source of truth for current work.
- [docs/PLAN.md](docs/PLAN.md) is the original v1 plan.

**Ensemble weight tuning:** [docs/AUTORESEARCH.md](docs/AUTORESEARCH.md).

**Future screener (phase 6):** [docs/SCREENER.md](docs/SCREENER.md).

**Work queue:** GitHub issues #12–#37. Each issue lists its user stories, acceptance criteria and `Blocked by`. Labels: `ready-for-agent` (AFK) and `ready-for-human` (HITL, needs a decision from the user).

Docs (PRD, issues) are in Czech. Code, comments, tests and the README are in English.

## Commands

```bash
uv run pytest                                          # full suite, no network
uv run streamlit run src/stock_picking/ui/app.py       # dashboard
uv run python -m stock_picking.research.autoresearch run   # tune ensemble weights
```

## File handling

- **Never Read `*.db` files** (`stock_picking.db`, `autoresearch_cache.db`). They are binary SQLite. Inspect them through the project's own `Cache`/`watchlist`/`journal` APIs or a short `sqlite3` query, looking at schema and a few rows only.
- **`research/*.json(l)` are generated artifacts and are gitignored.** Regenerate them with the harness; don't hand-edit them. Read `dataset.json` only in slices.
- **`.env` holds the FMP API key.** Never read it, print it or commit it. Config comes from `Settings` (pydantic-settings).

## Code structure

Layout is `src/stock_picking/`, with tests in `tests/` (pytest `pythonpath = src`).

Responsibilities split as follows:

- **Pure calculation core, with no I/O.** This covers valuation models (`models/`), the composite, and in v2 also quality, margin of safety, rank score, FX conversion and backtest metrics.
  - Each model has the signature `calculate(FinancialData, ModelConfig) -> (float | None, list[str])`.
  - A model that can't compute returns **`None` plus a warning, never an exception**. The UI shows N/A with the reason.
- **I/O only at the boundaries.** This means `data/fetcher.py`, `data/cache.py`, the FMP client, `watchlist.py` and `journal.py`. Everything entering here is external input: validate it (pydantic) before it reaches the core.
- **`valuator.py` orchestrates.** It builds the config from `Settings` plus per-ticker overrides, runs the models and composite, and produces a `ValuationResult`. It has no math of its own.
- **UI is render-only.** All table rows, formatting, colours, filters and chart data are pure functions in `ui/presenter.py`, and those are tested. `ui/app.py` and the Streamlit pages only draw what the presenter returns.
- **Model registry (v2, #24).** Once it lands, adding a model means writing the model function and adding one registry entry. If you find yourself editing a hand-written list of model names somewhere else, extend the registry instead.
- **Keep the screener possible.** v2 is scoped to the watchlist. A market-wide screener is deferred to phase 6, but its scalability rules apply now: [docs/SCREENER.md §2](docs/SCREENER.md).
  - The core never reads the watchlist or the DB.
  - `fetch_all` takes any ticker list.
  - Cache TTL is per data type.
  - The FMP client tracks its quota and degrades gracefully.
  - Valuations have no foreign key to `watchlist`.
  - The refresh logic is a callable function, not Streamlit-only code.
- **Extract shared helpers, never copy-paste.** For example, `_optional_float` in the fetcher is reused, not redefined.

## Financial correctness rules

These are the bugs that silently produce plausible-looking wrong numbers. Check every change against them:

- **Units:** rates are decimals (`0.10`, not `10`), and history lists are **oldest first**. Say in the field comment whether a value is **total** (FCF, EBITDA, debt, cash, EV) or **per share** (EPS, BVPS, DPS). DCF computes per share; EV-based models divide by `shares_outstanding`.
- **Currency:** never assume USD. Fundamentals may be reported in a different currency from the quote (ADRs, EU listings), so convert before mixing them with price (#21). Ratios and multiples are never converted.
- **Discounting guards:** any Gordon/terminal formula must return N/A when `WACC <= g`. Auto-derived growth is clamped and emits a warning; an explicit user override is not clamped.
- **Overrides:** a per-ticker override applies **only when it is actually set**. Otherwise the global `Settings` value applies (#18).
- **Reverse DCF is a diagnostic.** It must never enter the composite, because a value derived from the price would pull the composite toward the price.
- **Backtest has no look-ahead.** Valuation at decision date T may only use statements filed at least 3 months before T. The AutoResearch objective must measure stock-picking skill (rank IC vs. forward returns), not fit to the current price.
- **WACC is a manual required return** (default 10 %) with a per-ticker override. Don't introduce CAPM/beta. That was decided and is out of scope.

## Test-first rule

**Use the `tdd` skill for all implementation:** red, green, refactor per component.

Before writing any component:
1. Define what "correct" means: the expected outputs, ranges and edge cases.
2. Write the test.
3. Confirm it fails on a stub.
4. Implement until it passes.

**Numeric tests use hand-computed literals.** The expected fair value, F-score or MoS is a number worked out by hand (show the arithmetic in a short comment), with `pytest.approx`.

**Never build the expectation by re-running the formula under test, or from the module constant that produced it.** For example, `expected = settings.default_mos * ...` compares the code with itself and stays green through any edit. When in doubt, mutate the formula or constant and confirm the test goes red.

Always cover the edge cases: missing data, non-positive values, `WACC <= g`, clamping, a single active model, financials sector exclusions.

**No network in the default suite.** A plain `pytest` makes no network calls: yfinance and FMP are mocked.

### Data-source adapter contract (FMP client, fetcher, FX)

An adapter does not land without both of these:

1. **An offline test that pins the request in literals.** That means the endpoint URL and query params written out as strings, not compared against the module's own constants. It must also cover:
   - retry with backoff on timeout;
   - fallback to yfinance when FMP fails or there is no key;
   - an assertion that the **API key never appears** in exception text or log output.
2. **A live check that asserts, gated behind `pytest --live`.**
   - Register the `live` marker under `--strict-markers` when the first live test is added.
   - The live check drives the adapter's own fetch and mapping for AAPL, MSFT and CEZ.PR.
   - It asserts non-empty history and correct currency.
   - A live run that only prints is not a check.
   - When offering live output as evidence, state which tickers or sources actually ran and which were skipped (for example, no FMP key).

## Git workflow (per issue)

1. **Branch first.** Before editing any file, create a branch from `main` named `<type>/<issue-number>-<slug>` (for example `fix/18-override-global-defaults`):

   ```bash
   git checkout main && git pull && git checkout -b <type>/<issue-number>-<slug>
   ```

   Never commit issue work directly to `main`.
2. **Implement test-first** per the rule above.
3. **Gate on green.** Run the full suite and don't commit while anything fails.
4. **Commit once tests pass.**
   - Use an imperative summary that matches the history (`Fix …`, `Add …`, `Implement …`).
   - Reference the issue in the body with `Closes #<n>`.
5. **Open a PR** against `main` with `gh pr create`.
   - The body covers what changed, why, and what to verify.
   - Link the issue.
   - Don't merge unless asked.

Commit or push only when the issue's work is complete and verified, or when the user explicitly asks.

## Workflow guidelines

- Prefer simple, explicit code over abstractions. Three similar functions beat one premature abstraction.
- No speculative features. Build only what the current issue asks for, and stay within its acceptance criteria.
- No error handling for scenarios that cannot happen. Validate only at real boundaries: the data APIs, the DB, user input in the UI.
- No comments unless the WHY is non-obvious. Never explain what the code does. Financial formulas are the exception: name the method and its source (for example "Greenwald EPV").
