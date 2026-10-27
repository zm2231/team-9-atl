import json
import os
from pathlib import Path

import numpy as np
import pandas as pd
from google.cloud import bigquery

from ..model import FEATURES, transform
from ..windfield import NM_KM

DATA = Path(__file__).resolve().parents[1] / "data"
PROJECT = os.getenv("GOOGLE_CLOUD_PROJECT", "qwiklabs-gcp-04-edc952746633")
DATASET = os.getenv("EVAC_DATASET", "evac_prod")
NEAR_KM = 250
CLIMATE_FROM = 1950
TEMPLATE_FROM = 2001
SEED = 20261027


def table(name: str) -> str:
    return f"`{PROJECT}.{DATASET}.{name}`"


def origin_of(lat: float, lon: float) -> str:
    if lon < -83.5 and lat < 31.5:
        return "gulf"
    if lat < 30.5:
        return "florida_peninsula"
    if lon >= -81.6 and lat <= 32.6:
        return "atlantic_ga"
    if lat > 32.6 and lon >= -82.0:
        return "carolinas"
    return "overland_west"


def build_counties(bq: bigquery.Client) -> list[dict]:
    rows = bq.query(f"""
      SELECT t.county_fips, p.county AS county_name,
        SUM(t.lat * t.total_pop) / SUM(t.total_pop) AS lat,
        SUM(t.lon * t.total_pop) / SUM(t.total_pop) AS lon,
        SUM(t.total_pop) AS pop,
        ANY_VALUE(p.power_dependent_devices_dme) AS power_dependent,
        ANY_VALUE(p.facility_esrd_dialysis_any_dme) AS dialysis_patients
      FROM {table('vulnerability_tracts_clean')} t
      JOIN {table('power_dependent_counties_clean')} p ON p.fips_code = t.county_fips
      WHERE t.total_pop > 0
      GROUP BY 1, 2 ORDER BY 1""").to_dataframe()
    return [
        {"county_fips": r.county_fips, "county_name": r.county_name, "lat": round(r.lat, 5),
         "lon": round(r.lon, 5), "pop": int(r["pop"]),
         "power_dependent": int(r.power_dependent or 0), "dialysis_patients": int(r.dialysis_patients or 0)}
        for _, r in rows.iterrows()
    ]


def build_sites(bq: bigquery.Client) -> dict:
    shelters = bq.query(f"""
      SELECT shelter_id, shelter_name, county_fips, latitude, longitude, evacuation_capacity, generator_onsite
      FROM {table('shelters_clean')}
      WHERE is_medical AND latitude IS NOT NULL AND evacuation_capacity > 0 ORDER BY shelter_id""").to_dataframe()
    dialysis = bq.query(f"""
      SELECT ccn, facility_name, county_fips, latitude, longitude, stations, late_shift
      FROM {table('dialysis_centers_flow_staging')}
      WHERE latitude IS NOT NULL AND stations > 0 ORDER BY ccn""").to_dataframe()

    def flag(v):
        return None if pd.isna(v) else bool(v)

    return {
        "medical_shelters": [
            {"shelter_id": str(r.shelter_id), "name": r.shelter_name, "county_fips": r.county_fips,
             "lat": float(r.latitude), "lon": float(r.longitude), "seats": int(r.evacuation_capacity),
             "generator": flag(r.generator_onsite)}
            for _, r in shelters.iterrows()
        ],
        "dialysis_centers": [
            {"ccn": str(r.ccn), "name": r.facility_name, "county_fips": r.county_fips,
             "lat": float(r.latitude), "lon": float(r.longitude), "stations": int(r.stations),
             "late_shift": flag(r.late_shift)}
            for _, r in dialysis.iterrows()
        ],
    }


def mean_radius_km(row: pd.Series) -> float | None:
    vals = [row[c] for c in ("USA_R34_NE", "USA_R34_SE", "USA_R34_SW", "USA_R34_NW") if pd.notna(row[c]) and row[c] > 0]
    return float(np.mean(vals)) * NM_KM if vals else None


def build_tracks(bq: bigquery.Client) -> dict:
    pts = bq.query(f"""
      SELECT SID, NAME, SEASON, ISO_TIME, USA_LAT, USA_LON, USA_WIND, USA_RMW,
        USA_R34_NE, USA_R34_SE, USA_R34_SW, USA_R34_NW, dist_ga_km
      FROM {table('storm_tracks_ibtracs')}
      WHERE USA_WIND IS NOT NULL AND SEASON >= {CLIMATE_FROM}
      ORDER BY SID, ISO_TIME""").to_dataframe()
    storms, templates = [], []
    for sid, g in pts.groupby("SID", sort=True):
        if g.dist_ga_km.min() >= NEAR_KM:
            continue
        near = g[g.dist_ga_km < 300]
        entry = near.iloc[0]
        origin = origin_of(entry.USA_LAT, entry.USA_LON)
        w300 = float(near.USA_WIND.max())
        season = int(g.SEASON.iloc[0])
        storms.append({"sid": sid, "name": str(g.NAME.iloc[0]).title(), "season": season, "origin": origin, "w300": w300})
        has_radii = near[["USA_R34_NE", "USA_R34_SE", "USA_R34_SW", "USA_R34_NW"]].notna().any(axis=None)
        if season < TEMPLATE_FROM or not has_radii:
            continue
        anchor = g.loc[g.dist_ga_km.idxmin()]
        t0 = g.ISO_TIME.iloc[0]
        rmw, r34, points = 40.0, 0.0, []
        for _, r in g.iterrows():
            rmw = float(r.USA_RMW) * NM_KM if pd.notna(r.USA_RMW) and r.USA_RMW > 0 else rmw
            r34 = mean_radius_km(r) or r34
            hour = (r.ISO_TIME - t0).total_seconds() / 3600
            points.append([round(hour, 2), round(float(r.USA_LAT), 3), round(float(r.USA_LON), 3),
                           float(r.USA_WIND), round(rmw, 1), round(r34, 1)])
        templates.append({
            "sid": sid, "name": str(g.NAME.iloc[0]).title(), "season": season, "origin": origin, "w300": w300,
            "anchor": [round(float(anchor.USA_LAT), 3), round(float(anchor.USA_LON), 3)],
            "anchor_hour": round((anchor.ISO_TIME - t0).total_seconds() / 3600, 2), "points": points,
        })
    years = pts.SEASON.max() - CLIMATE_FROM + 1
    origins = {}
    for o in sorted({s["origin"] for s in storms}):
        group = [s for s in storms if s["origin"] == o]
        origins[o] = {
            "storms": len(group), "annual_rate": round(len(group) / years, 4),
            "annual_rate_2000": round(sum(s["season"] >= 2000 for s in group) / (pts.SEASON.max() - 1999), 4),
            "intensities_kt": sorted(s["w300"] for s in group),
            "templates": sum(t["origin"] == o for t in templates),
        }
    return {"years": [CLIMATE_FROM, int(pts.SEASON.max())], "near_km": NEAR_KM, "origins": origins,
            "storms": storms, "templates": templates}


