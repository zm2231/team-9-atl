from typing import Any

import numpy as np
import pytest

from readiness_agent import scenario_tools
from readiness_agent.scenario import data, season, site_updates, siting


def row(uid, site_id, field, value, when, kind="medical_shelter", who="pat"):
    return {
        "update_id": uid,
        "site_kind": kind,
        "site_id": site_id,
        "field": field,
        "value": value,
        "entered_by": who,
        "entered_at": when,
    }


UNRECORDED = next(
    s["shelter_id"] for s in data.sites()["medical_shelters"] if s["generator"] == "UNRECORDED"
)


def test_latest_row_wins_per_site_and_field():
    rows = [
        row("b", UNRECORDED, "generator", "YES", "2026-10-20T00:00:00"),
        row("a", UNRECORDED, "generator", "NO", "2026-10-01T00:00:00"),
        row("c", UNRECORDED, "seats", "300", "2026-10-02T00:00:00"),
    ]
    got = site_updates.latest(rows)[("medical_shelter", UNRECORDED)]
    assert got["generator"]["value"] == "YES"
    assert got["seats"]["value"] == "300"


def test_updates_applied_and_labelled_next_to_registry(monkeypatch):
    rows = [row("a", UNRECORDED, "generator", "yes", "2026-10-20T08:00:00", who="lee")]
    monkeypatch.setattr(scenario_tools, "_fetch_site_updates", lambda: rows)
    r = scenario_tools.season_county_risk()
    change = r["planner_updates"]["changes"][0]
    assert change["registry"] == "UNRECORDED" and change["planner"] == "YES"
    assert change["label"] == "planner-reported (lee, 2026-10-20)"
    base = season.run_season()
    assert (
        r["statewide"]["lacking_shelter"]["total"]["one_in_10"]
        <= base["statewide"]["lacking_shelter"]["total"]["one_in_10"]
    )
    sites = site_updates.effective_sites(
        data.sites(), site_updates.planner_inputs(rows, data.sites())
    )
    site = next(s for s in sites["medical_shelters"] if s["shelter_id"] == UNRECORDED)
    assert site["generator"] == "YES" and site["planner_reported"]["generator"].startswith(
        "planner"
    )
    assert (
        next(s for s in data.sites()["medical_shelters"] if s["shelter_id"] == UNRECORDED)[
            "generator"
        ]
        == "UNRECORDED"
    )


def test_bigquery_failure_falls_back_to_registry(monkeypatch):
    def fail():
        raise RuntimeError("no credentials")

    monkeypatch.setattr(scenario_tools, "_fetch_site_updates", fail)
    r = scenario_tools.season_county_risk(county_fips="13051")
    assert r["planner_updates"]["status"] == "registry_only"
    assert "registry values only" in r["planner_updates"]["message"]


def test_malformed_overrides_go_to_ignored_ids():
    stations: Any = "many"
    sites: Any = [{"lat": 99, "lon": -83, "seats": 50, "generator": "YES"}, "x"]
    r = scenario_tools.season_county_risk(
        county_fips="13051",
        seats_override={"nope": 5, UNRECORDED: -3},
        stations_override=stations,
        add_sites=sites,
    )
    ignored = " ".join(r["ignored_ids"])
    for bad in ("nope=5", f"{UNRECORDED}=-3", "'many'", "'lat': 99", "'x'"):
        assert bad in ignored
    assert r["added_sites"] == []


def test_added_site_reduces_lacking_shelter_where_it_reaches():
    base = season.run_season()
    worst = max(
        base["counties"], key=lambda c: c["lacking_shelter"]["no_powered_seat"]["one_in_10"]
    )
    c = next(x for x in data.counties() if x["county_fips"] == worst["county_fips"])
    r = season.run_season(
        add_sites=[{"lat": c["lat"], "lon": c["lon"], "seats": 5000, "generator": "YES"}]
    )
    after = next(x for x in r["counties"] if x["county_fips"] == c["county_fips"])
    assert (
        after["lacking_shelter"]["no_powered_seat"]["one_in_10"]
        < worst["lacking_shelter"]["no_powered_seat"]["one_in_10"]
    )
    assert r["added_sites"][0]["surge"] == season.ADDED_SURGE_NOTE
    reach = season.reach_of(c["lat"], c["lon"])
    fips = [str(f) for f in season.events()["county_fips"]]
    for x, y in zip(base["counties"], r["counties"], strict=True):
        if not reach[fips.index(x["county_fips"])]:
            assert (
                x["lacking_shelter"]["no_powered_seat"] == y["lacking_shelter"]["no_powered_seat"]
            )


