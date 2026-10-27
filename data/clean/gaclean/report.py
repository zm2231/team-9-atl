from pathlib import Path

from .build import BQ_COLUMNS, OUT, SHELTER_FEED_FIELDS, TABLES

ROOT = Path(__file__).resolve().parents[1]
PROJECT = "qwiklabs-gcp-04-edc952746633"
DATASET = "evacuation_readiness"


def _q(con, sql: str):
    return con.execute(sql).fetchall()[0]


def _fmt(v) -> str:
    if isinstance(v, float):
        return f"{v:,.4g}" if abs(v) < 10 else f"{v:,.0f}"
    if isinstance(v, int):
        return f"{v:,}"
    return str(v)


def checks(con) -> dict[str, list[tuple]]:
    h = _q(con, """SELECT COUNT(*) FILTER (WHERE cfld_expp_clean_status = 'imputed'), MIN(HRCN_EALP), MAX(HRCN_EALP),
                          COUNT(*), (SELECT geo_id FROM hazard_tracts ORDER BY HRCN_EALP DESC, geo_id LIMIT 1)
                   FROM hazard_tracts""")
    p = _q(con, """SELECT COUNT(*), SUM(power_dependent_dme), SUM(power_dependent_live),
                          COUNT(*) FILTER (WHERE power_dependent_live <> power_dependent_dme),
                          SUM(facility_esrd_dialysis_any_dme), SUM(dialysis_live),
                          COUNT(*) FILTER (WHERE dialysis_centers > 0), SUM(dialysis_stations)
                   FROM power_dependent_counties""")
    supp = con.execute("""
        SELECT f, n FROM (UNPIVOT (SELECT
            COUNT(*) FILTER (WHERE dialysis_live_status = 'imputed') AS dialysis,
            COUNT(*) FILTER (WHERE oxygen_live_status = 'imputed') AS oxygen,
            COUNT(*) FILTER (WHERE home_health_live_status = 'imputed') AS home_health,
            COUNT(*) FILTER (WHERE hospice_live_status = 'imputed') AS hospice,
            COUNT(*) FILTER (WHERE any_service_live_status = 'imputed') AS any_service,
            COUNT(*) FILTER (WHERE power_dependent_live_status = 'imputed') AS power_dependent
            FROM power_dependent_counties) ON COLUMNS(*) INTO NAME f VALUE n) WHERE n > 0 ORDER BY f""").fetchall()
    c = _q(con, """SELECT COUNT(*),
                          COUNT(*) FILTER (WHERE provider_name IS DISTINCT FROM provider_name_clean
                                              OR provider_address IS DISTINCT FROM provider_address_clean
                                              OR citytown IS DISTINCT FROM citytown_clean),
                          COUNT(*) FILTER (WHERE avg_residents_per_day IS NULL),
                          SUM(avg_residents_per_day) / SUM(cms_certified_beds) FILTER (WHERE avg_residents_per_day IS NOT NULL),
                          COUNT(*) FILTER (WHERE number_of_certified_beds IS DISTINCT FROM cms_certified_beds),
                          median(km_nearest_medical_shelter), max(km_nearest_medical_shelter)
                   FROM care_facilities""")
    disagree = _q(con, """SELECT COUNT(*) FROM care_facilities f JOIN raw_power p ON p.fips_code = f.county_fips
                          WHERE lower(replace(f.cms_county_text, ' ', '')) <> lower(replace(p.name, ' ', ''))""")[0]
    dropped = sorted({c for (c,) in con.execute("SELECT column_name FROM (DESCRIBE raw_power)").fetchall()}
                     - set(BQ_COLUMNS["power_dependent_counties"]))
    d = {k: n for k, n in con.execute("SELECT coordinates_confidence, COUNT(*) FROM dialysis_centers GROUP BY 1 ORDER BY 1").fetchall()}
    o = con.execute("SELECT place_group, COUNT(*), string_agg(DISTINCT source_license, ', ' ORDER BY source_license) "
                    "FROM overture_places GROUP BY 1 ORDER BY 1").fetchall()
    z = _q(con, """SELECT (SELECT COUNT(*) FROM hazard_tracts WHERE evac_zone IS NOT NULL),
                          (SELECT COUNT(*) FROM care_facilities WHERE evac_zone IS NOT NULL),
                          (SELECT COUNT(*) FROM assisted_living WHERE evac_zone IS NOT NULL),
                          (SELECT COUNT(*) FROM raw_zones)""")
    a = _q(con, """SELECT COUNT(*), COUNT(*) FILTER (WHERE facility_identity_status = 'aggregated_small_home'),
                          SUM(licensed_beds), median(km_nearest_medical_shelter)
                   FROM assisted_living""")
    a_disagree = _q(con, """SELECT COUNT(*) FROM assisted_living a JOIN raw_power p ON p.fips_code = a.county_fips
                            WHERE lower(replace(a.COUNTY, ' ', '')) <> lower(replace(p.name, ' ', ''))""")[0]
    cf = _q(con, "SELECT COUNT(*), COUNT(*) FILTER (WHERE evac_zone IS NOT NULL) FROM contraflow_intersections")
    se = {k: n for k, n in con.execute("SELECT storm_match_status, COUNT(*) FROM storm_events GROUP BY 1 ORDER BY 1").fetchall()}
    sh = _q(con, "SELECT COUNT(*) FROM storm_history")[0]
    dropped_feed = [n for (n,) in con.execute("SELECT name FROM raw_shelter_feed_fields ORDER BY name").fetchall()
                    if n not in SHELTER_FEED_FIELDS]
    return {
        "hazard_tracts": [
            ("source columns", h[3], "11 NRI columns as published", "unchanged, in the BigQuery `hazard_tracts_clean` order"),
            ("cfld_null_outside_layer", h[0], "`CFLD_EXPP` NULL", "`cfld_expp_clean` = 0, `cfld_expp_clean_status` = imputed"),
            ("hrcn_ealp_percentile", h[3], f"`HRCN_EALP` {h[1]:.3g} to {h[2]:.3g}",
             f"`hrcn_ealp_pctile` 0 to 1 (top: {h[4]})"),
            ("fips_from_geo_id", h[3], "no county column", "`county_fips` = left(geo_id, 5)"),
            ("gema_zone", z[0], f"no evacuation zone ({z[3]} GEMA zone polygons)",
             "`evac_zone`, `evac_zone_county` from the tract centroid; null elsewhere"),
        ],
        "power_dependent_counties": [
            ("columns dropped to match BigQuery clean schema", p[0], ", ".join(f"`{x}`" for x in dropped), "not carried"),
            ("empower_live_canonical", p[0], f"snapshot `power_dependent_dme` total {_fmt(p[1])}",
             f"`power_dependent_live` total {_fmt(p[2])}; {p[3]} counties differ"),
            ("empower_snapshot_unverified", p[0], f"`facility_esrd_dialysis_any_dme` total {_fmt(p[4])}",
             f"kept, status suspect; `dialysis_live` total {_fmt(p[5])} is canonical"),
            ("empower_suppressed_1_11", sum(n for _, n in supp), "value 11",
             "`<field>_live_low` = 1, status imputed (" + ", ".join(f"{f} {n}" for f, n in supp) + ")"),
            ("cms_dialysis_stations", p[6], "no station counts",
             f"`dialysis_centers`, `dialysis_stations` (total {_fmt(p[7])}) from CMS by ZIP county"),
        ],
        "care_facilities": [
            ("source columns", c[0], "10 snapshot columns", "unchanged, in the BigQuery `care_facilities_clean` order"),
            ("cms_join_ccn", c[0], "snapshot only", "CMS beds, residents/day, provider type, sprinklers joined (356/356)"),
            ("nullif_trim", c[1], "name/address/city with stray whitespace", "`*_clean` columns trimmed, blanks null"),
            ("cms_occupancy", c[0] - c[2], "no occupancy",
             f"`occupancy_rate` (statewide {100 * c[3]:.1f}%); {c[2]} homes unrecorded"),
            ("certified beds", c[4], "snapshot `number_of_certified_beds`", "differs from CMS `cms_certified_beds`"),
            ("nearest_tract_centroid", c[0], "no tract or county FIPS",
             f"`nearest_tract_geo_id`, `county_fips` (imputed); {disagree} disagree with CMS county text"),
            ("medical_shelter_distance_pending", c[0], "none",
             f"`km_nearest_medical_shelter` median {c[5]:.1f}, max {c[6]:.1f} (pending teammate shelters_clean)"),
            ("gema_zone", z[1], "no evacuation zone", "`evac_zone`, `evac_zone_county` from the facility point"),
        ],
        "assisted_living (GaMap2Care)": [
            ("gamap2care_facility", a[0], "GaMap2Care facility fields", f"one row per FACID; {_fmt(a[2])} licensed beds"),
            ("small_home_aggregated", a[1], "name, street address and point of homes with 6 or fewer beds",
             "`NAME`, `ADDRESS` null; `Latitude`/`Longitude` = tract centroid; status aggregated_small_home"),
            ("nearest_tract_centroid", a[0], "GaMap2Care `COUNTY` text",
             f"`county_fips` (imputed); {a_disagree} disagree with the county text, both kept"),
            ("gema_zone", z[2], "no evacuation zone", "`evac_zone`, `evac_zone_county`"),
            ("medical_shelter_distance_pending", a[0], "none",
             f"`km_nearest_medical_shelter` median {a[3]:.1f} (pending teammate shelters_clean)"),
        ],
        "contraflow_intersections (GEMA)": [
            ("gema_contraflow_point", cf[0], "GEMA I-16 contraflow points", f"`county_fips` imputed; {cf[1]} in a GEMA zone"),
        ],
        "gema_shelter_feed (input for the teammate shelters table)": [
            ("webeoc_facility_fields", 0, f"{len(SHELTER_FEED_FIELDS) + len(dropped_feed)} schema fields",
             f"{len(SHELTER_FEED_FIELDS)} facility/status fields kept; never read: "
             + ", ".join(f"`{n}`" for n in dropped_feed)),
        ],
        "storm_events / storm_history (NCEI)": [
            ("ncei_storm_match_narrative", se.get("external", 0), "HURDAT2 match by narrative name", "status external"),
            ("ncei_storm_match_nearest", se.get("imputed", 0), "nearest active HURDAT2 storm", "status imputed"),
            ("ncei_storm_unmatched", se.get("unrecorded", 0), "no storm", "status unrecorded"),
            ("ncei_storm_aggregate", sh, "events", "one row per storm and state"),
        ],
        "dialysis_centers (gap fill)": [
            ("zip_to_county_empower", sum(d.values()), "CMS county text", "`county_fips` from ZIP"),
            ("census_geocoder", sum(v for k, v in d.items() if k != "unmatched"), "no coordinates",
             ", ".join(f"{k} {v}" for k, v in d.items())),
        ],
        "overture_places (held: built to out/held/, not committed or posted)": [
            ("overture_places", n, f"Overture `{g}`", f"status external, licences: {lic}") for g, n, lic in o
        ],
    }


