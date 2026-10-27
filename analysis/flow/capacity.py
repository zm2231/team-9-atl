from common import connect, one, save_numbers, write_csv

con = connect()

n_rows = one(con, "SELECT COUNT(*) FROM ga_shelters")
assert n_rows == one(con, "SELECT COUNT(*) FROM ga_shelters_raw"), "staging changed row count"
unmatched = one(con, "SELECT COUNT(*) FROM ga_shelters WHERE county_pop IS NULL")
assert unmatched == 0, f"{unmatched} shelters have a county_fips with no tracts"

flags = con.execute("""
    SELECT capacity_flag, COUNT(*) AS shelters, SUM(evacuation_capacity) AS reported_capacity
    FROM ga_shelters GROUP BY 1 ORDER BY 2 DESC, 1
""").fetchall()
print("capacity_flag, shelters, reported_capacity")
for row in flags:
    print(row)

print("\nSuspect and largest rows (reported, never overwritten):")
write_csv(con, """
    SELECT shelter_id, shelter_name, city, county_fips, county_name, usage,
           evacuation_capacity, post_impact_capacity, county_pop,
           round(evacuation_capacity / county_pop, 3) AS capacity_per_county_resident,
           capacity_flag, is_duplicate
    FROM ga_shelters
    WHERE evacuation_capacity >= 4000
    ORDER BY evacuation_capacity DESC, shelter_id
""", "capacity_large_rows.csv")
for row in con.execute("""
    SELECT shelter_name, county_name, evacuation_capacity, county_pop, capacity_flag
    FROM ga_shelters WHERE evacuation_capacity >= 9000 ORDER BY 3 DESC, 1
""").fetchall():
    print(row)

dup = con.execute("""
    SELECT COUNT(*), SUM(evacuation_capacity) FILTER (WHERE capacity_flag = 'ok')
    FROM ga_shelters WHERE is_duplicate
""").fetchall()[0]

totals = con.execute("""
    SELECT SUM(evacuation_capacity),
           SUM(evacuation_capacity) FILTER (WHERE is_evac),
           SUM(clean_capacity),
           COUNT(*) FILTER (WHERE clean_capacity IS NOT NULL),
           COUNT(*) FILTER (WHERE is_evac AND NOT is_duplicate),
           COUNT(*) FILTER (WHERE is_evac AND NOT is_duplicate AND capacity_flag <> 'ok'),
           SUM(evacuation_capacity) FILTER (WHERE capacity_flag LIKE 'suspect%'),
           SUM(evacuation_capacity) FILTER (WHERE shelter_name = 'Georgia World Congress Center')
    FROM ga_shelters
""").fetchall()[0]
(reported, reported_evac, clean, clean_n, evac_buildings, evac_unrecorded,
 suspect_cap, gwcc) = totals
ga_pop = one(con, "SELECT SUM(total_pop) FROM ga_tracts")
print(f"\nreported {reported:,.0f}  EVAC/BOTH {reported_evac:,.0f}  clean {clean:,.0f} in {clean_n} shelters")
print(f"suspect rows {suspect_cap:,.0f} = {suspect_cap / reported:.1%} of reported")
print(f"duplicates {dup[0]} rows, {dup[1] or 0:,.0f} capacity on otherwise-ok rows")
print(f"clean seats per 1,000 Georgians {1000 * clean / ga_pop:.1f}")

county_sql = """
    WITH c AS (
        SELECT county_fips,
               MIN(county_name) AS county_name,
               COUNT(*) FILTER (WHERE is_evac AND NOT is_duplicate) AS evac_shelters,
               COUNT(*) FILTER (WHERE is_evac AND NOT is_duplicate AND clean_capacity IS NULL) AS evac_shelters_unrecorded_or_suspect,
               SUM(evacuation_capacity) FILTER (WHERE is_evac) AS reported_capacity,
               SUM(clean_capacity) AS clean_capacity,
               SUM(evacuation_capacity) FILTER (WHERE capacity_flag LIKE 'suspect%') AS suspect_capacity
        FROM ga_shelters GROUP BY 1
    )
    SELECT p.county_fips, c.county_name, p.county_pop,
           COALESCE(c.evac_shelters, 0) AS evac_shelters,
           COALESCE(c.evac_shelters_unrecorded_or_suspect, 0) AS evac_shelters_unrecorded_or_suspect,
           c.reported_capacity, c.clean_capacity, c.suspect_capacity,
           round(1000 * c.reported_capacity / p.county_pop, 1) AS reported_per_1000,
           round(1000 * c.clean_capacity / p.county_pop, 1) AS clean_per_1000,
           round(c.suspect_capacity / c.reported_capacity, 3) AS suspect_share_of_reported
    FROM ga_county_pop p LEFT JOIN c USING (county_fips)
    ORDER BY reported_per_1000 DESC NULLS LAST, county_fips
"""
write_csv(con, county_sql, "capacity_by_county.csv")
n_counties = one(con, f"SELECT COUNT(*) FROM ({county_sql})")
assert n_counties == 159, n_counties
no_clean = one(con, f"SELECT COUNT(*) FROM ({county_sql}) WHERE clean_capacity IS NULL")
no_clean_pop = one(con, f"SELECT SUM(county_pop) FROM ({county_sql}) WHERE clean_capacity IS NULL")
depends = con.execute(f"""
    SELECT county_name, reported_per_1000, clean_per_1000, suspect_share_of_reported
    FROM ({county_sql}) WHERE suspect_capacity > 0
""").fetchall()
print("\ncounties whose capacity depends on suspect rows:", depends)
print(f"counties with no clean evacuation capacity: {no_clean} (pop {no_clean_pop:,.0f})")
median_clean = one(con, f"SELECT median(clean_per_1000) FROM ({county_sql})")

wc = con.execute("""
    SELECT wheelchair, COUNT(*), SUM(clean_capacity)
    FROM ga_shelters WHERE is_evac AND NOT is_duplicate GROUP BY 1 ORDER BY 1
""").fetchall()
print("\nwheelchair among EVAC/BOTH buildings:", wc)

save_numbers("capacity", {
    "shelter_rows": n_rows,
    "reported_capacity_all_rows": reported,
    "reported_capacity_evac_both": reported_evac,
    "clean_capacity": clean,
    "clean_capacity_shelters": clean_n,
    "evac_both_buildings": evac_buildings,
    "evac_both_buildings_without_usable_capacity": evac_unrecorded,
    "suspect_capacity": suspect_cap,
    "suspect_share_of_reported": suspect_cap / reported,
    "gwcc_capacity": gwcc,
    "gwcc_share_of_clean": gwcc / clean,
    "duplicate_rows": dup[0],
    "duplicate_capacity_removed": dup[1] or 0,
    "flags": {f: {"shelters": n, "reported_capacity": c} for f, n, c in flags},
    "ga_pop": ga_pop,
    "clean_seats_per_1000": 1000 * clean / ga_pop,
    "median_county_clean_seats_per_1000": median_clean,
    "counties_without_clean_capacity": no_clean,
    "pop_in_counties_without_clean_capacity": no_clean_pop,
    "counties_depending_on_suspect_rows": [
        {"county": c, "reported_per_1000": r, "clean_per_1000": k, "suspect_share": s}
        for c, r, k, s in depends],
    "wheelchair_evac_buildings": {w: {"buildings": n, "clean_capacity": c} for w, n, c in wc},
})
