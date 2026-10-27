import datetime as dt

import numpy as np
import pytest

from readiness_agent import scenario_tools
from readiness_agent.scenario import conditions, season

ONI_PAGE = " SEAS  YR   TOTAL   ANOM\n  JJA 2026  29.09   1.80\n  JAS 2026  29.12   2.16\n"
TNA_PAGE = (
    " 1948 2026\n"
    " 2026     0.24    0.38    0.04    0.07    0.14    0.13    0.43  -99.99  -99.99  -99.99"
    "  -99.99  -99.99\n  -99.99\n"
)
ENSO_PAGE = (
    "<p>ENSO Alert System Status: El Nino Advisory</p><p>Synopsis: El Nino continues. "
    "More text.</p>"
)
OUTLOOK_PAGE = "<p>7-13 Named Storms, 2-6 Hurricanes 0-2 Major Hurricanes</p>"


def _online(monkeypatch, pages):
    def get(url):
        if url in pages:
            return pages[url]
        raise OSError(url)

    monkeypatch.setattr(conditions, "_get", get)
    conditions._cache.clear()


def test_offline_fallback_is_sourced_and_never_raises():
    out = conditions.season_conditions("2026-08-10")
    oni, tna = out["inputs"]["oni"], out["inputs"]["mdr_sst_anomaly"]
    assert oni["status"] == "fallback" and oni["fetch_error"] == "OSError"
    assert oni["season"] and "oni.txt" in oni["source"]
    assert tna["status"] == "fallback" and tna["value"] is None
    assert out["inputs"]["enso_forecast"]["status"] == "fallback"
    noaa = out["inputs"]["noaa_outlook"]
    assert noaa["status"] == "configured" and noaa["issued"] == "2026-08-06"
    assert noaa["url"] == season.NOAA_URL and noaa["named"] == (7, 13)
    assert out["conditions_model"]["storms_per_year"]["predictors"] == ["long_run"]


def test_live_inputs_are_parsed_and_cached_per_day(monkeypatch):
    calls = []
    pages = {conditions.ONI_URL: ONI_PAGE, conditions.TNA_URL: TNA_PAGE,
             conditions.ENSO_URL: ENSO_PAGE, season.NOAA_URL: OUTLOOK_PAGE}
    _online(monkeypatch, pages)
    real = conditions._get
    monkeypatch.setattr(conditions, "_get", lambda url: calls.append(url) or real(url))
    out = conditions.season_conditions("2026-08-10")
    assert out["inputs"]["oni"] == {
        "value": 2.16, "season": "JAS 2026", "source": "NOAA CPC ONI",
        "url": conditions.ONI_URL, "status": "live"}
    assert out["inputs"]["mdr_sst_anomaly"]["value"] == 0.43
    assert out["inputs"]["mdr_sst_anomaly"]["month"] == "2026-07"
    assert out["inputs"]["enso_forecast"]["synopsis"] == "El Nino continues."
    assert out["inputs"]["noaa_outlook"]["status"] == "live"
    n = len(calls)
    conditions.season_conditions("2026-09-01")
    assert len(calls) == n


def test_blend_math():
    model = {"value": 2.0, "p10": 1.0, "p90": 3.0}
    noaa = {"value": 1.0, "p10": 0.0, "p90": 2.0}
    assert conditions.blend(model, noaa, 0.5) == {"value": 1.5, "p10": 0.5, "p90": 2.5}
    assert conditions.blend(model, noaa, 0.25) == {"value": 1.75, "p10": 0.75, "p90": 2.75}
    assert conditions.blend(model, None) == model


def test_noaa_counts_convert_by_ratio_to_average():
    m = conditions.model()
    implied = conditions.noaa_implied(conditions.OUTLOOKS[2026])
    assert implied["storms_per_year"]["value"] == pytest.approx(m["storms_per_year"] * 10 / 14)
    assert implied["storms_per_year"]["p10"] == pytest.approx(m["storms_per_year"] * 7 / 14)
    assert implied["hurricane_share"]["value"] == pytest.approx(
        m["hurricane_share"] * (4 / 10) / (7 / 14))
    assert implied["major_share"]["value"] == pytest.approx(
        m["major_share"] * (1 / 10) / (3 / 14))


