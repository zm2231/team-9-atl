import csv
import os
from pathlib import Path

from common import (
    CORRIDOR_BUFFER_KM,
    CORRIDORS,
    OUT,
    PROJ,
    connect,
    one,
    save_numbers,
    table,
    write_csv,
)

EXTDATA = Path(os.environ.get("EXTDATA", Path.home() / "work" / "extdata"))
IBTRACS = EXTDATA / "ibtracs" / "ibtracs_na_within300km_ga.parquet"
GDOT = EXTDATA / "gdot_evac"
GEMA_CONTRAFLOW = EXTDATA / "gema" / "contraflow_intersections.geojson"
TIGER = EXTDATA / "tiger_roads" / "tl_2023_13_prisecroads.shp"
BUF = CORRIDOR_BUFFER_KM * 1000
LEVELS = ("low", "base", "high")

GA_COAST = ("13051", "13029", "13179", "13191", "13127", "13039")
GA_COASTAL_FLOOD = GA_COAST + ("13025", "13049", "13103", "13183", "13251", "13305")

# GDOT route ids encode the state route number: SR 401 is I-75, SR 404 is I-16.
GDOT_I75 = "1000100040100INC"
GDOT_I16 = "1000100040400INC"
MACON_LAT = 32.84
ATLANTA_LON = -84.40

# Every rate is an assumption, bracketed low/base/high.
EVACUATION_RATE = {"low": 0.20, "base": 0.35, "high": 0.50}
SHELTER_USE = {"low": 0.02, "base": 0.05, "high": 0.10}
CARLESS_SHELTER_USE = {"low": 0.30, "base": 0.50, "high": 0.70}

SCENARIOS = {
    "a_ga_coast": {
        "label": "(a) Atlantic hit on the Georgia coast",
        "origins": {"GA": {"counties": GA_COAST, "to_ga": {"low": 0.60, "base": 0.75, "high": 0.90}}},
        "routes": "gdot_network",
        "entry": "origin",
        "exclude_hosts": GA_COAST,
    },
    "a_ga_coast_wider_hosts_excluded": {
        "label": "(a') as (a), with all 12 coastal-flood counties unavailable as hosts",
        "origins": {"GA": {"counties": GA_COAST, "to_ga": {"low": 0.60, "base": 0.75, "high": 0.90}}},
        "routes": "gdot_network",
        "entry": "origin",
        "exclude_hosts": GA_COASTAL_FLOOD,
    },
    "b_ne_florida": {
        "label": "(b) NE Florida / Jacksonville, Georgia coast also ordered out",
        "origins": {
            "FL": {"counties": ("12089", "12031", "12109", "12035"),
                   "to_ga": {"low": 0.20, "base": 0.35, "high": 0.50}},
            "GA": {"counties": GA_COAST, "to_ga": {"low": 0.60, "base": 0.75, "high": 0.90}},
        },
        "routes": "gdot_network",
        "entry": "origin",
        "exclude_hosts": GA_COAST,
    },
    "c_fl_west_coast": {
        "label": "(c) Florida west coast, Milton-type, up I-75",
        "origins": {"FL": {"counties": ("12103", "12057", "12101", "12081", "12115", "12053", "12017"),
                           "to_ga": {"low": 0.05, "base": 0.15, "high": 0.30}}},
        "routes": "i75",
        "entry": (-83.20, 30.62),
        "exclude_hosts": (),
    },
    "d_carolinas": {
        "label": "(d) Carolinas coast, west on I-20",
        "origins": {"SC": {"counties": ("45013", "45053", "45029", "45019", "45035", "45015", "45043", "45051"),
                           "to_ga": {"low": 0.03, "base": 0.08, "high": 0.15}}},
        "routes": "i20",
        "entry": (-81.98, 33.49),
        "exclude_hosts": (),
    },
}

# Landfall region: first track point at hurricane strength over US mainland or Keys land
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
NEAR_MISS_KM = 100

con = connect()

