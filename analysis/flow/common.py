import json
import os
from pathlib import Path

import duckdb

HERE = Path(__file__).resolve().parent
OUT = HERE / "out"
DATA_ROOT = Path(os.environ.get("C4DATA", Path.home() / "work" / "c4data"))

# A single school cannot shelter a quarter of its county. Commerce High
# (270,135) and Commerce Primary (225,112) in Jackson County (pop ~80k) exceed
# it; the Georgia World Congress Center (68,896 in Fulton, pop ~1.07M) does not.
SUSPECT_SHARE = 0.25

# Interstate centrelines, approximated as polylines through interchange towns
# (lon, lat). Accuracy is a few km, well inside the 15 km corridor buffer.
CORRIDOR_BUFFER_KM = 15.0
CORRIDORS = {
    "I-75 south (FL line to Macon)": [
        (-83.20, 30.62), (-83.27, 30.84), (-83.53, 31.45), (-83.78, 31.96),
        (-83.75, 32.46), (-83.66, 32.84),
    ],
    "I-75 north (Macon to TN line)": [
        (-83.66, 32.84), (-83.94, 33.03), (-84.13, 33.45), (-84.39, 33.76),
        (-84.51, 33.95), (-84.77, 34.18), (-84.93, 34.50), (-84.97, 34.77),
        (-85.17, 34.98),
    ],
    "I-95 (FL line to SC line)": [
        (-81.70, 30.72), (-81.67, 30.80), (-81.55, 31.18), (-81.43, 31.40),
        (-81.40, 31.80), (-81.28, 31.95), (-81.23, 32.06), (-81.13, 32.22),
    ],
    "I-16 (Savannah to Macon)": [
        (-81.10, 32.07), (-81.23, 32.06), (-81.26, 32.10), (-81.73, 32.33),
        (-82.06, 32.40), (-82.59, 32.43), (-82.90, 32.52), (-83.08, 32.55),
        (-83.63, 32.83),
    ],
    "I-85 (AL line to SC line)": [
        (-85.18, 32.88), (-85.03, 33.04), (-84.80, 33.38), (-84.55, 33.57),
        (-84.39, 33.76), (-84.27, 33.90), (-84.07, 34.05), (-83.79, 34.11),
        (-83.47, 34.21), (-83.11, 34.43), (-83.03, 34.48),
    ],
}

PROJ = "'EPSG:4326', 'EPSG:32617', always_xy := true"

# Landfall region: first track point over US mainland or Keys land, at the strength the caller filters on
# (DIST2LAND = 0; the lat/lon gate drops Caribbean and Bahamas landfalls).
LANDFALL_CLASS = """
    CASE WHEN LAT < 26.5 THEN 'south_fl_or_keys'
         WHEN LON > -81.9 AND LAT BETWEEN 30.7 AND 32.1 THEN 'a_ga_coast'
         WHEN LON > -81.9 AND LAT < 30.7 THEN 'b_ne_florida'
         WHEN LON BETWEEN -84.6 AND -81.9 AND LAT < 30.7 THEN 'c_fl_west_coast'
         WHEN LON > -81.9 AND LAT >= 32.1 THEN 'd_carolinas'
         WHEN LON < -84.6 THEN 'gulf_panhandle_or_west'
         ELSE 'other' END
"""
US_LANDFALL = "DIST2LAND = 0 AND LAT >= 24.5 AND (LON <= -80.0 OR LAT >= 30.0)"


def table(state: str, name: str) -> str:
    path = DATA_ROOT / state / name / "data.parquet"
    if not path.exists():
        raise FileNotFoundError(path)
    return f"read_parquet('{path}')"


def pt(lon: str, lat: str) -> str:
    return f"ST_Transform(ST_Point({lon}, {lat}), {PROJ})"


