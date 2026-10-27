import json
import os
from pathlib import Path

import duckdb

HERE = Path(__file__).resolve().parent
OUT = HERE / "out"
EXT = Path(os.environ.get("GRID_EXTDATA", Path.home() / "work/extdata"))
C4 = Path(os.environ.get("GRID_C4DATA", Path.home() / "work/c4data"))

STORM_SUMMARY = EXT / "eagle_i/ga_fl_storm_outage_summary.parquet"
EIA_RELIABILITY = EXT / "eia861/eia861_reliability_ga_fl.parquet"
EIA_TERRITORY = EXT / "eia861/eia861_service_territory_ga_fl.parquet"
OE417 = EXT / "oe417/oe417_ga_fl_weather_events.csv"
COUNTIES = C4 / "GA/power_dependent_counties/data.parquet"

HIT_SHARE = 0.10
MILTON_ARRIVAL_UTC = "2024-10-10 00:00:00"
EIA_YEARS = (2018, 2024)
LOW_SHARE, LOW_HOURS = 0.50, 72.0
HIGH_SHARE, HIGH_HOURS = 0.25, 24.0

STATUSES = ("recorded", "derived", "low_data", "suspect", "unrecorded")
RULES = {
    "eaglei_storm_window": (
        "EAGLE-I county value for the named-storm window as computed in ga_fl_storm_outage_summary "
        "(15-minute county outages, window in local dates converted to UTC)."),
    "eaglei_share_capped": (
        "peak_customers_out / EAGLE-I 2024 total customers, capped at 1. Status suspect where the uncapped "
        "share exceeds 1 (denominator below the attributed outages)."),
    "eaglei_pre2018_excluded": "Storm before 2018: EAGLE-I has no data-quality index and known overcounts; kept, never used.",
    "milton_helene_carryover": (
        f"Milton row whose peak precedes Milton's arrival ({MILTON_ARRIVAL_UTC} UTC): the peak is Helene's "
        "outage still being restored; kept, never used."),
    "storm_hit": f"Usable storm row (2018+, not Helene carryover) with capped peak share >= {HIT_SHARE}.",
    "storm_not_hit": f"Usable storm row with capped peak share < {HIT_SHARE}: the storm did not test this county's grid.",
    "hit_storm_median": "Median across the county's hit storms. low_data when only one storm hit.",
    "hit_storm_worst": "Maximum across the county's hit storms. low_data when only one storm hit; suspect when it comes from a capped share.",
    "no_hit_storm": f"No 2018+ storm took {HIT_SHARE:.0%} or more of the county's customers out: no measurement.",
    "usable_storm_max": (
        "Maximum capped peak share across all usable storm rows (2018+, not Helene carryover), hit or not: "
        "the worst share of customers out the county has recorded since 2018."),
    "eia_customer_per_county_weight": (
        f"Mean over {EIA_YEARS[0]}-{EIA_YEARS[1]} utility-years with both IEEE SAIDI values, across utilities "
        "whose 2024 EIA-861 service territory includes the county. Each utility weighted by its mean customers / "
        "number of Georgia counties it serves (approximate customers per county, assuming an even spread). "
        "low_data when some serving utilities file no reliability data."),
    "eia_storm_multiplier": "Weighted SAIDI with major event days / weighted SAIDI without major event days.",
    "eia_no_reporting_utility": "No utility serving the county filed SAIDI in EIA-861 for the period.",
    "eia_utility_count": "Utilities whose 2024 EIA-861 service territory lists the county.",
    "tier_fixed_thresholds": (
        f"LOW: worst peak share >= {LOW_SHARE} and worst hours to 90% restored >= {LOW_HOURS:g}. "
        f"HIGH: worst peak share < {HIGH_SHARE} and worst hours to 90% restored < {HIGH_HOURS:g}. "
        "MEDIUM: otherwise. UNKNOWN: no hit storm."),
    "tier_terciles": (
        "Composite = mean of percent ranks of worst peak share and worst hours to 90% restored among tiered "
        "counties; top third LOW, bottom third HIGH."),
    "tier_median_thresholds": "Fixed-threshold rule applied to the median across hit storms instead of the worst.",
    "empower_snapshot": "power_dependent_dme from the team's c4data Georgia power_dependent_counties snapshot.",
}


def sql_rules() -> str:
    return ", ".join(f"'{r}'" for r in RULES)


