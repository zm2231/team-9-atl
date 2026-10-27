import json
import math
import os
import urllib.error
import urllib.request
from datetime import datetime, timezone
from functools import lru_cache
from typing import Any

from dotenv import load_dotenv

from .map_data import SHELTER_COLUMNS, SUSPECT_HIGH, SUSPECT_LOW, shelter_record

load_dotenv()

DEFAULT_PROJECT_ID = "qwiklabs-gcp-04-edc952746633"
DEFAULT_DATASET = "evac_prod"

# Every tool result names its dataset and table, so every figure the agent quotes can cite it
# (Constitution III).
SOURCES = {
    "shelters": "FEMA NSS registry · shelters_clean",
    "tracts": "ACS 5-yr and CDC SVI · vulnerability_tracts_clean",
    "power": "HHS emPOWER · power_dependent_counties_clean",
}

MAX_SHELTER_IDS = 25
LIVE_CHECK_STATUSES = ("exists", "renamed", "closed", "unknown")
GOOGLE_PLACES_TEXT_SEARCH_URL = "https://places.googleapis.com/v1/places:searchText"
GOOGLE_PLACES_FIELD_MASK = (
    "places.id,places.displayName,places.formattedAddress,places.location,"
    "places.businessStatus,places.currentOpeningHours.openNow,places.googleMapsUri"
)


def _dataset_name() -> str:
    return os.getenv("EVAC_DATASET", DEFAULT_DATASET)


def _project_id() -> str:
    return os.getenv("GOOGLE_CLOUD_PROJECT", DEFAULT_PROJECT_ID)


def _table_name(base_name: str) -> str:
    return f"{base_name}_clean"


def _table(base_name: str) -> str:
    return f"`{_project_id()}.{_dataset_name()}.{_table_name(base_name)}`"


def _bigquery():
    try:
        from google.cloud import bigquery
    except ImportError as exc:  # pragma: no cover - dependency is installed at runtime
        raise RuntimeError(
            "google-cloud-bigquery is required. Install dependencies from agent/requirements.txt."
        ) from exc
    return bigquery


def _bigquery_client():
    return _bigquery().Client(project=_project_id())


def _run_query(sql: str, params: list[Any] | None = None) -> list[dict[str, Any]]:
    bigquery = _bigquery()
    client = _bigquery_client()
    job_config = bigquery.QueryJobConfig()
    if params:
        job_config.query_parameters = params

    rows = client.query(sql, job_config=job_config)
    return [dict(row) for row in rows.result()]


def _scalar(name: str, type_: str, value: Any):
    return _bigquery().ScalarQueryParameter(name, type_, value)


SURGE_FALLBACK_TABLE = "shelter_surge_noaa"


@lru_cache(maxsize=1)
def _surge_fallback_exists() -> bool:
    try:
        from google.cloud.exceptions import NotFound

        _bigquery_client().get_table(
            f"{_project_id()}.{_dataset_name()}.{_table_name(SURGE_FALLBACK_TABLE)}"
        )
        return True
    except NotFound:
        return False


def _shelters_with_surge_fallback() -> str:
    """Shelters with the surge flag filled from NOAA's surge maps only where the registry is blank.

    A recorded FEMA value always wins. in_surge_source says which one was used, so every answer can
    name its source. If the fallback table has not been loaded yet, the registry is used unchanged.
    """
    shelters = f"`{_project_id()}.{_dataset_name()}.{_table_name('shelters')}`"
    if not _surge_fallback_exists():
        return f"(SELECT s.*, 'registry' AS in_surge_source, CAST(NULL AS INT64) AS surge_first_category FROM {shelters} s)"
    fallback = f"`{_project_id()}.{_dataset_name()}.{_table_name(SURGE_FALLBACK_TABLE)}`"
    return f"""(
          SELECT
            s.* REPLACE (
              COALESCE(SAFE_CAST(s.in_surge_slosh_area AS BOOL), f.in_surge_fallback) AS in_surge_slosh_area
            ),
            IF(SAFE_CAST(s.in_surge_slosh_area AS BOOL) IS NULL AND f.in_surge_fallback IS NOT NULL,
               'noaa_slosh', 'registry') AS in_surge_source,
            f.first_category AS surge_first_category
          FROM {shelters} s
          LEFT JOIN {fallback} f ON CAST(s.shelter_id AS STRING) = f.shelter_id
        )"""


