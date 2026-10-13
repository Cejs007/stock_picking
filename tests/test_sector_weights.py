import json
import math

import pytest

from stock_picking.data.models import FinancialData
from stock_picking.settings import DEFAULT_SECTOR_WEIGHTS, Settings
from stock_picking.valuator import valuate


def test_weights_for_known_sector_returns_template() -> None:
    s = Settings()
    assert s.weights_for("Financial Services") == DEFAULT_SECTOR_WEIGHTS["Financial Services"]


def test_weights_for_unknown_sector_falls_back_to_default() -> None:
    s = Settings()
    assert s.weights_for("Nonexistent Sector") == s.model_weights


def test_weights_for_none_falls_back_to_default() -> None:
    s = Settings()
    assert s.weights_for(None) == s.model_weights


def test_financials_template_disables_ev_and_dcf() -> None:
    # Banks have no meaningful EBITDA/FCF -> those models must be off.
    w = Settings().weights_for("Financial Services")
    assert w["ev_ebitda"] == 0.0
    assert w["dcf"] == 0.0
    assert w["graham"] > 0 and w["pe_relative"] > 0


def test_tech_template_disables_graham() -> None:
    assert Settings().weights_for("Technology")["graham"] == 0.0


def test_valuate_uses_sector_template(fin: FinancialData) -> None:
    # Financials template = graham + pe only (ev, dcf disabled).
    settings = Settings()
    settings.sector_weights["Financial Services"] = {
        "graham": 1.0, "pe_relative": 1.0, "ev_ebitda": 0.0, "dcf": 0.0
    }
    fin_bank = fin.model_copy(update={"sector": "Financial Services"})
    result = valuate(fin_bank, settings)
    graham_fv = math.sqrt(22.5 * 5.0 * 40.0)
    pe_fv = 85.0
    expected = (graham_fv + pe_fv) / 2
    assert result.fair_value_composite == pytest.approx(expected, rel=1e-6)


def test_valuate_without_sector_uses_default(fin: FinancialData) -> None:
    # No sector -> default fallback weights {graham:0, pe:1.5, ev:1, dcf:1}.
    settings = Settings()
    w = settings.model_weights
    result = valuate(fin, settings)
    assert result.fair_values["dcf"] is not None
    total = w["pe_relative"] + w["ev_ebitda"] + w["dcf"]  # graham weight is 0
    expected = (85.0 * w["pe_relative"] + 18.0 * w["ev_ebitda"]
                + result.fair_values["dcf"] * w["dcf"]) / total
    assert result.fair_value_composite == pytest.approx(expected, rel=1e-6)


def test_tuned_weights_path_overrides_priors(tmp_path) -> None:
    payload = {
        "sector_weights": {"Technology": {"graham": 0.0, "pe_relative": 9.0,
                                          "ev_ebitda": 0.0, "dcf": 0.0}},
        "default_weights": {"graham": 1.0, "pe_relative": 1.0,
                            "ev_ebitda": 1.0, "dcf": 1.0},
    }
    p = tmp_path / "tuned.json"
    p.write_text(json.dumps(payload), encoding="utf-8")
    s = Settings(tuned_weights_path=str(p))
    assert s.weights_for("Technology")["pe_relative"] == 9.0
    assert s.model_weights == {"graham": 1.0, "pe_relative": 1.0,
                               "ev_ebitda": 1.0, "dcf": 1.0}


def test_missing_tuned_path_keeps_priors() -> None:
    s = Settings(tuned_weights_path="/no/such/file.json")
    assert s.weights_for("Technology") == DEFAULT_SECTOR_WEIGHTS["Technology"]
