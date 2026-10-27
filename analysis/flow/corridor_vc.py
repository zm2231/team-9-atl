import csv
import json

from common import OUT, save_numbers

CASES = ("low", "base", "high")
ORIGINS = {"gulf": "c_fl_west_coast", "florida_peninsula": "b_ne_florida", "atlantic_ga": "a_ga_coast"}

# Every parameter below is an assumption. The low case pairs the low scenario volume with the
# capacity-friendly end of each bracket, the high case the reverse.
PERSONS_PER_VEHICLE = {"low": 2.5, "base": 2.0, "high": 1.6}
PEAK_HOUR_SHARE = {"low": 0.06, "base": 0.09, "high": 0.12}
LANE_FLOW_VPH = {"low": 1800, "base": 1500, "high": 1200}
CORRIDORS = {
    "I-75 S": {"route_source": "GDOT SR 401 (FL line to Macon)", "lanes": 3, "contraflow_lanes": 0},
    "I-16": {"route_source": "GDOT SR 404 + GDOT contraflow route", "lanes": 2, "contraflow_lanes": 2},
    "I-95": {"route_source": "TIGER I-95 (not in the GDOT layer)", "lanes": 3, "contraflow_lanes": 0},
}
# Share of each origin county's leaving vehicles on each corridor's busiest Georgia segment.
# A vehicle that takes I-95 north to I-16 west counts on both.
PATHS = {
    "13051": {"I-16": 1.0}, "13029": {"I-16": 1.0},
    "13179": {"I-16": 0.5, "I-95": 0.5},
    "13191": {"I-16": 0.4, "I-95": 0.4}, "13127": {"I-16": 0.4, "I-95": 0.4},
    "13039": {"I-16": 0.3, "I-95": 0.3},
    "FL_b_ne_florida": {"I-95": 0.4, "I-16": 0.4, "I-75 S": 0.4},
    "FL_c_fl_west_coast": {"I-75 S": 1.0},
}

assumptions = json.loads((OUT / "numbers.json").read_text())["scenarios"]["assumptions"]
with open(OUT / "scenario_origins.csv") as f:
    origins = list(csv.DictReader(f))

rows, detail = [], []
for origin, scenario in ORIGINS.items():
    counties = [r for r in origins if r["scenario"] == scenario]
    assert counties, scenario
    for case in CASES:
        ev = assumptions["evacuation_rate"][case]
        people = dict.fromkeys(CORRIDORS, 0.0)
        for r in counties:
            st = r["state"]
            # Georgia residents who leave by car use Georgia roads wherever they are headed;
            # out-of-state residents do only if Georgia is their destination.
            share = 1.0 if st == "GA" else assumptions["to_ga"][scenario][st][case]
            by_car = (float(r["pop"]) - float(r["carless_people"])) * ev * share
            paths = PATHS[r["county_fips"]] if st == "GA" else PATHS[f"{st}_{scenario}"]
            for corridor, s in paths.items():
                people[corridor] += by_car * s
        for corridor, c in CORRIDORS.items():
            vehicles = people[corridor] / PERSONS_PER_VEHICLE[case]
            peak = vehicles * PEAK_HOUR_SHARE[case]
            capacity = (c["lanes"] + c["contraflow_lanes"]) * LANE_FLOW_VPH[case]
            rows.append({"corridor": corridor, "origin": origin, "case": case,
                         "volume_to_capacity": round(peak / capacity, 3),
                         "route_source": c["route_source"], "status": "assumption"})
            detail.append({**rows[-1], "scenario": scenario, "evacuating_vehicles": round(vehicles),
                           "peak_hour_vehicles": round(peak), "capacity_vph": capacity,
                           "contraflow": c["contraflow_lanes"] > 0})

(OUT / "corridor_vc.json").write_text(json.dumps(rows, indent=2) + "\n")
for d in detail:
    print(d)
save_numbers("corridor_vc", {
    "origins": ORIGINS,
    "assumptions": {"persons_per_vehicle": PERSONS_PER_VEHICLE, "peak_hour_share": PEAK_HOUR_SHARE,
                    "lane_flow_vph": LANE_FLOW_VPH, "corridors": CORRIDORS, "paths": PATHS},
    "rows": detail,
})
