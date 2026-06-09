import pytest

from stock_picking.data.models import FinancialData, ModelConfig


@pytest.fixture
def fin() -> FinancialData:
    """
    Synthetic data designed so every model produces a deterministic, hand-checkable result.

    Graham:
        sqrt(22.5 * 5.0 * 40.0) = sqrt(4500) ≈ 67.08

    P/E relative (median of [15, 16, 17, 18, 19] = 17):
        17 * 5.0 = 85.0

    EV/EBITDA relative (median of [8, 9, 10, 11, 12] = 10):
        fair_ev = 10 * 20 = 200
        fair_equity = 200 - 30 + 10 = 180
        fair_price = 180 / 10 = 18.0

    DCF (auto CAGR from fcf_history, WACC 10%, terminal 3%, 10 years):
        FCF per share (latest) = 100 / 10 = 10.0
        growth ≈ 5.74%  (CAGR of [80, 85, 90, 95, 100])
    """
    return FinancialData(
        ticker="TEST",
        company_name="Test Corp",
        currency="USD",
        current_price=100.0,
        eps_ttm=5.0,
        bvps=40.0,
        fcf_history=[80.0, 85.0, 90.0, 95.0, 100.0],
        ebitda=20.0,
        ev=200.0,
        total_debt=30.0,
        cash=10.0,
        shares_outstanding=10.0,
        pe_history=[15.0, 16.0, 17.0, 18.0, 19.0],
        ev_ebitda_history=[8.0, 9.0, 10.0, 11.0, 12.0],
    )


@pytest.fixture
def cfg() -> ModelConfig:
    return ModelConfig()
