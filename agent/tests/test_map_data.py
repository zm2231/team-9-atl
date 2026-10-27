import json
from datetime import datetime, timezone
from pathlib import Path

import jsonschema
import pytest

from readiness_agent.map_data import SHELTERS_SQL, build_payload, to_flag

SCHEMA_PATH = (
    Path(__file__).resolve().parents[2]
    / "specs/001-georgia-shelter-map/contracts/map-data.schema.json"
)


def shelter(sid, fips="13157", cap=200, wc=None, gen=None, surge=None, med=False, pop_code="GEN",
            name=None, lat=34.2, lon=-83.4):
    return {
        "shelter_id": sid, "shelter_name": name or f"Shelter {sid}", "address_1": "1 Main St",
        "city": "Commerce", "zip": "30529", "county_fips": fips, "county_name": "Jackson",
        "county_parish": "JACKSON", "latitude": lat, "longitude": lon,
        "evacuation_capacity": cap, "post_impact_capacity": None, "usage": "EVAC",
        "wheelchair_accessible": wc, "generator_onsite": gen, "is_medical": med,
        "population_code": pop_code, "in_surge_slosh_area": surge,
    }


COUNTIES = [("13157", "Jackson"), ("13127", "Glynn"), ("13001", "Appling")]


@pytest.fixture
def payload():
    shelters = [
        shelter("a", cap=270135, name="Commerce High School", wc=True),
        shelter("b", cap=225112, name="Commerce Primary School"),
        shelter("c", cap=300, wc=False, gen=True),
        shelter("d", fips="13127", cap=150, surge=True),
        shelter("e", fips=None, cap=100, pop_code=None),  # coordinates outside any GA county
    ]
    tracts = [
        {"geo_id": "13157000100", "total_pop": 1000, "households_no_vehicle": 40,
         "pop_65_plus": 200, "pct_disability": 10.0},
        {"geo_id": "13157000200", "total_pop": 3000, "households_no_vehicle": 60,
         "pop_65_plus": 300, "pct_disability": -999},
        {"geo_id": "13127000100", "total_pop": 500, "households_no_vehicle": None,
         "pop_65_plus": 50, "pct_disability": 20.0},
    ]
    return build_payload(shelters, tracts, COUNTIES,
                         generated_at=datetime(2026, 10, 27, tzinfo=timezone.utc))


def county(payload, fips):
    return next(c for c in payload["counties"] if c["county_fips"] == fips)


def test_null_is_unrecorded_never_no():
    assert to_flag(None) == "UNRECORDED"
    assert to_flag(True) == "YES"
    assert to_flag(False) == "NO"


def test_shelter_flags_and_county_counts_keep_unrecorded_separate(payload):
    jackson = county(payload, "13157")
    assert jackson["wheelchair"] == {"yes": 1, "no": 1, "unrecorded": 1}
    assert jackson["in_surge"] == {"yes": 0, "no": 0, "unrecorded": 3}
    for s in payload["shelters"]:
        for key in ("wheelchair_accessible", "generator_onsite", "is_medical", "in_surge_slosh_area"):
            assert s[key] in ("YES", "NO", "UNRECORDED")


def test_is_medical_unrecorded_when_population_code_missing(payload):
    e = next(s for s in payload["shelters"] if s["shelter_id"] == "e")
    assert e["is_medical"] == "UNRECORDED"
    c = next(s for s in payload["shelters"] if s["shelter_id"] == "c")
    assert c["is_medical"] == "NO"


def test_suspect_capacity_excluded_from_total_and_named(payload):
    jackson = county(payload, "13157")
    assert jackson["capacity_total"]["value"] == 300
    assert jackson["capacity_total_incl_suspect"]["value"] == 270135 + 225112 + 300
    assert [x["name"] for x in jackson["capacity_excluded"]] == [
        "Commerce High School", "Commerce Primary School"]
    a = next(s for s in payload["shelters"] if s["shelter_id"] == "a")
    assert a["evacuation_capacity"] == 270135  # FEMA's value, never edited
    assert "suspect_capacity" in a["quality_flags"]


def test_location_disagrees_flagged_and_row_kept(payload):
    e = next(s for s in payload["shelters"] if s["shelter_id"] == "e")
    assert e["quality_flags"] == ["location_disagrees"]
    assert len(payload["shelters"]) == 5


