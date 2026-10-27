import json
from pathlib import Path

FILL_METHODS = ("maps_verify", "assumption_range", "external_source", "never_filled")
FILL_STATES = ("open", "partially_filled", "filled")
ROOT = Path(__file__).resolve().parents[1]


def measure(nums: dict) -> list[dict]:
    p = nums["power_dependent_counties"]
    c = nums["care_facilities"]
    d = nums["dialysis_centers"]
    h = nums["hazard_tracts"]
    o = {g: v["not_permanently_closed"] for g, v in nums["overture_places_held"].items()}
    al = nums["assisted_living"]
    return [
        {"id": "nursing_home_occupancy", "table": "care_facilities", "gap": "Residents to move per nursing home",
         "size": {"facilities": nums["rows"]["care_facilities"], "occupancy_unrecorded": c["occupancy_unrecorded"],
                  "avg_residents_per_day": c["avg_residents_per_day"], "cms_certified_beds": c["cms_certified_beds"],
                  "occupancy_pct": 100 * c["occupancy_rate"]},
         "affects": "medical transport demand from care facilities",
         "fill": "external_source", "fill_status": "partially_filled",
         "detail": "CMS 'Average Number of Residents per Day', an average not the census on the day. Daily census "
                   "(CMS Payroll Based Journal) is not loaded."},
        {"id": "non_ambulatory_share", "table": "care_facilities", "gap": "Residents needing a stretcher or wheelchair vehicle",
         "size": {"facilities": nums["rows"]["care_facilities"]},
         "affects": "vehicle type mix for care-facility evacuation",
         "fill": "assumption_range",
         "detail": "CMS MDS 3.0 frequency report is state-level only (not loaded): apply as a labelled range per home."},
        {"id": "nursing_home_generators_plans", "table": "care_facilities",
         "gap": "Generator, fuel and evacuation-agreement status of each nursing home",
         "size": {"facilities": nums["rows"]["care_facilities"]},
         "affects": "shelter-in-place vs evacuate decision per facility",
         "fill": "never_filled",
         "detail": "Not in CMS provider files. Ask the facility or the state survey agency."},
        {"id": "alf_pch_missing", "table": "assisted_living",
         "gap": "Assisted living communities and personal care homes are not in care_facilities",
         "size": {"assisted_living_communities": al["ASSISTED LIVING COMMUNITY"]["facilities"],
                  "assisted_living_beds": al["ASSISTED LIVING COMMUNITY"]["licensed_beds"],
                  "personal_care_homes": al["PERSONAL CARE HOME"]["facilities"],
                  "personal_care_home_beds": al["PERSONAL CARE HOME"]["licensed_beds"],
                  "small_homes_aggregated": al["PERSONAL CARE HOME"]["small_homes_aggregated"]},
         "affects": "medically dependent population outside nursing homes",
         "fill": "external_source", "fill_status": "filled",
         "detail": "assisted_living from GaMap2Care (Georgia DCH), facility fields only. Homes with 6 or fewer beds "
                   "carry no name or address and sit at their tract centroid. Licensed beds, not residents."},
        {"id": "home_health_hospice_listings", "table": None,
         "gap": "Home health and hospice agencies serving people at home",
         "size": {"overture_home_health_held": o["home_health"], "overture_hospice_held": o["hospice"]},
         "affects": "medically dependent population at home",
         "fill": "external_source",
         "detail": "Overture listings are built locally but held (out/held/, not committed) pending the licence "
                   "ruling on CDLA-Permissive and Apache rows."},
        {"id": "nemt_ambulance_inventory", "table": None, "gap": "NEMT, para-transit and ambulance fleet",
         "size": {"overture_ambulance_ems_held": o["ambulance_ems"], "overture_medical_transport_held": o["medical_transport"]},
         "affects": "transport capacity for medically dependent evacuees",
         "fill": "assumption_range",
         "detail": "Overture locates operators (held), never fleet size or wheelchair vans. Fleet is a labelled "
                   "low/base/high input until a county or state inventory is supplied."},
        {"id": "medical_shelter_distance", "table": "care_facilities",
         "gap": "Distance from each facility to a usable medical-needs shelter",
         "size": {"median_km_pending": c["median_km_nearest_medical_shelter_pending"]},
         "affects": "medical sheltering access per facility",
         "fill": "external_source",
         "detail": "Computed read-only from the raw snapshot shelters (is_medical): pending teammate shelters_clean."},
        {"id": "dialysis_coordinates", "table": "dialysis_centers", "gap": "Dialysis centers without coordinates",
         "size": {**{f"geocode_{k}": v for k, v in d["coordinates_confidence"].items()},
                  "stations_without_coordinates": d["stations_without_coordinates"]},
         "affects": "distance from dialysis patients to an operating center; center flood exposure",
         "fill": "external_source", "fill_status": "partially_filled",
         "detail": "Census Geocoder (US Government work), match quality in coordinates_confidence. Unmatched: Maps "
                   "place_id lookup at runtime."},
        {"id": "empower_suppressed", "table": "power_dependent_counties", "gap": "emPOWER counts 1-10 published as 11",
         "size": {f"counties_{k}": v for k, v in p["counties_suppressed_1_11"].items() if v},
         "affects": "dialysis, oxygen and home-health demand in small counties",
         "fill": "assumption_range",
         "detail": "Carried as the range 1-11 (<field>_live_low = 1, value = 11, status imputed)."},
        {"id": "empower_snapshot_mismatch", "table": "power_dependent_counties",
         "gap": "Snapshot dialysis-like column disagrees with the live service",
         "size": {"snapshot_facility_esrd_dialysis_any_dme": p["facility_esrd_dialysis_any_dme_snapshot"],
                  "live_dialysis": p["dialysis_live"],
                  "snapshot_power_dependent": p["power_dependent_snapshot"],
                  "live_power_dependent": p["power_dependent_live"]},
         "affects": "dialysis and power-dependent demand",
         "fill": "external_source", "fill_status": "filled",
         "detail": "Live emPOWER is canonical and carried beside the snapshot; the snapshot column is marked suspect."},
        {"id": "power_dependence_granularity", "table": "power_dependent_counties",
         "gap": "Power dependence is county-level",
         "size": {"counties": nums["rows"]["power_dependent_counties"]},
         "affects": "where in a county power-dependent residents live",
         "fill": "external_source",
         "detail": "emPOWER ZIP counts exist (extdata/emPOWER/empower_ga_zip.csv), not joined. Never assign to a block."},
        {"id": "surge_exposure", "table": "hazard_tracts", "gap": "Storm-surge inundation by category",
         "size": {"tracts_in_nri_coastal_flood_layer": h["coastal_flood_exposed"]},
         "affects": "which facilities and tracts flood in a given storm",
         "fill": "external_source",
         "detail": "NRI coastal flood is an annualised composite, and GEMA evacuation zones (now on hazard_tracts, "
                   "care_facilities and assisted_living) are planning zones, not inundation. NOAA NHC SLOSH MOM "
                   "rasters (public domain) are documented in extdata/slosh, not clipped."},
        {"id": "live_shelter_status", "table": "gema_shelter_feed", "gap": "Which shelters are open, full or closed now",
         "size": {"rows": nums["gema_shelter_feed"]["rows"], "fields_kept": nums["gema_shelter_feed"]["fields_kept"]},
         "affects": "operational shelter capacity during an event",
         "fill": "external_source",
         "detail": "GEMA WebEOC feed had no rows when fetched; gema_shelter_feed is its facility and status schema, "
                   "an input for the teammate shelters table. Contact, phone and remarks fields are never read."},
        {"id": "tracts_without_hazard_row", "table": "hazard_tracts", "gap": "2020 tracts with no NRI hazard row",
         "size": {"tracts": h["vulnerability_tracts_without_hazard_row"],
                  "population": h["vulnerability_tracts_without_hazard_row_population"]},
         "affects": "nothing while population is 0 (water tracts)",
         "fill": "never_filled", "detail": "Asserted at build: the build fails if any populated tract lacks a row."},
        {"id": "evacuation_route_geometry", "table": "contraflow_intersections", "gap": "Official evacuation route geometry",
         "size": {"contraflow_intersections": nums["contraflow_intersections"]["points"]},
         "affects": "which roads evacuees use",
         "fill": "external_source", "fill_status": "filled",
         "detail": "GDOT hurricane evacuation routes and contraflow route are the corridor layer in analysis/flow "
                   "(cleared with attribution); TIGER/Line covers I-75 north of Macon and I-20, which GDOT's layer "
                   "omits. GEMA I-16 contraflow intersections are in contraflow_intersections."},
    ]


