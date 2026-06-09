from stock_picking.data.models import FinancialData, ModelConfig


def calculate(data: FinancialData, config: ModelConfig) -> tuple[float | None, list[str]]:
    if not data.fcf_history:
        return None, ["FCF history is required for DCF"]
    if all(v <= 0 for v in data.fcf_history):
        return None, ["All FCF values are non-positive; DCF cannot be calculated"]
    if data.shares_outstanding is None or data.shares_outstanding <= 0:
        return None, ["shares_outstanding must be positive for DCF"]

    if config.growth_rate_override is not None:
        g = config.growth_rate_override
    else:
        first, last = data.fcf_history[0], data.fcf_history[-1]
        n = len(data.fcf_history)
        if n >= 2 and first > 0 and last > 0:
            g = (last / first) ** (1 / (n - 1)) - 1
        else:
            g = 0.0

    fcf_base = data.fcf_history[-1] / data.shares_outstanding
    wacc = config.wacc
    t_g = config.terminal_growth_rate
    n_years = config.projection_years

    pv_fcf = sum(
        fcf_base * (1 + g) ** t / (1 + wacc) ** t for t in range(1, n_years + 1)
    )
    fcf_terminal = fcf_base * (1 + g) ** n_years
    terminal_value = fcf_terminal * (1 + t_g) / (wacc - t_g)
    pv_terminal = terminal_value / (1 + wacc) ** n_years

    return pv_fcf + pv_terminal, []
