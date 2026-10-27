import argparse
import dataclasses
import json
import math
import os
import subprocess
import tempfile
from pathlib import Path

import numpy as np

from .. import data, engine, storms
from ..windfield import TrackPoint

DATA = Path(__file__).resolve().parents[1] / "data"
PROJECT = os.getenv("GOOGLE_CLOUD_PROJECT", "qwiklabs-gcp-04-edc952746633")
DATASET = os.getenv("EVAC_DATASET", "evac_prod")
SEED = 20261027
N_EVENTS = 2000
N_SEASONS = 20000
JITTER_DEG = 0.25
OUTAGE_25 = 0.25
RECEIVE_KM = 100.0
NEAR_GA_KM = 300.0
SAFFIR_KT = (64.0, 83.0, 96.0, 113.0, 137.0)
MAJOR_KT = 96.0
BACKTEST_YEARS = (2018, 2025)

BASE = {
    "generator_unrecorded_powered": False,
    "relocation_share": 0.20,
    "florida_inflow": 0.15,
    "major_bias_logit": 0.0,
    "dialysis_per_station": 1.0,
    "rates_from": 1950,
}

SWINGS = [
    {
        "gap": "medical_shelter_generators",
        "description": "Medical shelters with no generator record: none powered vs all powered",
        "record_to_collect": "Generator on site and fuel days for each medical shelter (GEMA)",
        "param": "generator_unrecorded_powered",
        "values": (False, True),
    },
    {
        "gap": "relocation_share",
        "description": "Share of power-dependent residents who seek a powered seat: 0.1 vs 0.4",
        "record_to_collect": "County special-needs registry counts and past shelter intake",
        "param": "relocation_share",
        "values": (0.10, 0.40),
    },
    {
        "gap": "florida_inflow",
        "description": "Share of Georgia receiving capacity Florida evacuees take: 0 vs 0.3",
        "record_to_collect": "Shelter intake by home state from Irma 2017 and Ian 2022",
        "param": "florida_inflow",
        "values": (0.0, 0.30),
    },
    {
        "gap": "model_major_storm_bias",
        "description": "Outage model under-predicts major storms by 0.7 logit vs no bias",
        "record_to_collect": "County outage records for more Category 3+ landfalls near Georgia",
        "param": "major_bias_logit",
        "values": (0.0, 0.7),
    },
    {
        "gap": "dialysis_surge_absorption",
        "description": "Displaced patients a dialysis station can absorb: 0.5 vs 2",
        "record_to_collect": "Each centre's extra-shift capacity in an emergency (ESRD Network 6)",
        "param": "dialysis_per_station",
        "values": (0.5, 2.0),
    },
    {
        "gap": "storm_rates",
        "description": "Storm frequency from tracks 1950-LAST vs 2000-LAST",
        "record_to_collect": "None; a modelling choice between long and recent climate",
        "param": "rates_from",
        "values": (1950, 2000),
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


def jitter(track: list[TrackPoint], dlat: float, dlon: float) -> list[TrackPoint]:
    return [dataclasses.replace(p, lat=p.lat + dlat, lon=p.lon + dlon) for p in track]


def sample_events(clim: list, rng: np.random.Generator, n: int) -> np.ndarray:
    w = np.array([a.weight for a in clim])
    return rng.choice(len(clim), size=n, p=w / w.sum())


def event_rates(seasons: np.ndarray, storm_of_event: np.ndarray, rates_from: int, last: int):
    years = last - rates_from + 1
    per_storm = np.where(seasons >= rates_from, 1.0 / years, 0.0)
    counts = np.bincount(storm_of_event, minlength=len(seasons))
    return per_storm[storm_of_event] / counts[storm_of_event]


def allocate(demand: np.ndarray, capacity: np.ndarray, reach: np.ndarray) -> np.ndarray:
    """demand (E, C), capacity (E, S), reach (C, S) -> covered (E, C), sites shared pro rata."""
    total = demand @ reach
    ratio = np.divide(capacity, total, out=np.ones_like(capacity), where=total > 0)
    return np.minimum(demand, demand * (np.minimum(ratio, 1.0) @ reach.T))


def worst_per_season(
    values: dict[str, np.ndarray], rate: np.ndarray, rng: np.random.Generator, n: int
) -> dict[str, np.ndarray]:
    lam = float(rate.sum())
    k = rng.poisson(lam, size=n)
    picks = rng.choice(len(rate), size=int(k.sum()), p=rate / lam)
    season = np.repeat(np.arange(n), k)
    out = {}
    for key, v in values.items():
        best = np.zeros((n, v.shape[1]))
        np.maximum.at(best, season, v[picks])
        out[key] = best
    return out


def poisson_quantile(mu: float, q: float) -> int:
    k, p = 0, math.exp(-mu)
    cdf = p
    while cdf < q:
        k += 1
        p *= mu / k
        cdf += p
    return k


def site_arrays(counties: list[dict], sites: dict):
    clat = np.array([c["lat"] for c in counties])
    clon = np.array([c["lon"] for c in counties])
    sh, dc = sites["medical_shelters"], sites["dialysis_centers"]

    def reach(rows):
        lat = np.array([r["lat"] for r in rows])
        lon = np.array([r["lon"] for r in rows])
        return dist_km(clat[:, None], clon[:, None], lat[None, :], lon[None, :]) <= RECEIVE_KM

    def surge_min(rows):
        return np.array([min(r["in_surge"]) if r["in_surge"] else 99 for r in rows])

    fips = [c["county_fips"] for c in counties]
    idx = {f: i for i, f in enumerate(fips)}
    dc_county = np.array([idx.get(r["county_fips"], -1) for r in dc])
    return {
        "shelter_reach": reach(sh).astype(float),
        "shelter_seats": np.array([r["seats"] for r in sh], float),
        "shelter_gen": np.array([r["generator"] for r in sh]),
        "shelter_surge": surge_min(sh),
        "dialysis_reach": reach(dc).astype(float),
        "dialysis_stations": np.array([r["stations"] for r in dc], float),
        "dialysis_surge": surge_min(dc),
        "dialysis_county": dc_county,
    }


def evaluate(outage: np.ndarray, cats: np.ndarray, counties: list[dict], s: dict, p: dict):
    pd_at_risk = outage * np.array([float(c.get("power_dependent") or 0) for c in counties])
    patients = np.array([float(c.get("dialysis_patients") or 0) for c in counties])
    flooded_dc = s["dialysis_surge"][None, :] <= cats[:, None]
    county_down = outage >= engine.DIALYSIS_DOWN_SHARE
    nc = len(counties)
    on_map = s["dialysis_county"] >= 0
    stations_by_county = np.bincount(
        s["dialysis_county"][on_map], weights=s["dialysis_stations"][on_map], minlength=nc
    )
    flooded_stations = np.zeros_like(outage)
    for j in np.flatnonzero(on_map):
        flooded_stations[:, s["dialysis_county"][j]] += flooded_dc[:, j] * s["dialysis_stations"][j]
    surge_frac = np.divide(
        flooded_stations,
        stations_by_county[None, :],
        out=np.zeros_like(outage),
        where=stations_by_county[None, :] > 0,
    )
    displaced = patients * np.where(county_down, 1.0, surge_frac)

    keep = 1.0 - p["florida_inflow"]
    powered = s["shelter_gen"] == "YES"
    if p["generator_unrecorded_powered"]:
        powered |= s["shelter_gen"] == "UNRECORDED"
    seats = s["shelter_seats"] * powered * keep
    seats = np.where(s["shelter_surge"][None, :] <= cats[:, None], 0.0, seats[None, :])
    seekers = p["relocation_share"] * pd_at_risk
    seat_gap = seekers - allocate(seekers, seats, s["shelter_reach"])

    dc_down = np.zeros_like(flooded_dc)
    valid = s["dialysis_county"] >= 0
    dc_down[:, valid] = county_down[:, s["dialysis_county"][valid]]
    chairs = s["dialysis_stations"] * p["dialysis_per_station"] * keep
    chairs = np.where(flooded_dc | dc_down, 0.0, chairs[None, :])
    chair_gap = displaced - allocate(displaced, chairs, s["dialysis_reach"])
    return {
        "pd_affected": pd_at_risk,
        "displaced": displaced,
        "uncovered": seat_gap + chair_gap,
    }


def biased(outage: np.ndarray, peaks: np.ndarray, shift: float) -> np.ndarray:
    if shift == 0:
        return outage
    o = np.clip(outage, 1e-9, 1 - 1e-9)
    logit = np.log(o / (1 - o)) + shift * (peaks >= MAJOR_KT)[:, None]
    return 1 / (1 + np.exp(-logit))


def run_case(ctx: dict, p: dict, seed: int) -> dict:
    outage = biased(ctx["outage"], ctx["peaks"], p["major_bias_logit"])
    per_event = evaluate(outage, ctx["cats"], ctx["counties"], ctx["sites"], p)
    rate = event_rates(ctx["seasons"], ctx["storm_of_event"], p["rates_from"], ctx["last"])
    seasons = worst_per_season(per_event, rate, np.random.default_rng(seed), N_SEASONS)
    return {"outage": outage, "rate": rate, "seasons": seasons}


def build(seed: int = SEED) -> dict:
    counties = data.counties()
    clat = np.array([c["lat"] for c in counties])
    clon = np.array([c["lon"] for c in counties])
    clim = storms.climatology()
    rng = np.random.default_rng(seed)
    storm_of_event = sample_events(clim, rng, N_EVENTS)
    shifts = rng.normal(0.0, JITTER_DEG, size=(N_EVENTS, 2))
    tracks = [
        jitter(clim[i].track, float(dy), float(dx))
        for i, (dy, dx) in zip(storm_of_event, shifts, strict=True)
    ]
    peak_by_storm = {i: peak_near_ga(clim[i].track, clat, clon) for i in set(storm_of_event)}
    peaks = np.array([peak_by_storm[i] for i in storm_of_event])
    result = engine.run(tracks, n_draws=N_EVENTS, seed=seed)
    order = np.argsort(result.track_of_draw, kind="stable")
    return {
        "counties": counties,
        "sites": site_arrays(counties, data.sites()),
        "outage": result.outage[order],
        "peaks": peaks,
        "cats": np.array([category(v) for v in peaks]),
        "seasons": np.array([a.season for a in clim]),
        "storm_of_event": storm_of_event,
        "last": data.tracks()["years"][1],
        "n_storms": len(clim),
    }


def county_rows(ctx: dict, base: dict) -> list[dict]:
    hits = (base["outage"] >= OUTAGE_25).astype(float)
    lam = base["rate"] @ hits
    s = base["seasons"]
    rows = []
    for j, c in enumerate(ctx["counties"]):
        rows.append(
            {
                "county_fips": c["county_fips"],
                "county_name": c["county_name"],
                "p_outage25_per_year": round(float(1 - math.exp(-lam[j])), 4),
                "power_dependent_affected_typical": round(float(np.median(s["pd_affected"][:, j]))),
                "power_dependent_affected_1in10": round(
                    float(np.quantile(s["pd_affected"][:, j], 0.9))
                ),
                "dialysis_displaced_1in10": round(float(np.quantile(s["displaced"][:, j], 0.9))),
                "uncovered_typical": round(float(np.median(s["uncovered"][:, j]))),
                "uncovered_1in10": round(float(np.quantile(s["uncovered"][:, j], 0.9))),
            }
        )
    return rows


def statewide_1in10(case: dict) -> float:
    return float(np.quantile(case["seasons"]["uncovered"].sum(1), 0.9))


def fix_ranking(ctx: dict) -> list[dict]:
    rows = []
    for sw in SWINGS:
        vals = []
        for v in sw["values"]:
            p = dict(BASE, **{sw["param"]: v})
            vals.append(statewide_1in10(run_case(ctx, p, SEED + 1)))
        lo, hi = min(vals), max(vals)
        rows.append(
            {
                "gap": sw["gap"],
                "description": sw["description"].replace("LAST", str(ctx["last"])),
                "record_to_collect": sw["record_to_collect"],
                "uncovered_1in10_low": round(lo),
                "uncovered_1in10_high": round(hi),
                "swing": round(hi - lo),
            }
        )
    return sorted(rows, key=lambda r: -r["swing"])


def backtest_counts(lam: np.ndarray, observed: dict[str, int], counties: list[dict]) -> dict:
    years = BACKTEST_YEARS[1] - BACKTEST_YEARS[0] + 1
    rows = []
    for j, c in enumerate(counties):
        mu = float(lam[j] * years)
        lo, hi = poisson_quantile(mu, 0.1), poisson_quantile(mu, 0.9)
        obs = int(observed.get(c["county_fips"], 0))
        rows.append(
            {
                "county_fips": c["county_fips"],
                "observed": obs,
                "expected": round(mu, 3),
                "p10": lo,
                "p90": hi,
                "inside": lo <= obs <= hi,
            }
        )
    total = float(lam.sum() * years)
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


def backtest(ctx: dict, base: dict, observed: dict[str, int]) -> dict:
    hits = (base["outage"] >= OUTAGE_25).astype(float)
    main = backtest_counts(base["rate"] @ hits, observed, ctx["counties"])
    recent_rate = event_rates(ctx["seasons"], ctx["storm_of_event"], 2000, ctx["last"])
    recent = backtest_counts(recent_rate @ hits, observed, ctx["counties"])
    return {
        "window": list(BACKTEST_YEARS),
        "threshold": OUTAGE_25,
        "method": "observed county-storms with peak_share >= 0.25 (not suspect) vs Poisson "
        "10th-90th percentile of the season model's expected count over the window; the "
        "statewide range treats counties as independent, so it is narrower than the truth",
        "counties": len(main["rows"]),
        "rates_from": BASE["rates_from"],
        "share_inside": main["share_inside"],
        "statewide": main["statewide"],
        "rates_from_2000": {
            "share_inside": recent["share_inside"],
            "statewide": recent["statewide"],
        },
        "rows": main["rows"],
    }


def observed_counts() -> dict[str, int]:
    sql = f"""
      SELECT fips_code, COUNTIF(peak_share >= {OUTAGE_25}) AS n
      FROM `{PROJECT}.{DATASET}.county_storm_outages`
      WHERE fips_code LIKE '13%' AND season BETWEEN {BACKTEST_YEARS[0]} AND {BACKTEST_YEARS[1]}
        AND IFNULL(peak_share_status, '') != 'suspect'
      GROUP BY 1"""
    out = subprocess.run(
        ["bq", "query", "--nouse_legacy_sql", "--format=json", "--max_rows=1000", sql],
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    return {r["fips_code"]: int(r["n"]) for r in json.loads(out)}


NOTE = (
    "Season risk uses every storm track since 1950 within 250 km of Georgia for exposure; "
    "the outage model behind it is labelled on 2018+ storms only."
)
SEASON_SCHEMA = [
    ("county_fips", "STRING", "Census county FIPS"),
    ("county_name", "STRING", "County name"),
    ("p_outage25_per_year", "FLOAT", "Chance per year of a storm leaving >= 25% of customers out"),
    (
        "power_dependent_affected_typical",
        "INTEGER",
        "Medicare power-dependent residents in outage, median season (worst storm of the season)",
    ),
    ("power_dependent_affected_1in10", "INTEGER", "Same, 90th percentile season"),
    (
        "dialysis_displaced_1in10",
        "INTEGER",
        (
            "Dialysis patients whose county is at >= 50% outage or whose centres are in the surge "
            "zone, 90th percentile season"
        ),
    ),
    (
        "uncovered_typical",
        "INTEGER",
        (
            "Seekers without a generator-recorded medical seat within 100 km plus displaced "
            "dialysis patients without a chair, median season"
        ),
    ),
    ("uncovered_1in10", "INTEGER", "Same, 90th percentile season"),
]
FIX_SCHEMA = [
    ("gap", "STRING", "Unknown or assumption"),
    ("description", "STRING", "The two values compared"),
    ("record_to_collect", "STRING", "Record that would resolve it"),
    ("uncovered_1in10_low", "INTEGER", "Statewide uncovered in a 1-in-10 season, lower setting"),
    ("uncovered_1in10_high", "INTEGER", "Statewide uncovered in a 1-in-10 season, higher setting"),
    ("swing", "INTEGER", "high minus low"),
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
        )
    subprocess.run(
        ["bq", "update", "--description", description, ref], check=True, stdout=subprocess.DEVNULL
    )


def main() -> None:
    a = argparse.ArgumentParser()
    a.add_argument("--no-load", action="store_true")
    args = a.parse_args()
    ctx = build()
    base = run_case(ctx, BASE, SEED + 1)
    counties = county_rows(ctx, base)
    ranking = fix_ranking(ctx)
    bt = backtest(ctx, base, observed_counts())
    (DATA / "season_backtest.json").write_text(json.dumps(bt, separators=(",", ":")))
    if not args.no_load:
        load(
            "scenario_season_county",
            counties,
            SEASON_SCHEMA,
            "Per-county hurricane season risk from about 2,000 simulated storms. " + NOTE,
        )
        load(
            "scenario_fix_ranking",
            ranking,
            FIX_SCHEMA,
            "Unknowns ranked by how much each moves statewide people left uncovered in a "
            "1-in-10 season. " + NOTE,
        )
    print(
        json.dumps(
            {
                "storms": ctx["n_storms"],
                "events": N_EVENTS,
                "annual_rate": round(float(base["rate"].sum()), 3),
                "statewide_uncovered_1in10": round(statewide_1in10(base)),
                "statewide_pd_affected_1in10": round(
                    float(np.quantile(base["seasons"]["pd_affected"].sum(1), 0.9))
                ),
                "backtest": {k: v for k, v in bt.items() if k != "rows"},
                "ranking": ranking,
                "top": sorted(counties, key=lambda r: -r["uncovered_1in10"])[:8],
            },
            indent=1,
        )
    )


if __name__ == "__main__":
    main()
