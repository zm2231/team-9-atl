"""Georgia map data for the frontend's session-start load (contracts/map-data.schema.json).

The only place BigQuery booleans become flags. TRUE -> YES, FALSE -> NO, NULL -> UNRECORDED:
a blank record is "nobody wrote it down", never "no" (Constitution I).
"""

from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Any, Iterable, Mapping

SCHEMA = "map-data/v1"
STATE = "GA"
STATE_FIPS = "13"

# The notebook's own validation thresholds (research R7).
SUSPECT_LOW, SUSPECT_HIGH = 0, 100_000

SRC_SHELTERS = "FEMA NSS registry · shelters"
SRC_ACS = "ACS 5-yr · vulnerability_tracts"
SRC_SVI = "ACS survey estimate via CDC SVI · vulnerability_tracts"

FLAG_KEYS = ("wheelchair_accessible", "generator_onsite", "is_medical", "in_surge_slosh_area")
COUNTY_FLAG_NAMES = {
    "wheelchair_accessible": "wheelchair",
    "generator_onsite": "generator",
    "is_medical": "medical",
    "in_surge_slosh_area": "in_surge",
}

Row = Mapping[str, Any]


def to_flag(value: Any) -> str:
    if value is True:
        return "YES"
    if value is False:
        return "NO"
    return "UNRECORDED"


def _clean_survey(value: Any) -> float | None:
    """SVI publishes -999 for missing; any negative survey value is missing, not zero."""
    if value is None:
        return None
    value = float(value)
    return None if value < 0 else value


def _is_suspect(capacity: Any) -> bool:
    return capacity is not None and (capacity < SUSPECT_LOW or capacity > SUSPECT_HIGH)


def _sourced(value: float | None, source: str, kind: str, coverage: str | None = None) -> dict:
    out = {"value": value, "source": source, "kind": kind}
    if coverage is not None:
        out["coverage"] = coverage
    return out


def _shelter(row: Row) -> dict:
    fips = row.get("county_fips")
    quality = []
    if _is_suspect(row.get("evacuation_capacity")):
        quality.append("suspect_capacity")
    if not fips or not str(fips).startswith(STATE_FIPS):
        quality.append("location_disagrees")
    address = ", ".join(str(p) for p in (row.get("address_1"), row.get("city"), row.get("zip")) if p)
    return {
        "shelter_id": str(row["shelter_id"]),
        "name": row.get("shelter_name") or "(unnamed)",
        "address": address,
        "county_fips": str(fips) if fips else None,
        "county_name": row.get("county_name") or row.get("county_parish") or "Unknown",
        "lat": float(row["latitude"]),
        "lon": float(row["longitude"]),
        "evacuation_capacity": row.get("evacuation_capacity"),
        "post_impact_capacity": row.get("post_impact_capacity"),
        "usage": row.get("usage"),
        "wheelchair_accessible": to_flag(row.get("wheelchair_accessible")),
        "generator_onsite": to_flag(row.get("generator_onsite")),
        # is_medical is derived from population_code; with no population_code we do not know.
        "is_medical": "UNRECORDED" if row.get("population_code") is None
        else to_flag(row.get("is_medical")),
        "in_surge_slosh_area": to_flag(row.get("in_surge_slosh_area")),
        "quality_flags": quality,
    }


def _flag_counts(shelters: list[dict], key: str) -> dict:
    counts = {"yes": 0, "no": 0, "unrecorded": 0}
    for s in shelters:
        counts[{"YES": "yes", "NO": "no", "UNRECORDED": "unrecorded"}[s[key]]] += 1
    return counts


def _people(tracts: list[Row]) -> dict:
    no_vehicle = [_clean_survey(t.get("households_no_vehicle")) for t in tracts]
    pop = [_clean_survey(t.get("total_pop")) for t in tracts]
    age = [_clean_survey(t.get("pop_65_plus")) for t in tracts]
    dis = [_clean_survey(t.get("pct_disability")) for t in tracts]
    n = len(tracts)

    nv_known = [v for v in no_vehicle if v is not None]
    age_pairs = [(a, p) for a, p in zip(age, pop) if a is not None and p]
    dis_pairs = [(d, p) for d, p in zip(dis, pop) if d is not None and p]

    share_65 = (sum(a for a, _ in age_pairs) / sum(p for _, p in age_pairs)) if age_pairs else None
    share_dis = (
        sum(d * p for d, p in dis_pairs) / sum(p for _, p in dis_pairs) / 100.0 if dis_pairs else None
    )
    return {
        "households_no_vehicle": _sourced(
            sum(nv_known) if nv_known else None, SRC_ACS, "survey", f"{len(nv_known)} of {n} tracts"
        ),
        "share_65_plus": _sourced(share_65, SRC_ACS, "survey", f"{len(age_pairs)} of {n} tracts"),
        "share_disability": _sourced(share_dis, SRC_SVI, "survey", f"{len(dis_pairs)} of {n} tracts"),
    }


