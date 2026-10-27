"""Tool output shaping, with BigQuery replaced by fakes (tasks T068, T078). No credentials needed."""

import json

import pytest

from readiness_agent import evacuation_tools as tools
from readiness_agent.map_data import shelter_record


def shelter_row(sid, cap=200, wc=None, gen=None, fips="13157", name=None):
    return {
        "shelter_id": sid, "shelter_name": name or f"Shelter {sid}", "address_1": "1 Main St",
        "city": "Commerce", "zip": "30529", "county_fips": fips, "county_name": "Jackson",
        "county_parish": "JACKSON", "latitude": 34.2, "longitude": -83.4,
        "evacuation_capacity": cap, "post_impact_capacity": None, "usage": "EVAC",
        "wheelchair_accessible": wc, "generator_onsite": gen, "is_medical": False,
        "population_code": "GEN", "in_surge_slosh_area": None,
    }


@pytest.fixture
def fake_bq(monkeypatch):
    calls = []
    rows = {"value": []}

    def run(sql, params=None):
        calls.append((sql, {p.name: getattr(p, "value", getattr(p, "values", None)) for p in params or []}))
        return rows["value"]

    monkeypatch.setattr(tools, "_run_query", run)
    return calls, rows


def test_assess_shelter_accessibility_uses_county_fips_and_returns_ids(fake_bq):
    calls, rows = fake_bq
    rows["value"] = [shelter_row("a", wc=None), shelter_row("b", wc=True), shelter_row("c", wc=False)]
    out = tools.assess_shelter_accessibility(county_fips="13157")
    sql, params = calls[0]
    assert params["county_fips"] == "13157"
    assert "county_fips = @county_fips" in sql
    assert all(s["shelter_id"] and s["county_fips"] == "13157" for s in out["shelters"])


def test_unrecorded_is_never_no(fake_bq):
    _, rows = fake_bq
    rows["value"] = [shelter_row("a", wc=None), shelter_row("b", wc=None), shelter_row("c", wc=False)]
    out = tools.assess_shelter_accessibility(county_fips="13157")
    assert out["shelters"][0]["wheelchair_accessible"] == "UNRECORDED"
    assert out["wheelchair"] == {"yes": 0, "no": 1, "unrecorded": 2}


def test_suspect_capacity_flagged_and_ranked_as_zero_in_sql(fake_bq):
    calls, rows = fake_bq
    rows["value"] = [shelter_row("a", cap=270135, name="Commerce High School")]
    out = tools.assess_shelter_accessibility(county_fips="13157")
    assert "suspect_capacity" in out["shelters"][0]["quality_flags"]
    assert "evacuation_capacity > 100000, 0" in calls[0][0]


def test_power_counties_have_county_fips(fake_bq):
    calls, rows = fake_bq
    rows["value"] = [{"county": "Chatham", "state": "GA", "power_dependent_dme": 5000, "county_fips": "13051"}]
    out = tools.find_power_dependent_counties(county_fips="13051")
    assert "fips_code AS county_fips" in calls[0][0]
    assert calls[0][1]["county_fips"] == "13051"
    assert out["counties"][0]["county_fips"] == "13051"


def test_get_shelters_caps_ids_and_preserves_order(fake_bq):
    calls, rows = fake_bq
    with pytest.raises(ValueError):
        tools.get_shelters([str(i) for i in range(26)])
    rows["value"] = [shelter_row("b"), shelter_row("a"), shelter_row("c")]
    out = tools.get_shelters(["c", "a", "b"])
    assert [s["shelter_id"] for s in out["shelters"]] == ["c", "a", "b"]
    assert calls[-1][1]["ids"] == ["c", "a", "b"]
    # shelters_clean.shelter_id is INT64; string ids must be compared against a cast.
    assert "CAST(shelter_id AS STRING) IN UNNEST(@ids)" in calls[-1][0]


def test_get_shelters_empty_makes_no_query(fake_bq):
    calls, _ = fake_bq
    assert tools.get_shelters([])["shelters"] == []
    assert calls == []


