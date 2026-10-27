import hashlib
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
INPUTS = (STORM_SUMMARY, EIA_RELIABILITY, EIA_TERRITORY, OE417, COUNTIES)

HIT_SHARE = 0.10
MILTON_ARRIVAL_UTC = "2024-10-10 00:00:00"
EIA_YEARS = (2018, 2024)
LOW_SHARE, LOW_HOURS = 0.50, 72.0
HIGH_SHARE, HIGH_HOURS = 0.25, 24.0

STATUSES = ("recorded", "derived", "low_data", "suspect", "unrecorded", "baseline_only")
RULES = {
    "eaglei_storm_window": (
        "EAGLE-I county value for the named-storm window as computed in ga_fl_storm_outage_summary "
        "(15-minute county outages, window in local dates converted to UTC). Status suspect on rows never used."),
    "eaglei_share_capped": (
        "peak_customers_out / EAGLE-I 2024 total customers, capped at 1. Status suspect where the uncapped "
        "share exceeds 1 (denominator below the attributed outages) and on rows never used."),
    "eaglei_hours_above_10pct": (
        "Hours with customers out >= 10% of EAGLE-I 2024 total customers. Status suspect where the peak share "
        "exceeds 1 (same too-small denominator) and on rows never used."),
    "eaglei_pre2018_excluded": "Storm before 2018: EAGLE-I has no data-quality index and known overcounts; kept, never used.",
    "milton_helene_carryover": (
        f"Milton row whose peak precedes Milton's arrival ({MILTON_ARRIVAL_UTC} UTC): the Helene and Milton "
        "windows overlap, so the peak is Helene's outage still being restored; kept, never used."),
    "storm_hit": f"Usable storm row (2018+, not Helene carryover) with capped peak share >= {HIT_SHARE}.",
    "storm_not_hit": f"Usable storm row with capped peak share < {HIT_SHARE}: the storm did not test this county's grid.",
    "hit_storm_count": "Number and list of the county's hit storms.",
    "hit_storm_median": (
        "Median across the county's hit storms. suspect when any hit storm's input is suspect; low_data when "
        "only one storm hit."),
    "hit_storm_worst": (
        "Maximum across the county's hit storms (and the storm it came from). suspect when the maximum comes "
        "from a suspect row; low_data when only one storm hit."),
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
    "eia_utility_count": "Utilities whose 2024 EIA-861 service territory lists the county, and how many of them filed SAIDI.",
    "eia_baseline_terciles": (
        "Baseline only, no storm test. Composite = mean of percent ranks of weighted SAIDI with major event days "
        "and the storm multiplier among counties with both; top third LOW, bottom third HIGH. Utility-wide "
        "annual figures, not a county storm measurement."),
    "tier_fixed_thresholds": (
        f"LOW: worst peak share >= {LOW_SHARE} and worst hours to 90% restored >= {LOW_HOURS:g}. "
        f"HIGH: worst peak share < {HIGH_SHARE} and worst hours to 90% restored < {HIGH_HOURS:g}. "
        "MEDIUM: otherwise. UNKNOWN: no hit storm. suspect when the worst peak share is suspect."),
    "tier_terciles": (
        "Composite = mean of percent ranks of worst peak share and worst hours to 90% restored among tiered "
        "counties; top third LOW, bottom third HIGH."),
    "tier_median_thresholds": "Fixed-threshold rule applied to the median across hit storms instead of the worst.",
    "tier_stable_all_rules": "True when the fixed-threshold, tercile and median rules give the same tier.",
    "empower_snapshot": "power_dependent_dme from the team's c4data Georgia power_dependent_counties snapshot.",
}

KEYS = {
    "county_storm_outages": {"fips_code", "county", "storm", "window_start_local", "window_end_local"},
    "county_grid_reliability": {"fips_code", "county"},
}
PROVENANCE_GROUPS = {
    "peak_customers_out": "eaglei_record",
    "eaglei_total_customers_2024": "eaglei_record",
    "peak_time_utc": "eaglei_record",
    "restore_censored": "eaglei_record",
    "peak_share_uncapped": "peak_share",
    "tier_composite_score": "tier_alt_terciles",
    "storms_hit": "n_storms_hit",
    "worst_restore_storm": "restore_90_hours_worst",
    "n_utilities_reporting": "n_utilities",
    "baseline_composite_score": "baseline_tier",
}
EXCLUDED = "storm_use_rule IN ('eaglei_pre2018_excluded', 'milton_helene_carryover')"


