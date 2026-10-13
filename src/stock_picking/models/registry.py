from collections.abc import Callable
from dataclasses import dataclass

from stock_picking.data.models import FinancialData, ModelConfig
from stock_picking.models import dcf, ev_ebitda, graham, pe_relative

ModelFn = Callable[[FinancialData, ModelConfig], tuple[float | None, list[str]]]


@dataclass(frozen=True)
class RegisteredModel:
    calculate: ModelFn
    label: str
    in_composite: bool = True


# Single source of truth for which valuation models exist. Order sets the
# dashboard column order. Adding a model = write `calculate` + one entry here.
MODEL_REGISTRY: dict[str, RegisteredModel] = {
    "graham": RegisteredModel(graham.calculate, "Graham"),
    "pe_relative": RegisteredModel(pe_relative.calculate, "P/E"),
    "ev_ebitda": RegisteredModel(ev_ebitda.calculate, "EV/EBITDA"),
    "dcf": RegisteredModel(dcf.calculate, "DCF"),
}
