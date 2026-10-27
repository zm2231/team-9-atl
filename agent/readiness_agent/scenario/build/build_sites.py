import argparse
import json
import os
import zipfile
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import rasterio
from google.cloud import bigquery
from rasterio import features
from rasterio.enums import Resampling
from shapely.geometry import mapping, shape
from shapely.ops import unary_union

DATA = Path(__file__).resolve().parents[1] / "data"
PROJECT = os.getenv("GOOGLE_CLOUD_PROJECT", "qwiklabs-gcp-04-edc952746633")
DATASET = os.getenv("EVAC_DATASET", "evac_prod")
CATEGORIES = (1, 2, 3, 4, 5)
NODATA = 255
MAP_FACTOR = 32
SIMPLIFY_DEG = 0.004


def table(name: str) -> str:
    return f"`{PROJECT}.{DATASET}.{name}`"


def flag(v) -> str:
    if v is None or (isinstance(v, float) and np.isnan(v)) or pd.isna(v):
        return "UNRECORDED"
    return "YES" if bool(v) else "NO"


def surge_rasters(slosh_dir: Path) -> dict[int, Path]:
    return {c: slosh_dir / f"ga_coast_cat{c}_mom_inundation_high.tif" for c in CATEGORIES}


def surge_categories(
    rasters: dict[int, Path], lats: np.ndarray, lons: np.ndarray
) -> list[list[int]]:
    hits: list[list[int]] = [[] for _ in lats]
    for cat, path in rasters.items():
        with rasterio.open(path) as r:
            b = r.bounds
            inside = (lons >= b.left) & (lons <= b.right) & (lats >= b.bottom) & (lats <= b.top)
            idx = np.flatnonzero(inside)
            if not len(idx):
                continue
            values = np.array([v[0] for v in r.sample(zip(lons[idx], lats[idx], strict=True))])
            for i, v in zip(idx, values, strict=True):
                if v != NODATA and 1 <= v <= 21:
                    hits[i].append(cat)
    return hits


def surge_zones(rasters: dict[int, Path]) -> dict:
    out = []
    for cat, path in rasters.items():
        with rasterio.open(path) as r:
            h, w = r.height // MAP_FACTOR, r.width // MAP_FACTOR
            band = r.read(1, out_shape=(h, w), resampling=Resampling.nearest)
            transform = r.transform * r.transform.scale(r.width / w, r.height / h)
        mask = (band != NODATA) & (band >= 1) & (band <= 21)
        polys = [
            shape(g)
            for g, v in features.shapes(mask.astype(np.uint8), mask=mask, transform=transform)
            if v == 1
        ]
        merged = unary_union(polys).simplify(SIMPLIFY_DEG, preserve_topology=True)
        out.append(
            {
                "type": "Feature",
                "properties": {
                    "category": cat,
                    "source": "NOAA NHC SLOSH MOM v4, high tide, worst case across storms",
                    "resolution_m": round(MAP_FACTOR * 9.3),
                },
                "geometry": json.loads(json.dumps(mapping(merged), default=float)),
            }
        )
    return {"type": "FeatureCollection", "features": out}


def round_coords(obj, nd=4):
    if isinstance(obj, float):
        return round(obj, nd)
    if isinstance(obj, (list, tuple)):
        return [round_coords(x, nd) for x in obj]
    if isinstance(obj, dict):
        return {k: round_coords(v, nd) for k, v in obj.items()}
    return obj


def build_sites(bq: bigquery.Client, rasters: dict[int, Path]) -> dict:
    shelters = bq.query(f"""
      SELECT shelter_id, shelter_name, county_fips, latitude, longitude, evacuation_capacity,
        generator_onsite
      FROM {table("shelters_clean")}
      WHERE is_medical AND latitude IS NOT NULL AND evacuation_capacity > 0
      ORDER BY shelter_id""").to_dataframe()
    dialysis = bq.query(f"""
      SELECT ccn, facility_name, county_fips, latitude, longitude, stations, late_shift
      FROM {table("dialysis_centers_flow_staging")}
      WHERE latitude IS NOT NULL AND stations > 0 ORDER BY ccn""").to_dataframe()
    s_surge = surge_categories(
        rasters, shelters.latitude.to_numpy(float), shelters.longitude.to_numpy(float)
    )
    d_surge = surge_categories(
        rasters, dialysis.latitude.to_numpy(float), dialysis.longitude.to_numpy(float)
    )
    return {
        "medical_shelters": [
            {
                "shelter_id": str(r.shelter_id),
                "name": r.shelter_name,
                "county_fips": r.county_fips,
                "lat": round(float(r.latitude), 5),
                "lon": round(float(r.longitude), 5),
                "seats": int(r.evacuation_capacity),
                "generator": flag(r.generator_onsite),
                "in_surge": s,
            }
            for r, s in zip(shelters.itertuples(), s_surge, strict=True)
        ],
        "dialysis_centers": [
            {
                "ccn": str(r.ccn),
                "name": r.facility_name,
                "county_fips": r.county_fips,
                "lat": round(float(r.latitude), 5),
                "lon": round(float(r.longitude), 5),
                "stations": int(r.stations),
                "late_shift": flag(r.late_shift),
                "in_surge": s,
            }
            for r, s in zip(dialysis.itertuples(), d_surge, strict=True)
        ],
    }


