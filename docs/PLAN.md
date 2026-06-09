# Stock Picking — Fair Valuation System

## Context

Přechod z pravidelného ETF investování na stock picking. Potřeba: automatizované férové naceňování akcií pomocí více modelů, nastavitelný margin of safety, a přehledná webová tabulka říkající "co a za kolik koupit." Decision journal pro zpětné hodnocení měsíčních nákupů. Projekt začíná od nuly.

---

## Rozhodnutí z grillingu

| Téma | Rozhodnutí |
|---|---|
| Data zdroj | yfinance jako primár; FMP opt-in (env var) |
| DCF growth rate | Auto z 5letého FCF CAGR, přepisovatelné per-ticker |
| DCF WACC | Globální default 10 %, přepisovatelné per-ticker |
| Neplatný model | N/A + varování; vyloučen z kompozitu |
| Váhy modelů | Globální (jednou nastavené), ne per-ticker |
| Měny | Původní měna firmy + jasný sloupec s měnou |
| Snapshot | Manuální tlačítko v UI před nákupem |
| Purchase log | Manuální formulář: datum, ticker, cena, množství |
| Retrospektiva | Top 10 alternativ ze snapshotu |
| Watchlist velikost | 50+ firem → paralelní fetch (ThreadPoolExecutor) + agresivní cache |
| P/E/EV fallback | Min. 3 roky dat → použij s varováním; méně = N/A |

---

## Tech stack

- **uv** + `pyproject.toml`
- **Streamlit** — webová aplikace
- **yfinance** — primární datový zdroj
- **requests** — FMP API (opt-in, pokud nastaven `FMP_API_KEY`)
- **pandas**, **plotly** — tabulky a grafy
- **pydantic v2** — validace dat a konfigurace
- **SQLite** (stdlib `sqlite3`) — cache s TTL + persistence (watchlist, snapshots, purchases)
- **concurrent.futures.ThreadPoolExecutor** — paralelní fetch pro 50+ tickerů

---

## Struktura projektu

```
c:\Users\582887\Code\Stock_picking\
  src/
    stock_picking/
      data/
        yf_client.py     # yfinance wrapper — ceny, fundamenty, historická data
        fmp.py           # FMP API klient (opt-in, guard: if not FMP_API_KEY: raise)
        cache.py         # SQLite cache s TTL (default 24h); force_refresh flag
        fetcher.py       # ThreadPoolExecutor wrapper — paralelní fetch N tickerů
      models/
        dcf.py           # DCF: FCF CAGR auto-derivace + WACC; vrací (fair_value | None, warnings)
        graham.py        # Graham Number: sqrt(22.5 × EPS × BVPS); None pokud EPS/BVPS ≤ 0
        pe_relative.py   # P/E median (min 3 roky); None + warning pokud méně dat
        ev_ebitda.py     # EV/EBITDA median (min 3 roky); None + warning pokud méně dat
        composite.py     # Vážený průměr aktivních modelů; vrací (fair_value, active_models, warnings)
      watchlist.py       # CRUD watchlist + per-ticker DCF overrides (SQLite)
      journal.py         # Snapshot CRUD, purchase log, retrospektivní výpočty
      settings.py        # Globální konfigurace: váhy modelů, default MoS, default WACC
      app.py             # Streamlit entry point
  tests/
    conftest.py          # Fixture data (statické JSON odpovědi z yfinance)
    test_dcf.py
    test_graham.py
    test_pe_relative.py
    test_ev_ebitda.py
    test_composite.py
    test_journal.py
  pyproject.toml
  .env.example           # FMP_API_KEY= (volitelné)
  .gitignore
```

---

## Datový tok

```
Uživatel spustí "Refresh all"
  → fetcher.py rozdělí tickery do ThreadPoolExecutoru
      → pro každý ticker: cache.py zkontroluje TTL
          → hit: vrátí uložená data
          → miss: yf_client.py fetchne data (FMP jako opt-in rozšíření)
              → data uloží do cache
                  → každý model dostane FinancialData (pydantic)
                      → composite.py spočítá fair_value + active_models + warnings
                          → watchlist.py uloží výsledek
                              → Streamlit zobrazí tabulku s progress barem
```

