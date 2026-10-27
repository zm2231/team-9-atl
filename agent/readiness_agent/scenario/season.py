import json
import math
from functools import cache

import numpy as np

from .data import DATA_DIR

EVENTS_FILE = DATA_DIR / "season_events.npz"
SEED = 20261027
YEARS = (1950, 2025)
ENSO_THRESHOLD = 0.5
RELOCATION_SHARE = {"low": 0.10, "base": 0.20, "high": 0.40}
FLORIDA_INFLOW = 0.15
DIALYSIS_PER_STATION = 1.0
NOAA_AUG_2026_SCALE = 10 / 14
NOAA_URL = "https://www.cpc.ncep.noaa.gov/products/outlooks/hurricane2026/August/hurricane.shtml"

OUTLOOKS = {
    "long_run": "Every storm 1950-2025 that came within 250 km of Georgia",
    "recent": "Storms 2000-2025 only",
    "la_nina": "Storms in La Nina years (Aug-Oct ONI <= -0.5)",
    "neutral": "Storms in ENSO-neutral years (Aug-Oct ONI between -0.5 and 0.5)",
    "el_nino": "Storms in El Nino years (Aug-Oct ONI >= 0.5)",
    "noaa_aug_2026": (
        "Outside forecast input: NOAA CPC August 2026 outlook (issued 6 August 2026, "
        f"{NOAA_URL}): 7-13 named storms, midpoint 10 against the 1991-2020 average of 14, "
        "so the long-run rate is scaled by 10/14"
    ),
}


@cache
def aso_oni() -> dict[int, float]:
    out = {}
    for line in (DATA_DIR / "oni.txt").read_text().splitlines()[1:]:
        parts = line.split()
        if len(parts) == 4 and parts[0] == "ASO":
            out[int(parts[1])] = float(parts[3])
    return out


def enso_phase(year: int) -> str:
    a = aso_oni()[year]
    if a <= -ENSO_THRESHOLD:
        return "la_nina"
    if a >= ENSO_THRESHOLD:
        return "el_nino"
    return "neutral"


def outlook_years(outlook: str) -> tuple[list[int], float]:
    every = list(range(YEARS[0], YEARS[1] + 1))
    if outlook in ("long_run", "noaa_aug_2026"):
        return every, NOAA_AUG_2026_SCALE if outlook == "noaa_aug_2026" else 1.0
    if outlook == "recent":
        return [y for y in every if y >= 2000], 1.0
    if outlook in ("la_nina", "neutral", "el_nino"):
        return [y for y in every if enso_phase(y) == outlook], 1.0
    raise ValueError(f"unknown outlook {outlook!r}; choose from {', '.join(OUTLOOKS)}")


def storms_per_year(outlook: str, storm_season: np.ndarray) -> float:
    years, scale = outlook_years(outlook)
    return float(np.isin(storm_season, years).sum() / len(years) * scale)


def event_rates(outlook: str, storm_season: np.ndarray, storm_of_event: np.ndarray) -> np.ndarray:
    years, scale = outlook_years(outlook)
    per_storm = np.where(np.isin(storm_season, years), scale / len(years), 0.0)
    counts = np.bincount(storm_of_event, minlength=len(storm_season))
    return per_storm[storm_of_event] / counts[storm_of_event]


def allocate(demand: np.ndarray, capacity: np.ndarray, reach: np.ndarray) -> np.ndarray:
    total = demand @ reach
    ratio = np.divide(capacity, total, out=np.ones_like(capacity), where=total > 0)
    return np.minimum(demand, demand * (np.minimum(ratio, 1.0) @ reach.T))


def worst_per_season(
    values: dict[str, np.ndarray], rate: np.ndarray, rng: np.random.Generator, n: int
) -> dict[str, np.ndarray]:
    lam = float(rate.sum())
    k = rng.poisson(lam, size=n)
    picks = rng.choice(len(rate), size=int(k.sum()), p=rate / lam)
    starts = (np.cumsum(k) - k)[k > 0]
    out = {}
    for key, v in values.items():
        best = np.zeros((n, v.shape[1]), dtype=v.dtype)
        if picks.size:
            best[k > 0] = np.maximum.reduceat(v[picks], starts, axis=0)
        out[key] = best
    return out


@cache
def events() -> dict[str, np.ndarray]:
    with np.load(EVENTS_FILE) as z:
        return {k: z[k] for k in z.files}


@cache
def vehicle_shares(fips: tuple[str, ...]) -> tuple[np.ndarray, np.ndarray]:
    rows = json.loads((DATA_DIR / "acs_vehicles.json").read_text())["counties"]
    s65 = np.array([float(rows.get(f, {}).get("no_vehicle_share_65") or 0) for f in fips])
    sall = np.array([float(rows.get(f, {}).get("no_vehicle_share_all") or 0) for f in fips])
    return s65.astype(np.float32), sall.astype(np.float32)