con.execute(f"""
    CREATE TABLE storms AS
    WITH t AS (
        SELECT * FROM read_parquet('{IBTRACS}') WHERE SEASON >= 1950 AND USA_WIND >= 64
    ), near AS (
        SELECT SID, MIN(dist_ga_km) AS km_from_ga,
               BOOL_OR(in300) AS hurricane_within_300km,
               BOOL_OR(dist_ga_km <= {NEAR_MISS_KM} AND DIST2LAND > 0 AND LON > -81.9 AND LAT BETWEEN 30.7 AND 32.1)
                   AS offshore_near_miss_ga_coast
        FROM t GROUP BY 1
    ), lf AS (
        SELECT SID, LAT AS landfall_lat, LON AS landfall_lon, ISO_TIME AS landfall_time
        FROM t WHERE DIST2LAND = 0 AND LAT >= 24.5 AND (LON <= -80.0 OR LAT >= 30.0)
        QUALIFY ROW_NUMBER() OVER (PARTITION BY SID ORDER BY ISO_TIME) = 1
    )
    SELECT t.SID, ANY_VALUE(t.SEASON) AS SEASON, ANY_VALUE(t.NAME) AS NAME, MAX(t.USA_WIND) AS max_wind_kt,
           ANY_VALUE(round(near.km_from_ga)) AS hurricane_km_from_ga,
           ANY_VALUE(near.offshore_near_miss_ga_coast) AS offshore_near_miss_ga_coast,
           ANY_VALUE(lf.landfall_lat) AS landfall_lat, ANY_VALUE(lf.landfall_lon) AS landfall_lon,
           CASE WHEN ANY_VALUE(lf.SID) IS NULL THEN 'no_us_hurricane_landfall'
                ELSE ANY_VALUE({LANDFALL_CLASS.replace('LAT', 'lf.landfall_lat').replace('LON', 'lf.landfall_lon')}) END
               AS scenario_class
    FROM t JOIN near USING (SID) LEFT JOIN lf USING (SID)
    WHERE near.hurricane_within_300km
    GROUP BY t.SID
""")
write_csv(con, "SELECT * FROM storms ORDER BY scenario_class, SEASON DESC, SID", "scenario_storms.csv")
storm_counts = con.execute("""
    SELECT scenario_class, COUNT(*), string_agg(NAME || ' ' || SEASON, ', ' ORDER BY SEASON DESC, SID)
    FROM storms GROUP BY 1 ORDER BY 1
""").fetchall()
for row in storm_counts:
    print(row)
near_miss = con.execute("""
    SELECT COUNT(*), string_agg(NAME || ' ' || SEASON, ', ' ORDER BY SEASON DESC, SID)
    FROM storms WHERE offshore_near_miss_ga_coast
""").fetchall()[0]
print("offshore near misses of the GA coast:", near_miss)

con.execute(f"""
    CREATE TABLE roads AS
    WITH r AS (
        SELECT FULLNAME AS route, ST_Transform(geom, 'EPSG:4269', 'EPSG:4326', always_xy := true) AS geom
        FROM ST_Read('{TIGER}')
        WHERE regexp_matches(FULLNAME, '^(I- \\d+|US Hwy \\d+)( |$)')
    )
    SELECT route, ST_Y(ST_Centroid(geom)) AS lat, ST_X(ST_Centroid(geom)) AS lon, geom AS geom_ll,
           ST_Transform(geom, {PROJ}) AS geom
    FROM r
""")
assert one(con, "SELECT COUNT(*) FROM roads WHERE route = 'I- 75'") > 0

con.execute(f"""
    CREATE TABLE gdot_lines AS
    SELECT ROUTE_ID AS route_id, geom AS geom_ll, ST_Transform(geom, {PROJ}) AS geom
    FROM ST_Read('{GDOT / 'hurricane_evacuation_routes.geojson'}')
    UNION ALL
    SELECT 'contraflow ' || TITLE, geom, ST_Transform(geom, {PROJ})
    FROM ST_Read('{GDOT / 'hurricane_evacuation_contraflow_route.geojson'}')
""")
assert one(con, "SELECT COUNT(*) FROM gdot_lines") == 110
con.execute(f"""CREATE TABLE contraflow_points AS
                SELECT ST_Transform(geom, {PROJ}) AS geom FROM ST_Read('{GEMA_CONTRAFLOW}')""")
