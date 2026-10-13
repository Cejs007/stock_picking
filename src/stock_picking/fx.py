from stock_picking.data.models import FinancialData


def needs_conversion(fin: FinancialData) -> bool:
    return fin.financial_currency is not None and fin.financial_currency != fin.currency


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
