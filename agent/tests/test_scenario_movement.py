import json

import pytest

from readiness_agent.scenario import movement, receiving


class FakeResponse:
    def __init__(self, payload, status=200):
        self.payload = payload
        self.status = status

    def raise_for_status(self):
        if self.status >= 400:
            raise movement_error()

    def json(self):
        return self.payload


def movement_error():
    import requests

    return requests.HTTPError("403")


class FakeSession:
    def __init__(self, response):
        self.headers = {}
        self.response = response
        self.calls = []

    def post(self, url, json, timeout):
        self.calls.append((url, json, timeout))
        if isinstance(self.response, Exception):
            raise self.response
        return self.response


@pytest.fixture
def session(monkeypatch):
    holder = {}

    def install(response):
        holder["s"] = FakeSession(response)
        monkeypatch.setattr(movement, "_session", lambda: holder["s"])
        return holder["s"]

    return install


SAVANNAH = (32.08, -81.09)
MACON = (32.84, -83.63)
DUBLIN = (32.54, -82.90)


def test_live_path_uses_route_matrix(session):
    s = session(FakeResponse([
        {"originIndex": 0, "destinationIndex": 1, "duration": "3600s", "distanceMeters": 90000,
         "condition": "ROUTE_EXISTS"},
        {"originIndex": 0, "destinationIndex": 0, "duration": "9000s", "distanceMeters": 270000,
         "condition": "ROUTE_EXISTS"},
    ]))
    out = movement.drive_times(SAVANNAH, [MACON, DUBLIN])
    assert [r["status"] for r in out] == ["live", "live"]
    assert out[0]["minutes"] == pytest.approx(150)
    assert out[1]["km"] == pytest.approx(90)
    body = s.calls[0][1]
    assert body["routingPreference"] == "TRAFFIC_UNAWARE"
    assert s.calls[0][2] == movement.TIMEOUT_S
    assert s.headers["X-Goog-FieldMask"] == movement.FIELD_MASK


def test_departure_time_switches_to_traffic_aware(session):
    s = session(FakeResponse([]))
    movement.drive_times(SAVANNAH, [MACON], departure_time="2026-09-20T12:00:00Z")
    assert s.calls[0][1]["routingPreference"] == "TRAFFIC_AWARE"
    assert s.calls[0][1]["departureTime"] == "2026-09-20T12:00:00Z"


def test_errors_fall_back_to_straight_line(session):
    session(FakeResponse({}, status=403))
    out = movement.drive_times(SAVANNAH, [MACON])
    assert out[0]["status"] == "straight_line"
    km = movement.haversine_km(*SAVANNAH, *MACON)
    assert out[0]["minutes"] == pytest.approx(km / 60 * 60 * 1.3)


def test_network_exception_and_missing_element_fall_back(session):
    session(OSError("timeout"))
    assert movement.drive_times(SAVANNAH, [MACON])[0]["status"] == "straight_line"
    session(FakeResponse([{"destinationIndex": 0, "condition": "ROUTE_NOT_FOUND"}]))
    assert movement.drive_times(SAVANNAH, [MACON])[0]["status"] == "straight_line"


def test_auth_failure_falls_back(monkeypatch):
    def boom():
        raise RuntimeError("no credentials")

    monkeypatch.setattr(movement, "_session", boom)
    assert movement.drive_times(SAVANNAH, [MACON])[0]["status"] == "straight_line"


def test_empty_destinations():
    assert movement.drive_times(SAVANNAH, []) == []


def test_multiplier_formula_and_cap():
    rows = {(r["corridor"], r["origin"], r["case"]): r["volume_to_capacity"]
            for r in json.loads((movement.DATA / "corridor_vc.json").read_text())}
    vc = rows[("I-75 S", "gulf", "base")]
    assert movement.delay_multiplier("I-75 S", "gulf", "base") == pytest.approx(
        min(4.0, 1 + 0.15 * vc**4))
    assert max(rows.values()) > 2
    assert all(movement.delay_multiplier(c, o, k) <= 4.0 for c, o, k in rows)
    assert movement.delay_multiplier("I-75 S", "carolinas", "base") == 1.0
    assert movement.delay_multiplier(None, "gulf", "base") == 1.0


