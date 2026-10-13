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

---
---

# PRD v2: Spolehlivá vnitřní hodnota, kvalita firmy, dynamická MoS, UI a backtest

> Rozšíření v1. Kde se v2 s v1 rozchází, platí v2. Zejména:
> - backtesting je nyní **in scope**;
> - FMP už není jen volitelný doplněk, ale preferovaný zdroj historických dat;
> - v1 user story 13 (globální slidery vah) se ruší. Váhy jsou podle sektoru, nastavují se v konfiguraci a ladí backtestem; UI je zobrazuje jen pro čtení (rozhodnuto 2026-10-13).

## Problem Statement

Investor má funkční jádro aplikace: 4 oceňovací modely, kompozit s vahami podle sektoru, margin of safety 25 % a signál BUY/WAIT. Výsledkům ale nemůže věřit:

- **Na živých datech běží jen dva modely ze čtyř.** P/E relativní a EV/EBITDA relativní vrací vždy N/A, protože se nestahuje historie násobků. Kompozit tak stojí jen na Grahamovi a DCF. Graham je navíc u technologických firem nepoužitelný.
- **DCF nadhodnocuje:**
  - neodečítá čistý dluh;
  - extrapoluje neomezený historický růst FCF po celých 10 let;
  - nehlídá případ, kdy je WACC ≤ terminálnímu růstu;
  - u tickerů na watchlistu ignoruje globální nastavení.
- **Margin of safety je pro všechny stejná.** Platí stejně pro kvalitního kompaundera i pro zadluženou cyklickou firmu. Nezohledňuje ani to, jak moc se modely navzájem rozcházejí.
- **Řazení nevidí kvalitu podniku.** Zná jen upside k férové hodnotě, ne ROIC, dluh nebo stabilitu. Nahoru proto vyplavou „value traps“: akcie, které jsou levné, protože je podnik špatný.
- **Měny jsou špatně:**
  - evropské a české akcie se zobrazují se znakem `$`;
  - když jsou fundamenty v jiné měně než cena (ADR), nepřepočítávají se.
- **Váhy modelů se ladí na špatný cíl.** Optimalizují se tak, aby férová hodnota kopírovala tržní cenu, což neměří schopnost najít podhodnocení. Investor tak neví, zda by se podle signálů vůbec vyplatilo nakupovat.
- **UI je jediná tabulka.** Nastavení pro jednotlivé tickery, detail akcie ani decision journal nejsou dostupné.

## Solution

Aplikace pro US i EU/CZ akcie bude dělat šest věcí:

1. **Data.** Stáhne 10letou historii výkazů a násobků z FMP, s yfinance jako fallbackem, a sjednotí měny.
2. **Vnitřní hodnota.** Spočítá ji sadou opravených a nových modelů:
   - DCF v2 s postupně klesajícím růstem a odečtením čistého dluhu
   - EPV, DDM, Graham s růstem
   - P/E relativní a EV/EBITDA relativní
   - Výsledkem je **rozpětí** férové hodnoty, ne jen jedno číslo. Reverse DCF navíc ukáže, jaký růst už cena implikuje.
3. **Kvalita podniku.** Ohodnotí ji skóre 0–100 z těchto metrik: ROIC, zadlužení, úrokové krytí, Piotroski F-score, stabilita marží a FCF a ředění akcií.
4. **Margin of safety a řazení.** Z kvality a z rozptylu modelů odvodí **dynamickou margin of safety** s rozpadem na složky a z ní nákupní cenu. Řazení kombinuje upside a kvalitu.
5. **UI.** Vše zobrazí ve vícestránkovém Streamlit UI: watchlist, editace tickeru, detail akcie, decision journal.
6. **Backtest.** Na historických datech ověří, zda vyšší rank skóre opravdu předpovídá vyšší budoucí výnos, a podle toho ladí váhy modelů.

WACC zůstává ručně zadaná požadovaná výnosnost (default 10 %). Pro každou akcii jde přepsat; CAPM se nepoužívá.

## User Stories

### Opravy a důvěryhodnost výpočtu

