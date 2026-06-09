from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    default_wacc: float = 0.10
    default_mos: float = 0.25
    default_terminal_g: float = 0.03
    default_projection_years: int = 10
    cache_ttl_hours: float = 24.0
    fmp_api_key: str | None = None
    model_weights: dict[str, float] = Field(
        default_factory=lambda: {
            "graham": 1.0,
            "pe_relative": 1.0,
            "ev_ebitda": 1.0,
            "dcf": 1.0,
        }
    )
