# Google Maps grounding probe — Georgia shelters

This is a non-operational preparedness-planning experiment, run 2026-10-27 on
Vertex AI `global` with `gemini-3-flash-preview`. It made **55** grounded calls
in total (including setup/rechecks), below the 80-call cap. The reproducible
batch is 40 calls: 30 one-building questions, one area question, and 9 routes.

## Result

One named building plus its street address is a useful runtime verification
check. It returned a Maps source for **30/30** sampled shelters and coded 28 as
existing, one as gone (the Lovejoy Middle School row), and one as renamed (the
Southern Polytechnic State University row). That is enough to make Maps a
gating input for a pre-season verification queue: `gone` should be removed
from candidate destinations, and `renamed` should be shown as a record to
reconcile. It is not an operational-status check.

Maps accessibility facts are **not** proof that a shelter is usable by a person
using a wheelchair. The building prompt got a specific Maps accessibility fact
for 30/30, including rows where FEMA had wheelchair unrecorded, but this probe
codes it only `definite`, never “verified accessible.” It does not establish a
usable entrance, operating hours, or shelter admission.

The county-wide accessibility question reproduced the expected failure. The
one response had Maps sources but answered with non-registry housing/support
organizations rather than the FEMA Chatham shelter roster. Therefore an agent
must obtain candidate shelters and their three-state accessibility record from
our data, then ground each candidate by name and address; it must not use an
area question to answer who “takes wheelchairs.”

Routing worked for **9/9** coastal-tract-centroid → inland-shelter prompts.
The metadata has a Maps `route` chunk (distance/duration/directions) but no
place ID for a route. Retain neither route content nor polyline; obtain it live
and render required Maps attribution next to the result.

## Measured response rates and latency

| Question | Calls | Maps-source rate | Usable response rate | Mean / median latency |
|---|---:|---:|---:|---:|
| One named shelter at address | 30 | 30/30 (100%) | 30/30 (100%) | 3.23 s / 2.69 s |
| Chatham wheelchair area query | 1 | 1/1 (100%) | 0/1 for the requested shelter-registry question | 15.05 s |
| Routing (3 coastal centroids × 3 inland shelters) | 9 | 9/9 (100%) | 9/9 (100%) | 3.04 s / 2.80 s |

The observed one-building range was 2.03–5.78 s; the routing range was
2.54–4.79 s. Every batch call completed without an API error.

The SDK returned prompt/output token usage, not billing cost. The building
calls averaged 87 prompt + 66 output tokens; routes averaged 100 + 79. At
typical Flash token pricing this is on the order of **10^-4–10^-3 USD of model
tokens per call**, before any Maps-grounding request charge. Do not represent
that as an all-in cost: check the current Vertex/Maps price sheet and billing
export before production budgeting.

## Sample design

`probe_maps.py` selects 30 unique rows from the local GA snapshot. It includes
the three large-capacity records (including both Commerce anomalies and GWCC),
one each from Chatham, Glynn, Camden, McIntosh, Liberty, and Bryan; one each
from Fulton, DeKalb, Cobb, Gwinnett, and Clayton; four medical sites; capacity
0 and capacity 1–2 placeholders; Commerce rows; and wheelchair-unrecorded
rows. It is a presence/identity experiment, not capacity math. In particular,
the Commerce capacities remain source values and are never used to rank.

The query uses snapshot county names only to *sample* the requested strata. It
does not join or roll up county data: production joins must use `county_fips`.

## What the API returned

For a single building, `candidate.grounding_metadata.grounding_chunks[*].maps`
was populated with a Maps source and usually a `place_id`. The committed
`results.csv` keeps only source identifiers allowed by Maps terms, plus source
snapshot fields, short derived labels, timing, and token counts. It never
contains raw model prose, Maps URLs, place details, ratings, hours, route
duration/distance, or polylines. `supplemental_results.csv` deliberately has
blank `place_id` values on routes because route chunks do not provide one.

Raw answers and grounding metadata were inspected transiently while coding and
are intentionally not written to disk or committed. Re-ground at runtime and
display Google Maps attribution immediately adjacent to content it supports.

## Working Vertex google-genai pattern

`global` is required for the Gemini 3.x call. The essential configuration,
implemented in [`probe_maps.py`](probe_maps.py), is:

```python
from google import genai
from google.genai import types

client = genai.Client(vertexai=True, project=PROJECT, location="global")
tool = types.Tool(google_maps=types.GoogleMaps(
    grounding_types=types.GoogleMapsGroundingTypes(
        places=types.GoogleMapsPlaces(),
        routing=types.GoogleMapsRouting(),  # omit for building-only calls
    )
))
response = client.models.generate_content(
    model="gemini-3-flash-preview",
    contents=prompt,
    config=types.GenerateContentConfig(tools=[tool], temperature=0),
)
```

Do not treat a nonempty answer as grounded. Check for a Maps object in
`grounding_chunks`; routes have a Maps object even when it has no `place_id`.
The script demonstrates both checks and keeps route metadata transient.

## Reproduce

```bash
source ~/work/google-hackathon/hackathon-env.sh
uv run --with duckdb --with google-genai python probes/maps/probe_maps.py
```

Use `--supplemental-only` to rerun just the area/routing set. The source is
`~/work/c4data/GA/shelters/data.parquet`; results are written alongside the
script. Do not run this in a live emergency workflow.
