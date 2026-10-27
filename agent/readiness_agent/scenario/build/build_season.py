import argparse
import json
import math
import os
import subprocess
import tempfile
from pathlib import Path

import numpy as np

from .. import data, engine, season, storms
from ..season import worst_per_season
from ..windfield import TrackPoint, exposure
from .limits import MAX_BYTES_BILLED
from .synthetic import perturb, wind_chance

DATA = Path(__file__).resolve().parents[1] / "data"
PROJECT = os.getenv("GOOGLE_CLOUD_PROJECT", "qwiklabs-gcp-04-edc952746633")
DATASET = os.getenv("EVAC_DATASET", "evac_prod")
SEED = season.SEED
EVENTS_HISTORICAL = 4
EVENTS_SYNTHETIC = 12
EVENT_KEYS = (
    "pd_affected",
    "displaced",
    "out25",
    "down50",
    "category",
    "storm_of_event",
    "event_year",
    "event_synthetic",
    "event_outside_support",
    "event_shift_km",
    "event_category_change",
    "event_speed_factor",
    "event_size_factor",
)
WORST_EVENTS = 50
TOP_COUNTIES = 10
N_SEASONS_TABLE = 20000
OUTAGE_25 = 0.25
RECEIVE_KM = 100.0
NEAR_GA_KM = 300.0
SAFFIR_KT = (64.0, 83.0, 96.0, 113.0, 137.0)
MAJOR_KT = 96.0
BACKTEST_YEARS = (2018, 2025)
STABILITY_SEEDS = 20
STABILITY_SEASONS = 5000
SWITCH_SETS = ("baseline", "all_unrecorded_generators_yes", "coastal_shelters_off")

SWINGS = [
    {
        "gap": "medical_shelter_generators",
        "description": "Medical shelters with no generator record: none powered vs all powered",
        "record_to_collect": "Generator on site and fuel days for each medical shelter (GEMA)",
    },
    {
        "gap": "relocation_share",
        "description": "Share of power-dependent residents who seek a powered seat: 0.1 vs 0.4",
        "record_to_collect": "County special-needs registry counts and past shelter intake",
    },
    {
        "gap": "florida_inflow",
        "description": "Share of Georgia receiving capacity Florida evacuees take: 0 vs 0.3",
        "record_to_collect": "Shelter intake by home state from Irma 2017 and Ian 2022",
    },
    {
        "gap": "model_major_storm_bias",
        "description": "Outage model under-predicts major storms by 0.7 logit vs no bias",
        "record_to_collect": "County outage records for more Category 3+ landfalls near Georgia",
    },
    {
        "gap": "dialysis_surge_absorption",
        "description": "Displaced patients a dialysis station can absorb: 0.5 vs 2",
        "record_to_collect": "Each centre's extra-shift capacity in an emergency (ESRD Network 6)",
    },
    {
        "gap": "storm_rates",
        "description": "Storm frequency from tracks 1950-2025 vs 2000-2025",
        "record_to_collect": "None; a modelling choice between long and recent climate",
    },
]


def dist_km(lat1, lon1, lat2, lon2) -> np.ndarray:
    p1, p2 = np.radians(lat1), np.radians(lat2)
    a = (
        np.sin((p2 - p1) / 2) ** 2
        + np.cos(p1) * np.cos(p2) * np.sin(np.radians(np.asarray(lon2) - lon1) / 2) ** 2
    )
    return 2 * 6371.0 * np.arcsin(np.minimum(1.0, np.sqrt(a)))


def category(vmax_kt: float) -> int:
    return int(np.searchsorted(SAFFIR_KT, vmax_kt, side="right"))


def peak_near_ga(track: list[TrackPoint], lats: np.ndarray, lons: np.ndarray) -> float:
    plat = np.array([p.lat for p in track])
    plon = np.array([p.lon for p in track])
    near = dist_km(plat[:, None], plon[:, None], lats[None, :], lons[None, :]).min(1) < NEAR_GA_KM
    v = np.array([p.vmax_kt for p in track])
    return float(v[near].max() if near.any() else v.max())


def poisson_quantile(mu: float, q: float) -> int:
    k, p = 0, math.exp(-mu)
    cdf = p
    while cdf < q:
        k += 1
        p *= mu / k
        cdf += p
    return k


