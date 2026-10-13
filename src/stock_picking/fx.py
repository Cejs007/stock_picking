from stock_picking.data.models import FinancialData

# Minor-unit quote codes used by Yahoo -> (major currency, minor units per major).
_MINOR_UNITS: dict[str, tuple[str, float]] = {
    "GBp": ("GBP", 100.0),
    "GBX": ("GBP", 100.0),
    "ZAc": ("ZAR", 100.0),
    "ILA": ("ILS", 100.0),
}


def major_currency(code: str) -> tuple[str, float]:
    """(major currency, minor units per 1 major unit); a major code maps to (code, 1.0)."""
    return _MINOR_UNITS.get(code, (code, 1.0))


def fx_pair(from_currency: str, to_currency: str) -> tuple[str, str] | None:
    """Major-currency pair whose market rate is needed, or None if they differ only by unit."""
    from_major, _ = major_currency(from_currency)
    to_major, _ = major_currency(to_currency)
    return None if from_major == to_major else (from_major, to_major)


def quote_rate(from_currency: str, to_currency: str, major_rate: float = 1.0) -> float:
    """Units of `to_currency` per 1 `from_currency`, given the rate between their majors."""
    _, from_minor = major_currency(from_currency)
    _, to_minor = major_currency(to_currency)
    return major_rate * to_minor / from_minor


def needs_conversion(fin: FinancialData) -> bool:
    return fin.financial_currency is not None and fin.financial_currency != fin.currency


def unresolved_currency_reason(fin: FinancialData) -> str | None:
    """Why statement totals can't be compared with the price, or None if they can."""
    if fin.financial_currency is None:
        return (
            f"Statement currency unknown, so fundamentals may not be in {fin.currency};"
            " refresh to re-fetch"
        )
    if needs_conversion(fin):
        return (
            f"Fundamentals are in {fin.financial_currency} but the price is in"
            f" {fin.currency}; FX rate unavailable, values not converted"
        )
    return None


def convert_to_quote_currency(fin: FinancialData, rate: float) -> FinancialData:
    """Convert the statement-currency fields (FCF, EBITDA, EV, debt, cash) to quote currency.

    `rate` is quote-currency units per 1 unit of statement currency. EPS and
    BVPS are already in the quote currency; price, share count and multiples
    (P/E, EV/EBITDA) are currency-free. All of those are untouched.
    """
    if not needs_conversion(fin):
        return fin

    def _scale(value: float | None) -> float | None:
        return value * rate if value is not None else None

    return fin.model_copy(update={
        "financial_currency": fin.currency,
        "fcf_history": [v * rate for v in fin.fcf_history],
        "ebitda": _scale(fin.ebitda),
        "ev": _scale(fin.ev),
        "total_debt": fin.total_debt * rate,
        "cash": fin.cash * rate,
    })
