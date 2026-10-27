import math
import time

import numpy as np
import pytest

from readiness_agent.scenario import data, engine, storms
from readiness_agent.scenario.windfield import TrackPoint, county_exposure, exposure


def synthetic_track() -> list[TrackPoint]:
    return [
        TrackPoint(h, 28.0 + 0.12 * h, -84.0 + 0.03 * h, 110 - h, 30 + 0.2 * h, 220 + h)
        for h in range(48)
    ] + [TrackPoint(48, 33.9, -82.5, 30, 60, 0), TrackPoint(54, 34.5, -82.3, 0, 60, 0)]


def test_exposure_matches_scalar():
    track = synthetic_track()
    rng = np.random.default_rng(1)
    lats = np.r_[rng.uniform(29, 35, 200), track[10].lat]
    lons = np.r_[rng.uniform(-86, -80, 200), track[10].lon]
    vec = exposure(track, lats, lons)
    for i in range(len(lats)):
        ref = county_exposure(track, lats[i], lons[i])
        for key, value in ref.items():
            if math.isnan(value):
                assert math.isnan(vec[key][i])
            else:
                assert vec[key][i] == pytest.approx(value, abs=1e-6), key


def test_exposure_empty_track():
    e = exposure([], np.array([32.0]), np.array([-83.0]))
    assert e["peak_wind_kt"][0] == 0 and math.isnan(e["first_34kt_hour"][0])


def test_counties_shape():
    rows = data.counties()
    assert len(rows) == 159
    keys = {
        "county_fips", "county_name", "lat", "lon", "pop", "power_dependent", "oxygen",
        "home_health", "dialysis_patients", "power_dependent_censored", "nursing_home_beds",
        "assisted_living_beds",
    }
    assert keys <= set(rows[0])


def test_sites_shape():
    s = data.sites()
    assert "medical_shelters" in s and "dialysis_centers" in s


def test_classify_origin():
    assert storms.classify_origin(29.5, -86.0) == "gulf"
    assert storms.classify_origin(27.0, -81.0) == "florida_peninsula"
    assert storms.classify_origin(31.5, -80.5) == "atlantic_ga"
    assert storms.classify_origin(33.5, -80.0) == "carolinas"
    assert storms.classify_origin(33.5, -86.0) == "overland_west"


def test_analog_tracks_shifted_and_filtered():
    analogs = storms.analog_tracks(29.0, -85.5, 20.0, 9, intensity_kt=90)
    assert 0 < len(analogs) <= 40
    for a in analogs:
        first = a.track[0]
        assert first.hour == 0
        assert (first.lat, first.lon) == pytest.approx((29.0, -85.5), abs=1e-9)
        assert abs(a.intensity_kt_at_match - 90) <= 20
    assert sum(a.weight for a in analogs) == pytest.approx(1.0)


def test_climatology_weights():
    clim = storms.climatology()
    first, last = data.tracks()["years"]
    assert first == 1950 and len(clim) > 100
    assert all(a.weight == pytest.approx(1 / (last - first + 1)) for a in clim)


def test_rescale_hits_category_midpoint():
    a = storms.analog_tracks(29.0, -85.5, 20.0, 9)[0]
    r = storms.rescale(a, 4)
    assert storms.peak_near_ga(r.track) == pytest.approx(124.0)


def test_drawn_track_decays_over_land():
    t = storms.drawn_track([[-86.0, 27.5], [-84.5, 29.8], [-83.5, 32.5]], 3)
    assert t[0].vmax_kt == 104.0
    assert t[-1].vmax_kt < 80
    assert t[-1].hour == pytest.approx(t[-1].hour)