def connect() -> duckdb.DuckDBPyConnection:
    con = duckdb.connect()
    con.execute("INSTALL spatial; LOAD spatial;")
    for st in ("GA", "FL"):
        s = st.lower()
        con.execute(f"""
            CREATE VIEW {s}_tracts AS
            SELECT v.* REPLACE (
                       CASE WHEN median_income < 0 THEN NULL ELSE median_income END AS median_income),
                   {pt('lon', 'lat')} AS geom
            FROM {table(st, 'vulnerability_tracts')} v
        """)
        con.execute(f"""
            CREATE VIEW {s}_hazard AS
            SELECT geo_id, POPULATION AS nri_pop, HRCN_AFREQ, HRCN_EALP,
                   CFLD_AFREQ, CFLD_EXPP,
                   -- null CFLD_EXPP means the tract is outside NRI's coastal-flood layer
                   CASE WHEN POPULATION > 0
                        THEN LEAST(COALESCE(CFLD_EXPP, 0) / POPULATION, 1.0) END AS cfld_share
            FROM {table(st, 'hazard_tracts')}
        """)
        missing = con.execute(f"""
            SELECT COUNT(*), COALESCE(SUM(total_pop), 0)
            FROM {s}_tracts ANTI JOIN {s}_hazard USING (geo_id)
        """).fetchall()[0]
        assert missing[1] == 0, f"{st}: {missing[0]} populated tracts have no hazard row"
    con.execute("""
        CREATE VIEW ga_county_pop AS
        SELECT county_fips, SUM(total_pop) AS county_pop
        FROM ga_tracts GROUP BY 1
    """)
    con.execute(f"""
        CREATE VIEW ga_shelters_raw AS
        SELECT s.* REPLACE (NULLIF(TRIM(usage), '') AS usage),
               CASE WHEN wheelchair_accessible THEN 'yes'
                    WHEN NOT wheelchair_accessible THEN 'no'
                    ELSE 'unrecorded' END AS wheelchair,
               CASE WHEN generator_onsite THEN 'yes'
                    WHEN NOT generator_onsite THEN 'no'
                    ELSE 'unrecorded' END AS generator,
               p.county_pop,
               {pt('longitude', 'latitude')} AS geom
        FROM {table('GA', 'shelters')} s
        LEFT JOIN ga_county_pop p USING (county_fips)
    """)
    con.execute(f"""
        CREATE VIEW ga_shelters AS
        WITH flagged AS (
            SELECT *,
                   usage IN ('EVAC', 'BOTH') AS is_evac,
                   CASE
                     WHEN usage IS NULL THEN 'no usage recorded'
                     WHEN usage = 'POST' THEN 'post-landfall only'
                     WHEN COALESCE(evacuation_capacity, 0) = 0 THEN 'capacity 0 or null'
                     WHEN evacuation_capacity <= 2 THEN 'capacity 1-2 placeholder'
                     WHEN evacuation_capacity > {SUSPECT_SHARE} * county_pop THEN 'suspect: exceeds county share'
                     ELSE 'ok' END AS capacity_flag,
                   ROW_NUMBER() OVER (
                       PARTITION BY round(latitude, 5), round(longitude, 5),
                                    upper(regexp_replace(shelter_name, '[^A-Za-z0-9]', '', 'g'))
                       ORDER BY evacuation_capacity DESC NULLS LAST, shelter_id) AS dup_rank
            FROM ga_shelters_raw
        )
        SELECT *,
               dup_rank > 1 AS is_duplicate,
               CASE WHEN capacity_flag = 'ok' AND dup_rank = 1 THEN evacuation_capacity END AS clean_capacity
        FROM flagged
    """)
    con.execute(f"""
        CREATE TABLE corridors AS
        SELECT * FROM (VALUES {', '.join(
            f"('{name}', ST_Transform(ST_GeomFromText('LINESTRING({', '.join(f'{x} {y}' for x, y in pts)})'), {PROJ}))"
            for name, pts in CORRIDORS.items())}) t(corridor, geom)
    """)
    return con


def write_csv(con, sql: str, name: str) -> Path:
    OUT.mkdir(exist_ok=True)
    path = OUT / name
    con.execute(f"COPY ({sql}) TO '{path}' (HEADER, DELIMITER ',')")
    return path


def save_numbers(section: str, numbers: dict) -> None:
    OUT.mkdir(exist_ok=True)
    path = OUT / "numbers.json"
    data = json.loads(path.read_text()) if path.exists() else {}
    data[section] = _rounded(numbers)
    path.write_text(json.dumps(data, indent=2, sort_keys=True, default=float) + "\n")


def _rounded(value):
    if isinstance(value, dict):
        return {k: _rounded(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_rounded(v) for v in value]
    if isinstance(value, float):
        return round(value, 4)
    return value


def one(con, sql: str):
    rows = con.execute(sql).fetchall()
    assert len(rows) == 1, (sql, len(rows))
    return rows[0][0] if len(rows[0]) == 1 else rows[0]
