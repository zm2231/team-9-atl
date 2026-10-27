import json
import math
from functools import cache
from typing import Any

import numpy as np

from . import data
from .data import DATA_DIR

EVENTS_FILE = DATA_DIR / "season_events.npz"
SEED = 20261027
YEARS = (1950, 2025)
ENSO_THRESHOLD = 0.5
RELOCATION_SHARE = {"low": 0.10, "base": 0.20, "high": 0.40}
FLORIDA_INFLOW = 0.15
DIALYSIS_PER_STATION = 1.0
NOAA_AUG_2026_SCALE = 10 / 14
RECEIVE_KM = 100.0
MAX_CAPACITY = 100_000
GENERATOR_FLAGS = ("YES", "NO", "UNRECORDED")
GA_LAT = (30.3, 35.1)
GA_LON = (-85.7, -80.7)
UNKNOWN_SURGE = 99
ADDED_SURGE_NOTE = "unknown, treated as not flooded"
PROBABILITY_LABEL = "share of simulated seasons"
NOAA_URL = "https://www.cpc.ncep.noaa.gov/products/outlooks/hurricane2026/August/hurricane.shtml"

OUTLOOKS = {
    "long_run": "Every storm 1950-2025 that came within 250 km of Georgia",
    "recent": "Storms 2000-2025 only",
    "la_nina": "Storms in La Nina years (Aug-Oct ONI <= -0.5)",
    "neutral": "Storms in ENSO-neutral years (Aug-Oct ONI between -0.5 and 0.5)",
    "el_nino": "Storms in El Nino years (Aug-Oct ONI >= 0.5)",
    "noaa_aug_2026": (
        "Outside forecast input: NOAA CPC August 2026 outlook (issued 6 August 2026, "
        f"{NOAA_URL}): midpoints 10 named storms, 4 hurricanes and 1 major against 1991-2020 "
        "averages of 14, 7 and 3. The long-run rate is scaled by 10/14 and events are reweighted "
        "by category so the Cat 1+ and Cat 3+ shares move by the same ratios as NOAA's counts"
    ),
}
CUSTOM = "custom"
NOAA_MIDPOINTS = {"named": 10, "hurricanes": 4, "major": 1}
BASIN_AVERAGE = {"named": 14, "hurricanes": 7, "major": 3}


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


def event_classes(category: np.ndarray) -> np.ndarray:
    return np.where(category >= 3, 2, np.where(category >= 1, 1, 0))


def severity_shares(rate: np.ndarray, category: np.ndarray) -> dict[str, float]:
    total = float(rate.sum())
    if total <= 0:
        return {"cat1_plus_share": 0.0, "cat3_plus_share": 0.0}
    return {
        "cat1_plus_share": round(float(rate[category >= 1].sum() / total), 4),
        "cat3_plus_share": round(float(rate[category >= 3].sum() / total), 4),
    }


def reweight(
    rate: np.ndarray, category: np.ndarray, hurricane_share: float, major_share: float
) -> np.ndarray:
    cls = event_classes(category)
    total = float(rate.sum())
    target = np.array([1 - hurricane_share, hurricane_share - major_share, major_share]) * total
    mass = np.array([rate[cls == c].sum() for c in range(3)])
    if np.any((mass <= 0) & (target > 0)):
        raise ValueError("no simulated storms in a category the target shares need")
    factor = np.divide(target, mass, out=np.zeros(3), where=mass > 0)
    return rate * factor[cls]


def _check_custom(custom: Any) -> dict[str, Any]:
    custom = custom if isinstance(custom, dict) else {}
    try:
        n = float(custom["storms_per_year"])
        h = float(custom["hurricane_share"])
        m = float(custom["major_share"])
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError(f"custom outlook: {exc}") from exc
    source = custom.get("source")
    if not (math.isfinite(n) and 0 < n <= 20):
        raise ValueError("storms_per_year must be above 0 and at most 20")
    if not (0 <= m <= h <= 1):
        raise ValueError("need 0 <= major_share <= hurricane_share <= 1")
    if not isinstance(source, str) or not source.strip():
        raise ValueError("custom outlook needs a source")
    return {"storms_per_year": n, "hurricane_share": h, "major_share": m, "source": source.strip()}


