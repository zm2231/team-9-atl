import math
from dataclasses import dataclass
from functools import cache

import numpy as np

from . import data
from .windfield import EARTH_KM, TrackPoint, interpolate_hourly

CATEGORY_KT = {0: 50.0, 1: 73.0, 2: 89.0, 3: 104.0, 4: 124.0, 5: 145.0}
MATCH_KM = 300.0
HEADING_DEG = 45.0
INTENSITY_KT = 20.0
NEAR_GA_KM = 300.0
LAND_KM = 35.0
DECAY_BASE_KT = 26.7
DECAY_RATE_PER_H = 0.095
LANDFALL_FACTOR = 0.9
PATTERN_TRACK_KM = 150.0
PATTERN_RANGE_Q = (0.1, 0.9)
EXAMPLE_STORMS = 5


@dataclass(frozen=True)
class Analog:
    sid: str
    name: str
    season: int
    track: list[TrackPoint]
    weight: float
    intensity_kt_at_match: float
    reached_ga_100km: bool


def _dist_km(lat: float, lon: float, lats: np.ndarray, lons: np.ndarray) -> np.ndarray:
    p1, p2 = math.radians(lat), np.radians(lats)
    a = (
        np.sin((p2 - p1) / 2) ** 2
        + math.cos(p1) * np.cos(p2) * np.sin(np.radians(lons - lon) / 2) ** 2
    )
    return 2 * EARTH_KM * np.arcsin(np.minimum(1.0, np.sqrt(a)))


def _bearing(lat1, lon1, lat2, lon2) -> np.ndarray:
    p1, p2 = np.radians(lat1), np.radians(lat2)
    dl = np.radians(np.asarray(lon2) - np.asarray(lon1))
    y = np.sin(dl) * np.cos(p2)
    x = np.cos(p1) * np.sin(p2) - np.sin(p1) * np.cos(p2) * np.cos(dl)
    return (np.degrees(np.arctan2(y, x)) + 360.0) % 360.0


def _angle_diff(a, b) -> np.ndarray:
    return np.abs((np.asarray(a) - b + 180.0) % 360.0 - 180.0)


def size_for(vmax_kt: float) -> tuple[float, float]:
    table = data.tracks()["size_by_intensity"]
    row = min(table, key=lambda r: abs(r[0] - vmax_kt))
    return float(row[1]), float(row[2]) if vmax_kt >= 34 else 0.0


def _ga_centroids() -> tuple[np.ndarray, np.ndarray]:
    rows = data.counties()
    return np.array([r["lat"] for r in rows]), np.array([r["lon"] for r in rows])


def peak_near_ga(track: list[TrackPoint]) -> float:
    lats, lons = _ga_centroids()
    near = [
        p.vmax_kt for p in track if _dist_km(p.lat, p.lon, lats, lons).min() < NEAR_GA_KM
    ]
    return max(near) if near else max((p.vmax_kt for p in track), default=0.0)


def near_ga_km(lat: float, lon: float) -> float:
    lats, lons = _ga_centroids()
    return float(_dist_km(lat, lon, lats, lons).min())


def _over_land(lat: float, lon: float) -> bool:
    pts = np.array(data.tracks()["land_points"])
    return bool(_dist_km(lat, lon, pts[:, 0], pts[:, 1]).min() <= LAND_KM)


def classify_origin(lat: float, lon: float) -> str:
    if lon < -83.5 and lat < 31.5:
        return "gulf"
    if lat < 30.5:
        return "florida_peninsula"
    if lon >= -81.6 and lat <= 32.6:
        return "atlantic_ga"
    if lat > 32.6 and lon >= -82.0:
        return "carolinas"
    return "overland_west"


def origin_of(track: list[TrackPoint]) -> str | None:
    if not track:
        return None
    lats, lons = _ga_centroids()
    best = None
    for p in track:
        d = float(_dist_km(p.lat, p.lon, lats, lons).min())
        if d < NEAR_GA_KM:
            return classify_origin(p.lat, p.lon)
        if best is None or d < best[0]:
            best = (d, p)
    return classify_origin(best[1].lat, best[1].lon)


def support(track: list[TrackPoint]) -> str:
    origin = origin_of(track)
    peak = peak_near_ga(track)
    limit = data.tracks()["labelled_max_kt"].get(origin or "")
    if limit is None or peak > limit + 10.0:
        return "outside_labeled_support"
    return "within_labeled_support"