1. Jako investor chci, aby ticker bez vlastního nastavení terminálního růstu a délky projekce používal globální nastavení, abych změnou jednoho defaultu ovlivnil celý watchlist.
2. Jako investor chci, aby DCF vrátil N/A s varováním, když je WACC ≤ terminální růst, abych nedostal nesmyslnou nebo zápornou férovou hodnotu.
3. Jako investor chci, aby automaticky odvozený růst FCF měl horní a dolní mez a abych při oříznutí dostal varování, aby jeden výjimečný rok nevyrobil pětinásobnou férovou hodnotu.
4. Jako investor chci, aby každé ocenění mělo skutečný čas výpočtu, abych věděl, jak stará čísla vidím.
5. Jako investor chci, aby běžné obnovení dat respektovalo cache a obcházel ji jen „Force refresh“, abych zbytečně nečekal a nevyčerpal limity API.

### Data a měny

6. Jako investor chci, aby se stahovala až 10letá historie EPS, účetní hodnoty, tržeb, provozního a čistého zisku, FCF, počtu akcií a dividend, aby modely mohly pracovat s průměrnými hodnotami místo jednoho roku.
7. Jako investor chci, aby se stahovala historie P/E a EV/EBITDA, aby relativní modely přestaly vracet N/A.
8. Jako investor chci, aby FMP byl preferovaný zdroj a yfinance doplnil chybějící pole, abych měl co nejúplnější data i pro tickery, které FMP nepokrývá.
9. Jako investor chci u každého ocenění vidět, ze kterého zdroje data pocházejí, abych mohl posoudit jejich spolehlivost.
10. Jako investor chci, aby aplikace fungovala i bez FMP klíče (jen s yfinance) a aby modely s nedostatečnou historií vrátily N/A s varováním, abych ji mohl používat bez placeného API.
11. Jako investor chci, aby výpadek nebo pomalost FMP nezablokovaly obnovení dat: po timeoutu a několika opakováních se použije fallback, abych vždy dostal výsledek.
12. Jako investor chci, aby se fundamenty vykázané v jiné měně, než je kótovaná cena, přepočetly aktuálním kurzem, abych u ADR a evropských firem nesrovnával koruny s dolary.
13. Jako investor chci u každé akcie vidět správnou měnu (CZK u ČEZ, EUR u ASML apod.), abych věděl, v čem je férová hodnota vyjádřena.
14. Jako investor chci, aby se API klíč nikdy neobjevil v logu ani v chybové hlášce, abych ho omylem nezveřejnil.

### Vnitřní hodnota

15. Jako investor chci DCF, ve kterém počáteční růst postupně klesá k terminálnímu růstu, aby projekce odpovídala tomu, že vysoký růst nevydrží věčně.
16. Jako investor chci, aby DCF vycházel z průměru FCF za poslední roky, ne z jednoho roku, aby jednorázový výkyv nezkreslil ocenění.
17. Jako investor chci, aby DCF odečetl čistý dluh (dluh − hotovost) před přepočtem na akcii, abych dostal hodnotu pro akcionáře, ne pro celou firmu.
18. Jako investor chci Earnings Power Value (hodnotu současného výdělku bez růstu), abych věděl, kolik platím za růst a kolik za to, co firma už vydělává.
19. Jako investor chci dividendový model pro firmy se stabilní historií dividend (utility, ČEZ, banky), abych je ocenil metodou, která jim odpovídá.
20. Jako investor chci Grahamův vzorec s růstem a průměrným EPS, abych měl klasické value měřítko, které zohledňuje růst i úroveň úrokových sazeb.
21. Jako investor chci reverse DCF (jaký růst FCF implikuje dnešní cena) a jeho srovnání s historickým růstem, abych rychle viděl, zda trh čeká něco nerealistického.
22. Jako investor chci, aby reverse DCF nevstupoval do kompozitu, protože hodnota odvozená z ceny by kompozit jen táhla k ceně.
23. Jako investor chci vidět rozpětí férové hodnoty (minimum a maximum aktivních modelů) vedle kompozitu, abych chápal nejistotu ocenění.
24. Jako investor chci vidět míru neshody modelů (variační koeficient), abych poznal, kdy kompozit stojí na protichůdných odhadech.
25. Jako investor chci, aby každý nový model měl teoreticky zdůvodněné výchozí váhy podle sektoru (např. dividendový model jen pro utility, finance a reality), abych nemusel váhy nastavovat ručně.
26. Jako investor chci, aby přidání dalšího modelu nevyžadovalo zásahy na mnoha místech aplikace, aby se systém dal snadno rozšiřovat.

