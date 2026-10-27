import json
from pathlib import Path

import numpy as np
import pytest

from readiness_agent.scenario import season

DATA = Path(__file__).resolve().parents[1] / "readiness_agent" / "scenario" / "data"


@pytest.fixture(scope="module")
def baseline():
    return season.run_season()


def test_outlook_rates_match_measured():
    storm_season = season.events()["storm_season"]
    assert len(storm_season) == 200
    rates = {o: season.storms_per_year(o, storm_season) for o in season.OUTLOOKS}
    assert round(rates["la_nina"], 2) == 3.22
    assert round(rates["neutral"], 2) == 2.50
    assert round(rates["el_nino"], 2) == 2.35
    assert rates["long_run"] == pytest.approx(200 / 76)
    assert rates["noaa_aug_2026"] == pytest.approx(rates["long_run"] * 10 / 14)
    assert len(season.outlook_years("la_nina")[0]) == 18
    assert "NOAA CPC August 2026" in season.OUTLOOKS["noaa_aug_2026"]


def test_event_rates_sum_to_storm_rate():
    ev = season.events()
    for o in season.OUTLOOKS:
        rate = season.event_rates(o, ev["storm_season"], ev["storm_of_event"])
        assert rate.sum() == pytest.approx(season.storms_per_year(o, ev["storm_season"]))


def test_baseline_matches_table_values(baseline):
    table = json.loads((DATA / "season_backtest.json").read_text())["long_run_statewide"]
    got = baseline["statewide"]
    for path in (
        ("power_dependent_affected",),
        ("lacking_shelter", "no_powered_seat"),
        ("lacking_shelter", "total"),
        ("needing_transport", "no_vehicle"),
    ):
        a, b = got, table
        for k in path:
            a, b = a[k], b[k]
        assert a["one_in_10"] == pytest.approx(b["one_in_10"], rel=0.08)
        assert a["typical"] == pytest.approx(b["typical"], rel=0.08)
    assert len(baseline["counties"]) == 159
    assert baseline["ignored_ids"] == []


def test_every_site_off_leaves_every_seeker_without_a_seat():
    ev = season.events()
    ids = [str(x) for x in ev["shelter_id"]] + [str(x) for x in ev["dialysis_ccn"]]
    r = season.run_season(sites_off=ids)
    assert r["ignored_ids"] == []
    share = season.RELOCATION_SHARE["base"]
    for c in r["counties"]:
        pd = c["power_dependent_affected"]
        seat = c["lacking_shelter"]["no_powered_seat"]
        assert abs(seat["one_in_10"] - share * pd["one_in_10"]) <= 1
        assert abs(seat["typical"] - share * pd["typical"]) <= 1


def test_unknown_ids_are_ignored_not_raised():
    ev = season.events()
    ccn = str(ev["dialysis_ccn"][0])
    r = season.run_season(sites_off=["nope"], assume_generator=["also-nope", ccn])
    assert r["ignored_ids"] == ["also-nope", "nope", ccn]
    assert r["sites_off"] == []


def test_assume_generator_never_raises_need(baseline):
    ev = season.events()
    unrec = [str(x) for x in ev["shelter_id"][ev["shelter_generator"] == "UNRECORDED"]]
    assert unrec
    r = season.run_season(assume_generator=unrec)
    before = baseline["statewide"]["lacking_shelter"]["no_powered_seat"]["one_in_10"]
    after = r["statewide"]["lacking_shelter"]["no_powered_seat"]["one_in_10"]
    assert after <= before
    assert r["assume_generator"] == sorted(unrec)


def test_events_file_is_small_and_float32():
    assert season.EVENTS_FILE.stat().st_size < 10_000_000
    ev = season.events()
    assert ev["pd_affected"].dtype == np.float32
    n = len(ev["category"])
    assert ev["pd_affected"].shape == (n, 159)
    assert ev["event_synthetic"].shape == ev["event_outside_support"].shape == (n,)
    assert 0 < ev["event_synthetic"].mean() < 1
    assert (ev["event_shift_km"][~ev["event_synthetic"]] == 0).all()
    assert len(ev["storm_name"]) == len(ev["storm_season"])


def test_season_reports_one_in_100():
    r = season.run_season("long_run")
    block = r["statewide"]["lacking_shelter"]["total"]
    assert block["typical"] <= block["one_in_10"] <= block["one_in_100"]


def test_synthetic_wind_climate_matches_history():
    check = json.loads((DATA / "season_synthetic_check.json").read_text())
    diff = check["per_county_wind_chance_difference"]
    assert diff["p34kt"]["mean_abs_diff"] < 0.03
    assert diff["p64kt"]["mean_abs_diff"] < 0.02


def test_enso_backtest_is_reported():
    bt = json.loads((DATA / "season_backtest.json").read_text())
    cond = bt["enso_conditional"]
    assert set(cond["phases"].values()) <= {"la_nina", "neutral", "el_nino"}
    assert 0 <= cond["share_inside"] <= 1
    assert ("does not improve" in cond["verdict"]) == (cond["share_inside"] <= bt["share_inside"])


def test_unknown_outlook_and_case_raise():
    with pytest.raises(ValueError):
        season.run_season("hot")
    with pytest.raises(ValueError):
        season.run_season(case="extreme")
