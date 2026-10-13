import json
from pathlib import Path

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from stock_picking.models.registry import MODEL_REGISTRY

# Weight keys: the registered models that enter the composite.
MODEL_NAMES = tuple(name for name, model in MODEL_REGISTRY.items() if model.in_composite)


def _w(graham: float, pe: float, ev: float, dcf: float) -> dict[str, float]:
    # Any other registered composite model gets weight 0 until a prior is set.
    weights = dict.fromkeys(MODEL_NAMES, 0.0)
    weights.update({"graham": graham, "pe_relative": pe, "ev_ebitda": ev, "dcf": dcf})
    return weights


# --------------------------------------------------------------------------- #
# Per-sector ensemble templates.
#
# These are THEORY-BASED PRIORS, not empirically tuned numbers. They encode
# which models are structurally meaningful for each sector:
#   * Graham Number leans on book value -> useful for asset-heavy / financial
#     names, near-useless for capital-light tech (tiny BVPS -> outlier).
#   * EV/EBITDA needs a real EBITDA -> meaningless for banks/insurers.
#   * DCF rewards durable free cash flow -> strong for stable cash compounders,
#     noisy for deep cyclicals at the wrong point in the cycle.
#   * P/E relative tracks the stock's own historical multiple -> broadly useful.
#
# Run `python -m stock_picking.research.autoresearch` to REPLACE these with
# weights tuned on a held-out validation split (see docs/AUTORESEARCH.md).
# Sector keys are the strings yfinance returns in info["sector"].
# --------------------------------------------------------------------------- #
DEFAULT_SECTOR_WEIGHTS: dict[str, dict[str, float]] = {
    "Technology":             _w(0.0, 1.0, 1.0, 1.5),
    "Communication Services": _w(0.0, 1.0, 1.0, 1.0),
    "Healthcare":             _w(0.5, 1.0, 1.0, 1.0),
    "Financial Services":     _w(1.0, 1.5, 0.0, 0.0),
    "Energy":                 _w(0.5, 0.5, 1.5, 0.5),
    "Basic Materials":        _w(0.5, 0.5, 1.5, 0.5),
    "Industrials":            _w(0.5, 1.0, 1.0, 1.0),
    "Consumer Cyclical":      _w(0.5, 1.0, 1.0, 1.0),
    "Consumer Defensive":     _w(0.5, 1.0, 1.0, 1.5),
    "Utilities":              _w(0.5, 1.0, 1.0, 1.5),
    "Real Estate":            _w(1.0, 1.0, 1.0, 0.5),
}


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    default_wacc: float = 0.10
    default_mos: float = 0.25
    default_terminal_g: float = 0.03
    default_projection_years: int = 10
    cache_ttl_hours: float = 24.0
    fmp_api_key: str | None = None

    # Fallback weights used when a ticker has no sector, or its sector is not in
    # `sector_weights`. Kept from the original AutoResearch (June 2026) run on
    # the AAPL/MSFT/CEZ.PR benchmark: Graham disabled, P/E relative upweighted.
    model_weights: dict[str, float] = Field(
        default_factory=lambda: _w(0.0, 1.5, 1.0, 1.0)
    )

    # Per-sector ensemble templates. Overridden wholesale if `tuned_weights_path`
    # points at a JSON file produced by the AutoResearch harness.
    sector_weights: dict[str, dict[str, float]] = Field(
        default_factory=lambda: {k: dict(v) for k, v in DEFAULT_SECTOR_WEIGHTS.items()}
    )

    # Optional path to AutoResearch output (JSON: {"sector_weights": {...},
    # "default_weights": {...}}). When set and present, replaces the priors above.
    tuned_weights_path: str | None = None

    @model_validator(mode="after")
    def _load_tuned_weights(self) -> "Settings":
        if not self.tuned_weights_path:
            return self
        path = Path(self.tuned_weights_path)
        if not path.is_file():
            return self
        payload = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(payload.get("sector_weights"), dict):
            self.sector_weights = payload["sector_weights"]
        if isinstance(payload.get("default_weights"), dict):
            self.model_weights = payload["default_weights"]
        return self

    def weights_for(self, sector: str | None) -> dict[str, float]:
        """Ensemble weights for a sector, falling back to `model_weights`."""
        if sector and sector in self.sector_weights:
            return self.sector_weights[sector]
        return self.model_weights