def test_blended_outlook_uses_stated_weights():
    out = conditions.season_conditions("2026-08-10")
    w = out["weights"]["noaa_outlook"]
    assert w == conditions.NOAA_WEIGHT and out["weights"]["conditions_model"] == 1 - w
    for part in ("storms_per_year", "hurricane_share", "major_share"):
        expect = (1 - w) * out["conditions_model"][part]["value"] + w * out["noaa_implied"][
            part]["value"]
        assert out["blended"][part]["value"] == pytest.approx(expect, abs=1e-3)
    assert out["custom"]["storms_per_year"] == pytest.approx(
        out["blended"]["storms_per_year"]["value"], abs=1e-3)
    assert "NOAA CPC August 2026" in out["custom"]["source"]


def test_plans_current_season_trimmed_when_most_remains():
    out = conditions.season_conditions("2026-06-01")
    plan = out["plan"]
    assert out["share_of_season_remaining"] > conditions.PLAN_CURRENT_ABOVE
    assert plan["season"] == 2026 and plan["trimmed_to_as_of"] is True
    assert plan["run_as_of_date"] == "2026-06-01"
    assert plan["reason"].startswith("Planning the rest of the 2026 season:")
    assert out["rest_of_current_season"] is None
    assert out["inputs"]["noaa_outlook"] is None
    assert plan["expected_storms"]["value"] == pytest.approx(
        out["blended"]["storms_per_year"]["value"] * out["share_of_season_remaining"], abs=0.01)


def test_plans_next_full_season_late_in_the_year():
    out = conditions.season_conditions(dt.date(2026, 10, 27))
    plan, rest = out["plan"], out["rest_of_current_season"]
    assert plan["season"] == 2027 and plan["trimmed_to_as_of"] is False
    assert plan["run_as_of_date"] is None
    pct = round((1 - out["share_of_season_remaining"]) * 100)
    assert plan["reason"] == (
        f"Planning the 2027 season: {pct}% of 2026's storms historically arrive before 27 Oct.")
    assert out["inputs"]["noaa_outlook"] is None
    assert "2027" in out["noaa_note"]
    assert out["weights"] == {"conditions_model": 1.0, "noaa_outlook": 0.0}
    assert plan["expected_storms"]["value"] == pytest.approx(
        out["conditions_model"]["storms_per_year"]["value"], abs=0.01)
    assert "2027 season" in out["custom"]["source"]
    assert rest["season"] == 2026 and rest["as_of_date"] == "2026-10-27"
    assert rest["noaa_outlook"]["issued"] == "2026-08-06"
    assert rest["expected_storms"]["value"] == pytest.approx(
        rest["blended"]["storms_per_year"]["value"] * rest["share_of_season_remaining"],
        abs=0.01)


def test_no_outlook_before_issue_date_or_in_other_years():
    for day in ("2026-07-01", "2025-09-01"):
        out = conditions.season_conditions(day)
        assert out["inputs"]["noaa_outlook"] is None
        assert out["weights"] == {"conditions_model": 1.0, "noaa_outlook": 0.0}
        assert out["blended"]["storms_per_year"]["value"] == pytest.approx(
            out["conditions_model"]["storms_per_year"]["value"], abs=1e-3)


def test_backtest_reports_selection_honestly():
    m = conditions.model()
    base = next(r for r in m["models"] if r["predictors"] == ["long_run"])
    fam = m["count_family"]
    for part, names in m["selected"].items():
        if names == ["long_run"]:
            continue
        row = next(r for r in m["models"] if r["predictors"] == names)
        key = "loso_log_score" if part == "storms" else "loso_share_log_score"
        sub = fam if part == "storms" else part.split("_")[0]
        assert row[key][sub] > base[key][sub]
    assert m["oni_only_per_unit"]["ci95"][0] < m["oni_only_per_unit"]["rate_ratio"]


