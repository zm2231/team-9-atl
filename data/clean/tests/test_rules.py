import pytest

from gaclean import build as B
from gaclean.sources import Sources


def table(con, name, cols, rows):
    con.execute(f"CREATE TABLE {name} ({', '.join(cols)})")
    if rows:
        con.executemany(f"INSERT INTO {name} VALUES ({', '.join('?' for _ in cols)})", rows)


EMPOWER = ["Medicare_Benes", "Power_Dependent_Devices_DME", "Facility_ESRD_Dialysis_Any_DME", "O2_Services_Any_DME",
           "Home_Health_Services_Any_DME", "AtHome_Hospice_Any_DME", "Any_Healthcare_Srvc_Any_DME"]
POWER_TYPES = {"objectid": "BIGINT", "power_dependent_is_censored": "BOOLEAN"}
NUMERIC = {"medicare_benes", "power_dependent_devices_dme", "facility_esrd_dialysis_any_dme", "o2_services_any_dme",
           "home_health_services_any_dme", "athome_hospice_any_dme", "any_healthcare_srvc_any_dme", "shape__area",
           "shape__length", "power_dependent_dme"}


def power_row(fips, name, esrd):
    vals = {"objectid": int(fips), "name": name, "fips_code": fips, "facility_esrd_dialysis_any_dme": esrd,
            "power_dependent_is_censored": False, "power_dependent_dme": 40.0}
    row = [vals.get(c, 1.0 if c in NUMERIC else "x") for c in B.BQ_COLUMNS["power_dependent_counties"]]
    return row + ["13", 1.0, 2.0]


@pytest.fixture
def con():
    c = B.connect()
    table(c, "raw_tracts", ["geo_id VARCHAR", "county_fips VARCHAR", "lat DOUBLE", "lon DOUBLE", "total_pop DOUBLE"], [
        ["13001000100", "13001", 33.00, -84.00, 1000], ["13001000200", "13001", 33.10, -84.10, 3000],
        ["13003000100", "13003", 31.00, -82.00, 2000], ["13003990000", "13003", 30.90, -81.90, 0]])
    hz = [f"{c} {'VARCHAR' if c == 'geo_id' else 'DOUBLE'}" for c in B.BQ_COLUMNS["hazard_tracts"]]
    table(c, "raw_hazard", hz, [
        ["13001000100", 1000, 1, 0.1, 1, 1, 0.001, None, None, None, None],
        ["13001000200", 3000, 1, 0.1, 1, 1, 0.003, None, None, None, None],
        ["13003000100", 2000, 1, 0.3, 1, 1, 0.002, 1.0, 500, 1, 1]])
    table(c, "raw_power",
          [f"{col} {POWER_TYPES.get(col, 'DOUBLE' if col in NUMERIC else 'VARCHAR')}"
           for col in B.BQ_COLUMNS["power_dependent_counties"]]
          + ["first_state_fips_code VARCHAR", "objectid_1 DOUBLE", "power_de_1 DOUBLE"],
          [power_row("13001", "Appling", 5.0), power_row("13003", "Atkinson", 3.0)])
    table(c, "raw_empower_live", ["FIPS_Code VARCHAR"] + [f"{e} BIGINT" for e in EMPOWER], [
        ["13001", 510, 45, 30, 12, 9, 8, 60], ["13003", 310, 22, 11, 11, 11, 11, 25]])
    table(c, "raw_empower_zip", ["Zip_Code VARCHAR", "FIPS_Code VARCHAR"], [["31510", "13003"], ["30000", "13001"]])
    table(c, "raw_cms_dialysis", ['"CMS Certification Number (CCN)" VARCHAR', '"Facility Name" VARCHAR',
                                  '"Address Line 1" VARCHAR', '"City/Town" VARCHAR', '"ZIP Code" VARCHAR',
                                  '"County/Parish" VARCHAR', '"# of Dialysis Stations" VARCHAR', '"Late Shift" VARCHAR',
                                  '"Offers in-center hemodialysis" VARCHAR', '"Offers peritoneal dialysis" VARCHAR',
                                  '"Offers home hemodialysis training" VARCHAR', '"Profit or Non-Profit" VARCHAR',
                                  '"Chain Organization" VARCHAR'],
          [["112500", "Coast Dialysis", "2 Elm", "Pearson", "31510-1234", "Atkinson", "18", "No", "Yes", "Yes", "No",
            "Profit", " "],
           ["112501", "Town Dialysis", "3 Elm", "Town", "30000", "Appling", "12", "No", "Yes", "No", "No", "Profit", "X"]])
    table(c, "raw_dialysis_geo", ["ccn VARCHAR", "lat DOUBLE", "lon DOUBLE", "location_status VARCHAR"],
          [["112500", 31.3, -82.8, "geocoded_census_non_exact"], ["112501", None, None, "unmatched"]])
    table(c, "raw_shelters", ["latitude DOUBLE", "longitude DOUBLE", "is_medical BOOLEAN"],
          [[33.0, -84.0, False], [32.0, -83.0, True]])
    c.execute("""CREATE TABLE raw_zones AS SELECT * FROM (VALUES
                 ('Coast', 'B', ST_GeomFromText('POLYGON((-82.2 30.8, -81.8 30.8, -81.8 31.2, -82.2 31.2, -82.2 30.8))')),
                 ('Coast', 'A', ST_GeomFromText('POLYGON((-82.1 30.9, -81.9 30.9, -81.9 31.1, -82.1 31.1, -82.1 30.9))')))
                 t(County, Zone, geom)""")
    yield c
    c.close()