assert one(con, "SELECT COUNT(*) FROM contraflow_points") == 32


def linestring(pts):
    return f"ST_Transform(ST_GeomFromText('LINESTRING({', '.join(f'{x} {y}' for x, y in pts)})'), {PROJ})"


# GDOT's hurricane layer is the official corridor geometry; TIGER fills only what it does not cover.
ROUTES = {
    "gdot_network": ("GDOT hurricane evacuation routes + contraflow", "SELECT geom FROM gdot_lines"),
    "i75": ("GDOT SR 401 (FL line to Macon) + TIGER I-75 north of Macon",
            f"""SELECT geom FROM gdot_lines WHERE route_id = '{GDOT_I75}'
                UNION ALL SELECT geom FROM roads WHERE route = 'I- 75' AND lat >= {MACON_LAT}"""),
    "i20": ("TIGER I-20 east of Atlanta (not in the GDOT layer)",
            f"SELECT geom FROM roads WHERE route = 'I- 20' AND lon > {ATLANTA_LON}"),
}
route_segments = {name: one(con, f"SELECT COUNT(*) FROM ({sql})") for name, (_, sql) in ROUTES.items()}
print("route segments:", route_segments)

check = {}
for tiger_route, gdot_id, name in (("I- 75", GDOT_I75, "I-75 south (FL line to Macon)"),
                                   ("I- 16", GDOT_I16, "I-16 (Savannah to Macon)")):
    max_lat = MACON_LAT if tiger_route == "I- 75" else 90
    for source, lines in (("gdot", f"SELECT geom_ll FROM gdot_lines WHERE route_id = '{gdot_id}'"),
                          ("tiger", f"SELECT geom_ll FROM roads WHERE route = '{tiger_route}'")):
        km = con.execute(f"""
            WITH v AS (
                SELECT ST_Transform(p, {PROJ}) AS p FROM (
                    SELECT UNNEST(ST_Dump(ST_Points(geom_ll))).geom AS p FROM ({lines})
                ) WHERE ST_Y(p) < {max_lat}
            )
            SELECT max(ST_Distance(p, {linestring(CORRIDORS[name])})) / 1000,
                   quantile_cont(ST_Distance(p, {linestring(CORRIDORS[name])}), 0.5) / 1000
            FROM v
        """).fetchall()[0]
        check.setdefault(name, {})[source] = {"max_km": km[0], "median_km": km[1]}
        print(f"{name}: {source} vertices within max {km[0]:.1f} km, median {km[1]:.1f} km of the approximation")


def total(df, *cols) -> float:
    values = df[cols[0]].fillna(0).to_numpy(dtype=float)
    for c in cols[1:]:
        values = values * df[c].to_numpy(dtype=float)
    return float(values.sum())


def origin_rows(state, counties):
    fips = ", ".join(f"'{c}'" for c in counties)
    return con.execute(f"""
        WITH t AS (
            SELECT county_fips, SUM(total_pop) AS pop, SUM(pop_65_plus) AS pop_65_plus,
                   SUM(households_no_vehicle) AS carless_hh,
                   SUM(households_no_vehicle * total_pop / NULLIF(households, 0)) AS carless_people,
                   SUM(total_pop * lon) / SUM(total_pop) AS lon, SUM(total_pop * lat) / SUM(total_pop) AS lat
            FROM {table(state, 'vulnerability_tracts')} WHERE county_fips IN ({fips}) GROUP BY 1
        )
        SELECT t.*, 1 - t.carless_people / t.pop AS car_share, p.power_dependent_dme
        FROM t JOIN {table(state, 'power_dependent_counties')} p ON p.fips_code = t.county_fips
        ORDER BY t.county_fips
    """).df()


con.execute("""
    CREATE TABLE host_shelters AS
    SELECT shelter_id, county_fips, county_name, clean_capacity, is_medical, wheelchair, geom
    FROM ga_shelters WHERE clean_capacity IS NOT NULL
""")

