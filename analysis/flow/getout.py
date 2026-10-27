from common import connect, one, save_numbers, write_csv

con = connect()

con.execute("""
    CREATE TABLE dest AS
    SELECT shelter_id, shelter_name, wheelchair, in_surge_slosh_area, geom
    FROM ga_shelters WHERE clean_capacity IS NOT NULL
""")
con.execute("""
    CREATE TABLE coastal AS
    SELECT t.geo_id, t.county_fips, t.total_pop, t.households, t.households_no_vehicle,
           t.households - t.households_no_vehicle AS car_households,
           t.pop_65_plus, t.pct_disability, t.pct_lacktrpt, h.cfld_share, h.CFLD_EXPP, t.geom
    FROM ga_tracts t JOIN ga_hazard h USING (geo_id)
    WHERE h.CFLD_EXPP > 0
""")
n_coastal = one(con, "SELECT COUNT(*) FROM coastal")

con.execute("""
    CREATE TABLE coastal_dist AS
    SELECT c.geo_id,
           MIN(ST_Distance(c.geom, d.geom)) / 1000 AS km_any,
           MIN(ST_Distance(c.geom, d.geom)) FILTER (WHERE d.wheelchair = 'yes') / 1000 AS km_wheelchair_yes,
           MIN(ST_Distance(c.geom, d.geom)) FILTER (
               WHERE d.wheelchair = 'yes' AND d.in_surge_slosh_area IS NOT TRUE) / 1000 AS km_wheelchair_yes_not_in_surge
    FROM coastal c CROSS JOIN dest d GROUP BY 1
""")
assert one(con, "SELECT COUNT(*) FROM coastal_dist") == n_coastal

tract_sql = """
    SELECT c.geo_id, c.county_fips, c.total_pop, c.households, c.households_no_vehicle,
           c.car_households,
           round(c.car_households / NULLIF(c.households_no_vehicle, 0), 2) AS car_hh_per_carless_hh,
           round(c.households_no_vehicle * c.cfld_share, 1) AS carless_hh_on_flood_layer,
           round(c.cfld_share, 3) AS cfld_share, c.pop_65_plus, c.pct_disability, c.pct_lacktrpt,
           round(d.km_any, 2) AS km_nearest_shelter,
           round(d.km_wheelchair_yes, 2) AS km_nearest_wheelchair_yes,
           round(d.km_wheelchair_yes_not_in_surge, 2) AS km_nearest_wheelchair_yes_not_in_surge
    FROM coastal c JOIN coastal_dist d USING (geo_id)
"""
write_csv(con, f"{tract_sql} ORDER BY carless_hh_on_flood_layer DESC, geo_id", "coastal_tracts.csv")
write_csv(con, f"{tract_sql} ORDER BY carless_hh_on_flood_layer DESC, geo_id LIMIT 20", "top20_coastal_carless.csv")

agg = con.execute(f"""
    SELECT SUM(households_no_vehicle), SUM(car_households),
           SUM(car_households) / SUM(households_no_vehicle),
           COUNT(*) FILTER (WHERE car_hh_per_carless_hh < 2),
           COUNT(*) FILTER (WHERE households_no_vehicle = 0),
           median(km_nearest_shelter), median(km_nearest_wheelchair_yes),
           median(km_nearest_wheelchair_yes_not_in_surge),
           COUNT(*) FILTER (WHERE km_nearest_wheelchair_yes > 10),
           SUM(households_no_vehicle) FILTER (WHERE km_nearest_wheelchair_yes > 10),
           SUM(carless_hh_on_flood_layer), SUM(total_pop)
    FROM ({tract_sql})
""").fetchall()[0]
low_ratio = con.execute(f"""
    SELECT geo_id, households_no_vehicle, car_households, car_hh_per_carless_hh, km_nearest_wheelchair_yes
    FROM ({tract_sql}) WHERE car_hh_per_carless_hh < 2 ORDER BY car_hh_per_carless_hh, geo_id
""").fetchall()
by_county = f"""
    SELECT county_fips, COUNT(*) AS coastal_tracts, SUM(total_pop) AS pop,
           SUM(households_no_vehicle) AS carless_households,
           round(SUM(car_households) / SUM(households_no_vehicle), 1) AS car_hh_per_carless_hh,
           round(SUM(carless_hh_on_flood_layer)) AS carless_hh_on_flood_layer,
           round(median(km_nearest_wheelchair_yes), 1) AS median_km_wheelchair_yes
    FROM ({tract_sql}) GROUP BY 1 ORDER BY carless_hh_on_flood_layer DESC, county_fips
"""
write_csv(con, by_county, "coastal_by_county.csv")
print(con.execute(by_county).df().to_string())
print("aggregate:", agg)
print("tracts with <2 car households per carless:", low_ratio)
surge = con.execute("""
    SELECT COUNT(*), COUNT(*) FILTER (WHERE in_surge_slosh_area),
           COUNT(*) FILTER (WHERE in_surge_slosh_area IS NULL)
    FROM ga_shelters
    WHERE clean_capacity IS NOT NULL AND wheelchair = 'yes'
      AND county_fips IN (SELECT DISTINCT county_fips FROM coastal)
""").fetchall()[0]
print("coastal-county wheelchair-yes shelters: total, in surge, surge unrecorded:", surge)

save_numbers("getout", {
    "coastal_tracts": n_coastal,
    "coastal_pop": agg[11],
    "carless_households": agg[0],
    "car_households": agg[1],
    "car_hh_per_carless_hh": agg[2],
    "tracts_ratio_under_2": agg[3],
    "tracts_ratio_under_2_list": [
        {"geo_id": g, "carless": a, "car_hh": b, "ratio": r, "km_wheelchair_yes": k}
        for g, a, b, r, k in low_ratio],
    "tracts_zero_carless": agg[4],
    "median_km_any_shelter": agg[5],
    "median_km_wheelchair_yes": agg[6],
    "median_km_wheelchair_yes_not_in_surge": agg[7],
    "tracts_wheelchair_yes_over_10km": agg[8],
    "carless_hh_in_tracts_wheelchair_yes_over_10km": agg[9],
    "carless_hh_on_flood_layer": agg[10],
    "coastal_county_wheelchair_yes_shelters": surge[0],
    "coastal_county_wheelchair_yes_in_surge": surge[1],
    "coastal_county_wheelchair_yes_surge_unrecorded": surge[2],
})
