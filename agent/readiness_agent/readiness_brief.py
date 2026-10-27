"""The readiness brief in the challenge's four segments, computed for a whole county: who cannot
leave, where they would go, what to fix before the season, and what could not be determined."""

from concurrent.futures import ThreadPoolExecutor
from typing import Any

from . import evacuation_tools as tools
from .map_data import shelter_record, to_flag

REACH_KM = 16.0
REACH_BASIS = (
    "Assumption: reachable means within 16 km (10 miles) straight-line of the tract centre, a "
    "county transport run for households without a vehicle. Drive times come from Routes in "
    "run_scenario."
)
FACILITY_COUNTY_BASIS = "Facility county assigned from the nearest tract centre (straight-line)."
PRE_LANDFALL = ("EVAC", "BOTH")
FACILITIES_SOURCE = "CMS nursing homes · care_facilities_clean"
FLOOD_SOURCE = "FEMA NRI coastal flood, joined by tract · care_facilities_flow_staging"
MODELED_SOURCE = "CDC PLACES modeled estimates · vulnerability_tracts_clean"


def build_readiness_brief(county_fips: str, tract_limit: int = 8, destination_limit: int = 10) -> dict[str, Any]:
    """Build the county readiness brief.

    who_cannot_leave: tracts ranked by households without a vehicle, each with its reasons, and
    the county's nursing homes, each saying whether its tract is coastal-flood exposed.
    where_they_would_go: pre-landfall shelters within reach of the
    ranked tracts, with capacity, recorded flags and surge exposure; confirm each one live with
    Google Maps before relying on it. what_to_fix: tracts with no recorded wheelchair-accessible
    shelter within reach (each says whether none is in reach, the ones in reach are unrecorded, or
    they are recorded not accessible), nursing homes with no recorded generator in a county with power-dependent
    residents, nursing homes in a coastal-flood-exposed tract, and shelters in a surge or flood zone. could_not_tell: counts over the whole county.
    """
    if not county_fips:
        raise ValueError("county_fips is required.")

    with ThreadPoolExecutor(max_workers=5) as pool:
        tracts_job = pool.submit(_county_tracts, county_fips)
        reach_job = pool.submit(_tract_reach, county_fips)
        shelters_job = pool.submit(_county_shelters, county_fips)
        facilities_job = pool.submit(_county_facilities, county_fips)
        power_job = pool.submit(tools.find_power_dependent_counties, county_fips=county_fips, limit=1)
        tracts = tracts_job.result()
        ranked = sorted(tracts, key=lambda t: (t.get("households_no_vehicle") or 0), reverse=True)
        top = ranked[:tract_limit]
        destinations_job = pool.submit(_destinations, [t["geo_id"] for t in top], destination_limit)
        reach = {r["geo_id"]: r for r in reach_job.result()}
        shelters = [shelter_record(r) | {"in_100_yr_floodplain": r.get("in_100_yr_floodplain")}
                    for r in shelters_job.result()]
        facilities = facilities_job.result()
        power = power_job.result()["counties"]
        destinations = destinations_job.result()
    power_dependent = _count(power[0].get("power_dependent_dme")) if power else None

    no_accessible = [
        _accessibility_gap(t, reach.get(t["geo_id"], {}))
        for t in ranked
        if (t.get("households_no_vehicle") or 0) > 0
        and not reach.get(t["geo_id"], {}).get("wheelchair_yes_within_reach")
    ]
    flood = [
        {"shelter_id": s["shelter_id"], "name": s["name"], "usage": s.get("usage"),
         "evacuation_capacity": s.get("evacuation_capacity"), "in_surge": s["in_surge_slosh_area"],
         "in_surge_source": s.get("in_surge_source"),
         "in_100_yr_floodplain": s.get("in_100_yr_floodplain")}
        for s in shelters
        if s["in_surge_slosh_area"] == "YES" or s.get("in_100_yr_floodplain") is True
    ]
    facility_entries = [_facility_entry(f) for f in facilities]

    return {
        "county_fips": county_fips,
        "who_cannot_leave": {
            "tracts": [_tract_entry(t) for t in top],
            "facilities": facility_entries,
            "power_dependent_residents": power_dependent,
            "sources": [tools.SOURCES["tracts"], MODELED_SOURCE, FACILITIES_SOURCE, FLOOD_SOURCE,
                        tools.SOURCES["power"]],
            "basis": FACILITY_COUNTY_BASIS,
        },
        "where_they_would_go": {
            "destinations": destinations,
            "live_check": "Not yet verified: ground each destination with Google Maps before relying on it.",
            "reachable": REACH_BASIS,
            "source": tools.SOURCES["shelters"],
        },
        "what_to_fix": {
            "tracts_without_recorded_accessible_shelter_in_reach": no_accessible,
            "facilities_without_recorded_generator": {
                "count": len(facilities),
                "power_dependent_residents_in_county": power_dependent,
                "note": "No source records nursing-home generators; every facility listed above is unknown.",
            },
            "facilities_in_coastal_flood_tract": {
                "facilities": [{"ccn": f["ccn"], "name": f["name"], "certified_beds": f["certified_beds"]}
                               for f in facility_entries if f["coastal_flood_exposed"] == "YES"],
                "note": "Exposure of the facility's census tract, not of the building; not a storm forecast.",
                "source": FLOOD_SOURCE,
            },
            "shelters_in_surge_or_flood_zone": flood,
            "reachable": REACH_BASIS,
        },
        "could_not_tell": _could_not_tell(shelters, facilities),
    }