def leading(con, name):
    cols = [r[0] for r in con.execute(f"DESCRIBE {name}").fetchall()]
    return cols[:len(B.BQ_COLUMNS[name])]


def test_hazard_cfld_percentile_and_source_columns_unchanged(con):
    B.build_hazard_tracts(con)
    assert leading(con, "hazard_tracts") == B.BQ_COLUMNS["hazard_tracts"]
    t = {r[0]: r[1:] for r in con.execute(
        "SELECT geo_id, CFLD_EXPP, cfld_expp_clean, cfld_expp_clean_status, cfld_expp_clean_rule, hrcn_ealp_pctile, "
        "county_fips "
        "FROM hazard_tracts").fetchall()}
    assert len(t) == 3
    assert t["13001000100"][:4] == (None, 0, "imputed", "cfld_null_outside_layer")
    assert t["13003000100"][:4] == (500, 500, "recorded", "source_value")
    assert t["13001000100"][4] < t["13003000100"][4] < t["13001000200"][4]
    assert t["13003000100"][5] == "13003"
    z = dict(con.execute("SELECT geo_id, evac_zone || ':' || evac_zone_status FROM hazard_tracts "
                         "WHERE evac_zone IS NOT NULL OR evac_zone_status <> 'external'").fetchall())
    assert z == {"13003000100": "A:external"}


def test_populated_tract_without_hazard_row_fails(con):
    con.execute("INSERT INTO raw_tracts VALUES ('13003000999', '13003', 31.1, -82.1, 50)")
    with pytest.raises(AssertionError, match="without a hazard row hold 50"):
        B.build_hazard_tracts(con)


def test_empower_live_beside_snapshot_with_suppression(con):
    B.build_power_dependent_counties(con)
    assert leading(con, "power_dependent_counties") == B.BQ_COLUMNS["power_dependent_counties"]
    cols = [r[0] for r in con.execute("DESCRIBE power_dependent_counties").fetchall()]
    assert not {"first_state_fips_code", "objectid_1", "power_de_1"} & set(cols)
    c = {r[0]: r[1:] for r in con.execute(
        "SELECT fips_code, facility_esrd_dialysis_any_dme, facility_esrd_dialysis_any_dme_status, dialysis_live, "
        "dialysis_live_low, dialysis_live_status, dialysis_live_rule, dialysis_stations "
        "FROM power_dependent_counties").fetchall()}
    assert c["13001"] == (5, "suspect", 30, 30, "recorded", "empower_live_canonical", 12)
    assert c["13003"] == (3, "suspect", 11, 1, "imputed", "empower_suppressed_1_11", 18)


