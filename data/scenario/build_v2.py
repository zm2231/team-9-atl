import math
import sys
from pathlib import Path

import duckdb
from windfield import (
    NM_KM,
    TrackPoint,
    county_exposure,
    haversine_km,
    interpolate_hourly,
)

EXT = Path("/Volumes/4/GitHub/google-hackathon/prework/data/external")
SNAP = Path("/Volumes/4/GitHub/google-hackathon/prework/data/snapshots/challenge-4-evacuation/GA")
GAZ = Path(sys.argv[2])
HERE = Path(sys.argv[1])
NEAR_KM = 250
PRE_H, POST_H = 24, 48

con = duckdb.connect()
con.execute("set timezone='UTC'")

storms = con.sql(f"""
  SELECT SID, NAME, SEASON FROM '{EXT}/ibtracs/ibtracs_na_within800km_ga.parquet'
  WHERE SEASON BETWEEN 2014 AND 2025 GROUP BY ALL HAVING min(dist_ga_km) < {NEAR_KM} ORDER BY min(ISO_TIME)""").fetchall()

ga = con.sql(f"""
  SELECT county_fips, sum(lat * total_pop) / sum(total_pop), sum(lon * total_pop) / sum(total_pop), sum(total_pop)
  FROM '{SNAP}/vulnerability_tracts/data.parquet' WHERE total_pop > 0 GROUP BY 1""").fetchall()
fl = con.sql(f"""
  SELECT g.GEOID, g.INTPTLAT, trim(g.INTPTLONG)::DOUBLE, c.eaglei_total_customers_2024 * 2.2
  FROM read_csv('{GAZ}', delim='\t', header=true, all_varchar=true) g
  JOIN '{EXT}/eagle_i/ga_fl_county_customers.parquet' c ON c.fips = g.GEOID
  WHERE g.USPS = 'FL'""").fetchall()
counties = [(f, "GA", float(a), float(b), float(p)) for f, a, b, p in ga] + [(f, "FL", float(a), float(b), float(p)) for f, a, b, p in fl]


def mean_radius(vals: tuple) -> float:
    v = [x for x in vals if x is not None and x > 0]
    return sum(v) / len(v) * NM_KM if v else math.nan


def load_track(sid: str) -> list[TrackPoint]:
    rows = con.sql(f"""
      SELECT epoch(ISO_TIME::TIMESTAMP) / 3600.0, USA_LAT, USA_LON, USA_WIND, USA_RMW, USA_R34_NE, USA_R34_SE, USA_R34_SW, USA_R34_NW
      FROM '{EXT}/ibtracs/ibtracs_na_within800km_ga.parquet'
      WHERE SID = '{sid}' AND USA_WIND IS NOT NULL ORDER BY ISO_TIME""").fetchall()
    pts, last_rmw, last_r34 = [], 40.0, 0.0
    for h, lat, lon, w, rmw, *r34 in rows:
        rmw_km = rmw * NM_KM if rmw and rmw > 0 else last_rmw
        r = mean_radius(tuple(r34))
        r34_km = r if not math.isnan(r) else last_r34
        last_rmw, last_r34 = rmw_km, r34_km
        pts.append(TrackPoint(h, lat, lon, float(w), rmw_km, r34_km))
    return interpolate_hourly(pts)


rows = []
for sid, name, season in storms:
    track = load_track(sid)
    if not track:
        continue
    for fips, state, lat, lon, pop in counties:
        e = county_exposure(track, lat, lon)
        t_close = min(track, key=lambda p: haversine_km(lat, lon, p.lat, p.lon)).hour
        rows.append((fips, state, f"{name.title()} {season}", season, pop, t_close, *e.values()))

con.execute("""CREATE TABLE f (fips VARCHAR, state VARCHAR, storm VARCHAR, season INT, pop DOUBLE, t_close DOUBLE,
  peak_wind_kt DOUBLE, hours_34kt DOUBLE, hours_50kt DOUBLE, hours_64kt DOUBLE, min_dist_km DOUBLE, first_34kt_hour DOUBLE)""")
con.executemany("INSERT INTO f VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", rows)
con.execute(f"""CREATE TABLE w AS SELECT fips, min(to_timestamp(t_close * 3600) - INTERVAL {PRE_H} HOUR) lo, max(to_timestamp(t_close * 3600) + INTERVAL {POST_H} HOUR) hi FROM f GROUP BY 1""")
con.execute(f"""CREATE TABLE o AS
  SELECT f.fips, f.storm, max(e.customers_out) peak,
    max(e.customers_out) FILTER (WHERE e.run_start_time < to_timestamp(f.t_close * 3600) - INTERVAL {PRE_H - 3} HOUR) start_level,
    count(*) n_records
  FROM f JOIN '{EXT}/eagle_i/ga_fl_outages_15min.parquet' e
    ON e.fips = f.fips AND e.run_start_time::TIMESTAMPTZ BETWEEN to_timestamp(f.t_close * 3600) - INTERVAL {PRE_H} HOUR
                                                     AND to_timestamp(f.t_close * 3600) + INTERVAL {POST_H} HOUR
  GROUP BY 1, 2""")
con.sql(f"""
  SELECT f.*, c.eaglei_total_customers_2024 customers, o.peak peak_customers_out, o.start_level, o.n_records,
    least(coalesce(o.peak, 0) / c.eaglei_total_customers_2024, 1.0) peak_share,
    CASE WHEN f.season < 2018 THEN 'suspect'
         WHEN o.peak / c.eaglei_total_customers_2024 > 1 THEN 'suspect'
         WHEN o.start_level >= 0.5 * o.peak AND o.peak / c.eaglei_total_customers_2024 >= 0.02 THEN 'carryover'
         ELSE 'recorded' END peak_share_status
  FROM f JOIN '{EXT}/eagle_i/ga_fl_county_customers.parquet' c ON c.fips = f.fips
  LEFT JOIN o ON o.fips = f.fips AND o.storm = f.storm""").write_parquet(str(HERE / "features_v2.parquet"))
print(con.sql(f"""SELECT storm, count(*) n, count(*) FILTER (WHERE peak_share_status='recorded') ok,
  round(avg(peak_share) FILTER (WHERE state='GA'),3) ga, round(avg(peak_share) FILTER (WHERE state='FL'),3) fl,
  round(corr(peak_wind_kt, peak_share),2) r
  FROM '{HERE}/features_v2.parquet' GROUP BY 1 ORDER BY min(season), 1""").fetchall())
