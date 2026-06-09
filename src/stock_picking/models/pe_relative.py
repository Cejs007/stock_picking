import statistics

from stock_picking.data.models import FinancialData, ModelConfig


def calculate(data: FinancialData, config: ModelConfig) -> tuple[float | None, list[str]]:
    if data.eps_ttm is None or data.eps_ttm <= 0:
        return None, ["EPS must be positive for P/E Relative model"]
    if len(data.pe_history) < config.min_history_years:
        return None, [f"P/E history requires at least {config.min_history_years} years (got {len(data.pe_history)})"]
    return statistics.median(data.pe_history) * data.eps_ttm, []