### Kvalita firmy

27. Jako investor chci vidět ROIC, jeho průměr a trend, abych poznal, zda firma vydělává víc, než ji stojí kapitál.
28. Jako investor chci vidět ROE, abych měl měřítko výnosnosti i u firem, kde ROIC nedává smysl.
29. Jako investor chci vidět poměr čistý dluh / EBITDA a úrokové krytí, abych odhalil firmy, kterým hrozí finanční potíže.
30. Jako investor chci Piotroski F-score (0–9), abych měl ověřený souhrnný signál finančního zdraví a jeho zlepšování.
31. Jako investor chci vidět stabilitu hrubé a provozní marže a podíl let s kladným FCF, abych odlišil předvídatelné podniky od cyklických.
32. Jako investor chci vidět tempo ředění (růst počtu akcií), abych poznal, zda management rozdává hodnotu přes emise a opce.
33. Jako investor chci jedno quality score 0–100, které tyto metriky shrnuje, abych mohl firmy rychle porovnat.
34. Jako investor chci, aby u bank a pojišťoven byly nevhodné metriky (EBITDA, úrokové krytí) vynechány s varováním, aby je skóre neodsoudilo neprávem.

### Margin of safety a řazení

35. Jako investor chci, aby margin of safety rostla s nižší kvalitou firmy a s větší neshodou modelů, abych u rizikovějších akcií vyžadoval větší slevu.
36. Jako investor chci, aby margin of safety měla dolní a horní mez, aby nikdy nebyla absurdně malá ani velká.
37. Jako investor chci vidět rozpad margin of safety (základ + přirážka za kvalitu + přirážka za neshodu modelů), abych rozuměl, proč je nákupní cena tam, kde je.
38. Jako investor chci, aby ručně zadaná margin of safety pro konkrétní ticker měla vždy přednost, abych mohl uplatnit vlastní úsudek.
39. Jako investor chci, aby všechny konstanty margin of safety šly nastavit v konfiguraci, abych je mohl později zkalibrovat podle backtestu.
40. Jako investor chci řazení podle rank skóre, které kombinuje upside a kvalitu, aby nahoře nebyly levné, ale špatné firmy.
41. Jako investor chci volitelně skrýt akcie s F-score pod 4 nebo úrokovým krytím pod 3, abych se rychle zbavil zjevně rizikových kandidátů.
42. Jako investor chci, aby se quality score, použitá margin of safety a rozpětí férové hodnoty ukládaly s oceněním i do snapshotu v decision journalu, abych mohl zpětně vyhodnotit i roli kvality.

### UI

43. Jako investor chci na watchlistu sloupce MoS, Quality, rozpětí férové hodnoty a měnu, abych měl vše podstatné v jednom pohledu.
44. Jako investor chci barevně zvýrazněné signály BUY/WAIT a podhodnocení, abych příležitosti viděl okamžitě.
45. Jako investor chci exportovat watchlist do CSV, abych mohl data dále zpracovat.
46. Jako investor chci tlačítkem uložit snapshot pořadí do decision journalu, abych měl před nákupem záznam o tehdejší situaci.
47. Jako investor chci graf ceny vs. rozpětí férové hodnoty pro všechny akcie, abych vizuálně porovnal podhodnocení a nejistotu.
48. Jako investor chci formulář pro přidání a úpravu tickeru s vlastním nastavením (WACC, růst, terminální růst, délka projekce, MoS) a s náhledem přepočtu před uložením, abych viděl dopad svých předpokladů.
49. Jako investor chci detail akcie, abych mohl udělat informované rozhodnutí. Detail bude obsahovat:
    - karty: cena, férová hodnota, nákupní cena, signál, quality score
    - rozpad MoS
    - tabulku DCF projekce
    - reverse DCF vs. historický růst
    - quality metriky a varování
    - cenový graf za 2 roky