---

## Oceňovací modely

### DCF
```python
# Vstupy (globální defaults, přepisovatelné per-ticker):
fcf_growth_rate: float  # auto: 5letý FCF CAGR z yfinance; přepisovatelné
discount_rate: float = 0.10       # WACC
terminal_growth_rate: float = 0.03
projection_years: int = 10

# Výstup: (fair_value_per_share | None, list[str] warnings)
# None pokud: FCF záporné všechny roky, nebo nedostatek dat
```

### Graham Number
```python
# sqrt(22.5 × EPS_ttm × BVPS)
# None pokud EPS_ttm ≤ 0 nebo BVPS ≤ 0
```

### P/E relativní
```python
# fair_pe = median(trailing_pe, min 3 roky z posledních 5)
# fair_value = fair_pe × EPS_ttm
# None + warning pokud méně než 3 roky dat
```

### EV/EBITDA relativní
```python
# fair_ev_ebitda = median(ev_ebitda_ratio, min 3 roky z posledních 5)
# zpětný výpočet: fair_ev = fair_ratio × EBITDA; fair_price = (fair_ev - debt + cash) / shares
# None + warning pokud méně než 3 roky dat nebo záporné EBITDA
```

### Composite
```python
# active = [m for m in models if m.fair_value is not None]
# fair_value = sum(w_i × fv_i for i in active) / sum(w_i for i in active)
# Globální váhy nastaveny v settings.py (default: rovnoměrné)
```

---

## Margin of Safety & buy signal

```python
buy_target = fair_value * (1 - margin_of_safety)  # default MoS = 0.25
upside_pct = (fair_value - current_price) / current_price * 100
signal = "BUY" if current_price <= buy_target else "WAIT"
```

MoS nastavitelný globálně v settings + přepisovatelný per-ticker.

---

## Streamlit aplikace — 4 stránky

### 1. Watchlist (hlavní)

Tabulka (`st.data_editor` s `column_config`), sortovatelná, defaultně dle Master Score DESC:

| Ticker ↕ | Název | Cena | Měna | DCF FV | Graham FV | P/E FV | EV/EBITDA FV | **Master Score ↕** | Buy Target | MoS | Signal |
|---|---|---|---|---|---|---|---|---|---|---|---|

- Záhlaví sloupců: `help=` popis (otazník ikonka) — vysvětlivka každého modelu
- Fair value buňky: zelená = cena pod FV, červená = nad FV
- Řádky s `BUY` signálem: zvýrazněné pozadí
- Progress bar při refreshi: "Načítám 3 / 52..."
- Tlačítka: "Refresh all", "Force refresh" (ignoruje TTL), "Export CSV", "Uložit snapshot"

Plotly grouped bar chart pod tabulkou: pro každý ticker 4 pruhy (modely) + reference linka = aktuální cena.

### 2. Přidat / upravit akcii

- Formulář: ticker, MoS override, DCF overrides (growth rate, WACC, terminal g, years)
- Globální váhy modelů (slidery, auto-normalizace)
- "Preview" — zobrazí fair values před uložením

### 3. Detail akcie

- Metrické karty nahoře: Cena | Master Score | Buy Target | Signal
- Plotly grouped bar: 4 modely + composite vs. aktuální cena
- Plotly line chart: historická cena (2 roky) + composite FV jako čára
- Tabulka fundamentálních dat (EPS, BVPS, FCF, EBITDA, ...)
- DCF projekce: tabulka FCF year 1–10 + terminal value
- Aktivní modely + varování (proč je nějaký model N/A)

### 4. Historie rozhodnutí

Tabulka nákupů:

| Datum | Ticker | Pořadí v snapshotu | Nákupní cena | Aktuální výnos % | Nejlepší alternativa (top 10) | Výnos nejlepší alt. % | Δ |
|---|---|---|---|---|---|---|---|