def build(con: duckdb.DuckDBPyConnection) -> dict:
    con.execute(f"""
    CREATE TABLE counties AS
    SELECT fips_code, NULLIF(TRIM(name), '') AS county, power_dependent_dme
    FROM read_parquet('{COUNTIES}')""")
    assert con.execute("SELECT count(*), count(DISTINCT fips_code) FROM counties").fetchone() == (159, 159)

    con.execute(f"""
    CREATE TABLE storm AS
    WITH s AS (
      SELECT storm, window_start_local, window_end_local, fips AS fips_code, county,
             peak_customers_out, eaglei_total_customers_2024, peak_time_utc, peak_share AS peak_share_uncapped,
             LEAST(peak_share, 1.0) AS peak_share, share_gt_1, hours_above_10pct,
             hours_peak_to_90pct_restored AS restore_90_hours, restore_censored, data_quality_era
      FROM read_parquet('{STORM_SUMMARY}') WHERE fips LIKE '13%')
    SELECT *,
      CASE WHEN data_quality_era <> '2018+' THEN 'eaglei_pre2018_excluded'
           WHEN storm = 'Milton' AND peak_time_utc < TIMESTAMP '{MILTON_ARRIVAL_UTC}' AND peak_share >= {HIT_SHARE}
             THEN 'milton_helene_carryover'
           WHEN peak_share >= {HIT_SHARE} THEN 'storm_hit'
           ELSE 'storm_not_hit' END AS storm_use_rule
    FROM s""")
    con.execute("""
    CREATE TABLE county_storm_outages AS
    SELECT fips_code, county, storm, window_start_local, window_end_local,
      peak_customers_out, eaglei_total_customers_2024, peak_time_utc,
      peak_share, CASE WHEN share_gt_1 THEN 'suspect' WHEN storm_use_rule IN ('eaglei_pre2018_excluded', 'milton_helene_carryover') THEN 'suspect' ELSE 'derived' END AS peak_share_status,
        'eaglei_share_capped' AS peak_share_rule,
      peak_share_uncapped,
      hours_above_10pct, CASE WHEN storm_use_rule IN ('eaglei_pre2018_excluded', 'milton_helene_carryover') THEN 'suspect' ELSE 'recorded' END AS hours_above_10pct_status,
        'eaglei_storm_window' AS hours_above_10pct_rule,
      restore_90_hours, CASE WHEN restore_censored THEN 'unrecorded' WHEN storm_use_rule IN ('eaglei_pre2018_excluded', 'milton_helene_carryover') THEN 'suspect' ELSE 'recorded' END AS restore_90_hours_status,
        'eaglei_storm_window' AS restore_90_hours_rule,
      restore_censored,
      storm_use_rule = 'storm_hit' AS used_in_tier, storm_use_rule AS used_in_tier_rule,
      CASE WHEN storm_use_rule IN ('eaglei_pre2018_excluded', 'milton_helene_carryover') THEN 'suspect' ELSE 'derived' END AS used_in_tier_status
    FROM storm ORDER BY fips_code, window_start_local""")
    assert con.execute("SELECT count(*) FROM county_storm_outages").fetchone()[0] == 159 * 9
    assert con.execute("SELECT count(*) FROM county_storm_outages WHERE used_in_tier AND restore_censored").fetchone()[0] == 0

    con.execute("""
    CREATE TABLE eaglei_county AS
    WITH h AS (SELECT * FROM county_storm_outages WHERE used_in_tier),
    worst AS (
      SELECT fips_code, arg_max(storm, restore_90_hours) AS worst_restore_storm,
             arg_max(peak_share_status, peak_share) AS worst_share_status
      FROM h GROUP BY fips_code)
    SELECT h.fips_code, count(*) AS n_storms_hit, string_agg(storm, ', ' ORDER BY window_start_local) AS storms_hit,
      median(peak_share) AS peak_share_median, max(peak_share) AS peak_share_worst,
      median(hours_above_10pct) AS hours_above_10pct_median, max(hours_above_10pct) AS hours_above_10pct_worst,
      median(restore_90_hours) AS restore_90_hours_median, max(restore_90_hours) AS restore_90_hours_worst,
      any_value(w.worst_restore_storm) AS worst_restore_storm, any_value(w.worst_share_status) AS worst_share_status
    FROM h JOIN worst w USING (fips_code) GROUP BY h.fips_code""")

    con.execute("""
    CREATE TABLE exposure AS
    SELECT fips_code, max(peak_share) AS peak_share_max_2018plus,
      arg_max(peak_share_status, peak_share) AS peak_share_max_2018plus_status
    FROM county_storm_outages WHERE used_in_tier_rule IN ('storm_hit', 'storm_not_hit') GROUP BY fips_code""")
    assert con.execute("SELECT count(*) FROM exposure").fetchone()[0] == 159

    con.execute(f"""
    CREATE TABLE eia_county AS
    WITH terr AS (
      SELECT DISTINCT t.utility_number, k.fips_code
      FROM read_parquet('{EIA_TERRITORY}') t
      LEFT JOIN counties k ON lower(TRIM(t.county)) = lower(k.county)
      WHERE t.state = 'GA' AND t.data_year = 2024),
    rel AS (
      SELECT utility_number, avg(saidi_with_med) AS saidi_with, avg(saidi_without_med) AS saidi_without,
             avg(customers) AS customers, count(*) AS n_years
      FROM read_parquet('{EIA_RELIABILITY}')
      WHERE state = 'GA' AND data_year BETWEEN {EIA_YEARS[0]} AND {EIA_YEARS[1]}
        AND saidi_with_med IS NOT NULL AND saidi_without_med IS NOT NULL AND customers > 0
      GROUP BY utility_number),
    nc AS (SELECT utility_number, count(*) AS n_counties FROM terr GROUP BY utility_number),
    j AS (
      SELECT terr.fips_code, terr.utility_number, rel.saidi_with, rel.saidi_without,
             rel.customers / nc.n_counties AS w
      FROM terr JOIN nc USING (utility_number) LEFT JOIN rel USING (utility_number))
    SELECT fips_code, count(*) AS n_utilities, count(w) AS n_utilities_reporting,
      sum(saidi_with * w) / sum(w) AS saidi_with_med, sum(saidi_without * w) / sum(w) AS saidi_without_med
    FROM j GROUP BY fips_code""")
    unmatched = con.execute(f"""
      SELECT DISTINCT t.county FROM read_parquet('{EIA_TERRITORY}') t
      LEFT JOIN counties k ON lower(TRIM(t.county)) = lower(k.county)
      WHERE t.state = 'GA' AND t.data_year = 2024 AND k.fips_code IS NULL""").fetchall()
    print("EIA-861 territory county names unmatched to FIPS:", [u for (u,) in unmatched] or "none")
    assert not unmatched

    con.execute(f"""
    CREATE TABLE tiers AS
    WITH e AS (SELECT * FROM eaglei_county),
    r AS (
      SELECT fips_code,
        (percent_rank() OVER (ORDER BY peak_share_worst) + percent_rank() OVER (ORDER BY restore_90_hours_worst)) / 2 AS composite
      FROM e),
    t AS (SELECT fips_code, composite, ntile(3) OVER (ORDER BY composite, fips_code) AS third FROM r)
    SELECT e.fips_code,
      CASE WHEN peak_share_worst >= {LOW_SHARE} AND restore_90_hours_worst >= {LOW_HOURS} THEN 'LOW'
           WHEN peak_share_worst < {HIGH_SHARE} AND restore_90_hours_worst < {HIGH_HOURS} THEN 'HIGH'
           ELSE 'MEDIUM' END AS tier,
      t.composite,
      CASE third WHEN 3 THEN 'LOW' WHEN 2 THEN 'MEDIUM' ELSE 'HIGH' END AS tier_terciles,
      CASE WHEN peak_share_median >= {LOW_SHARE} AND restore_90_hours_median >= {LOW_HOURS} THEN 'LOW'
           WHEN peak_share_median < {HIGH_SHARE} AND restore_90_hours_median < {HIGH_HOURS} THEN 'HIGH'
           ELSE 'MEDIUM' END AS tier_median
    FROM e JOIN t USING (fips_code)""")

    con.execute("""
    CREATE TABLE county_grid_reliability AS
    SELECT k.fips_code, k.county,
      COALESCE(t.tier, 'UNKNOWN') AS reliability_tier,
        CASE WHEN t.tier IS NULL THEN 'unrecorded' WHEN e.n_storms_hit = 1 THEN 'low_data' ELSE 'derived' END AS reliability_tier_status,
        CASE WHEN t.tier IS NULL THEN 'no_hit_storm' ELSE 'tier_fixed_thresholds' END AS reliability_tier_rule,
      COALESCE(t.tier_terciles, 'UNKNOWN') AS tier_alt_terciles,
        CASE WHEN t.tier IS NULL THEN 'unrecorded' WHEN e.n_storms_hit = 1 THEN 'low_data' ELSE 'derived' END AS tier_alt_terciles_status,
        CASE WHEN t.tier IS NULL THEN 'no_hit_storm' ELSE 'tier_terciles' END AS tier_alt_terciles_rule,
      COALESCE(t.tier_median, 'UNKNOWN') AS tier_alt_median,
        CASE WHEN t.tier IS NULL THEN 'unrecorded' WHEN e.n_storms_hit = 1 THEN 'low_data' ELSE 'derived' END AS tier_alt_median_status,
        CASE WHEN t.tier IS NULL THEN 'no_hit_storm' ELSE 'tier_median_thresholds' END AS tier_alt_median_rule,
      t.composite AS tier_composite_score,
      t.tier IS NOT NULL AND t.tier = t.tier_terciles AND t.tier = t.tier_median AS tier_stable,
      COALESCE(e.n_storms_hit, 0) AS n_storms_hit, e.storms_hit,
      x.peak_share_max_2018plus, x.peak_share_max_2018plus_status, 'usable_storm_max' AS peak_share_max_2018plus_rule,
      e.peak_share_median,
        CASE WHEN e.fips_code IS NULL THEN 'unrecorded' WHEN e.n_storms_hit = 1 THEN 'low_data' ELSE 'derived' END AS peak_share_median_status,
        CASE WHEN e.fips_code IS NULL THEN 'no_hit_storm' ELSE 'hit_storm_median' END AS peak_share_median_rule,
      e.peak_share_worst,
        CASE WHEN e.fips_code IS NULL THEN 'unrecorded' WHEN e.worst_share_status = 'suspect' THEN 'suspect'
             WHEN e.n_storms_hit = 1 THEN 'low_data' ELSE 'derived' END AS peak_share_worst_status,
        CASE WHEN e.fips_code IS NULL THEN 'no_hit_storm' ELSE 'hit_storm_worst' END AS peak_share_worst_rule,
      e.hours_above_10pct_median,
        CASE WHEN e.fips_code IS NULL THEN 'unrecorded' WHEN e.n_storms_hit = 1 THEN 'low_data' ELSE 'derived' END AS hours_above_10pct_median_status,
        CASE WHEN e.fips_code IS NULL THEN 'no_hit_storm' ELSE 'hit_storm_median' END AS hours_above_10pct_median_rule,
      e.hours_above_10pct_worst,
        CASE WHEN e.fips_code IS NULL THEN 'unrecorded' WHEN e.n_storms_hit = 1 THEN 'low_data' ELSE 'derived' END AS hours_above_10pct_worst_status,
        CASE WHEN e.fips_code IS NULL THEN 'no_hit_storm' ELSE 'hit_storm_worst' END AS hours_above_10pct_worst_rule,
      e.restore_90_hours_median,
        CASE WHEN e.fips_code IS NULL THEN 'unrecorded' WHEN e.n_storms_hit = 1 THEN 'low_data' ELSE 'derived' END AS restore_90_hours_median_status,
        CASE WHEN e.fips_code IS NULL THEN 'no_hit_storm' ELSE 'hit_storm_median' END AS restore_90_hours_median_rule,
      e.restore_90_hours_worst, e.worst_restore_storm,
        CASE WHEN e.fips_code IS NULL THEN 'unrecorded' WHEN e.n_storms_hit = 1 THEN 'low_data' ELSE 'derived' END AS restore_90_hours_worst_status,
        CASE WHEN e.fips_code IS NULL THEN 'no_hit_storm' ELSE 'hit_storm_worst' END AS restore_90_hours_worst_rule,
      a.n_utilities, 'recorded' AS n_utilities_status, 'eia_utility_count' AS n_utilities_rule,
      a.n_utilities_reporting,
      a.saidi_with_med,
        CASE WHEN a.saidi_with_med IS NULL THEN 'unrecorded' WHEN a.n_utilities_reporting < a.n_utilities THEN 'low_data' ELSE 'derived' END AS saidi_with_med_status,
        CASE WHEN a.saidi_with_med IS NULL THEN 'eia_no_reporting_utility' ELSE 'eia_customer_per_county_weight' END AS saidi_with_med_rule,
      a.saidi_without_med,
        CASE WHEN a.saidi_without_med IS NULL THEN 'unrecorded' WHEN a.n_utilities_reporting < a.n_utilities THEN 'low_data' ELSE 'derived' END AS saidi_without_med_status,
        CASE WHEN a.saidi_without_med IS NULL THEN 'eia_no_reporting_utility' ELSE 'eia_customer_per_county_weight' END AS saidi_without_med_rule,
      a.saidi_with_med / NULLIF(a.saidi_without_med, 0) AS storm_multiplier,
        CASE WHEN a.saidi_without_med IS NULL THEN 'unrecorded' WHEN a.n_utilities_reporting < a.n_utilities THEN 'low_data' ELSE 'derived' END AS storm_multiplier_status,
        CASE WHEN a.saidi_without_med IS NULL THEN 'eia_no_reporting_utility' ELSE 'eia_storm_multiplier' END AS storm_multiplier_rule,
      k.power_dependent_dme,
        CASE WHEN k.power_dependent_dme IS NULL THEN 'unrecorded' ELSE 'recorded' END AS power_dependent_dme_status,
        'empower_snapshot' AS power_dependent_dme_rule
    FROM counties k
    LEFT JOIN eaglei_county e USING (fips_code)
    LEFT JOIN exposure x USING (fips_code)
    LEFT JOIN tiers t USING (fips_code)
    LEFT JOIN eia_county a USING (fips_code)
    ORDER BY k.fips_code""")
    assert con.execute("SELECT count(*), count(DISTINCT fips_code) FROM county_grid_reliability").fetchone() == (159, 159)
    assert con.execute("SELECT count(*) FROM county_grid_reliability WHERE n_utilities IS NULL").fetchone()[0] == 0

    for table in ("county_grid_reliability", "county_storm_outages"):
        for (col,) in con.execute(f"SELECT column_name FROM (DESCRIBE {table})").fetchall():
            if col.endswith("_status"):
                bad = con.execute(f"SELECT DISTINCT {col} FROM {table} WHERE {col} NOT IN {STATUSES}").fetchall()
                assert not bad, f"{table}.{col}: unknown status {bad}"
            if col.endswith("_rule"):
                bad = con.execute(f"SELECT DISTINCT {col} FROM {table} WHERE {col} NOT IN ({sql_rules()})").fetchall()
                assert not bad, f"{table}.{col}: unknown rule {bad}"

    return summarize(con)