def build_payload(
    shelter_rows: Iterable[Row],
    tract_rows: Iterable[Row],
    counties: Iterable[tuple[str, str]],
    generated_at: datetime | None = None,
) -> dict:
    """Pure transform from query rows to the map-data/v1 payload. Never edits or drops a row."""
    shelters = [_shelter(r) for r in shelter_rows]
    tracts_by_county: dict[str, list[Row]] = {}
    for t in tract_rows:
        tracts_by_county.setdefault(str(t["geo_id"])[:5], []).append(t)

    county_records = []
    for fips, name in sorted(counties):
        mine = [s for s in shelters if s["county_fips"] == fips]
        suspect = [s for s in mine if "suspect_capacity" in s["quality_flags"]]
        caps = [s["evacuation_capacity"] for s in mine if s["evacuation_capacity"] is not None]
        caps_clean = [
            s["evacuation_capacity"] for s in mine
            if s["evacuation_capacity"] is not None and s not in suspect
        ]
        record = {
            "county_fips": fips,
            "name": name,
            "shelter_count": len(mine),
            "capacity_total": _sourced(float(sum(caps_clean)), SRC_SHELTERS, "registry"),
            "capacity_total_incl_suspect": _sourced(float(sum(caps)), SRC_SHELTERS, "registry"),
            "capacity_excluded": [{"shelter_id": s["shelter_id"], "name": s["name"]} for s in suspect],
        }
        for key, out_name in COUNTY_FLAG_NAMES.items():
            record[out_name] = _flag_counts(mine, key)
        record.update(_people(tracts_by_county.get(fips, [])))
        county_records.append(record)

    return {
        "schema": SCHEMA,
        "state": STATE,
        "generated_at": (generated_at or datetime.now(timezone.utc)).isoformat(),
        "shelters": shelters,
        "counties": county_records,
        "notes": _notes(shelters),
    }


def _notes(shelters: list[dict]) -> list[str]:
    n = len(shelters)
    wc = sum(1 for s in shelters if s["wheelchair_accessible"] == "UNRECORDED")
    gen = sum(1 for s in shelters if s["generator_onsite"] == "UNRECORDED")
    suspect = [s["name"] for s in shelters if "suspect_capacity" in s["quality_flags"]]
    misplaced = sum(1 for s in shelters if "location_disagrees" in s["quality_flags"])
    notes = [
        f"{wc} of {n} shelters have no wheelchair-access record.",
        f"{gen} of {n} shelters have no generator record.",
    ]
    if suspect:
        notes.append(
            f"{len(suspect)} shelter(s) have a suspect capacity and are excluded from totals: "
            + ", ".join(suspect) + "."
        )
    if misplaced:
        notes.append(f"{misplaced} shelter(s) have coordinates that disagree with their recorded state.")
    notes += [
        "Distances are straight-line; drive times are not included.",
        "Whether a shelter is open during a real storm is not known from this data.",
    ]
    return notes


# --- BigQuery access -----------------------------------------------------------------------------

SHELTERS_SQL = """
SELECT shelter_id, shelter_name, address_1, city, zip, county_fips, county_name, county_parish,
       latitude, longitude, evacuation_capacity, post_impact_capacity, usage,
       wheelchair_accessible, generator_onsite, is_medical, population_code, in_surge_slosh_area
FROM `{project}.{dataset}.shelters`
WHERE state = 'GA' AND latitude IS NOT NULL AND longitude IS NOT NULL
"""

TRACTS_SQL = """
SELECT geo_id, total_pop, households_no_vehicle, pop_65_plus, pct_disability
FROM `{project}.{dataset}.vulnerability_tracts`
WHERE geo_id LIKE '13%'
"""

COUNTIES_SQL = """
SELECT geo_id AS county_fips, county_name
FROM `bigquery-public-data.geo_us_boundaries.counties`
WHERE state_fips_code = '13'
"""

_CACHE: dict[str, tuple[float, dict]] = {}
_CACHE_SECONDS = 600


def get_georgia_map_data(project: str, dataset: str = "evacuation_readiness") -> dict:
    """Query BigQuery and return the map-data/v1 payload, cached in-process for 10 minutes."""
    key = f"{project}.{dataset}"
    hit = _CACHE.get(key)
    if hit and time.monotonic() - hit[0] < _CACHE_SECONDS:
        return hit[1]

    from google.cloud import bigquery  # imported lazily so tests need no credentials

    client = bigquery.Client(project=project)

    def rows(sql: str) -> list[dict]:
        return [dict(r) for r in client.query(sql.format(project=project, dataset=dataset)).result()]

    payload = build_payload(
        rows(SHELTERS_SQL),
        rows(TRACTS_SQL),
        [(r["county_fips"], r["county_name"]) for r in rows(COUNTIES_SQL)],
    )
    _CACHE[key] = (time.monotonic(), payload)
    return payload