def site_arrays(counties: list[dict], sites: dict) -> dict[str, np.ndarray]:
    clat = np.array([c["lat"] for c in counties])
    clon = np.array([c["lon"] for c in counties])
    sh, dc = sites["medical_shelters"], sites["dialysis_centers"]

    def reach(rows):
        lat = np.array([r["lat"] for r in rows])
        lon = np.array([r["lon"] for r in rows])
        return dist_km(clat[:, None], clon[:, None], lat[None, :], lon[None, :]) <= RECEIVE_KM

    def surge_min(rows):
        return np.array([min(r["in_surge"]) if r["in_surge"] else 99 for r in rows], np.int8)

    idx = {c["county_fips"]: i for i, c in enumerate(counties)}
    return {
        "shelter_id": np.array([str(r["shelter_id"]) for r in sh]),
        "shelter_seats": np.array([r["seats"] for r in sh], np.float32),
        "shelter_generator": np.array([r["generator"] for r in sh]),
        "shelter_surge": surge_min(sh),
        "shelter_reach": reach(sh),
        "dialysis_ccn": np.array([str(r["ccn"]) for r in dc]),
        "dialysis_stations": np.array([r["stations"] for r in dc], np.float32),
        "dialysis_surge": surge_min(dc),
        "dialysis_county": np.array([idx.get(r["county_fips"], -1) for r in dc], np.int16),
        "dialysis_reach": reach(dc),
    }


def impacts(outage: np.ndarray, cats: np.ndarray, counties: list[dict], s: dict) -> dict:
    pd_aff = outage * np.array([float(c.get("power_dependent") or 0) for c in counties])
    patients = np.array([float(c.get("dialysis_patients") or 0) for c in counties])
    down = outage >= engine.DIALYSIS_DOWN_SHARE
    on_map = s["dialysis_county"] >= 0
    county = s["dialysis_county"][on_map]
    stations = s["dialysis_stations"][on_map].astype(np.float64)
    flooded = s["dialysis_surge"][on_map][None, :] <= cats[:, None]
    by_county = np.bincount(county, weights=stations, minlength=len(counties))
    flooded_by_county = np.zeros_like(outage)
    np.add.at(flooded_by_county.T, county, (flooded * stations).T)
    frac = np.divide(flooded_by_county, by_county, out=np.zeros_like(outage), where=by_county > 0)
    displaced = patients * np.where(down, 1.0, frac)
    return {
        "pd_affected": pd_aff.astype(np.float32),
        "displaced": displaced.astype(np.float32),
        "out25": outage >= OUTAGE_25,
        "down50": down,
    }


def biased(outage: np.ndarray, peaks: np.ndarray, shift: float) -> np.ndarray:
    o = np.clip(outage, 1e-9, 1 - 1e-9)
    logit = np.log(o / (1 - o)) + shift * (peaks >= MAJOR_KT)[:, None]
    return 1 / (1 + np.exp(-logit))


def build(seed: int = SEED) -> dict:
    counties = data.counties()
    clat = np.array([c["lat"] for c in counties])
    clon = np.array([c["lon"] for c in counties])
    clim = [a for a in storms.climatology() if season.YEARS[0] <= a.season <= season.YEARS[1]]
    rng = np.random.default_rng(seed)
    tracks, parent, synthetic, shift, dcat, speed, size = [], [], [], [], [], [], []
    for i, a in enumerate(clim):
        for _ in range(EVENTS_HISTORICAL):
            tracks.append(a.track)
            parent.append(i)
            synthetic.append(False)
            shift.append(0.0)
            dcat.append(0)
            speed.append(1.0)
            size.append(1.0)
        for _ in range(EVENTS_SYNTHETIC):
            v = perturb(a.track, rng)
            tracks.append(v.track)
            parent.append(i)
            synthetic.append(True)
            shift.append(v.shift_km)
            dcat.append(v.category_change)
            speed.append(v.speed_factor)
            size.append(v.size_factor)
    storm_of_event = np.array(parent)
    peak = np.array([peak_near_ga(t, clat, clon) for t in tracks])
    result = engine.run(tracks, n_draws=len(tracks), seed=seed)
    outage = result.outage[np.argsort(result.track_of_draw, kind="stable")]
    wind = np.array([exposure(t, clat, clon)["peak_wind_kt"] for t in tracks], np.float32)
    cats = np.array([category(v) for v in peak], np.int8)
    sites = site_arrays(counties, data.sites())
    storm_season = np.array([a.season for a in clim], np.int16)
    ev = {
        **impacts(outage, cats, counties, sites),
        **sites,
        "category": cats,
        "storm_of_event": storm_of_event.astype(np.int16),
        "storm_season": storm_season,
        "storm_name": np.array([f"{a.name} {a.season}" for a in clim]),
        "event_year": storm_season[storm_of_event],
        "event_synthetic": np.array(synthetic),
        "event_outside_support": np.array(result.outside_support),
        "event_shift_km": np.array(shift, np.float32),
        "event_category_change": np.array(dcat, np.int8),
        "event_speed_factor": np.array(speed, np.float32),
        "event_size_factor": np.array(size, np.float32),
        "county_fips": np.array([c["county_fips"] for c in counties]),
        "county_name": np.array([c["county_name"] for c in counties]),
    }
    return {"ev": ev, "outage": outage, "peak": peak, "counties": counties, "wind": wind}


def subset(ev: dict, keep: np.ndarray) -> dict:
    return {k: (v[keep] if k in EVENT_KEYS else v) for k, v in ev.items()}


