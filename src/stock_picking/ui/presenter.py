from stock_picking.models.registry import MODEL_REGISTRY
from stock_picking.watchlist import ValuationResult

_CURRENCY_SYMBOLS: dict[str, str] = {
    "USD": "$",
    "EUR": "€",
    "GBP": "£",
    "JPY": "¥",
}


def format_currency(value: float | None, currency: str = "USD") -> str:
    if value is None:
        return "N/A"
    symbol = _CURRENCY_SYMBOLS.get(currency, f"{currency} ")
    return f"{symbol}{value:.2f}"


def build_dashboard_rows(results: list[ValuationResult]) -> list[dict]:
    sorted_results = sorted(
        results,
        key=lambda r: (r.master_score is None, -(r.master_score or 0)),
    )
    rows = []
    for r in sorted_results:
        currency = "USD"
        row = {
            "Ticker": r.ticker,
            "Price": format_currency(r.current_price, currency),
            "Fair Value": format_currency(r.fair_value_composite, currency),
            "Upside": format_percent(r.master_score),
            "Buy Target": format_currency(r.buy_target, currency),
            "Signal": r.signal,
        }
        for name, model in MODEL_REGISTRY.items():
            row[model.label] = format_currency(r.fair_values.get(name), currency)
        rows.append(row)
    return rows


def format_percent(value: float | None) -> str:
    if value is None:
        return "N/A"
    sign = "+" if value >= 0 else ""
    return f"{sign}{value:.1f}%"