def _accessibility_gap(t: dict[str, Any], reach: dict[str, Any]) -> dict[str, Any]:
    within = reach.get("within_reach") or 0
    unrecorded = reach.get("wheelchair_unrecorded_within_reach") or 0
    if not within:
        gap = "no pre-landfall shelter within reach"
    elif unrecorded:
        gap = "shelters within reach, but none recorded accessible: unknown, not no"
    else:
        gap = "every shelter within reach is recorded not accessible"
    return {"geo_id": t["geo_id"], "households_no_vehicle": _count(t.get("households_no_vehicle")),
            "gap": gap, "shelters_within_reach": within,
            "wheelchair_no_within_reach": reach.get("wheelchair_no_within_reach") or 0,
            "wheelchair_unrecorded_within_reach": unrecorded,
            "nearest_shelter_km": reach.get("nearest_km")}


def _facility_entry(f: dict[str, Any]) -> dict[str, Any]:
    beds = _count(f["beds"])
    flood = to_flag(f.get("coastal_flood_exposed"))
    reasons = [f"{beds or 'unknown number of'} certified nursing-home beds"]
    if flood == "YES":
        reasons.append("in a coastal-flood-exposed tract")
    reasons.append("generator, fuel and evacuation-agreement status not recorded in any source")
    return {"ccn": f["ccn"], "name": f["name"], "city": f["city"], "certified_beds": beds,
            "coastal_flood_exposed": flood, "reasons": reasons}


def _count(value: Any) -> int | None:
    return None if value is None else round(float(value))


def _tract_entry(t: dict[str, Any]) -> dict[str, Any]:
    no_vehicle, older, group = (_count(t.get(k)) for k in ("households_no_vehicle", "pop_65_plus", "group_quarters_pop"))
    reasons = []
    if no_vehicle:
        reasons.append(f"{no_vehicle} households without a vehicle")
    if t.get("pct_disability") is not None:
        reasons.append(f"{t['pct_disability']:.0f}% with a disability")
    if t.get("pct_mobility") is not None:
        reasons.append(f"{t['pct_mobility']:.0f}% with a mobility difficulty (modeled)")
    if t.get("pct_selfcare") is not None:
        reasons.append(f"{t['pct_selfcare']:.0f}% with a self-care difficulty (modeled)")
    if older:
        reasons.append(f"{older} residents aged 65+")
    if group:
        reasons.append(f"{group} in group quarters")
    return {"geo_id": t["geo_id"], "total_pop": _count(t.get("total_pop")),
            "households_no_vehicle": no_vehicle, "reasons": reasons}