def fit_model(bq: bigquery.Client, exposure: pd.DataFrame, counties: list[dict], storms: list[dict]) -> dict:
    labels = bq.query(f"""
      SELECT fips_code, sid, peak_share, eaglei_total_customers_2024 AS customers
      FROM {table('county_storm_outages')}
      WHERE peak_share_status != 'suspect' AND peak_share IS NOT NULL""").to_dataframe()
    data = exposure.merge(labels, left_on=["fips", "sid"], right_on=["fips_code", "sid"]).dropna(subset=FEATURES)
    x_raw = transform(data[FEATURES].to_numpy(float))
    mu, sd = x_raw.mean(0), x_raw.std(0)
    z = (x_raw - mu) / sd
    county_ids = sorted(data.fips.unique())
    storm_ids = sorted(data.sid.unique())
    ci = {c: i for i, c in enumerate(county_ids)}
    si = {s: i for i, s in enumerate(storm_ids)}
    k = 1 + len(FEATURES)
    nc, ns = len(county_ids), len(storm_ids)
    x = np.zeros((len(data), k + nc + ns))
    x[:, 0] = 1
    x[:, 1:k] = z
    x[np.arange(len(data)), k + data.fips.map(ci).to_numpy()] = 1
    x[np.arange(len(data)), k + nc + data.sid.map(si).to_numpy()] = 1
    share = data.peak_share.to_numpy(float)
    cust = data.customers.to_numpy(float)
    y = np.log((share * cust + 0.5) / (cust - share * cust + 0.5))
    tau_c, tau_s = 0.7, 0.8
    for _ in range(12):
        prior = np.r_[4.0, np.repeat(1.5, len(FEATURES)), np.repeat(tau_c, nc), np.repeat(tau_s, ns)]
        cov_unit = np.linalg.inv(x.T @ x + np.diag(1 / prior**2))
        coef = cov_unit @ x.T @ y
        sigma = float(np.sqrt(np.mean((y - x @ coef) ** 2)))
        cov = sigma**2 * cov_unit
        diag = np.diag(cov)
        tau_c = float(np.sqrt(np.mean(coef[k:k + nc] ** 2 + diag[k:k + nc])))
        tau_s = float(np.sqrt(np.mean(coef[k + nc:] ** 2 + diag[k + nc:])))
    ga = [c["county_fips"] for c in counties]
    keep = list(range(k)) + [k + ci[c] for c in ga]
    sub = cov[np.ix_(keep, keep)]
    chol = np.linalg.cholesky(sub + 1e-10 * np.eye(len(keep)))
    labelled = {s["sid"] for s in storms} & set(storm_ids)
    support = {}
    for s in storms:
        if s["sid"] in labelled:
            support[s["origin"]] = max(support.get(s["origin"], 0.0), s["w300"])
    return {
        "mu": mu, "sd": sd, "mean": coef[keep], "chol": chol, "county_fips": np.array(ga),
        "tau_storm": tau_s, "tau_county": tau_c, "sigma": sigma, "rows": len(data), "storms": ns,
        "support_origins": np.array(sorted(support)), "support_max_kt": np.array([support[o] for o in sorted(support)]),
    }


def main() -> None:
    bq = bigquery.Client(project=PROJECT)
    DATA.mkdir(exist_ok=True)
    counties = build_counties(bq)
    (DATA / "counties.json").write_text(json.dumps(counties, separators=(",", ":")))
    (DATA / "sites.json").write_text(json.dumps(build_sites(bq), separators=(",", ":")))
    tracks = build_tracks(bq)
    (DATA / "tracks.json").write_text(json.dumps(tracks, separators=(",", ":")))
    exposure = pd.read_parquet(os.environ["SCENARIO_EXPOSURE_PARQUET"])
    model = fit_model(bq, exposure, counties, tracks["storms"])
    np.savez_compressed(DATA / "outage_model.npz", **{k: v for k, v in model.items() if k not in ("rows", "storms")},
                        meta=np.array(json.dumps({"rows": model["rows"], "storms": model["storms"], "seed": SEED})))
    print(json.dumps({"counties": len(counties), "templates": len(tracks["templates"]), "rows": model["rows"],
                      "storms": model["storms"], "tau_storm": model["tau_storm"], "sigma": model["sigma"],
                      "origins": {o: {k: v for k, v in d.items() if k != "intensities_kt"} for o, d in tracks["origins"].items()}}, indent=1))


if __name__ == "__main__":
    main()
