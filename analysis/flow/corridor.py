import csv

from common import CORRIDOR_BUFFER_KM, OUT, connect, one, save_numbers, table, write_csv

# Every rate below is an assumption, not a measurement. Low/base/high bracket it.
ASSUMPTIONS = {
    # share of residents of coastal-flood-exposed land who leave home
    "evacuation_rate": {"low": 0.30, "base": 0.50, "high": 0.70},
    # share of evacuees who use a public shelter rather than hotels, friends, family.
    # Anchor: Irma 2017, Florida reported 127,000 in shelters against ~6.4M told to leave (~2%).
    "shelter_use_rate": {"low": 0.02, "base": 0.05, "high": 0.10},
    # share of Florida evacuees whose destination is in Georgia, by Florida region
    "fl_to_ga_share": {
        "north FL (lat >= 29.5)": {"low": 0.15, "base": 0.30, "high": 0.50},
        "central FL (27.5-29.5)": {"low": 0.05, "base": 0.15, "high": 0.30},
        "south FL (lat < 27.5)": {"low": 0.02, "base": 0.05, "high": 0.15},
    },
}
SCENARIOS = ("low", "base", "high")
BUF = CORRIDOR_BUFFER_KM * 1000

con = connect()

con.execute(f"""
    CREATE TABLE corridor_shelters AS
    SELECT c.corridor, s.*
    FROM ga_shelters s JOIN corridors c ON ST_DWithin(s.geom, c.geom, {BUF})
""")
con.execute(f"""
    CREATE TABLE corridor_tracts AS
    SELECT c.corridor, t.*, h.cfld_share
    FROM ga_tracts t JOIN corridors c ON ST_DWithin(t.geom, c.geom, {BUF})
    LEFT JOIN ga_hazard h USING (geo_id)
""")

per_corridor = """
    WITH s AS (
        SELECT corridor,
               COUNT(*) FILTER (WHERE is_evac AND NOT is_duplicate) AS evac_buildings,
               SUM(evacuation_capacity) FILTER (WHERE is_evac) AS reported_capacity,
               SUM(clean_capacity) AS clean_capacity,
               SUM(clean_capacity) FILTER (WHERE wheelchair = 'yes') AS clean_capacity_wheelchair_yes,
               SUM(clean_capacity) FILTER (WHERE in_surge_slosh_area) AS clean_capacity_in_surge_area,
               COUNT(*) FILTER (WHERE is_medical AND is_evac) AS medical_shelters
        FROM corridor_shelters GROUP BY 1
    ), t AS (
        SELECT corridor, COUNT(*) AS tracts, SUM(total_pop) AS resident_pop,
               SUM(households_no_vehicle) AS carless_households, SUM(pop_65_plus) AS pop_65_plus,
               SUM(total_pop * cfld_share) AS resident_pop_coastal_flood_exposed
        FROM corridor_tracts GROUP BY 1
    )
    SELECT corridor, t.tracts, t.resident_pop, t.carless_households, t.pop_65_plus,
           round(t.resident_pop_coastal_flood_exposed) AS resident_pop_coastal_flood_exposed,
           s.evac_buildings, s.reported_capacity, s.clean_capacity, s.clean_capacity_wheelchair_yes,
           s.clean_capacity_in_surge_area, s.medical_shelters,
           round(1000 * s.clean_capacity / t.resident_pop, 1) AS clean_per_1000_residents
    FROM t JOIN s USING (corridor) ORDER BY corridor
"""
write_csv(con, per_corridor, "corridor_capacity.csv")
corr = con.execute(per_corridor).df()
print(corr.to_string())

counties_sql = """
    SELECT t.corridor, t.county_fips, s.county_name, COUNT(*) AS tracts_in_buffer
    FROM corridor_tracts t
    LEFT JOIN (SELECT county_fips, MIN(county_name) AS county_name FROM ga_shelters GROUP BY 1) s
      USING (county_fips)
    GROUP BY ALL ORDER BY 1, 4 DESC, 2
"""
write_csv(con, counties_sql, "corridor_counties.csv")
for name, names in con.execute(f"""
    SELECT corridor, string_agg(county_name, ', ' ORDER BY tracts_in_buffer DESC, county_fips)
    FROM ({counties_sql}) GROUP BY 1 ORDER BY 1
""").fetchall():
    print(name, ":", names)