def season_quantiles(ev: dict, outlook: str = "long_run") -> dict:
    values = season.per_event(ev, relocation_share=season.RELOCATION_SHARE["base"])
    rate = season.event_rates(outlook, ev["storm_season"], ev["storm_of_event"])
    seasons = worst_per_season(
        {k: values[k] for k in ("pd_affected", "lacking_shelter")},
        rate,
        np.random.default_rng(SEED),
        N_SEASONS_TABLE,
    )
    q = (0.5, 0.9, 0.99)

    def block(x: np.ndarray) -> dict:
        return dict(zip(("p50", "p90", "p99"), (round(float(v)) for v in np.quantile(x, q))))

    lacking = seasons["lacking_shelter"]
    top = np.argsort(-np.quantile(lacking, 0.9, axis=0))[:TOP_COUNTIES]
    return {
        "statewide": {k: block(v.sum(axis=1)) for k, v in seasons.items()},
        "top_counties": [
            {
                "county_fips": str(ev["county_fips"][i]),
                "county_name": str(ev["county_name"][i]),
                "lacking_shelter": block(lacking[:, i]),
                "power_dependent_affected": block(seasons["pd_affected"][:, i]),
            }
            for i in top
        ],
    }


def synthetic_check(ctx: dict, observed: dict[str, int]) -> dict:
    ev = ctx["ev"]
    syn = ev["event_synthetic"]
    out = {
        "events": int(len(syn)),
        "historical_events": int((~syn).sum()),
        "synthetic_events": int(syn.sum()),
        "synthetic_outside_support": int((syn & ev["event_outside_support"]).sum()),
        "historical_outside_support": int((~syn & ev["event_outside_support"]).sum()),
        "rules": {
            "cross_track_shift_km": "normal, sd 50, clipped to +-150, perpendicular to heading",
            "category_change": (
                "-1 / 0 / +1 with probability 0.25 / 0.5 / 0.25 at the peak near Georgia, "
                "to the next category's midpoint, never above the storm's own lifetime peak"
            ),
            "forward_speed_factor": "uniform 0.7-1.3, retimed about the closest approach",
            "size_factor": "radii from the intensity size table times lognormal(0, 0.2)",
            "weight": "each storm keeps its rate, split evenly over its events",
        },
    }
    for name, keep in (("historical", ~syn), ("synthetic", syn)):
        part = subset(ev, keep)
        rate = season.event_rates("long_run", part["storm_season"], part["storm_of_event"])
        out[f"{name}_wind"] = {
            f"p{int(t)}kt": wind_chance(ctx["wind"][keep], rate, t) for t in (34.0, 64.0)
        }
    diffs = {}
    for key in ("p34kt", "p64kt"):
        d = out["synthetic_wind"][key] - out["historical_wind"][key]
        diffs[key] = {
            "mean_abs_diff": round(float(np.abs(d).mean()), 4),
            "max_abs_diff": round(float(np.abs(d).max()), 4),
            "historical_mean": round(float(out["historical_wind"][key].mean()), 4),
            "synthetic_mean": round(float(out["synthetic_wind"][key].mean()), 4),
        }
    del out["historical_wind"], out["synthetic_wind"]
    out["per_county_wind_chance_difference"] = diffs
    hist = subset(ev, ~syn)
    out["season_historical_only"] = season_quantiles(hist)
    out["season_with_synthetic"] = season_quantiles(ev)
    long_run = {}
    out["backtest_share_inside"] = {
        "historical_only": backtest(hist, observed, long_run)["share_inside"],
        "with_synthetic": backtest(ev, observed, long_run)["share_inside"],
    }
    return out


def worst_rows(ctx: dict) -> list[dict]:
    ev = ctx["ev"]
    values = season.per_event(ev, relocation_share=season.RELOCATION_SHARE["base"])
    lacking = values["lacking_shelter"].sum(axis=1)
    affected = values["pd_affected"].sum(axis=1)
    order = [i for i in np.argsort(-affected) if ev["event_synthetic"][i]][:WORST_EVENTS]
    rows = []
    for rank, i in enumerate(order, 1):
        worst = int(np.argmax(values["pd_affected"][i]))
        rows.append(
            {
                "rank": rank,
                "parent_storm": str(ev["storm_name"][ev["storm_of_event"][i]]),
                "shift_km": round(float(ev["event_shift_km"][i]), 1),
                "category_change": int(ev["event_category_change"][i]),
                "speed_factor": round(float(ev["event_speed_factor"][i]), 2),
                "size_factor": round(float(ev["event_size_factor"][i]), 2),
                "category_near_georgia": int(ev["category"][i]),
                "outside_support": bool(ev["event_outside_support"][i]),
                "power_dependent_affected": round(float(affected[i])),
                "lacking_shelter": round(float(lacking[i])),
                "worst_county_fips": str(ev["county_fips"][worst]),
                "worst_county_name": str(ev["county_name"][worst]),
            }
        )
    return rows