def _flag_counts(shelters: list[dict[str, Any]], key: str) -> dict[str, int]:
    counts = {"yes": 0, "no": 0, "unrecorded": 0}
    for s in shelters:
        counts[s[key].lower()] += 1
    return counts


def _survey(value: Any) -> Any:
    """CDC SVI publishes -999 for missing; a missing estimate is None, never a number."""
    return None if isinstance(value, (int, float)) and value < 0 else value


def find_vulnerable_tracts(
    state: str | None = None,
    county: str | None = None,
    county_fips: str | None = None,
    limit: int = 10,
) -> dict[str, Any]:
    """Return the tracts with the most households without a vehicle, then the highest no-vehicle,
    age 65+ and disability shares. Pass county_fips (e.g. "13051") when the screen gives one.

    pct_disability is an ACS survey estimate via CDC SVI; a missing value (-999 at source) is
    returned as None. Every tract keeps its county_fips.
    """
    filters = []
    params = [_scalar("limit", "INT64", limit)]
    if state:
        filters.append("c.state = @state")
        params.append(_scalar("state", "STRING", state.upper()))
    if county:
        filters.append("LOWER(c.county) = LOWER(@county)")
        params.append(_scalar("county", "STRING", county))
    if county_fips:
        filters.append("v.county_fips = @county_fips")
        params.append(_scalar("county_fips", "STRING", county_fips))
    where_clause = "WHERE " + " AND ".join(filters) if filters else ""

    sql = f"""
        SELECT
          v.geo_id AS tract_id,
          v.county_fips,
          c.county AS county_name,
          v.households_no_vehicle,
          v.pct_no_vehicle,
          v.pct_age_65_plus,
          v.pct_disability,
          v.mobile_homes
        FROM {_table('vulnerability_tracts')} v
        JOIN {_table('power_dependent_counties')} c ON c.fips_code = v.county_fips
        {where_clause}
        ORDER BY v.households_no_vehicle DESC, v.pct_no_vehicle DESC, v.pct_age_65_plus DESC
        LIMIT @limit
    """

    tracts = [
        {**row, **{k: _survey(row.get(k)) for k in ("pct_no_vehicle", "pct_age_65_plus", "pct_disability")}}
        for row in _run_query(sql, params=params)
    ]
    return {"tracts": tracts, "source": SOURCES["tracts"]}


def assess_shelter_accessibility(
    state: str | None = "GA",
    county: str | None = None,
    county_fips: str | None = None,
    limit: int = 10,
) -> dict[str, Any]:
    """Return the shelters most in need of verification across a county or state: those with no
    wheelchair-access record first, then by recorded capacity. Pass county_fips when the screen
    gives one.

    Flags are YES / NO / UNRECORDED. UNRECORDED means nobody assessed it; it is never "no".
    Capacities below 0 or above 100,000 are flagged suspect_capacity and never rank first.
    """
    filters = ["latitude IS NOT NULL", "longitude IS NOT NULL"]
    params = [_scalar("limit", "INT64", limit)]
    if state:
        filters.append("state = @state")
        params.append(_scalar("state", "STRING", state.upper()))
    if county:
        filters.append("LOWER(county_name) = LOWER(@county)")
        params.append(_scalar("county", "STRING", county))
    if county_fips:
        filters.append("county_fips = @county_fips")
        params.append(_scalar("county_fips", "STRING", county_fips))

    sql = f"""
        SELECT {", ".join(SHELTER_COLUMNS)}
        FROM {_table('shelters')}
        WHERE {" AND ".join(filters)}
        ORDER BY
          wheelchair_accessible IS NULL DESC,
          IF(evacuation_capacity < {SUSPECT_LOW} OR evacuation_capacity > {SUSPECT_HIGH}, 0,
             evacuation_capacity) DESC,
          shelter_name ASC
        LIMIT @limit
    """

    shelters = [shelter_record(row) for row in _run_query(sql, params=params)]
    return {
        "shelters": shelters,
        "wheelchair": _flag_counts(shelters, "wheelchair_accessible"),
        "source": SOURCES["shelters"],
    }


