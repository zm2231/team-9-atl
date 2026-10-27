import json
from pathlib import Path

import duckdb

from . import rules as R
from .sources import Sources

OUT = Path(__file__).resolve().parents[1] / "out"

# Leading columns, names and order, of the team's BigQuery evacuation_readiness.*_clean tables
# (bq show --schema, 2026-10-27). Clean-layer columns are appended after them.
BQ_COLUMNS = {
    "care_facilities": ["cms_certification_number_ccn", "provider_name", "provider_address", "citytown", "state",
                        "zip_code", "number_of_certified_beds", "ownership_type", "latitude", "longitude"],
    "hazard_tracts": ["geo_id", "POPULATION", "BUILDVALUE", "HRCN_AFREQ", "HRCN_EXPP", "HRCN_EALT", "HRCN_EALP",
                      "CFLD_AFREQ", "CFLD_EXPP", "CFLD_EALT", "CFLD_EALP"],
    "power_dependent_counties": ["objectid", "name", "namelsad", "fips_code_recode", "state", "fips_code",
                                 "county_fips_code", "county", "state_fips_code", "medicare_benes",
                                 "power_dependent_devices_dme", "facility_esrd_dialysis_any_dme",
                                 "o2_services_any_dme", "home_health_services_any_dme", "athome_hospice_any_dme",
                                 "any_healthcare_srvc_any_dme", "shape__area", "shape__length",
                                 "power_dependent_is_censored", "power_dependent_dme"],
}
EMPOWER_FIELDS = {
    "medicare_benes": "Medicare_Benes", "power_dependent": "Power_Dependent_Devices_DME",
    "dialysis": "Facility_ESRD_Dialysis_Any_DME", "oxygen": "O2_Services_Any_DME",
    "home_health": "Home_Health_Services_Any_DME", "hospice": "AtHome_Hospice_Any_DME",
    "any_service": "Any_Healthcare_Srvc_Any_DME",
}
OVERTURE_GROUPS = {
    "assisted_living_facility": "assisted_living", "retirement_home": "retirement_home",
    "ambulance_or_ems_service": "ambulance_ems", "medical_transportation": "medical_transport",
    "home_health_care": "home_health", "hospice": "hospice",
}


SOURCE_COLUMNS = {
    **BQ_COLUMNS,
    "dialysis_centers": ["ccn", "facility_name", "address", "city", "zip", "cms_county_text", "stations", "late_shift",
                         "offers_in_center_hemodialysis", "offers_peritoneal", "offers_home_hemodialysis_training",
                         "profit_status", "chain"],
    "overture_places": ["id", "name", "category", "confidence", "address", "locality", "postcode", "lon", "lat",
                        "source_dataset", "source_license", "operating_status"],
}
SHELTER_FEED_FIELDS = [
    "dataid", "GlobalID", "label", "incidentid", "county", "gema_area", "address", "shelter_type", "status",
    "capacity", "post_impact_capacity", "occupancy", "shelter_open_datetime", "shelter_opening_qualifier",
    "shelter_closing_datetime", "shelter_closing_qualifier",
]
SOURCE_COLUMNS["gema_shelter_feed"] = SHELTER_FEED_FIELDS
RAW_SOURCE = {"assisted_living": "raw_gamap2care", "contraflow_intersections": "raw_contraflow",
              "storm_events": "raw_ncei"}
STORM_AGGREGATES = ["storm_name", "year", "events", "tropical_type_events", "counties", "deaths_direct",
                    "deaths_indirect", "injuries_direct", "damage_property_usd", "damage_crops_usd", "first_event",
                    "last_event"]
SOURCE_COLUMNS["storm_history"] = ["storm_atcf_id", "state"]
PROVENANCE_GROUPS = {"latitude": "coordinates", "longitude": "coordinates", "coordinates_confidence": "coordinates",
                     **{f"{name}_live_low": f"{name}_live" for name in EMPOWER_FIELDS},
                     **{c: "aggregate" for c in STORM_AGGREGATES}}


def source_columns(con, table: str) -> list[str]:
    if table in RAW_SOURCE:
        return [r[0] for r in con.execute(f"DESCRIBE {RAW_SOURCE[table]}").fetchall()]
    return SOURCE_COLUMNS[table]


def unprovenanced(con, table: str) -> list[str]:
    cols = [r[0] for r in con.execute(f"DESCRIBE {table}").fetchall()]
    have = set(cols)
    source = source_columns(con, table)
    return [c for c in cols
            if c not in source and not c.endswith(("_status", "_rule"))
            and not {f"{PROVENANCE_GROUPS.get(c, c)}_status", f"{PROVENANCE_GROUPS.get(c, c)}_rule"} <= have]


def lead(table: str, alias: str) -> str:
    return ", ".join(f'{alias}."{c}"' for c in BQ_COLUMNS[table])


def count(con, sql: str) -> int:
    return con.execute(f"SELECT COUNT(*) FROM ({sql})").fetchall()[0][0]


def expect(con, table: str, n: int) -> None:
    got = count(con, f"SELECT * FROM {table}")
    assert got == n, f"{table}: expected {n} rows, got {got}"
    print(f"  {table}: {got} rows")


