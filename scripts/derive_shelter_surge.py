"""Sample NOAA NHC storm-surge maps (SLOSH MOM inundation v4, high tide) at every shelter.

Writes agent/readiness_agent/data/shelter_surge_slosh.csv: the fallback for shelters whose registry
surge flag is blank. The map payload reads the CSV; scripts/load_surge_fallback.sh loads the same
file into BigQuery as shelter_surge_noaa_clean for the SQL tools. The registry value always wins
when it is recorded.

Inputs are not in the repo (4 GB): download
https://www.nhc.noaa.gov/gis/hazardmaps/US_SLOSH_MOM_Inundation_v4.zip, unzip the five
us_Category{1..5}_MOM_Inundation_HIGH.tif files, then run from the repo root:

    python scripts/derive_shelter_surge.py --tifs <dir with the five tifs>

Needs rasterio, numpy and pandas.

Rules:
- A shelter is "inundated" in a category when any cell within about 100 m of its point is
  inundated (class 1-21). Registry coordinates are geocodes, so a single 9 m cell is too strict.
- Raster nodata (255) means "not inundated or outside SLOSH coverage". The script checks that the
  Cat 5 inundation inside Georgia never touches the edge of the inland search box, so every
  shelter beyond the box is also beyond the worst-case surge envelope.
- Class 99 (levee areas, "consult local officials") is recorded as levee, never as dry.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd
import rasterio
from rasterio.enums import Resampling
from rasterio.windows import Window, from_bounds

REPO = Path(__file__).resolve().parents[1]
SHELTERS = REPO / "data/local/parquet/shelters.parquet"
OUT = REPO / "agent/readiness_agent/data/shelter_surge_slosh.csv"

CATEGORIES = (1, 2, 3, 4, 5)
NODATA, LEVEE = 255, 99
RADIUS_M = 100

# Georgia south of the Fall Line plus a margin; the envelope check below proves it is wide enough.
SEARCH_BOX = (-83.6, 30.3, -80.7, 33.0)  # west, south, east, north


def tif(tifs: Path, cat: int) -> Path:
    return tifs / f"us_Category{cat}_MOM_Inundation_HIGH.tif"


def check_envelope(tifs: Path) -> None:
    """Fail unless Cat 5 inundation stays clear of the box's west and north (inland) edges."""
    with rasterio.open(tif(tifs, 5)) as r:
        win = from_bounds(*SEARCH_BOX, transform=r.transform).round_offsets().round_lengths()
        h, w = int(win.height) // 8, int(win.width) // 8
        a = r.read(1, window=win, out_shape=(h, w), resampling=Resampling.max, boundless=True,
                   fill_value=NODATA)
    wet = (a != NODATA) & (a != 0)
    west, north = int(wet[:, :3].sum()), int(wet[:3, :].sum())
    if west or north:
        raise SystemExit(f"Cat 5 surge reaches the search box edge (west {west}, north {north} "
                         "cells); widen SEARCH_BOX")
    cols = np.where(wet.any(axis=0))[0]
    print(f"Cat 5 envelope clear of inland edges; westmost wet column {cols.min()} of {w}")


def sample(r: rasterio.DatasetReader, lon: float, lat: float) -> int | None:
    """Worst class within RADIUS_M of the point: depth class 1-21, LEVEE, or None for dry."""
    row, col = r.index(lon, lat)
    dy = abs(r.transform.e) * 111_320
    dx = abs(r.transform.a) * 111_320 * np.cos(np.radians(lat))
    ry, rx = int(np.ceil(RADIUS_M / dy)), int(np.ceil(RADIUS_M / dx))
    win = Window(col - rx, row - ry, 2 * rx + 1, 2 * ry + 1)
    a = r.read(1, window=win, boundless=True, fill_value=NODATA)
    yy, xx = np.mgrid[-ry:ry + 1, -rx:rx + 1]
    a = a[(yy * dy) ** 2 + (xx * dx) ** 2 <= RADIUS_M ** 2]
    depth = a[(a >= 1) & (a <= 21)]
    if depth.size:
        return int(depth.max())
    return LEVEE if (a == LEVEE).any() else None


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tifs", type=Path, required=True)
    args = ap.parse_args()

    check_envelope(args.tifs)
    shelters = pd.read_parquet(SHELTERS, columns=["shelter_id", "latitude", "longitude"])
    shelters = shelters.dropna(subset=["latitude", "longitude"])
    w, s, e, n = SEARCH_BOX
    inside = shelters.longitude.between(w, e) & shelters.latitude.between(s, n)

    out = shelters.copy()
    for cat in CATEGORIES:
        with rasterio.open(tif(args.tifs, cat)) as r:
            out[f"cat{cat}_class"] = [
                sample(r, lon, lat) if ok else None
                for lon, lat, ok in zip(shelters.longitude, shelters.latitude, inside)
            ]
    classes = out[[f"cat{c}_class" for c in CATEGORIES]]
    wet = classes.apply(lambda col: col.between(1, 21))
    levee = (classes == LEVEE).any(axis=1)
    out["first_category"] = wet.idxmax(axis=1).str.extract(r"(\d)")[0].where(wet.any(axis=1))
    out["status"] = np.select([wet.any(axis=1), levee], ["inundated", "levee"], "dry")
    out["searched"] = np.where(inside, "sampled", "beyond_envelope")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    # BigQuery-ready fallback value: TRUE flooded, FALSE dry, NULL for levee areas (never filled).
    out["in_surge_fallback"] = out.status.map({"inundated": "true", "dry": "false"})
    cols = ["shelter_id", "in_surge_fallback", "status", "first_category", *classes.columns,
            "searched"]
    out[cols].astype({c: "Int64" for c in classes.columns}).to_csv(OUT, index=False)
    print(out.status.value_counts().to_dict(), out.searched.value_counts().to_dict())
    print(f"wrote {OUT.relative_to(REPO)} ({len(out)} shelters)")


if __name__ == "__main__":
    main()
