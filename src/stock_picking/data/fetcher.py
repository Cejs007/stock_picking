import logging
import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed

import yfinance as yf
from pydantic import BaseModel, Field, ValidationError

from stock_picking.data.cache import Cache
from stock_picking.data.models import FinancialData
from stock_picking.fx import (
    convert_to_quote_currency,
    fx_pair,
    major_currency,
    needs_conversion,
    quote_rate,
)

logger = logging.getLogger(__name__)

FX_RATE_TTL_HOURS = 12.0
_FX_ATTEMPTS = 3
_FX_BACKOFF_S = 0.5


class _FxRate(BaseModel):
    rate: float = Field(gt=0, allow_inf_nan=False)


class FetchError(Exception):
    pass


def fetch(ticker: str) -> FinancialData:
    t = yf.Ticker(ticker)
    info = t.info

    price = info.get("currentPrice") or info.get("regularMarketPrice")
    if not price:
        raise FetchError(f"No price available for {ticker!r}")

    currency = info.get("currency", "USD")
    # Minor-unit listings (GBp, ZAc, ILA) are priced in pence/cents, but yfinance
    # reports per-share fields in the major unit (SHEL.L: price / 100 / trailingEps
    # == trailingPE), so bring them into the quote's unit.
    _, minor_per_major = major_currency(currency)

    return FinancialData(
        ticker=ticker,
        company_name=info.get("longName"),
        currency=currency,
        financial_currency=info.get("financialCurrency"),
        sector=info.get("sector"),
        current_price=float(price),
        eps_ttm=_scaled(_optional_float(info.get("trailingEps")), minor_per_major),
        bvps=_scaled(_optional_float(info.get("bookValue")), minor_per_major),
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
        fin = _cached_or_fetched(ticker)
        if fin is None:
            return ticker, None
        return ticker, _in_quote_currency(fin, cache, force_refresh)

    def _cached_or_fetched(ticker: str) -> FinancialData | None:
        if not force_refresh:
            cached = cache.get(ticker, "financials")
            if cached is not None:
                return FinancialData.model_validate(cached)
        try:
            fin = fetch(ticker)
        except FetchError as exc:
            logger.warning("fetch_all: skipping %s — %s", ticker, exc)
            return None
        cache.set(ticker, "financials", fin.model_dump())
        return fin

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


def _in_quote_currency(fin: FinancialData, cache: Cache, force_refresh: bool) -> FinancialData:
    # If no rate is available the data is returned unconverted; the valuator
    # sees the currency mismatch and warns.
    if not needs_conversion(fin) or fin.financial_currency is None:
        return fin
    pair = fx_pair(fin.financial_currency, fin.currency)
    major_rate = 1.0 if pair is None else _cached_fx_rate(*pair, cache, force_refresh)
    if major_rate is None:
        return fin
    rate = quote_rate(fin.financial_currency, fin.currency, major_rate)
    return convert_to_quote_currency(fin, rate)


def _cached_fx_rate(
    from_currency: str, to_currency: str, cache: Cache, force_refresh: bool
) -> float | None:
    key = f"{from_currency}{to_currency}=X"
    cached = None if force_refresh else cache.get(key, "fx_rate", ttl_hours=FX_RATE_TTL_HOURS)
    if cached is not None:
        return _FxRate.model_validate(cached).rate
    rate = fetch_fx_rate(from_currency, to_currency)
    if rate is not None:
        cache.set(key, "fx_rate", {"rate": rate})
    return rate


def fetch_fx_rate(
    from_currency: str,
    to_currency: str,
    _sleep: Callable[[float], None] = time.sleep,
) -> float | None:
    """Units of `to_currency` per 1 `from_currency`, or None if unavailable."""
    pair = f"{from_currency}{to_currency}=X"
    for attempt in range(_FX_ATTEMPTS):
        try:
            info = yf.Ticker(pair).info
            break
        # yfinance surfaces network failures as many unrelated exception types.
        except Exception as exc:
            logger.warning("fetch_fx_rate: %s attempt %d failed: %s", pair, attempt + 1, exc)
            if attempt + 1 < _FX_ATTEMPTS:
                _sleep(_FX_BACKOFF_S * 2**attempt)
    else:
        return None
    try:
        return _FxRate(rate=info.get("regularMarketPrice")).rate
    except ValidationError:
        logger.warning("fetch_fx_rate: no valid rate for %s", pair)
        return None


def _optional_float(value: object) -> float | None:
    return float(value) if value is not None else None


def _scaled(value: float | None, factor: float) -> float | None:
    return value * factor if value is not None else None


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
