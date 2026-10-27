import json
from pathlib import Path

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