def test_care_facility_must_join_cms_on_ccn(con):
    B.build_hazard_tracts(con)
    table(con, "raw_care", [f"{c} {'DOUBLE' if c in ('number_of_certified_beds', 'latitude', 'longitude') else 'VARCHAR'}"
                            for c in B.BQ_COLUMNS["care_facilities"]],
          [["115001", "Home A ", "1 Oak", "Town", "GA", "30000", 100, "Profit", 33.0, -84.0],
           ["115002", "Home B", "2 Oak", "Town", "GA", "30000", 50, "Profit", 31.0, -82.0]])
    table(con, "raw_cms_nh", ['"CMS Certification Number (CCN)" VARCHAR', '"County/Parish" VARCHAR',
                              '"Number of Certified Beds" VARCHAR', '"Average Number of Residents per Day" VARCHAR',
                              '"Provider Type" VARCHAR', '"Automatic Sprinkler Systems in All Required Areas" VARCHAR'],
          [["115001", "Appling", "100", "80", "Medicare and Medicaid", "Yes"]])
    with pytest.raises(AssertionError, match="care_facilities_pre: expected 2 rows, got 1"):
        B.build_care_facilities(con)
    con.execute("DROP TABLE care_facilities_pre")
    con.execute("INSERT INTO raw_cms_nh VALUES ('115002', 'Atkinson', '50', NULL, 'Medicaid', 'Yes')")
    B.build_care_facilities(con)
    assert leading(con, "care_facilities") == B.BQ_COLUMNS["care_facilities"]
    f = {r[0]: r[1:] for r in con.execute(
        "SELECT cms_certification_number_ccn, provider_name, provider_name_clean, occupancy_rate, "
        "occupancy_rate_status, county_fips, county_fips_status, round(km_nearest_medical_shelter) "
        "FROM care_facilities").fetchall()}
    assert f["115001"][:5] == ("Home A ", "Home A", 0.8, "recorded", "13001")
    assert f["115002"][3:6] == ("unrecorded", "13003", "imputed")
    assert f["115001"][6] == pytest.approx(144, abs=2)


def test_dialysis_county_from_zip_and_geocode_confidence(con):
    B.build_dialysis_centers(con)
    rows = con.execute("SELECT ccn, county_fips, stations, latitude IS NOT NULL, coordinates_status, coordinates_rule, "
                       "coordinates_confidence, chain FROM dialysis_centers ORDER BY ccn").fetchall()
    assert rows == [
        ("112500", "13003", 18, True, "external", "census_geocoder", "geocoded_census_non_exact", None),
        ("112501", "13001", 12, False, "unrecorded", "coordinates_absent", "unmatched", "X"),
    ]


def test_overture_places_keep_licence_and_group(con):
    table(con, "raw_overture", [f"{c} {'DOUBLE' if c in ('confidence', 'lon', 'lat') else 'VARCHAR'}"
                                for c in B.SOURCE_COLUMNS["overture_places"]],
          [["o1", "Pines ALF", "assisted_living_facility", 0.9, "1 Pine", "Town", "30000", -84.0, 33.0, "Foursquare",
            "Apache-2.0", "open"],
           ["o2", "Grill", "restaurant", 0.9, "2 Pine", "Town", "30000", -84.0, 33.0, "meta", "CDLA-Permissive-2.0",
            "open"],
           ["o3", "Coast EMS", "ambulance_or_ems_service", 0.5, "3 Pine", "Port", "31510", -82.0, 31.0, "meta",
            "CDLA-Permissive-2.0", None]])
    B.build_overture_places(con)
    rows = con.execute("SELECT id, place_group, place_group_status, place_group_rule, source_license, county_fips, "
                       "county_fips_status FROM overture_places ORDER BY id").fetchall()
    assert rows == [("o1", "assisted_living", "external", "overture_places", "Apache-2.0", "13001", "imputed"),
                    ("o3", "ambulance_ems", "external", "overture_places", "CDLA-Permissive-2.0", "13003", "imputed")]


