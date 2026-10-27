#!/usr/bin/env python3
"""Bounded, non-operational Google Maps grounding probe for Georgia shelters.

Run with the hackathon ADC environment.  The committed CSV deliberately contains
only source fields, coded conclusions, timings, token counts, and Maps place IDs.
Raw Maps prose and grounding chunks are deliberately kept in memory: Maps terms
allow retaining place IDs, not cached/exported Maps content.
"""
import argparse
import csv
import os
import time
from pathlib import Path

import duckdb
from google import genai
from google.genai import types

ROOT = Path(__file__).parent
PARQUET = Path.home() / "work/c4data/GA/shelters/data.parquet"
OUT = ROOT / "results.csv"
SUPPLEMENTAL_OUT = ROOT / "supplemental_results.csv"
MODEL = "gemini-3-flash-preview"
PROJECT = os.environ.get("GOOGLE_CLOUD_PROJECT", "qwiklabs-gcp-04-edc952746633")

SHELTER_TOOL = types.Tool(
    google_maps=types.GoogleMaps(
        grounding_types=types.GoogleMapsGroundingTypes(places=types.GoogleMapsPlaces())
    )
)
ROUTING_TOOL = types.Tool(
    google_maps=types.GoogleMaps(
        grounding_types=types.GoogleMapsGroundingTypes(
            places=types.GoogleMapsPlaces(), routing=types.GoogleMapsRouting()
        )
    )
)


def sample_rows():
    """Thirty unique rows with explicit strata; no capacity ranking is produced."""
    c = duckdb.connect()
    cols = "shelter_id, shelter_name, address_1, city, state, zip, county_name, evacuation_capacity, wheelchair_accessible, is_medical"
    selected = []
    seen = set()
    def add(stratum, where, limit, partitions=None):
        partition = f"PARTITION BY {partitions}" if partitions else ""
        sql = f"""SELECT {cols} FROM (SELECT *, row_number() OVER ({partition} ORDER BY shelter_id) rn
                   FROM read_parquet(?) WHERE {where}) WHERE rn <= ?"""
        for row in c.execute(sql, [str(PARQUET), limit]).fetchall():
            if row[0] not in seen:
                seen.add(row[0]); selected.append((*row, stratum if not partitions else f"{stratum}_{row[6]}"))
    add("large_capacity", "shelter_name IN ('Commerce High School','Commerce Primary School','Georgia World Congress Center')", 3)
    add("coastal", "county_name IN ('Chatham','Glynn','Camden','McIntosh','Liberty','Bryan')", 1, "county_name")
    add("metro", "county_name IN ('Fulton','DeKalb','Cobb','Gwinnett','Clayton')", 1, "county_name")
    add("medical", "is_medical", 4)
    add("placeholder_zero", "evacuation_capacity = 0", 2)
    add("placeholder_one_two", "evacuation_capacity IN (1,2)", 2)
    add("commerce", "upper(city) = 'COMMERCE'", 6)
    add("wheelchair_unrecorded", "wheelchair_accessible IS NULL", 30)
    if len(selected) < 30:
        raise RuntimeError(f"sample returned only {len(selected)} unique rows")
    return selected[:30]


def maps_ids(response):
    """Extract only the permitted durable identifier from Maps grounding metadata."""
    ids = []
    metadata = getattr(response.candidates[0], "grounding_metadata", None) if response.candidates else None
    for chunk in (getattr(metadata, "grounding_chunks", None) or []):
        maps = getattr(chunk, "maps", None)
        if maps and getattr(maps, "place_id", None):
            ids.append(maps.place_id)
    return ";".join(dict.fromkeys(ids))


def has_maps_source(response):
    metadata = getattr(response.candidates[0], "grounding_metadata", None) if response.candidates else None
    return any(getattr(chunk, "maps", None) is not None
               for chunk in (getattr(metadata, "grounding_chunks", None) or []))


def ask(client, prompt, tool):
    """Return transient response plus measured wall-clock and token accounting."""
    started = time.perf_counter()
    response = client.models.generate_content(
        model=MODEL, contents=prompt,
        config=types.GenerateContentConfig(tools=[tool], temperature=0),
    )
    latency_ms = round((time.perf_counter() - started) * 1000)
    usage = response.usage_metadata
    return response, latency_ms, getattr(usage, "prompt_token_count", None), getattr(usage, "candidates_token_count", None)