WORST_SCHEMA = [
    ("rank", "INTEGER", "Rank by statewide power-dependent residents affected, 1 = worst"),
    ("parent_storm", "STRING", "Historical storm the synthetic event was perturbed from"),
    ("shift_km", "FLOAT", "Cross-track shift, km; positive is to the right of the heading"),
    ("category_change", "INTEGER", "Saffir-Simpson category change at the peak near Georgia"),
    ("speed_factor", "FLOAT", "Forward-speed multiplier"),
    ("size_factor", "FLOAT", "Wind-radius multiplier on the intensity size table"),
    ("category_near_georgia", "INTEGER", "Category at the peak within 300 km of Georgia (0 = TS)"),
    ("outside_support", "BOOLEAN", "Intensity near Georgia beyond the labelled storms' range"),
    ("power_dependent_affected", "INTEGER", "Statewide power-dependent residents x outage share"),
    ("lacking_shelter", "INTEGER", "Statewide people lacking a powered seat or dialysis chair"),
    ("worst_county_fips", "STRING", "County with the most power-dependent residents affected"),
    ("worst_county_name", "STRING", "Name of that county"),
]


def statewide_lacking(ev: dict, outlook: str = "long_run", **params) -> np.ndarray:
    params.setdefault("relocation_share", season.RELOCATION_SHARE["base"])
    values = {"x": season.per_event(ev, **params)["lacking_shelter"]}
    rate = season.outlook_event_rates(outlook, ev=ev)
    seasons = worst_per_season(values, rate, np.random.default_rng(SEED), N_SEASONS_TABLE)
    return seasons["x"].sum(1)


def fix_ranking(ctx: dict, ev: dict) -> list[dict]:
    unrec = np.isin(ev["shelter_generator"], ["YES", "UNRECORDED"])
    shifted = biased(ctx["outage"], ctx["peak"], 0.7)
    bias_ev = {**ev, **impacts(shifted, ev["category"], ctx["counties"], ev)}
    pairs = {
        "medical_shelter_generators": (
            statewide_lacking(ev),
            statewide_lacking(ev, shelter_powered=unrec),
        ),
        "relocation_share": (
            statewide_lacking(ev, relocation_share=0.1),
            statewide_lacking(ev, relocation_share=0.4),
        ),
        "florida_inflow": (
            statewide_lacking(ev, florida_inflow=0.0),
            statewide_lacking(ev, florida_inflow=0.3),
        ),
        "model_major_storm_bias": (statewide_lacking(ev), statewide_lacking(bias_ev)),
        "dialysis_surge_absorption": (
            statewide_lacking(ev, dialysis_per_station=0.5),
            statewide_lacking(ev, dialysis_per_station=2.0),
        ),
        "storm_rates": (statewide_lacking(ev), statewide_lacking(ev, "recent")),
    }
    rows = []
    for sw in SWINGS:
        a, b = pairs[sw["gap"]]
        worse, better = (a, b) if np.quantile(a, 0.9) >= np.quantile(b, 0.9) else (b, a)
        lo, hi = float(np.quantile(better, 0.9)), float(np.quantile(worse, 0.9))
        paired = sw["gap"] != "storm_rates"
        diff = worse - better
        rows.append(
            {
                **sw,
                "uncovered_1in10_low": round(lo),
                "uncovered_1in10_high": round(hi),
                "swing": round(hi - lo),
                "p_helps": round(float((diff >= 1).mean()), 4) if paired else None,
                "expected_reduction_per_year": round(float(diff.mean()), 1) if paired else None,
            }
        )
    return sorted(rows, key=lambda r: -r["swing"])


def stability(seeds: int = STABILITY_SEEDS, n: int = STABILITY_SEASONS) -> dict:
    values = [
        season.run_season(n_seasons=n, seed=SEED + k)["statewide"]["lacking_shelter"]["total"][
            "one_in_10"
        ]
        for k in range(seeds)
    ]
    return {
        "seeds": seeds,
        "seasons_per_run": n,
        "min": int(min(values)),
        "median": float(np.median(values)),
        "max": int(max(values)),
    }


def stability_text(st: dict) -> str:
    return (
        f"Stability: statewide lacking shelter in a 1-in-10 season across {st['seeds']} seeds of "
        f"{st['seasons_per_run']:,} simulated seasons: min {st['min']:,}, median "
        f"{st['median']:,.0f}, max {st['max']:,}."
    )


def season_p_rows(outlook: str) -> list[dict]:
    r = season.run_season(outlook, n_seasons=N_SEASONS_TABLE)

    def row(scope: str, fips, name, p: dict) -> dict:
        return {
            "outlook": outlook,
            "scope": scope,
            "county_fips": fips,
            "county_name": name,
            **{k: v for k, v in p.items() if k != "label"},
        }

    return [row("statewide", None, None, r["statewide"]["probability"])] + [
        row("county", c["county_fips"], c["county_name"], c["probability"]) for c in r["counties"]
    ]


