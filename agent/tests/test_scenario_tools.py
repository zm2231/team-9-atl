import json
from types import SimpleNamespace

from readiness_agent.scenario_tools import _context, _track_lonlats, run_scenario


def ctx(payload):
    parts = [SimpleNamespace(text="What happens here?"), SimpleNamespace(text=f"CONTEXT v1 {json.dumps(payload)}")]
    return SimpleNamespace(user_content=SimpleNamespace(parts=parts))


def test_context_is_read_from_the_second_part():
    assert _context(ctx({"county_fips": "13051"})) == {"county_fips": "13051"}


def test_missing_or_bad_context_is_empty():
    assert _context(None) == {}
    bad = SimpleNamespace(user_content=SimpleNamespace(parts=[SimpleNamespace(text="CONTEXT v1 {")]))
    assert _context(bad) == {}


def test_track_accepts_linestring_feature_and_point():
    line = {"type": "LineString", "coordinates": [[-85.0, 29.0], [-84.0, 31.0]]}
    assert _track_lonlats({"track": line}) == [(-85.0, 29.0), (-84.0, 31.0)]
    assert _track_lonlats({"track": {"type": "Feature", "geometry": line}}) == [(-85.0, 29.0), (-84.0, 31.0)]
    assert _track_lonlats({"track": {"type": "Point", "coordinates": [-81.1, 32.0]}}) == [(-81.1, 32.0)]
    assert _track_lonlats({}) == []


def test_without_track_or_position_it_asks_for_one():
    assert run_scenario(tool_context=ctx({}))["status"] == "needs_track_or_position"


def raw_ctx(text):
    parts = [SimpleNamespace(text="q"), SimpleNamespace(text=text)]
    return SimpleNamespace(user_content=SimpleNamespace(parts=parts))


def test_non_object_context_is_empty_and_never_raises():
    for text in ["CONTEXT v1 []", "CONTEXT v1 3", 'CONTEXT v1 "x"', "CONTEXT v1 null"]:
        assert _context(raw_ctx(text)) == {}
        result = run_scenario(tool_context=raw_ctx(text))
        assert result["status"] == "needs_track_or_position"
        assert result["source"]


def test_malformed_geometry_is_dropped():
    assert _track_lonlats({"track": "x"}) == []
    assert _track_lonlats({"track": {"type": "LineString", "coordinates": "x"}}) == []
    bad = {"type": "LineString", "coordinates": [[-85, 29], ["a", 1], [1], None, [-84, 999]]}
    assert _track_lonlats({"track": bad}) == [(-85.0, 29.0)]


def test_bad_scenario_and_category_still_run():
    track = {"type": "LineString", "coordinates": [[-85.6, 29.0], [-84.3, 31.6]]}
    for scenario in [[], "x", {"track": track, "category": "huge"}, {"track": track, "category": 9}]:
        result = run_scenario(tool_context=ctx({"scenario": scenario, "county_fips": 7}))
        assert result["source"]


def test_bad_date_returns_status_with_source():
    result = run_scenario(lat=26.0, lon=-86.0, heading_deg=0, date="soon", tool_context=ctx({}))
    assert result["status"] == "bad_date"
    assert result["source"]


def test_no_matching_storms_returns_status_with_source():
    result = run_scenario(lat=10.0, lon=-30.0, heading_deg=180, date="2026-02-01", tool_context=ctx({}))
    assert result["status"] == "no_matching_past_storms"
    assert result["source"]


def test_drawn_scenario_contract(monkeypatch):
    from readiness_agent.scenario import movement

    monkeypatch.setattr(movement, "_session", lambda: (_ for _ in ()).throw(OSError("offline")))
    track = {"type": "LineString", "coordinates": [[-86.5, 27.0], [-85.2, 30.5], [-84.3, 31.6], [-82.0, 34.0]]}
    result = run_scenario(tool_context=ctx({"county_fips": "13095", "scenario": {"track": track, "category": 4}}))
    assert result["source"]
    selected = next(r for r in result["counties"] if r["county_fips"] == "13095")
    assert {"patients", "centres", "stations", "centres_down"} <= set(selected["dialysis_patients"])
    assert set(selected["in_surge_zone"]) == {"shelter_ids", "dialysis_ccns"}
    assert "modelled" in selected["status"]
    shelter_ids = {r["shelter_id"] for r in result["receiving"]["sites"] if "shelter_id" in r}
    assert set(result["receiving_top"]) <= shelter_ids
    assert result["statewide"]["counties_affected_in_most_draws"] == len(result["affected_county_fips"])


