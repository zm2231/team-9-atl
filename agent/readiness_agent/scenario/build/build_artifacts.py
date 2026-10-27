import csv
import json
import math
import os
import subprocess
import sys
from collections import defaultdict

import numpy as np
from google.cloud import bigquery

from .. import data, storms
from ..model import FEATURES, expit, transform
from ..windfield import NM_KM, TrackPoint, exposure, interpolate_hourly

DATA = data.DATA_DIR
PROJECT = os.getenv("GOOGLE_CLOUD_PROJECT", "qwiklabs-gcp-04-edc952746633")
DATASET = os.getenv("EVAC_DATASET", "evac_prod")
CLIMATE_FROM = 1950
SIZE_FROM = 2004
TRACK_KM = 800.0
FL_PEOPLE_PER_CUSTOMER = 2.2
LAND_STATES = {"TX", "LA", "MS", "AL", "FL", "GA", "SC", "NC", "TN", "VA"}
EM_ITERS = 8
LOSO_DRAWS = 1000
SEED = 20261027
BIG_STORM_SHARE = 0.10
FACILITY_BEDS_REF = "origin/scenario-season:agent/readiness_agent/scenario/data/facility_beds.json"


def table(name: str) -> str:
    return f"`{PROJECT}.{DATASET}.{name}`"


def query(bq: bigquery.Client, sql: str) -> list:
    return list(bq.query(sql).result())


def facility_beds() -> dict:
    local = DATA / "facility_beds.json"
    if local.exists():
        return json.loads(local.read_text())["counties"]
    try:
        raw = subprocess.run(
            ["git", "show", FACILITY_BEDS_REF], capture_output=True, text=True, check=True
        ).stdout
    except subprocess.CalledProcessError:
        return {}
    return json.loads(raw)["counties"]


def build_counties(bq: bigquery.Client) -> list[dict]:
    rows = query(bq, f"""
      SELECT t.county_fips, p.county AS county_name,
        SUM(t.lat * t.total_pop) / SUM(t.total_pop) AS lat,
        SUM(t.lon * t.total_pop) / SUM(t.total_pop) AS lon,
        SUM(t.total_pop) AS pop,
        ANY_VALUE(p.power_dependent_dme) AS power_dependent,
        ANY_VALUE(p.o2_services_any_dme) AS oxygen,
        ANY_VALUE(p.home_health_services_any_dme) AS home_health,
        ANY_VALUE(p.facility_esrd_dialysis_any_dme) AS dialysis_patients,
        ANY_VALUE(p.power_dependent_is_censored) AS censored
      FROM {table('vulnerability_tracts_clean')} t
      JOIN {table('power_dependent_counties_clean')} p ON p.fips_code = t.county_fips
      WHERE t.total_pop > 0
      GROUP BY 1, 2 ORDER BY 1""")
    beds = facility_beds()
    return [
        {
            "county_fips": r.county_fips, "county_name": r.county_name,
            "lat": round(r.lat, 5), "lon": round(r.lon, 5), "pop": int(r.pop),
            "power_dependent": int(r.power_dependent or 0), "oxygen": int(r.oxygen or 0),
            "home_health": int(r.home_health or 0),
            "dialysis_patients": int(r.dialysis_patients or 0),
            "power_dependent_censored": bool(r.censored),
            "nursing_home_beds": int(beds.get(r.county_fips, {}).get("nursing_home_beds", 0)),
            "assisted_living_beds": int(
                beds.get(r.county_fips, {}).get("assisted_living_beds", 0)
            ),
        }
        for r in rows
    ]


def read_gazetteer(path: str) -> list[dict]:
    with open(path, newline="") as f:
        reader = csv.DictReader(f, delimiter="\t")
        return [{k.strip(): v.strip() for k, v in r.items()} for r in reader]


def mean_radius_km(r) -> float | None:
    vals = [
        v for v in (r.USA_R34_NE, r.USA_R34_SE, r.USA_R34_SW, r.USA_R34_NW)
        if v is not None and v > 0
    ]
    return sum(vals) / len(vals) * NM_KM if vals else None


def size_table(obs: list[tuple[float, float, float]]) -> list[list[float]]:
    arr = np.array(obs)
    out = []
    for center in range(25, 175, 10):
        sel = arr[np.abs(arr[:, 0] - center) <= 5]
        if len(sel) < 10:
            continue
        r34 = sel[sel[:, 0] >= 34, 2] if center >= 34 else np.array([0.0])
        out.append([
            float(center), round(float(np.median(sel[:, 1])), 1),
            round(float(np.median(r34)) if len(r34) else 0.0, 1),
        ])
    return out


