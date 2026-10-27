from datetime import datetime, timedelta
from pathlib import Path

import duckdb
import pytest

import storm_outages

EAGLEI = Path.home() / "work/extdata/eagle_i"
SUMMARY = EAGLEI / "ga_fl_storm_outage_summary.parquet"
OUTAGES = EAGLEI / "ga_fl_outages_15min.parquet"
CUSTOMERS = EAGLEI / "ga_fl_county_customers.parquet"
FIELDS = ("n_records_window", "peak_customers_out", "peak_time_utc", "eaglei_total_customers_2024", "share_gt_1",
          "hours_above_10pct", "hours_peak_to_90pct_restored", "restore_censored")


@pytest.mark.skipif(not (SUMMARY.exists() and OUTAGES.exists()), reason="EAGLE-I extract not present")
def test_reproduces_published_storm_summary():
    con = duckdb.connect()
    storm_outages.load_customers(con, CUSTOMERS)
    con.execute(f"""CREATE TABLE w AS
        SELECT DISTINCT storm, window_start_local, window_end_local FROM read_parquet('{SUMMARY}')""")
    storm_outages.window_utc(con, "w")
    storm_outages.compute(con, OUTAGES)
    differs = " OR ".join(f"s.{f} IS DISTINCT FROM m.{f}" for f in FIELDS)
    mismatched = con.execute(f"""
        SELECT s.storm, s.fips FROM read_parquet('{SUMMARY}') s
        FULL JOIN storm_county_metrics m USING (storm, fips)
        WHERE s.fips IS NULL OR m.fips IS NULL OR {differs}
           OR abs(s.peak_share - m.peak_share) > 1e-12""").fetchall()
    assert con.execute(f"SELECT count(*) FROM read_parquet('{SUMMARY}')").fetchone() == (2034,)
    assert con.execute("SELECT count(*) FROM storm_county_metrics").fetchone() == (2034,)
    assert mismatched == []


def write_outages(path: Path, rows: list[tuple[str, datetime, int | None]]) -> None:
    con = duckdb.connect()
    con.execute("CREATE TABLE o (fips VARCHAR, run_start_time TIMESTAMP, customers_out BIGINT)")
    con.executemany("INSERT INTO o VALUES (?, ?, ?)", rows)
    con.execute(f"COPY o TO '{path}' (FORMAT PARQUET)")


def test_gaps_nulls_window_start_and_passage(tmp_path):
    start = datetime(2024, 9, 1, 4, 0)
    t = [start + timedelta(minutes=15 * i) for i in range(96)]
    filler: list[tuple[str, datetime, int | None]] = [("13999", ti, 1) for i, ti in enumerate(t) if i != 3]
    rows: list[tuple[str, datetime, int | None]] = filler + [("13001", t[0], 30), ("13003", t[0], 5), ("13001", t[1], 40), ("13001", t[2], None),
            ("13003", t[4], 5), ("13001", t[5], 10), ("13001", t[8], 90), ("13003", t[8], 5)]
    outages = tmp_path / "outages.parquet"
    write_outages(outages, rows)
    con = duckdb.connect()
    con.execute("""CREATE TABLE county_customers AS SELECT * FROM (VALUES
        ('13001', 'A', 'Georgia', 100), ('13003', 'B', 'Georgia', 50))
        t(fips, county, state, eaglei_total_customers_2024)""")
    con.execute("""CREATE TABLE w AS SELECT 'S' AS storm, '2024-09-01' AS window_start_local,
        '2024-09-01' AS window_end_local, TIMESTAMP '2024-09-01 05:45' AS passage_end""")
    storm_outages.window_utc(con, "w", "passage_end")
    storm_outages.compute(con, outages)
    got = {r[0]: r[1:] for r in con.execute("""
        SELECT fips, n_records_window, null_value_intervals, gap_intervals, customers_out_at_window_start,
               peak_customers_out, peak_time_utc, hours_above_10pct
        FROM storm_county_metrics""").fetchall()}
    # t[3] is a statewide gap; 40 carries through the null at t[2] and the gap, so 13001 is >= 10% at
    # t[0..3], t[5] and t[8] (1.5 h). The 90 at t[8] is after passage (05:45), so not the peak.
    assert got["13001"] == (5, 1, 1, 30, 40, t[1], 1.5)
    assert got["13003"] == (3, 0, 1, 5, 5, t[0], 0.75)
