# PRD: Stock Picking — Fair Valuation System

## Problem Statement

Investor přecházející z pravidelného ETF investování na aktivní stock picking nemá žádný systematický způsob, jak ocenit akcie, porovnat je mezi sebou a zpětně vyhodnotit kvalitu svých rozhodnutí. Ruční oceňování v tabulkách je pomalé, nesystematické a nenabízí žádný audit trail. Výsledkem je, že nákupní rozhodnutí závisí na intuici místo na datech, a neexistuje způsob, jak zjistit, zda by byl lepší výsledek dosažen koupí jiné akcie.

## Solution

Webová aplikace (Streamlit) automaticky oceňuje 50+ akcií čtyřmi valuačními modely (DCF, Graham Number, P/E relativní, EV/EBITDA relativní), kombinuje je do kompozitního skóre s nastavitelnými váhami, a říká investorovi jasně: "co a za kolik koupit." Součástí je decision journal, který ke každému nákupu přiřadí ranking snapshot a umožňuje retrospektivně porovnat výnos koupené akcie s nejlepšími alternativami, které byly v momentě nákupu k dispozici.

---

## User Stories

### Watchlist a oceňování

1. Jako investor chci vidět přehlednou tabulku všech sledovaných akcií se všemi fair values a buy signály, abych mohl jedním pohledem rozhodnout, co koupit.
2. Jako investor chci, aby se data refreshovala paralelně pro všechny tickery s progress barem, abych nemusel čekat neúměrně dlouho při watchlistu 50+ firem.
3. Jako investor chci vidět sloupec s měnou každé akcie, abych věděl, v jaké měně je fair value vyjádřena.
4. Jako investor chci, aby buňky s fair value byly barevně odlišeny (zelená = cena pod FV, červená = nad FV), abych okamžitě viděl, které akcie jsou podhodnoceny.
5. Jako investor chci, aby řádky s BUY signálem byly vizuálně zvýrazněny, abych je okamžitě odlišil od ostatních.
6. Jako investor chci tabulku defaultně seřazenou dle Master Score sestupně, abych viděl nejzajímavější příležitosti nahoře.
7. Jako investor chci exportovat tabulku do CSV, abych ji mohl sdílet nebo dále zpracovat.
8. Jako investor chci vidět sloupcová záhlaví s popisem (tooltip/otazník), abych rozuměl, co každý model počítá.
9. Jako investor chci Plotly grouped bar chart pod tabulkou (4 pruhy na ticker + čára aktuální ceny), abych vizuálně porovnal, jak se jednotlivé modely liší.

### Přidání a konfigurace akcií

10. Jako investor chci přidat novou akcii do watchlistu zadáním tickeru, abych rozšířil svůj universe.
11. Jako investor chci nastavit per-ticker Margin of Safety override, abych mohl zohlednit různou rizikovost různých firem.
12. Jako investor chci přepsat DCF parametry (growth rate, WACC, terminal g, projection years) pro konkrétní ticker, abych mohl modelovat konzervativnější nebo agresivnější scénáře.
13. Jako investor chci nastavit globální váhy modelů pomocí sliderů s automatickou normalizací, abych přizpůsobil mix modelů svému přístupu k oceňování.
14. Jako investor chci "Preview" výsledků před uložením, abych viděl, jaký vliv mají zadané parametry na fair value.
15. Jako investor chci, aby globální default WACC byl 10 % a default MoS 25 %, abych mohl začít bez konfigurace.
16. Jako investor chci globální default growth rate odvozený automaticky z 5letého FCF CAGR, abych nemusel zadávat historická data ručně.

### Detail akcie

17. Jako investor chci vidět detail konkrétní akcie s metrickými kartami (Cena, Master Score, Buy Target, Signal), abych rychle pochopil situaci.
18. Jako investor chci vidět grouped bar chart s fair values všech modelů a compositem vs. aktuální cenou, abych viděl, jak se modely rozcházejí.
19. Jako investor chci vidět historický price chart (2 roky) s kompozitní fair value jako čárou, abych pochopil, zda je akcie historicky levná nebo drahá.
20. Jako investor chci vidět tabulku klíčových fundamentálních dat (EPS, BVPS, FCF, EBITDA, ...), abych mohl posoudit kvalitu vstupů.
21. Jako investor chci vidět DCF projekci (FCF year 1–10 + terminal value), abych rozuměl, co DCF model předpokládá.
22. Jako investor chci vidět seznam aktivních modelů a varování (proč je nějaký model N/A), abych věděl, na jakých datech composite závisí.