summary, fills, origins_out = [], [], []
for key, sc in SCENARIOS.items():
    origin_frames = {st: origin_rows(st, o["counties"]) for st, o in sc["origins"].items()}
    for st, df in origin_frames.items():
        assert len(df) == len(sc["origins"][st]["counties"]), (key, st, len(df))
        for _, r in df.iterrows():
            origins_out.append({"scenario": key, "state": st, **r.to_dict()})

    entry = sc["entry"]
    if isinstance(entry, tuple):
        ex, ey = entry
    else:
        tot = sum(total(d, "pop") for d in origin_frames.values())
        ex = sum(total(d, "pop", "lon") for d in origin_frames.values()) / tot
        ey = sum(total(d, "pop", "lat") for d in origin_frames.values()) / tot
    excl = ", ".join(f"'{c}'" for c in sc["exclude_hosts"]) or "''"
    hosts = con.execute(f"""
        WITH r AS ({ROUTES[sc['routes']][1]}),
        s AS (
            SELECT h.* FROM host_shelters h
            WHERE h.county_fips NOT IN ({excl})
              AND EXISTS (SELECT 1 FROM r WHERE ST_DWithin(h.geom, r.geom, {BUF}))
        )
        SELECT county_fips, MIN(county_name) AS county_name,
               COALESCE(SUM(clean_capacity) FILTER (WHERE NOT is_medical), 0) AS general_capacity,
               SUM(clean_capacity) FILTER (WHERE is_medical) AS medical_seats,
               SUM(clean_capacity) FILTER (WHERE wheelchair = 'yes') AS wheelchair_yes_seats,
               SUM(clean_capacity * ST_Distance(geom, ST_Transform(ST_Point({ex}, {ey}), {PROJ}))) / SUM(clean_capacity) / 1000 AS km_from_entry
        FROM s GROUP BY 1 ORDER BY km_from_entry, county_fips
    """)
    cols = [d[0] for d in hosts.description]
    hosts = [dict(zip(cols, row)) for row in hosts.fetchall()]
    contraflow = one(con, f"""SELECT COUNT(*) FROM contraflow_points c WHERE EXISTS (
                                  SELECT 1 FROM ({ROUTES[sc['routes']][1]}) r WHERE ST_DWithin(c.geom, r.geom, 1000))""")
    route_capacity = float(sum(h["general_capacity"] for h in hosts))
    route_medical = float(sum(h["medical_seats"] or 0 for h in hosts))
    route_wheelchair = float(sum(h["wheelchair_yes_seats"] or 0 for h in hosts))
    medical_counties = "; ".join(
        f"{h['county_name']} {h['medical_seats']:.0f}"
        for h in sorted((h for h in hosts if h["medical_seats"]), key=lambda h: -h["medical_seats"]))

    for lvl in LEVELS:
        ev, su, csu = EVACUATION_RATE[lvl], SHELTER_USE[lvl], CARLESS_SHELTER_USE[lvl]
        leave = into_ga = seekers = pd_into = old_into = carless_into = carless_stay = 0.0
        for st, df in origin_frames.items():
            k = ev * sc["origins"][st]["to_ga"][lvl]
            pop, carless = total(df, "pop"), total(df, "carless_people")
            leave += pop * ev
            if st == "GA":
                # Carless Georgians reach inland hosts on public transport, and mostly need a shelter.
                into_ga += pop * k
                old_into += total(df, "pop_65_plus") * k
                pd_into += total(df, "power_dependent_dme") * k
                seekers += (pop - carless) * k * su + carless * k * csu
                carless_into += carless * k
            else:
                # Carless out-of-state residents are assumed not to arrive in Georgia; 65+ and
                # power-dependent residents are assumed carless at their county's average rate.
                into_ga += (pop - carless) * k
                old_into += total(df, "pop_65_plus", "car_share") * k
                pd_into += total(df, "power_dependent_dme", "car_share") * k
                seekers += (pop - carless) * k * su
                carless_stay += carless * k

        remaining, first_full, filled, reached = seekers, None, 0, None
        for i, h in enumerate(hosts):
            cap, km = float(h["general_capacity"]), float(h["km_from_entry"])
            take = min(remaining, cap)
            remaining -= take
            full = cap > 0 and take >= cap
            fills.append({
                "scenario": key, "level": lvl, "fill_order": i + 1, "county_fips": h["county_fips"],
                "county_name": h["county_name"], "km_from_entry": round(km, 1),
                "general_capacity": cap, "seekers_placed": round(take), "is_full": full,
            })
            if full:
                filled += 1
                first_full = first_full or h["county_name"]
            if take > 0:
                reached = round(km, 1)
        summary.append({
            "scenario": key, "label": sc["label"], "level": lvl, "route_source": ROUTES[sc["routes"]][0],
            "evacuation_rate": ev, "shelter_use": su, "carless_shelter_use": csu,
            "to_ga_share": "; ".join(f"{st} {o['to_ga'][lvl]}" for st, o in sc["origins"].items()),
            "people_leaving_origin": round(leave), "people_into_ga_hosts": round(into_ga),
            "pop_65_plus_into_ga": round(old_into), "power_dependent_into_ga": round(pd_into),
            "carless_georgians_needing_transport": round(carless_into),
            "carless_out_of_state_not_arriving": round(carless_stay),
            "shelter_seekers": round(seekers),
            "route_contraflow_intersections": contraflow, "route_host_counties": len(hosts), "route_general_capacity": route_capacity,
            "route_medical_seats": route_medical, "route_medical_seats_by_county": medical_counties,
            "route_wheelchair_yes_seats": route_wheelchair,
            "load_on_route_general_capacity": round(seekers / route_capacity, 3),
            "power_dependent_per_route_medical_seat": round(pd_into / route_medical, 2) if route_medical else None,
            "counties_filled": filled, "first_county_full": first_full,
            "km_reached": reached, "unplaced_seekers": round(remaining),
        })

