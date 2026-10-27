import os
from pathlib import Path

from common import (
    HERE,
    LANDFALL_CLASS,
    US_LANDFALL,
    connect,
    one,
    save_numbers,
    table,
    write_csv,
)

EXTDATA = Path(os.environ.get("EXTDATA", Path.home() / "work" / "extdata"))
IBTRACS = EXTDATA / "ibtracs" / "ibtracs_na_within800km_ga.parquet"
VTEC = EXTDATA / "nws_vtec" / "ga_fl_tropical_vtec.parquet"
LEAD_TIMES = EXTDATA / "nhc_advisories" / "storm_lead_times.parquet"
GRID_OUT = Path(os.environ.get("GRID_OUT", HERE.parent / "grid" / "out"))
STORM_OUTAGES = GRID_OUT / "county_storm_outages.parquet"
EVAC_ORDERS = HERE.parent.parent / "data" / "clean" / "out" / "evac_orders.parquet"
TROPICAL_STORM_KT = 34

for path in (IBTRACS, VTEC, LEAD_TIMES, STORM_OUTAGES, EVAC_ORDERS):
    if not path.exists():
        raise FileNotFoundError(f"{path} (set EXTDATA or GRID_OUT)")

con = connect()
con.execute("SET TimeZone = 'UTC'")

con.execute(f"""
    CREATE TABLE storms AS
    WITH t AS (SELECT * FROM read_parquet('{IBTRACS}')),
    lf AS (
        SELECT SID, LAT AS landfall_lat, LON AS landfall_lon, USA_WIND AS landfall_wind_kt
        FROM t WHERE {US_LANDFALL} AND USA_WIND >= {TROPICAL_STORM_KT}
        QUALIFY ROW_NUMBER() OVER (PARTITION BY SID ORDER BY ISO_TIME) = 1
    )
    SELECT t.SID AS sid, ANY_VALUE(t.USA_ATCF_ID ORDER BY t.ISO_TIME DESC) AS atcf_id,
           ANY_VALUE(t.NAME) AS name, ANY_VALUE(t.SEASON) AS season, MAX(t.USA_WIND) AS max_wind_kt,
           round(MIN(t.dist_ga_km)) AS closest_km_to_ga, BOOL_OR(t.state = 'GA') AS track_entered_ga,
           ANY_VALUE(lf.landfall_lat) AS landfall_lat, ANY_VALUE(lf.landfall_lon) AS landfall_lon,
           ANY_VALUE(lf.landfall_wind_kt) AS landfall_wind_kt,
           CASE WHEN ANY_VALUE(lf.SID) IS NULL THEN 'no_us_landfall'
                ELSE ANY_VALUE({LANDFALL_CLASS.replace('LAT', 'lf.landfall_lat').replace('LON', 'lf.landfall_lon')})
                END AS origin_class
    FROM t LEFT JOIN lf USING (SID)
    GROUP BY t.SID
""")
storms = one(con, "SELECT COUNT(*) FROM storms")
assert storms == one(con, f"SELECT COUNT(DISTINCT SID) FROM read_parquet('{IBTRACS}')")

con.execute(f"""
    CREATE TABLE vtec AS
    SELECT storm_atcf_id AS atcf_id,
           MIN(issue_utc) FILTER (WHERE state = 'GA' AND significance = 'A') AS ga_first_watch_utc,
           MIN(issue_utc) FILTER (WHERE state = 'GA' AND significance = 'W') AS ga_first_warning_utc,
           COUNT(DISTINCT ugc) FILTER (WHERE state = 'GA') AS ga_zones_with_watch_or_warning
    FROM read_parquet('{VTEC}') GROUP BY 1
""")
con.execute(f"""
    CREATE TABLE leads AS
    SELECT storm_id AS atcf_id, timezone('UTC', ga_ts_wind_onset_utc) AS ga_ts_wind_onset_utc,
           ga_watch_lead_h AS ga_coastal_watch_lead_h_nhc, ga_warning_lead_h AS ga_coastal_warning_lead_h_nhc
    FROM read_parquet('{LEAD_TIMES}')
""")
con.execute(f"""
    CREATE TABLE outages AS
    SELECT upper(storm) AS name, CAST(left(MIN(window_start_local), 4) AS INTEGER) AS season,
           COUNT(*) FILTER (WHERE used_in_tier) AS ga_counties_hit,
           SUM(p.power_dependent_dme) FILTER (WHERE used_in_tier) AS power_dependent_in_hit_counties,
           COUNT(*) FILTER (WHERE peak_share >= 0.10) AS ga_counties_peak_share_10pct_any_quality,
           BOOL_OR(used_in_tier) AS eaglei_usable
    FROM read_parquet('{STORM_OUTAGES}') o
    JOIN {table('GA', 'power_dependent_counties')} p ON p.fips_code = o.fips_code
    GROUP BY storm
""")
con.execute(f"""
    CREATE TABLE orders AS
    SELECT upper(storm) AS name, CAST(season AS INTEGER) AS season,
           MIN(effective_hours_before_low) FILTER (WHERE order_type = 'mandatory') AS mandatory_effective_h_low,
           MAX(effective_hours_before_high) FILTER (WHERE order_type = 'mandatory') AS mandatory_effective_h_high,
           MIN(contraflow_hours_before_low) AS contraflow_h_low, MAX(contraflow_hours_before_high) AS contraflow_h_high
    FROM read_parquet('{EVAC_ORDERS}') GROUP BY 1, 2
""")

