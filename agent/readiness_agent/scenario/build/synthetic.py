import math
from dataclasses import dataclass

import numpy as np

from .. import storms
from ..windfield import TrackPoint

SHIFT_SD_KM = 50.0
SHIFT_MAX_KM = 150.0
CATEGORY_STEP_P = (0.25, 0.5, 0.25)
SPEED_RANGE = (0.7, 1.3)
SIZE_SD_LOG = 0.2
MAX_VMAX_KT = 165.0
CATEGORY_MID_KT = (50.0, 73.0, 89.0, 104.0, 124.0, 145.0)
SAFFIR_KT = (64.0, 83.0, 96.0, 113.0, 137.0)
KM_PER_DEG = 111.2
SUPPORT_TOLERANCE_KT = 10.0


@dataclass(frozen=True)
class Variant:
    track: list[TrackPoint]
    shift_km: float
    category_change: int
    speed_factor: float
    size_factor: float


def category(vmax_kt: float) -> int:
    return int(np.searchsorted(SAFFIR_KT, vmax_kt, side="right"))


def _closest(track: list[TrackPoint]) -> int:
    lats, lons = storms._ga_centroids()
    d = [float(storms._dist_km(p.lat, p.lon, lats, lons).min()) for p in track]
    return int(np.argmin(d))


def _heading(track: list[TrackPoint], i: int) -> float:
    a = track[max(i - 3, 0)]
    b = track[min(i + 3, len(track) - 1)]
    return float(storms._bearing(a.lat, a.lon, b.lat, b.lon))


def perturb(track: list[TrackPoint], rng: np.random.Generator) -> Variant:
    i0 = _closest(track)
    h0 = track[i0].hour
    shift = float(np.clip(rng.normal(0.0, SHIFT_SD_KM), -SHIFT_MAX_KM, SHIFT_MAX_KM))
    perp = math.radians(_heading(track, i0) + 90.0)
    dlat = shift * math.cos(perp) / KM_PER_DEG
    dlon = shift * math.sin(perp) / (KM_PER_DEG * math.cos(math.radians(track[i0].lat)))

    peak = storms.peak_near_ga(track)
    lifetime = max(p.vmax_kt for p in track)
    step = int(rng.choice((-1, 0, 1), p=CATEGORY_STEP_P))
    target = peak
    if step and peak > 0:
        cat = min(max(category(peak) + step, 0), len(CATEGORY_MID_KT) - 1)
        target = min(CATEGORY_MID_KT[cat], max(lifetime, peak))
    scale = target / peak if peak > 0 else 1.0
    speed = float(rng.uniform(*SPEED_RANGE))
    size = float(math.exp(rng.normal(0.0, SIZE_SD_LOG)))
    out = []
    for p in track:
        v = min(p.vmax_kt * scale, MAX_VMAX_KT)
        rmw, r34 = storms.size_for(v)
        out.append(TrackPoint(
            h0 + (p.hour - h0) / speed, p.lat + dlat, p.lon + dlon, v, rmw * size, r34 * size,
        ))
    applied = category(storms.peak_near_ga(out)) - category(peak)
    return Variant(out, shift, applied, speed, size)


def wind_chance(peak_wind: np.ndarray, rate: np.ndarray, threshold: float) -> np.ndarray:
    return 1.0 - np.exp(-(rate @ (peak_wind >= threshold).astype(np.float64)))