def unmatched(con, label: str, sql: str) -> int:
    rows = con.execute(sql).fetchall()
    print(f"  unmatched {label}: {len(rows)}" + (f" e.g. {rows[:3]}" if rows else ""))
    return len(rows)


def connect() -> duckdb.DuckDBPyConnection:
    con = duckdb.connect()
    con.execute("INSTALL spatial; LOAD spatial; SET geometry_always_xy = true;")
    return con


def register(con, src: Sources) -> None:
    src.check()
    for name, table in (("raw_shelters", "shelters"), ("raw_tracts", "vulnerability_tracts"),
                        ("raw_hazard", "hazard_tracts"), ("raw_care", "care_facilities"),
                        ("raw_power", "power_dependent_counties")):
        con.execute(f"CREATE VIEW {name} AS SELECT * FROM read_parquet('{src.snapshot / table / 'data.parquet'}')")
    con.execute(f"""CREATE VIEW raw_empower_live AS SELECT * FROM read_csv('{src.empower_live_county}',
                    types={{'FIPS_Code': 'VARCHAR'}})""")
    con.execute(f"""CREATE VIEW raw_empower_zip AS SELECT * FROM read_csv('{src.empower_live_zip}',
                    types={{'Zip_Code': 'VARCHAR', 'FIPS_Code': 'VARCHAR'}})""")
    con.execute(f"CREATE VIEW raw_cms_nh AS SELECT * FROM read_parquet('{src.cms / 'nursing_homes_ga.parquet'}')")
    con.execute(f"CREATE VIEW raw_cms_dialysis AS SELECT * FROM read_parquet('{src.cms / 'dialysis_facilities_ga.parquet'}')")
    con.execute(f"CREATE VIEW raw_dialysis_geo AS SELECT * FROM read_csv('{src.dialysis_geocoded}', types={{'ccn': 'VARCHAR'}})")
    con.execute(f"CREATE VIEW raw_overture AS SELECT * FROM read_parquet('{src.overture_places}')")
    con.execute(f"""CREATE TABLE raw_zones AS SELECT County, Zone, geom
                    FROM ST_Read('{src.gema / 'evacuation_zones.geojson'}')""")
    con.execute(f"""CREATE TABLE raw_contraflow AS SELECT * EXCLUDE (geom), ST_X(geom) AS lon, ST_Y(geom) AS lat
                    FROM ST_Read('{src.gema / 'contraflow_intersections.geojson'}')""")
    con.execute(f"CREATE VIEW raw_gamap2care AS SELECT * FROM read_parquet('{src.gamap2care}')")
    con.execute(f"CREATE VIEW raw_ncei AS SELECT * FROM read_parquet('{src.ncei_storm_events}')")
    con.execute(f"""CREATE TABLE raw_shelter_feed_fields AS
                    SELECT f.name, f.type FROM (SELECT UNNEST(fields) AS f
                    FROM read_json('{src.gema / 'shelters_v2_schema.json'}'))""")


def zone_join(points: str, key: str, lon: str, lat: str) -> str:
    return f"""(SELECT p.{key}, z.County AS evac_zone_county, z.Zone AS evac_zone
                FROM {points} p JOIN raw_zones z ON ST_Contains(z.geom, ST_Point(p.{lon}, p.{lat}))
                QUALIFY ROW_NUMBER() OVER (PARTITION BY p.{key} ORDER BY z.Zone, z.County) = 1)"""


def zone_columns(alias: str, has_point: str) -> str:
    status = f"CASE WHEN {has_point} THEN 'external' ELSE 'unrecorded' END"
    return (f"{R.tag(f'{alias}.evac_zone', 'evac_zone', status, 'gema_zone')}, "
            f"{R.tag(f'{alias}.evac_zone_county', 'evac_zone_county', status, 'gema_zone')}")


