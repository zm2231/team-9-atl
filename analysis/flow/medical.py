from common import connect, one, pt, save_numbers, table, write_csv

HIGH_HURRICANE_QUANTILE = 0.8

con = connect()

con.execute("""
    CREATE TABLE med AS
    SELECT shelter_id, shelter_name, county_fips, usage, evacuation_capacity, clean_capacity,
           capacity_flag, wheelchair, generator, in_surge_slosh_area, geom
    FROM ga_shelters WHERE is_medical AND NOT is_duplicate
""")
med_rows = con.execute("""
    SELECT shelter_name, county_fips, usage, evacuation_capacity, capacity_flag, generator, in_surge_slosh_area
    FROM med ORDER BY county_fips, shelter_name
""").fetchall()
print("medical-needs shelters:")
for r in med_rows:
    print(r)

hurricane_cut = one(con, f"SELECT quantile_cont(HRCN_AFREQ, {HIGH_HURRICANE_QUANTILE}) FROM ga_hazard")

con.execute("""
    CREATE TABLE tract_med AS
    SELECT t.geo_id, t.county_fips, t.total_pop, t.pop_65_plus, h.cfld_share, h.CFLD_EXPP, h.HRCN_AFREQ,
           MIN(ST_Distance(t.geom, m.geom)) / 1000 AS km_medical
    FROM ga_tracts t CROSS JOIN med m LEFT JOIN ga_hazard h USING (geo_id)
    GROUP BY ALL
""")
assert one(con, "SELECT COUNT(*) FROM tract_med") == one(con, "SELECT COUNT(*) FROM ga_tracts")

county_sql = f"""
    WITH pd AS (
        SELECT fips_code AS county_fips, name AS county_name, medicare_benes, power_dependent_dme,
               facility_esrd_dialysis_any_dme, o2_services_any_dme
        FROM {table('GA', 'power_dependent_counties')}
    ), seats AS (
        SELECT county_fips, COUNT(*) AS medical_shelters, SUM(clean_capacity) AS medical_seats_clean,
               SUM(evacuation_capacity) AS medical_seats_reported
        FROM med GROUP BY 1
    ), dist AS (
        SELECT county_fips, SUM(km_medical * total_pop) / SUM(total_pop) AS pop_weighted_km_medical
        FROM tract_med GROUP BY 1
    )
    SELECT pd.county_fips, pd.county_name, pd.medicare_benes, pd.power_dependent_dme,
           pd.facility_esrd_dialysis_any_dme, pd.o2_services_any_dme,
           COALESCE(seats.medical_shelters, 0) AS medical_shelters,
           seats.medical_seats_reported, seats.medical_seats_clean,
           round(pd.power_dependent_dme / seats.medical_seats_clean, 2) AS power_dependent_per_medical_seat,
           round(dist.pop_weighted_km_medical, 1) AS pop_weighted_km_medical
    FROM pd LEFT JOIN seats USING (county_fips) LEFT JOIN dist USING (county_fips)
    ORDER BY pd.power_dependent_dme DESC, pd.county_fips
"""
assert one(con, f"SELECT COUNT(*) FROM ({county_sql})") == 159
write_csv(con, county_sql, "medical_by_county.csv")
cty = con.execute(f"""
    SELECT SUM(power_dependent_dme),
           SUM(power_dependent_dme) FILTER (WHERE medical_shelters = 0),
           COUNT(*) FILTER (WHERE medical_shelters = 0),
           SUM(medical_seats_clean), SUM(medical_seats_reported),
           COUNT(*) FILTER (WHERE medical_shelters > 0 AND medical_seats_clean IS NULL)
    FROM ({county_sql})
""").fetchall()[0]
print("power-dependent total, in counties w/o medical shelter, n such counties, clean seats, reported seats, counties with medical shelter but no usable seat:", cty)
print(con.execute(f"SELECT * FROM ({county_sql}) WHERE medical_shelters > 0").df().to_string())

