import json
from pathlib import Path

import numpy as np

DATA = Path(__file__).resolve().parents[1] / "readiness_agent" / "scenario" / "data"
FLAGS = {"YES", "NO", "UNRECORDED"}


def load(name):
    return json.loads((DATA / name).read_text())


def test_sites_shape():
    sites = load("sites.json")
    assert len(sites["medical_shelters"]) > 0
    assert len(sites["dialysis_centers"]) > 0
    for s in sites["medical_shelters"]:
        assert s["county_fips"].startswith("13")
        assert s["seats"] > 0
        assert s["generator"] in FLAGS
        assert set(s["in_surge"]) <= {1, 2, 3, 4, 5}
    for d in sites["dialysis_centers"]:
        assert d["stations"] > 0
        assert d["late_shift"] in FLAGS
        assert set(d["in_surge"]) <= {1, 2, 3, 4, 5}


def test_surge_categories_nest():
    sites = load("sites.json")
    for d in sites["medical_shelters"] + sites["dialysis_centers"]:
        cats = d["in_surge"]
        if cats:
            assert cats == list(range(min(cats), 6))


def test_surge_zones_small_and_complete():
    path = DATA / "surge_zones.geojson"
    assert path.stat().st_size < 1_500_000
    zones = json.loads(path.read_text())
    assert [f["properties"]["category"] for f in zones["features"]] == [1, 2, 3, 4, 5]


def test_facility_beds_cover_every_county():
    beds = load("facility_beds.json")
    assert len(beds["counties"]) == 159
    assert beds["unjoined_nursing_homes"] == 0
    assert sum(v["nursing_home_beds"] for v in beds["counties"].values()) > 0
    for row in beds["counties"].values():
        assert set(row) == {
            "nursing_home_beds",
            "nursing_homes",
            "assisted_living_beds",
            "assisted_living_homes",
        }


def test_allocate_shares_a_site_pro_rata():
    from readiness_agent.scenario.build.build_season import allocate

    demand = np.array([[30.0, 10.0, 5.0]])
    capacity = np.array([[20.0, 100.0]])
    reach = np.array([[1.0, 0.0], [1.0, 0.0], [0.0, 1.0]])
    covered = allocate(demand, capacity, reach)
    np.testing.assert_allclose(covered, [[15.0, 5.0, 5.0]])


def test_worst_per_season_takes_the_max_event():
    from readiness_agent.scenario.build.build_season import worst_per_season

    values = {"x": np.array([[1.0, 0.0], [3.0, 2.0]])}
    out = worst_per_season(values, np.array([1.0, 1.0]), np.random.default_rng(0), 5000)
    assert out["x"].shape == (5000, 2)
    assert set(np.unique(out["x"][:, 0])) <= {0.0, 1.0, 3.0}
    assert abs((out["x"][:, 0] == 0).mean() - np.exp(-2)) < 0.03


def test_poisson_quantile():
    from readiness_agent.scenario.build.build_season import poisson_quantile

    assert poisson_quantile(0.0, 0.9) == 0
    assert poisson_quantile(2.0, 0.1) == 0
    assert poisson_quantile(2.0, 0.9) == 4


def test_season_backtest_shape():
    bt = load("season_backtest.json")
    assert bt["window"] == [2018, 2025]
    assert bt["counties"] == len(bt["rows"]) == 159
    inside = sum(r["inside"] for r in bt["rows"]) / len(bt["rows"])
    assert abs(inside - bt["share_inside"]) < 1e-3
    for r in bt["rows"]:
        assert r["p10"] <= r["p90"]
        assert r["inside"] == (r["p10"] <= r["observed"] <= r["p90"])