def test_corridor_mapping():
    chatham = SAVANNAH
    lowndes = (30.83, -83.28)
    glynn = (31.21, -81.50)
    fulton = (33.79, -84.47)
    assert movement.corridor_for("13051", MACON, chatham) == "I-16"
    assert movement.corridor_for("13185", MACON, lowndes) == "I-75 S"
    assert movement.corridor_for("13127", (32.08, -81.09), glynn) == "I-95"
    assert movement.corridor_for("13121", (34.5, -84.9), fulton) is None
    assert movement.corridor_for("99999", MACON) is None


def test_receiving_sites_contract(session):
    session(FakeResponse([
        {"destinationIndex": 1, "duration": "7200s", "distanceMeters": 150000,
         "condition": "ROUTE_EXISTS"},
    ]))
    county = {"county_fips": "13051", "county_name": "Chatham", "lat": SAVANNAH[0],
              "lon": SAVANNAH[1]}
    sites = {
        "medical_shelters": [
            {"shelter_id": "S1", "name": "Macon", "county_fips": "13021", "lat": MACON[0],
             "lon": MACON[1], "seats": 400, "generator": "YES", "in_surge": []},
            {"shelter_id": "S2", "name": "Coastal", "county_fips": "13051", "lat": 32.0,
             "lon": -81.1, "seats": 100, "generator": "UNRECORDED", "in_surge": [2, 3, 4, 5]},
            {"shelter_id": "S3", "name": "Down county", "county_fips": "13029", "lat": 32.0,
             "lon": -81.4, "seats": 50, "generator": "YES", "in_surge": []},
        ],
        "dialysis_centers": [
            {"ccn": "112233", "name": "Dublin Dialysis", "county_fips": "13175",
             "lat": DUBLIN[0], "lon": DUBLIN[1], "stations": 20, "generator": "UNRECORDED",
             "in_surge": []},
        ],
    }
    out = receiving.receiving_sites(county, sites, {"13029"}, 3, "florida_peninsula", "base",
                                    10, relocation_share=0.2, power_dependent_at_risk=3000)
    rows = out["sites"]
    assert {r.get("shelter_id") or r.get("ccn") for r in rows} == {"S1", "112233"}
    by_id = {r.get("shelter_id") or r.get("ccn"): r for r in rows}
    assert by_id["112233"]["kind"] == "dialysis_centre"
    assert by_id["112233"]["drive_minutes"] == {"value": 120, "status": "live"}
    assert by_id["S1"]["drive_minutes"]["status"] == "straight_line"
    assert by_id["S1"]["kind"] == "medical_shelter" and by_id["S1"]["seats"] == 400
    assert set(by_id["S1"]["evacuation_delay_minutes"]) == {"low", "base", "high"}
    assert all(r["county_fips"] for r in rows)
    assert [r["drive_minutes"]["value"] for r in rows] == sorted(
        r["drive_minutes"]["value"] for r in rows)
    assert by_id["S1"]["arrives_before_ts_winds"] is True
    assert out["lacking_shelter"] == {"seeking_powered_seat": 600,
                                      "powered_seats_reachable": 400, "no_powered_seat": 200}
    assert out["needing_transport"] == {"cannot_arrive_in_time": 0}
    assert out["ignored_ids"] == []
    assert out["drive_time_source"] == "straight_line"


def test_surge_category_none_keeps_coastal_sites(session):
    session(OSError("offline"))
    county = {"county_fips": "13051", "lat": SAVANNAH[0], "lon": SAVANNAH[1]}
    sites = {"medical_shelters": [
        {"shelter_id": "S2", "name": "Coastal", "county_fips": "13051", "lat": 32.0,
         "lon": -81.1, "seats": 100, "generator": None, "in_surge": [1]}]}
    out = receiving.receiving_sites(county, sites, set(), None, "overland_west", "high", None,
                                    relocation_share=0.2, power_dependent_at_risk=0)
    assert out["sites"][0]["generator"] == "UNRECORDED"
    assert out["sites"][0]["arrives_before_ts_winds"] is None
    assert out["sites"][0]["evacuation_delay_minutes"] == {"low": 0, "base": 0, "high": 0}
    assert out["lacking_shelter"]["no_powered_seat"] == 0