def _day_of_year(value: Any) -> int:
    from datetime import date

    d = value if isinstance(value, date) else date.fromisoformat(str(value))
    day = 28 if (d.month, d.day) == (2, 29) else d.day
    return date(2001, d.month, day).timetuple().tm_yday


@cache
def storm_day_of_year() -> np.ndarray:
    from datetime import date, timedelta

    clat, clon = county_centres()
    days, seasons = [], []
    for s in data.tracks()["storms"]:
        if s["dmin_ga_km"] >= 250.0 or not YEARS[0] <= s["season"] <= YEARS[1]:
            continue
        pts = np.array(s["points"], float)
        d = _distance_km(clat[None, :], clon[None, :], pts[:, 1:2], pts[:, 2:3]).min(axis=1)
        genesis = date(int(s["sid"][:4]), 1, 1) + timedelta(days=int(s["sid"][4:7]) - 1)
        closest = genesis + timedelta(hours=float(pts[int(d.argmin()), 0]))
        days.append(_day_of_year(closest))
        seasons.append(s["season"])
    if seasons != [int(x) for x in events()["storm_season"]]:
        raise ValueError("tracks.json and season_events.npz disagree on the storm list")
    return np.array(days, float)


def season_remaining_share(as_of_date: Any) -> float:
    days = storm_day_of_year()
    return round(float((days > _day_of_year(as_of_date)).mean()), 4)


def outlook_event_rates(
    outlook: str,
    custom: Any = None,
    as_of_date: Any = None,
    ev: dict[str, np.ndarray] | None = None,
) -> np.ndarray:
    ev = events() if ev is None else ev
    if outlook == CUSTOM:
        c = _check_custom(custom)
        rate = event_rates("long_run", ev["storm_season"], ev["storm_of_event"])
        rate = reweight(rate, ev["category"], c["hurricane_share"], c["major_share"])
        rate = rate * c["storms_per_year"] / rate.sum()
    else:
        rate = event_rates(outlook, ev["storm_season"], ev["storm_of_event"])
        if outlook == "noaa_aug_2026":
            long = severity_shares(rate, ev["category"])
            h = (
                long["cat1_plus_share"]
                * (NOAA_MIDPOINTS["hurricanes"] / NOAA_MIDPOINTS["named"])
                / (BASIN_AVERAGE["hurricanes"] / BASIN_AVERAGE["named"])
            )
            m = (
                long["cat3_plus_share"]
                * (NOAA_MIDPOINTS["major"] / NOAA_MIDPOINTS["named"])
                / (BASIN_AVERAGE["major"] / BASIN_AVERAGE["named"])
            )
            rate = reweight(rate, ev["category"], min(h, 1.0), min(m, h, 1.0))
    if as_of_date is not None:
        after = storm_day_of_year()[ev["storm_of_event"]] > _day_of_year(as_of_date)
        rate = rate * after
    return rate


def allocate(demand: np.ndarray, capacity: np.ndarray, reach: np.ndarray) -> np.ndarray:
    total = demand @ reach
    ratio = np.divide(capacity, total, out=np.ones_like(capacity), where=total > 0)
    return np.minimum(demand, demand * (np.minimum(ratio, 1.0) @ reach.T))


def season_draws(rate: np.ndarray, rng: np.random.Generator, n: int) -> dict[str, np.ndarray]:
    lam = float(rate.sum())
    if lam <= 0:
        return {"k": np.zeros(n, int), "picks": np.zeros(0, int), "starts": np.zeros(0, int)}
    k = rng.poisson(lam, size=n)
    picks = rng.choice(len(rate), size=int(k.sum()), p=rate / lam)
    return {"k": k, "picks": picks, "starts": (np.cumsum(k) - k)[k > 0]}


def worst(v: np.ndarray, draws: dict[str, np.ndarray]) -> np.ndarray:
    k = draws["k"]
    best = np.zeros((len(k), v.shape[1]), dtype=v.dtype)
    if draws["picks"].size:
        best[k > 0] = np.maximum.reduceat(v[draws["picks"]], draws["starts"], axis=0)
    return best


def worst_per_season(
    values: dict[str, np.ndarray], rate: np.ndarray, rng: np.random.Generator, n: int
) -> dict[str, np.ndarray]:
    draws = season_draws(rate, rng, n)
    return {key: worst(v, draws) for key, v in values.items()}


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
    return summarize_seasons(seasons, rate, out25)