con.execute("""
    CREATE TABLE library AS
    SELECT s.*, l.ga_ts_wind_onset_utc, v.ga_first_watch_utc, v.ga_first_warning_utc,
           v.ga_zones_with_watch_or_warning,
           round(date_diff('minute', v.ga_first_watch_utc, l.ga_ts_wind_onset_utc) / 60.0) AS ga_watch_lead_h,
           round(date_diff('minute', v.ga_first_warning_utc, l.ga_ts_wind_onset_utc) / 60.0) AS ga_warning_lead_h,
           round(l.ga_coastal_watch_lead_h_nhc) AS ga_coastal_watch_lead_h_nhc,
           round(l.ga_coastal_warning_lead_h_nhc) AS ga_coastal_warning_lead_h_nhc,
           o.mandatory_effective_h_low, o.mandatory_effective_h_high, o.contraflow_h_low, o.contraflow_h_high,
           g.ga_counties_hit AS eaglei_ga_counties_hit, g.power_dependent_in_hit_counties AS eaglei_power_dependent_in_hit_counties,
           g.ga_counties_peak_share_10pct_any_quality AS eaglei_ga_counties_10pct_any_quality,
           g.eaglei_usable
    FROM storms s
    LEFT JOIN leads l USING (atcf_id)
    LEFT JOIN vtec v USING (atcf_id)
    LEFT JOIN orders o ON o.name = upper(s.name) AND o.season = s.season
    LEFT JOIN outages g ON g.name = upper(s.name) AND g.season = s.season
""")
assert one(con, "SELECT COUNT(*) FROM library") == storms
for label, sql in (
    ("lead-time storms without an IBTrACS storm",
     "SELECT atcf_id FROM leads WHERE atcf_id NOT IN (SELECT atcf_id FROM storms WHERE atcf_id IS NOT NULL)"),
    ("grid outage storms not matched",
     "SELECT name, season FROM outages ANTI JOIN library l ON upper(l.name) = outages.name AND l.season = outages.season"),
    ("evacuation orders not matched",
     "SELECT name, season FROM orders ANTI JOIN library l ON upper(l.name) = orders.name AND l.season = orders.season"),
):
    rows = con.execute(sql).fetchall()
    print(f"unmatched {label}: {len(rows)}" + (f" {rows[:5]}" if rows else ""))

write_csv(con, """
    SELECT * EXCLUDE (ga_ts_wind_onset_utc, ga_first_watch_utc, ga_first_warning_utc),
           strftime(ga_ts_wind_onset_utc, '%Y-%m-%d %H:%M') AS ga_ts_wind_onset_utc,
           strftime(ga_first_watch_utc, '%Y-%m-%d %H:%M') AS ga_first_watch_utc,
           strftime(ga_first_warning_utc, '%Y-%m-%d %H:%M') AS ga_first_warning_utc
    FROM library ORDER BY season, sid""", "storm_library.csv")

by_class = {c: {"storms": n, "since_1950": n50, "with_ga_lead_time": nl, "median_ga_watch_lead_h": w,
                "median_ga_warning_lead_h": wr, "min_ga_watch_lead_h": wmin, "max_ga_watch_lead_h": wmax}
            for c, n, n50, nl, w, wr, wmin, wmax in con.execute("""
    SELECT origin_class, COUNT(*), COUNT(*) FILTER (WHERE season >= 1950),
           COUNT(ga_watch_lead_h), median(ga_watch_lead_h), median(ga_warning_lead_h),
           MIN(ga_watch_lead_h), MAX(ga_watch_lead_h)
    FROM library GROUP BY 1 ORDER BY 1""").fetchall()}
lead_storms = [dict(zip(("name", "season", "origin_class", "watch_h", "warning_h", "coastal_watch_h_nhc",
                         "coastal_warning_h_nhc"), r)) for r in con.execute("""
    SELECT name, season, origin_class, ga_watch_lead_h, ga_warning_lead_h, ga_coastal_watch_lead_h_nhc,
           ga_coastal_warning_lead_h_nhc
    FROM library WHERE ga_watch_lead_h IS NOT NULL OR ga_warning_lead_h IS NOT NULL ORDER BY season, sid""").fetchall()]
outage_storms = [dict(zip(("name", "season", "origin_class", "ga_counties_hit", "power_dependent_in_hit_counties",
                           "ga_counties_10pct_any_quality", "eaglei_usable"), r)) for r in con.execute("""
    SELECT name, season, origin_class, eaglei_ga_counties_hit, eaglei_power_dependent_in_hit_counties,
           eaglei_ga_counties_10pct_any_quality, eaglei_usable
    FROM library WHERE eaglei_usable IS NOT NULL ORDER BY season, sid""").fetchall()]
for r in lead_storms:
    print(r)
for r in outage_storms:
    print(r)
save_numbers("storm_library", {
    "storms": storms,
    "seasons": list(con.execute("SELECT MIN(season), MAX(season) FROM library").fetchall()[0]),
    "by_origin_class": by_class,
    "lead_time_storms": lead_storms,
    "ga_watch_lead_h_all": list(con.execute(
        "SELECT median(ga_watch_lead_h), MIN(ga_watch_lead_h), MAX(ga_watch_lead_h), COUNT(ga_watch_lead_h) "
        "FROM library").fetchall()[0]),
    "outage_storms": outage_storms,
    "evac_order_effective_h_recorded": [r[0] for r in con.execute("""
        SELECT mandatory_effective_h_low FROM library
        WHERE mandatory_effective_h_low = mandatory_effective_h_high ORDER BY 1""").fetchall()],
})