def build_hazard_tracts(con) -> None:
    cfld = "CASE WHEN h.CFLD_EXPP IS NULL THEN 'imputed' ELSE 'recorded' END"
    con.execute(f"""
        CREATE TABLE hazard_tracts AS
        SELECT {lead('hazard_tracts', 'h')},
               {R.tag("left(h.geo_id, 5)", "county_fips", "'recorded'", "fips_from_geo_id")},
               {R.tag("PERCENT_RANK() OVER (ORDER BY h.HRCN_EALP)", "hrcn_ealp_pctile",
                      R.recorded_or_unrecorded("h.HRCN_EALP"), "hrcn_ealp_percentile")},
               COALESCE(h.CFLD_EXPP, 0) AS cfld_expp_clean, {cfld} AS cfld_expp_clean_status,
               CASE WHEN h.CFLD_EXPP IS NULL THEN 'cfld_null_outside_layer' ELSE 'source_value' END
                   AS cfld_expp_clean_rule,
               {R.tag("CASE WHEN h.POPULATION > 0 THEN LEAST(COALESCE(h.CFLD_EXPP, 0) / h.POPULATION, 1.0) END",
                      "cfld_share", f"CASE WHEN h.POPULATION > 0 THEN {cfld} ELSE 'unrecorded' END", "cfld_share")},
               {R.tag("COALESCE(h.CFLD_EXPP, 0) > 0", "coastal_flood_exposed", cfld, "coastal_flood_exposed")},
               {R.tag("t.geo_id IS NOT NULL", "has_vulnerability_tract", "'recorded'", "vulnerability_tract_join")},
               {zone_columns("zt", "t.geo_id IS NOT NULL")}
        FROM raw_hazard h LEFT JOIN (SELECT geo_id FROM raw_tracts) t USING (geo_id)
        LEFT JOIN {zone_join("raw_tracts", "geo_id", "lon", "lat")} zt USING (geo_id)
        ORDER BY h.geo_id
    """)
    expect(con, "hazard_tracts", count(con, "SELECT * FROM raw_hazard"))
    unmatched(con, "hazard rows without a vulnerability tract",
              "SELECT geo_id FROM hazard_tracts WHERE NOT has_vulnerability_tract")
    missing = con.execute("""SELECT COUNT(*), COALESCE(SUM(total_pop), 0)
                             FROM raw_tracts ANTI JOIN raw_hazard USING (geo_id)""").fetchall()[0]
    assert missing[1] == 0, f"{missing[0]} tracts without a hazard row hold {missing[1]} people"
    unmatched(con, "vulnerability tracts without a hazard row (pop 0)",
              "SELECT geo_id FROM raw_tracts ANTI JOIN raw_hazard USING (geo_id)")


def build_power_dependent_counties(con) -> None:
    live = []
    for name, col in EMPOWER_FIELDS.items():
        v, lo, st = R.empower_value(f"l.{col}")
        live.append(f"{v} AS {name}_live, {lo} AS {name}_live_low, {st} AS {name}_live_status, "
                    f"CASE WHEN l.{col} = 11 THEN 'empower_suppressed_1_11' ELSE 'empower_live_canonical' END "
                    f"AS {name}_live_rule")
    listed = "CASE WHEN d.fips_code IS NULL THEN 'imputed' ELSE 'recorded' END"
    dialysis_status = R.empower_value("l.Facility_ESRD_Dialysis_Any_DME")[2]
    con.execute(f"""
        CREATE TABLE power_dependent_counties AS
        WITH d AS (
            SELECT z.FIPS_Code AS fips_code, COUNT(*) AS dialysis_centers,
                   SUM(TRY_CAST(c."# of Dialysis Stations" AS INTEGER)) AS dialysis_stations
            FROM raw_cms_dialysis c JOIN raw_empower_zip z ON z.Zip_Code = left(c."ZIP Code", 5)
            GROUP BY 1
        )
        SELECT {lead('power_dependent_counties', 'p')},
               'recorded' AS power_dependent_dme_status, 'source_value' AS power_dependent_dme_rule,
               'suspect' AS facility_esrd_dialysis_any_dme_status,
               'empower_snapshot_unverified' AS facility_esrd_dialysis_any_dme_rule,
               {', '.join(live)},
               {R.tag("COALESCE(d.dialysis_centers, 0)", "dialysis_centers", listed, "cms_dialysis_stations")},
               {R.tag("COALESCE(d.dialysis_stations, 0)", "dialysis_stations", listed, "cms_dialysis_stations")},
               {R.tag("l.Facility_ESRD_Dialysis_Any_DME / NULLIF(d.dialysis_stations, 0)",
                      "dialysis_patients_per_station",
                      f"CASE WHEN COALESCE(d.dialysis_stations, 0) = 0 THEN 'unrecorded' ELSE {dialysis_status} END",
                      "dialysis_patients_per_station")}
        FROM raw_power p
        JOIN raw_empower_live l ON l.FIPS_Code = p.fips_code
        LEFT JOIN d ON d.fips_code = p.fips_code
        ORDER BY p.fips_code
    """)
    expect(con, "power_dependent_counties", count(con, "SELECT * FROM raw_power"))
    unmatched(con, "live emPOWER counties not in snapshot",
              "SELECT l.FIPS_Code FROM raw_empower_live l ANTI JOIN raw_power p ON p.fips_code = l.FIPS_Code")
    unmatched(con, "CMS dialysis ZIPs without an emPOWER county",
              """SELECT "ZIP Code" FROM raw_cms_dialysis c
                 ANTI JOIN raw_empower_zip z ON z.Zip_Code = left(c."ZIP Code", 5)""")


def nearest_tract(con, table: str, key: str, lon: str, lat: str) -> None:
    con.execute(f"""
        CREATE TABLE {table}_nearest AS
        SELECT x.{key}, t.geo_id AS nearest_tract_geo_id, t.county_fips AS nearest_tract_county_fips,
               ST_Distance({R.point('x.' + lon, 'x.' + lat)}, {R.point('t.lon', 't.lat')}) / 1000 AS km_to_tract_centroid
        FROM {table}_pre x CROSS JOIN raw_tracts t
        WHERE x.{lat} IS NOT NULL
        QUALIFY ROW_NUMBER() OVER (PARTITION BY x.{key}
                ORDER BY ST_Distance({R.point('x.' + lon, 'x.' + lat)}, {R.point('t.lon', 't.lat')}), t.geo_id) = 1
    """)


