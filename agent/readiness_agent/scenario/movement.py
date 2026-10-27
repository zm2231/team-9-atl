import json
import math
import os
from functools import cache
from pathlib import Path

DATA = Path(__file__).resolve().parent / "data"
ROUTES_URL = "https://routes.googleapis.com/distanceMatrix/v2:computeRouteMatrix"
FIELD_MASK = "originIndex,destinationIndex,duration,distanceMeters,condition"
TIMEOUT_S = 8
STRAIGHT_LINE_KMH = 60.0
STRAIGHT_LINE_DETOUR = 1.3
MAX_MULTIPLIER = 4.0
EARTH_KM = 6371.0


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    a = (math.sin((p2 - p1) / 2) ** 2
         + math.cos(p1) * math.cos(p2) * math.sin(math.radians(lon2 - lon1) / 2) ** 2)
    return 2 * EARTH_KM * math.asin(min(1.0, math.sqrt(a)))


def _straight_line(origin: tuple[float, float], dest: tuple[float, float]) -> dict:
    km = haversine_km(*origin, *dest)
    return {"minutes": km / STRAIGHT_LINE_KMH * 60 * STRAIGHT_LINE_DETOUR, "km": km,
            "status": "straight_line"}


def _waypoint(lat: float, lon: float) -> dict:
    return {"waypoint": {"location": {"latLng": {"latitude": lat, "longitude": lon}}}}


def _session():
    key = os.getenv("ROUTES_API_KEY")
    if key:
        import requests

        session = requests.Session()
        session.headers["X-Goog-Api-Key"] = key
        return session
    import google.auth
    from google.auth.transport.requests import AuthorizedSession

    credentials, project = google.auth.default(
        scopes=["https://www.googleapis.com/auth/cloud-platform"])
    session = AuthorizedSession(credentials)
    session.headers["X-Goog-User-Project"] = os.getenv("GOOGLE_CLOUD_PROJECT") or project or ""
    return session


def _route_matrix(origin: tuple[float, float], dests: list[tuple[float, float]],
                  departure_time: str | None) -> dict[int, dict]:
    body = {
        "origins": [_waypoint(*origin)],
        "destinations": [_waypoint(*d) for d in dests],
        "travelMode": "DRIVE",
        "routingPreference": "TRAFFIC_AWARE" if departure_time else "TRAFFIC_UNAWARE",
    }
    if departure_time:
        body["departureTime"] = departure_time
    session = _session()
    session.headers["X-Goog-FieldMask"] = FIELD_MASK
    response = session.post(ROUTES_URL, json=body, timeout=TIMEOUT_S)
    response.raise_for_status()
    out = {}
    for element in response.json():
        if element.get("condition") != "ROUTE_EXISTS" or "duration" not in element:
            continue
        seconds = float(str(element["duration"]).rstrip("s"))
        out[element.get("destinationIndex", 0)] = {
            "minutes": seconds / 60, "km": element.get("distanceMeters", 0) / 1000,
            "status": "live"}
    return out


def drive_times(origin_latlon: tuple[float, float], dests: list[tuple[float, float]],
                departure_time: str | None = None) -> list[dict]:
    if not dests:
        return []
    try:
        live = _route_matrix(origin_latlon, dests, departure_time)
    except Exception:  # noqa: BLE001
        live = {}
    return [live.get(i) or _straight_line(origin_latlon, d) for i, d in enumerate(dests)]


@cache
def _county_centroids() -> dict[str, tuple[float, float]]:
    path = DATA / "counties.json"
    if not path.exists():
        return {}
    return {c["county_fips"]: (c["lat"], c["lon"]) for c in json.loads(path.read_text())}


@cache
def _corridor_vc() -> dict[tuple[str, str, str], float]:
    rows = json.loads((DATA / "corridor_vc.json").read_text())
    return {(r["corridor"], r["origin"], r["case"]): float(r["volume_to_capacity"]) for r in rows}


def corridor_for(origin_county_fips: str, dest_latlon: tuple[float, float],
                 origin_latlon: tuple[float, float] | None = None) -> str | None:
    origin = origin_latlon or _county_centroids().get(origin_county_fips)
    if origin is None:
        return None
    (olat, olon), (dlat, dlon) = origin, dest_latlon
    # Coast-to-coast northbound trips use I-95; inland from the coast I-16; south Georgia north I-75.
    if olon >= -81.9 and dlon >= -82.2 and dlat > olat + 0.3:
        return "I-95"
    if olon >= -82.6 and olat <= 32.6 and dlon < olon - 0.5:
        return "I-16"
    if olon < -82.6 and olat <= 32.85 and dlat > olat + 0.3:
        return "I-75 S"
    return None


def delay_multiplier(corridor: str | None, origin_class: str, case: str) -> float:
    vc = _corridor_vc().get((corridor, origin_class, case)) if corridor else None
    if vc is None:
        return 1.0
    return min(MAX_MULTIPLIER, 1 + 0.15 * vc**4)