def summarize_seasons(seasons: dict[str, np.ndarray], rate: np.ndarray, out25: np.ndarray) -> dict:
    lam = rate @ out25.astype(np.float64)
    any_lam = float(rate @ out25.any(axis=1))

    def pair(x: np.ndarray, axis=0):
        return tuple(np.quantile(x, (0.5, 0.9, 0.99), axis=axis))

    county: dict[str, Any] = {k: pair(v) for k, v in seasons.items()}
    state: dict[str, Any] = {k: pair(v.sum(axis=1)) for k, v in seasons.items()}
    county["p"] = exceedance(seasons["lacking_shelter"], seasons["no_dialysis_chair"])
    state["p"] = exceedance(
        seasons["lacking_shelter"].sum(axis=1), seasons["no_dialysis_chair"].sum(axis=1)
    )
    return {
        "p_outage25_per_year": 1 - np.exp(-lam),
        "p_any_county_outage25_per_year": 1 - math.exp(-any_lam),
        "county": county,
        "statewide": state,
    }


UNCERTAINTY_MODES = ("fixed", "sampled")
UNKNOWNS = {
    "relocation_share": (
        "triangular(0.10, 0.20, 0.40): the low and high fixed cases bound it and the base case "
        "is the mode; no county records how many power-dependent residents seek a powered seat"
    ),
    "florida_inflow": (
        "uniform(0.05, 0.25) share of Georgia receiving capacity taken by Florida evacuees: no "
        "intake record by home state exists, so the range brackets the fixed 0.15"
    ),
    "dialysis_per_station": (
        "uniform(1, 2) displaced patients per station: one with a late shift, up to two with "
        "extra shifts; no centre reports surge capacity"
    ),
    "unrecorded_generators": (
        "each medical shelter with no generator record has one with probability {p:.3f}, a "
        "prior from the {n} medical shelters whose generator is recorded ({yes} YES, {no} NO)"
    ),
    "no_vehicle_share": (
        "uniform between each county's all-household and 65+ no-vehicle share (ACS B25045); one "
        "draw per season, at the same point of every county's range"
    ),
}
SOBOL_BINS = 20


def generator_prior(ev: dict[str, np.ndarray]) -> dict[str, Any]:
    flags = [str(x) for x in ev["shelter_generator"]]
    yes, no = flags.count("YES"), flags.count("NO")
    return {"p": yes / (yes + no), "yes": yes, "no": no, "n": yes + no}


def _per_pick_worst(v: np.ndarray, draws: dict[str, np.ndarray]) -> np.ndarray:
    k = draws["k"]
    best = np.zeros((len(k), v.shape[1]), dtype=v.dtype)
    if v.shape[0]:
        best[k > 0] = np.maximum.reduceat(v, draws["starts"], axis=0)
    return best