def build_care_facilities(con) -> None:
    cms = (("cms_county_text", R.trim('n."County/Parish"')),
           ("cms_certified_beds", 'TRY_CAST(n."Number of Certified Beds" AS DOUBLE)'),
           ("avg_residents_per_day", 'TRY_CAST(n."Average Number of Residents per Day" AS DOUBLE)'),
           ("cms_provider_type", R.trim('n."Provider Type"')),
           ("cms_sprinklers_all_required_areas", R.trim('n."Automatic Sprinkler Systems in All Required Areas"')))
    cms_d = dict(cms)
    con.execute(f"""
        CREATE TABLE care_facilities_pre AS
        SELECT {lead('care_facilities', 'c')},
               {', '.join(R.tag(R.trim(f'c.{c}'), f'{c}_clean', R.recorded_or_unrecorded(R.trim(f'c.{c}')),
                                'nullif_trim') for c in ('provider_name', 'provider_address', 'citytown'))},
               {', '.join(R.tag(expr, name, R.recorded_or_unrecorded(expr), 'cms_join_ccn') for name, expr in cms)},
               {R.tag(f"{cms_d['avg_residents_per_day']} / NULLIF({cms_d['cms_certified_beds']}, 0)", "occupancy_rate",
                      R.recorded_or_unrecorded(f"{cms_d['avg_residents_per_day']} / NULLIF({cms_d['cms_certified_beds']}, 0)"),
                      "cms_occupancy")}
        FROM raw_care c JOIN raw_cms_nh n ON n."CMS Certification Number (CCN)" = c.cms_certification_number_ccn
    """)
    expect(con, "care_facilities_pre", count(con, "SELECT * FROM raw_care"))
    unmatched(con, "CMS nursing homes not in snapshot",
              """SELECT "CMS Certification Number (CCN)" FROM raw_cms_nh
                 ANTI JOIN raw_care ON cms_certification_number_ccn = "CMS Certification Number (CCN)\"""")
    nearest_tract(con, "care_facilities", "cms_certification_number_ccn", "longitude", "latitude")
    con.execute(f"""
        CREATE TABLE care_facilities AS
        WITH med AS (SELECT {R.point('longitude', 'latitude')} AS g FROM raw_shelters WHERE is_medical)
        SELECT p.*,
               {R.tag("n.nearest_tract_geo_id", "nearest_tract_geo_id", "'imputed'", "nearest_tract_centroid")},
               {R.tag("n.km_to_tract_centroid", "km_to_tract_centroid", "'imputed'", "nearest_tract_centroid")},
               {R.tag("n.nearest_tract_county_fips", "county_fips", "'imputed'", "nearest_tract_centroid")},
               {', '.join(R.tag(f"h.{src}", name, "CASE WHEN h.geo_id IS NULL THEN 'unrecorded' ELSE 'imputed' END",
                                "tract_hazard_join")
                          for name, src in (("hrcn_ealp_pctile", "hrcn_ealp_pctile"), ("hrcn_afreq", "HRCN_AFREQ"),
                                            ("cfld_share", "cfld_share"),
                                            ("coastal_flood_exposed", "coastal_flood_exposed")))},
               {R.tag(f"(SELECT MIN(ST_Distance({R.point('p.longitude', 'p.latitude')}, med.g)) / 1000 FROM med)",
                      "km_nearest_medical_shelter", "'assumption'", "medical_shelter_distance_pending")},
               {zone_columns("z", "p.latitude IS NOT NULL")}
        FROM care_facilities_pre p JOIN care_facilities_nearest n USING (cms_certification_number_ccn)
        LEFT JOIN hazard_tracts h ON h.geo_id = n.nearest_tract_geo_id
        LEFT JOIN {zone_join("care_facilities_pre", "cms_certification_number_ccn", "longitude", "latitude")} z
            USING (cms_certification_number_ccn)
        ORDER BY p.cms_certification_number_ccn
    """)
    expect(con, "care_facilities", count(con, "SELECT * FROM raw_care"))
    unmatched(con, "care facilities whose tract has no hazard row",
              "SELECT cms_certification_number_ccn FROM care_facilities WHERE hrcn_ealp_pctile IS NULL")