union = con.execute("""
    SELECT SUM(clean_capacity), SUM(evacuation_capacity) FILTER (WHERE is_evac),
           SUM(clean_capacity) FILTER (WHERE wheelchair = 'yes')
    FROM (SELECT DISTINCT ON (shelter_id) * FROM corridor_shelters)
""").fetchall()[0]
union_pop = one(con, "SELECT SUM(total_pop) FROM (SELECT DISTINCT ON (geo_id) * FROM corridor_tracts)")
state_clean = one(con, "SELECT SUM(clean_capacity) FROM ga_shelters")
print(f"\nany corridor: clean {union[0]:,.0f} of state {state_clean:,.0f}; reported {union[1]:,.0f}; residents {union_pop:,.0f}")

# Florida source pool: exposure-weighted counts assume carless, 65+ and
# power-dependent residents are spread evenly within each tract.
con.execute(f"""
    CREATE TABLE fl_pool AS
    WITH t AS (
        SELECT t.geo_id, t.county_fips, t.total_pop, t.households_no_vehicle, t.pop_65_plus, t.lat,
               h.cfld_share,
               CASE WHEN t.lat >= 29.5 THEN 'north FL (lat >= 29.5)'
                    WHEN t.lat >= 27.5 THEN 'central FL (27.5-29.5)'
                    ELSE 'south FL (lat < 27.5)' END AS region
        FROM fl_tracts t JOIN fl_hazard h USING (geo_id)
    ), county AS (
        SELECT county_fips, SUM(total_pop) AS county_pop,
               SUM(total_pop * cfld_share) AS county_exposed_pop
        FROM t GROUP BY 1
    ), pd AS (
        SELECT fips_code AS county_fips, power_dependent_dme
        FROM {table('FL', 'power_dependent_counties')}
    )
    SELECT t.region,
           SUM(t.total_pop * t.cfld_share) AS exposed_pop,
           SUM(t.households_no_vehicle * t.cfld_share) AS exposed_carless_households,
           SUM(t.pop_65_plus * t.cfld_share) AS exposed_pop_65_plus,
           SUM(pd.power_dependent_dme * t.total_pop * t.cfld_share / county.county_pop) AS exposed_power_dependent
    FROM t JOIN county USING (county_fips) JOIN pd USING (county_fips)
    WHERE county.county_pop > 0
    GROUP BY 1 ORDER BY 1
""")
fl_unjoined = one(con, """
    SELECT COUNT(*) FROM fl_tracts t ANTI JOIN fl_hazard h USING (geo_id)
""")
fl_pd_unjoined = one(con, f"""
    SELECT COUNT(DISTINCT county_fips) FROM fl_tracts
    WHERE county_fips NOT IN (SELECT fips_code FROM {table('FL', 'power_dependent_counties')})
""")
print(f"FL tracts without hazard row: {fl_unjoined}; FL counties without emPOWER row: {fl_pd_unjoined}")
pool = con.execute("SELECT * FROM fl_pool").df()
print(pool.to_string())

rows = []
for scen in SCENARIOS:
    ev = ASSUMPTIONS["evacuation_rate"][scen]
    su = ASSUMPTIONS["shelter_use_rate"][scen]
    for _, r in pool.iterrows():
        share = ASSUMPTIONS["fl_to_ga_share"][r.region][scen]
        k = ev * share
        rows.append({
            "scenario": scen, "region": r.region, "evacuation_rate": ev,
            "fl_to_ga_share": share, "shelter_use_rate": su,
            "people_into_ga": round(r.exposed_pop * k),
            "pop_65_plus_into_ga": round(r.exposed_pop_65_plus * k),
            "power_dependent_into_ga": round(r.exposed_power_dependent * k),
            "carless_households_upper_bound": round(r.exposed_carless_households * k),
            "shelter_seekers_into_ga": round(r.exposed_pop * k * su),
        })
