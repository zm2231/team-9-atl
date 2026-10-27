import pytest

from readiness_agent import evacuation_tools as tools
from readiness_agent import readiness_brief


def shelter(sid, wc=None, gen=None, surge=None, flood=None, usage="EVAC", cap=200.0):
    return {"shelter_id": sid, "shelter_name": f"S{sid}", "address_1": "1 Main", "city": "X",
            "zip": "31401", "county_fips": "13051", "county_name": "Chatham", "latitude": 32.0,
            "longitude": -81.1, "evacuation_capacity": cap, "post_impact_capacity": None,
            "usage": usage, "wheelchair_accessible": wc, "generator_onsite": gen, "is_medical": None,
            "population_code": None, "in_surge_slosh_area": surge, "in_100_yr_floodplain": flood}


@pytest.fixture
def fake(monkeypatch):
    calls = []
    data = {
        "tracts": [
            {"geo_id": "t1", "total_pop": 3000.0, "households_no_vehicle": 400.0, "pop_65_plus": 300.0,
             "group_quarters_pop": 0.0, "pct_disability": 21.4, "pct_mobility": 30.2, "pct_selfcare": -999,
             "lat": 32.0, "lon": -81.1},
            {"geo_id": "t2", "total_pop": 2500.0, "households_no_vehicle": 50.0, "pop_65_plus": None,
             "group_quarters_pop": 12.0, "pct_disability": -999, "lat": 32.1, "lon": -81.2},
            {"geo_id": "t3", "total_pop": 900.0, "households_no_vehicle": 0.0, "pop_65_plus": 10.0,
             "group_quarters_pop": 0.0, "pct_disability": 5.0, "lat": 32.2, "lon": -81.3},
        ],
        "reach": [
            {"geo_id": "t1", "within_reach": 3, "wheelchair_yes_within_reach": 1,
             "wheelchair_no_within_reach": 1, "wheelchair_unrecorded_within_reach": 1, "nearest_km": 1.2},
            {"geo_id": "t2", "within_reach": 1, "wheelchair_yes_within_reach": 0,
             "wheelchair_no_within_reach": 0, "wheelchair_unrecorded_within_reach": 1, "nearest_km": 9.5},
        ],
        "shelters": [shelter("a", wc=True, surge=True), shelter("b", flood=True), shelter("c", wc=False, gen=True)],
        "facilities": [{"ccn": "115641", "name": "Riverview", "city": "Savannah", "beds": 284.0,
                        "coastal_flood_exposed": True, "cfld_share": 0.0020497},
                       {"ccn": "115339", "name": "Pruitt", "city": "Savannah", "beds": 140.0,
                        "coastal_flood_exposed": None}],
        "destinations": [shelter("a", wc=True) | {"serves_tracts": ["t1", "t2"], "nearest_km": 1.2}],
    }

    def run(sql, params=None):
        calls.append(sql)
        if "ARRAY_AGG(t.geo_id" in sql:
            return data["destinations"]
        if "wheelchair_yes_within_reach" in sql:
            return data["reach"]
        if "cms_certification_number_ccn" in sql:
            return data["facilities"]
        if "power_dependent_counties" in sql:
            return [{"county_fips": "13051", "power_dependent_dme": 2328.0}]
        if "households_no_vehicle" in sql:
            return data["tracts"]
        return data["shelters"]

    monkeypatch.setattr(tools, "_run_query", run)
    monkeypatch.setattr(readiness_brief, "shelter_record",
                        lambda r: tools.shelter_record(r, surge_lookup={}))
    return calls


def test_four_segments_in_challenge_order(fake):
    brief = readiness_brief.build_readiness_brief("13051")
    assert list(brief)[1:] == ["who_cannot_leave", "where_they_would_go", "what_to_fix", "could_not_tell"]


def test_who_cannot_leave_ranks_tracts_with_reasons_and_lists_facilities(fake):
    who = readiness_brief.build_readiness_brief("13051")["who_cannot_leave"]
    assert [t["geo_id"] for t in who["tracts"]] == ["t1", "t2", "t3"]
    assert who["tracts"][0]["reasons"] == ["400 households without a vehicle", "21% with a disability",
                                           "30% with a mobility difficulty (modeled)", "300 residents aged 65+"]
    assert who["tracts"][1]["reasons"] == ["50 households without a vehicle", "12 in group quarters"]
    assert who["facilities"][0]["certified_beds"] == 284
    assert who["facilities"][0]["coastal_flood_exposed"] == "YES"
    assert who["facilities"][0]["tract_coastal_flood_share_pct"] == 0.2
    assert "0.2% of residents exposed to coastal flooding" in who["facilities"][0]["reasons"][1]
    assert "not recorded" in who["facilities"][0]["reasons"][2]
    assert who["facilities"][1]["coastal_flood_exposed"] == "UNRECORDED"
    assert len(who["facilities"][1]["reasons"]) == 2
    assert who["power_dependent_residents"] == 2328


def test_destinations_carry_flags_and_say_they_are_not_yet_verified(fake):
    where = readiness_brief.build_readiness_brief("13051")["where_they_would_go"]
    d = where["destinations"][0]
    assert d["shelter_id"] == "a" and d["wheelchair_accessible"] == "YES" and d["serves_tracts"] == ["t1", "t2"]
    assert "Google Maps" in where["live_check"] and "16 km" in where["reachable"]


def test_what_to_fix_lists_the_three_gaps(fake):
    fix = readiness_brief.build_readiness_brief("13051")["what_to_fix"]
    gaps = fix["tracts_without_recorded_accessible_shelter_in_reach"]
    assert [t["geo_id"] for t in gaps] == ["t2"]
    assert "unknown, not no" in gaps[0]["gap"] and gaps[0]["wheelchair_unrecorded_within_reach"] == 1
    assert {s["shelter_id"] for s in fix["shelters_in_surge_or_flood_zone"]} == {"a", "b"}
    assert fix["facilities_without_recorded_generator"]["count"] == 2
    flood = fix["facilities_in_coastal_flood_tract"]
    assert [f["ccn"] for f in flood["facilities"]] == ["115641"]
    assert "care_facilities_flow_staging" in flood["source"]


def test_could_not_tell_counts_the_whole_county(fake):
    cnt = readiness_brief.build_readiness_brief("13051", destination_limit=1)["could_not_tell"]
    assert cnt["shelters_in_county"] == 3
    assert cnt["wheelchair_unrecorded"] == 1
    assert cnt["generator_unrecorded"] == 2
    assert cnt["hurricane_rating_unrecorded"] == 3
    assert cnt["nursing_home_generator_unrecorded"] == 2
    assert cnt["nursing_home_coastal_flood_unrecorded"] == 1
    assert cnt["medical_unrecorded"] == 3


def test_county_is_required():
    with pytest.raises(ValueError):
        readiness_brief.build_readiness_brief("")
