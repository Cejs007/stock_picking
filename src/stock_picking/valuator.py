from stock_picking.data.models import FinancialData, ModelConfig
from stock_picking.fx import needs_conversion
from stock_picking.models import dcf, ev_ebitda, graham, pe_relative
from stock_picking.models.composite import calculate_composite
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

    if needs_conversion(fin):
        # Statement totals are still in another currency than the price, so any
        # fair value would compare mixed currencies. Don't value or rank it.
        return ValuationResult(
            ticker=fin.ticker,
            current_price=fin.current_price,
            currency=fin.currency,
            signal="N/A",
            warnings=[
                f"Fundamentals are in {fin.financial_currency} but the price is in"
                f" {fin.currency}; FX rate unavailable, values not converted"
            ],
        )

    results = {
        "graham": graham.calculate(fin, cfg),
        "pe_relative": pe_relative.calculate(fin, cfg),
        "ev_ebitda": ev_ebitda.calculate(fin, cfg),
        "dcf": dcf.calculate(fin, cfg),
    }

    weights = settings.weights_for(fin.sector)
    composite, _active, all_warnings = calculate_composite(results, weights)

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
        fair_value_graham=results["graham"][0],
        fair_value_pe=results["pe_relative"][0],
        fair_value_ev_ebitda=results["ev_ebitda"][0],
        fair_value_dcf=results["dcf"][0],
        fair_value_composite=composite,
        current_price=fin.current_price,
        currency=fin.currency,
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
    terminal_g = overrides.dcf_terminal_g if overrides else settings.default_terminal_g
    proj_years = overrides.dcf_years if overrides else settings.default_projection_years
    growth_override = overrides.dcf_growth_override if overrides else None

    return ModelConfig(
        wacc=wacc,
        terminal_growth_rate=terminal_g,
        projection_years=proj_years,
        growth_rate_override=growth_override,
    )