@pytest.fixture
def late_october(monkeypatch):
    monkeypatch.setattr(conditions, "_today", lambda: dt.date(2026, 10, 27))


def test_auto_is_default_and_sourced(late_october):
    r = scenario_tools.season_county_risk("13051")
    assert r["outlook"] == "auto"
    note = r["outlook_note"]
    assert note.startswith("Planning the 2027 season:")
    assert "No NOAA seasonal hurricane outlook for 2027" in note
    assert "Rest of 2026 after 2026-10-27" in note
    assert r["auto"]["inputs"]["oni"]["source"]
    assert r["auto"]["backtest"]["selected"]
    assert r["as_of"] is None or r["as_of"].get("date") is None
    rest = r["auto"]["rest_of_current_season"]
    assert rest["result"]["as_of"]["share_of_season_remaining"] == rest[
        "share_of_season_remaining"]
    assert [c["county_fips"] for c in rest["result"]["counties"]] == ["13051"]
    explicit = scenario_tools.season_county_risk("13051", outlook="long_run")
    assert "auto" not in explicit and explicit["outlook"] == "long_run"


def test_season_county_risk_plans_current_season_in_june():
    r = scenario_tools.season_county_risk("13051", as_of_date="2026-06-01")
    assert r["outlook_note"].startswith("Planning the rest of the 2026 season:")
    assert r["as_of"]["date"] == "2026-06-01"
    assert r["auto"]["rest_of_current_season"] is None


def test_auto_rejects_bad_date():
    assert scenario_tools.season_county_risk("13051", as_of_date="soon")["status"] == "bad_date"
    assert scenario_tools.season_conditions("27/10/2026")["status"] == "bad_date"


def test_county_plan_defaults_to_auto(late_october):
    plan = scenario_tools.county_plan("13127")
    assert plan["outlook"] == "auto"
    assert plan["auto"]["plan"]["season"] == 2027
    section = plan["power_outage_frequency"]
    assert set(section["by_outlook"]) == {"auto", "long_run"}
    assert section["by_outlook"]["auto"]["note"].startswith("Planning the 2027 season:")
    rest = section["rest_of_current_season"]
    assert rest["season"] == 2026 and rest["county_fips"] == "13127"
    assert rest["as_of"]["date"] == "2026-10-27"


def test_county_plan_plans_current_season_in_june():
    plan = scenario_tools.county_plan("13127", as_of_date="2026-06-01")
    assert plan["auto"]["plan"]["season"] == 2026
    assert "rest_of_current_season" not in plan["power_outage_frequency"]


def test_county_plan_takes_as_of_date_and_keeps_auto_provenance():
    assert scenario_tools.county_plan("13127", as_of_date="soon")["status"] == "bad_date"
    plan = scenario_tools.county_plan("13127", as_of_date="2026-08-10")
    assert plan["auto"]["plan"]["season"] == 2026
    auto = plan["auto"]
    assert auto["as_of_date"] == "2026-08-10"
    assert 0 < auto["share_of_season_remaining"] < 1
    assert auto["inputs"]["noaa_outlook"]["issued"] == "2026-08-06"
    assert auto["inputs"]["oni"]["season"]
    assert auto["backtest"]["models"]


def test_fold_standardization_uses_training_rows_only():
    from readiness_agent.scenario.build.build_conditions import standardize

    raw = {"oni": np.array([0.0, 1.0, 2.0, 1000.0])}
    z, stats = standardize(raw, np.array([0, 1, 2]))
    assert stats["oni"] == (1.0, pytest.approx(np.std([0.0, 1.0, 2.0])))
    assert z["oni"][1] == 0.0
