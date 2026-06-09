import logging
from concurrent.futures import ThreadPoolExecutor, as_completed

import yfinance as yf

from stock_picking.data.cache import Cache
from stock_picking.data.models import FinancialData

logger = logging.getLogger(__name__)


class FetchError(Exception):
    pass


def fetch(ticker: str) -> FinancialData:
    t = yf.Ticker(ticker)
    info = t.info

    price = info.get("currentPrice") or info.get("regularMarketPrice")
    if not price:
        raise FetchError(f"No price available for {ticker!r}")

    return FinancialData(
        ticker=ticker,
        company_name=info.get("longName"),
        currency=info.get("currency", "USD"),
        current_price=float(price),
        eps_ttm=_optional_float(info.get("trailingEps")),
        bvps=_optional_float(info.get("bookValue")),
        shares_outstanding=_optional_float(info.get("sharesOutstanding")),
        ebitda=_optional_float(info.get("ebitda")),
        ev=_optional_float(info.get("enterpriseValue")),
        total_debt=float(info.get("totalDebt") or 0.0),
        cash=float(info.get("totalCash") or 0.0),
        fcf_history=_fcf_history(t),
    )


def fetch_all(
    tickers: list[str],
    cache: Cache,
    force_refresh: bool = False,
    status_callback: object = None,
) -> dict[str, FinancialData]:
    results: dict[str, FinancialData] = {}
    total = len(tickers)
    done = 0

    def _fetch_one(ticker: str) -> tuple[str, FinancialData | None]:
        if not force_refresh:
            cached = cache.get(ticker, "financials")
            if cached is not None:
                return ticker, FinancialData.model_validate(cached)
        try:
            fin = fetch(ticker)
        except FetchError as exc:
            logger.warning("fetch_all: skipping %s — %s", ticker, exc)
            return ticker, None
        cache.set(ticker, "financials", fin.model_dump())
        return ticker, fin

    with ThreadPoolExecutor() as executor:
        futures = {executor.submit(_fetch_one, t): t for t in tickers}
        for future in as_completed(futures):
            ticker, fin = future.result()
            if fin is not None:
                results[ticker] = fin
            done += 1
            if callable(status_callback):
                status_callback(done, total)

    return results


def _optional_float(value: object) -> float | None:
    return float(value) if value is not None else None


def _fcf_history(ticker: yf.Ticker) -> list[float]:
    cf = ticker.cashflow
    if cf is None or cf.empty:
        return []

    if "Free Cash Flow" in cf.index:
        series = cf.loc["Free Cash Flow"]
    elif "Operating Cash Flow" in cf.index and "Capital Expenditure" in cf.index:
        series = cf.loc["Operating Cash Flow"] + cf.loc["Capital Expenditure"]
    else:
        return []

    series = series.dropna().iloc[:5]
    return [float(v) for v in series.iloc[::-1]]
