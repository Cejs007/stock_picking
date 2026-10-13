# Spike #22: pokrytí FMP free tieru

**Datum:** 2026-10-13
**Issue:** #22 (parent #17), navazují #23 (FMP klient) a #36 (backtest)
**Stav:** průzkum hotový, **rozhodnutí uživatele chybí** (viz poslední sekce).

## Shrnutí

- **Free tier (Basic, 0 $) je pro tento projekt skoro bezcenný.** Výkazy, key-metrics, ratios, enterprise values i dividendy jsou na free tieru omezené na **vzorek 87 symbolů** („AAPL, TSLA, AMZN and 84 more“) a na **max. 5 záznamů na jeden požadavek**, tedy 5 ročních období.
- **EU a CZ tickery (ASML.AS, CEZ.PR) jdou jen v nejdražším plánu Ultimate** („Global Coverage“). Starter pokrývá jen US burzy, Premium US, UK a Kanadu.
- **10 let historie** dává až Premium (30+ let). Free a Starter mají 5 let.
- **Filing date existuje**, ale jen pro firmy, které podávají výkazy SEC. U mezinárodních symbolů je `filingDate` podle FAQ FMP **nahrazený datem konce období**. Pro point-in-time backtest je to past, protože by vypadal korektně a přitom by měl look-ahead.
- **Hromadné (bulk) endpointy a screener na free tieru nejsou.** Bulk je jen v Ultimate, screener od Starteru (jen US).
- yfinance pro srovnání dává 4–5 ročních období pro všech 5 testovaných symbolů, včetně CEZ.PR a ASML.AS, a celou historii dividend.

## Metoda