def build_tracks(bq: bigquery.Client, gazetteer: list[dict]) -> dict:
    rows = query(bq, f"""
      SELECT SID, NAME, SEASON, ISO_TIME, USA_LAT, USA_LON, USA_WIND, USA_RMW,
        USA_R34_NE, USA_R34_SE, USA_R34_SW, USA_R34_NW, dist_ga_km
      FROM {table('storm_tracks_ibtracs')}
      WHERE SEASON >= {CLIMATE_FROM} AND USA_WIND IS NOT NULL AND USA_LAT IS NOT NULL
        AND EXTRACT(HOUR FROM ISO_TIME) IN (0, 6, 12, 18) AND EXTRACT(MINUTE FROM ISO_TIME) = 0
        AND SID IN (SELECT SID FROM {table('storm_tracks_ibtracs')}
                    GROUP BY SID HAVING MIN(dist_ga_km) < {TRACK_KM})
      ORDER BY SID, ISO_TIME""")
    by_sid = defaultdict(list)
    for r in rows:
        by_sid[r.SID].append(r)
    obs = []
    for g in by_sid.values():
        for r in g:
            r34 = mean_radius_km(r)
            if g[0].SEASON >= SIZE_FROM and r.USA_RMW and r.USA_RMW > 0 and (
                r34 is not None or r.USA_WIND < 34
            ):
                obs.append((float(r.USA_WIND), float(r.USA_RMW) * NM_KM, r34 or 0.0))
    sizes = size_table(obs)

    def typical(v: float) -> tuple[float, float]:
        row = min(sizes, key=lambda s: abs(s[0] - v))
        return row[1], row[2] if v >= 34 else 0.0

    storms_out = []
    for sid in sorted(by_sid):
        g = by_sid[sid]
        t0 = g[0].ISO_TIME
        points = []
        for r in g:
            vmax = float(r.USA_WIND)
            rmw_t, r34_t = typical(vmax)
            rmw = float(r.USA_RMW) * NM_KM if r.USA_RMW and r.USA_RMW > 0 else None
            r34 = mean_radius_km(r) if vmax >= 34 else 0.0
            filled = int(rmw is None or r34 is None)
            points.append([
                round((r.ISO_TIME - t0).total_seconds() / 3600, 1),
                round(float(r.USA_LAT), 2), round(float(r.USA_LON), 2), vmax,
                round(rmw if rmw is not None else rmw_t, 1),
                round(r34 if r34 is not None else r34_t, 1),
                r.ISO_TIME.month, filled,
            ])
        storms_out.append({
            "sid": sid, "name": str(g[0].NAME).title(), "season": int(g[0].SEASON),
            "dmin_ga_km": round(float(min(r.dist_ga_km for r in g)), 1), "points": points,
        })
    land = [
        [round(float(r["INTPTLAT"]), 3), round(float(r["INTPTLONG"]), 3)]
        for r in gazetteer if r["USPS"] in LAND_STATES
    ]
    return {
        "years": [CLIMATE_FROM, max(s["season"] for s in storms_out)],
        "columns": ["hour", "lat", "lon", "vmax_kt", "rmw_km", "r34_km", "month", "size_filled"],
        "size_by_intensity": sizes,
        "land_points": land,
        "storms": storms_out,
    }


def storm_track(storm: dict) -> list[TrackPoint]:
    return interpolate_hourly([TrackPoint(*p[:6]) for p in storm["points"]])