def build_dialysis_centers(con) -> None:
    con.execute(f"""
        CREATE TABLE dialysis_centers AS
        SELECT d."CMS Certification Number (CCN)" AS ccn,
               {R.trim('d."Facility Name"')} AS facility_name, {R.trim('d."Address Line 1"')} AS address,
               {R.trim('d."City/Town"')} AS city, left(d."ZIP Code", 5) AS zip,
               {R.trim('d."County/Parish"')} AS cms_county_text,
               {R.tag("z.FIPS_Code", "county_fips", "'imputed'", "zip_to_county_empower")},
               TRY_CAST(d."# of Dialysis Stations" AS INTEGER) AS stations,
               {R.trim('d."Late Shift"')} AS late_shift,
               {R.trim('d."Offers in-center hemodialysis"')} AS offers_in_center_hemodialysis,
               {R.trim('d."Offers peritoneal dialysis"')} AS offers_peritoneal,
               {R.trim('d."Offers home hemodialysis training"')} AS offers_home_hemodialysis_training,
               {R.trim('d."Profit or Non-Profit"')} AS profit_status, {R.trim('d."Chain Organization"')} AS chain,
               CASE WHEN g.location_status LIKE 'geocoded%' THEN g.lat END AS latitude,
               CASE WHEN g.location_status LIKE 'geocoded%' THEN g.lon END AS longitude,
               CASE WHEN g.location_status LIKE 'geocoded%' THEN 'external' ELSE 'unrecorded' END AS coordinates_status,
               CASE WHEN g.location_status LIKE 'geocoded%' THEN 'census_geocoder' ELSE 'coordinates_absent' END
                   AS coordinates_rule,
               g.location_status AS coordinates_confidence
        FROM raw_cms_dialysis d JOIN raw_empower_zip z ON z.Zip_Code = left(d."ZIP Code", 5)
        LEFT JOIN raw_dialysis_geo g ON g.ccn = d."CMS Certification Number (CCN)"
        ORDER BY ccn
    """)
    expect(con, "dialysis_centers", count(con, "SELECT * FROM raw_cms_dialysis"))
    unmatched(con, "dialysis centers missing from geocoder output",
              "SELECT ccn FROM dialysis_centers WHERE coordinates_confidence IS NULL")


def build_overture_places(con) -> None:
    groups = " ".join(f"WHEN '{k}' THEN '{v}'" for k, v in OVERTURE_GROUPS.items())
    con.execute(f"""
        CREATE TABLE overture_places_pre AS
        SELECT *, {R.tag(f"CASE category {groups} END", "place_group", "'external'", "overture_places")}
        FROM raw_overture WHERE category IN ({', '.join(f"'{k}'" for k in OVERTURE_GROUPS)})
    """)
    nearest_tract(con, "overture_places", "id", "lon", "lat")
    con.execute(f"""
        CREATE TABLE overture_places AS
        SELECT p.*, {R.tag("n.nearest_tract_geo_id", "nearest_tract_geo_id", "'imputed'", "nearest_tract_centroid")},
               {R.tag("n.nearest_tract_county_fips", "county_fips", "'imputed'", "nearest_tract_centroid")}
        FROM overture_places_pre p LEFT JOIN overture_places_nearest n USING (id)
        ORDER BY place_group, id
    """)
    expect(con, "overture_places", count(con, "SELECT * FROM overture_places_pre"))
    unmatched(con, "overture places without coordinates", "SELECT id FROM overture_places WHERE county_fips IS NULL")


def build_assisted_living(con) -> None:
    small = f"g.facility_type = 'PERSONAL CARE HOME' AND g.licensed_beds <= {R.SMALL_HOME_BEDS}"
    con.execute("CREATE TABLE assisted_living_pre AS SELECT * FROM raw_gamap2care")
    nearest_tract(con, "assisted_living", "FACID", "Longitude", "Latitude")
    con.execute(f"""
        CREATE TABLE assisted_living AS
        WITH g AS (
            SELECT g.*, {small} AS is_small_home, n.nearest_tract_geo_id, n.nearest_tract_county_fips,
                   CASE WHEN {small} THEN t.lon ELSE g.Longitude END AS pub_lon,
                   CASE WHEN {small} THEN t.lat ELSE g.Latitude END AS pub_lat
            FROM assisted_living_pre g
            LEFT JOIN assisted_living_nearest n USING (FACID)
            LEFT JOIN raw_tracts t ON t.geo_id = n.nearest_tract_geo_id
        ), med AS (SELECT {R.point('longitude', 'latitude')} AS geom FROM raw_shelters WHERE is_medical)
        SELECT g.* EXCLUDE (NAME, ADDRESS, Latitude, Longitude, is_small_home, nearest_tract_geo_id,
                            nearest_tract_county_fips, pub_lon, pub_lat),
               CASE WHEN is_small_home THEN NULL ELSE g.NAME END AS NAME,
               CASE WHEN is_small_home THEN NULL ELSE g.ADDRESS END AS ADDRESS,
               g.pub_lat AS Latitude, g.pub_lon AS Longitude,
               CASE WHEN is_small_home THEN 'aggregated_small_home' ELSE 'recorded' END AS facility_identity_status,
               CASE WHEN is_small_home THEN 'small_home_aggregated' ELSE 'gamap2care_facility' END AS facility_identity_rule,
               {R.tag("g.nearest_tract_geo_id", "nearest_tract_geo_id", "'imputed'", "nearest_tract_centroid")},
               {R.tag("g.nearest_tract_county_fips", "county_fips", "'imputed'", "nearest_tract_centroid")},
               {', '.join(R.tag(f"h.{src}", name, "CASE WHEN h.geo_id IS NULL THEN 'unrecorded' ELSE 'imputed' END",
                                "tract_hazard_join")
                          for name, src in (("hrcn_ealp_pctile", "hrcn_ealp_pctile"), ("cfld_share", "cfld_share"),
                                            ("coastal_flood_exposed", "coastal_flood_exposed")))},
               {zone_columns("z", "g.Latitude IS NOT NULL")},
               {R.tag(f"(SELECT MIN(ST_Distance({R.point('g.pub_lon', 'g.pub_lat')}, med.geom)) / 1000 FROM med)",
                      "km_nearest_medical_shelter", "'assumption'", "medical_shelter_distance_pending")}
        FROM g
        LEFT JOIN hazard_tracts h ON h.geo_id = g.nearest_tract_geo_id
        LEFT JOIN {zone_join("g", "FACID", "pub_lon", "pub_lat")} z USING (FACID)
        ORDER BY FACID
    """)
    expect(con, "assisted_living", count(con, "SELECT * FROM raw_gamap2care"))
    assert count(con, "SELECT DISTINCT FACID FROM assisted_living") == count(con, "SELECT * FROM assisted_living")
    unmatched(con, "assisted living without a tract", "SELECT FACID FROM assisted_living WHERE county_fips IS NULL")
    unmatched(con, "assisted living whose GaMap2Care county differs from the imputed county",
              """SELECT a.FACID, a.COUNTY, p.name FROM assisted_living a JOIN raw_power p ON p.fips_code = a.county_fips
                 WHERE lower(replace(a.COUNTY, ' ', '')) <> lower(replace(p.name, ' ', ''))""")
    leaked = count(con, """SELECT * FROM assisted_living WHERE facility_identity_status = 'aggregated_small_home'
                           AND (NAME IS NOT NULL OR ADDRESS IS NOT NULL)""")
    assert leaked == 0, f"{leaked} small homes carry a name or address"