def sampled_seasons(
    ev: dict[str, np.ndarray], masks: dict[str, np.ndarray], rate: np.ndarray, n: int, seed: int
) -> tuple[dict[str, np.ndarray], dict[str, np.ndarray]]:
    rng = np.random.default_rng(seed)
    draws = season_draws(rate, rng, n)
    prior = generator_prior(ev)
    unknown_gen = np.flatnonzero(
        (ev["shelter_generator"] == "UNRECORDED") & ~masks["shelter_powered"]
    )
    params = {
        "relocation_share": rng.triangular(0.10, 0.20, 0.40, size=n),
        "florida_inflow": rng.uniform(0.05, 0.25, size=n),
        "dialysis_per_station": rng.uniform(1.0, 2.0, size=n),
        "no_vehicle_share": rng.uniform(0.0, 1.0, size=n),
    }
    gen = rng.random((n, len(unknown_gen))) < prior["p"]
    params["unrecorded_generators"] = (gen * ev["shelter_seats"][unknown_gen]).sum(axis=1)

    picks = draws["picks"]
    s_of = np.repeat(np.arange(n), draws["k"])
    cats = ev["category"][picks][:, None]
    keep = (1.0 - params["florida_inflow"][s_of])[:, None]

    powered = np.repeat(masks["shelter_powered"][None, :], len(picks), axis=0)
    powered[:, unknown_gen] = gen[s_of]
    seats = ev["shelter_seats"][None, :] * powered * masks["shelter_open"][None, :] * keep
    seats = np.where(ev["shelter_surge"][None, :] <= cats, 0.0, seats).astype(np.float32)
    pd = ev["pd_affected"][picks]
    seekers = (params["relocation_share"][s_of][:, None] * pd).astype(np.float32)
    reach_s = ev["shelter_reach"].astype(np.float32)
    no_seat = np.maximum(seekers - allocate(seekers, seats, reach_s), 0)

    county = ev["dialysis_county"]
    valid = county >= 0
    down = np.zeros((len(picks), len(county)), bool)
    down[:, valid] = ev["down50"][picks][:, county[valid]]
    flooded = ev["dialysis_surge"][None, :] <= cats
    chairs = (
        ev["dialysis_stations"][None, :]
        * masks["dialysis_open"][None, :]
        * params["dialysis_per_station"][s_of][:, None]
        * keep
    )
    chairs = np.where(flooded | down, 0.0, chairs).astype(np.float32)
    displaced = ev["displaced"][picks]
    no_chair = np.maximum(
        displaced - allocate(displaced, chairs, ev["dialysis_reach"].astype(np.float32)), 0
    )

    s65, sall = vehicle_shares(tuple(str(f) for f in ev["county_fips"]))
    share = sall[None, :] + params["no_vehicle_share"][s_of][:, None] * (s65 - sall)[None, :]
    per_pick = {
        "pd_affected": pd,
        "no_powered_seat": no_seat,
        "no_dialysis_chair": no_chair,
        "lacking_shelter": no_seat + no_chair,
        "no_vehicle": pd * share,
        "no_vehicle_low": pd * sall[None, :],
    }
    return {k: _per_pick_worst(v, draws) for k, v in per_pick.items()}, params


def unknown_ranges(ev: dict[str, np.ndarray]) -> dict[str, str]:
    prior = generator_prior(ev)
    return {
        k: v.format(**prior) if k == "unrecorded_generators" else v for k, v in UNKNOWNS.items()
    }


def first_order(y: np.ndarray, x: np.ndarray, bins: int = SOBOL_BINS) -> dict[str, float]:
    var = float(y.var())
    if var <= 0:
        return {"sobol_first_order": 0.0, "correlation_squared": 0.0}
    order = np.argsort(x, kind="stable")
    groups = np.array_split(order, bins)
    means = np.array([y[g].mean() for g in groups])
    sizes = np.array([len(g) for g in groups])
    between = float((sizes * (means - y.mean()) ** 2).sum() / len(y))
    between = max(0.0, between - var * (bins - 1) / len(y))
    corr = float(np.corrcoef(x, y)[0, 1]) if x.std() > 0 else 0.0
    return {"sobol_first_order": round(between / var, 4), "correlation_squared": round(corr**2, 4)}


def spread_attribution(seasons: dict[str, np.ndarray], params: dict[str, np.ndarray]) -> dict:
    out = {}
    for target, key in (
        ("lacking_shelter", "lacking_shelter"),
        ("needing_transport", "no_vehicle"),
    ):
        y = seasons[key].sum(axis=1)
        sd = float(y.std())
        rows = {}
        for name, x in params.items():
            fo = first_order(y, x)
            left = max(0.0, 1 - fo["sobol_first_order"])
            rows[name] = {
                **fo,
                "sd_reduction_if_known": round(sd - sd * math.sqrt(left), 1),
            }
        out[target] = {"statewide_sd": round(sd, 1), "unknowns": rows}
    return out


def exceedance(lacking: np.ndarray, no_chair: np.ndarray) -> dict[str, np.ndarray]:
    return {
        "p_lacking_shelter_any": (lacking >= 1).mean(axis=0),
        "p_lacking_shelter_50": (lacking >= 50).mean(axis=0),
        "p_no_dialysis_chair_any": (no_chair >= 1).mean(axis=0),
    }


def _block(t, i=None) -> dict:
    typical, one_in_10, one_in_100 = (x if i is None else x[i] for x in t)
    return {
        "typical": round(float(typical)),
        "one_in_10": round(float(one_in_10)),
        "one_in_100": round(float(one_in_100)),
    }


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
        "probability": {
            "label": PROBABILITY_LABEL,
            **{k: round(float(v if i is None else v[i]), 4) for k, v in src["p"].items()},
        },
    }


