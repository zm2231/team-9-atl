from pathlib import Path

import duckdb

RESTORE_SEARCH_DAYS = 7


def load_customers(con: duckdb.DuckDBPyConnection, path: Path) -> None:
    con.execute(f"""
    CREATE OR REPLACE TABLE county_customers AS
    SELECT fips, county, state, eaglei_total_customers_2024 FROM read_parquet('{path}')""")


def window_utc(con: duckdb.DuckDBPyConnection, windows: str, peak_end: str | None = None) -> None:
    con.execute(f"""
    CREATE OR REPLACE TABLE storm_windows AS
    SELECT *, {peak_end or 'NULL::TIMESTAMP'} AS peak_end_utc,
      timezone('UTC', (window_start_local::DATE)::TIMESTAMP AT TIME ZONE 'America/New_York')::TIMESTAMP AS start_utc,
      timezone('UTC', ((window_end_local::DATE) + 1)::TIMESTAMP AT TIME ZONE 'America/New_York')::TIMESTAMP AS end_utc
    FROM {windows}""")


def compute(con: duckdb.DuckDBPyConnection, outages: Path) -> None:
    con.execute(f"""
    CREATE OR REPLACE TEMP TABLE storm_grid AS
    SELECT w.storm, g.t, g.t < w.end_utc AS in_window, g.t < LEAST(w.end_utc, COALESCE(w.peak_end_utc, w.end_utc)) AS in_peak
    FROM storm_windows w, LATERAL (SELECT unnest(generate_series(w.start_utc,
      w.end_utc + INTERVAL {RESTORE_SEARCH_DAYS} DAY - INTERVAL 15 MINUTE, INTERVAL 15 MINUTE)) AS t) g""")
    con.execute(f"""
    CREATE OR REPLACE TEMP TABLE storm_records AS
    SELECT o.fips, o.run_start_time AS t, o.customers_out
    FROM read_parquet('{outages}') o
    WHERE o.run_start_time IN (SELECT t FROM storm_grid)""")
    con.execute("CREATE OR REPLACE TEMP TABLE storm_live AS SELECT DISTINCT t FROM storm_records")
    con.execute("""
    CREATE OR REPLACE TEMP TABLE storm_dense AS
    SELECT g.storm, g.t, g.in_window, g.in_peak, c.fips, c.eaglei_total_customers_2024 AS total,
           r.t IS NOT NULL AS recorded, r.t IS NOT NULL AND r.customers_out IS NULL AS value_null,
           CASE WHEN l.t IS NULL OR (r.t IS NOT NULL AND r.customers_out IS NULL) THEN NULL
                ELSE COALESCE(r.customers_out, 0) END AS v_raw
    FROM storm_grid g CROSS JOIN county_customers c
    LEFT JOIN storm_live l ON l.t = g.t
    LEFT JOIN storm_records r ON r.fips = c.fips AND r.t = g.t""")
    con.execute("""
    CREATE OR REPLACE TEMP TABLE storm_filled AS
    SELECT *, COALESCE(last_value(v_raw IGNORE NULLS) OVER (PARTITION BY storm, fips ORDER BY t), 0) AS v
    FROM storm_dense""")
    con.execute(f"""
    CREATE OR REPLACE TABLE storm_county_metrics AS
    WITH peak AS (
      SELECT storm, fips, any_value(total) AS total, max(v) FILTER (in_peak) AS peak, count(*) FILTER (recorded) AS n_records_window,
             count(*) FILTER (v_raw IS NULL AND NOT value_null) AS gap_intervals,
             count(*) FILTER (value_null) AS null_value_intervals,
             first(t ORDER BY v DESC, t) FILTER (in_peak) AS peak_t,
             first(v ORDER BY t) AS start_v,
             0.25 * count(*) FILTER (v >= 0.1 * total)::DOUBLE AS hours_above_10pct
      FROM storm_filled WHERE in_window GROUP BY storm, fips),
    restore AS (
      SELECT p.storm, p.fips, min(f.t) AS restored_t
      FROM peak p JOIN storm_filled f ON f.storm = p.storm AND f.fips = p.fips AND f.t >= p.peak_t AND f.v <= 0.1 * p.peak
      WHERE p.peak > 0 GROUP BY p.storm, p.fips)
    SELECT p.storm, p.fips, p.n_records_window, p.gap_intervals, p.null_value_intervals, p.peak AS peak_customers_out,
      CASE WHEN p.peak > 0 THEN p.peak_t END AS peak_time_utc,
      p.total AS eaglei_total_customers_2024, p.peak / p.total AS peak_share, p.peak > p.total AS share_gt_1,
      p.hours_above_10pct,
      CASE WHEN p.peak > 0 THEN date_diff('minute', p.peak_t,
        COALESCE(r.restored_t, w.end_utc + INTERVAL {RESTORE_SEARCH_DAYS} DAY)) / 60.0 END AS hours_peak_to_90pct_restored,
      p.peak > 0 AND r.restored_t IS NULL AS restore_censored, p.start_v AS customers_out_at_window_start
    FROM peak p LEFT JOIN restore r USING (storm, fips) JOIN storm_windows w USING (storm)""")
    for t in ("storm_grid", "storm_records", "storm_live", "storm_dense", "storm_filled"):
        con.execute(f"DROP TABLE {t}")