def classify(text, sourced):
    """Conservative coding of a one-building answer; do not infer accessibility."""
    low = (text or "").lower()
    if not sourced or not text:
        existence = "unverified"
    elif any(x in low for x in ("no longer", "permanently closed", "demolished", "does not exist")):
        existence = "gone"
    elif any(x in low for x in ("renamed", "now known as", "formerly")):
        existence = "renamed"
    elif any(x in low for x in ("exists", "is located", "is a ", "currently")):
        existence = "exists"
    else:
        existence = "unknown"
    # "definite" means a specific accessibility fact was supplied, never that entry is usable.
    access = "definite" if sourced and any(x in low for x in ("wheelchair", "accessible entrance", "accessibility", "ada ")) else "not_definite"
    return existence, access


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=30)
    parser.add_argument("--supplemental-only", action="store_true")
    args = parser.parse_args()
    client = genai.Client(vertexai=True, project=PROJECT, location="global")
    if args.supplemental_only:
        run_supplemental(client)
        return
    rows = sample_rows()[:args.limit]
    if len(rows) != args.limit:
        raise RuntimeError(f"sample returned {len(rows)}, expected {args.limit}")
    fieldnames = ["question_type", "shelter_id", "stratum", "shelter_name", "address", "county",
                  "capacity", "wheelchair_record", "medical_record", "existence_verdict",
                  "accessibility_verdict", "maps_source", "place_id", "latency_ms",
                  "prompt_tokens", "output_tokens", "error"]
    output = []
    for row in rows:
        shelter_id, name, address, city, state, zip_code, county, capacity, wheelchair, medical, stratum = row
        full_address = f"{address}, {city}, {state} {zip_code}"
        prompt = ("This is preparedness planning, not emergency response. Use Google Maps grounding "
                  f"for this one named building at this address: {name}, {full_address}. "
                  "Say whether it exists and what it is now (school, church, etc.). "
                  "Report only a specific accessibility fact if Maps supplies one; otherwise say unknown. "
                  "Do not claim current shelter operational status.")
        record = dict(question_type="single_building", shelter_id=shelter_id, stratum=stratum,
                      shelter_name=name, address=full_address, county=county, capacity=capacity,
                      wheelchair_record="unrecorded" if wheelchair is None else str(bool(wheelchair)).lower(),
                      medical_record=str(bool(medical)).lower(), existence_verdict="unverified",
                      accessibility_verdict="not_definite", maps_source="no", place_id="",
                      latency_ms="", prompt_tokens="", output_tokens="", error="")
        try:
            response, latency, pin, pout = ask(client, prompt, SHELTER_TOOL)
            sourced = has_maps_source(response)
            record.update(zip(("existence_verdict", "accessibility_verdict"), classify(response.text, sourced)))
            record.update(maps_source="yes" if sourced else "no", place_id=maps_ids(response), latency_ms=latency,
                          prompt_tokens=pin, output_tokens=pout)
        except Exception as exc:
            record["error"] = type(exc).__name__
        output.append(record)
        print(f"{shelter_id}: {record['existence_verdict']} {record['latency_ms']}ms")
    with OUT.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader(); writer.writerows(output)
    run_supplemental(client)


def run_supplemental(client):
    """One known-weak area question plus the 3×3 routing test (10 calls)."""
    fields = ["question_type", "origin", "destination", "maps_source", "place_id",
              "answer_status", "latency_ms", "prompt_tokens", "output_tokens", "error"]
    records = []
    area_prompt = ("This is preparedness planning, not emergency response. Which shelters in "
                   "Chatham County, Georgia take wheelchairs? Use Google Maps grounding. If Maps "
                   "cannot determine that from an area query, say so plainly; do not invent a list.")
    record = dict(question_type="area_accessibility", origin="Chatham County, GA", destination="",
                  maps_source="no", place_id="", answer_status="unverified", latency_ms="",
                  prompt_tokens="", output_tokens="", error="")
    try:
        response, latency, pin, pout = ask(client, area_prompt, SHELTER_TOOL)
        low = (response.text or "").lower()
        sourced = has_maps_source(response)
        record.update(maps_source="yes" if sourced else "no", place_id=maps_ids(response), latency_ms=latency,
                      prompt_tokens=pin, output_tokens=pout,
                      answer_status="not_answered" if any(x in low for x in ("cannot", "don't have", "do not have", "unable")) else "answered")
    except Exception as exc:
        record["error"] = type(exc).__name__
    records.append(record)

    # Highest-no-vehicle tract in each named coastal county, paired with three inland destinations.
    tracts = duckdb.connect().execute("""
      SELECT geo_id, county_fips, lat, lon FROM (
        SELECT *, row_number() OVER (PARTITION BY county_fips ORDER BY households_no_vehicle DESC NULLS LAST) rn
        FROM read_parquet(?) WHERE county_fips IN ('13051','13039','13127')
      ) WHERE rn=1 ORDER BY county_fips
    """, [str(Path.home() / "work/c4data/GA/vulnerability_tracts/data.parquet")]).fetchall()
    destinations = [
        ("Georgia World Congress Center", "285 Andrew Young International Blvd NW, Atlanta, GA 30313"),
        ("Dacula Park Activity Building", "2735 Old Auburn Ave, Dacula, GA 30019"),
        ("Macon Coliseum", "200 Coliseum Dr, Macon, GA 31217"),
    ]
    for geo_id, county_fips, lat, lon in tracts:
        for name, address in destinations:
            origin = f"tract {geo_id} centroid ({lat:.5f}, {lon:.5f})"
            prompt = ("This is preparedness planning, not emergency response. With Google Maps grounding "
                      f"and routing, give a driving travel time from {origin} in Georgia to {name}, {address}. "
                      "If routing cannot be produced, say so; do not substitute straight-line distance.")
            rec = dict(question_type="routing", origin=origin, destination=name, maps_source="no", place_id="",
                       answer_status="unverified", latency_ms="", prompt_tokens="", output_tokens="", error="")
            try:
                response, latency, pin, pout = ask(client, prompt, ROUTING_TOOL)
                sourced = has_maps_source(response)
                rec.update(maps_source="yes" if sourced else "no", place_id=maps_ids(response), latency_ms=latency,
                           prompt_tokens=pin, output_tokens=pout,
                           answer_status="answered" if response.text else "empty_reply")
            except Exception as exc:
                rec["error"] = type(exc).__name__
            records.append(rec)
    with SUPPLEMENTAL_OUT.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader(); writer.writerows(records)


if __name__ == "__main__":
    main()
