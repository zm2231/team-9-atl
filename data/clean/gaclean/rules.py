STATUSES = ("recorded", "unrecorded", "imputed", "assumption", "suspect", "external", "aggregated_small_home",
            "reported_lower_bound", "activated_readiness_unrecorded")
SMALL_HOME_BEDS = 6

PROJ = "'EPSG:4326', 'EPSG:32617', always_xy := true"

RULES = {
    "source_value": "Value as published by the source; no transformation.",
    "nullif_trim": "Blank or whitespace-only strings are null (unrecorded), never a value.",
    "nearest_tract_centroid": "Assigned to the tract whose 2020 centroid is nearest (straight line, UTM 17N).",
    "fips_from_geo_id": "County FIPS = first five digits of the 2020 tract geo_id.",
    "cfld_null_outside_layer": (
        "cfld_expp null means the tract is outside NRI's coastal-flood layer: cfld_expp_clean = 0, status "
        "imputed. The source column is unchanged."),
    "hrcn_ealp_percentile": (
        "Canonical hurricane exposure: percent rank (0-1) of NRI hrcn_ealp, expected annual population loss, "
        "among Georgia hazard rows. hrcn_afreq stays as published."),
    "empower_live_canonical": "HHS emPOWER REST service, fetched 2026-10-27; canonical for power dependence and dialysis.",
    "empower_suppressed_1_11": "emPOWER shows counts of 1-10 as 11: the value is the range 1-11, _low = 1, value kept as upper bound.",
    "empower_snapshot_unverified": (
        "Snapshot column facility_esrd_dialysis_any_dme (6,009 statewide) does not match the live service's "
        "dialysis count (18,026); kept as published, marked suspect, never used as dialysis patients."),
    "cfld_share": "Share of tract population in NRI's coastal-flood layer: cfld_expp_clean / population, capped at 1.",
    "coastal_flood_exposed": "True when cfld_expp_clean > 0.",
    "vulnerability_tract_join": "True when the hazard row's geo_id is in the snapshot vulnerability_tracts table.",
    "tract_hazard_join": "Hazard value of the facility's nearest tract (hazard_tracts clean columns).",
    "cms_join_ccn": "Joined to CMS Nursing Home Provider Information on CMS Certification Number (CCN).",
    "cms_occupancy": "Occupancy = CMS Average Number of Residents per Day / CMS certified beds (an average, not the daily census).",
    "medical_shelter_distance_pending": (
        "Straight-line km to the nearest snapshot shelter with is_medical = true, read-only from the raw "
        "snapshot: pending shelters_clean."),
    "zip_to_county_empower": "County from the facility ZIP via the emPOWER ZIP table's county FIPS (one county per ZIP).",
    "census_geocoder": (
        "Coordinates from the US Census Geocoder batch on the CMS address (US Government work); "
        "coordinates_confidence carries the match quality."),
    "coordinates_absent": "CMS publishes no coordinates and the geocoder found no match.",
    "cms_dialysis_stations": (
        "Dialysis centers and stations summed from the CMS Dialysis Facility listing, county from ZIP; a county "
        "with no listed center is 0, status imputed."),
    "dialysis_patients_per_station": "Live emPOWER dialysis beneficiaries / CMS stations; null where a county has no station.",
    "overture_places": (
        "Overture Maps Places release 2026-10-21.0, per-row licence in source_license (CDLA-Permissive-2.0, "
        "Apache-2.0, CC0-1.0); confidence is Overture's own. A listing, not licensure: no beds, no fleet size."),
    "gema_zone": (
        "GEMA hurricane evacuation zone (County, Zone) whose polygon contains the point (tract centroid for "
        "tracts). Null with status external: outside every zone; GEMA zones cover 11 coastal counties. Where "
        "edge slivers overlap, the earliest zone letter wins. Null with status unrecorded: no point."),
    "gamap2care_facility": "GaMap2Care facility record as published by Georgia DCH, facility fields only.",
    "small_home_aggregated": (
        f"Personal care home with {SMALL_HOME_BEDS} or fewer licensed beds, often a family home in a private "
        "residence: facid is replaced by an opaque key (pch_small_<county>_<n>, numbered by tract and beds); "
        "every other GaMap2Care field except facility_type and licensed_beds is null; latitude/longitude are "
        "its tract centroid in every output. Distances and evacuation zone use the tract centroid."),
    "gema_contraflow_point": "GEMA I-16 contraflow intersection as published.",
    "webeoc_facility_fields": (
        "GEMA WebEOC shelter feed restricted to facility and status fields; contact names, phones, fax, "
        "remarks, subscriber and editor fields are never read."),
    "nss_last_activation": (
        "FEMA NSS keeps only the most recent activation per shelter (incident_id > 0); earlier activations are "
        "overwritten. Evidence that the shelter has opened, not a count of openings."),
    "nss_no_activation": "incident_id 0 or null: NSS records no activation for this shelter (populations unused).",
    "nss_stub_activation": (
        "Activated (incident_id > 0) with no evacuation or post-impact capacity: a real activation whose "
        "readiness fields are unrecorded. Kept, never counted as extra seats."),
    "nss_population_lower_bound": (
        "NSS populations are sparse and undercounted (Helene 2024: 38 people in 19 GA shelters against Red Cross "
        "reports of 680+ in 35): a lower bound and evidence of opening, never a fill rate."),
    "nss_snapshot_join": "True when shelter_id is in the Georgia snapshot shelters table (1:1).",
    "order_time_stated": "Local time stated in the cited release, converted to UTC.",
    "order_time_day_range": "Only the date is stated: the range is 00:00 to 24:00 local that day.",
    "order_time_evening_range": "Stated as 'evening': the range is 18:00 to 24:00 local that day.",
    "order_time_absent": "No time stated for this step.",
    "order_hours_before_ga_ts_winds": (
        "Hours from the order step to Georgia tropical-storm-wind onset (NHC best-track R34 reaching Georgia, "
        "storm_lead_times; our calculation). Low and high follow the time range."),
    "oe417_filing": (
        "DOE OE-417 filing as published: utility-reported, per filing; several filings can describe one storm, "
        "so customer counts are not additive across rows."),
    "oe417_unknown": "Value published as Unknown or blank.",
    "ncei_storm_match_narrative": "NCEI event matched to a HURDAT2 storm by the storm name in its narrative and active dates.",
    "ncei_storm_match_nearest": "NCEI event assigned to the nearest active HURDAT2 storm (no name in the narrative).",
    "ncei_storm_unmatched": "No HURDAT2 storm matched.",
    "ncei_storm_aggregate": (
        "Per storm and state: NCEI Storm Events counts and sums as reported (counties from county-type rows "
        "only; forecast-zone rows carry no county)."),
}


def trim(col: str) -> str:
    return f"NULLIF(TRIM({col}), '')"


def recorded_or_unrecorded(col: str) -> str:
    return f"CASE WHEN {col} IS NULL THEN 'unrecorded' ELSE 'recorded' END"


def empower_value(col: str) -> tuple[str, str, str]:
    return (col,
            f"CASE WHEN {col} = 11 THEN 1 ELSE {col} END",
            f"CASE WHEN {col} IS NULL THEN 'unrecorded' WHEN {col} = 11 THEN 'imputed' ELSE 'recorded' END")


def tag(expr: str, name: str, status: str, rule: str) -> str:
    return f"{expr} AS {name}, {status} AS {name}_status, '{rule}' AS {name}_rule"


def point(lon: str, lat: str) -> str:
    return f"ST_Transform(ST_Point({lon}, {lat}), {PROJ})"