50. Jako investor chci stránku decision journalu s evidencí nákupů a retrospektivou proti alternativám ze snapshotu, abych se učil z vlastních rozhodnutí.
51. Jako investor chci end-to-end smoke test na AAPL, MSFT a CEZ.PR (včetně měn a fallbacku), abych věděl, že celý řetězec funguje na reálných datech.

### Validace

52. Jako investor chci backtest, který pro historická data spočítá ocenění jen z informací tehdy dostupných (výkazy se zpožděním publikace), abych nevyhodnocoval s pomocí budoucnosti.
53. Jako investor chci vidět rank IC, tedy korelaci pořadí rank skóre s budoucím výnosem za 1 a 3 roky, abych věděl, zda skóre něco předpovídá.
54. Jako investor chci vidět výnos horního kvintilu proti celému universu a úspěšnost BUY signálů, abych pochopil praktický dopad.
55. Jako investor chci, aby se váhy modelů ladily na rank IC na validační sadě místo shody s cenou, aby optimalizace mířila na hledání podhodnocení.
56. Jako investor chci, aby backtest byl deterministický a jeho výsledky se ukládaly, abych mohl porovnávat běhy.
57. Jako investor chci mít zdokumentovaná omezení backtestu (survivorship bias, look-ahead bias, malý vzorek), abych výsledky nepřeceňoval.

## Implementation Decisions

### Datová vrstva

- **FMP klient (nový, hluboký modul).**
  - Rozhraní: pro ticker vrátí sadu ročních řad (výkazy, key-metrics, dividendy), nebo signalizuje, že data nejsou k dispozici.
  - Uvnitř řeší HTTP, timeout, retry s exponenciálním backoffem, cache přes existující SQLite cache a mapování polí FMP.
  - API klíč čte z nastavení a nikdy ho neloguje, ani jako součást URL v chybových hláškách. Bez klíče se FMP tiše nepoužije.
  - Odpovědi FMP se validují (typy, chybějící pole), protože externí vstup je nedůvěryhodný.
- **Fetcher: slučování zdrojů.** Pro jeden ticker spojí FMP a yfinance: FMP má přednost, yfinance doplní chybějící pole. Výsledek nese informaci, odkud která skupina polí pochází. Rozhraní paralelního `fetch_all` se nemění.
- **FX převod (nový, malý čistý modul + načtení kurzu).**
  - Když se měna výkazů liší od měny kotace, peněžní fundamenty se přepočtou kurzem. Kurz se bere z yfinance a cachuje.
  - Násobky a poměry se nepřepočítávají.
  - Převod je čistá funkce `(FinancialData, kurz) -> FinancialData`.
- **FinancialData: rozšíření.**
  - Nové řady, vždy od nejstaršího roku: EPS, BVPS, tržby, provozní zisk, čistý zisk, hrubý zisk, počet akcií, dividendy na akcii, investovaný kapitál, úrokové náklady, aktiva, krátkodobá aktiva a závazky a další vstupy pro F-score.
  - Nová pole: měna výkazů a zdroje dat.
  - Všechna nová pole mají výchozí hodnotu, aby šly validovat i staré záznamy v cache.

### Oceňování

- **Registr modelů.** Jedno místo, které mapuje jméno modelu na funkci `calculate(FinancialData, ModelConfig) -> (float | None, list[str])` a říká, zda model vstupuje do kompozitu. Valuátor iteruje přes registr. Seznam jmen modelů, výchozí sektorové váhy a sloupce výsledku se odvozují z něj.
- **Oceňovací modely** jsou čisté funkce a jejich signatura se nemění:
  - **DCF v2**, dvoufázový:
    - růst lineárně klesá z počátečního g na terminální g během projekce;
    - základem je průměr FCF za poslední 3 roky;
    - z enterprise value se na equity value přechází odečtením čistého dluhu;
    - když je WACC ≤ g, vrátí N/A;
    - automaticky odvozený růst se ořezává na [−5 %, 15 %] (nastavitelné); ručně zadaný růst se neořezává.
  - **EPV:** průměrná provozní marže × současné tržby × (1 − efektivní daň) / WACC + čistá hotovost, přepočteno na akcii.
  - **DDM:** Gordonův model z aktuální dividendy a udržitelného růstu dividend. Počítá se jen tehdy, když firma platí dividendu nepřetržitě alespoň minimální počet let, jinak N/A.
  - **Graham s růstem:** průměrné EPS × (8,5 + 2g) × 4,4 / Y, kde Y je výnos AAA dluhopisů z nastavení a g (v procentech) má mez.
  - **Reverse DCF:** numericky (bisekcí) najde počáteční růst, při kterém DCF v2 = aktuální cena. Je jen informativní a do kompozitu nevstupuje.
  - **Graham Number, P/E relativní a EV/EBITDA relativní** zůstávají. P/E a EV/EBITDA začnou fungovat díky historii násobků.