def test_check_shelter_google_maps_uses_coordinates_and_returns_live_listing(monkeypatch):
    monkeypatch.setenv("GOOGLE_MAPS_API_KEY", "test-key")
    monkeypatch.setattr(
        tools,
        "get_shelters",
        lambda ids: {
            "shelters": [
                {
                    "shelter_id": ids[0],
                    "name": "Jackson County High School",
                    "address": "1660 Winder Highway, Jefferson, 30549",
                    "county_name": "Jackson",
                    "lat": 34.2,
                    "lon": -83.4,
                }
            ]
        },
    )
    requests = []

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *_):
            return None

        def read(self):
            return json.dumps({
                "places": [{
                    "id": "place-1",
                    "displayName": {"text": "Jackson County High School"},
                    "formattedAddress": "1660 Winder Hwy, Jefferson, GA",
                    "location": {"latitude": 34.2001, "longitude": -83.4001},
                    "businessStatus": "OPERATIONAL",
                    "currentOpeningHours": {"openNow": False},
                    "googleMapsUri": "https://maps.google.com/?cid=1",
                }]
            }).encode()

    def fake_urlopen(request, timeout):
        requests.append((request, timeout))
        return Response()

    monkeypatch.setattr(tools.urllib.request, "urlopen", fake_urlopen)
    result = tools.check_shelter_google_maps("363507")

    request, timeout = requests[0]
    request_body = json.loads(request.data)
    assert request.full_url == tools.GOOGLE_PLACES_TEXT_SEARCH_URL
    assert request.get_header("X-goog-api-key") == "test-key"
    assert request_body["locationBias"]["circle"]["center"] == {
        "latitude": 34.2,
        "longitude": -83.4,
    }
    assert timeout == 15
    assert result["shelter_id"] == "363507"
    assert result["candidates"][0]["distance_m"] == 14
    assert result["candidates"][0]["business_status"] == "OPERATIONAL"
    assert result["candidates"][0]["opening_hours_status"] == "closed_now"
    assert "not emergency shelter operations" in result["limitation"]


def test_check_shelter_google_maps_requires_api_key(monkeypatch):
    monkeypatch.delenv("GOOGLE_MAPS_API_KEY", raising=False)
    result = tools.check_shelter_google_maps("363507")
    assert result["status"] == "error" and "GOOGLE_MAPS_API_KEY" in result["message"]
    assert result["candidates"] == [] and "Google Maps" in result["source"]


def test_check_shelter_google_maps_returns_no_match_without_claiming_closed(monkeypatch):
    monkeypatch.setenv("GOOGLE_MAPS_API_KEY", "test-key")
    monkeypatch.setattr(
        tools,
        "get_shelters",
        lambda _: {
            "shelters": [{
                "shelter_id": "363507",
                "name": "Jackson County High School",
                "address": "1660 Winder Highway",
                "county_name": "Jackson",
                "lat": 34.2,
                "lon": -83.4,
            }]
        },
    )

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *_):
            return None

        def read(self):
            return b'{"places": []}'

    monkeypatch.setattr(tools.urllib.request, "urlopen", lambda *_args, **_kwargs: Response())
    result = tools.check_shelter_google_maps("363507")
    assert result["candidates"] == []
    assert "ambiguous or missing match is unknown" in result["limitation"]


def test_vulnerable_tracts_map_sentinel_to_none(fake_bq):
    calls, rows = fake_bq
    rows["value"] = [{"tract_id": "13051000100", "county_fips": "13051", "households_no_vehicle": 40,
                      "pct_no_vehicle": 12.0, "pct_age_65_plus": -999, "pct_disability": -999}]
    out = tools.find_vulnerable_tracts(county_fips="13051")
    assert out["tracts"][0]["pct_disability"] is None
    assert out["tracts"][0]["pct_age_65_plus"] is None
    assert out["tracts"][0]["pct_no_vehicle"] == 12.0
    assert calls[0][1]["county_fips"] == "13051"