def _points(storm: dict) -> list[TrackPoint]:
    return [TrackPoint(p[0], p[1], p[2], p[3], p[4], p[5]) for p in storm["points"]]


def analog_tracks(
    lat: float,
    lon: float,
    heading_deg: float,
    month: int,
    intensity_kt: float | None = None,
    max_tracks: int = 40,
) -> list[Analog]:
    hits = []
    for s, pts, heading in _storm_arrays():
        d = _dist_km(lat, lon, pts[:, 1], pts[:, 2])
        gap = np.abs(pts[:, 6] - month)
        ok = (
            (d <= MATCH_KM)
            & (_angle_diff(heading, heading_deg) <= HEADING_DEG)
            & (np.minimum(gap, 12 - gap) <= 1)
        )
        if intensity_kt is not None:
            ok &= np.abs(pts[:, 3] - intensity_kt) <= INTENSITY_KT
        ok[-1] = False
        if not ok.any():
            continue
        idx = int(np.where(ok, d, np.inf).argmin())
        hits.append((float(d[idx]), s, idx))
    hits.sort(key=lambda h: (h[0], h[1]["sid"]))
    hits = hits[:max_tracks]
    out = []
    for _, s, idx in hits:
        pts = _points(s)[idx:]
        m = pts[0]
        dlat, dlon, h0 = lat - m.lat, lon - m.lon, m.hour
        shifted = [
            TrackPoint(p.hour - h0, p.lat + dlat, p.lon + dlon, p.vmax_kt, p.rmw_km, p.r34_km)
            for p in pts
        ]
        out.append(Analog(
            sid=s["sid"], name=s["name"], season=s["season"],
            track=interpolate_hourly(shifted), weight=1.0 / len(hits),
            intensity_kt_at_match=m.vmax_kt, reached_ga_100km=s["dmin_ga_km"] < 100.0,
        ))
    return out


