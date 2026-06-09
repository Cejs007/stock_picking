from pydantic import BaseModel, Field


class FinancialData(BaseModel):
    ticker: str
    company_name: str | None = None
    currency: str = "USD"
    current_price: float
    eps_ttm: float | None = None
    bvps: float | None = None
    # Total FCF per year, oldest first (e.g. 5+ years). Used for DCF CAGR derivation.
    fcf_history: list[float] = Field(default_factory=list)
    ebitda: float | None = None
    ev: float | None = None
    total_debt: float = 0.0
    cash: float = 0.0
    shares_outstanding: float | None = None
    # Trailing P/E ratios per year, oldest first.
    pe_history: list[float] = Field(default_factory=list)
    # EV/EBITDA ratios per year, oldest first.
    ev_ebitda_history: list[float] = Field(default_factory=list)


class ModelConfig(BaseModel):
    wacc: float = 0.10
    terminal_growth_rate: float = 0.03
    projection_years: int = 10
    # When None the DCF model auto-derives growth from FCF CAGR.
    growth_rate_override: float | None = None
    # Minimum years of history required for P/E and EV/EBITDA relative models.
    min_history_years: int = 3
