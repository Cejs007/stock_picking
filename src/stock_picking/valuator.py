from stock_picking.data.models import FinancialData, ModelConfig
from stock_picking.models.composite import calculate_composite
from stock_picking.models.registry import MODEL_REGISTRY
from stock_picking.settings import Settings
from stock_picking.watchlist import TickerOverrides, ValuationResult


def valuate(
    fin: FinancialData,
    settings: Settings,
    overrides: TickerOverrides | None = None,
) -> ValuationResult:
    cfg = _build_model_config(settings, overrides)
    mos = (
        overrides.mos_override
        if overrides and overrides.mos_override is not None
        else settings.default_mos
    )

    results = {name: model.calculate(fin, cfg) for name, model in MODEL_REGISTRY.items()}

    weights = settings.weights_for(fin.sector)
    composite_weights = {
        name: weights.get(name, 0.0)
        for name, model in MODEL_REGISTRY.items()
        if model.in_composite
    }
    composite, _active, all_warnings = calculate_composite(results, composite_weights)

    if composite is not None:
        master_score = (composite - fin.current_price) / fin.current_price * 100
        buy_target = composite * (1 - mos)
        signal = "BUY" if fin.current_price <= buy_target else "WAIT"
    else:
        master_score = None
        buy_target = None
        signal = "N/A"

    return ValuationResult(
        ticker=fin.ticker,
        fair_values={name: value for name, (value, _) in results.items()},
        fair_value_composite=composite,
        current_price=fin.current_price,
        master_score=master_score,
        buy_target=buy_target,
        signal=signal,
        warnings=all_warnings,
    )


def _build_model_config(settings: Settings, overrides: TickerOverrides | None) -> ModelConfig:
    wacc = (
        overrides.dcf_wacc_override
        if overrides and overrides.dcf_wacc_override is not None
        else settings.default_wacc
    )
    terminal_g = (
        overrides.dcf_terminal_g
        if overrides and overrides.dcf_terminal_g is not None
        else settings.default_terminal_g
    )
    proj_years = (
        overrides.dcf_years
        if overrides and overrides.dcf_years is not None
        else settings.default_projection_years
    )
    growth_override = overrides.dcf_growth_override if overrides else None

    return ModelConfig(
        wacc=wacc,
        terminal_growth_rate=terminal_g,
        projection_years=proj_years,
        growth_rate_override=growth_override,
    )
