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


def test_receiving_sites_rows(session):
    session(FakeResponse([
        {"destinationIndex": 0, "duration": "7200s", "distanceMeters": 150000,
         "condition": "ROUTE_EXISTS"},
    ]))
    county = {"county_fips": "13051", "lat": SAVANNAH[0], "lon": SAVANNAH[1]}
    sites = [
        {"shelter_id": "S1", "name": "Macon", "county_fips": "13021", "lat": MACON[0],
         "lon": MACON[1], "seats": 400, "generator": True},
        {"ccn": "112233", "name": "Dublin Dialysis", "county_fips": "13175", "lat": DUBLIN[0],
         "lon": DUBLIN[1], "stations": 20, "late_shift": None},
        {"shelter_id": "S2", "name": "In surge", "county_fips": "13051", "lat": 32.0,
         "lon": -81.1, "seats": 100, "generator": None},
    ]
    rows = receiving.receiving_sites(county, sites, [True, True, False], "florida_peninsula",
                                     ts_arrival_h=10)
    assert {r.get("shelter_id") or r.get("ccn") for r in rows} == {"S1", "112233"}
    by_id = {r.get("shelter_id") or r.get("ccn"): r for r in rows}
    assert by_id["112233"]["drive_minutes"] == {"value": 120, "status": "live"}
    assert by_id["S1"]["drive_minutes"]["status"] == "straight_line"
    assert by_id["S1"]["generator"] == "YES"
    assert by_id["112233"]["late_shift"] == "UNRECORDED"
    assert set(by_id["S1"]["evacuation_delay_minutes"]) == {"low", "base", "high"}
    assert all(r["county_fips"] for r in rows)
    assert by_id["S1"]["arrives_before_ts_winds"] is True
    gap = receiving.shortfall(1000, rows)
    assert gap == {"seekers": 1000, "generator_recorded_seats_in_time": 400, "uncovered": 600}