for name, rows in (("scenario_summary.csv", summary), ("scenario_host_fill.csv", fills),
                   ("scenario_origins.csv", origins_out)):
    with open(OUT / name, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]), lineterminator="\n")
        w.writeheader()
        w.writerows(rows)
for s in summary:
    print({k: s[k] for k in ("scenario", "level", "people_into_ga_hosts", "shelter_seekers", "route_general_capacity",
                             "load_on_route_general_capacity", "counties_filled", "first_county_full", "km_reached",
                             "unplaced_seekers", "power_dependent_into_ga", "route_medical_seats")})

coast = con.execute(f"""
    SELECT COUNT(*), SUM(clean_capacity), COUNT(*) FILTER (WHERE in_surge_slosh_area)
    FROM ga_shelters WHERE clean_capacity IS NOT NULL AND county_fips IN ({', '.join(f"'{c}'" for c in GA_COAST)})
""").fetchall()[0]
candler = con.execute("""
    SELECT COUNT(*) FILTER (WHERE county_fips = '13043'), COUNT(*),
           SUM(clean_capacity) FILTER (WHERE county_fips = '13043'), SUM(clean_capacity)
    FROM ga_shelters WHERE is_medical AND NOT is_duplicate
""").fetchall()[0]

save_numbers("scenarios", {
    "assumptions": {"evacuation_rate": EVACUATION_RATE, "shelter_use": SHELTER_USE,
                    "carless_shelter_use": CARLESS_SHELTER_USE,
                    "to_ga": {k: {st: o["to_ga"] for st, o in sc["origins"].items()} for k, sc in SCENARIOS.items()}},
    "storms_since_1950_hurricane_within_300km": one(con, "SELECT COUNT(*) FROM storms"),
    "storm_classes": {c: {"storms": n, "names": names} for c, n, names in storm_counts},
    "ga_coast_offshore_near_misses": {"storms": near_miss[0], "names": near_miss[1], "km": NEAR_MISS_KM},
    "corridor_check": check,
    "route_segments": route_segments,
    "ga_coast_usable_shelters": coast[0],
    "ga_coast_clean_seats": coast[1],
    "ga_coast_shelters_in_surge": coast[2],
    "candler_medical_shelters": candler[0],
    "medical_shelters": candler[1],
    "candler_medical_seats": candler[2],
    "medical_seats": candler[3],
    "summary": summary,
})