ASSUMPTION_READING = {
    "UNRECORDED": "confirms a generator where none is recorded either way",
    "NO": "adds a generator where the record says none",
    "YES": "no change: a generator is already recorded",
}


def _distance_km(lat1, lon1, lat2, lon2) -> np.ndarray:
    p1, p2 = np.radians(lat1), np.radians(lat2)
    a = (
        np.sin((p2 - p1) / 2) ** 2
        + np.cos(p1) * np.cos(p2) * np.sin(np.radians(np.asarray(lon2) - lon1) / 2) ** 2
    )
    return 2 * 6371.0 * np.arcsin(np.minimum(1.0, np.sqrt(a)))


@cache
def county_centres() -> tuple[np.ndarray, np.ndarray]:
    by_fips = {c["county_fips"]: c for c in data.counties()}
    fips = [str(f) for f in events()["county_fips"]]
    return (
        np.array([by_fips[f]["lat"] for f in fips]),
        np.array([by_fips[f]["lon"] for f in fips]),
    )


def reach_of(lat: float, lon: float) -> np.ndarray:
    clat, clon = county_centres()
    return _distance_km(clat, clon, lat, lon) <= RECEIVE_KM


def _count(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    try:
        n = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(n) or n < 0 or n > MAX_CAPACITY or n != int(n):
        return None
    return int(n)


def new_site(raw: Any, index: int) -> dict | None:
    if not isinstance(raw, dict):
        return None
    kind = raw.get("site_kind", "medical_shelter")
    try:
        lat, lon = float(raw["lat"]), float(raw["lon"])
    except (KeyError, TypeError, ValueError):
        return None
    if not (GA_LAT[0] <= lat <= GA_LAT[1] and GA_LON[0] <= lon <= GA_LON[1]):
        return None
    site_id = raw.get("id") if isinstance(raw.get("id"), str) and raw.get("id") else None
    if kind == "medical_shelter":
        seats = _count(raw.get("seats"))
        generator = str(raw.get("generator", "")).upper()
        if not seats or generator not in GENERATOR_FLAGS:
            return None
        return {
            "site_kind": kind,
            "id": site_id or f"added-shelter-{index}",
            "lat": lat,
            "lon": lon,
            "seats": seats,
            "generator": generator,
        }
    if kind == "dialysis":
        stations = _count(raw.get("stations"))
        if not stations:
            return None
        return {
            "site_kind": kind,
            "id": site_id or f"added-dialysis-{index}",
            "lat": lat,
            "lon": lon,
            "stations": stations,
        }
    return None


def site_inputs(
    ev: dict[str, np.ndarray],
    *,
    seats_override: Any = None,
    stations_override: Any = None,
    generator_override: Any = None,
    location_override: Any = None,
    add_sites: Any = (),
) -> tuple[dict[str, np.ndarray], list[str], list[dict]]:
    out = dict(ev)
    ignored: list[str] = []
    seats = ev["shelter_seats"].astype(np.float32).copy()
    stations = ev["dialysis_stations"].astype(np.float32).copy()
    generator = ev["shelter_generator"].astype("<U10").copy()
    shelter_ids = [str(x) for x in ev["shelter_id"]]
    ccns = [str(x) for x in ev["dialysis_ccn"]]

    def apply(mapping: Any, ids: list[str], target: np.ndarray, parse) -> None:
        if mapping is None:
            return
        if not isinstance(mapping, dict):
            ignored.append(repr(mapping))
            return
        for key, raw in mapping.items():
            value = parse(raw)
            if not isinstance(key, str) or key not in ids or value is None:
                ignored.append(f"{key}={raw!r}")
                continue
            target[ids.index(key)] = value

    def flag(raw: Any) -> str | None:
        text = str(raw).upper() if isinstance(raw, str) else None
        return text if text in GENERATOR_FLAGS else None

    apply(seats_override, shelter_ids, seats, _count)
    apply(stations_override, ccns, stations, _count)
    apply(generator_override, shelter_ids, generator, flag)

    shelter_reach = ev["shelter_reach"].copy()
    dialysis_reach = ev["dialysis_reach"].copy()
    for sid, loc in (location_override or {}).items():
        try:
            lat, lon = float(loc["lat"]), float(loc["lon"])
        except (KeyError, TypeError, ValueError):
            ignored.append(f"{sid} location={loc!r}")
            continue
        if sid in shelter_ids:
            shelter_reach[:, shelter_ids.index(sid)] = reach_of(lat, lon)
        elif sid in ccns:
            dialysis_reach[:, ccns.index(sid)] = reach_of(lat, lon)
        else:
            ignored.append(f"{sid} location={loc!r}")

    added: list[dict] = []
    if add_sites is not None and not isinstance(add_sites, list | tuple):
        ignored.append(repr(add_sites))
        add_sites = ()
    for i, raw in enumerate(add_sites or ()):
        site = new_site(raw, i + 1)
        if site is None or site["id"] in shelter_ids or site["id"] in ccns:
            ignored.append(repr(raw))
            continue
        added.append(site)
    new_s = [a for a in added if a["site_kind"] == "medical_shelter"]
    new_d = [a for a in added if a["site_kind"] == "dialysis"]
    clat, clon = county_centres()

    def reach_cols(rows: list[dict]) -> np.ndarray:
        return (
            np.column_stack([reach_of(a["lat"], a["lon"]) for a in rows])
            if rows
            else (np.zeros((len(clat), 0), bool))
        )

    out["shelter_id"] = np.array(shelter_ids + [a["id"] for a in new_s])
    out["shelter_seats"] = np.concatenate([seats, [a["seats"] for a in new_s]]).astype(np.float32)
    out["shelter_generator"] = np.concatenate([generator, [a["generator"] for a in new_s]])
    out["shelter_surge"] = np.concatenate(
        [ev["shelter_surge"], np.full(len(new_s), UNKNOWN_SURGE, np.int8)]
    )
    out["shelter_reach"] = np.hstack([shelter_reach, reach_cols(new_s)])
    out["dialysis_ccn"] = np.array(ccns + [a["id"] for a in new_d])
    out["dialysis_stations"] = np.concatenate([stations, [a["stations"] for a in new_d]]).astype(
        np.float32
    )
    out["dialysis_surge"] = np.concatenate(
        [ev["dialysis_surge"], np.full(len(new_d), UNKNOWN_SURGE, np.int8)]
    )
    out["dialysis_county"] = np.concatenate(
        [
            ev["dialysis_county"],
            np.array(
                [int(_distance_km(clat, clon, a["lat"], a["lon"]).argmin()) for a in new_d],
                np.int16,
            ),
        ]
    ).astype(np.int16)
    out["dialysis_reach"] = np.hstack([dialysis_reach, reach_cols(new_d)])
    for a in added:
        a["surge"] = ADDED_SURGE_NOTE
        a["counties_in_reach"] = int(reach_of(a["lat"], a["lon"]).sum())
    return out, ignored, added


def _prepare(
    sites_off, assume_generator, case, site_kwargs: dict
) -> tuple[dict[str, np.ndarray], dict[str, np.ndarray], dict]:
    if case not in RELOCATION_SHARE:
        raise ValueError(f"unknown case {case!r}; choose low, base or high")
    ev, ignored, added = site_inputs(events(), **site_kwargs)
    shelter_ids = [str(x) for x in ev["shelter_id"]]
    ccns = [str(x) for x in ev["dialysis_ccn"]]
    known = set(shelter_ids) | set(ccns)
    off = {str(x) for x in sites_off}
    gen = {str(x) for x in assume_generator}
    ignored = ignored + sorted((off | gen) - known) + sorted(gen & set(ccns) - off)
    powered = (ev["shelter_generator"] == "YES") | np.isin(shelter_ids, list(gen))
    masks = {
        "shelter_open": ~np.isin(shelter_ids, list(off)),
        "shelter_powered": powered,
        "dialysis_open": ~np.isin(ccns, list(off)),
    }
    meta = {
        "sites_off": sorted(off & known),
        "assume_generator": sorted(gen & set(shelter_ids)),
        "generator_assumptions": {
            sid: ASSUMPTION_READING[str(rec)]
            for sid, rec in zip(shelter_ids, ev["shelter_generator"], strict=True)
            if sid in gen
        },
        "ignored_ids": ignored,
        "added_sites": added,
    }
    return ev, masks, meta


def run_season(
    outlook: str = "long_run",
    sites_off: tuple[str, ...] | list[str] = (),
    assume_generator: tuple[str, ...] | list[str] = (),
    case: str = "base",
    n_seasons: int = 5000,
    seed: int = SEED,
    seats_override: Any = None,
    stations_override: Any = None,
    generator_override: Any = None,
    location_override: Any = None,
    add_sites: Any = (),
    as_of_date: Any = None,
    custom: Any = None,
    uncertainty: str = "fixed",
) -> dict:
    if uncertainty not in UNCERTAINTY_MODES:
        raise ValueError(f"uncertainty must be one of {', '.join(UNCERTAINTY_MODES)}")
    years, _ = outlook_years("long_run" if outlook == CUSTOM else outlook)
    rate = outlook_event_rates(outlook, custom, as_of_date)
    ev, masks, meta = _prepare(
        sites_off,
        assume_generator,
        case,
        {
            "seats_override": seats_override,
            "stations_override": stations_override,
            "generator_override": generator_override,
            "location_override": location_override,
            "add_sites": add_sites,
        },
    )
    if uncertainty == "sampled":
        seasons, params = sampled_seasons(ev, masks, rate, n_seasons, seed)
        s = summarize_seasons(seasons, rate, ev["out25"])
        spread = {
            "mode": "sampled",
            "unknowns": unknown_ranges(ev),
            "spread_attribution": spread_attribution(seasons, params),
            "note": "Each simulated season draws its own value for every unknown; case does "
            "not apply. Spread attribution: share of the variance of the statewide total "
            "explained by each unknown alone (first-order Sobol from 20 equal-count bins, less "
            "the (bins - 1) / seasons bias a pure-noise input would show, with the squared "
            "correlation alongside); the rest is the storms themselves.",
        }
    else:
        values = per_event(
            ev,
            relocation_share=RELOCATION_SHARE[case],
            shelter_open=masks["shelter_open"],
            shelter_powered=masks["shelter_powered"],
            dialysis_open=masks["dialysis_open"],
        )
        s = summarize(values, rate, ev["out25"], n_seasons, seed)
        spread = {"mode": "fixed", "case": case}
    fips, names = ev["county_fips"], ev["county_name"]
    return {
        "uncertainty": spread,
        "outlook": outlook,
        "label": OUTLOOKS.get(outlook, "Custom season: " + str((custom or {}).get("source"))),
        "storms_per_year": round(float(rate.sum()), 3),
        "years_used": len(years),
        "severity": severity_shares(rate, ev["category"]),
        "as_of": None
        if as_of_date is None
        else {
            "date": str(as_of_date),
            "share_of_season_remaining": season_remaining_share(as_of_date),
            "reading": f"{season_remaining_share(as_of_date):.0%} of Georgia storms since 1950 "
            f"came after {str(as_of_date)[5:]} (closest approach to Georgia)",
        },
        "custom_source": _check_custom(custom)["source"] if outlook == CUSTOM else None,
        "case": case,
        "relocation_share": RELOCATION_SHARE[case],
        **meta,
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


def siting_base(
    outlook: str = "long_run",
    case: str = "base",
    n_seasons: int = 5000,
    seed: int = SEED,
    sites_off: tuple[str, ...] | list[str] = (),
    assume_generator: tuple[str, ...] | list[str] = (),
    as_of_date: Any = None,
    custom: Any = None,
    **site_kwargs: Any,
) -> dict:
    rate = outlook_event_rates(outlook, custom, as_of_date)
    ev, masks, meta = _prepare(sites_off, assume_generator, case, site_kwargs)
    values = per_event(
        ev,
        relocation_share=RELOCATION_SHARE[case],
        shelter_open=masks["shelter_open"],
        shelter_powered=masks["shelter_powered"],
        dialysis_open=masks["dialysis_open"],
    )
    keep = 1.0 - FLORIDA_INFLOW
    cats = ev["category"][:, None]
    seats = ev["shelter_seats"] * masks["shelter_powered"] * masks["shelter_open"] * keep
    cap = np.where(ev["shelter_surge"][None, :] <= cats, 0.0, seats[None, :]).astype(np.float32)
    base = {
        "ev": ev,
        "meta": meta,
        "keep": keep,
        "cap": cap,
        "reach": ev["shelter_reach"].astype(np.float32),
        "seekers": (RELOCATION_SHARE[case] * ev["pd_affected"]).astype(np.float32),
        "no_chair": values["no_dialysis_chair"],
        "draws": season_draws(rate, np.random.default_rng(seed), n_seasons),
    }
    base["before"] = lacking(base, base["cap"], base["reach"])
    return base


def lacking(base: dict, cap: np.ndarray, reach: np.ndarray) -> dict[str, np.ndarray]:
    seekers = base["seekers"]
    no_seat = np.maximum(seekers - allocate(seekers, cap, reach), 0)
    seasons = worst(no_seat + base["no_chair"], base["draws"])
    state = seasons.sum(axis=1)
    return {
        "seasons": seasons,
        "state": state,
        "county_typical": np.median(seasons, axis=0),
        "county_1in10": np.quantile(seasons, 0.9, axis=0),
        "state_typical": np.median(state),
        "state_1in10": np.quantile(state, 0.9),
    }


def with_candidate(
    base: dict, cap: np.ndarray, reach: np.ndarray, cand: dict
) -> tuple[np.ndarray, np.ndarray]:
    seats = float(cand["seats"]) * base["keep"]
    if cand["kind"] == "upgrade":
        j = [str(x) for x in base["ev"]["shelter_id"]].index(cand["shelter_id"])
        flooded = base["ev"]["shelter_surge"][j] <= base["ev"]["category"]
        cap = cap.copy()
        cap[:, j] = np.where(flooded, 0.0, seats)
        return cap, reach
    column = np.full((cap.shape[0], 1), seats, np.float32)
    return (
        np.hstack([cap, column]),
        np.hstack([reach, reach_of(cand["lat"], cand["lon"]).astype(np.float32)[:, None]]),
    )


def _score(before: dict, after: dict, county: int | None) -> dict:
    if county is None:
        b1, a1 = before["state_1in10"], after["state_1in10"]
        bt, at = before["state_typical"], after["state_typical"]
    else:
        b1, a1 = before["county_1in10"][county], after["county_1in10"][county]
        bt, at = before["county_typical"][county], after["county_typical"][county]
    helped = before["county_1in10"] - after["county_1in10"] >= 1
    if county is None:
        diff = before["state"] - after["state"]
    else:
        diff = before["seasons"][:, county] - after["seasons"][:, county]
    return {
        "p_helps": round(float((diff >= 1).mean()), 4),
        "expected_reduction_per_year": round(float(diff.mean()), 1),
        "lacking_shelter_1in10_before": round(float(b1)),
        "lacking_shelter_1in10_after": round(float(a1)),
        "lacking_shelter_1in10_reduction": round(float(b1 - a1)),
        "lacking_shelter_typical_before": round(float(bt)),
        "lacking_shelter_typical_after": round(float(at)),
        "lacking_shelter_typical_reduction": round(float(bt - at)),
        "counties_helped": int(helped.sum()),
    }


def evaluate_candidates(base: dict, candidates: list[dict], county: int | None = None) -> list:
    out = []
    for cand in candidates:
        cap, reach = with_candidate(base, base["cap"], base["reach"], cand)
        out.append({**cand, **_score(base["before"], lacking(base, cap, reach), county)})
    return sorted(out, key=lambda r: -r["lacking_shelter_1in10_reduction"])


def greedy(
    base: dict, candidates: list[dict], picks: int = 3, county: int | None = None
) -> list[dict]:
    cap, reach, before = base["cap"], base["reach"], base["before"]
    chosen: list[dict] = []
    remaining = list(candidates)
    for _ in range(picks):
        best = None
        for cand in remaining:
            c2, r2 = with_candidate(base, cap, reach, cand)
            after = lacking(base, c2, r2)
            gain = _score(before, after, county)["lacking_shelter_1in10_reduction"]
            if best is None or gain > best[0]:
                best = (gain, cand, c2, r2, after)
        if best is None or best[0] <= 0:
            break
        gain, cand, cap, reach, after = best
        chosen.append(
            {**cand, "added_reduction_1in10": gain, **_score(base["before"], after, county)}
        )
        before = after
        remaining = [c for c in remaining if c is not cand]
    return chosen
