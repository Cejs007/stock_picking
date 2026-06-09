import yfinance as yf

from stock_picking.data.models import FinancialData


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