def test_every_appended_column_carries_status_and_rule(con):
    B.build_hazard_tracts(con)
    B.build_power_dependent_counties(con)
    B.build_dialysis_centers(con)
    con.execute("ALTER TABLE hazard_tracts ADD COLUMN extra DOUBLE")
    assert B.unprovenanced(con, "hazard_tracts") == ["extra"]
    assert B.unprovenanced(con, "power_dependent_counties") == []
    assert B.unprovenanced(con, "dialysis_centers") == []
    statuses = {v for t in ("hazard_tracts", "power_dependent_counties", "dialysis_centers")
                for (c,) in con.execute(f"SELECT column_name FROM (DESCRIBE {t})").fetchall() if c.endswith("_status")
                and c not in B.SOURCE_COLUMNS[t]
                for (v,) in con.execute(f"SELECT DISTINCT {c} FROM {t}").fetchall()}
    assert statuses <= set(B.R.STATUSES)
    rules = {v for t in ("hazard_tracts", "power_dependent_counties", "dialysis_centers")
             for (c,) in con.execute(f"SELECT column_name FROM (DESCRIBE {t})").fetchall() if c.endswith("_rule")
             for (v,) in con.execute(f"SELECT DISTINCT {c} FROM {t}").fetchall()}
    assert rules <= set(B.R.RULES)


GAMAP = ["FACTYPE VARCHAR", "FACID VARCHAR", "NAME VARCHAR", "ADDRESS VARCHAR", "FAC_CITY VARCHAR", "FAC_ST VARCHAR",
         "FAC_ZIP VARCHAR", "OPERSTDESC VARCHAR", "OPERSTATDT VARCHAR", "OPEN_DATE VARCHAR", "CLOSEDDATE VARCHAR",
         "licensed_beds DOUBLE", "EFFECTIVE_DATE_OF_LICENSE VARCHAR", "facility_type VARCHAR", "SUBTYPE VARCHAR",
         "COUNTY VARCHAR", "Latitude DOUBLE", "Longitude DOUBLE", "Accuracy VARCHAR"]


def gamap_row(facid, ftype, beds, lat, lon):
    return [None, facid, f"Home {facid}", f"{facid} Oak St", "Town", "GA", "30000", "Active", "2020-01-01",
            "2019-01-01", None, beds, "2021-01-01", ftype, None, "APPLING", lat, lon, "ROOFTOP"]


def test_small_personal_care_homes_lose_name_address_and_point(con):
    B.build_hazard_tracts(con)
    table(con, "raw_gamap2care", GAMAP, [
        gamap_row("PCH1", "PERSONAL CARE HOME", 6, 33.01, -84.02),
        gamap_row("PCH2", "PERSONAL CARE HOME", 7, 33.01, -84.02),
        gamap_row("ALC1", "ASSISTED LIVING COMMUNITY", 6, 31.0, -82.0)])
    B.build_assisted_living(con)
    rows = {r[0]: r[1:] for r in con.execute(
        "SELECT FACID, NAME, ADDRESS, Latitude, Longitude, facility_identity_status, licensed_beds, county_fips, "
        "evac_zone FROM assisted_living").fetchall()}
    assert "PCH1" not in rows
    assert rows["pch_small_13001_001"] == (None, None, 33.0, -84.0, "aggregated_small_home", 6, "13001", None)
    small = con.execute(f"SELECT {', '.join(B.SMALL_HOME_REMOVED)} FROM assisted_living "
                        "WHERE facility_identity_status = 'aggregated_small_home'").fetchall()
    assert small == [(None,) * len(B.SMALL_HOME_REMOVED)]
    assert rows["PCH2"][:5] == ("Home PCH2", "PCH2 Oak St", 33.01, -84.02, "recorded")
    assert rows["ALC1"][4:] == ("recorded", 6, "13003", "A")
    assert B.unprovenanced(con, "assisted_living") == []