def build_facility_beds(bq: bigquery.Client, county_zip: Path) -> dict:
    nursing = bq.query(f"""
      SELECT cms_certification_number_ccn AS ccn, latitude, longitude,
        number_of_certified_beds AS beds
      FROM {table("care_facilities_clean")} WHERE latitude IS NOT NULL""").to_dataframe()
    assisted = bq.query(f"""
      SELECT county_fips, SUM(licensed_beds) AS beds, COUNT(*) AS homes
      FROM {table("ext_ga_assisted_living")}
      WHERE county_fips IS NOT NULL AND (operstdesc IS NULL OR UPPER(operstdesc) = 'ACTIVE')
        AND closeddate IS NULL
      GROUP BY 1""").to_dataframe()
    with zipfile.ZipFile(county_zip) as z:
        shp = next(n for n in z.namelist() if n.endswith(".shp"))
    counties = gpd.read_file(f"zip://{county_zip}!{shp}")
    counties = counties[counties.STATEFP == "13"][["GEOID", "geometry"]].to_crs("EPSG:4326")
    pts = gpd.GeoDataFrame(
        nursing, geometry=gpd.points_from_xy(nursing.longitude, nursing.latitude), crs="EPSG:4326"
    )
    joined = gpd.sjoin(pts, counties, how="left", predicate="within")
    missing = joined.GEOID.isna()
    if missing.any():
        near = gpd.sjoin_nearest(
            pts[missing].to_crs("EPSG:5070"), counties.to_crs("EPSG:5070"), how="left"
        )
        joined.loc[missing, "GEOID"] = near.GEOID.to_numpy()
    nh = joined.groupby("GEOID").agg(beds=("beds", "sum"), homes=("ccn", "count"))
    rows = {}
    for fips in sorted(counties.GEOID):
        a = assisted[assisted.county_fips == fips]
        rows[fips] = {
            "nursing_home_beds": int(nh.beds.get(fips, 0) or 0),
            "nursing_homes": int(nh.homes.get(fips, 0) or 0),
            "assisted_living_beds": int(a.beds.sum()) if len(a) else 0,
            "assisted_living_homes": int(a.homes.sum()) if len(a) else 0,
        }
    return {
        "source": "CMS nursing homes (care_facilities_clean, joined to Census 2023 county "
        "boundaries); GaMap2Care assisted living and personal care homes "
        "(ext_ga_assisted_living, active or unstated status, not closed)",
        "generator": "not recorded for any facility",
        "counties": rows,
        "unjoined_nursing_homes": int(missing.sum()),
    }


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--slosh-dir", type=Path, required=True)
    p.add_argument("--county-zip", type=Path, required=True)
    a = p.parse_args()
    bq = bigquery.Client(project=PROJECT)
    rasters = surge_rasters(a.slosh_dir)
    sites = build_sites(bq, rasters)
    (DATA / "sites.json").write_text(json.dumps(sites, separators=(",", ":")))
    zones = round_coords(surge_zones(rasters), 3)
    (DATA / "surge_zones.geojson").write_text(json.dumps(zones, separators=(",", ":")))
    beds = build_facility_beds(bq, a.county_zip)
    (DATA / "facility_beds.json").write_text(json.dumps(beds, separators=(",", ":")))
    summary = {
        "medical_shelters": len(sites["medical_shelters"]),
        "dialysis_centers": len(sites["dialysis_centers"]),
        "shelters_in_surge_by_cat": {
            c: sum(c in s["in_surge"] for s in sites["medical_shelters"]) for c in CATEGORIES
        },
        "dialysis_in_surge_by_cat": {
            c: sum(c in s["in_surge"] for s in sites["dialysis_centers"]) for c in CATEGORIES
        },
        "surge_zones_kb": round((DATA / "surge_zones.geojson").stat().st_size / 1024),
        "nursing_home_beds": sum(v["nursing_home_beds"] for v in beds["counties"].values()),
        "assisted_living_beds": sum(v["assisted_living_beds"] for v in beds["counties"].values()),
        "unjoined_nursing_homes": beds["unjoined_nursing_homes"],
    }
    print(json.dumps(summary, indent=1))


if __name__ == "__main__":
    main()