def check(cond: bool, msg: str) -> None:
    if not cond:
        raise AssertionError(msg)


def scalar(con: duckdb.DuckDBPyConnection, q: str):
    row = con.execute(q).fetchone()
    if row is None:
        raise AssertionError(f"no row: {q}")
    return row[0]


def storm_status(suspect: str) -> str:
    return (f"CASE WHEN e.fips_code IS NULL THEN 'unrecorded' WHEN {suspect} THEN 'suspect' "
            "WHEN e.n_storms_hit = 1 THEN 'low_data' ELSE 'derived' END")


def storm_rule(rule: str) -> str:
    return f"CASE WHEN e.fips_code IS NULL THEN 'no_hit_storm' ELSE '{rule}' END"


def storm_metric(expr: str, name: str, suspect: str, rule: str) -> str:
    return f"{expr} AS {name}, {storm_status(suspect)} AS {name}_status, {storm_rule(rule)} AS {name}_rule"


def eia_metric(expr: str, name: str, rule: str) -> str:
    return (f"{expr} AS {name}, CASE WHEN {expr} IS NULL THEN 'unrecorded' "
            f"WHEN a.n_utilities_reporting < a.n_utilities THEN 'low_data' ELSE 'derived' END AS {name}_status, "
            f"CASE WHEN {expr} IS NULL THEN 'eia_no_reporting_utility' ELSE '{rule}' END AS {name}_rule")


def tercile(third: str) -> str:
    return f"CASE {third} WHEN 3 THEN 'LOW' WHEN 2 THEN 'MEDIUM' WHEN 1 THEN 'HIGH' END"


def thresholds(share: str, hours: str) -> str:
    return (f"CASE WHEN {share} >= {LOW_SHARE} AND {hours} >= {LOW_HOURS} THEN 'LOW' "
            f"WHEN {share} < {HIGH_SHARE} AND {hours} < {HIGH_HOURS} THEN 'HIGH' ELSE 'MEDIUM' END")


