from stock_picking.watchlist import ValuationResult

_CURRENCY_SYMBOLS: dict[str, str] = {
    "USD": "$",
    "EUR": "€",
    "GBP": "£",
    "JPY": "¥",
}


def format_currency(value: float | None, currency: str | None = "USD") -> str:
    if value is None:
        return "N/A"
    if currency is None:
        return f"{value:.2f}"
    symbol = _CURRENCY_SYMBOLS.get(currency, f"{currency} ")
    return f"{symbol}{value:.2f}"


def build_dashboard_rows(results: list[ValuationResult]) -> list[dict]:
    sorted_results = sorted(
        results,
        key=lambda r: (r.master_score is None, -(r.master_score or 0)),
    )
    rows = []
    for r in sorted_results:
        currency = r.currency
        rows.append({
            "Ticker": r.ticker,
            "Price": format_currency(r.current_price, currency),
            "Fair Value": format_currency(r.fair_value_composite, currency),
            "Upside": format_percent(r.master_score),
            "Buy Target": format_currency(r.buy_target, currency),
            "Signal": r.signal,
            "Graham": format_currency(r.fair_value_graham, currency),
            "P/E": format_currency(r.fair_value_pe, currency),
            "EV/EBITDA": format_currency(r.fair_value_ev_ebitda, currency),
            "DCF": format_currency(r.fair_value_dcf, currency),
            "Warnings": " | ".join(r.warnings),
        })
    return rows


def format_percent(value: float | None) -> str:
    if value is None:
        return "N/A"
    sign = "+" if value >= 0 else ""
    return f"{sign}{value:.1f}%"