### Validace dat a robustnost

23. Jako investor chci, aby model vrátil N/A s varováním (ne chybu), pokud firma nemá dostatek historických dat (< 3 roky pro P/E a EV/EBITDA), abych věděl, proč composite nezahrnuje všechny modely.
24. Jako investor chci, aby DCF vrátil N/A s varováním, pokud jsou všechny roky FCF záporné, abych věděl, že model nelze aplikovat.
25. Jako investor chci, aby Graham Number vrátil N/A (bez chyby), pokud je EPS nebo BVPS ≤ 0, abych viděl konzistentní chování.
26. Jako investor chci, aby composite zahrnul pouze modely s nenulovou fair value a přepočítal váhy, abych dostal robustní skóre i při částečné dostupnosti dat.
27. Jako investor chci, aby FMP API bylo opt-in přes env var a při absenci klíče bylo tiché (ne crash), abych mohl spustit aplikaci bez API klíče.

### Cache a výkon

28. Jako investor chci, aby data byla cachována v SQLite s TTL 24 h, abych se vyhnul zbytečným API voláním.
29. Jako investor chci tlačítko "Force refresh" které ignoruje TTL a znovu fetchne všechna data, abych mohl získat aktuální data před nákupem.
30. Jako investor chci, aby fetch 50+ tickerů probíhal paralelně pomocí ThreadPoolExecutor, abych nemusel čekat minuty na refresh watchlistu.

### Decision journal — snímky a nákupy

31. Jako investor chci před nákupem uložit snapshot pořadí všech tickerů s datumem, abych měl auditní stopu o situaci v momentě rozhodnutí.
32. Jako investor chci zadat nákup (datum, ticker, cena, množství) přes formulář v UI, abych evidoval svá investiční rozhodnutí.
33. Jako investor chci, aby každý nákup byl provázán s nejbližším snapshotem, abych mohl retrospektivně hodnotit, co bylo k dispozici v momentě nákupu.

### Retrospektiva

34. Jako investor chci vidět tabulku nákupů s aktuálním výnosem %, pořadím v snapshotu a nejlepší alternativou ze snapshotu, abych věděl, zda jsem udělal dobrou volbu.
35. Jako investor chci sloupec Δ (výnos koupené akcie − výnos nejlepší alternativy), abych viděl, o kolik jsem překonal nebo zaostal za nejlepší dostupnou alternativou.
36. Jako investor chci barevné odlišení Δ (zelená = překonal nejlepší alt., červená = zaostal), abych okamžitě viděl kvalitu rozhodnutí.
37. Jako investor chci Plotly line chart výnosu zakoupené akcie vs. top 3 alternativ od data nákupu, abych sledoval, jak se volby v čase rozcházejí.
38. Jako investor chci vidět top 10 alternativ ze snapshotu pro každý nákup, abych měl dostatečný kontext pro retrospektivu.

---

## Implementation Decisions

### Moduly a jejich rozhraní

**`data/cache.py`**
SQLite cache s TTL. Klíč je `(ticker, data_type)`. Metody: `get(ticker, data_type) -> dict | None`, `set(ticker, data_type, data)`, `invalidate(ticker)`. TTL kontrola při `get` — vrátí `None` pokud expired. `force_refresh` flag na volajícím místě (v `fetcher.py`).

**`data/yf_client.py`**
Tenký wrapper nad `yfinance`. Vrací pydantic model `FinancialData` se všemi poli potřebnými pro oceňovací modely. Nikdy nevyhazuje výjimky — chybějící pole = `None` v modelu.

**`data/fmp.py`**
Opt-in klient. Guard na začátku: `if not os.getenv("FMP_API_KEY"): raise RuntimeError(...)`. Vrací stejný `FinancialData` formát jako `yf_client`.

