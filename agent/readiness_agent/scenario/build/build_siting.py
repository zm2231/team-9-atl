import argparse
import json
import subprocess
import tempfile
import time
from pathlib import Path

from shapely.geometry import Point, shape
from shapely.prepared import prep

from .. import data, season, siting
from .build_season import DATASET, PROJECT, load
from .limits import MAX_BYTES_BILLED

SITE_UPDATES_SCHEMA = [
    ("update_id", "STRING", "Unique id of this change"),
    ("site_kind", "STRING", "medical_shelter or dialysis"),
    ("site_id", "STRING", "shelter_id or ccn, or a new id for a site not in the registry"),
    ("field", "STRING", "generator, seats, stations, open, lat, lon, name or county_fips"),
    ("value", "STRING", "Validated value as text"),
    ("entered_by", "STRING", "Request user, or planner"),
    ("entered_at", "TIMESTAMP", "When the change was recorded"),
    ("note", "STRING", "Planner's note"),
]
UPDATES_DESCRIPTION = (
    "Planner-reported site updates, one row per change; the latest row per site and field "
    "wins; registry tables are never overwritten"
)
SITING_SCHEMA = [
    ("candidate_id", "STRING", "upgrade-<shelter_id>, general-<shelter_id> or county-<fips>"),
    ("kind", "STRING", "upgrade, general_shelter or county_centre"),
    ("name", "STRING", "Site name"),
    ("county_fips", "STRING", "County of the site"),
    ("shelter_id", "STRING", "Shelter id for upgrade and general_shelter candidates"),
    ("lat", "FLOAT", "Latitude"),
    ("lon", "FLOAT", "Longitude"),
    (
        "seats_assumed",
        "INTEGER",
        "Powered seats assumed: recorded seats for upgrades, otherwise an assumed number",
    ),
    ("lacking_shelter_1in10_before", "INTEGER", "Statewide lacking shelter, 1-in-10 season"),
    ("lacking_shelter_1in10_after", "INTEGER", "Same with this site added or upgraded"),
    ("lacking_shelter_1in10_reduction", "INTEGER", "before minus after"),
    ("lacking_shelter_typical_before", "INTEGER", "Statewide lacking shelter, median season"),
    ("lacking_shelter_typical_after", "INTEGER", "Same with this site"),
    ("lacking_shelter_typical_reduction", "INTEGER", "before minus after"),
    ("counties_helped", "INTEGER", "Counties whose 1-in-10 figure drops by at least 1"),
    (
        "p_helps",
        "FLOAT",
        (
            "Share of simulated seasons in which the site cuts statewide lacking shelter by at "
            "least 1; before and after use the same seasons"
        ),
    ),
    ("expected_reduction_per_year", "FLOAT", "Mean reduction across the same simulated seasons"),
]