def test_sentinel_minus_999_excluded_with_coverage(payload):
    jackson = county(payload, "13157")
    assert jackson["share_disability"]["value"] == pytest.approx(0.10)
    assert jackson["share_disability"]["coverage"] == "1 of 2 tracts"
    assert jackson["share_65_plus"]["value"] == pytest.approx(500 / 4000)
    assert jackson["households_no_vehicle"]["value"] == 100
    glynn = county(payload, "13127")
    assert glynn["households_no_vehicle"]["value"] is None
    assert glynn["households_no_vehicle"]["coverage"] == "0 of 1 tracts"


def test_zero_shelter_county_present(payload):
    appling = county(payload, "13001")
    assert appling["shelter_count"] == 0
    assert appling["capacity_total"]["value"] == 0
    assert appling["share_65_plus"]["value"] is None


def test_every_source_names_its_table(payload):
    for c in payload["counties"]:
        for key in ("capacity_total", "capacity_total_incl_suspect", "households_no_vehicle",
                    "share_65_plus", "share_disability"):
            src = c[key]["source"]
            assert "· shelters_clean" in src or "· vulnerability_tracts_clean" in src, src


def test_notes_are_counted(payload):
    notes = " ".join(payload["notes"])
    assert "3 of 5 shelters have no wheelchair-access record" in notes
    assert "Commerce High School" in notes


def test_payload_validates_against_contract(payload):
    schema = json.loads(SCHEMA_PATH.read_text())
    jsonschema.validate(json.loads(json.dumps(payload)), schema)


def test_no_personal_data_columns_selected():
    # FR-021: contact columns must never be queried.
    assert "org_poc" not in SHELTERS_SQL.lower()


SURGE = {
    "c": {"status": "inundated", "first_category": "3"},
    "d": {"status": "dry", "first_category": ""},
    "b": {"status": "dry", "first_category": ""},
}


@pytest.fixture
def surge_payload():
    shelters = [
        shelter("b", cap=300),                             # blank registry, NOAA dry
        shelter("c", cap=300),                             # blank registry, NOAA inundated
        shelter("d", fips="13127", cap=150, surge=True),   # registry yes, NOAA dry
        shelter("f", cap=100),                             # blank, not in the NOAA lookup
    ]
    return build_payload(shelters, [], COUNTIES, surge_lookup=SURGE,
                         generated_at=datetime(2026, 10, 27, tzinfo=timezone.utc))


def by_id(payload, sid):
    return next(s for s in payload["shelters"] if s["shelter_id"] == sid)


def test_blank_surge_filled_from_noaa_and_marked(surge_payload):
    c = by_id(surge_payload, "c")
    assert (c["in_surge_slosh_area"], c["in_surge_source"]) == ("YES", "noaa_slosh")
    assert c["surge_noaa"] == {"status": "inundated", "first_category": 3}
    b = by_id(surge_payload, "b")
    assert (b["in_surge_slosh_area"], b["in_surge_source"]) == ("NO", "noaa_slosh")
    f = by_id(surge_payload, "f")
    assert (f["in_surge_slosh_area"], f["in_surge_source"]) == ("UNRECORDED", "registry")
    assert "surge_noaa" not in f


def test_registry_surge_wins_and_disagreement_is_flagged(surge_payload):
    d = by_id(surge_payload, "d")
    assert (d["in_surge_slosh_area"], d["in_surge_source"]) == ("YES", "registry")
    assert "surge_disagrees" in d["quality_flags"]
    assert any("contradict" in n for n in surge_payload["notes"])


def test_levee_area_is_never_filled():
    payload = build_payload([shelter("x")], [], COUNTIES,
                            surge_lookup={"x": {"status": "levee", "first_category": ""}})
    x = by_id(payload, "x")
    assert (x["in_surge_slosh_area"], x["in_surge_source"]) == ("UNRECORDED", "registry")


def test_county_counts_say_how_many_came_from_noaa(surge_payload):
    jackson = county(surge_payload, "13157")
    assert jackson["in_surge"] == {"yes": 1, "no": 1, "unrecorded": 1}
    assert jackson["in_surge_from_noaa"] == 2
    assert any("2 of 4 shelters had no surge record" in n for n in surge_payload["notes"])


def test_surge_payload_validates_against_contract(surge_payload):
    schema = json.loads(SCHEMA_PATH.read_text())
    jsonschema.validate(json.loads(json.dumps(surge_payload)), schema)


def test_committed_surge_csv_covers_every_shelter():
    from readiness_agent.map_data import load_surge_lookup
    lookup = load_surge_lookup()
    assert len(lookup) == 1792
    assert {r["status"] for r in lookup.values()} <= {"inundated", "dry", "levee"}