def test_late_base_trip_needs_transport_not_shelter(session):
    session(FakeResponse([
        {"destinationIndex": 0, "duration": "7200s", "distanceMeters": 250000,
         "condition": "ROUTE_EXISTS"},
    ]))
    county = {"county_fips": "13051", "lat": SAVANNAH[0], "lon": SAVANNAH[1]}
    sites = {"medical_shelters": [
        {"shelter_id": "S1", "name": "Macon", "county_fips": "13021", "lat": MACON[0],
         "lon": MACON[1], "seats": 400, "generator": "YES", "in_surge": []}]}
    out = receiving.receiving_sites(county, sites, set(), 3, "florida_peninsula", "low", 3.0,
                                    relocation_share=0.3, power_dependent_at_risk=1000)
    row = out["sites"][0]
    assert row["corridor"] == "I-16"
    multiplier = movement.delay_multiplier("I-16", "florida_peninsula", "base")
    assert 120 * multiplier / 60 > 3.0 > 120 / 60
    assert row["evacuation_delay_minutes"]["base"] == round(120 * (multiplier - 1))
    assert row["arrives_before_ts_winds"] is False
    assert out["lacking_shelter"] == {"seeking_powered_seat": 300,
                                      "powered_seats_reachable": 400, "no_powered_seat": 0}
    assert out["needing_transport"] == {"cannot_arrive_in_time": 300}
    assert out["drive_time_source"] == "live"


def _shelter(sid, lat, lon, seats, generator):
    return {"shelter_id": sid, "name": sid, "county_fips": "13021", "lat": lat, "lon": lon,
            "seats": seats, "generator": generator, "in_surge": []}


SWITCH_SITES = {
    "medical_shelters": [
        _shelter("NEAR", 32.3, -81.5, 100, "YES"),
        _shelter("MID", 32.6, -82.5, 300, "UNRECORDED"),
        _shelter("FAR", MACON[0], MACON[1], 50, "YES"),
    ],
    "dialysis_centers": [
        {"ccn": "C1", "name": "C1", "county_fips": "13175", "lat": DUBLIN[0],
         "lon": DUBLIN[1], "stations": 20, "in_surge": []},
    ],
}
CHATHAM = {"county_fips": "13051", "lat": SAVANNAH[0], "lon": SAVANNAH[1]}


def _run(ts_arrival_h=None, seeking_base=1000.0, **switches):
    return receiving.receiving_sites(CHATHAM, SWITCH_SITES, set(), None, "gulf", "base",
                                     ts_arrival_h, relocation_share=0.2,
                                     power_dependent_at_risk=seeking_base, **switches)


def test_switched_off_site_is_not_returned_or_counted(session):
    session(OSError("offline"))
    base = _run()
    assert base["lacking_shelter"]["powered_seats_reachable"] == 150
    out = _run(sites_off=frozenset({"NEAR", "C1", "NOPE"}))
    ids = {r.get("shelter_id") or r.get("ccn") for r in out["sites"]}
    assert ids == {"MID", "FAR"}
    assert out["lacking_shelter"] == {"seeking_powered_seat": 200,
                                      "powered_seats_reachable": 50, "no_powered_seat": 150}
    assert out["ignored_ids"] == ["NOPE"]


def test_every_site_off_leaves_all_seekers_without_a_seat(session):
    session(OSError("offline"))
    off = frozenset({"NEAR", "MID", "FAR", "C1"})
    out = _run(sites_off=off)
    assert out["sites"] == []
    assert out["lacking_shelter"]["no_powered_seat"] == 200
    assert out["needing_transport"]["cannot_arrive_in_time"] == 0


def test_assumed_generator_adds_its_seats(session):
    session(OSError("offline"))
    out = _run(assume_generator=frozenset({"MID", "C1"}))
    mid = next(r for r in out["sites"] if r.get("shelter_id") == "MID")
    assert mid["generator"] == "UNRECORDED" and mid["generator_assumed"] is True
    assert not any(r["generator_assumed"] for r in out["sites"] if r is not mid)
    assert out["lacking_shelter"]["powered_seats_reachable"] == 150 + 300
    assert out["lacking_shelter"]["no_powered_seat"] == 0
    assert out["ignored_ids"] == ["C1"]


def test_blocks_when_everything_is_late_or_no_deadline(session):
    session(OSError("offline"))
    late = _run(ts_arrival_h=0.01)
    assert all(r["arrives_before_ts_winds"] is False for r in late["sites"])
    assert late["lacking_shelter"] == {"seeking_powered_seat": 200,
                                       "powered_seats_reachable": 150, "no_powered_seat": 50}
    assert late["needing_transport"] == {"cannot_arrive_in_time": 150}
    for ts in (None, float("nan")):
        out = _run(ts_arrival_h=ts)
        assert all(r["arrives_before_ts_winds"] is None for r in out["sites"])
        assert out["lacking_shelter"] == late["lacking_shelter"]
        assert out["needing_transport"] == {"cannot_arrive_in_time": 0}