def test_every_result_names_its_table(fake_bq):
    _, rows = fake_bq
    rows["value"] = []
    for result, table in [
        (tools.assess_shelter_accessibility(county_fips="13051"), "shelters_clean"),
        (tools.get_shelters(["x"]), "shelters_clean"),
        (tools.find_vulnerable_tracts(county_fips="13051"), "vulnerability_tracts_clean"),
        (tools.find_power_dependent_counties(county_fips="13051"), "power_dependent_counties_clean"),
    ]:
        assert table in result["source"]


def test_record_live_check_validates_status():
    with pytest.raises(ValueError):
        tools.record_live_check("a", "gone")
    out = tools.record_live_check("a", "renamed", place_id="p1")["live_check"]
    assert out["shelter_id"] == "a" and out["status"] == "renamed" and out["place_id"] == "p1"
    assert out["checked_at"]


def test_readiness_brief_counts_what_it_could_not_tell(fake_bq, monkeypatch):
    _, rows = fake_bq
    monkeypatch.setattr(tools, "identify_risky_shelters", lambda **kw: {"risky_shelters": []})
    rows["value"] = [shelter_row("a", wc=None, gen=None), shelter_row("b", wc=True, gen=None)]
    brief = tools.build_readiness_brief("GA", county_fips="13157")
    cnt = brief["could_not_tell"]
    assert cnt["wheelchair_unrecorded"] == 1
    assert cnt["generator_unrecorded"] == 2
    assert cnt["shelters_considered"] == 2
    assert "shelters_clean" in brief["sources"]["shelters_to_verify"]


def test_readiness_brief_requires_a_county():
    with pytest.raises(ValueError):
        tools.build_readiness_brief("GA")


def test_surge_fallback_sql_prefers_registry_and_names_the_source(monkeypatch):
    monkeypatch.setattr(tools, "_surge_fallback_exists", lambda: True)
    sql = tools._shelters_with_surge_fallback()
    # A recorded FEMA value is kept; NOAA's value is used only when the registry is NULL.
    assert "COALESCE(SAFE_CAST(s.in_surge_slosh_area AS BOOL), f.in_surge_fallback)" in sql
    assert "'noaa_slosh'" in sql and "'registry'" in sql
    assert "shelter_surge_noaa_clean" in sql
    assert "LEFT JOIN" in sql  # shelters outside the lookup stay in, unrecorded


def test_missing_fallback_table_leaves_registry_unchanged(monkeypatch):
    monkeypatch.setattr(tools, "_surge_fallback_exists", lambda: False)
    sql = tools._shelters_with_surge_fallback()
    assert "shelter_surge_noaa_clean" not in sql
    assert "'registry' AS in_surge_source" in sql


def test_risky_shelters_read_the_fallback_and_filter_by_county_fips(monkeypatch, fake_bq):
    calls, _ = fake_bq
    monkeypatch.setattr(tools, "_surge_fallback_exists", lambda: True)
    tools.identify_risky_shelters(state="GA", county_fips="13051", limit=1)
    sql, params = calls[0]
    assert "shelter_surge_noaa_clean" in sql and "surge_from_noaa_count" in sql
    assert "s.county_fips = @county_fips" in sql
    assert params["county_fips"] == "13051"


def test_shelter_tool_records_fill_surge_from_noaa_and_mark_it(fake_bq, monkeypatch):
    _, rows = fake_bq
    lookup = {"a": {"status": "inundated", "first_category": "2"}}
    monkeypatch.setattr(tools, "shelter_record", lambda r: shelter_record(r, lookup))
    rows["value"] = [shelter_row("a"), shelter_row("b")]
    out = tools.assess_shelter_accessibility(county_fips="13157")
    a, b = out["shelters"]
    assert (a["in_surge_slosh_area"], a["in_surge_source"]) == ("YES", "noaa_slosh")
    assert (b["in_surge_slosh_area"], b["in_surge_source"]) == ("UNRECORDED", "registry")