def test_shelter_feed_never_reads_contact_fields(con):
    fields = [(f, "esriFieldTypeInteger" if f in ("dataid", "capacity", "post_impact_capacity", "occupancy")
               else "esriFieldTypeString") for f in B.SHELTER_FEED_FIELDS]
    fields += [("primary_contact", "esriFieldTypeString"), ("primary_phone", "esriFieldTypeString"),
               ("remarks", "esriFieldTypeString")]
    table(con, "raw_shelter_feed_fields", ["name VARCHAR", "type VARCHAR"], fields)
    B.build_gema_shelter_feed(con)
    cols = [r[0] for r in con.execute("DESCRIBE gema_shelter_feed").fetchall()]
    assert cols == B.SHELTER_FEED_FIELDS
    assert not any("contact" in c or "phone" in c or c in ("remarks", "Creator", "Editor") for c in cols)


def test_storm_match_status_and_history(con):
    table(con, "raw_ncei", ["event_id BIGINT", "state VARCHAR", "year INTEGER", "is_tropical_type BOOLEAN",
                            "county_fips VARCHAR", "deaths_direct INTEGER", "deaths_indirect INTEGER",
                            "injuries_direct INTEGER", "damage_property_usd DOUBLE", "damage_crops_usd DOUBLE",
                            "begin_local TIMESTAMP", "end_local TIMESTAMP", "storm_atcf_id VARCHAR",
                            "storm_name VARCHAR", "storm_match_method VARCHAR"], [
        [1, "GA", 2017, True, "13051", 1, 0, 0, 100.0, 0.0, "2017-09-11", "2017-09-11", "AL112017", "IRMA",
         "narrative_name+hurdat2_active"],
        [2, "GA", 2017, True, None, 0, 1, 0, 50.0, 0.0, "2017-09-10", "2017-09-12", "AL112017", "IRMA",
         "nearest_active_hurdat2"],
        [3, "GA", 2018, False, "13051", 0, 0, 0, 0.0, 0.0, "2018-01-01", "2018-01-01", None, None, None]])
    B.build_storm_events(con)
    st = dict(con.execute("SELECT event_id, storm_match_status FROM storm_events").fetchall())
    assert st == {1: "external", 2: "imputed", 3: "unrecorded"}
    assert con.execute("SELECT storm_atcf_id, events, counties, deaths_direct, deaths_indirect, damage_property_usd "
                       "FROM storm_history").fetchall() == [("AL112017", 2, 1, 1, 1, 150.0)]


SRC = Sources.from_env()


@pytest.mark.skipif(not SRC.snapshot.exists(), reason="Georgia snapshot not present")
def test_real_inputs_canonical_numbers():
    con = B.connect()
    B.register(con, SRC)
    B.build_all(con)
    nums = B.numbers(con)
    assert nums["rows"] == {"care_facilities": 356, "hazard_tracts": 2791, "power_dependent_counties": 159,
                            "dialysis_centers": 355, "assisted_living": 1894, "contraflow_intersections": 32,
                            "gema_shelter_feed": 0, "storm_events": 6934, "storm_history": 192}
    assert nums["assisted_living"]["PERSONAL CARE HOME"]["small_homes_aggregated"] == 1044
    small = con.execute("""
        SELECT COUNT(*) FROM assisted_living a WHERE facility_identity_status = 'aggregated_small_home' AND (
            FACID IN (SELECT FACID FROM raw_gamap2care) OR NAME IS NOT NULL OR ADDRESS IS NOT NULL
            OR EXISTS (SELECT 1 FROM raw_gamap2care g WHERE g.Latitude = a.Latitude AND g.Longitude = a.Longitude))
    """).fetchall()[0][0]
    assert small == 0
    assert nums["evacuation_zones"]["tracts_in_zone"] == 198
    p = nums["power_dependent_counties"]
    assert (p["dialysis_live"], p["dialysis_stations"], p["facility_esrd_dialysis_any_dme_snapshot"]) == (18026, 5956, 6009)
    assert nums["hazard_tracts"]["cfld_imputed_outside_layer"] == 2588
    assert nums["care_facilities"]["occupancy_unrecorded"] == 2