def build_contraflow_intersections(con) -> None:
    con.execute("CREATE TABLE contraflow_intersections_pre AS SELECT * FROM raw_contraflow")
    nearest_tract(con, "contraflow_intersections", "OBJECTID", "lon", "lat")
    con.execute(f"""
        CREATE TABLE contraflow_intersections AS
        SELECT c.*, 'external' AS record_status, 'gema_contraflow_point' AS record_rule,
               {R.tag("n.nearest_tract_county_fips", "county_fips", "'imputed'", "nearest_tract_centroid")},
               {zone_columns("z", "c.lat IS NOT NULL")}
        FROM contraflow_intersections_pre c
        LEFT JOIN contraflow_intersections_nearest n USING (OBJECTID)
        LEFT JOIN {zone_join("contraflow_intersections_pre", "OBJECTID", "lon", "lat")} z USING (OBJECTID)
        ORDER BY OBJECTID
    """)
    expect(con, "contraflow_intersections", count(con, "SELECT * FROM raw_contraflow"))


def build_gema_shelter_feed(con) -> None:
    fields = dict(con.execute("SELECT name, type FROM raw_shelter_feed_fields").fetchall())
    missing = [f for f in SHELTER_FEED_FIELDS if f not in fields]
    assert not missing, f"WebEOC schema lacks {missing}"
    sql_type = {"esriFieldTypeInteger": "INTEGER", "esriFieldTypeString": "VARCHAR", "esriFieldTypeGlobalID": "VARCHAR"}
    cols = ", ".join(f"CAST(NULL AS {sql_type[fields[f]]}) AS {f}" for f in SHELTER_FEED_FIELDS)
    con.execute(f"CREATE TABLE gema_shelter_feed AS SELECT {cols} WHERE false")


def build_storm_events(con) -> None:
    con.execute("""
        CREATE TABLE storm_events AS
        SELECT *,
               CASE storm_match_method WHEN 'narrative_name+hurdat2_active' THEN 'external'
                    WHEN 'nearest_active_hurdat2' THEN 'imputed' ELSE 'unrecorded' END AS storm_match_status,
               CASE storm_match_method WHEN 'narrative_name+hurdat2_active' THEN 'ncei_storm_match_narrative'
                    WHEN 'nearest_active_hurdat2' THEN 'ncei_storm_match_nearest' ELSE 'ncei_storm_unmatched' END
                   AS storm_match_rule
        FROM raw_ncei ORDER BY event_id
    """)
    expect(con, "storm_events", count(con, "SELECT * FROM raw_ncei"))
    assert count(con, "SELECT DISTINCT event_id FROM storm_events") == count(con, "SELECT * FROM storm_events")
    con.execute("""
        CREATE TABLE storm_history AS
        SELECT storm_atcf_id, ANY_VALUE(storm_name ORDER BY event_id) AS storm_name, MIN(year) AS year, state,
               COUNT(*) AS events, COUNT(*) FILTER (WHERE is_tropical_type) AS tropical_type_events,
               COUNT(DISTINCT county_fips) AS counties, SUM(deaths_direct) AS deaths_direct,
               SUM(deaths_indirect) AS deaths_indirect, SUM(injuries_direct) AS injuries_direct,
               SUM(damage_property_usd) AS damage_property_usd, SUM(damage_crops_usd) AS damage_crops_usd,
               MIN(begin_local) AS first_event, MAX(end_local) AS last_event,
               'recorded' AS aggregate_status, 'ncei_storm_aggregate' AS aggregate_rule
        FROM storm_events WHERE storm_atcf_id IS NOT NULL
        GROUP BY storm_atcf_id, state ORDER BY year, storm_atcf_id, state
    """)
    assert count(con, "SELECT * FROM storm_events WHERE storm_atcf_id IS NULL") == count(
        con, "SELECT * FROM storm_events WHERE storm_match_status = 'unrecorded'")
    unmatched(con, "storm events without a storm", "SELECT event_id FROM storm_events WHERE storm_atcf_id IS NULL")