def drawn_track(
    lonlats: list[list[float]], category: int, forward_kmh: float = 20.0
) -> list[TrackPoint]:
    if len(lonlats) < 2:
        return []
    v0 = CATEGORY_KT[int(category)]
    lats = np.array([p[1] for p in lonlats], float)
    lons = np.array([p[0] for p in lonlats], float)
    seg = np.array([
        _dist_km(lats[i], lons[i], lats[i + 1:i + 2], lons[i + 1:i + 2])[0]
        for i in range(len(lats) - 1)
    ])
    total = float(seg.sum())
    if total <= 0:
        return []
    cum = np.concatenate([[0.0], np.cumsum(seg)])
    n = max(2, int(total // forward_kmh) + 1)
    s_at = np.linspace(0.0, total, n)
    plat = np.interp(s_at, cum, lats)
    plon = np.interp(s_at, cum, lons)
    hours = s_at / forward_kmh
    out, landfall_h = [], None
    for h, la, lo in zip(hours, plat, plon, strict=True):
        if landfall_h is None and _over_land(la, lo):
            landfall_h = h
        if landfall_h is None:
            v = v0
        else:
            v = DECAY_BASE_KT + (LANDFALL_FACTOR * v0 - DECAY_BASE_KT) * math.exp(
                -DECAY_RATE_PER_H * (h - landfall_h)
            )
        rmw, r34 = size_for(v)
        out.append(TrackPoint(float(h), float(la), float(lo), float(v), rmw, r34))
    return interpolate_hourly(out)


def climatology() -> list[Analog]:
    t = data.tracks()
    years = t["years"][1] - t["years"][0] + 1
    return [
        Analog(
            sid=s["sid"], name=s["name"], season=s["season"],
            track=interpolate_hourly(_points(s)), weight=1.0 / years,
            intensity_kt_at_match=max(p[3] for p in s["points"]),
            reached_ga_100km=s["dmin_ga_km"] < 100.0,
        )
        for s in t["storms"]
        if s["dmin_ga_km"] < 250.0
    ]


def rescale(analog: Analog, category: int) -> Analog:
    target = CATEGORY_KT[int(category)]
    peak = peak_near_ga(analog.track)
    if peak <= 0:
        return analog
    f = target / peak
    track = []
    for p in analog.track:
        v = min(p.vmax_kt * f, 165.0)
        _, r34 = size_for(v)
        track.append(TrackPoint(p.hour, p.lat, p.lon, v, p.rmw_km, max(p.r34_km, r34)))
    return Analog(
        sid=analog.sid, name=analog.name, season=analog.season, track=track,
        weight=analog.weight, intensity_kt_at_match=analog.intensity_kt_at_match * f,
        reached_ga_100km=analog.reached_ga_100km,
    )


@cache
def _storm_arrays() -> list[tuple[dict, np.ndarray, np.ndarray]]:
    out = []
    for s in data.tracks()["storms"]:
        pts = np.array(s["points"], float)
        if len(pts) < 2:
            continue
        heading = np.empty(len(pts))
        heading[:-1] = _bearing(pts[:-1, 1], pts[:-1, 2], pts[1:, 1], pts[1:, 2])
        heading[-1] = heading[-2]
        out.append((s, pts, heading))
    return out


def _poisson_quantile(mean: float, q: float) -> int:
    k, term = 0, math.exp(-mean)
    total = term
    while total < q:
        k += 1
        term *= mean / k
        total += term
    return k


def _track_matches(
    track: list[TrackPoint], min_intensity_kt: float | None
) -> list[dict]:
    lats, lons = _ga_centroids()
    pts = np.array([[p.lat, p.lon] for p in track])
    head = np.empty(len(pts))
    head[:-1] = _bearing(pts[:-1, 0], pts[:-1, 1], pts[1:, 0], pts[1:, 1])
    head[-1] = head[-2]
    near = np.array([_dist_km(la, lo, lats, lons).min() < NEAR_GA_KM for la, lo in pts])
    if near.any():
        pts, head = pts[near], head[near]
    out = []
    for s, sp, sh in _storm_arrays():
        d = np.stack([_dist_km(la, lo, pts[:, 0], pts[:, 1]) for la, lo in sp[:, 1:3]])
        nearest = d.argmin(axis=1)
        close = d.min(axis=1) <= PATTERN_TRACK_KM
        ok = close & (_angle_diff(sh, head[nearest]) <= HEADING_DEG)
        if not ok.any():
            continue
        if min_intensity_kt is not None and sp[close, 3].max() < min_intensity_kt:
            continue
        out.append(s)
    return out


def _position_matches(
    lat: float,
    lon: float,
    heading_deg: float | None,
    month: int | None,
    min_intensity_kt: float | None,
) -> list[dict]:
    out = []
    for s, sp, sh in _storm_arrays():
        ok = _dist_km(lat, lon, sp[:, 1], sp[:, 2]) <= MATCH_KM
        if heading_deg is not None:
            ok &= _angle_diff(sh, heading_deg) <= HEADING_DEG
        if month is not None:
            gap = np.abs(sp[:, 6] - month)
            ok &= np.minimum(gap, 12 - gap) <= 1
        if min_intensity_kt is not None:
            ok &= sp[:, 3] >= min_intensity_kt
        if ok.any():
            out.append(s)
    return out


def pattern_frequency(
    *,
    track: list[TrackPoint] | None = None,
    lat: float | None = None,
    lon: float | None = None,
    heading_deg: float | None = None,
    month: int | None = None,
    min_intensity_kt: float | None = None,
) -> dict:
    if track:
        hits = _track_matches(track, min_intensity_kt)
    elif lat is not None and lon is not None:
        hits = _position_matches(lat, lon, heading_deg, month, min_intensity_kt)
    else:
        raise ValueError("pattern_frequency needs a track or a lat/lon position")
    first, last = data.tracks()["years"]
    years = last - first + 1
    n = len(hits)
    per_year = n / years
    lo, hi = (_poisson_quantile(n, q) / years for q in PATTERN_RANGE_Q)
    recent = sorted(hits, key=lambda s: (-s["season"], s["sid"]))[:EXAMPLE_STORMS]
    return {
        "matching_storms": n,
        "years": [first, last],
        "per_year": round(per_year, 4),
        "return_period_years": round(1 / per_year, 1) if n else None,
        "p_at_least_one_per_season": round(1 - math.exp(-per_year), 4),
        "per_year_range80": [round(lo, 4), round(hi, 4)],
        "example_storms": [f"{s['name']} {s['season']}" for s in recent],
    }
