import pytest

from stock_picking.settings import Settings


def test_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    for key in ("DEFAULT_WACC", "DEFAULT_MOS", "FMP_API_KEY"):
        monkeypatch.delenv(key, raising=False)
    s = Settings()
    assert s.default_wacc == pytest.approx(0.10)
    assert s.default_mos == pytest.approx(0.25)
    assert s.default_terminal_g == pytest.approx(0.03)
    assert s.default_projection_years == 10
    assert s.cache_ttl_hours == pytest.approx(24.0)
    assert s.fmp_api_key is None


def test_default_model_weights(monkeypatch: pytest.MonkeyPatch) -> None:
    s = Settings()
    assert s.model_weights == {
        "graham": 1.0,
        "pe_relative": 1.0,
        "ev_ebitda": 1.0,
        "dcf": 1.0,
    }


def test_wacc_overridden_by_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DEFAULT_WACC", "0.08")
    s = Settings()
    assert s.default_wacc == pytest.approx(0.08)


def test_mos_overridden_by_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DEFAULT_MOS", "0.30")
    s = Settings()
    assert s.default_mos == pytest.approx(0.30)


def test_fmp_api_key_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FMP_API_KEY", "test-secret")
    s = Settings()
    assert s.fmp_api_key == "test-secret"


def test_fmp_api_key_absent_is_none(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("FMP_API_KEY", raising=False)
    s = Settings()
    assert s.fmp_api_key is None