def get_shelters(shelter_ids: list[str]) -> dict[str, Any]:
    """Return the registry records for specific shelters, in the order given (at most 25). Use it
    for the CONTEXT v1 shelter_id, or for a scenario's receiving_top / affected_shelter_ids.

    Flags are YES / NO / UNRECORDED. UNRECORDED means nobody assessed it; it is never "no".
    """
    if len(shelter_ids) > MAX_SHELTER_IDS:
        raise ValueError(f"At most {MAX_SHELTER_IDS} shelter ids per call; got {len(shelter_ids)}.")
    if not shelter_ids:
        return {"shelters": [], "source": SOURCES["shelters"]}

    sql = f"""
        SELECT {", ".join(SHELTER_COLUMNS)}
        FROM {_table('shelters')}
        WHERE CAST(shelter_id AS STRING) IN UNNEST(@ids)  -- shelter_id is INT64 in shelters_clean
          AND latitude IS NOT NULL AND longitude IS NOT NULL
    """
    params = [_bigquery().ArrayQueryParameter("ids", "STRING", [str(i) for i in shelter_ids])]
    by_id = {str(row["shelter_id"]): shelter_record(row) for row in _run_query(sql, params=params)}
    return {
        "shelters": [by_id[str(i)] for i in shelter_ids if str(i) in by_id],
        "source": SOURCES["shelters"],
    }


def _distance_meters(lat1: float, lon1: float, lat2: float, lon2: float) -> int:
    """Return straight-line distance between two coordinates."""
    earth_radius_m = 6_371_000
    lat1_rad, lat2_rad = math.radians(lat1), math.radians(lat2)
    delta_lat = math.radians(lat2 - lat1)
    delta_lon = math.radians(lon2 - lon1)
    a = (
        math.sin(delta_lat / 2) ** 2
        + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(delta_lon / 2) ** 2
    )
    return round(earth_radius_m * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a)))


def check_shelter_google_maps(shelter_id: str) -> dict[str, Any]:
    """Find nearby Google Maps place listings for one shelter and return their live listing
    status and current opening-hours status. Opening hours describe the place listing only; they
    do not establish that the shelter is accepting evacuees or has capacity.

    Google Maps data is fetched on every call and is not cached or persisted. The caller should
    verify the candidate name, address and distance before treating it as the shelter.
    """
    try:
        return _check_shelter_google_maps(shelter_id)
    except (RuntimeError, ValueError) as exc:
        return {
            "status": "error",
            "shelter_id": shelter_id,
            "message": str(exc),
            "candidates": [],
            "source": "Google Maps · Places API (live listing; check failed)",
        }