def label_rows(bq: bigquery.Client, counties: list[dict], gazetteer: list[dict], tracks: dict):
    labels = query(bq, f"""
      SELECT fips_code, sid, peak_share, eaglei_total_customers_2024 AS customers
      FROM {table('county_storm_outages')}
      WHERE peak_share_status != 'suspect' AND peak_share IS NOT NULL
        AND eaglei_total_customers_2024 > 0
      ORDER BY sid, fips_code""")
    place = {c["county_fips"]: (c["lat"], c["lon"], float(c["pop"])) for c in counties}
    gaz = {r["GEOID"]: (float(r["INTPTLAT"]), float(r["INTPTLONG"])) for r in gazetteer}
    for r in labels:
        if r.fips_code not in place and r.fips_code in gaz:
            lat, lon = gaz[r.fips_code]
            place[r.fips_code] = (lat, lon, float(r.customers) * FL_PEOPLE_PER_CUSTOMER)
    by_sid = {s["sid"]: s for s in tracks["storms"]}
    out = defaultdict(list)
    for r in labels:
        if r.fips_code in place:
            out[r.sid].append(r)
    fips, sids, feats, share, cust = [], [], [], [], []
    for sid in sorted(out):
        group = out[sid]
        lat = np.array([place[r.fips_code][0] for r in group])
        lon = np.array([place[r.fips_code][1] for r in group])
        e = exposure(storm_track(by_sid[sid]), lat, lon)
        e["pop"] = np.array([place[r.fips_code][2] for r in group])
        feats.append(np.column_stack([e[f] for f in FEATURES]))
        for r in group:
            fips.append(r.fips_code)
            sids.append(sid)
            share.append(float(r.peak_share))
            cust.append(float(r.customers))
    return np.array(fips), np.array(sids), np.vstack(feats), np.array(share), np.array(cust)


def logit(p: np.ndarray) -> np.ndarray:
    p = np.clip(p, 1e-6, 1 - 1e-6)
    return np.log(p / (1 - p))


def fit(feats, fips, sids, share, cust, county_ids):
    xr = transform(feats)
    mu, sd = xr.mean(0), xr.std(0)
    sd[sd == 0] = 1.0
    z = (xr - mu) / sd
    storm_ids = sorted(set(sids))
    ci = {c: i for i, c in enumerate(county_ids)}
    si = {s: i for i, s in enumerate(storm_ids)}
    k = 1 + len(FEATURES)
    nc, ns = len(county_ids), len(storm_ids)
    x = np.zeros((len(z), k + nc + ns))
    x[:, 0] = 1.0
    x[:, 1:k] = z
    rows = np.arange(len(z))
    x[rows, k + np.array([ci[f] for f in fips])] = 1.0
    x[rows, k + nc + np.array([si[s] for s in sids])] = 1.0
    y = logit((share * cust + 0.5) / (cust + 1.0))
    tau_c, tau_s = 0.70, 0.80
    for _ in range(EM_ITERS):
        prior = np.r_[4.0, np.repeat(1.5, len(FEATURES)), np.repeat(tau_c, nc), np.repeat(tau_s, ns)]
        cov_unit = np.linalg.pinv(x.T @ x + np.diag(1 / prior**2))
        coef = cov_unit @ x.T @ y
        sigma = max(float(np.sqrt(np.mean((y - x @ coef) ** 2))), 0.25)
        cov = sigma**2 * cov_unit
        diag = np.diag(cov)
        tau_c = float(np.sqrt(np.mean(coef[k:k + nc] ** 2 + diag[k:k + nc])))
        tau_s = float(np.sqrt(np.mean(coef[k + nc:] ** 2 + diag[k + nc:])))
    keep = np.arange(k + nc)
    return {
        "mu": mu, "sd": sd, "mean": coef[keep], "cov": cov[np.ix_(keep, keep)],
        "tau_storm": tau_s, "tau_county": tau_c, "sigma": sigma, "county_ids": county_ids,
    }


def predict(m: dict, feats, fips, rng, n_draws) -> np.ndarray:
    z = (transform(feats) - m["mu"]) / m["sd"]
    k = 1 + len(FEATURES)
    ci = {c: i for i, c in enumerate(m["county_ids"])}
    x = np.zeros((len(z), len(m["mean"])))
    x[:, 0] = 1.0
    x[:, 1:k] = z
    for r, f in enumerate(fips):
        x[r, k + ci[f]] = 1.0
    theta = rng.multivariate_normal(m["mean"], m["cov"], size=n_draws, method="cholesky")
    latent = theta @ x.T
    latent += rng.normal(0, m["tau_storm"], size=(n_draws, 1))
    latent += rng.normal(0, m["sigma"], size=latent.shape)
    return expit(latent)