def rows(con, q: str) -> list[dict]:
    cur = con.execute(q)
    names = [d[0] for d in cur.description]
    return [dict(zip(names, r)) for r in cur.fetchall()]


def summarize(con) -> dict:
    g = "county_grid_reliability"
    order = "CASE reliability_tier WHEN 'LOW' THEN 1 WHEN 'MEDIUM' THEN 2 WHEN 'HIGH' THEN 3 ELSE 4 END"
    return {
        "tiers": rows(con, f"""
          SELECT reliability_tier AS tier, count(*) AS counties, sum(power_dependent_dme)::BIGINT AS power_dependent_dme,
                 sum((n_storms_hit = 1)::INT) AS counties_one_storm
          FROM {g} GROUP BY 1 ORDER BY {order.replace('reliability_tier', 'tier')}"""),
        "sensitivity": rows(con, f"""
          SELECT count(*) FILTER (reliability_tier <> 'UNKNOWN') AS tiered,
                 count(*) FILTER (reliability_tier <> 'UNKNOWN' AND reliability_tier <> tier_alt_terciles) AS changed_vs_terciles,
                 count(*) FILTER (reliability_tier <> 'UNKNOWN' AND reliability_tier <> tier_alt_median) AS changed_vs_median,
                 count(*) FILTER (tier_stable) AS stable_all_three
          FROM {g}""")[0],
        "tier_crosstab_terciles": rows(con, f"""
          SELECT reliability_tier AS tier, tier_alt_terciles AS alt, count(*) AS counties FROM {g}
          WHERE reliability_tier <> 'UNKNOWN' GROUP BY ALL ORDER BY ALL"""),
        "tier_crosstab_median": rows(con, f"""
          SELECT reliability_tier AS tier, tier_alt_median AS alt, count(*) AS counties FROM {g}
          WHERE reliability_tier <> 'UNKNOWN' GROUP BY ALL ORDER BY ALL"""),
        "top_low": rows(con, f"""
          SELECT county, fips_code, power_dependent_dme::BIGINT AS power_dependent_dme, n_storms_hit, storms_hit,
                 round(peak_share_worst, 2) AS peak_share_worst, restore_90_hours_worst, worst_restore_storm,
                 hours_above_10pct_worst, tier_stable
          FROM {g} WHERE reliability_tier = 'LOW' ORDER BY power_dependent_dme DESC, fips_code LIMIT 15"""),
        "unknown_largest": rows(con, f"""
          SELECT county, fips_code, power_dependent_dme::BIGINT AS power_dependent_dme,
                 round(peak_share_max_2018plus, 3) AS peak_share_max_2018plus FROM {g}
          WHERE reliability_tier = 'UNKNOWN' ORDER BY power_dependent_dme DESC, fips_code LIMIT 10"""),
        "unknown_max_share": rows(con, f"""
          SELECT round(max(peak_share_max_2018plus), 3) AS max, round(median(peak_share_max_2018plus), 3) AS median
          FROM {g} WHERE reliability_tier = 'UNKNOWN'""")[0],
        "unknown_irma_hit": con.execute(f"""
          SELECT count(DISTINCT s.fips_code) FROM county_storm_outages s JOIN {g} USING (fips_code)
          WHERE reliability_tier = 'UNKNOWN' AND storm = 'Irma' AND peak_share >= {HIT_SHARE}""").fetchone()[0],
        "storm_hits": rows(con, """
          SELECT storm, count(*) FILTER (used_in_tier) AS counties_hit,
                 count(*) FILTER (used_in_tier_rule = 'milton_helene_carryover') AS helene_carryover,
                 count(*) FILTER (used_in_tier AND peak_share_status = 'suspect') AS share_capped
          FROM county_storm_outages GROUP BY storm ORDER BY min(window_start_local)"""),
        "eia": rows(con, f"""
          SELECT count(*) FILTER (saidi_with_med IS NOT NULL) AS counties_with_saidi,
                 count(*) FILTER (saidi_with_med_status = 'derived') AS counties_all_utilities_report,
                 round(median(storm_multiplier), 2) AS median_multiplier,
                 round(quantile_cont(storm_multiplier, 0.1), 2) AS p10_multiplier,
                 round(quantile_cont(storm_multiplier, 0.9), 2) AS p90_multiplier
          FROM {g}""")[0],
        "eia_multiplier_by_tier": rows(con, f"""
          SELECT reliability_tier AS tier, round(median(storm_multiplier), 2) AS median_multiplier,
                 count(storm_multiplier) AS counties_with_multiplier
          FROM {g} GROUP BY 1 ORDER BY {order.replace('reliability_tier', 'tier')}"""),
        "oe417_crosscheck": rows(con, f"""
          WITH o AS (
            SELECT storm_window AS storm, count(*) AS oe417_ga_filings,
                   sum(TRY_CAST("Number of Customers Affected" AS BIGINT)) AS oe417_customers
            FROM read_csv('{OE417}') WHERE state_ga AND storm_window IS NOT NULL GROUP BY 1),
          e AS (SELECT storm, sum(peak_customers_out) AS eaglei_sum_county_peaks FROM county_storm_outages GROUP BY 1)
          SELECT storm, oe417_ga_filings, oe417_customers, eaglei_sum_county_peaks
          FROM o LEFT JOIN e USING (storm) ORDER BY storm"""),
        "params": {"hit_share": HIT_SHARE, "low_share": LOW_SHARE, "low_hours": LOW_HOURS,
                   "high_share": HIGH_SHARE, "high_hours": HIGH_HOURS, "eia_years": list(EIA_YEARS),
                   "milton_arrival_utc": MILTON_ARRIVAL_UTC},
        "rules": RULES,
    }


def main() -> None:
    OUT.mkdir(exist_ok=True)
    con = duckdb.connect(config={"threads": 1})
    summary = build(con)
    for table in ("county_grid_reliability", "county_storm_outages"):
        con.execute(f"COPY {table} TO '{OUT / table}.parquet' (FORMAT PARQUET)")
    con.execute(f"COPY county_grid_reliability TO '{OUT / 'county_grid_reliability.csv'}' (HEADER)")
    (OUT / "summary.json").write_text(json.dumps(summary, indent=2, default=str) + "\n")
    print(json.dumps({k: summary[k] for k in ("tiers", "sensitivity", "eia", "storm_hits")}, indent=2, default=str))


if __name__ == "__main__":
    main()