def _check_shelter_google_maps(shelter_id: str) -> dict[str, Any]:
    api_key = os.getenv("GOOGLE_MAPS_API_KEY")
    if not api_key:
        raise RuntimeError(
            "GOOGLE_MAPS_API_KEY is required for live Google Maps checks. "
            "Enable Places API (New) and set a restricted API key."
        )

    if not shelter_id:
        raise ValueError("shelter_id is required.")

    shelter_results = get_shelters([str(shelter_id)])["shelters"]
    if not shelter_results:
        raise ValueError(f"No shelter with id {shelter_id!r} was found in the configured dataset.")
    shelter = shelter_results[0]

    lat = float(shelter["lat"])
    lon = float(shelter["lon"])
    query = ", ".join(
        part
        for part in (
            shelter["name"],
            shelter["address"],
            shelter["county_name"],
            "Georgia",
        )
        if part
    )
    body = {
        "textQuery": query,
        "maxResultCount": 5,
        "locationBias": {
            "circle": {
                "center": {"latitude": lat, "longitude": lon},
                "radius": 250.0,
            }
        },
    }
    request = urllib.request.Request(
        GOOGLE_PLACES_TEXT_SEARCH_URL,
        data=json.dumps(body).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "X-Goog-Api-Key": api_key,
            "X-Goog-FieldMask": GOOGLE_PLACES_FIELD_MASK,
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            places_response = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = ""
        try:
            error_body = json.loads(exc.read().decode("utf-8"))
            detail = error_body.get("error", {}).get("message", "")
        except (json.JSONDecodeError, UnicodeDecodeError):
            pass
        message = f"Google Maps Places API returned HTTP {exc.code}"
        if detail:
            message += f": {detail}"
        raise RuntimeError(message) from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Could not reach Google Maps Places API: {exc.reason}") from exc

    candidates = []
    for place in places_response.get("places", []):
        location = place.get("location") or {}
        place_lat, place_lon = location.get("latitude"), location.get("longitude")
        hours = place.get("currentOpeningHours") or {}
        open_now = hours.get("openNow")
        candidates.append(
            {
                "place_id": place.get("id"),
                "name": (place.get("displayName") or {}).get("text"),
                "address": place.get("formattedAddress"),
                "distance_m": (
                    _distance_meters(lat, lon, place_lat, place_lon)
                    if place_lat is not None and place_lon is not None
                    else None
                ),
                "business_status": place.get("businessStatus", "UNKNOWN"),
                "open_now": open_now,
                "opening_hours_status": (
                    "open_now" if open_now is True
                    else "closed_now" if open_now is False
                    else "not_available"
                ),
                "google_maps_uri": place.get("googleMapsUri"),
            }
        )

    candidates.sort(key=lambda candidate: (
        candidate["distance_m"] is None,
        candidate["distance_m"] if candidate["distance_m"] is not None else float("inf"),
    ))
    return {
        "shelter_id": shelter["shelter_id"],
        "shelter_name": shelter["name"],
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "candidates": candidates,
        "registry_source": SOURCES["shelters"],
        "source": "Google Maps · Places API (live listing; checked just now)",
        "limitation": (
            "Google Maps business status and opening hours describe the place listing, not "
            "emergency shelter operations, available beds, or storm-time availability. "
            "Verify the candidate name, address, and distance; an ambiguous or missing match is unknown."
        ),
    }


def find_power_dependent_counties(
    state: str | None = None,
    county: str | None = None,
    county_fips: str | None = None,
    limit: int = 10,
) -> dict[str, Any]:
    """Return counties ranked by electricity-dependent medical-equipment demand.

    emPOWER is published per county: say how many, never which tract or block.
    """
    filters = []
    params = [_scalar("limit", "INT64", limit)]
    if state:
        filters.append("state = @state")
        params.append(_scalar("state", "STRING", state.upper()))
    if county:
        filters.append("LOWER(county) = LOWER(@county)")
        params.append(_scalar("county", "STRING", county))
    if county_fips:
        filters.append("fips_code = @county_fips")
        params.append(_scalar("county_fips", "STRING", county_fips))
    where_clause = "WHERE " + " AND ".join(filters) if filters else ""

    sql = f"""
        SELECT
          county,
          state,
          power_dependent_dme,
          power_dependent_devices_dme,
          facility_esrd_dialysis_any_dme,
          o2_services_any_dme,
          home_health_services_any_dme,
          athome_hospice_any_dme,
          any_healthcare_srvc_any_dme,
          fips_code AS county_fips
        FROM {_table('power_dependent_counties')}
        {where_clause}
        ORDER BY power_dependent_dme DESC
        LIMIT @limit
    """

    return {"counties": _run_query(sql, params=params), "source": SOURCES["power"]}


def identify_risky_shelters(
    state: str | None = "GA",
    county: str | None = None,
    county_fips: str | None = None,
    limit: int = 10,
) -> dict[str, Any]:
    """Identify risky shelters vs. non-risky shelters using census tract spatial mapping and FEMA NRI hurricane hazard metrics, and return capacity for each category and shelter.

    Classification criteria (from Shelter_clean.ipynb):
    - Risky ('High Exposure Risk'): in_surge_slosh_area is TRUE OR tract hurricane annual frequency (HRCN_AFREQ) > 0.1.
    - Not Risky:
      - 'Designated Resilient': Not risky AND generator_onsite is TRUE.
      - 'Standard Shelter': Not risky AND generator_onsite is not TRUE.

    in_surge_slosh_area is FEMA's value where recorded; where it is blank it comes from NOAA's
    surge maps (table shelter_surge_noaa_clean), and in_surge_source says which ("registry" or
    "noaa_slosh"). Report how many flags came from NOAA (surge_from_noaa_count).
    """
    try:
        from google.cloud import bigquery
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError(
            "google-cloud-bigquery is required. Install dependencies from agent/requirements.txt."
        ) from exc

    shelters_table = _shelters_with_surge_fallback()
    hazard_table = f"`{_project_id()}.{_dataset_name()}.{_table_name('hazard_tracts')}`"

    filters = []
    if state:
        filters.append("s.state = @state")
    if county:
        filters.append("(LOWER(s.county_name) = LOWER(@county) OR LOWER(s.county_parish) = LOWER(@county))")
    if county_fips:
        filters.append("s.county_fips = @county_fips")
    where_clause = "WHERE " + " AND ".join(filters) if filters else ""

    cte_sql = f"""
        WITH mapped_shelters AS (
          SELECT
            s.shelter_id,
            s.shelter_name,
            s.address_1,
            s.city,
            s.county_fips,
            COALESCE(s.county_name, s.county_parish) AS county_name,
            s.state,
            s.latitude,
            s.longitude,
            s.evacuation_capacity,
            s.post_impact_capacity,
            s.wheelchair_accessible,
            s.generator_onsite,
            s.in_surge_slosh_area,
            s.in_surge_source,
            s.surge_first_category,
            t.geo_id AS tract_geo_id
          FROM {shelters_table} s
          LEFT JOIN `bigquery-public-data.geo_census_tracts.us_census_tracts_national` t
            ON ST_CONTAINS(t.tract_geom, ST_GEOGPOINT(s.longitude, s.latitude))
            AND (s.county_fips IS NULL OR t.state_fips_code = SUBSTR(s.county_fips, 1, 2))
          {where_clause}
        ),
        classified_shelters AS (
          SELECT
            m.*,
            h.HRCN_AFREQ,
            h.HRCN_EXPP,
            h.HRCN_EALT,
            h.HRCN_EALP,
            CASE
              WHEN m.evacuation_capacity IS NOT NULL
                   AND (m.evacuation_capacity < 0 OR m.evacuation_capacity > 100000)
                THEN TRUE
              ELSE FALSE
            END AS has_suspect_capacity,
            CASE
              WHEN m.evacuation_capacity IS NOT NULL
                   AND m.evacuation_capacity BETWEEN 0 AND 100000
                THEN m.evacuation_capacity
              ELSE NULL
            END AS clean_evacuation_capacity,
            CASE
              WHEN COALESCE(SAFE_CAST(m.in_surge_slosh_area AS BOOL), FALSE) = TRUE
                   OR COALESCE(h.HRCN_AFREQ, 0.0) > 0.1
                THEN TRUE
              ELSE FALSE
            END AS is_risky,
            CASE
              WHEN COALESCE(SAFE_CAST(m.in_surge_slosh_area AS BOOL), FALSE) = TRUE
                   OR COALESCE(h.HRCN_AFREQ, 0.0) > 0.1
                THEN 'Risky'
              ELSE 'Not Risky'
            END AS risk_status,
            CASE
              WHEN COALESCE(SAFE_CAST(m.in_surge_slosh_area AS BOOL), FALSE) = TRUE
                   OR COALESCE(h.HRCN_AFREQ, 0.0) > 0.1
                THEN 'High Exposure Risk'
              WHEN COALESCE(SAFE_CAST(m.generator_onsite AS BOOL), FALSE) = TRUE
                THEN 'Designated Resilient'
              ELSE 'Standard Shelter'
            END AS hurricane_designation,
            CASE
              WHEN m.in_surge_slosh_area IS NULL THEN 'unrecorded'
              WHEN SAFE_CAST(m.in_surge_slosh_area AS BOOL) = TRUE THEN 'yes'
              ELSE 'no'
            END AS surge_status,
            CASE
              WHEN m.generator_onsite IS NULL THEN 'unrecorded'
              WHEN SAFE_CAST(m.generator_onsite AS BOOL) = TRUE THEN 'yes'
              ELSE 'no'
            END AS generator_status,
            CASE
              WHEN m.wheelchair_accessible IS NULL THEN 'unrecorded'
              WHEN SAFE_CAST(m.wheelchair_accessible AS BOOL) = TRUE THEN 'yes'
              ELSE 'no'
            END AS wheelchair_status
          FROM mapped_shelters m
          LEFT JOIN {hazard_table} h
            ON m.tract_geo_id = h.geo_id
        )
    """

    risk_summary_sql = f"""
        {cte_sql}
        SELECT
          risk_status,
          is_risky,
          COUNT(*) AS total_shelters,
          COUNTIF(clean_evacuation_capacity IS NOT NULL AND clean_evacuation_capacity > 0) AS shelters_with_evac_capacity,
          COUNTIF(evacuation_capacity IS NULL OR evacuation_capacity <= 0) AS shelters_missing_or_zero_capacity,
          COUNTIF(has_suspect_capacity) AS suspect_capacity_shelters,
          COALESCE(SUM(clean_evacuation_capacity), 0) AS total_evacuation_capacity,
          COALESCE(SUM(evacuation_capacity), 0) AS raw_evacuation_capacity_incl_suspect,
          ROUND(AVG(clean_evacuation_capacity), 1) AS avg_evacuation_capacity,
          COALESCE(SUM(post_impact_capacity), 0) AS total_post_impact_capacity,
          ROUND(AVG(post_impact_capacity), 1) AS avg_post_impact_capacity,
          COUNTIF(wheelchair_status = 'yes') AS wheelchair_yes_count,
          COUNTIF(wheelchair_status = 'no') AS wheelchair_no_count,
          COUNTIF(wheelchair_status = 'unrecorded') AS wheelchair_unrecorded_count,
          COUNTIF(generator_status = 'yes') AS generator_yes_count,
          COUNTIF(generator_status = 'no') AS generator_no_count,
          COUNTIF(generator_status = 'unrecorded') AS generator_unrecorded_count,
          COUNTIF(surge_status = 'yes') AS surge_yes_count,
          COUNTIF(surge_status = 'no') AS surge_no_count,
          COUNTIF(surge_status = 'unrecorded') AS surge_unrecorded_count,
          COUNTIF(in_surge_source = 'noaa_slosh') AS surge_from_noaa_count
        FROM classified_shelters
        GROUP BY risk_status, is_risky
        ORDER BY is_risky DESC
    """

    designation_summary_sql = f"""
        {cte_sql}
        SELECT
          hurricane_designation,
          is_risky,
          COUNT(*) AS total_shelters,
          COUNTIF(has_suspect_capacity) AS suspect_capacity_shelters,
          COALESCE(SUM(clean_evacuation_capacity), 0) AS total_evacuation_capacity,
          COALESCE(SUM(evacuation_capacity), 0) AS raw_evacuation_capacity_incl_suspect,
          ROUND(AVG(clean_evacuation_capacity), 1) AS avg_evacuation_capacity,
          COALESCE(SUM(post_impact_capacity), 0) AS total_post_impact_capacity,
          COUNTIF(surge_status = 'yes') AS in_surge_count,
          COUNTIF(surge_status = 'no') AS not_in_surge_count,
          COUNTIF(surge_status = 'unrecorded') AS surge_unrecorded_count,
          COUNTIF(in_surge_source = 'noaa_slosh') AS surge_from_noaa_count,
          ROUND(AVG(IF(surge_status = 'yes', 1.0, 0.0)) * 100, 2) AS in_surge_percent,
          COUNTIF(generator_status = 'yes') AS generator_count,
          COUNTIF(generator_status = 'no') AS generator_no_count,
          COUNTIF(generator_status = 'unrecorded') AS generator_unrecorded_count,
          ROUND(AVG(IF(generator_status = 'yes', 1.0, 0.0)) * 100, 2) AS generator_percent,
          COUNTIF(wheelchair_status = 'yes') AS wheelchair_yes_count,
          COUNTIF(wheelchair_status = 'no') AS wheelchair_no_count,
          COUNTIF(wheelchair_status = 'unrecorded') AS wheelchair_unrecorded_count,
          ROUND(AVG(HRCN_AFREQ), 4) AS hrcn_freq_mean,
          MIN(HRCN_AFREQ) AS hrcn_freq_min,
          MAX(HRCN_AFREQ) AS hrcn_freq_max,
          COUNTIF(HRCN_AFREQ IS NULL) AS hrcn_freq_nulls
        FROM classified_shelters
        GROUP BY hurricane_designation, is_risky
        ORDER BY is_risky DESC, hurricane_designation ASC
    """

    shelter_list_sql = f"""
        {cte_sql}
        SELECT
          shelter_id,
          shelter_name,
          address_1,
          city,
          county_fips,
          county_name,
          state,
          clean_evacuation_capacity AS evacuation_capacity,
          evacuation_capacity AS raw_evacuation_capacity,
          has_suspect_capacity,
          post_impact_capacity,
          is_risky,
          risk_status,
          hurricane_designation,
          in_surge_slosh_area,
          in_surge_source,
          surge_first_category,
          surge_status,
          generator_onsite,
          generator_status,
          wheelchair_accessible,
          wheelchair_status,
          tract_geo_id,
          ROUND(HRCN_AFREQ, 4) AS hrcn_afreq,
          HRCN_EXPP AS hrcn_expp,
          HRCN_EALT AS hrcn_ealt,
          HRCN_EALP AS hrcn_ealp,
          ST_GEOGPOINT(longitude, latitude) AS geo
        FROM classified_shelters
        WHERE is_risky = @is_risky
        ORDER BY COALESCE(clean_evacuation_capacity, -1) DESC, shelter_name ASC
        LIMIT @limit
    """

    base_params: list[Any] = []
    if state:
        base_params.append(bigquery.ScalarQueryParameter("state", "STRING", state.upper()))
    if county:
        base_params.append(bigquery.ScalarQueryParameter("county", "STRING", county))
    if county_fips:
        base_params.append(bigquery.ScalarQueryParameter("county_fips", "STRING", county_fips))

    risky_params = list(base_params) + [
        bigquery.ScalarQueryParameter("is_risky", "BOOL", True),
        bigquery.ScalarQueryParameter("limit", "INT64", limit),
    ]
    not_risky_params = list(base_params) + [
        bigquery.ScalarQueryParameter("is_risky", "BOOL", False),
        bigquery.ScalarQueryParameter("limit", "INT64", limit),
    ]

    return {
        "state": state.upper() if state else None,
        "county": county,
        "county_fips": county_fips,
        "capacity_by_risk": _run_query(risk_summary_sql, params=base_params),
        "capacity_by_designation": _run_query(designation_summary_sql, params=base_params),
        "risky_shelters": _run_query(shelter_list_sql, params=risky_params),
        "not_risky_shelters": _run_query(shelter_list_sql, params=not_risky_params),
        "fema_attribution": (
            "This product uses the Federal Emergency Management Agency's National Risk Index "
            "but is not endorsed by FEMA."
        ),
    }


def record_live_check(shelter_id: str, status: str, place_id: str | None = None) -> dict[str, Any]:
    """Report what Google Maps showed for one shelter you grounded: status is exists, renamed,
    closed or unknown. Call it after grounding a specific shelter. Nothing is stored; only the
    place_id is kept, by the frontend, for the session."""
    if status not in LIVE_CHECK_STATUSES:
        raise ValueError(f"status must be one of {', '.join(LIVE_CHECK_STATUSES)}; got {status!r}.")
    return {
        "live_check": {
            "shelter_id": str(shelter_id),
            "status": status,
            "place_id": place_id,
            "checked_at": datetime.now(timezone.utc).isoformat(),
        }
    }


def build_readiness_brief(
    state: str,
    county: str | None = None,
    county_fips: str | None = None,
    shelter_limit: int = 5,
    tract_limit: int = 5,
) -> dict[str, Any]:
    """Construct a concise readiness brief: the riskiest tracts, the shelters most in need of
    verification, medical power dependence, and a counted list of what could not be determined."""
    if not state or not (county or county_fips):
        raise ValueError("A state and either a county or a county_fips are required.")

    where = {"state": state, "county": county, "county_fips": county_fips}
    vulnerable = find_vulnerable_tracts(**where, limit=tract_limit)
    shelters = assess_shelter_accessibility(**where, limit=shelter_limit)
    power = find_power_dependent_counties(**where, limit=5)
    risk = identify_risky_shelters(**where, limit=shelter_limit)
    to_verify = shelters["shelters"]

    return {
        "state": state.upper(),
        "county": county,
        "county_fips": county_fips,
        "vulnerable_tracts": vulnerable["tracts"],
        "shelters_to_verify": to_verify,
        "medical_dependency": power["counties"],
        "shelter_risk_and_capacity": risk,
        "sources": {
            "vulnerable_tracts": vulnerable["source"],
            "shelters_to_verify": shelters["source"],
            "medical_dependency": power["source"],
        },
        "could_not_tell": {
            "wheelchair_unrecorded": _flag_counts(to_verify, "wheelchair_accessible")["unrecorded"],
            "generator_unrecorded": _flag_counts(to_verify, "generator_onsite")["unrecorded"],
            "shelters_considered": len(to_verify),
            "notes": [
                "Distances are straight-line; drive times are not included.",
                "emPOWER is county-level: it says how many, never which block.",
                "Whether a shelter will be open during a storm is not known from this data.",
            ],
        },
        "recommendation": (
            "Prioritize shelters with missing accessibility data, high surge exposure, and low verified capacity; "
            "then route vulnerable tracts to the nearest workable shelter candidates."
        ),
    }