**`data/fetcher.py`**
`fetch_all(tickers: list[str], force_refresh: bool = False) -> dict[str, FinancialData]` pomocí `ThreadPoolExecutor`. Interně volá cache; miss → yf_client; uloží do cache.

**`models/dcf.py`**, **`models/graham.py`**, **`models/pe_relative.py`**, **`models/ev_ebitda.py`**
Každý model je pure funkce: `calculate(data: FinancialData, config: ModelConfig) -> tuple[float | None, list[str]]`. Žádný side-effect, žádný I/O.

**`models/composite.py`**
`calculate_composite(results: dict[str, tuple[float | None, list[str]]], weights: dict[str, float]) -> tuple[float | None, list[str], list[str]]` — vrací `(fair_value, active_models, all_warnings)`. Přepočítá váhy přes aktivní modely.

**`settings.py`**
Pydantic `Settings` model načítaný z env / `.env` souboru. Obsahuje: `model_weights`, `default_mos`, `default_wacc`, `default_terminal_g`, `default_projection_years`, `cache_ttl_hours`, `fmp_api_key`.

**`watchlist.py`**
CRUD pro watchlist a per-ticker overrides v SQLite. Ukládá také poslední výsledky valuace do tabulky `valuations`.

**`journal.py`**
`save_snapshot(tickers_ranked: list[dict])`, `log_purchase(purchase: Purchase)`, `get_retrospective(purchase_id: int) -> RetroResult`. Retrospektiva počítá výnosy jako `(current_price - price_paid) / price_paid` pro koupenou akcii i alternativy.

### Datový model

Klíčový pydantic model `FinancialData` zahrnuje:
- `ticker`, `company_name`, `currency`
- `current_price`, `eps_ttm`, `bvps`, `fcf_history` (list 5+ let), `ebitda`, `ev`, `total_debt`, `cash`, `shares_outstanding`
- `pe_history` (list 5+ let), `ev_ebitda_history` (list 5+ let)

### Master Score

`master_score = upside_pct = (fair_value_composite - current_price) / current_price * 100`. Vyšší = zajímavější příležitost.

### SQLite schema

Čtyři tabulky: `cache`, `watchlist`, `valuations`, `ranking_snapshots`, `purchases`. Schema definováno v PLAN.md.

### Architektonická rozhodnutí

- Modely jsou pure funkce — testovatelné bez DB nebo sítě.
- Cache a persistence jsou v SQLite (stdlib) — nulová external dependency.
- FMP je opt-in — aplikace běží bez API klíče.
- Streamlit `st.session_state` pro progress bar stav během paralelního fetche.
- Všechny globální defaulty jsou v `settings.py`; per-ticker overrides v DB.

---

## Testing Decisions

Testy ověřují **externí chování** (vstupy → výstupy), ne implementační detaily. Modely jsou pure funkce, takže nevyžadují live API ani DB — fixture `FinancialData` v `conftest.py` stačí pro celou test suite. Konkrétní testovací případy vzniknou inline v TDD cyklu při implementaci každého modulu.

---

## Out of Scope

- Automatické nákupy nebo propojení s brokerem.
- Real-time (intraday) ceny — data jsou end-of-day z yfinance.
- Portfolio tracking (celkový výnos portfolia, alokace, rebalancing).
- Screener nad celým trhem — aplikace pracuje pouze s explicitně přidanými tickery.
- Alerting (email/push notifikace při dosažení buy targetu).
- Multi-user podpora nebo autentizace.
- Backtesting oceňovacích modelů.
- Automatický refresh na pozadí (cron) — refresh je vždy manuální.

---

## Further Notes

- Projekt začíná od nuly — žádný existující kód.
- Implementační pořadí je definováno v PLAN.md: scaffolding → cache/data → modely → composite/settings → journal → Streamlit app → smoke test.
- Smoke test ověřuje AAPL, MSFT a CEZ.PR (mix US large-cap a středoevropská firma s kratší historií).
- Barvy a vizuální styl Streamlit aplikace nejsou specifikovány — použít výchozí téma.
- Retrospektivní výpočet "nejlepší alternativa" bere top 10 z rankingového snapshotu (excl. koupené akcie) seřazeného dle Master Score.
