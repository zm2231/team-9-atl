import math
from dataclasses import dataclass
from itertools import pairwise

EARTH_KM = 6371.0
NM_KM = 1.852


@dataclass(frozen=True)
class TrackPoint:
    hour: float
    lat: float
    lon: float
    vmax_kt: float
    rmw_km: float
    r34_km: float


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    a = math.sin((p2 - p1) / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(math.radians(lon2 - lon1) / 2) ** 2
    return 2 * EARTH_KM * math.asin(min(1.0, math.sqrt(a)))


def wind_at(p: TrackPoint, dist_km: float) -> float:
    if p.vmax_kt <= 0:
        return 0.0
    rmw = max(p.rmw_km, 10.0)
    if dist_km <= rmw:
        return p.vmax_kt * dist_km / rmw
    if p.vmax_kt > 34 and p.r34_km > rmw:
        x = math.log(p.vmax_kt / 34.0) / math.log(p.r34_km / rmw)
    else:
        x = 0.5
    return p.vmax_kt * (rmw / dist_km) ** x


def county_exposure(track: list[TrackPoint], lat: float, lon: float) -> dict[str, float]:
    peak = 0.0
    h34 = h50 = h64 = 0.0
    dmin = float("inf")
    first34 = None
    for i, p in enumerate(track):
        d = haversine_km(lat, lon, p.lat, p.lon)
        dmin = min(dmin, d)
        w = wind_at(p, d)
        peak = max(peak, w)
        step = track[i + 1].hour - p.hour if i + 1 < len(track) else 0.0
        if w >= 34:
            h34 += step
            if first34 is None:
                first34 = p.hour
        if w >= 50:
            h50 += step
        if w >= 64:
            h64 += step
    return {
        "peak_wind_kt": peak,
        "hours_34kt": h34,
        "hours_50kt": h50,
        "hours_64kt": h64,
        "min_dist_km": dmin,
        "first_34kt_hour": first34 if first34 is not None else float("nan"),
    }


def interpolate_hourly(points: list[TrackPoint]) -> list[TrackPoint]:
    out: list[TrackPoint] = []
    for a, b in pairwise(points):
        span = b.hour - a.hour
        if span <= 0:
            continue
        steps = max(1, round(span))
        for k in range(steps):
            f = k / steps
            out.append(TrackPoint(
                hour=a.hour + f * span,
                lat=a.lat + f * (b.lat - a.lat),
                lon=a.lon + f * (b.lon - a.lon),
                vmax_kt=a.vmax_kt + f * (b.vmax_kt - a.vmax_kt),
                rmw_km=a.rmw_km + f * (b.rmw_km - a.rmw_km),
                r34_km=a.r34_km + f * (b.r34_km - a.r34_km),
            ))
    if points:
        out.append(points[-1])
    return out
