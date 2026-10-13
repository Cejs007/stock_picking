from stock_picking.data.models import FinancialData, ModelConfig

# Number of most recent years averaged into the DCF base FCF.
BASE_YEARS = 3


def growth_path(initial: float, terminal: float, years: int) -> list[float]:
    """Yearly growth fading linearly from `initial` (year 1) to `terminal` (last year)."""
    if years == 1:
        return [terminal]
    step = (terminal - initial) / (years - 1)
    return [initial + step * t for t in range(years)]


def calculate(data: FinancialData, config: ModelConfig) -> tuple[float | None, list[str]]:
    if not data.fcf_history:
        return None, ["FCF history is required for DCF"]
    recent = data.fcf_history[-BASE_YEARS:]
    fcf_base = sum(recent) / len(recent)
    if fcf_base <= 0:
        return None, [
            f"Average FCF of the last {len(recent)} year(s) is non-positive; "
            "DCF cannot be calculated"
        ]
    if data.shares_outstanding is None or data.shares_outstanding <= 0:
        return None, ["shares_outstanding must be positive for DCF"]
    if config.wacc <= config.terminal_growth_rate:
        return None, [
            f"WACC ({config.wacc:.1%}) must exceed terminal growth "
            f"({config.terminal_growth_rate:.1%}) for DCF"
        ]

    warnings: list[str] = []
    if len(recent) < BASE_YEARS:
        warnings.append(
            f"Only {len(recent)} year(s) of FCF history; DCF base is their average "
            f"instead of {BASE_YEARS} years"
        )
    g, growth_warnings = _initial_growth(data, config)
    warnings.extend(growth_warnings)

    # Two-stage DCF: growth fades linearly to terminal g, then Gordon terminal value.
    # Totals throughout; equity value = EV - net debt, then per share.
    wacc = config.wacc
    t_g = config.terminal_growth_rate
    n_years = config.projection_years
    fcf = fcf_base
    pv_fcf = 0.0
    for t, growth in enumerate(growth_path(g, t_g, n_years), start=1):
        fcf *= 1 + growth
        pv_fcf += fcf / (1 + wacc) ** t
    terminal_value = fcf * (1 + t_g) / (wacc - t_g)
    enterprise_value = pv_fcf + terminal_value / (1 + wacc) ** n_years

    equity_value = enterprise_value - (data.total_debt - data.cash)
    if equity_value <= 0:
        return None, [*warnings, "Equity value is non-positive after net debt; DCF N/A"]
    return equity_value / data.shares_outstanding, warnings


def _initial_growth(data: FinancialData, config: ModelConfig) -> tuple[float, list[str]]:
    """Explicit override as-is, else FCF CAGR clamped to the configured bounds."""
    if config.growth_rate_override is not None:
        return config.growth_rate_override, []
    first, last = data.fcf_history[0], data.fcf_history[-1]
    n = len(data.fcf_history)
    g = (last / first) ** (1 / (n - 1)) - 1 if n >= 2 and first > 0 and last > 0 else 0.0
    clamped = min(max(g, config.auto_growth_min), config.auto_growth_max)
    if clamped != g:
        return clamped, [f"Auto-derived FCF growth {g:.1%} clamped to {clamped:.1%} for DCF"]
    return g, []