- **Kompozit.** Kromě váženého průměru vrací rozpětí (min, max) a variační koeficient aktivních modelů. Místo n-tice vrací strukturovaný výsledek.

### Kvalita, MoS a řazení

- **Quality (nový, hluboký modul).**
  - Čisté funkce nad FinancialData, výstupem je `QualityResult`: dílčí metriky, F-score, quality score 0–100 a varování.
  - Skóre je vážená kombinace normalizovaných dílčích metrik.
  - Metriky, které nelze spočítat nebo které pro daný sektor nedávají smysl (finance), se vynechají a váhy se přepočítají.
- **Margin of safety (nová čistá funkce).**
  - Vstup: quality score, variační koeficient a nastavení. Výstup: MoS a její rozpad.
  - Výchozí vzorec: základ 20 % + až 20 % za nízkou kvalitu (lineárně z quality score) + až 15 % za neshodu modelů (lineárně z CV, s horní mezí). Výsledek se ořízne na [15 %, 50 %].
  - Ručně zadaná MoS pro ticker má přednost; rozpad pak uvede „override“.
  - Všechny konstanty jsou v nastavení.
- **Rank skóre.** Kombinace upside k nákupní ceně a quality score; váha kvality je v nastavení. Filtr kvality je volitelný a uplatňuje se v presenteru, ne ve výpočtu.
- **Valuátor** řídí celý výpočet:
  - sestaví konfiguraci z nastavení; hodnotu pro ticker použije, jen když je skutečně nastavená;
  - spustí modely z registru a spočítá kompozit, quality a MoS;
  - z toho určí nákupní cenu, signál a rank skóre.
  - Výsledek obsahuje měnu, rozpětí, quality score, použitou MoS a její rozpad.

### Persistence a UI

- **Persistence.**
  - Tabulka ocenění a snapshoty journalu dostanou sloupce quality score, použitá MoS, dolní a horní mez férové hodnoty a měna.
  - Migrace přidá sloupce při startu; existující data zůstanou zachována.
  - Nastavení terminálního růstu a délky projekce pro ticker má výchozí hodnotu „nenastaveno“.
- **Presenter.** Veškerá logika UI je v presenteru jako čisté funkce: řádky tabulky, formátování měn, barvy, filtry, data grafů a DCF projekce pro detail. Streamlit stránky jen vykreslují.

### Backtest

- **Backtest (nový modul).**
  - Pro zvolené historické rozhodovací dny sestaví FinancialData jen z tehdy dostupných dat: výkazy zveřejněné alespoň 3 měsíce před datem.
  - Spočítá rank skóre a porovná ho s výnosem za 1 a 3 roky.
  - Metriky: rank IC (Spearman), výnos horního kvintilu vs. universum, hit rate signálů BUY.
  - Je deterministický (pevný seed) a výsledky ukládá do adresáře výzkumu.
- **AutoResearch.** Hill-climb zůstává. Cílová funkce se mění z MAPE vůči ceně na rank IC na validační sadě z backtestu.

### Architektonická rozhodnutí