TABLES = {
    "care_facilities": "SELECT * FROM care_facilities",
    "hazard_tracts": "SELECT * FROM hazard_tracts",
    "power_dependent_counties": "SELECT * FROM power_dependent_counties",
    "dialysis_centers": "SELECT * FROM dialysis_centers",
    "assisted_living": "SELECT * FROM assisted_living",
    "contraflow_intersections": "SELECT * FROM contraflow_intersections",
    "gema_shelter_feed": "SELECT * FROM gema_shelter_feed",
    "storm_events": "SELECT * FROM storm_events",
    "storm_history": "SELECT * FROM storm_history",
}
HELD = {"overture_places": "SELECT * FROM overture_places"}


def build_all(con) -> None:
    for step in (build_hazard_tracts, build_power_dependent_counties, build_care_facilities, build_dialysis_centers,
                 build_overture_places, build_assisted_living, build_contraflow_intersections, build_gema_shelter_feed,
                 build_storm_events):
        print(step.__name__)
        step(con)
    for table in (*TABLES, *HELD):
        missing = unprovenanced(con, table)
        assert not missing, f"{table}: columns without _status and _rule: {missing}"


def numbers(con) -> dict:
    def q(sql: str):
        return con.execute(sql).fetchall()[0]

    p = q("""SELECT SUM(power_dependent_live), SUM(power_dependent_dme), SUM(dialysis_live),
                    SUM(facility_esrd_dialysis_any_dme), SUM(dialysis_stations), SUM(dialysis_centers)
             FROM power_dependent_counties""")
    suppressed = {name: q(f"SELECT COUNT(*) FROM power_dependent_counties WHERE {name}_live_status = 'imputed'")[0]
                  for name in EMPOWER_FIELDS}
    h = q("""SELECT COUNT(*) FILTER (WHERE cfld_expp_clean_status = 'imputed'), COUNT(*) FILTER (WHERE coastal_flood_exposed),
                    SUM(POPULATION), COUNT(*) FILTER (WHERE NOT has_vulnerability_tract)
             FROM hazard_tracts""")
    missing = q("SELECT COUNT(*), COALESCE(SUM(total_pop), 0) FROM raw_tracts ANTI JOIN raw_hazard USING (geo_id)")
    c = q("""SELECT SUM(number_of_certified_beds), SUM(cms_certified_beds), SUM(avg_residents_per_day),
                    SUM(avg_residents_per_day) / SUM(cms_certified_beds) FILTER (WHERE avg_residents_per_day IS NOT NULL),
                    COUNT(*) FILTER (WHERE avg_residents_per_day IS NULL),
                    COUNT(*) FILTER (WHERE coastal_flood_exposed), COUNT(*) FILTER (WHERE hrcn_ealp_pctile >= 0.8),
                    median(km_nearest_medical_shelter)
             FROM care_facilities""")
    return {
        "rows": {name: count(con, sql) for name, sql in TABLES.items()},
        "hazard_tracts": {"cfld_imputed_outside_layer": h[0], "coastal_flood_exposed": h[1], "nri_population": h[2],
                          "without_vulnerability_tract": h[3],
                          "vulnerability_tracts_without_hazard_row": missing[0],
                          "vulnerability_tracts_without_hazard_row_population": missing[1]},
        "power_dependent_counties": {
            "power_dependent_live": p[0], "power_dependent_snapshot": p[1], "dialysis_live": p[2],
            "facility_esrd_dialysis_any_dme_snapshot": p[3], "dialysis_stations": p[4], "dialysis_centers": p[5],
            "dialysis_patients_per_station": p[2] / p[4], "counties_suppressed_1_11": suppressed,
        },
        "care_facilities": {
            "snapshot_certified_beds": c[0], "cms_certified_beds": c[1], "avg_residents_per_day": c[2],
            "occupancy_rate": c[3], "occupancy_unrecorded": c[4], "in_coastal_flood_tract": c[5],
            "in_top_quintile_hurricane_tract": c[6], "median_km_nearest_medical_shelter_pending": c[7],
            "cms_county_text_disagrees_with_imputed_fips": q("""
                SELECT COUNT(*) FROM care_facilities f JOIN raw_power p ON p.fips_code = f.county_fips
                WHERE lower(replace(f.cms_county_text, ' ', '')) <> lower(replace(p.name, ' ', ''))""")[0],
        },
        "dialysis_centers": {
            "coordinates_confidence": {k: n for k, n in con.execute(
                "SELECT coordinates_confidence, COUNT(*) FROM dialysis_centers GROUP BY 1 ORDER BY 1").fetchall()},
            "stations_without_coordinates": q("SELECT SUM(stations) FROM dialysis_centers WHERE latitude IS NULL")[0],
        },
        "evacuation_zones": {
            "tracts_in_zone": q("SELECT COUNT(*) FROM hazard_tracts WHERE evac_zone IS NOT NULL")[0],
            "population_by_zone": dict(con.execute("""
                SELECT evac_zone, SUM(POPULATION) FROM hazard_tracts WHERE evac_zone IS NOT NULL
                GROUP BY 1 ORDER BY 1""").fetchall()),
            "care_facilities_in_zone": q("SELECT COUNT(*) FROM care_facilities WHERE evac_zone IS NOT NULL")[0],
            "assisted_living_in_zone": q("SELECT COUNT(*) FROM assisted_living WHERE evac_zone IS NOT NULL")[0],
            "assisted_living_beds_in_zone": q(
                "SELECT SUM(licensed_beds) FROM assisted_living WHERE evac_zone IS NOT NULL")[0],
        },
        "assisted_living": {
            t: {"facilities": n, "licensed_beds": b, "small_homes_aggregated": sm, "small_home_beds": sb}
            for t, n, b, sm, sb in con.execute("""
                SELECT facility_type, COUNT(*), SUM(licensed_beds),
                       COUNT(*) FILTER (WHERE facility_identity_status = 'aggregated_small_home'),
                       COALESCE(SUM(licensed_beds) FILTER (WHERE facility_identity_status = 'aggregated_small_home'), 0)
                FROM assisted_living GROUP BY 1 ORDER BY 1""").fetchall()
        } | {"county_text_disagrees_with_imputed_fips": q("""
                SELECT COUNT(*) FROM assisted_living a JOIN raw_power p ON p.fips_code = a.county_fips
                WHERE lower(replace(a.COUNTY, ' ', '')) <> lower(replace(p.name, ' ', ''))""")[0],
             "median_km_nearest_medical_shelter_pending": q(
                "SELECT median(km_nearest_medical_shelter) FROM assisted_living")[0]},
        "contraflow_intersections": {
            "points": q("SELECT COUNT(*) FROM contraflow_intersections")[0],
            "counties": q("SELECT COUNT(DISTINCT county_fips) FROM contraflow_intersections")[0],
            "in_zone": q("SELECT COUNT(*) FROM contraflow_intersections WHERE evac_zone IS NOT NULL")[0],
        },
        "gema_shelter_feed": {"rows": q("SELECT COUNT(*) FROM gema_shelter_feed")[0],
                              "fields_kept": len(SHELTER_FEED_FIELDS),
                              "fields_dropped": q(f"""SELECT COUNT(*) FROM raw_shelter_feed_fields WHERE name NOT IN
                                  ({', '.join(f"'{f}'" for f in SHELTER_FEED_FIELDS)})""")[0]},
        "storm_events": {
            "events": q("SELECT COUNT(*) FROM storm_events")[0],
            "years": list(q("SELECT MIN(year), MAX(year) FROM storm_events")),
            "storms": q("SELECT COUNT(DISTINCT storm_atcf_id) FROM storm_events")[0],
            "match": dict(con.execute(
                "SELECT storm_match_status, COUNT(*) FROM storm_events GROUP BY 1 ORDER BY 1").fetchall()),
            "ga_events": q("SELECT COUNT(*) FROM storm_events WHERE state = 'GA'")[0],
            "ga_storms": q("SELECT COUNT(DISTINCT storm_atcf_id) FROM storm_events WHERE state = 'GA'")[0],
        },
        "overture_places_held": {
            g: {"places": n, "not_permanently_closed": o}
            for g, n, o in con.execute("""
                SELECT place_group, COUNT(*), COUNT(*) FILTER (WHERE operating_status IS DISTINCT FROM 'permanently_closed')
                FROM overture_places GROUP BY 1 ORDER BY 1""").fetchall()
        },
    }