def general_shelters(min_capacity: int, seats: int) -> list[dict]:
    sql = f"""
      SELECT shelter_id, shelter_name, county_fips, latitude, longitude, evacuation_capacity
      FROM `{PROJECT}.{DATASET}.shelters_clean`
      WHERE NOT IFNULL(is_medical, FALSE) AND NOT IFNULL(in_surge_slosh_area, FALSE)
        AND evacuation_capacity >= @min_capacity AND latitude IS NOT NULL
      ORDER BY shelter_id"""
    out = subprocess.run(
        [
            "bq",
            "query",
            "--nouse_legacy_sql",
            "--format=json",
            "--max_rows=100000",
            f"--maximum_bytes_billed={MAX_BYTES_BILLED}",
            f"--parameter=min_capacity:INT64:{min_capacity}",
            sql,
        ],
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    zones = json.loads((data.DATA_DIR / "surge_zones.geojson").read_text())["features"]
    worst = prep(shape(next(f for f in zones if f["properties"]["category"] == 5)["geometry"]))
    rows, seen = [], set()
    for r in json.loads(out):
        lat, lon = float(r["latitude"]), float(r["longitude"])
        sid = str(r["shelter_id"])
        if sid in seen or worst.contains(Point(lon, lat)):
            continue
        if not (
            season.GA_LAT[0] <= lat <= season.GA_LAT[1]
            and season.GA_LON[0] <= lon <= season.GA_LON[1]
        ):
            continue
        seen.add(sid)
        rows.append(
            {
                "candidate_id": f"general-{sid}",
                "kind": "general_shelter",
                "shelter_id": sid,
                "name": r["shelter_name"],
                "county_fips": r["county_fips"],
                "lat": lat,
                "lon": lon,
                "seats": seats,
            }
        )
    return rows


def create_site_updates_table() -> None:
    ref = f"{PROJECT}:{DATASET}.scenario_site_updates"
    exists = subprocess.run(["bq", "show", ref], capture_output=True, check=False).returncode == 0
    if exists:
        return
    with tempfile.TemporaryDirectory() as tmp:
        spec = Path(tmp) / "schema.json"
        spec.write_text(
            json.dumps(
                [{"name": n, "type": t, "description": d} for n, t, d in SITE_UPDATES_SCHEMA]
            )
        )
        subprocess.run(
            ["bq", "mk", "--table", "--description", UPDATES_DESCRIPTION, ref, str(spec)],
            check=True,
            stdout=subprocess.DEVNULL,
        )


def main() -> None:
    a = argparse.ArgumentParser()
    a.add_argument("--no-load", action="store_true")
    a.add_argument("--seats", type=int, default=siting.NEW_SITE_SEATS)
    a.add_argument("--min-capacity", type=int, default=siting.GENERAL_MIN_CAPACITY)
    args = a.parse_args()
    t0 = time.perf_counter()
    base = season.siting_base("long_run")
    cands = (
        siting.upgrade_candidates(base["ev"])
        + general_shelters(args.min_capacity, args.seats)
        + siting.county_candidates(args.seats)
    )
    scored = season.evaluate_candidates(base, cands)
    rows = []
    for r in scored:
        row = {k: r.get(k) for k, *_ in SITING_SCHEMA if k != "seats_assumed"}
        row["seats_assumed"] = round(float(r["seats"]))
        rows.append(row)
    siting.CANDIDATES_FILE.write_text(
        json.dumps(
            {
                "seats_assumed_new": args.seats,
                "general_min_capacity": args.min_capacity,
                "candidates": [
                    {
                        **{
                            k: r.get(k)
                            for k in (
                                "candidate_id",
                                "kind",
                                "name",
                                "county_fips",
                                "shelter_id",
                                "lat",
                                "lon",
                                "recorded_generator",
                            )
                        },
                        "seats": r["seats"],
                        "lacking_shelter_1in10_reduction": r["lacking_shelter_1in10_reduction"],
                    }
                    for r in scored
                ],
            },
            separators=(",", ":"),
        )
    )
    runtime = time.perf_counter() - t0
    if not args.no_load:
        create_site_updates_table()
        load(
            "scenario_siting",
            rows,
            SITING_SCHEMA,
            "Candidate medical-shelter sites ranked by modelled reduction in statewide people "
            "lacking shelter, long_run outlook, 5,000 simulated seasons. Modelled reduction; "
            f"assumes {args.seats} powered seats for new or converted sites (an assumption) and "
            f"the recorded seats for upgrades; straight-line reach of {season.RECEIVE_KM:.0f} km. "
            "Reductions do not add up across sites. General shelters: not medical, outside "
            f"every SLOSH category, capacity >= {args.min_capacity}.",
        )
    combo = season.greedy(base, scored[:20])
    print(
        json.dumps(
            {
                "candidates": len(rows),
                "by_kind": {
                    k: sum(r["kind"] == k for r in rows)
                    for k in ("upgrade", "general_shelter", "county_centre")
                },
                "runtime_s": round(runtime, 1),
                "json_kb": round(siting.CANDIDATES_FILE.stat().st_size / 1024),
                "top5": [
                    {
                        k: r[k]
                        for k in (
                            "candidate_id",
                            "name",
                            "lacking_shelter_1in10_reduction",
                            "p_helps",
                            "expected_reduction_per_year",
                        )
                    }
                    for r in rows[:5]
                ],
                "best_3": [(r["candidate_id"], r["added_reduction_1in10"]) for r in combo],
            },
            indent=1,
        )
    )


if __name__ == "__main__":
    main()