with open(OUT / "fl_incoming_demand.csv", "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0]), lineterminator="\n")
    w.writeheader()
    w.writerows(rows)

ga_exposed = con.execute("""
    SELECT SUM(t.total_pop * h.cfld_share), SUM(t.households_no_vehicle * h.cfld_share),
           SUM(t.pop_65_plus * h.cfld_share)
    FROM ga_tracts t JOIN ga_hazard h USING (geo_id)
""").fetchall()[0]

south_clean = float(corr.loc[corr.corridor.str.startswith("I-75 south"), "clean_capacity"].iloc[0])
summary = {}
for scen in SCENARIOS:
    ev = ASSUMPTIONS["evacuation_rate"][scen]
    su = ASSUMPTIONS["shelter_use_rate"][scen]
    fl_people = sum(r["people_into_ga"] for r in rows if r["scenario"] == scen)
    fl_seek = sum(r["shelter_seekers_into_ga"] for r in rows if r["scenario"] == scen)
    ga_seek = ga_exposed[0] * ev * su
    summary[scen] = {
        "fl_people_into_ga": fl_people,
        "fl_pop_65_plus_into_ga": sum(r["pop_65_plus_into_ga"] for r in rows if r["scenario"] == scen),
        "fl_power_dependent_into_ga": sum(r["power_dependent_into_ga"] for r in rows if r["scenario"] == scen),
        "fl_shelter_seekers": fl_seek,
        "ga_coastal_shelter_seekers": round(ga_seek),
        "total_shelter_seekers": round(fl_seek + ga_seek),
        "share_of_any_corridor_clean_capacity": (fl_seek + ga_seek) / union[0],
        "share_of_i75_south_clean_capacity": (fl_seek + ga_seek) / south_clean,
        "share_of_state_clean_capacity": (fl_seek + ga_seek) / state_clean,
    }
    print(scen, summary[scen])

surge_i95 = con.execute("""
    SELECT COUNT(*) FILTER (WHERE is_evac AND NOT is_duplicate),
           COUNT(*) FILTER (WHERE is_evac AND NOT is_duplicate AND in_surge_slosh_area),
           COUNT(*) FILTER (WHERE is_evac AND NOT is_duplicate AND in_surge_slosh_area IS NULL),
           SUM(clean_capacity), SUM(clean_capacity) FILTER (WHERE in_surge_slosh_area)
    FROM corridor_shelters WHERE corridor LIKE 'I-95%'
""").fetchall()[0]
print("I-95 corridor EVAC buildings, in surge, surge unrecorded, clean cap, clean cap in surge:", surge_i95)

save_numbers("corridor", {
    "buffer_km": CORRIDOR_BUFFER_KM,
    "assumptions": ASSUMPTIONS,
    "per_corridor": corr.to_dict(orient="records"),
    "any_corridor_clean_capacity": union[0],
    "any_corridor_reported_capacity": union[1],
    "any_corridor_clean_capacity_wheelchair_yes": union[2],
    "any_corridor_resident_pop": union_pop,
    "state_clean_capacity": state_clean,
    "fl_pool": pool.to_dict(orient="records"),
    "fl_pool_total_exposed_pop": float(pool.exposed_pop.sum()),
    "fl_pool_total_carless_households": float(pool.exposed_carless_households.sum()),
    "fl_pool_total_65_plus": float(pool.exposed_pop_65_plus.sum()),
    "fl_pool_total_power_dependent": float(pool.exposed_power_dependent.sum()),
    "fl_tracts_without_hazard_row": fl_unjoined,
    "ga_coastal_exposed_pop": ga_exposed[0],
    "ga_coastal_exposed_carless_households": ga_exposed[1],
    "ga_coastal_exposed_65_plus": ga_exposed[2],
    "scenarios": summary,
    "i95_evac_buildings": surge_i95[0],
    "i95_evac_buildings_in_surge": surge_i95[1],
    "i95_evac_buildings_surge_unrecorded": surge_i95[2],
    "i95_clean_capacity": surge_i95[3],
    "i95_clean_capacity_in_surge": surge_i95[4],
})