def rounded(value):
    if isinstance(value, dict):
        return {k: rounded(v) for k, v in value.items()}
    if isinstance(value, float):
        return round(value, 4)
    return value


def write(con, out: Path = OUT) -> dict:
    out.mkdir(parents=True, exist_ok=True)
    (out / "held").mkdir(exist_ok=True)
    for name, sql in TABLES.items():
        con.execute(f"COPY ({sql}) TO '{out / (name + '.parquet')}' (FORMAT parquet, COMPRESSION zstd)")
    for name, sql in HELD.items():
        con.execute(f"COPY ({sql}) TO '{out / 'held' / (name + '.parquet')}' (FORMAT parquet, COMPRESSION zstd)")
    nums = rounded(numbers(con))
    (out / "numbers.json").write_text(json.dumps(nums, indent=2, sort_keys=True, default=float) + "\n")
    (out / "rules.json").write_text(json.dumps(R.RULES, indent=2, sort_keys=True) + "\n")
    return nums


def main() -> None:
    from .gaps import write_gaps
    from .report import write_cleaning, write_post

    con = connect()
    register(con, Sources.from_env())
    build_all(con)
    nums = write(con)
    write_gaps(nums)
    write_cleaning(con)
    write_post(con)
    print(json.dumps(nums["rows"], indent=2))


if __name__ == "__main__":
    main()
