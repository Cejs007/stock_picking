# Screener (fáze 6): návrh a pravidla škálovatelnosti

**Stav:** odloženo. Rozhodnuto 2026-10-13.

- **v2 (PRD #17, issues #12–#37)** zůstává omezená na **watchlist**: akcie, které uživatel přidá ručně. Aplikace je hodnotí a řadí, ale sama je nevyhledává.
- **Screener** (vyhledávání kandidátů nad širokým universem) přijde jako **fáze 6** až po dokončení v2, pokud ho budeme chtít.

Tento dokument má dva účely:
1. Popsat, jak screener postavit.
2. Hlavně stanovit, **co musí implementace v2 dodržet už teď**, aby se screener dal přidat bez přepisování.

---

## 1. Cílová podoba screeneru

Screener je dvoustupňová trychtýřovitá pipeline. Plné ocenění je drahé na data, proto se počítá jen pro malý zlomek universa.

```
Universe (~1 000–3 000 tickerů)
  │  Stupeň 1: levný předfiltr (TTM metriky, 1 požadavek na stovky tickerů)
  ▼
Kandidáti (~50–150)
  │  Stupeň 2: plné ocenění (stejný fetch + valuate + quality + MoS jako watchlist)
  ▼
Výsledky screeneru (seřazené podle rank skóre)
  │  ruční krok uživatele
  ▼
Watchlist
```

- **Universe.**
  - Seznam tickerů z indexů, např. S&P 500, STOXX 600 a pražská burza (PX).
  - Uloží se do tabulky `universe` (ticker, burza, měna, sektor, zdroj, datum aktualizace).
  - Seznam se obnovuje zřídka, typicky měsíčně.
- **Stupeň 1: předfiltr.**
  - Jednoduchá kritéria nad TTM daty: P/E nebo FCF yield, ROIC/ROE, čistý dluh / EBITDA, tržní kapitalizace a likvidita.
  - Zdrojem jsou hromadné endpointy (screener a bulk key-metrics endpointy FMP), ne požadavek na každý ticker zvlášť.
  - Kritéria jsou v `Settings` a jejich vyhodnocení je čistá funkce.
- **Stupeň 2: plné ocenění** běží nad kandidáty **přesně stejným kódem** jako watchlist: `fetch_all` → `valuate` (modely, kompozit, quality, MoS, rank).
- **Výsledky** se ukládají do vlastní tabulky (`screener_runs`, `screener_results`), ne do watchlistu.
- **UI** jen zobrazuje výsledky posledního běhu a nabízí tlačítko „Přidat do watchlistu“. Do watchlistu se nic nepřidává automaticky.
- **Běh** se spouští z příkazové řádky nebo na pozadí (`python -m stock_picking.screener run`), **nikdy synchronně ve Streamlitu**. Pokud se přeruší kvůli limitu API, dá se navázat.

### Datový rozpočet (orientačně, ověří spike #22)

| | Watchlist (v2) | Screener |
|---|---|---|
| Počet tickerů | 10–50 | 1 000–3 000 |
| Požadavky na plné ocenění | ~5–8 / ticker | jen kandidáti (~100) |
| Požadavky na předfiltr | — | jednotky až desítky (hromadně) |
| FMP free tier ~250 požadavků/den | stačí | stačí **jen** díky stupni 1, delší TTL a navazování běhu |

Pokud free tier nestačí ani takto, jsou dvě možnosti: placený FMP tier, nebo předfiltr z yfinance s pomalejším, postupným obnovováním. O tom se rozhodne při zahájení fáze 6.

---

## 2. Pravidla pro implementaci v2 (platí už teď)

Tato pravidla nepřidávají nové funkce, jen zakazují vazby, které by screener později zablokovaly. Každé má u sebe issue, kde se ho týká.

1. **Výpočetní jádro nezná watchlist.**
   - `valuate`, modely, kompozit, quality, MoS a rank pracují s `FinancialData`, `Settings` a volitelnými overrides.
   - Nikdy nečtou watchlist ani DB.
   - *(#24, #31, #33, #34)*
2. **Fetch pracuje se seznamem tickerů, ne s watchlistem.**
   - `fetch_all(tickers, …)` zůstává obecný.
   - Napojení na watchlist je jen ve volající vrstvě (UI).
   - *(#23)*
3. **Cache má TTL podle typu dat.**
   - Roční výkazy se mění jednou za čtvrtletí až rok (TTL 30–90 dní).
   - Ceny a kurzy se mění denně (TTL ~1 den).
   - Jedno globální TTL pro všechno by u velkého universa plýtvalo limitem API.
   - *(#23, #21)*
4. **FMP klient hlídá spotřebu.**
   - Počítá požadavky a respektuje denní limit.
   - Po dosažení limitu skončí řízeně: vrátí „nedostupné“ a použije se fallback. Nikdy nepadne a nezahlcuje API retry smyčkou.
   - Zdroj dat je zaznamenaný.
   - *(#23)*
5. **Ocenění není vázané na členství ve watchlistu.**
   - `ValuationResult` je samostatný záznam: ticker, čas, měna, metriky.
   - Do tabulky `valuations` nepřidávat cizí klíč na `watchlist`, aby šlo stejný výsledek uložit i do výsledků screeneru.
   - *(#26, #31, #33)*
6. **Dlouhé běhy patří mimo Streamlit.**
   - Logika obnovení dat (fetch → valuate → save) je funkce, kterou volá UI, ale jde ji zavolat i z příkazové řádky.
   - UI kolem ní jen zobrazuje průběh.
   - *(#20, #12)*
7. **Presenter neočekává malý počet řádků.**
   - Řazení a filtry (rank, filtr kvality) jsou čisté funkce nad seznamem výsledků.
   - Stejné funkce pak poslouží i výsledkům screeneru.
   - *(#34, #12)*

Když issue z v2 narazí na konflikt s těmito pravidly, má přednost jednodušší řešení pro watchlist. Konflikt se ale poznamená sem do sekce 4.

---

## 3. Předběžný rozpad fáze 6 (zatím bez issues)

1. **Universe:** načtení seznamu z indexů a tabulka `universe`.
2. **Předfiltr:** kritéria v nastavení, čistá funkce a hromadný fetch TTM metrik.
3. **Běh screeneru:** příkaz pro příkazovou řádku, navazování po přerušení, hlídání limitu API a tabulky výsledků.
4. **UI stránka Screener:** výsledky posledního běhu a akce „Přidat do watchlistu“.
5. **Backtest nad universem:** rozšířit #36 z watchlistu na universe. Zmenší to survivorship bias, pokud budou dostupné historické složení indexů.

Issues se vytvoří přes `to-issues` při zahájení fáze 6.

## 4. Otevřené body a známé konflikty

- Pokrytí EU a CZ tickerů v hromadných endpointech FMP: výsledek spiku #22.
- Zdroj historického složení indexů pro backtest bez survivorship bias, pravděpodobně placený.
- *(zatím žádné konflikty s pravidly v sekci 2)*