| | Stav |
|---|---|
| Živé volání FMP s klíčem uživatele | **neproběhlo.** V `Settings` není nastavený `fmp_api_key`: hlavní checkout nemá `.env` a proměnná `FMP_API_KEY` není nastavená v procesu, uživatelském ani systémovém prostředí. |
| Živé volání FMP s veřejným klíčem `demo` | 1 požadavek (`/stable/income-statement?symbol=AAPL&period=annual&limit=10&apikey=***`), odpověď **HTTP 401 „Invalid API KEY“**. Demo klíč na `stable` API nefunguje. |
| Dokumentace FMP | Stažená a rozparsovaná srovnávací tabulka plánů z [pricing](https://site.financialmodelingprep.com/developer/docs/pricing), metadata endpointů z `developer/docs/stable/*` (parametry, `maxLimit`, měna), [FAQ](https://site.financialmodelingprep.com/faqs) a [návod k income statement](https://site.financialmodelingprep.com/how-to/fundamentals-at-your-fingertips-fmp-income-statement-api-essentials) (seznam polí). |
| yfinance (srovnání) | Živě, bez klíče: AAPL, MSFT, ASML, ASML.AS, CEZ.PR. Jen tvar dat (počet let, měny, počet dividend). |

Odpovědi o FMP níže jsou proto **z dokumentace, neověřené živě**, pokud není uvedeno jinak. Co ověřit živě je v sekci „Živé ověření“.

## Zápis tickerů ve FMP

| Firma | yfinance | FMP | Poznámka |
|---|---|---|---|
| Apple | `AAPL` | `AAPL` | |
| Microsoft | `MSFT` | `MSFT` | |
| ASML (NASDAQ) | `ASML` | `ASML` | Kotace v USD, výkazy v EUR (yfinance: `currency=USD`, `financialCurrency=EUR`). Typický případ pro #21. Podává 20-F u SEC. |
| ASML (Euronext Amsterdam) | `ASML.AS` | `ASML.AS` | FMP má pro `ASML.AS` vlastní stránku (DCF model), suffix `.AS` je tedy potvrzený z webu FMP. |
| ČEZ (Praha) | `CEZ.PR` | pravděpodobně `CEZ.PR` | Suffix `.PR` pro pražskou burzu uvádí [Wisesheets](https://www.wisesheets.io/available-exchanges), který stojí na datech FMP. **Neověřeno.** Ověřit jedním voláním `search-symbol?query=CEZ` (dostupné i na free tieru, „Full Global Coverage“). |

Zápis je stejný jako v yfinance (`<symbol>.<suffix burzy>`). Mapování mezi zdroji tedy pravděpodobně bude identita, ale mapovací funkce by měla existovat, kdyby se ukázala výjimka.

## Odpovědi na otázky

### 1. Vrací free tier roční výkazy a key-metrics pro AAPL, MSFT, ASML a CEZ.PR?

Endpointy (`stable` API, parametry `symbol`, `period` = `annual`/`quarter`/`FY`/`Q1`–`Q4`, `limit`, `maxLimit` 1000):

- `https://financialmodelingprep.com/stable/income-statement?symbol=AAPL&period=annual&limit=5&apikey=***`
- `https://financialmodelingprep.com/stable/balance-sheet-statement?symbol=AAPL&period=annual&limit=5&apikey=***`
- `https://financialmodelingprep.com/stable/cashflow-statement?symbol=AAPL&period=annual&limit=5&apikey=***`
- `https://financialmodelingprep.com/stable/key-metrics?symbol=AAPL&period=annual&limit=5&apikey=***`
- `https://financialmodelingprep.com/stable/ratios?symbol=AAPL&period=annual&limit=5&apikey=***`

Omezení free tieru podle srovnávací tabulky plánů:

| Endpoint | Basic (free) | Starter | Premium | Ultimate |
|---|---|---|---|---|
| Income / Balance / Cash flow | max. 5 záznamů; jen vzorek 87 symbolů | US burzy | US, UK, CA | globálně |
| Key Metrics | max. 5 záznamů; jen roční; vzorek 87 symbolů | jen roční; US | US, UK, CA | globálně |
| Financial Ratios | max. 5 záznamů; jen roční; vzorek 87 symbolů | jen roční; US | US, UK, CA | globálně |
| Enterprise Values | max. 5 záznamů; vzorek 87 symbolů | US | US, UK, CA | globálně |
| Statements TTM | — | — | — | globálně |
| As-reported výkazy | max. 5 záznamů; jen roční; vzorek 87 symbolů | plný přístup | plný přístup | plný přístup |
| Financial Reports Dates | plný přístup | plný přístup | plný přístup | plný přístup |

Odpověď po tickerech:

| Ticker | Free tier | Důvod |
|---|---|---|
| AAPL | **ano**, 5 let | AAPL je výslovně jmenovaný ve vzorku. |
| MSFT | **pravděpodobně ano**, neověřeno | Úplný seznam 87 symbolů FMP nezveřejňuje (stránka ukazuje jen první tři). MSFT tam nejspíš je, ale je potřeba to ověřit živě. |
| ASML (NASDAQ) | **nejisté** | Záleží, jestli je ve vzorku. Ve Starteru ano, protože jde o US burzu. |
| ASML.AS | **ne** | Euronext. Jen Ultimate. |
| CEZ.PR | **ne** | Pražská burza. Jen Ultimate. |

### 2. Kolik let historie je dostupných?

- **Free:** 5 ročních období („Maximum 5 Responses per API Call“ a „Historical Data Range 5 years“). FAQ: „you can access up to 5 years of annual statements for US companies“.
- **Starter:** 5 let. **Premium a Ultimate:** 30+ let.
- **10 let historie, se kterou počítá #23, tedy znamená minimálně Premium** (jen US, UK, CA) nebo Ultimate (EU, CZ).
- Neověřeno: co free tier vrátí na `limit=10`. Buď oseká na 5, nebo vrátí chybu. Klient s tím musí počítat.

Pro srovnání yfinance (živě, roční `income_stmt`):

| Ticker | Roky výkazů v yfinance | Měna kotace / výkazů | Dividend v historii |
|---|---|---|---|
| AAPL | FY2022–FY2025 (4) | USD / USD | 92 (od 1987) |
| MSFT | FY2023–FY2026 (4) | USD / USD | 91 (od 2003) |
| ASML | 2021–2025 (5) | USD / **EUR** | 37 (od 2007) |
| ASML.AS | 2021–2025 (5) | EUR / EUR | 36 (od 2007) |
| CEZ.PR | 2022–2025 (4) | CZK / CZK | 25 (od 2001) |

**Free FMP tedy proti yfinance přidává nanejvýš jeden rok historie, a to jen u symbolů ze vzorku.**

### 3. Jsou dostupné historické P/E, EV/EBITDA, ROIC a dividendy?

Ano, ale na free tieru jen pro vzorek, za 5 let a jen ročně.

> **Názvy polí v této sekci jsou zástupné (placeholder), ne ověřené.** Nejsou ve statické dokumentaci (viz níže). Platné budou až po živém ověření (bod 5 v sekci „Živé ověření“). #23 podle nich nesmí psát mapování.

- **P/E (historické):** `ratios`, pole `priceToEarningsRatio`. Počítá se z ceny ke konci fiskálního období.
- **EV/EBITDA:** `key-metrics`, pole `evToEBITDA`, nebo `ratios`, pole `enterpriseValueMultiple`. Samotné EV je v `enterprise-values`.
- **ROIC:** `key-metrics`, pole `returnOnInvestedCapital` a `investedCapital`.
- **Dividendy:**
  - roční dividenda na akcii je v `ratios` (`dividendPerShare`, `dividendPayoutRatio`);
  - jednotlivé výplaty jsou v `https://financialmodelingprep.com/stable/dividends?symbol=AAPL&apikey=***`, na free tieru ale **max. 5 záznamů**, což je u čtvrtletního plátce jen ~1,25 roku. yfinance dává celou historii.
- Názvy polí v `key-metrics` a `ratios` nejsou v dokumentaci staticky dostupné (ukázky se načítají až v prohlížeči). Výše uvedené názvy jsou tedy z paměti a **je nutné je ověřit živě** před psaním mapování v #23.
- Metadata dokumentace u výkazů, key-metrics i ratios uvádějí `"currency": "asReported"`. Hodnoty jsou tedy v **měně výkazu** (`reportedCurrency`), ne v měně kotace. U ASML (NASDAQ) to znamená EUR fundamenty proti USD ceně, což je přesně případ #21.

### 4. Mají výkazy data zveřejnění (filing date) pro point-in-time backtest?

- **Ano, pole existují.** Podle návodu FMP vrací `income-statement` (a stejně tak balance a cash flow) pole `date` (konec fiskálního období), `filingDate` („Date when the financial report was submitted“), `acceptedDate` („Timestamp when SEC officially received filing“), `fiscalYear`, `period` a `reportedCurrency`.
- **Ale jen pro SEC filery.** FAQ FMP doslova: *„The filing date field is sourced from the SEC. Since international stocks don't report to the SEC, this field isn't available for them and is instead mapped to the report date.“*
  - U AAPL a MSFT bude `filingDate` skutečné datum podání 10-K.
  - U ASML (NASDAQ) pravděpodobně datum 20-F. Ověřit.
  - U `ASML.AS`, `CEZ.PR` a jiných ne-SEC symbolů je `filingDate == date`. Backtest, který by mu věřil, by používal výkazy dřív, než byly zveřejněné.
- Endpoint `financial-reports-dates?symbol=…` je na free tieru „Full Access“. Podle názvu jde o seznam dostupných reportů (10-K), ne o data zveřejnění mezinárodních výkazů. Neověřeno.
- **Restatementy:** standardizované výkazy FMP nejsou zaručeně „tak, jak byly tehdy zveřejněné“. Endpointy `*-as-reported` jsou na free tieru jen roční, max. 5 záznamů a jen pro vzorek.
- **Důsledek pro #36:**
  - Pro US SEC filery jde 3měsíční pravidlo postavit nad `filingDate`/`acceptedDate`.
  - Pro ne-SEC symboly je nutné odvozené zpoždění od `date` (např. konec FY + N měsíců).
  - Na free tieru je ale hlavní překážka délka historie. S 5 ročními obdobími, 3měsíčním zpožděním a 3letým forward výnosem zbývá prakticky 1–2 rozhodovací roky. A každé z těch rozhodnutí má za sebou jen 1–2 roky výkazů, takže modely, které potřebují 3+ roky historie (P/E a EV/EBITDA relativní, CAGR v DCF), v něm budou N/A nebo s varováním.

### 5. Jaký je reálný denní limit a kolik požadavků potřebuje jeden ticker?

- **Limit free tieru:** 250 požadavků za den. Podle návodu FMP se resetuje po 24 hodinách, po vyčerpání vrací `429 Too Many Requests`. Navíc platí **bandwidth limit 500 MB za klouzavých 30 dní**.
- Placené plány se počítají za minutu: Starter 300/min, Premium 750/min, Ultimate 3000/min.
- „One request counts as one API call“, i když vrací víc období.
- Živě neověřeno.

Požadavky na plné ocenění jednoho tickeru (návrh pro #23):

| # | Endpoint | Co dává | Nutné? |
|---|---|---|---|
| 1 | `income-statement` | tržby, hrubý, provozní a čistý zisk, EPS, úroky, počet akcií, `filingDate` | ano |
| 2 | `balance-sheet-statement` | aktiva, závazky, krátkodobá aktiva a závazky, dluh, hotovost, vlastní kapitál | ano |
| 3 | `cashflow-statement` | provozní CF, capex, FCF, vyplacené dividendy | ano |
| 4 | `key-metrics` | EV, EV/EBITDA, ROIC, investovaný kapitál | ano |
| 5 | `ratios` | P/E, DPS, payout | ano |
| 6 | `dividends` | jednotlivé výplaty | volitelné (na free jen 5 záznamů, lépe z yfinance) |
| 7 | `profile` | měna, sektor, burza | volitelné (dává i yfinance). Dostupnost na free pro symboly mimo vzorek neověřená. |
| — | `search-symbol` | mapování tickeru | jednorázově na nový ticker, cachovat. Pokrytí na free („Full Global Coverage“) jen podle tabulky plánů, neověřeno. |

- **5 požadavků na ticker (7 s volitelnými).** Při studené cache to je 250 / 5 = 50 tickerů denně, se všemi volitelnými ~35.
- S TTL 30–90 dní pro roční výkazy (SCREENER.md §2, bod 3) je denní spotřeba u watchlistu 10–50 tickerů zanedbatelná. Ceny a kurzy jdou z yfinance.
- Pozor: požadavek na symbol mimo plán stojí požadavek také. Klient si **musí** odpověď „mimo plán“ uložit do cache (negativní cache), aby ji neopakoval každý refresh. Pro #23 je to požadavek, ne doporučení.
- **Sledování kvóty v #23 (SCREENER.md §2, bod 4):**
  - počítat požadavky proti 250/den a zároveň sledovat bandwidth 500 MB / 30 dní;
  - free plán má denní limit, placené plány limit za minutu. Počítadlo musí umět obojí, podle nastaveného plánu;
  - `429 Too Many Requests` znamená „kvóta vyčerpaná, přepnout na yfinance“, **ne** „zkusit znovu s backoffem“. Retry s backoffem patří jen k timeoutu a 5xx.
- **Pro screener (komentář v #22):** hromadné endpointy (`*-bulk`, `key-metrics-ttm-bulk`, `ratios-ttm-bulk`) jsou jen v Ultimate. Screener endpoint na free tieru není, Starter má jen US a Premium US, UK a CA. Předpoklad SCREENER.md, že free tier stačí díky hromadnému předfiltru, **neplatí**.

## Doporučení: co přes FMP a co jen přes yfinance

Za předpokladu, že zůstane **free tier**:

| Ticker / trh | Zdroj | Poznámka |
|---|---|---|
| AAPL | FMP (5 let) + yfinance fallback | Historické P/E, EV/EBITDA a ROIC hotové z FMP. |
| MSFT a další US large caps **ve vzorku 87** | FMP + yfinance fallback | Členství ve vzorku ověřit živě. Klient zjistí „mimo plán“ a přepne na yfinance. |
| US tickery mimo vzorek | jen yfinance | |
| ASML (NASDAQ) | FMP, pokud je ve vzorku, jinak yfinance | V obou případech nutný FX převod EUR→USD (#21). |
| ASML.AS, EU burzy | jen yfinance | FMP jen v Ultimate. |
| CEZ.PR, pražská burza | jen yfinance | FMP jen v Ultimate. |
| Dividendy (všechny tickery) | yfinance | Na free tieru má FMP jen 5 výplat. |

Pro rozhodnutí, jak se plány liší pro tento projekt:

| Plán | Cena (měsíčně / při ročním placení) | Pokrytí výkazů | Historie | Co to znamená |
|---|---|---|---|---|
| Basic | 0 $ | vzorek 87 symbolů | 5 let | Skoro žádný přínos proti yfinance. |
| Starter | 29 $ / 19 $ | US burzy | 5 let | Celé US, ale pořád jen 5 let. Backtest nepomůže. |
| Premium | 69 $ / 49 $ | US, UK, CA | 30+ let | 10 let historie a backtest pro US. EU a CZ dál jen yfinance. |
| Ultimate | 139 $ / 99 $ | globálně | 30+ let | Vše včetně CEZ.PR a ASML.AS a bulk endpointů pro screener. Ne-SEC filing date pořád chybí. |

Ceny jsou z pricing stránky k datu spiku (personal use).

**Doporučení:** pokud se nic nekupuje, postavit #23 tak, že **yfinance je primární zdroj a FMP doplňuje** jen symboly, které plán pokrývá. To je obráceně, než předpokládá PRD v2 („FMP preferovaný zdroj“). Pokud má platit „10 let historie“ a backtest #36 s rozumným vzorkem, je minimum Premium (US). Pro EU a CZ je to Ultimate.

## Živé ověření (až bude k dispozici klíč)

Do 15 požadavků. Tisknout jen tvar (počet řádků, roky, názvy polí, 1 řádek), URL vždy s `apikey=***`.

1. `search-symbol?query=CEZ` a `search-symbol?query=ASML`: zápis symbolu a burzy.
2. `income-statement?symbol=AAPL&period=annual&limit=10`: kolik řádků se vrátí (5, nebo chyba?), přítomnost a hodnoty `filingDate`/`acceptedDate`.
3. `income-statement` pro `MSFT` a `ASML`: jsou ve vzorku? U ASML porovnat `filingDate` a `date`.
4. `income-statement?symbol=CEZ.PR`: přesné znění chyby a HTTP kód pro symbol mimo plán (pro negativní cache v #23).
5. `key-metrics` a `ratios` pro AAPL: skutečné názvy polí pro P/E, EV/EBITDA, ROIC, DPS a `reportedCurrency`.
   - Pokud je ASML ve vzorku, také `key-metrics?symbol=ASML`: jsou `enterpriseValue` a `marketCap` v měně výkazu (EUR), nebo v měně kotace (USD)? Na tom závisí, které hodnoty převádí FX (#21).
6. `dividends?symbol=AAPL`: kolik záznamů a v jaké struktuře.
7. Po běhu zkontrolovat v dashboardu FMP spotřebu požadavků a bandwidth.

## Rozhodnutí uživatele

> **TODO (uživatel):** nic z toho zatím není rozhodnuté. Issues #23, #36 ani PRD tento spike neměnil.

1. **Plán FMP:** zůstat na free, nebo koupit Starter, Premium nebo Ultimate? Na tom závisí všechny další body.
2. **#23: priorita zdrojů.**
   - Platí dál „FMP má přednost, yfinance doplní“?
   - Nebo na free tieru obráceně: yfinance primárně a FMP jen pro pokryté symboly?
3. **#23: délka historie.** Změnit „až 10 let ročních řad“ na „až 5 let“ (free a Starter), nebo ponechat 10 a podmínit to plánem Premium a výš?
4. **#23: historické P/E a EV/EBITDA pro tickery mimo FMP** (CEZ.PR, ASML.AS, US mimo vzorek):
   - Smířit se s N/A u P/E relativního a EV/EBITDA relativního?
   - Nebo rozšířit #23 o výpočet historických násobků z yfinance (výkazy plus cena ke konci FY, 4–5 let)?
5. **#23: akceptační kritérium „AAPL a MSFT mají nenulové P/E FV a EV/EBITDA FV“** platí jen tehdy, je-li MSFT ve vzorku free tieru. Ponechat, nebo upravit?
6. **#23: který ASML je v watchlistu,** `ASML` (USD kotace, EUR výkazy, SEC filing date), nebo `ASML.AS`?
7. **#36: rozsah backtestu.** Universe a roky:
   - free nebo Starter: 5 let, tedy 1–2 rozhodovací roky pro 3letý horizont; zkrátit na 1letý horizont?
   - Premium: US universe, 10+ let;
   - Ultimate: včetně EU a CZ.
8. **#36: zpoždění pro ne-SEC výkazy.** U nich je `filingDate == date`. Jaké pevné zpoždění od konce FY použít (např. 4 nebo 6 měsíců místo 3), nebo je z backtestu vyřadit?
9. **SCREENER.md a PRD:**
   - Promítnout do tabulky datového rozpočtu v SCREENER.md a do „Further Notes“ v PRD, že bulk a screener endpointy free tier nemá (komentář v #22)?
   - Udělat to v tomto PR, nebo zvlášť?