def build(con: duckdb.DuckDBPyConnection) -> dict:
    con.execute(f"""
    CREATE TABLE counties AS
    SELECT fips_code, NULLIF(TRIM(name), '') AS county, power_dependent_dme
    FROM read_parquet('{COUNTIES}')""")
    check(con.execute("SELECT count(*), count(DISTINCT fips_code) FROM counties").fetchone() == (159, 159),
          "counties: expected 159 unique fips_code")

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
           WHEN storm = 'Milton' AND peak_time_utc < TIMESTAMP '{MILTON_ARRIVAL_UTC}' THEN 'milton_helene_carryover'
           WHEN peak_share >= {HIT_SHARE} THEN 'storm_hit'
           ELSE 'storm_not_hit' END AS storm_use_rule
    FROM s""")
    con.execute(f"""
    CREATE TABLE county_storm_outages AS
    SELECT fips_code, county, storm, window_start_local, window_end_local,
      peak_customers_out, eaglei_total_customers_2024, peak_time_utc, restore_censored,
        CASE WHEN {EXCLUDED} THEN 'suspect' ELSE 'recorded' END AS eaglei_record_status,
        'eaglei_storm_window' AS eaglei_record_rule,
      peak_share, peak_share_uncapped,
        CASE WHEN share_gt_1 OR {EXCLUDED} THEN 'suspect' ELSE 'derived' END AS peak_share_status,
        'eaglei_share_capped' AS peak_share_rule,
      hours_above_10pct,
        CASE WHEN share_gt_1 OR {EXCLUDED} THEN 'suspect' ELSE 'recorded' END AS hours_above_10pct_status,
        'eaglei_hours_above_10pct' AS hours_above_10pct_rule,
      restore_90_hours,
        CASE WHEN restore_censored THEN 'unrecorded' WHEN {EXCLUDED} THEN 'suspect' ELSE 'recorded' END
          AS restore_90_hours_status,
        'eaglei_storm_window' AS restore_90_hours_rule,
      storm_use_rule = 'storm_hit' AS used_in_tier,
        CASE WHEN {EXCLUDED} THEN 'suspect' ELSE 'derived' END AS used_in_tier_status,
        storm_use_rule AS used_in_tier_rule
    FROM storm ORDER BY fips_code, window_start_local""")
    check(scalar(con, "SELECT count(*) FROM county_storm_outages") == 159 * 9, "storm rows: expected 159 x 9")
    check(scalar(con, "SELECT count(*) FROM county_storm_outages WHERE used_in_tier AND restore_censored") == 0,
          "a censored restore time feeds a tier")
    check(scalar(con, f"""SELECT count(*) FROM county_storm_outages WHERE storm = 'Milton'
                           AND peak_time_utc < TIMESTAMP '{MILTON_ARRIVAL_UTC}'
                           AND used_in_tier_rule <> 'milton_helene_carryover'""") == 0,
          "pre-arrival Milton row not marked carryover")

    con.execute("""
    CREATE TABLE eaglei_county AS
    SELECT fips_code, count(*) AS n_storms_hit, string_agg(storm, ', ' ORDER BY window_start_local) AS storms_hit,
      median(peak_share) AS peak_share_median, max(peak_share) AS peak_share_worst,
      median(hours_above_10pct) AS hours_above_10pct_median, max(hours_above_10pct) AS hours_above_10pct_worst,
      median(restore_90_hours) AS restore_90_hours_median, max(restore_90_hours) AS restore_90_hours_worst,
      arg_max(storm, restore_90_hours) AS worst_restore_storm,
      bool_or(peak_share_status = 'suspect') AS share_suspect_any,
      arg_max(peak_share_status, peak_share) = 'suspect' AS share_suspect_worst,
      bool_or(hours_above_10pct_status = 'suspect') AS hours_suspect_any,
      arg_max(hours_above_10pct_status, hours_above_10pct) = 'suspect' AS hours_suspect_worst
    FROM county_storm_outages WHERE used_in_tier GROUP BY fips_code""")

    con.execute("""
    CREATE TABLE exposure AS
    SELECT fips_code, max(peak_share) AS peak_share_max_2018plus,
      arg_max(peak_share_status, peak_share) AS peak_share_max_2018plus_status
    FROM county_storm_outages WHERE used_in_tier_rule IN ('storm_hit', 'storm_not_hit') GROUP BY fips_code""")
    check(scalar(con, "SELECT count(*) FROM exposure") == 159, "exposure: expected 159 counties")

    con.execute(f"""
    CREATE TABLE eia_territory AS
    SELECT DISTINCT t.utility_number, k.fips_code
    FROM read_parquet('{EIA_TERRITORY}') t
    LEFT JOIN counties k ON lower(TRIM(t.county)) = lower(k.county)
    WHERE t.state = 'GA' AND t.data_year = 2024""")
    unmatched = con.execute(f"""
      SELECT DISTINCT t.county FROM read_parquet('{EIA_TERRITORY}') t
      LEFT JOIN counties k ON lower(TRIM(t.county)) = lower(k.county)
      WHERE t.state = 'GA' AND t.data_year = 2024 AND k.fips_code IS NULL""").fetchall()
    print("EIA-861 territory county names unmatched to FIPS:", [u for (u,) in unmatched] or "none")
    check(not unmatched, f"unmatched EIA county names: {unmatched}")
    con.execute(f"""
    CREATE TABLE eia_utility AS
    SELECT utility_number, avg(saidi_with_med) AS saidi_with, avg(saidi_without_med) AS saidi_without,
           avg(customers) AS customers
    FROM read_parquet('{EIA_RELIABILITY}')
    WHERE state = 'GA' AND data_year BETWEEN {EIA_YEARS[0]} AND {EIA_YEARS[1]}
      AND saidi_with_med IS NOT NULL AND saidi_without_med IS NOT NULL AND customers > 0
    GROUP BY utility_number""")
    con.execute("""
    CREATE TABLE eia_county AS
    WITH nc AS (SELECT utility_number, count(*) AS n_counties FROM eia_territory GROUP BY utility_number),
    j AS (
      SELECT t.fips_code, u.saidi_with, u.saidi_without, u.customers / nc.n_counties AS w
      FROM eia_territory t JOIN nc USING (utility_number) LEFT JOIN eia_utility u USING (utility_number)),
    c AS (
      SELECT fips_code, count(*) AS n_utilities, count(w) AS n_utilities_reporting,
        sum(saidi_with * w) / sum(w) AS saidi_with_med, sum(saidi_without * w) / sum(w) AS saidi_without_med
      FROM j GROUP BY fips_code),
    m AS (SELECT *, saidi_with_med / NULLIF(saidi_without_med, 0) AS storm_multiplier FROM c),
    r AS (
      SELECT fips_code,
        (percent_rank() OVER (ORDER BY saidi_with_med) + percent_rank() OVER (ORDER BY storm_multiplier)) / 2
          AS baseline_composite_score
      FROM m WHERE saidi_with_med IS NOT NULL AND storm_multiplier IS NOT NULL),
    t AS (SELECT *, ntile(3) OVER (ORDER BY baseline_composite_score, fips_code) AS third FROM r)
    SELECT m.*, t.baseline_composite_score, t.third AS baseline_third
    FROM m LEFT JOIN t USING (fips_code)""")

    con.execute(f"""
    CREATE TABLE tiers AS
    WITH r AS (
      SELECT fips_code,
        (percent_rank() OVER (ORDER BY peak_share_worst) + percent_rank() OVER (ORDER BY restore_90_hours_worst)) / 2
          AS composite
      FROM eaglei_county),
    t AS (SELECT fips_code, composite, ntile(3) OVER (ORDER BY composite, fips_code) AS third FROM r)
    SELECT e.fips_code,
      {thresholds('peak_share_worst', 'restore_90_hours_worst')} AS tier,
      t.composite,
      {tercile('third')} AS tier_terciles,
      {thresholds('peak_share_median', 'restore_90_hours_median')} AS tier_median
    FROM eaglei_county e JOIN t USING (fips_code)""")

    con.execute(f"""
    CREATE TABLE county_grid_reliability AS
    SELECT k.fips_code, k.county,
      {storm_metric("COALESCE(t.tier, 'UNKNOWN')", 'reliability_tier', 'e.share_suspect_worst', 'tier_fixed_thresholds')},
      {storm_metric("COALESCE(t.tier_terciles, 'UNKNOWN')", 'tier_alt_terciles', 'e.share_suspect_worst', 'tier_terciles')},
      t.composite AS tier_composite_score,
      {storm_metric("COALESCE(t.tier_median, 'UNKNOWN')", 'tier_alt_median', 'e.share_suspect_any', 'tier_median_thresholds')},
      {storm_metric('t.tier = t.tier_terciles AND t.tier = t.tier_median', 'tier_stable', 'e.share_suspect_any', 'tier_stable_all_rules')},
      COALESCE(e.n_storms_hit, 0) AS n_storms_hit, e.storms_hit,
        'derived' AS n_storms_hit_status, 'hit_storm_count' AS n_storms_hit_rule,
      x.peak_share_max_2018plus, x.peak_share_max_2018plus_status, 'usable_storm_max' AS peak_share_max_2018plus_rule,
      {storm_metric('e.peak_share_median', 'peak_share_median', 'e.share_suspect_any', 'hit_storm_median')},
      {storm_metric('e.peak_share_worst', 'peak_share_worst', 'e.share_suspect_worst', 'hit_storm_worst')},
      {storm_metric('e.hours_above_10pct_median', 'hours_above_10pct_median', 'e.hours_suspect_any', 'hit_storm_median')},
      {storm_metric('e.hours_above_10pct_worst', 'hours_above_10pct_worst', 'e.hours_suspect_worst', 'hit_storm_worst')},
      {storm_metric('e.restore_90_hours_median', 'restore_90_hours_median', 'false', 'hit_storm_median')},
      {storm_metric('e.restore_90_hours_worst', 'restore_90_hours_worst', 'false', 'hit_storm_worst')},
      e.worst_restore_storm,
      a.n_utilities, a.n_utilities_reporting, 'recorded' AS n_utilities_status, 'eia_utility_count' AS n_utilities_rule,
      {eia_metric('a.saidi_with_med', 'saidi_with_med', 'eia_customer_per_county_weight')},
      {eia_metric('a.saidi_without_med', 'saidi_without_med', 'eia_customer_per_county_weight')},
      {eia_metric('a.storm_multiplier', 'storm_multiplier', 'eia_storm_multiplier')},
      COALESCE({tercile('a.baseline_third')}, 'UNKNOWN') AS baseline_tier, a.baseline_composite_score,
        CASE WHEN a.baseline_third IS NULL THEN 'unrecorded' ELSE 'baseline_only' END AS baseline_tier_status,
        CASE WHEN a.baseline_third IS NULL THEN 'eia_no_reporting_utility' ELSE 'eia_baseline_terciles' END
          AS baseline_tier_rule,
      k.power_dependent_dme,
        CASE WHEN k.power_dependent_dme IS NULL THEN 'unrecorded' ELSE 'recorded' END AS power_dependent_dme_status,
        'empower_snapshot' AS power_dependent_dme_rule
    FROM counties k
    LEFT JOIN eaglei_county e USING (fips_code)
    LEFT JOIN exposure x USING (fips_code)
    LEFT JOIN tiers t USING (fips_code)
    LEFT JOIN eia_county a USING (fips_code)
    ORDER BY k.fips_code""")
    check(con.execute("SELECT count(*), count(DISTINCT fips_code) FROM county_grid_reliability").fetchone() == (159, 159),
          "county_grid_reliability: expected 159 unique fips_code")
    check(scalar(con, "SELECT count(*) FROM county_grid_reliability WHERE n_utilities IS NULL") == 0,
          "county with no EIA territory utility")
    check(scalar(con, """SELECT count(*) FROM county_grid_reliability
                          WHERE (reliability_tier = 'UNKNOWN') <> (n_storms_hit = 0)""") == 0,
          "UNKNOWN must equal no hit storm")

    for table in KEYS:
        check_provenance(con, table)
    return summarize(con)


def check_provenance(con: duckdb.DuckDBPyConnection, table: str) -> None:
    cols = [c for (c,) in con.execute(f"SELECT column_name FROM (DESCRIBE {table})").fetchall()]
    have = set(cols)
    metrics = [c for c in cols if c not in KEYS[table] and not c.endswith(("_status", "_rule"))]
    missing = [c for c in metrics
               if not {f"{PROVENANCE_GROUPS.get(c, c)}_status", f"{PROVENANCE_GROUPS.get(c, c)}_rule"} <= have]
    check(not missing, f"{table}: columns without _status and _rule: {missing}")
    for c in cols:
        if c.endswith("_status"):
            bad = con.execute(f"SELECT DISTINCT {c} FROM {table} WHERE {c} IS NULL OR {c} NOT IN {STATUSES}").fetchall()
            check(not bad, f"{table}.{c}: unknown status {bad}")
        if c.endswith("_rule"):
            rules = ", ".join(f"'{r}'" for r in RULES)
            bad = con.execute(f"SELECT DISTINCT {c} FROM {table} WHERE {c} IS NULL OR {c} NOT IN ({rules})").fetchall()
            check(not bad, f"{table}.{c}: unknown rule {bad}")


def rows(con, q: str) -> list[dict]:
    cur = con.execute(q)
    names = [d[0] for d in cur.description]
    return [dict(zip(names, r)) for r in cur.fetchall()]


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def summarize(con) -> dict:
    g = "county_grid_reliability"
    order = "CASE tier WHEN 'LOW' THEN 1 WHEN 'MEDIUM' THEN 2 WHEN 'HIGH' THEN 3 ELSE 4 END"
    return {
        "inputs": {str(p.relative_to(EXT if p.is_relative_to(EXT) else C4)): sha256(p) for p in INPUTS},
        "tiers": rows(con, f"""
          SELECT reliability_tier AS tier, count(*) AS counties, sum(power_dependent_dme)::BIGINT AS power_dependent_dme,
                 count(*) FILTER (n_storms_hit = 1) AS counties_one_storm,
                 count(*) FILTER (reliability_tier_status = 'suspect') AS counties_suspect
          FROM {g} GROUP BY 1 ORDER BY {order}"""),
        "power_dependent_total": scalar(con, f"SELECT sum(power_dependent_dme)::BIGINT FROM {g}"),
        "tier_status": rows(con, f"""
          SELECT reliability_tier_status AS status, count(*) AS counties FROM {g} GROUP BY 1 ORDER BY 1"""),
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
                 round(peak_share_worst, 2) AS peak_share_worst, peak_share_worst_status,
                 restore_90_hours_worst, worst_restore_storm, hours_above_10pct_worst, tier_stable
          FROM {g} WHERE reliability_tier = 'LOW' ORDER BY power_dependent_dme DESC, fips_code LIMIT 15"""),
        "unknown_largest": rows(con, f"""
          SELECT county, fips_code, power_dependent_dme::BIGINT AS power_dependent_dme,
                 round(peak_share_max_2018plus, 3) AS peak_share_max_2018plus, baseline_tier
          FROM {g} WHERE reliability_tier = 'UNKNOWN' ORDER BY power_dependent_dme DESC, fips_code LIMIT 10"""),
        "unknown_max_share": rows(con, f"""
          SELECT round(max(peak_share_max_2018plus), 3) AS max, round(median(peak_share_max_2018plus), 3) AS median
          FROM {g} WHERE reliability_tier = 'UNKNOWN'""")[0],
        "unknown_irma_hit": scalar(con, f"""
          SELECT count(DISTINCT s.fips_code) FROM county_storm_outages s JOIN {g} USING (fips_code)
          WHERE reliability_tier = 'UNKNOWN' AND storm = 'Irma' AND peak_share >= {HIT_SHARE}"""),
        "storm_hits": rows(con, f"""
          SELECT storm, count(*) FILTER (used_in_tier) AS counties_hit,
                 count(*) FILTER (used_in_tier_rule = 'milton_helene_carryover') AS helene_carryover,
                 count(*) FILTER (used_in_tier_rule = 'milton_helene_carryover' AND peak_share >= {HIT_SHARE}) AS helene_carryover_hit,
                 count(*) FILTER (used_in_tier AND peak_share_uncapped > 1) AS share_capped
          FROM county_storm_outages GROUP BY storm ORDER BY min(window_start_local)"""),
        "eia": rows(con, f"""
          SELECT (SELECT count(DISTINCT utility_number) FROM eia_territory) AS ga_territory_utilities,
                 (SELECT count(DISTINCT t.utility_number) FROM eia_territory t JOIN eia_utility USING (utility_number))
                   AS utilities_reporting_saidi,
                 count(*) FILTER (saidi_with_med IS NOT NULL) AS counties_with_saidi,
                 count(*) FILTER (saidi_with_med_status = 'derived') AS counties_all_utilities_report,
                 round(median(storm_multiplier), 2) AS median_multiplier,
                 round(quantile_cont(storm_multiplier, 0.1), 2) AS p10_multiplier,
                 round(quantile_cont(storm_multiplier, 0.9), 2) AS p90_multiplier
          FROM {g}""")[0],
        "eia_largest_territory": rows(con, f"""
          WITH u AS (
            SELECT utility_number, count(DISTINCT fips_code) AS counties FROM eia_territory
            GROUP BY 1 ORDER BY counties DESC, utility_number LIMIT 1)
          SELECT u.utility_number, u.counties,
                 (SELECT any_value(ownership) FROM read_parquet('{EIA_RELIABILITY}') r
                   WHERE r.utility_number = u.utility_number AND r.state = 'GA') AS ownership,
                 (SELECT list(k.county ORDER BY k.county) FROM counties k
                   WHERE k.fips_code NOT IN (SELECT fips_code FROM eia_territory t WHERE t.utility_number = u.utility_number))
                   AS counties_not_listed,
                 (SELECT count(DISTINCT utility_number) FROM read_parquet('{EIA_RELIABILITY}')
                   WHERE state = 'GA' AND ownership = 'Investor Owned') AS ga_investor_owned_utilities
          FROM u""")[0],
        "eia_multiplier_by_tier": rows(con, f"""
          SELECT reliability_tier AS tier, round(median(storm_multiplier), 2) AS median_multiplier,
                 count(storm_multiplier) AS counties_with_multiplier
          FROM {g} GROUP BY 1 ORDER BY {order}"""),
        "baseline_tiers": rows(con, f"""
          SELECT baseline_tier AS tier, count(*) AS counties, sum(power_dependent_dme)::BIGINT AS power_dependent_dme,
                 count(*) FILTER (reliability_tier = 'UNKNOWN') AS counties_storm_unknown,
                 sum(power_dependent_dme) FILTER (reliability_tier = 'UNKNOWN')::BIGINT AS power_dependent_storm_unknown
          FROM {g} GROUP BY 1 ORDER BY {order}"""),
        "baseline_vs_storm_tier": rows(con, f"""
          SELECT reliability_tier AS tier, baseline_tier AS baseline, count(*) AS counties FROM {g}
          WHERE reliability_tier <> 'UNKNOWN' GROUP BY ALL ORDER BY ALL"""),
        "baseline_agreement": rows(con, f"""
          SELECT count(*) AS tiered_both, count(*) FILTER (reliability_tier = baseline_tier) AS same_tier
          FROM {g} WHERE reliability_tier <> 'UNKNOWN' AND baseline_tier <> 'UNKNOWN'""")[0],
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
    for table in KEYS:
        con.execute(f"COPY {table} TO '{OUT / table}.parquet' (FORMAT PARQUET)")
    con.execute(f"COPY county_grid_reliability TO '{OUT / 'county_grid_reliability.csv'}' (HEADER)")
    (OUT / "summary.json").write_text(json.dumps(summary, indent=2, default=str) + "\n")
    print(json.dumps({k: summary[k] for k in ("tiers", "tier_status", "sensitivity", "eia", "baseline_tiers",
                                              "baseline_agreement")}, indent=2, default=str))


if __name__ == "__main__":
    main()