def test_zero_length_track_returns_status_with_source():
    track = {"type": "LineString", "coordinates": [[-83.0, 32.0], [-83.0, 32.0]]}
    result = run_scenario(tool_context=ctx({"scenario": {"track": track, "category": 3}}))
    assert result["status"] == "needs_track_or_position"
    assert result["source"]


def test_season_tools_return_sourced_error_when_bigquery_fails(monkeypatch):
    from google.api_core.exceptions import Forbidden

    from readiness_agent import scenario_tools

    def fail(*_a, **_k):
        raise Forbidden("denied")

    monkeypatch.setattr(scenario_tools, "_run_query", fail)
    risk = scenario_tools.season_county_risk("13051")
    gaps = scenario_tools.gap_sensitivity()
    assert risk["status"] == gaps["status"] == "error"
    assert risk["counties"] == [] and gaps["gaps"] == []
    assert risk["source"] and gaps["source"]


def test_switches_merge_context_and_arguments():
    from readiness_agent.scenario_tools import _switches

    s = _switches({"site_overrides": {"off": ["a", 3], "assume_generator": "b"}}, ["c"], None)
    assert s["sites_off"] == frozenset({"a", "c"})
    assert s["assume_generator"] == frozenset()
    assert set(s["invalid"]) == {"3", "'b'"}
    bad = _switches({"site_overrides": "x"}, None, None)
    assert bad["sites_off"] == frozenset() and bad["invalid"] == ["'x'"]


def test_malformed_switches_leave_baseline_and_are_reported():
    track = {"type": "LineString", "coordinates": [[-86.5, 27.0], [-85.2, 30.5], [-84.3, 31.6], [-82.0, 34.0]]}
    base = run_scenario(tool_context=ctx({"county_fips": "13095", "scenario": {"track": track, "category": 4}}))
    for off in ["140058", [123], {"x": 1}]:
        r = run_scenario(tool_context=ctx({"county_fips": "13095", "scenario": {
            "track": track, "category": 4, "site_overrides": {"off": off}}}))
        assert r["receiving"]["lacking_shelter"] == base["receiving"]["lacking_shelter"]
        assert r["receiving"]["ignored_ids"]
        assert "delta" not in r["receiving"]


def test_season_malformed_switch_reported():
    from readiness_agent.scenario_tools import season_county_risk

    r = season_county_risk(county_fips="13127", sites_off="140058")
    assert "'140058'" in r["ignored_ids"]


def test_season_rejects_unknown_outlook_with_source():
    from readiness_agent.scenario_tools import season_county_risk

    r = season_county_risk(outlook="bogus")
    assert r["status"] == "unknown_outlook" and r["source"]


def test_season_with_switches_runs_live_and_reports_ignored_ids():
    from readiness_agent.scenario_tools import season_county_risk

    r = season_county_risk(county_fips="13127", outlook="el_nino", sites_off=["nope"])
    assert r["run"] == "live" and r["ignored_ids"] == ["nope"]
    assert len(r["counties"]) == 1
    assert "ENSO" in r["outlook_note"]


def test_outlook_notes_state_backtest_honestly():
    from readiness_agent.scenario_tools import season_outlook_note

    assert "not an independent check" in season_outlook_note("recent")
    assert "cpc.ncep.noaa.gov" in season_outlook_note("noaa_aug_2026")


def test_county_plan_marks_failed_sections_not_determined(monkeypatch):
    from google.api_core.exceptions import Forbidden

    from readiness_agent import scenario_tools

    def fail(*_a, **_k):
        raise Forbidden("denied")

    monkeypatch.setattr(scenario_tools, "_readiness_brief", fail)
    monkeypatch.setattr(scenario_tools, "_run_query", fail)
    plan = scenario_tools.county_plan("13127")
    assert plan["readiness_brief"]["status"] == "not_determined"
    assert plan["audit"]["status"] == "not_determined"
    assert plan["power_outage_frequency"]["by_outlook"]["long_run"]["county_fips"] == "13127"
    eff = plan["generator_switch_effect"]
    assert eff["statewide_lacking_shelter"]["all_assumed"]["one_in_10"] <= (
        eff["statewide_lacking_shelter"]["recorded_only"]["one_in_10"])


def test_county_plan_rejects_non_georgia():
    from readiness_agent.scenario_tools import county_plan

    assert county_plan("12001")["status"] == "needs_county"
