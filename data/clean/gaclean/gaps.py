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
    o = {g: v["not_permanently_closed"] for g, v in nums["overture_places"].items()}
    sa = nums["shelter_activation_history"]
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
         "size": {"overture_home_health": o["home_health"], "overture_hospice": o["hospice"]},
         "affects": "medically dependent population at home",
         "fill": "external_source", "fill_status": "partially_filled",
         "detail": "overture_places (Overture Maps, per-row licence kept): listings only, no caseload or service area. "
                   "CMS Home Health and Hospice provider files (US Government work) are the next source; not fetched."},
        {"id": "nemt_ambulance_inventory", "table": None, "gap": "NEMT, para-transit and ambulance fleet",
         "size": {"overture_ambulance_ems": o["ambulance_ems"], "overture_medical_transport": o["medical_transport"]},
         "affects": "transport capacity for medically dependent evacuees",
         "fill": "assumption_range", "fill_status": "partially_filled",
         "detail": "overture_places locates operators, never fleet size or wheelchair vans; NPPES type-2 provider "
                   "records (US Government work) are another operator list, not fetched. Fleet is a labelled "
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
                   "an input for the teammate shelters table. Contact, phone and remarks fields are never read. "
                   "FEMA OpenShelters total_population is a live query only."},
        {"id": "tracts_without_hazard_row", "table": "hazard_tracts", "gap": "2020 tracts with no NRI hazard row",
         "size": {"tracts": h["vulnerability_tracts_without_hazard_row"],
                  "population": h["vulnerability_tracts_without_hazard_row_population"]},
         "affects": "nothing while population is 0 (water tracts)",
         "fill": "never_filled", "detail": "Asserted at build: the build fails if any populated tract lacks a row."},
        {"id": "shelter_opening_evidence", "table": "shelter_activation_history",
         "gap": "Which shelters actually open in an incident",
         "size": {"ga_shelters": sa["GA"]["shelters"], "ga_activated": sa["GA"]["activated"],
                  "ga_never_activated": sa["ga_never_activated"]},
         "affects": "shelter-opening probability per shelter",
         "fill": "external_source", "fill_status": "partially_filled",
         "detail": "FEMA NSS last-activation layer (US Government work), 1:1 on shelter_id. Only the most recent "
                   "activation per shelter survives, so earlier openings are lost."},
        {"id": "shelter_fill_history", "table": "shelter_activation_history",
         "gap": "Shelter fill and occupancy in past storms",
         "size": {"ga_activated_with_population": sa["GA"]["activated_with_population"],
                  "ga_population_reported": sa["GA"]["population_reported"]},
         "affects": "shelter demand against capacity",
         "fill": "assumption_range",
         "detail": "No shelter-level history. NSS populations are a lower bound (status reported_lower_bound). "
                   "Anchor a labelled range on Red Cross statewide peaks once their releases are cited; live "
                   "occupancy only from the GEMA feed during an incident."},
        {"id": "stub_shelter_activations", "table": "shelter_activation_history",
         "gap": "Activated shelters with no readiness data",
         "size": {"ga_activated_readiness_unrecorded": sa["GA"]["activated_readiness_unrecorded"],
                  "in_incidents_155_26_and_193_25": sa["ga_stub_incident_rows"]},
         "affects": "shelter capacity and opening evidence",
         "fill": "external_source", "fill_status": "filled",
         "detail": "Real activations: status activated_readiness_unrecorded, kept as opening evidence and never "
                   "counted as extra seats."},
        {"id": "shelter_hurricane_suitability", "table": None,
         "gap": "Whether a shelter is rated for hurricane use",
         "size": {"ga_pre_landfall_shelter_blank_or_unk": sa["ga_blank_pre_landfall_shelter"],
                  "ga_never_activated": sa["ga_never_activated"],
                  "ga_evac_or_both_in_surge_area": sa["ga_evac_or_both_in_surge"]},
         "affects": "which shelters can be used before landfall",
         "fill": "maps_verify",
         "detail": "No ARC 4496 or FEMA P-361 rating in any source. Fill: NSS hurricane-activation evidence "
                   "(proven, excluded, unknown) plus Maps verification of the largest unknowns; the shelters "
                   "table itself is owned by a teammate."},
        {"id": "warning_lead_time", "table": None, "gap": "Warning lead time by storm origin",
         "size": {},
         "affects": "evacuation window per scenario",
         "fill": "external_source", "fill_status": "filled",
         "detail": "analysis/flow storm library: first NWS VTEC watch and warning for any Georgia zone to Georgia "
                   "tropical-storm-wind onset (NHC best track), our calculation."},
        {"id": "evac_order_timing", "table": "evac_orders", "gap": "Evacuation order timing and areas",
         "size": {"orders": nums["evac_orders"]["orders"]},
         "affects": "departure start time per county",
         "fill": "external_source", "fill_status": "partially_filled",
         "detail": "OpenFEMA IPAWS holds no Georgia coastal evacuation order before 2022 (none for Matthew, Irma, "
                   "Michael or Dorian). evac_orders takes Matthew, Irma and Dorian from cited governor releases. "
                   "Gulf storms (Michael, Helene, Milton, Isaias 2026): no coastal mandatory order found, unverified."},
        {"id": "hurricane_evacuation_clearance_times", "table": None,
         "gap": "Official clearance times from the Hurricane Evacuation Study",
         "size": {},
         "affects": "how long the coast needs to clear",
         "fill": "never_filled",
         "detail": "Published only in HURREVAC, which is restricted to emergency managers."},
        {"id": "power_outage_extent", "table": "outage_events", "gap": "Power outage extent and duration per storm",
         "size": {"oe417_filings": nums["outage_events"]["filings"], "oe417_ga_filings": nums["outage_events"]["ga_filings"]},
         "affects": "when power-dependent residents become an emergency",
         "fill": "external_source", "fill_status": "filled",
         "detail": "County storm outages from EAGLE-I (ORNL, CC BY 4.0) as published by the grid analysis "
                   "(analysis/grid county_storm_outages), used by the storm library; DOE OE-417 filings in "
                   "outage_events. The trigger is county outage share, not coastal zone."},
        {"id": "departure_timing", "table": None, "gap": "Departure-timing curve", "size": {},
         "affects": "congestion and clearance time", "fill": "assumption_range",
         "detail": "Not in hand: a labelled curve from cited departure-timing studies (Matthew)."},
        {"id": "florida_inflow", "table": None, "gap": "Florida inflow competing for Georgia capacity", "size": {},
         "affects": "Georgia medical seats, dialysis chairs and I-75/I-16 load in Gulf and NE Florida scenarios",
         "fill": "external_source", "fill_status": "filled",
         "detail": "Florida snapshot tables; analysis/flow scenarios (b) and (c)."},
        {"id": "dialysis_schedule_cohort", "table": None, "gap": "Dialysis schedule cohort (MWF or TTS)", "size": {},
         "affects": "which patients miss a session for a given landfall day", "fill": "assumption_range",
         "detail": "Not published: half and half, swept 40-60%."},
        {"id": "staff_availability", "table": None,
         "gap": "Staff available at dialysis centers, nursing homes and shelters", "size": {},
         "affects": "usable capacity when staff evacuate too", "fill": "assumption_range",
         "detail": "Not published: a labelled range correlated with storm category."},
        {"id": "nursing_home_evacuation_mortality", "table": None,
         "gap": "Evacuation mortality risk for nursing-home residents", "size": {},
         "affects": "evacuate or shelter in place per facility", "fill": "assumption_range",
         "detail": "Range from cited post-Rita and Gustav cohort studies."},
        {"id": "shelter_failure", "table": None, "gap": "Shelter failure in the storm (power, roof, cooling, water)",
         "size": {}, "affects": "post-impact capacity", "fill": "assumption_range",
         "detail": "Florida after-action documents give failure modes, not rates: a labelled range."},
        {"id": "duration_clocks", "table": None,
         "gap": "Time to harm: portable oxygen, dialysis interval, shelter stay", "size": {},
         "affects": "time-to-harm per person type", "fill": "assumption_range",
         "detail": "Clinical norms, cited."},
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