def severity_backtest(ev: dict, observed: dict[str, int], long_run_share: float) -> dict:
    years = list(range(BACKTEST_YEARS[0], BACKTEST_YEARS[1] + 1))
    base = season.outlook_event_rates("long_run", ev=ev)
    cat = ev["category"]
    year_of_event = ev["storm_season"][ev["storm_of_event"]]
    replay = ~ev["event_synthetic"] if "event_synthetic" in ev else np.ones(len(cat), bool)
    out25 = ev["out25"].astype(np.float64)
    count_only, severity = np.zeros(out25.shape[1]), np.zeros(out25.shape[1])
    for y in years:
        n = int((ev["storm_season"] == y).sum())
        mine = (year_of_event == y) & replay
        if n == 0 or base[mine].sum() <= 0:
            continue
        w = base[mine]
        h = float(w[cat[mine] >= 1].sum() / w.sum())
        m = float(w[cat[mine] >= 3].sum() / w.sum())
        count_only += (base * n / base.sum()) @ out25
        heavy = season.reweight(base, cat, h, m)
        severity += (heavy * n / heavy.sum()) @ out25
    fips = ev["county_fips"]
    c = coverage(count_only, observed, fips)
    s = coverage(severity, observed, fips)
    better = s["share_inside"] > c["share_inside"]
    return {
        "method": "hindsight upper bound: each year uses its own observed count of storms near "
        "Georgia (count only), or its count plus the Cat 1+ and Cat 3+ shares of its storms' "
        "historical replays (severity). No past forecasts are used, so this bounds what a "
        "perfect outlook could add.",
        "count_only_share_inside": c["share_inside"],
        "severity_share_inside": s["share_inside"],
        "count_only_statewide": c["statewide"],
        "severity_statewide": s["statewide"],
        "long_run_share_inside": long_run_share,
        "verdict": (
            f"Severity reweighting {'improves' if better else 'does not improve'} "
            f"on count only: {s['share_inside']:.1%} vs {c['share_inside']:.1%} of counties inside "
            f"(long run {long_run_share:.1%})."
        ),
    }


def county_lambda(ev: dict, outlook: str) -> np.ndarray:
    rate = season.outlook_event_rates(outlook, ev=ev)
    return rate @ ev["out25"].astype(np.float64)


def coverage(mu: np.ndarray, observed: dict[str, int], fips: np.ndarray) -> dict:
    rows = []
    for f, m in zip(fips, mu, strict=True):
        lo, hi = poisson_quantile(float(m), 0.1), poisson_quantile(float(m), 0.9)
        obs = int(observed.get(str(f), 0))
        rows.append(
            {
                "county_fips": str(f),
                "observed": obs,
                "expected": round(float(m), 3),
                "p10": lo,
                "p90": hi,
                "inside": lo <= obs <= hi,
            }
        )
    total = float(mu.sum())
    return {
        "share_inside": round(sum(r["inside"] for r in rows) / len(rows), 3),
        "statewide": {
            "observed": sum(r["observed"] for r in rows),
            "expected": round(total, 1),
            "p10": poisson_quantile(total, 0.1),
            "p90": poisson_quantile(total, 0.9),
        },
        "rows": rows,
    }


def backtest(ev: dict, observed: dict[str, int], long_run_state: dict) -> dict:
    years = list(range(BACKTEST_YEARS[0], BACKTEST_YEARS[1] + 1))
    lam = {o: county_lambda(ev, o) for o in ("long_run", "recent", "la_nina", "neutral", "el_nino")}
    phases = {y: season.enso_phase(y) for y in years}
    fips = ev["county_fips"]
    long_run = coverage(lam["long_run"] * len(years), observed, fips)
    recent = coverage(lam["recent"] * len(years), observed, fips)
    cond = coverage(np.sum([lam[phases[y]] for y in years], axis=0), observed, fips)
    better = cond["share_inside"] > long_run["share_inside"]
    return {
        "window": [BACKTEST_YEARS[0], BACKTEST_YEARS[1]],
        "threshold": OUTAGE_25,
        "method": (
            "observed county-storms with peak_share >= 0.25 (not suspect) vs Poisson 10th-90th "
            "percentile of the season model's expected count over the window; the statewide "
            "range treats counties as independent, so it is narrower than the truth"
        ),
        "counties": len(long_run["rows"]),
        "share_inside": long_run["share_inside"],
        "statewide": long_run["statewide"],
        "rates_from_2000": {k: recent[k] for k in ("share_inside", "statewide")},
        "enso_conditional": {
            "phases": {str(y): p for y, p in phases.items()},
            "share_inside": cond["share_inside"],
            "statewide": cond["statewide"],
            "verdict": (
                "Conditioning each year on its Aug-Oct ENSO phase "
                f"{'improves' if better else 'does not improve'} coverage: "
                f"{cond['share_inside']:.1%} of counties inside vs "
                f"{long_run['share_inside']:.1%} with the long-run rate "
                f"({sum(r['inside'] for r in cond['rows'])} vs "
                f"{sum(r['inside'] for r in long_run['rows'])} of {len(fips)} counties)."
            ),
        },
        "long_run_statewide": long_run_state,
        "severity_hindsight": severity_backtest(ev, observed, long_run["share_inside"]),
        "rows": long_run["rows"],
    }


