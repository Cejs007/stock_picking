import statistics

from stock_picking.data.models import FinancialData, ModelConfig


def calculate(data: FinancialData, config: ModelConfig) -> tuple[float | None, list[str]]:
    if data.ebitda is None or data.ebitda <= 0:
        return None, ["EBITDA must be positive for EV/EBITDA Relative model"]
    if data.shares_outstanding is None or data.shares_outstanding <= 0:
        return None, ["shares_outstanding must be positive for EV/EBITDA Relative model"]
    if len(data.ev_ebitda_history) < config.min_history_years:
        return None, [
            f"EV/EBITDA history requires at least {config.min_history_years} years"
            f" (got {len(data.ev_ebitda_history)})"
        ]
    fair_ev = statistics.median(data.ev_ebitda_history) * data.ebitda
    fair_equity = fair_ev - data.total_debt + data.cash
    return fair_equity / data.shares_outstanding, []