con.execute(f"""
    CREATE TABLE fac AS
    SELECT f.cms_certification_number_ccn AS ccn, f.provider_name, f.citytown, f.number_of_certified_beds AS beds,
           {pt('f.longitude', 'f.latitude')} AS geom
    FROM {table('GA', 'care_facilities')} f
    WHERE f.latitude IS NOT NULL
""")
n_fac = one(con, f"SELECT COUNT(*) FROM {table('GA', 'care_facilities')}")
n_fac_geo = one(con, "SELECT COUNT(*) FROM fac")
con.execute("""
    CREATE TABLE fac_tract AS
    SELECT f.ccn, f.provider_name, f.citytown, f.beds, t.geo_id, t.county_fips,
           ST_Distance(f.geom, t.geom) / 1000 AS km_to_tract_centroid
    FROM fac f CROSS JOIN ga_tracts t
    QUALIFY ROW_NUMBER() OVER (PARTITION BY f.ccn ORDER BY ST_Distance(f.geom, t.geom), t.geo_id) = 1
""")
con.execute("""
    CREATE TABLE fac_med AS
    SELECT f.ccn, MIN(ST_Distance(f.geom, m.geom)) / 1000 AS km_medical
    FROM fac f CROSS JOIN med m GROUP BY 1
""")
fac_sql = f"""
    SELECT ft.ccn, ft.provider_name, ft.citytown, ft.county_fips, ft.beds, ft.geo_id AS nearest_tract,
           round(h.cfld_share, 3) AS tract_cfld_share, round(h.HRCN_AFREQ, 4) AS tract_hrcn_afreq,
           COALESCE(h.CFLD_EXPP, 0) > 0 AS coastal_flood_tract,
           h.HRCN_AFREQ >= {hurricane_cut} AS high_hurricane_tract,
           round(fm.km_medical, 1) AS km_nearest_medical_shelter
    FROM fac_tract ft JOIN fac_med fm USING (ccn) LEFT JOIN ga_hazard h USING (geo_id)
"""
assert one(con, f"SELECT COUNT(*) FROM ({fac_sql})") == n_fac_geo
write_csv(con, f"{fac_sql} WHERE coastal_flood_tract OR high_hurricane_tract ORDER BY km_nearest_medical_shelter DESC, ccn",
          "care_facilities_exposed.csv")
fac_agg = con.execute(f"""
    SELECT COUNT(*) FILTER (WHERE coastal_flood_tract), SUM(beds) FILTER (WHERE coastal_flood_tract),
           COUNT(*) FILTER (WHERE high_hurricane_tract), SUM(beds) FILTER (WHERE high_hurricane_tract),
           COUNT(*) FILTER (WHERE coastal_flood_tract OR high_hurricane_tract),
           SUM(beds) FILTER (WHERE coastal_flood_tract OR high_hurricane_tract),
           median(km_nearest_medical_shelter) FILTER (WHERE coastal_flood_tract OR high_hurricane_tract),
           median(km_nearest_medical_shelter),
           COUNT(*) FILTER (WHERE (coastal_flood_tract OR high_hurricane_tract) AND km_nearest_medical_shelter > 50),
           SUM(beds)
    FROM ({fac_sql})
""").fetchall()[0]
print("facilities coastal n/beds, high-hurricane n/beds, either n/beds, median km exposed, median km all, exposed >50km, all beds:", fac_agg)

tract_agg = con.execute("""
    SELECT median(km_medical),
           SUM(total_pop) FILTER (WHERE km_medical > 50),
           SUM(pop_65_plus) FILTER (WHERE km_medical > 50),
           median(km_medical) FILTER (WHERE CFLD_EXPP > 0)
    FROM tract_med
""").fetchall()[0]
print("median tract km to medical, pop >50km, 65+ >50km, coastal median km:", tract_agg)

save_numbers("medical", {
    "medical_shelters": len(med_rows),
    "medical_shelter_rows": [
        {"name": n, "county_fips": c, "usage": u, "capacity": cap, "flag": f, "generator": g, "in_surge": s}
        for n, c, u, cap, f, g, s in med_rows],
    "power_dependent_total": cty[0],
    "power_dependent_in_counties_without_medical_shelter": cty[1],
    "counties_without_medical_shelter": cty[2],
    "medical_seats_clean": cty[3],
    "medical_seats_reported": cty[4],
    "counties_with_medical_shelter_but_no_usable_seat": cty[5],
    "power_dependent_per_clean_medical_seat_statewide": cty[0] / cty[3],
    "high_hurricane_afreq_cut": hurricane_cut,
    "care_facilities": n_fac,
    "care_facilities_with_coords": n_fac_geo,
    "care_beds": fac_agg[9],
    "care_facilities_coastal_flood_tract": fac_agg[0],
    "care_beds_coastal_flood_tract": fac_agg[1],
    "care_facilities_high_hurricane_tract": fac_agg[2],
    "care_beds_high_hurricane_tract": fac_agg[3],
    "care_facilities_exposed": fac_agg[4],
    "care_beds_exposed": fac_agg[5],
    "median_km_medical_exposed_facilities": fac_agg[6],
    "median_km_medical_all_facilities": fac_agg[7],
    "exposed_facilities_over_50km_from_medical": fac_agg[8],
    "median_tract_km_medical": tract_agg[0],
    "pop_over_50km_from_medical": tract_agg[1],
    "pop_65_plus_over_50km_from_medical": tract_agg[2],
    "median_coastal_tract_km_medical": tract_agg[3],
})