def write_gaps(nums: dict, root: Path = ROOT) -> list[dict]:
    gaps = measure(nums)
    for g in gaps:
        g.setdefault("fill_status", "open")
        assert g["fill"] in FILL_METHODS and g["fill_status"] in FILL_STATES, g
    (root / "out" / "gaps.json").write_text(json.dumps(gaps, indent=2, default=float) + "\n")
    lines = ["# Gap register: care facilities, hazard tracts, power-dependent counties", "",
             "Generated by `python -m gaclean.build` (`out/gaps.json`). Fill methods: `maps_verify` (grounded live, only",
             "place_ids stored), `assumption_range` (a labelled low/base/high simulator input), `external_source` (a",
             "named source that clears the licence bar), `never_filled`. Shelter and vulnerability-tract gaps belong",
             "to the teammates' tables.", "",
             "| Table | Gap | Size | Affects | Fill | State | How |", "|---|---|---|---|---|---|---|"]
    for g in gaps:
        size = "; ".join(f"{k.replace('_', ' ')} {v:,.1f}".replace(".0 ", " ").removesuffix(".0")
                         if isinstance(v, float) else f"{k.replace('_', ' ')} {v:,}" for k, v in g["size"].items()) or "n/a"
        lines.append(f"| {g['table'] or 'n/a'} | {g['gap']} | {size} | {g['affects']} | `{g['fill']}` | "
                     f"{g['fill_status']} | {g['detail']} |")
    (root / "GAPS.md").write_text("\n".join(lines) + "\n")
    return gaps
