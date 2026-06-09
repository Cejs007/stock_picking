import time

import pytest

from stock_picking.data.cache import Cache


@pytest.fixture
def cache() -> Cache:
    return Cache(db_path=":memory:")


def test_get_returns_none_on_empty(cache: Cache) -> None:
    assert cache.get("AAPL", "financials") is None


def test_get_returns_data_after_set(cache: Cache) -> None:
    payload = {"price": 150.0, "eps": 6.0}
    cache.set("AAPL", "financials", payload)
    assert cache.get("AAPL", "financials") == payload


def test_expired_entry_returns_none() -> None:
    t = 1_000_000.0
    cache = Cache(db_path=":memory:", ttl_hours=24.0, _now=lambda: t)
    cache.set("AAPL", "financials", {"price": 150.0})
    # Advance clock past TTL
    cache._now = lambda: t + 24 * 3600 + 1
    assert cache.get("AAPL", "financials") is None


def test_set_overwrites_existing_entry(cache: Cache) -> None:
    cache.set("AAPL", "financials", {"price": 100.0})
    cache.set("AAPL", "financials", {"price": 200.0})
    assert cache.get("AAPL", "financials") == {"price": 200.0}


def test_invalidate_clears_all_data_types_for_ticker(cache: Cache) -> None:
    cache.set("AAPL", "financials", {"price": 150.0})
    cache.set("AAPL", "metadata", {"name": "Apple"})
    cache.invalidate("AAPL")
    assert cache.get("AAPL", "financials") is None
    assert cache.get("AAPL", "metadata") is None


def test_invalidate_does_not_affect_other_tickers(cache: Cache) -> None:
    cache.set("AAPL", "financials", {"price": 150.0})
    cache.set("MSFT", "financials", {"price": 400.0})
    cache.invalidate("AAPL")
    assert cache.get("MSFT", "financials") == {"price": 400.0}


def test_non_expired_entry_returns_data() -> None:
    t = 1_000_000.0
    cache = Cache(db_path=":memory:", ttl_hours=24.0, _now=lambda: t)
    payload = {"price": 150.0}
    cache.set("AAPL", "financials", payload)
    # Advance clock to just before TTL boundary
    cache._now = lambda: t + 24 * 3600 - 1
    assert cache.get("AAPL", "financials") == payload