def _could_not_tell(shelters: list[dict[str, Any]], facilities: list[dict[str, Any]]) -> dict[str, Any]:
    def unrecorded(flag: str) -> int:
        return sum(1 for s in shelters if s[flag] == "UNRECORDED")

    return {
        "shelters_in_county": len(shelters),
        "wheelchair_unrecorded": unrecorded("wheelchair_accessible"),
        "generator_unrecorded": unrecorded("generator_onsite"),
        "medical_unrecorded": unrecorded("is_medical"),
        "surge_unrecorded": unrecorded("in_surge_slosh_area"),
        "hurricane_rating_unrecorded": len(shelters),
        "nursing_home_generator_unrecorded": len(facilities),
        "nursing_home_coastal_flood_unrecorded": sum(1 for f in facilities if f.get("coastal_flood_exposed") is None),
        "notes": [
            "No source records whether a shelter building is rated for hurricane winds.",
            "No source records nursing-home generators, fuel or evacuation agreements.",
            "Ambulance and wheelchair-van fleet sizes are not recorded.",
            "Official clearance times are published only in HURREVAC, which is restricted.",
            "emPOWER is county-level: it says how many, never which block.",
            "Whether a shelter will open during a storm is not known from this data.",
        ],
    }


def _county_tracts(county_fips: str) -> list[dict[str, Any]]:
    sql = f"""
        SELECT geo_id, total_pop, households_no_vehicle, pop_65_plus, group_quarters_pop,
               pct_disability, pct_mobility, pct_selfcare, lat, lon
        FROM {tools._table('vulnerability_tracts')}
        WHERE county_fips = @county_fips
    """
    rows = tools._run_query(sql, [tools._scalar("county_fips", "STRING", county_fips)])
    return [r | {k: tools._survey(r.get(k)) for k in ("pct_disability", "pct_mobility", "pct_selfcare")}
            for r in rows]


def _tract_reach(county_fips: str) -> list[dict[str, Any]]:
    sql = f"""
        WITH t AS (
          SELECT geo_id, ST_GEOGPOINT(lon, lat) AS pt
          FROM {tools._table('vulnerability_tracts')}
          WHERE county_fips = @county_fips AND lat IS NOT NULL
        ),
        s AS (
          SELECT ST_GEOGPOINT(longitude, latitude) AS pt, wheelchair_accessible
          FROM {tools._table('shelters')}
          WHERE latitude IS NOT NULL AND usage IN UNNEST(@usage)
        )
        SELECT t.geo_id,
               COUNTIF(ST_DWITHIN(t.pt, s.pt, @reach_m)) AS within_reach,
               COUNTIF(ST_DWITHIN(t.pt, s.pt, @reach_m) AND s.wheelchair_accessible IS TRUE)
                 AS wheelchair_yes_within_reach,
               COUNTIF(ST_DWITHIN(t.pt, s.pt, @reach_m) AND s.wheelchair_accessible IS FALSE)
                 AS wheelchair_no_within_reach,
               COUNTIF(ST_DWITHIN(t.pt, s.pt, @reach_m) AND s.wheelchair_accessible IS NULL)
                 AS wheelchair_unrecorded_within_reach,
               ROUND(MIN(ST_DISTANCE(t.pt, s.pt)) / 1000, 1) AS nearest_km
        FROM t CROSS JOIN s
        GROUP BY t.geo_id
    """
    return tools._run_query(sql, [
        tools._scalar("county_fips", "STRING", county_fips),
        tools._scalar("reach_m", "FLOAT64", REACH_KM * 1000),
        tools._bigquery().ArrayQueryParameter("usage", "STRING", list(PRE_LANDFALL)),
    ])