def test_pattern_frequency_position():
    p = storms.pattern_frequency(lat=29.0, lon=-85.5, heading_deg=20.0, month=9)
    assert p["matching_storms"] > 0
    assert p["years"][0] == 1950
    years = p["years"][1] - 1950 + 1
    assert p["per_year"] == pytest.approx(p["matching_storms"] / years, abs=1e-4)
    assert p["p_at_least_one_per_season"] == pytest.approx(
        1 - math.exp(-p["per_year"]), abs=1e-4
    )
    lo, hi = p["per_year_range80"]
    assert lo <= p["per_year"] <= hi
    assert 0 < len(p["example_storms"]) <= 5


def test_pattern_frequency_drawn_track_intensity_floor():
    t = storms.drawn_track([[-86.0, 27.5], [-84.5, 29.8], [-83.5, 32.5]], 3)
    weak = storms.pattern_frequency(track=t, min_intensity_kt=34)
    strong = storms.pattern_frequency(track=t, min_intensity_kt=96)
    assert weak["matching_storms"] >= strong["matching_storms"] > 0


def test_poisson_quantile():
    assert storms._poisson_quantile(0, 0.9) == 0
    assert storms._poisson_quantile(10, 0.1) == 6
    assert storms._poisson_quantile(10, 0.9) == 14


def test_run_contract_and_speed():
    analogs = storms.analog_tracks(29.0, -85.5, 20.0, 9, max_tracks=40)
    tracks = [a.track for a in analogs]
    start = time.perf_counter()
    r = engine.run(tracks, n_draws=400, seed=7)
    elapsed = time.perf_counter() - start
    assert elapsed < 3.0
    n = len(data.counties())
    assert r.outage.shape == (400, n)
    assert ((r.outage >= 0) & (r.outage <= 1)).all()
    counts = np.bincount(r.track_of_draw, minlength=len(tracks))
    assert counts.max() - counts.min() <= 1
    assert r.peak_wind_kt.shape == r.hours_34kt.shape == r.ts_arrival_h.shape == (n,)
    assert len(r.outside_support) == len(tracks)
    assert r.ts_arrival_share.shape == r.p_affected.shape == (n,)
    assert np.array_equal(np.isnan(r.ts_arrival_h), r.ts_arrival_share == 0)
    assert np.allclose(r.p_affected, (r.outage >= engine.AFFECTED_SHARE).mean(axis=0))
    again = engine.run(tracks, n_draws=400, seed=7)
    assert np.array_equal(r.outage, again.outage)


def test_strong_landfall_gives_big_outage_in_south_ga():
    t = storms.drawn_track([[-85.0, 27.0], [-84.3, 30.0], [-83.5, 33.5]], 4)
    r = engine.run([t], n_draws=400, seed=1)
    fips = [c["county_fips"] for c in data.counties()]
    assert np.median(r.outage[:, fips.index("13275")]) > 0.3
    assert np.median(r.outage[:, fips.index("13241")]) < np.median(
        r.outage[:, fips.index("13275")]
    )
    assert r.ts_arrival_h[fips.index("13275")] < r.ts_arrival_h[fips.index("13121")]


def test_people_at_risk_thresholds():
    counties = [
        {"power_dependent": 100, "oxygen": 10, "home_health": 20, "dialysis_patients": 50,
         "nursing_home_beds": 30, "assisted_living_beds": 5},
        {"power_dependent": 200, "oxygen": 0, "home_health": 0, "dialysis_patients": 40,
         "nursing_home_beds": 0, "assisted_living_beds": 0},
    ]
    result = engine.Result(
        outage=np.array([[0.6, 0.2]]), track_of_draw=np.zeros(1, int),
        peak_wind_kt=np.zeros(2), hours_34kt=np.zeros(2), ts_arrival_h=np.zeros(2),
        outside_support=[False], ts_arrival_share=np.ones(2), p_affected=np.ones(2),
    )
    p = engine.people_at_risk(result, counties)
    assert p["power_dependent"].tolist() == [[60.0, 40.0]]
    assert p["oxygen"].tolist() == [[6.0, 0.0]]
    assert p["dialysis"].tolist() == [[50.0, 0.0]]
    assert p["facility_beds"].tolist() == [[35.0, 0.0]]