def per_event(
    ev: dict[str, np.ndarray],
    *,
    relocation_share: float,
    florida_inflow: float = FLORIDA_INFLOW,
    dialysis_per_station: float = DIALYSIS_PER_STATION,
    shelter_open: np.ndarray | None = None,
    shelter_powered: np.ndarray | None = None,
    dialysis_open: np.ndarray | None = None,
) -> dict[str, np.ndarray]:
    keep = 1.0 - florida_inflow
    cats = ev["category"][:, None]
    powered = ev["shelter_generator"] == "YES" if shelter_powered is None else shelter_powered
    s_open = np.ones(len(powered), bool) if shelter_open is None else shelter_open
    seats = (ev["shelter_seats"] * powered * s_open * keep).astype(np.float32)
    seats = np.where(ev["shelter_surge"][None, :] <= cats, 0.0, seats[None, :])
    seekers = relocation_share * ev["pd_affected"]
    reach_s = ev["shelter_reach"].astype(np.float32)
    no_seat = seekers - allocate(seekers, seats.astype(np.float32), reach_s)

    d_open = np.ones(len(ev["dialysis_stations"]), bool) if dialysis_open is None else dialysis_open
    chairs = (ev["dialysis_stations"] * dialysis_per_station * d_open * keep).astype(np.float32)
    county = ev["dialysis_county"]
    down = np.zeros((len(cats), len(county)), bool)
    valid = county >= 0
    down[:, valid] = ev["down50"][:, county[valid]]
    flooded = ev["dialysis_surge"][None, :] <= cats
    chairs = np.where(flooded | down, 0.0, chairs[None, :]).astype(np.float32)
    displaced = ev["displaced"]
    reach_d = ev["dialysis_reach"].astype(np.float32)
    no_chair = displaced - allocate(displaced, chairs, reach_d)

    s65, sall = vehicle_shares(tuple(str(f) for f in ev["county_fips"]))
    no_seat, no_chair = np.maximum(no_seat, 0), np.maximum(no_chair, 0)
    return {
        "pd_affected": ev["pd_affected"],
        "no_powered_seat": no_seat,
        "no_dialysis_chair": no_chair,
        "lacking_shelter": no_seat + no_chair,
        "no_vehicle": ev["pd_affected"] * s65,
        "no_vehicle_low": ev["pd_affected"] * sall,
    }


def summarize(
    values: dict[str, np.ndarray], rate: np.ndarray, out25: np.ndarray, n: int, seed: int
) -> dict:
    seasons = worst_per_season(values, rate, np.random.default_rng(seed), n)
    lam = rate @ out25.astype(np.float64)
    any_lam = float(rate @ out25.any(axis=1))

    def pair(x: np.ndarray, axis=0):
        typical = np.median(x, axis=axis)
        one_in_10 = np.quantile(x, 0.9, axis=axis)
        return typical, one_in_10

    county = {k: pair(v) for k, v in seasons.items()}
    state = {k: pair(v.sum(axis=1)) for k, v in seasons.items()}
    return {
        "p_outage25_per_year": 1 - np.exp(-lam),
        "p_any_county_outage25_per_year": 1 - math.exp(-any_lam),
        "county": county,
        "statewide": state,
    }


def _block(t, i=None) -> dict:
    typical, one_in_10 = t
    if i is not None:
        typical, one_in_10 = typical[i], one_in_10[i]
    return {"typical": round(float(typical)), "one_in_10": round(float(one_in_10))}


def _shape(s: dict, i=None) -> dict:
    src = s["statewide"] if i is None else s["county"]
    return {
        "power_dependent_affected": _block(src["pd_affected"], i),
        "lacking_shelter": {
            "no_powered_seat": _block(src["no_powered_seat"], i),
            "no_dialysis_chair": _block(src["no_dialysis_chair"], i),
            "total": _block(src["lacking_shelter"], i),
        },
        "needing_transport": {
            "no_vehicle": _block(src["no_vehicle"], i),
            "no_vehicle_low": _block(src["no_vehicle_low"], i),
        },
    }


ASSUMPTION_READING = {
    "UNRECORDED": "confirms a generator where none is recorded either way",
    "NO": "adds a generator where the record says none",
    "YES": "no change: a generator is already recorded",
}


def run_season(
    outlook: str = "long_run",
    sites_off: tuple[str, ...] | list[str] = (),
    assume_generator: tuple[str, ...] | list[str] = (),
    case: str = "base",
    n_seasons: int = 5000,
    seed: int = SEED,
) -> dict:
    if case not in RELOCATION_SHARE:
        raise ValueError(f"unknown case {case!r}; choose low, base or high")
    ev = events()
    years, _ = outlook_years(outlook)
    shelter_ids = [str(x) for x in ev["shelter_id"]]
    ccns = [str(x) for x in ev["dialysis_ccn"]]
    known = set(shelter_ids) | set(ccns)
    off = {str(x) for x in sites_off}
    gen = {str(x) for x in assume_generator}
    ignored = sorted((off | gen) - known) + sorted(gen & set(ccns) - off)
    powered = (ev["shelter_generator"] == "YES") | np.isin(shelter_ids, list(gen))
    values = per_event(
        ev,
        relocation_share=RELOCATION_SHARE[case],
        shelter_open=~np.isin(shelter_ids, list(off)),
        shelter_powered=powered,
        dialysis_open=~np.isin(ccns, list(off)),
    )
    rate = event_rates(outlook, ev["storm_season"], ev["storm_of_event"])
    s = summarize(values, rate, ev["out25"], n_seasons, seed)
    fips, names = ev["county_fips"], ev["county_name"]
    return {
        "outlook": outlook,
        "label": OUTLOOKS[outlook],
        "storms_per_year": round(storms_per_year(outlook, ev["storm_season"]), 3),
        "years_used": len(years),
        "case": case,
        "relocation_share": RELOCATION_SHARE[case],
        "sites_off": sorted(off & known),
        "assume_generator": sorted(gen & set(shelter_ids)),
        "generator_assumptions": {
            sid: ASSUMPTION_READING[str(rec)]
            for sid, rec in zip(shelter_ids, ev["shelter_generator"], strict=True)
            if sid in gen
        },
        "ignored_ids": ignored,
        "statewide": {
            "p_any_county_outage25_per_year": round(s["p_any_county_outage25_per_year"], 4),
            **_shape(s),
        },
        "counties": [
            {
                "county_fips": str(fips[i]),
                "county_name": str(names[i]),
                "p_outage25_per_year": round(float(s["p_outage25_per_year"][i]), 4),
                **_shape(s, i),
            }
            for i in range(len(fips))
        ],
    }