def loso(feats, fips, sids, share, cust, county_ids) -> dict:
    per_storm, err, const_err, inside, big_err, big_inside = [], [], [], [], [], []
    for fold, sid in enumerate(sorted(set(sids))):
        tr, te = sids != sid, sids == sid
        m = fit(feats[tr], fips[tr], sids[tr], share[tr], cust[tr], county_ids)
        pred = predict(m, feats[te], fips[te], np.random.default_rng(SEED + fold), LOSO_DRAWS)
        lo, hi = np.quantile(pred, [0.1, 0.9], axis=0)
        y = share[te]
        e = np.abs(y - pred.mean(0))
        ins = (y >= lo) & (y <= hi)
        err.append(e)
        const_err.append(np.abs(y - share[tr].mean()))
        inside.append(ins)
        if y.mean() >= BIG_STORM_SHARE:
            big_err.append(e)
            big_inside.append(ins)
        per_storm.append({
            "sid": sid, "counties": int(te.sum()), "observed_mean": round(float(y.mean()), 4),
            "predicted_mean": round(float(pred.mean()), 4), "mae": round(float(e.mean()), 4),
            "inside_10_90": round(float(ins.mean()), 4),
        })
        print(per_storm[-1], flush=True)
    cat = np.concatenate
    return {
        "method": "leave one storm out; logit-normal hierarchical model, EM variances",
        "rows": len(share), "storms": len(per_storm),
        "mae": round(float(cat(err).mean()), 4),
        "inside_10_90": round(float(cat(inside).mean()), 4),
        "constant_mae": round(float(cat(const_err).mean()), 4),
        "big_storm_threshold": BIG_STORM_SHARE,
        "big_storms": [p["sid"] for p in per_storm if p["observed_mean"] >= BIG_STORM_SHARE],
        "big_storm_mae": round(float(cat(big_err).mean()), 4) if big_err else None,
        "big_storm_inside_10_90": round(float(cat(big_inside).mean()), 4) if big_inside else None,
        "per_storm": per_storm,
    }


def labelled_max_kt(tracks: dict, labelled: set[str]) -> dict[str, float]:
    out: dict[str, float] = {}
    for s in tracks["storms"]:
        if s["sid"] not in labelled:
            continue
        track = storm_track(s)
        origin = storms.origin_of(track)
        out[origin] = max(out.get(origin, 0.0), storms.peak_near_ga(track))
    return out


def write_json(name: str, obj) -> None:
    (DATA / name).write_text(json.dumps(obj, separators=(",", ":")) + "\n")


def main(gazetteer_path: str) -> None:
    bq = bigquery.Client(project=PROJECT)
    DATA.mkdir(exist_ok=True)
    gazetteer = read_gazetteer(gazetteer_path)
    counties = build_counties(bq)
    write_json("counties.json", counties)
    tracks = build_tracks(bq, gazetteer)
    tracks["labelled_max_kt"] = {}
    write_json("tracks.json", tracks)
    data.clear_cache()

    fips, sids, feats, share, cust = label_rows(bq, counties, gazetteer, tracks)
    ga = [c["county_fips"] for c in counties]
    county_ids = ga + sorted(set(fips) - set(ga))
    tracks["labelled_max_kt"] = labelled_max_kt(tracks, set(sids))
    write_json("tracks.json", tracks)
    data.clear_cache()

    m = fit(feats, fips, sids, share, cust, county_ids)
    k = 1 + len(FEATURES)
    keep = np.arange(k + len(ga))
    chol = np.linalg.cholesky(m["cov"][np.ix_(keep, keep)] + 1e-10 * np.eye(len(keep)))
    np.savez_compressed(
        DATA / "outage_model.npz", mu=m["mu"], sd=m["sd"], mean=m["mean"][keep], chol=chol,
        county_fips=np.array(ga), tau_storm=m["tau_storm"], tau_county=m["tau_county"],
        sigma=m["sigma"],
    )
    metrics = loso(feats, fips, sids, share, cust, county_ids)
    metrics["full_fit"] = {
        "tau_storm": round(m["tau_storm"], 4), "tau_county": round(m["tau_county"], 4),
        "sigma": round(m["sigma"], 4),
    }
    (DATA / "outage_model_metrics.json").write_text(json.dumps(metrics, indent=1) + "\n")
    summary = {k: v for k, v in metrics.items() if k != "per_storm"}
    summary.update(
        counties=len(counties), storms_in_tracks=len(tracks["storms"]),
        size_filled_points=sum(p[7] for s in tracks["storms"] for p in s["points"]),
        points=sum(len(s["points"]) for s in tracks["storms"]),
        labelled_max_kt=tracks["labelled_max_kt"],
    )
    print(json.dumps(summary, indent=1))
    if not math.isfinite(m["sigma"]):
        raise SystemExit("fit failed")


if __name__ == "__main__":
    main(sys.argv[1])