- WACC je ručně zadaná požadovaná výnosnost, kterou lze pro ticker přepsat. CAPM ani beta se nepoužívají, kvůli transparentnosti a stabilitě.
- Všechny výpočty jsou čisté funkce bez I/O: modely, kompozit, quality, MoS, rank, FX převod a metriky backtestu. I/O je jen ve fetcheru, FMP klientovi, cache, watchlistu a journalu.
- Volání FMP mají timeout, retry s backoffem a fallback na yfinance. Selhání externího API nikdy neshodí obnovení dat.
- Reverse DCF je diagnostika, ne model kompozitu.
- Implementace po fázích; každá fáze je samostatně releasovatelná:
  - 0 opravy
  - 1 data a měny
  - 2 modely
  - 3 quality a MoS
  - 4 UI
  - 5 backtest

## Testing Decisions

### Co je dobrý test

- Ověřuje vnější chování (vstup → výstup) přes veřejné rozhraní modulu, ne jeho vnitřní kroky.
- Číselné modely se testují na ručně spočítaných příkladech (známý vstup → známá hodnota s tolerancí).
- Testují se i hraniční případy: chybějící data, záporné hodnoty, WACC ≤ g, oříznutí růstu.

### Co se testuje

Testují se všechny moduly kromě Streamlit stránek:

- **FMP klient** s mockovaným HTTP:
  - úspěch;
  - timeout + retry;
  - chybějící klíč;
  - nevalidní odpověď;
  - klíč se neobjeví v chybové hlášce.
- **Slučování zdrojů a FX převod.**
- **Každý oceňovací model** včetně reverse DCF. Reverse DCF se testuje tam a zpět: růst nalezený z ceny, která se rovná hodnotě z DCF, musí být původní růst.
- **Kompozit:** rozpětí a CV.
- **Quality:**
  - každá metrika;
  - F-score na ručně sestaveném příkladu;
  - vynechání metrik u finančních firem.
- **Margin of safety:** rozpad se sčítá na výslednou MoS, meze, override.
- **Valuátor:** globální defaulty u tickeru bez vlastního nastavení, propagace měny.
- **Persistence:** migrace na existující DB.
- **Presenter:** měny, barvy, filtr kvality, data pro CSV.
- **Backtest:**
  - žádný look-ahead: data po rozhodovacím dni se nepoužijí;
  - determinismus;
  - metriky na syntetických datech.

Streamlit stránky se ověřují ručně a end-to-end smoke testem. Ten běží na živých datech, mimo běžnou test suite.

### Prior art

- Existující testy modelů: fixture FinancialData, čisté funkce.
- Testy fetcheru s mockovaným yfinance.
- Testy watchlistu a journalu nad dočasnou SQLite.
- Testy AutoResearch harnessu.

## Out of Scope

- CAPM a výpočet WACC z bety a struktury kapitálu.
- Screener nad celým trhem: aplikace dál pracuje jen s explicitně přidanými tickery. Universe pro backtest je výjimka pro výzkum.
  - Screener je odložený jako fáze 6, viz [SCREENER.md](SCREENER.md).
  - Implementace v2 ale musí dodržet pravidla škálovatelnosti z jeho sekce 2, aby šel screener přidat bez přepisování.
- Monte Carlo simulace a scénáře bear/base/bull nad rámec rozpětí modelů.
- Beneish M-score, Altman Z-score, insider ownership.
- Automatické nákupy, napojení na brokera, alerting, sledování portfolia, víc uživatelů.
- Placené datové zdroje kromě FMP.

## Further Notes

- **Pokrytí FMP free tier (~250 požadavků/den)** nemusí stačit na CZ/EU tickery ani na 10 let historie. Ověří se jako první krok fáze 1. Pokud nestačí:
  - EU tickery poběží na yfinance (~4–5 let historie);
  - modely, které potřebují delší historii, vrátí N/A s varováním.
- **Historické výkazy pro backtest** (tak, jak byly tehdy zveřejněné) mohou být ve FMP za paywallem. V takovém případě se backtest omezí na US universe a dostupné roky.
- **Výchozí konstanty jsou odhady**, které se mají zkalibrovat backtestem: konstanty MoS, strop růstu a váha kvality v rank skóre.
- **Rizika backtestu** se dokumentují u AutoResearch:
  - survivorship bias (universe tvoří dnešní large caps);
  - look-ahead bias;
  - malý vzorek.
- **Existující issues #12–#16** (UI a smoke test) se rozšíří o prvky v2; duplicitní issues nevzniknou.