def observed_counts() -> dict[str, int]:
    sql = f"""
      SELECT fips_code, COUNTIF(peak_share >= @outage_share) AS n
      FROM `{PROJECT}.{DATASET}.county_storm_outages`
      WHERE fips_code LIKE '13%' AND season BETWEEN @first_year AND @last_year
        AND IFNULL(peak_share_status, '') != 'suspect'
      GROUP BY 1"""
    out = subprocess.run(
        [
            "bq",
            "query",
            "--nouse_legacy_sql",
            "--format=json",
            "--max_rows=1000",
            f"--maximum_bytes_billed={MAX_BYTES_BILLED}",
            f"--parameter=outage_share:FLOAT64:{OUTAGE_25}",
            f"--parameter=first_year:INT64:{BACKTEST_YEARS[0]}",
            f"--parameter=last_year:INT64:{BACKTEST_YEARS[1]}",
            sql,
        ],
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    return {r["fips_code"]: int(r["n"]) for r in json.loads(out)}


def switches(name: str, ev: dict) -> dict:
    if name == "all_unrecorded_generators_yes":
        ids = ev["shelter_id"][ev["shelter_generator"] == "UNRECORDED"]
        return {"assume_generator": [str(x) for x in ids]}
    if name == "coastal_shelters_off":
        return {"sites_off": [str(x) for x in ev["shelter_id"][ev["shelter_surge"] <= 3]]}
    return {}


def flat(r: dict) -> dict:
    ls, nt = r["lacking_shelter"], r["needing_transport"]
    out = {
        "power_dependent_affected": r["power_dependent_affected"],
        "no_powered_seat": ls["no_powered_seat"],
        "no_dialysis_chair": ls["no_dialysis_chair"],
        "no_vehicle": nt["no_vehicle"],
        "no_vehicle_low": nt["no_vehicle_low"],
    }
    row = {}
    for k, v in out.items():
        row[f"{k}_typical"] = v["typical"]
        row[f"{k}_1in10"] = v["one_in_10"]
    return row


def season_rows(ev: dict, outlook: str) -> list[dict]:
    r = season.run_season(outlook, n_seasons=N_SEASONS_TABLE)
    rate = season.outlook_event_rates(outlook, ev=ev)
    d = worst_per_season(
        {"d": ev["displaced"]}, rate, np.random.default_rng(SEED), N_SEASONS_TABLE
    )["d"]
    displaced = np.quantile(d, 0.9, axis=0)
    rows = []
    for i, c in enumerate(r["counties"]):
        ls = c["lacking_shelter"]
        rows.append(
            {
                "outlook": outlook,
                "county_fips": c["county_fips"],
                "county_name": c["county_name"],
                "p_outage25_per_year": c["p_outage25_per_year"],
                "power_dependent_affected_typical": c["power_dependent_affected"]["typical"],
                "power_dependent_affected_1in10": c["power_dependent_affected"]["one_in_10"],
                "dialysis_displaced_1in10": round(float(displaced[i])),
                "uncovered_typical": ls["total"]["typical"],
                "uncovered_1in10": ls["total"]["one_in_10"],
                "no_powered_seat_1in10": ls["no_powered_seat"]["one_in_10"],
                "no_dialysis_chair_1in10": ls["no_dialysis_chair"]["one_in_10"],
                "no_vehicle_1in10": c["needing_transport"]["no_vehicle"]["one_in_10"],
                "storms_per_year": r["storms_per_year"],
            }
        )
    return rows


def batch_rows(ev: dict) -> list[dict]:
    rows = []
    for outlook in season.OUTLOOKS:
        for sw in SWITCH_SETS:
            for case in season.RELOCATION_SHARE:
                r = season.run_season(outlook, case=case, **switches(sw, ev))
                key = {
                    "outlook": outlook,
                    "switch_set": sw,
                    "case": case,
                    "storms_per_year": r["storms_per_year"],
                }
                st = r["statewide"]
                rows.append(
                    {
                        **key,
                        "scope": "statewide",
                        "county_fips": None,
                        "county_name": None,
                        "p_outage25_per_year": st["p_any_county_outage25_per_year"],
                        **flat(st),
                    }
                )
                for c in r["counties"]:
                    rows.append(
                        {
                            **key,
                            "scope": "county",
                            "county_fips": c["county_fips"],
                            "county_name": c["county_name"],
                            "p_outage25_per_year": c["p_outage25_per_year"],
                            **flat(c),
                        }
                    )
    return rows


NOTE = (
    "Season risk uses every storm track 1950-2025 within 250 km of Georgia for exposure; "
    "the outage model behind it is labelled on 2018+ storms only. Outlooks reweight those "
    "storms: long_run (default), recent (2000-2025), la_nina / neutral / el_nino (years by "
    "Aug-Oct ONI), noaa_aug_2026 (outside forecast input: NOAA CPC August 2026 outlook, count "
    "and Cat 1+ / Cat 3+ shares scaled to its midpoints, "
    f"{season.NOAA_URL})."
)
TYPICAL = "median season (worst storm of the season)"
ONE_IN_10 = "90th percentile season"
OUTLOOK_FIELD = ("outlook", "STRING", "Season outlook used to weight storms")
STORMS_FIELD = ("storms_per_year", "FLOAT", "Storms per year near Georgia under this outlook")
SEASON_SCHEMA = [
    OUTLOOK_FIELD,
    ("county_fips", "STRING", "Census county FIPS"),
    ("county_name", "STRING", "County name"),
    ("p_outage25_per_year", "FLOAT", "Chance per year of a storm leaving >= 25% of customers out"),
    (
        "power_dependent_affected_typical",
        "INTEGER",
        "Medicare power-dependent residents in outage, " + TYPICAL,
    ),
    ("power_dependent_affected_1in10", "INTEGER", "Same, " + ONE_IN_10),
    (
        "dialysis_displaced_1in10",
        "INTEGER",
        "Dialysis patients whose county is at >= 50% outage or whose centres are in the surge "
        "zone, " + ONE_IN_10,
    ),
    (
        "uncovered_typical",
        "INTEGER",
        "Lacking shelter: seekers without a generator-recorded medical seat within 100 km plus "
        "displaced dialysis patients without a chair, " + TYPICAL,
    ),
    ("uncovered_1in10", "INTEGER", "Same, " + ONE_IN_10),
    ("no_powered_seat_1in10", "INTEGER", "Seekers without a powered seat, " + ONE_IN_10),
    ("no_dialysis_chair_1in10", "INTEGER", "Displaced patients without a chair, " + ONE_IN_10),
    (
        "no_vehicle_1in10",
        "INTEGER",
        "Needing transport: power-dependent affected x county no-vehicle share of 65+ "
        "households (ACS B25045), " + ONE_IN_10 + "; never added to uncovered",
    ),
    STORMS_FIELD,
]
FIX_SCHEMA = [
    ("gap", "STRING", "Unknown or assumption"),
    ("description", "STRING", "The two values compared"),
    ("record_to_collect", "STRING", "Record that would resolve it"),
    ("uncovered_1in10_low", "INTEGER", "Statewide lacking shelter in a 1-in-10 season, lower"),
    ("uncovered_1in10_high", "INTEGER", "Statewide lacking shelter in a 1-in-10 season, higher"),
    ("swing", "INTEGER", "high minus low"),
    (
        "p_helps",
        "FLOAT",
        (
            "Share of simulated seasons in which the better setting leaves at least 1 fewer "
            "person lacking shelter; same seasons for both settings; null for storm_rates, "
            "whose two settings simulate different seasons"
        ),
    ),
    ("expected_reduction_per_year", "FLOAT", "Mean difference across the same seasons"),
]
SEASON_P_SCHEMA = [
    OUTLOOK_FIELD,
    ("scope", "STRING", "statewide or county"),
    ("county_fips", "STRING", "Census county FIPS; null for statewide"),
    ("county_name", "STRING", "County name; null for statewide"),
    ("p_lacking_shelter_any", "FLOAT", "Share of simulated seasons with anyone lacking shelter"),
    ("p_lacking_shelter_50", "FLOAT", "Share of simulated seasons with 50 or more"),
    (
        "p_no_dialysis_chair_any",
        "FLOAT",
        "Share of simulated seasons with any dialysis patient without a chair",
    ),
]
BATCH_SCHEMA = [
    OUTLOOK_FIELD,
    (
        "switch_set",
        "STRING",
        (
            "baseline (registry), all_unrecorded_generators_yes, or coastal_shelters_off "
            "(medical shelters in the Category 3 surge zone switched off)"
        ),
    ),
    ("case", "STRING", "Relocation share: low 0.1, base 0.2, high 0.4"),
    STORMS_FIELD,
    ("scope", "STRING", "statewide or county"),
    ("county_fips", "STRING", "Census county FIPS; null for statewide"),
    ("county_name", "STRING", "County name; null for statewide"),
    (
        "p_outage25_per_year",
        "FLOAT",
        "County: chance per year of >= 25% outage. Statewide: chance any county reaches it",
    ),
    ("power_dependent_affected_typical", "INTEGER", "Power-dependent in outage, " + TYPICAL),
    ("power_dependent_affected_1in10", "INTEGER", "Same, " + ONE_IN_10),
    ("no_powered_seat_typical", "INTEGER", "Lacking shelter: no powered seat, " + TYPICAL),
    ("no_powered_seat_1in10", "INTEGER", "Same, " + ONE_IN_10),
    ("no_dialysis_chair_typical", "INTEGER", "Lacking shelter: no dialysis chair, " + TYPICAL),
    ("no_dialysis_chair_1in10", "INTEGER", "Same, " + ONE_IN_10),
    (
        "no_vehicle_typical",
        "INTEGER",
        "Needing transport: affected x 65+ no-vehicle share, " + TYPICAL,
    ),
    ("no_vehicle_1in10", "INTEGER", "Same, " + ONE_IN_10),
    (
        "no_vehicle_low_typical",
        "INTEGER",
        "Needing transport, low case: affected x all-household no-vehicle share, " + TYPICAL,
    ),
    ("no_vehicle_low_1in10", "INTEGER", "Same, " + ONE_IN_10),
]


def load(name: str, rows: list[dict], schema: list[tuple], description: str) -> None:
    ref = f"{PROJECT}:{DATASET}.{name}"
    with tempfile.TemporaryDirectory() as tmp:
        body = Path(tmp) / "rows.json"
        body.write_text("\n".join(json.dumps(r) for r in rows))
        spec = Path(tmp) / "schema.json"
        spec.write_text(
            json.dumps([{"name": n, "type": t, "description": d} for n, t, d in schema])
        )
        subprocess.run(
            ["bq", "load", "--replace", "--source_format=NEWLINE_DELIMITED_JSON", ref, body, spec],
            check=True,
            stdout=subprocess.DEVNULL,
        )
    subprocess.run(
        ["bq", "update", "--description", description, ref], check=True, stdout=subprocess.DEVNULL
    )


def main() -> None:
    a = argparse.ArgumentParser()
    a.add_argument("--no-load", action="store_true")
    a.add_argument("--skip-batch", action="store_true")
    args = a.parse_args()
    ctx = build()
    np.savez_compressed(season.EVENTS_FILE, **ctx["ev"])
    season.events.cache_clear()
    ev = season.events()
    counties = [r for o in season.OUTLOOKS for r in season_rows(ev, o)]
    ranking = fix_ranking(ctx, ev)
    p_rows = [r for o in season.OUTLOOKS for r in season_p_rows(o)]
    stable = stability()
    long_run = season.run_season("long_run", n_seasons=N_SEASONS_TABLE)["statewide"]
    observed = observed_counts()
    bt = backtest(ev, observed, long_run)
    check = synthetic_check(ctx, observed)
    (DATA / "season_synthetic_check.json").write_text(json.dumps(check, indent=1) + "\n")
    worst = worst_rows(ctx)
    (DATA / "season_backtest.json").write_text(json.dumps(bt, separators=(",", ":")))
    batch = [] if args.skip_batch else batch_rows(ev)
    if not args.no_load:
        load(
            "scenario_season_county",
            counties,
            SEASON_SCHEMA,
            f"Per-county hurricane season risk per outlook from {len(ev['category']):,} simulated "
            "events (historical replays and synthetic variants). " + NOTE,
        )
        load(
            "scenario_season_county_p",
            p_rows,
            SEASON_P_SCHEMA,
            f"Probabilities per outlook as shares of {N_SEASONS_TABLE:,} simulated seasons "
            "(worst storm of each season). " + stability_text(stable) + " " + NOTE,
        )
        load(
            "scenario_fix_ranking",
            ranking,
            FIX_SCHEMA,
            "Unknowns ranked by how much each moves statewide people lacking shelter in a "
            "1-in-10 season (long_run outlook), with p_helps and expected reduction per year "
            "over the same simulated seasons. " + stability_text(stable) + " " + NOTE,
        )
        load(
            "scenario_worst_events",
            worst,
            WORST_SCHEMA,
            f"The {WORST_EVENTS} synthetic storms with the most power-dependent residents "
            "affected statewide, each a historical storm shifted, re-intensified, re-timed and "
            "resized. " + NOTE,
        )
        if batch:
            load(
                "scenario_batch",
                batch,
                BATCH_SCHEMA,
                "Every outlook x switch set x relocation case, statewide and per county, from "
                "readiness_agent.scenario.season.run_season with 5,000 seasons. " + NOTE,
            )
    print(
        json.dumps(
            {
                "storms": len(ev["storm_season"]),
                "events": len(ev["category"]),
                "events_npz_kb": round(season.EVENTS_FILE.stat().st_size / 1024),
                "outlook_rates": {
                    o: round(season.storms_per_year(o, ev["storm_season"]), 3)
                    for o in season.OUTLOOKS
                },
                "long_run_statewide": long_run,
                "backtest": {k: v for k, v in bt.items() if k != "rows"},
                "ranking": ranking,
                "stability": stable,
                "severity": {
                    o: season.severity_shares(season.outlook_event_rates(o), ev["category"])
                    for o in season.OUTLOOKS
                },
                "p_rows": len(p_rows),
                "season_rows": len(counties),
                "batch_rows": len(batch),
                "synthetic_check": check,
                "worst_events": worst[:5],
            },
            indent=1,
        )
    )


if __name__ == "__main__":
    main()