def _destinations(geo_ids: list[str], limit: int) -> list[dict[str, Any]]:
    if not geo_ids:
        return []
    sql = f"""
        WITH t AS (
          SELECT geo_id, ST_GEOGPOINT(lon, lat) AS pt
          FROM {tools._table('vulnerability_tracts')}
          WHERE geo_id IN UNNEST(@geo_ids) AND lat IS NOT NULL
        )
        SELECT {", ".join(f"s.{c}" for c in _SHELTER_GROUP)},
               ARRAY_AGG(t.geo_id ORDER BY t.geo_id) AS serves_tracts,
               ROUND(MIN(ST_DISTANCE(t.pt, ST_GEOGPOINT(s.longitude, s.latitude))) / 1000, 1) AS nearest_km
        FROM {tools._table('shelters')} s
        JOIN t ON ST_DWITHIN(t.pt, ST_GEOGPOINT(s.longitude, s.latitude), @reach_m)
        WHERE s.usage IN UNNEST(@usage)
        GROUP BY {", ".join(f"s.{c}" for c in _SHELTER_GROUP)}
        ORDER BY ARRAY_LENGTH(serves_tracts) DESC, s.evacuation_capacity DESC
        LIMIT @limit
    """
    rows = tools._run_query(sql, [
        tools._bigquery().ArrayQueryParameter("geo_ids", "STRING", geo_ids),
        tools._scalar("reach_m", "FLOAT64", REACH_KM * 1000),
        tools._bigquery().ArrayQueryParameter("usage", "STRING", list(PRE_LANDFALL)),
        tools._scalar("limit", "INT64", limit),
    ])
    return [shelter_record(r) | {"serves_tracts": list(r["serves_tracts"]), "nearest_km": r["nearest_km"]}
            for r in rows]


_SHELTER_GROUP = (
    "shelter_id", "shelter_name", "address_1", "city", "zip", "county_fips", "county_name",
    "county_parish", "latitude", "longitude", "evacuation_capacity", "post_impact_capacity",
    "usage", "wheelchair_accessible", "generator_onsite", "is_medical", "population_code",
    "in_surge_slosh_area", "in_100_yr_floodplain",
)


def _county_shelters(county_fips: str) -> list[dict[str, Any]]:
    sql = f"""
        SELECT * FROM {tools._table('shelters')}
        WHERE county_fips = @county_fips
    """
    return tools._run_query(sql, [tools._scalar("county_fips", "STRING", county_fips)])


def _county_facilities(county_fips: str) -> list[dict[str, Any]]:
    sql = f"""
        WITH f0 AS (
          SELECT cms_certification_number_ccn AS ccn, provider_name AS name, citytown AS city,
                 number_of_certified_beds AS beds, ST_GEOGPOINT(longitude, latitude) AS pt
          FROM {tools._table('care_facilities')}
          WHERE latitude IS NOT NULL
        ),
        f AS (
          SELECT f0.*, x.coastal_flood_exposed
          FROM f0
          LEFT JOIN `{tools._project_id()}.{tools._dataset_name()}.care_facilities_flow_staging` x
            ON x.cms_certification_number_ccn = f0.ccn
        ),
        nearest AS (
          SELECT f.ccn, f.name, f.city, f.beds, f.coastal_flood_exposed,
                 ARRAY_AGG(t.county_fips ORDER BY ST_DISTANCE(f.pt, ST_GEOGPOINT(t.lon, t.lat)) LIMIT 1)[OFFSET(0)]
                   AS county_fips
          FROM f CROSS JOIN {tools._table('vulnerability_tracts')} t
          WHERE t.lat IS NOT NULL
          GROUP BY f.ccn, f.name, f.city, f.beds, f.coastal_flood_exposed
        )
        SELECT ccn, name, city, beds, coastal_flood_exposed FROM nearest
        WHERE county_fips = @county_fips
        ORDER BY beds DESC
    """
    return tools._run_query(sql, [tools._scalar("county_fips", "STRING", county_fips)])
