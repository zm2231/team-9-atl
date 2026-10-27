from dataclasses import dataclass

import numpy as np

from . import data
from .model import FEATURES, OutageModel
from .storms import support
from .windfield import TrackPoint, exposure

DIALYSIS_DOWN_SHARE = 0.5
FACILITY_DOWN_SHARE = 0.5


@dataclass(frozen=True)
class Result:
    outage: np.ndarray
    track_of_draw: np.ndarray
    peak_wind_kt: np.ndarray
    hours_34kt: np.ndarray
    ts_arrival_h: np.ndarray
    outside_support: list[bool]


def run(tracks: list[list[TrackPoint]], n_draws: int = 400, seed: int = 20261027) -> Result:
    counties = data.counties()
    model = OutageModel.load()
    lats = np.array([c["lat"] for c in counties])
    lons = np.array([c["lon"] for c in counties])
    pop = np.array([c["pop"] for c in counties], float)
    tracks = [t for t in tracks if t]
    if not tracks:
        raise ValueError("run needs at least one non-empty track")
    rng = np.random.default_rng(seed)
    per = np.full(len(tracks), n_draws // len(tracks))
    per[: n_draws - per.sum()] += 1
    outage, owner, wind, h34, arrival = [], [], [], [], []
    for i, (track, k) in enumerate(zip(tracks, per, strict=True)):
        e = exposure(track, lats, lons)
        e["pop"] = pop
        wind.append(e["peak_wind_kt"])
        h34.append(e["hours_34kt"])
        arrival.append(e["first_34kt_hour"])
        if k == 0:
            continue
        feats = np.column_stack([e[f] for f in FEATURES])
        outage.append(model.sample(feats, rng, int(k)))
        owner.append(np.full(int(k), i))
    ts = np.median(np.nan_to_num(np.array(arrival), nan=np.inf), axis=0)
    ts[~np.isfinite(ts)] = np.nan
    return Result(
        outage=np.vstack(outage),
        track_of_draw=np.concatenate(owner),
        peak_wind_kt=np.median(np.array(wind), axis=0),
        hours_34kt=np.median(np.array(h34), axis=0),
        ts_arrival_h=ts,
        outside_support=[support(t) == "outside_labeled_support" for t in tracks],
    )


def people_at_risk(result: Result, counties: list[dict]) -> dict[str, np.ndarray]:
    share = result.outage

    def col(key: str) -> np.ndarray:
        return np.array([float(c.get(key) or 0) for c in counties])[None, :]

    return {
        "power_dependent": share * col("power_dependent"),
        "oxygen": share * col("oxygen"),
        "home_health": share * col("home_health"),
        "dialysis": np.where(share >= DIALYSIS_DOWN_SHARE, col("dialysis_patients"), 0.0),
        "facility_beds": np.where(
            share >= FACILITY_DOWN_SHARE,
            col("nursing_home_beds") + col("assisted_living_beds"),
            0.0,
        ),
    }