def write_cleaning(con, root: Path = ROOT) -> None:
    lines = ["# Cleaning log", "",
             "Generated by `python -m gaclean.build`. One row per rule: rows affected, value before, value after. Rule",
             "texts are in `out/rules.json`. Every output keeps one row per source row, and every source column keeps",
             "its published value; cleaned values go in appended columns with `_status` and `_rule`.", ""]
    for table, rows in checks(con).items():
        lines += [f"## {table}", "", "| Rule | Rows | Before | After |", "|---|---:|---|---|"]
        lines += [f"| `{r}` | {_fmt(n)} | {b} | {a} |" for r, n, b, a in rows]
        lines.append("")
    (root / "CLEANING.md").write_text("\n".join(lines))


def write_post(con, root: Path = ROOT) -> None:
    lines = ["# Posting to BigQuery (do not run until Zain says post)", "",
             "Generated by `python -m gaclean.build`. Each table loads into a staging table first; replacing the",
             "team's `_clean` table is a separate, deliberate step. The leading columns match the existing",
             "`evacuation_readiness.<table>_clean` schemas (read with `bq show --schema`), and the clean-layer",
             "columns follow.", "", "```bash", "source ~/work/google-hackathon/hackathon-env.sh"]
    staged = [n for n in TABLES if n != "gema_shelter_feed"]
    for name in staged:
        lines.append(f"bq load --source_format=PARQUET --replace {PROJECT}:{DATASET}.{name}_flow_staging "
                     f"data/clean/out/{name}.parquet")
    lines += ["```", "", "Check the leading columns before replacing:", "", "```sql"]
    for name, cols in BQ_COLUMNS.items():
        lines.append(f"SELECT COUNT(*) FROM `{PROJECT}.{DATASET}.{name}_clean` a FULL JOIN "
                     f"`{PROJECT}.{DATASET}.{name}_flow_staging` b USING ({cols[0] if name != 'power_dependent_counties' else 'fips_code'}) "
                     f"WHERE a.{cols[0]} IS NULL OR b.{cols[0]} IS NULL;  -- expect 0")
    lines += ["```", "", "Replace (destructive; only on go):", "", "```sql"]
    for name in BQ_COLUMNS:
        lines.append(f"CREATE OR REPLACE TABLE `{PROJECT}.{DATASET}.{name}_clean` AS "
                     f"SELECT * FROM `{PROJECT}.{DATASET}.{name}_flow_staging`;")
    lines += ["```", "", "The other tables (" + ", ".join(f"`{n}`" for n in staged if n not in BQ_COLUMNS)
              + ") are new and stay as `<name>_flow_staging` until the team names them.",
              "`gema_shelter_feed` is an input for the teammate shelters table and is not loaded here.",
              "`overture_places` is held pending the licence ruling and is not loaded.", "",
              "Column counts:", ""]
    for name in TABLES:
        n = len(con.execute(f"DESCRIBE {name}").fetchall())
        lines.append(f"- `{name}`: {n} columns ({len(BQ_COLUMNS.get(name, []))} leading BigQuery columns)")
    (root / "POST.md").write_text("\n".join(lines) + "\n")
    assert OUT.exists()
