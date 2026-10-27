from pathlib import Path

import duckdb
import pytest

import storm_outages

EAGLEI = Path.home() / "work/extdata/eagle_i"
SUMMARY = EAGLEI / "ga_fl_storm_outage_summary.parquet"
OUTAGES = EAGLEI / "ga_fl_outages_15min.parquet"
CUSTOMERS = EAGLEI / "ga_fl_county_customers.parquet"


@pytest.mark.skipif(not (SUMMARY.exists() and OUTAGES.exists()), reason="EAGLE-I extract not present")
def test_reproduces_published_storm_summary():
    con = duckdb.connect()
    storm_outages.load_customers(con, CUSTOMERS)
    con.execute(f"""CREATE TABLE w AS
        SELECT DISTINCT storm, window_start_local, window_end_local FROM read_parquet('{SUMMARY}')""")
    storm_outages.window_utc(con, "w")
    storm_outages.compute(con, OUTAGES)
    mismatched = con.execute(f"""
        SELECT s.storm, s.fips FROM read_parquet('{SUMMARY}') s
        LEFT JOIN storm_county_metrics m USING (storm, fips)
        WHERE m.fips IS NULL
           OR s.peak_customers_out <> m.peak_customers_out
           OR s.peak_time_utc IS DISTINCT FROM m.peak_time_utc
           OR s.n_records_window <> m.n_records_window
           OR s.hours_above_10pct <> m.hours_above_10pct
           OR s.hours_peak_to_90pct_restored IS DISTINCT FROM m.hours_peak_to_90pct_restored
           OR s.restore_censored <> m.restore_censored
           OR abs(s.peak_share - m.peak_share) > 1e-12""").fetchall()
    assert con.execute(f"SELECT count(*) FROM read_parquet('{SUMMARY}')").fetchone() == (2034,)
    assert mismatched == []
