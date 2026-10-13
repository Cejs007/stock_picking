import pytest

from stock_picking.data.cache import Cache
from stock_picking.data.fetcher import fetch, fetch_all, fetch_fx_rate

pytestmark = pytest.mark.live


@pytest.mark.parametrize(
    ("ticker", "quote_ccy", "statement_ccy"),
    [("AAPL", "USD", "USD"), ("MSFT", "USD", "USD"), ("CEZ.PR", "CZK", "CZK")],
)
def test_fetch_maps_quote_and_statement_currency(
    ticker: str, quote_ccy: str, statement_ccy: str
) -> None:
    fin = fetch(ticker)
    assert fin.currency == quote_ccy
    assert fin.financial_currency == statement_ccy
    assert fin.fcf_history


@pytest.mark.parametrize(
    ("from_ccy", "to_ccy", "low", "high"),
    # Sanity bands, deliberately wide: EURUSD ~1.1, CZKUSD ~0.045.
    [("EUR", "USD", 0.8, 1.6), ("CZK", "USD", 0.02, 0.1)],
)
def test_fetch_fx_rate_returns_plausible_rate(
    from_ccy: str, to_ccy: str, low: float, high: float
) -> None:
    rate = fetch_fx_rate(from_ccy, to_ccy)
    assert rate is not None
    assert low < rate < high


def test_adr_fundamentals_end_up_in_quote_currency() -> None:
    # ASML on NASDAQ: quoted in USD, reports in EUR.
    fin = fetch_all(["ASML"], Cache(db_path=":memory:"))["ASML"]
    assert fin.currency == "USD"
    assert fin.financial_currency == "USD"