def test_greedy_accounts_for_overlap():
    base = season.siting_base()
    scored = season.evaluate_candidates(base, siting.county_candidates())
    a = next(c for c in scored if c["lacking_shelter_1in10_reduction"] > 0)
    twin = {**a, "candidate_id": "twin"}
    single = season.evaluate_candidates(base, [twin])[0]["lacking_shelter_1in10_reduction"]
    combo = season.greedy(base, [a, twin])
    assert combo[0]["candidate_id"] == a["candidate_id"]
    assert len(combo) == 1 or combo[1]["added_reduction_1in10"] < single


def test_p_helps_is_paired():
    base = season.siting_base()
    useless = {"candidate_id": "x", "kind": "county_centre", "lat": 34.9, "lon": -85.6, "seats": 0}
    r = season.evaluate_candidates(base, [useless])[0]
    assert r["p_helps"] == 0 and r["expected_reduction_per_year"] == 0


def test_record_site_update_rejects_bad_input():
    bad = scenario_tools.record_site_update("medical_shelter", UNRECORDED, "colour", "red")
    assert bad["status"] == "invalid" and "field must be one of" in bad["message"]
    assert scenario_tools.record_site_update("dialysis", "x", "seats", "4")["status"] == "invalid"
    assert (
        scenario_tools.record_site_update("medical_shelter", UNRECORDED, "seats", "-1")["status"]
        == "invalid"
    )


def test_recommend_sites_label_and_proposal():
    r = scenario_tools.recommend_sites(limit=3, lat=33.0, lon=-84.0, seats=150)
    assert "modelled reduction" in r["label"] and "do not add up" in r["note"]
    assert len(r["top"]) == 3 and r["proposed"][0]["seats_assumed"] == 150
    assert len(r["best_combination_of_3"]) <= 3
    assert scenario_tools.recommend_sites(lat=0, lon=0, seats=5)["ignored_ids"]


def test_probabilities_are_shares_of_seasons():
    r = season.run_season()
    for p in (r["statewide"]["probability"], r["counties"][0]["probability"]):
        assert p["label"] == "share of simulated seasons"
        assert 0 <= p["p_lacking_shelter_50"] <= p["p_lacking_shelter_any"] <= 1


def test_severity_outlooks_and_custom():
    ev = season.events()
    long = season.severity_shares(season.outlook_event_rates("long_run"), ev["category"])
    noaa = season.outlook_event_rates("noaa_aug_2026")
    shares = season.severity_shares(noaa, ev["category"])
    assert shares["cat3_plus_share"] == pytest.approx(
        long["cat3_plus_share"] * (1 / 10) / (3 / 14), abs=1e-3
    )
    assert noaa.sum() == pytest.approx(200 / 76 * 10 / 14)
    custom = {"storms_per_year": 3, "hurricane_share": 0.5, "major_share": 0.2, "source": "test"}
    r = season.run_season("custom", custom=custom)
    assert r["storms_per_year"] == 3 and r["custom_source"] == "test"
    assert r["severity"] == {"cat1_plus_share": 0.5, "cat3_plus_share": 0.2}
    with pytest.raises(ValueError):
        season.run_season("custom", custom={**custom, "major_share": 0.9})
    with pytest.raises(ValueError):
        season.run_season("custom", custom={**custom, "source": ""})


def test_as_of_date_keeps_rest_of_season():
    share = season.season_remaining_share("2026-10-27")
    assert 0 < share < season.season_remaining_share("2026-08-01") < 1
    r = season.run_season(as_of_date="2026-10-27")
    assert r["as_of"]["share_of_season_remaining"] == share
    assert r["storms_per_year"] == pytest.approx(200 / 76 * share, rel=0.05)
    assert np.isclose(
        season.outlook_event_rates("long_run", as_of_date="2026-01-01").sum(), 200 / 76
    )


