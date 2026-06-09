import math

from stock_picking.data.models import FinancialData, ModelConfig


def calculate(data: FinancialData, config: ModelConfig) -> tuple[float | None, list[str]]:
    if data.eps_ttm is None or data.eps_ttm <= 0:
        return None, ["EPS must be positive to calculate Graham Number"]
    if data.bvps is None or data.bvps <= 0:
        return None, ["BVPS must be positive to calculate Graham Number"]
    return math.sqrt(22.5 * data.eps_ttm * data.bvps), []
