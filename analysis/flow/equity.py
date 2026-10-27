from common import HERE, OUT, connect, one, save_numbers, write_csv

RACE = HERE / "data" / "ga_tract_race_acs2022.csv"
GROUPS = ("white_nh", "black_nh", "hispanic", "asian_nh")

con = connect()
con.execute(f"CREATE TABLE race AS SELECT * FROM read_csv('{RACE}', types={{'geo_id': 'VARCHAR'}})")
assert one(con, "SELECT COUNT(*) FROM race r SEMI JOIN ga_tracts t USING (geo_id)") == 2796

con.execute(f"CREATE TABLE coastal AS SELECT * FROM read_csv('{OUT / 'coastal_tracts.csv'}', types={{'geo_id': 'VARCHAR'}})")
lists = {
    "state": "SELECT geo_id FROM ga_tracts",
    "coastal_flood_tracts": "SELECT geo_id FROM coastal",
    "top20_carless_on_flood_layer": "SELECT geo_id FROM coastal ORDER BY carless_hh_on_flood_layer DESC, geo_id LIMIT 20",
    "top20_carless_raw_count": "SELECT geo_id FROM coastal ORDER BY households_no_vehicle DESC, geo_id LIMIT 20",
}

parts = []
for name, sql in lists.items():
    shares = ", ".join(f"round(SUM(r.{g}) / SUM(r.total), 3) AS {g}" for g in GROUPS)
    parts.append(f"""
        SELECT '{name}' AS tract_set, COUNT(*) AS tracts, SUM(r.total) AS pop, {shares},
               round(1 - ({' + '.join(f'SUM(r.{g})' for g in GROUPS)}) / SUM(r.total), 3) AS other,
               SUM(t.households_no_vehicle) AS carless_households
        FROM ({sql}) l JOIN race r USING (geo_id) JOIN ga_tracts t USING (geo_id)
    """)
audit_sql = " UNION ALL ".join(parts)
write_csv(con, audit_sql, "equity_audit.csv")
audit = con.execute(audit_sql).df()
print(audit.to_string())

overlap = one(con, f"""
    SELECT COUNT(*) FROM ({lists['top20_carless_on_flood_layer']}) a
    SEMI JOIN ({lists['top20_carless_raw_count']}) b USING (geo_id)
""")
print("overlap between the two top-20 lists:", overlap)

save_numbers("equity", {
    "source": "ACS 2022 5-year B03002, Georgia tracts; audit only, never a model input",
    "sets": audit.set_index("tract_set").to_dict(orient="index"),
    "top20_overlap": overlap,
})