def test_single_coordinate_update_moves_reach():
    site = next(s for s in data.sites()["medical_shelters"] if s["generator"] == "YES")
    rows = [row("a", site["shelter_id"], "lat", "34.9", "2026-10-20T00:00:00")]
    planner = site_updates.planner_inputs(rows, data.sites())
    assert planner["location_override"][site["shelter_id"]] == {"lat": 34.9, "lon": site["lon"]}
    ev, ignored, _ = season.site_inputs(
        season.events(), location_override=planner["location_override"]
    )
    assert ignored == []
    j = [str(x) for x in ev["shelter_id"]].index(site["shelter_id"])
    assert (ev["shelter_reach"][:, j] == season.reach_of(34.9, site["lon"])).all()


def test_as_of_date_handles_leap_years():
    assert season._day_of_year("2024-02-29") == season._day_of_year("2025-02-28")
    assert season._day_of_year("2024-03-01") == season._day_of_year("2025-03-01")
    assert season.season_remaining_share("2024-02-29") == 1.0
    days = season.storm_day_of_year()
    cut = season._day_of_year("2026-09-15")
    assert season.season_remaining_share("2024-09-15") == round(float((days > cut).mean()), 4)


def _subset(ev: dict, keep: np.ndarray) -> dict:
    n = len(ev["category"])
    return {k: v[keep] if getattr(v, "shape", (0,))[:1] == (n,) else v for k, v in ev.items()}


def test_builder_rates_follow_the_event_subset_given():
    from readiness_agent.scenario.build import build_season

    ev = season.events()
    hist = _subset(ev, ~ev["event_synthetic"])
    observed = {str(f): 1 for f in ev["county_fips"]}
    for part in (hist, ev):
        lam = build_season.county_lambda(part, "long_run")
        assert lam.shape == (159,)
        bt = build_season.severity_backtest(part, observed, 0.7)
        assert 0 <= bt["severity_share_inside"] <= 1


def test_severity_backtest_ignores_event_order():
    from readiness_agent.scenario.build import build_season

    ev = season.events()
    observed = {str(f): 1 for f in ev["county_fips"]}
    order = np.random.default_rng(1).permutation(len(ev["category"]))
    shuffled = _subset(ev, order)
    a = build_season.severity_backtest(ev, observed, 0.7)
    b = build_season.severity_backtest(shuffled, observed, 0.7)
    assert a["severity_share_inside"] == b["severity_share_inside"]
    assert a["severity_statewide"] == b["severity_statewide"]


def test_as_of_after_last_storm_gives_an_empty_season():
    r = season.run_season(as_of_date="2026-12-31")
    assert r["storms_per_year"] == 0 and r["as_of"]["share_of_season_remaining"] == 0
    assert r["statewide"]["lacking_shelter"]["total"]["one_in_10"] == 0
    assert r["statewide"]["probability"]["p_lacking_shelter_any"] == 0
    assert season.siting_base(as_of_date="2026-12-31")["before"]["state_1in10"] == 0


def test_fixed_default_is_unchanged():
    a, b = season.run_season(), season.run_season(uncertainty="fixed")
    assert a["statewide"] == b["statewide"] and a["uncertainty"]["mode"] == "fixed"


def test_sampled_mode_reports_ranges_and_attribution():
    r = season.run_season(uncertainty="sampled")
    u = r["uncertainty"]
    assert u["mode"] == "sampled"
    assert set(u["unknowns"]) == set(season.UNKNOWNS)
    assert "0.375" in u["unknowns"]["unrecorded_generators"]
    assert "8 medical shelters" in u["unknowns"]["unrecorded_generators"]
    rows = u["spread_attribution"]["lacking_shelter"]["unknowns"]
    assert sum(x["sobol_first_order"] for x in rows.values()) <= 1
    total = r["statewide"]["lacking_shelter"]["total"]
    assert total["typical"] <= total["one_in_10"] <= total["one_in_100"]
    with pytest.raises(ValueError):
        season.run_season(uncertainty="maybe")


def test_first_order_estimator_on_known_cases():
    rng = np.random.default_rng(0)
    x = rng.random(5000)
    assert season.first_order(x, x)["sobol_first_order"] > 0.99
    assert season.first_order(rng.random(5000), x)["sobol_first_order"] < 0.01
    y = x + rng.random(5000)
    assert abs(season.first_order(y, x)["sobol_first_order"] - 0.5) < 0.05


def test_tools_accept_uncertainty():
    r = scenario_tools.season_county_risk(county_fips="13051", uncertainty="sampled")
    assert r["uncertainty"]["mode"] == "sampled"
    assert scenario_tools.season_county_risk(uncertainty="bogus")["status"] == "unknown_uncertainty"