- **Δ** = výnos koupené akcie − výnos nejlepší alternativy ze snapshotu
- Zelená Δ = překonal nejlepší alternativu; červená = horší volba
- Plotly line chart: výnos zakoupené akcie vs. top 3 alternativ v čase (od data nákupu)
- Formulář pro zadání nákupu: datum, ticker, cena, množství

---

## SQLite schema

```sql
-- Cache
CREATE TABLE cache (
    ticker TEXT NOT NULL,
    data_type TEXT NOT NULL,  -- 'fundamentals', 'price_history', etc.
    data JSON NOT NULL,
    fetched_at TIMESTAMP NOT NULL,
    PRIMARY KEY (ticker, data_type)
);

-- Watchlist
CREATE TABLE watchlist (
    ticker TEXT PRIMARY KEY,
    company_name TEXT,
    currency TEXT,
    mos_override REAL,          -- NULL = použij globální default
    dcf_growth_override REAL,   -- NULL = auto z CAGR
    dcf_wacc_override REAL,     -- NULL = globální default (0.10)
    dcf_terminal_g REAL DEFAULT 0.03,
    dcf_years INTEGER DEFAULT 10,
    added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Valuation results (poslední výsledky per ticker)
CREATE TABLE valuations (
    ticker TEXT PRIMARY KEY,
    fair_value_dcf REAL,
    fair_value_graham REAL,
    fair_value_pe REAL,
    fair_value_ev_ebitda REAL,
    fair_value_composite REAL,
    current_price REAL,
    master_score REAL,
    buy_target REAL,
    signal TEXT,
    warnings JSON,
    calculated_at TIMESTAMP
);

-- Decision journal
CREATE TABLE ranking_snapshots (
    id INTEGER PRIMARY KEY,
    snapshot_date DATE NOT NULL,
    ticker TEXT NOT NULL,
    rank INTEGER,
    fair_value_composite REAL,
    current_price REAL,
    master_score REAL,
    signal TEXT
);

CREATE TABLE purchases (
    id INTEGER PRIMARY KEY,
    purchase_date DATE NOT NULL,
    ticker TEXT NOT NULL,
    price_paid REAL NOT NULL,
    quantity REAL,
    snapshot_id INTEGER REFERENCES ranking_snapshots(id)
);
```

---

## Implementační pořadí

1. **Scaffolding** — `uv init`, `pyproject.toml`, `.env.example`, `.gitignore`, `git init`
2. **Cache + yf_client** — `cache.py` (SQLite TTL), `yf_client.py`, `fetcher.py` (ThreadPoolExecutor); unit testy s mock yfinance
3. **Oceňovací modely** — každý jako pure funkce vracející `(float | None, list[str])`; unit testy s fixture daty
4. **Composite + settings** — `composite.py`, `settings.py`; watchlist CRUD
5. **Decision journal** — `journal.py` (snapshot, purchase log, retrospektivní výpočty)
6. **Streamlit app** — 4 stránky, tabulky s `column_config`, plotly grafy, progress bar
7. **End-to-end smoke test** — AAPL, MSFT, CEZ.PR: refresh, snapshot, purchase log, retrospektiva

---

## Ověření po implementaci

- `uv run streamlit run src/stock_picking/app.py` spustí bez chyb
- Refresh 52 tickerů s progress barem, bez timeoutu
- AAPL: všechny 4 modely vrátí nenulovou fair value
- Firma s kratší historií (< 3 roky): P/E = N/A + varování v detailu
- Force refresh ignoruje TTL a znovu fetchne
- MoS 25 % → buy_target = fair_value × 0.75
- Tabulka seřazena dle Master Score DESC
- Snapshot uloží pořadí všech tickerů s datem
- Purchase log: zadání nákupu → provázání s nejbližším snapshotem
- Retrospektiva zobrazí top 10 alternativ + Δ výnos
- Export CSV funguje
