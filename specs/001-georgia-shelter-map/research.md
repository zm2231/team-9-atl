# Research: Georgia Shelter Readiness Map

Phase 0 decisions for [plan.md](plan.md). Every unknown in Technical Context is resolved below.
These decisions are the decision log that Constitution §Development Workflow requires.

## R1. How the browser talks to the ADK agent

- **Decision**: Serve the agent with ADK's FastAPI app (`google.adk.cli.fast_api.get_fast_api_app`)
  on Cloud Run. The browser uses the standard ADK HTTP API:
  - `POST /apps/{app}/users/{user}/sessions` to create a session
  - `POST /run_sse` for streamed chat
  - `POST /run` for the one-shot map-data load
- **Rationale**: This is the documented ADK serving path, and the built-in web UI uses the same
  routes. Streaming over Server-Sent Events gives visible progress during the 5–8 s grounded calls
  (FR-015).
- **Alternatives considered**:
  - Agent Runtime (Vertex AI Agent Engine) query API. Rejected: it is not designed to be called from
    a browser and is awkward to put behind a user-facing IAP gate.
  - A custom chat endpoint that wraps the runner. Rejected: it duplicates what ADK already provides.
- **Verified 2026-10-27**: `google-adk==2.13.0` (pinned in `agent/requirements.txt`). Routes
  `POST /apps/{app}/users/{user}/sessions`, `POST /run` and `POST /run_sse` exist as assumed.
  Events serialize in camelCase (`invocationId`, `groundingMetadata`, `errorCode`,
  `functionResponse`). `before_agent_callback` receives a `Context` exposing `user_content`;
  returning `types.Content` ends the turn with no model call (proved by `agent/tests/test_server.py`).

## R2. Map data "through the agent" without an LLM round-trip (Clarification Q1 → C)

- **Decision**:
  - The frontend creates a **dedicated session** and sends the message `LOAD_MAP_DATA v1` to
    `POST /run`.
  - The root agent's `before_agent_callback` recognises the exact command. It calls
    `get_georgia_map_data()`, which is a BigQuery query shared with the agent's own tools, and
    returns a `types.Content` holding one text part: the JSON `MapData` payload (contracts
    §2). Returning content from `before_agent_callback` skips the model entirely.
  - Any other message goes through to the LLM as normal.
- **Rationale**:
  - It honours the "everything goes through the agent" decision: the same entry point, the same
    agent and the same tool code.
  - It is deterministic and fast, with no tokens spent re-emitting about 400 KB.
  - A separate session keeps the large payload out of the chat session's history, so it does not
    bloat later prompts.
- **Alternatives considered**:
  - The LLM calls the tool and the frontend reads the `functionResponse`. Rejected: the model may
    not call the tool, and it adds latency.
  - A separate REST route. Rejected in the Clarifications.

## R3. County boundaries

- **Decision**: Use `us-atlas@3` `counties-10m.json` (TopoJSON). A build script filters it to FIPS
  `13***` and commits the result as `frontend/src/assets/ga-counties.topo.json`. The script checks
  that exactly 159 features come out.
- **License**: us-atlas is ISC-licensed and is derived from the US Census Bureau's cartographic
  boundary files, which are public domain. Both are allowed under Constitution IV.
- **Rationale**: Outlines must render before the agent data arrives (FR-008b). The 1:10m
  generalisation is small (about 100 KB for Georgia) and plenty for a state view.
- **Alternatives considered**:
  - `bigquery-public-data.geo_us_boundaries.counties` through the agent. Rejected: no outlines
    before the load (see Complexity Tracking).
  - Census TIGER shapefiles converted by hand. Same data, more work.

## R4. Map rendering

- **Decision**: Draw the map as SVG with `d3-geo`. Use `geoMercator().fitSize()` to fit Georgia,
  with one `<path>` per county and one `<circle>` per shelter. Do not use a basemap tile layer.
- **Rationale**:
  - 159 paths and about 1,800 circles is comfortably within SVG's limits.
  - Hover highlighting is a plain CSS or state change.
  - No tile provider means no API key, no OSM ODbL tile-usage questions, and nothing to attribute
    except Google Maps in the chat.
- **Alternatives considered**:
  - MapLibre or Leaflet with tiles. Rejected: they bring license, usage-policy and key concerns, and
    a basemap adds nothing to a state-level planning view.
  - The Google Maps JavaScript API. Rejected: it needs a Maps Platform key, which is outside the
    one-API setup.

## R5. Simulation geometry and band widths

- **Decision**:
  - Use `@turf/turf` in the browser. The drawn track is captured as pointer positions,
    inverse-projected to lon/lat and thinned to points at least 5 km apart. That gives a
    `LineString`, or a `Point` for a click.
  - The band is `buffer(track, halfWidthKm)`.
  - Shelters are affected if `booleanPointInPolygon(shelter, band)`. Counties are affected if
    `booleanIntersects(county, band)`.
- **Band half-widths (illustrative; FR-017, Assumptions)**:

  | Category | Half-width | Full band |
  |---|---:|---:|
  | 1 | 30 km | 60 km |
  | 2 | 45 km | 90 km |
  | 3 | 60 km | 120 km |
  | 4 | 80 km | 160 km |
  | 5 | 100 km | 200 km |

  These are loosely scaled to typical radii of hurricane-force winds and grow with category. They
  are **not** a wind or surge model, and the UI says so (FR-019).
- **Rationale**: About 1,800 point-in-polygon tests plus 159 intersections take well under 100 ms
  in the browser, which beats SC-005's 2 s with no round-trip.
- **Alternatives considered**: computing in the agent. Rejected because it adds latency to every
  drag and cutoff change and would miss SC-005a. The agent still **receives** the computed scenario
  (R8), so both sides see the same affected set.

## R6. Receiving-list rule (Clarifications Q2, Q3)

- **Decision**:
  1. Candidates are shelters **outside** the band.
  2. For each candidate, `d` is the straight-line distance (`turf.distance`) to the center of the
     **nearest affected county**. The center is `turf.centroid` of the county polygon, precomputed
     once.
  3. Keep candidates with `d ≤ cutoff`. The cutoff defaults to 80 km and ranges from 25 to 200 km.
  4. Sort by `evacuation_capacity` descending, then by `d` ascending.
  5. Suspect-capacity shelters stay in the list, flagged. Their capacity is excluded from totals,
     and they sort as if their capacity were 0, so a data error cannot top the list.
- **Rationale**: This follows the clarified rule exactly. Accessibility never affects the order
  (FR-018c), which keeps the ranking free of the reporting bias that Constitution V warns about.
- **Alternatives considered**: polygon-to-shelter distance. It is more exact but harder to explain
  in a demo; centroids are good enough and simple to state.

## R7. Flags, sentinels and suspect values

- **Decision**:
  - BigQuery booleans already have whitespace stripped by the loader. `TRUE` becomes `"YES"`,
    `FALSE` becomes `"NO"`, and `NULL` becomes `"UNRECORDED"`. This happens in `map_data.py`, the
    single place the conversion is made.
  - `is_medical` is derived from `population_code` and is never null in the table. If
    `population_code` is null, it is reported as `"UNRECORDED"`, not `"NO"`.
  - A capacity is suspect if `evacuation_capacity < 0` or `> 100000`, the notebook's own validation
    thresholds. In Georgia these are Commerce High School (270,135) and Commerce Primary School
    (225,112).
  - SVI `-999` values become null before any aggregation.
  - A shelter whose `county_fips` is null or outside `13***`, meaning its coordinates and its
    `state` disagree, gets the data-quality flag `location_disagrees`. It is shown under its
    recorded county name.
- **Rationale**: Constitution I and VI. These guard against defects 2, 4 and 6 and the
  wrong-state-coordinates case.

## R8. Chat: sending context, highlighting what an answer refers to, and grounding display

- **Context (FR-011)**: Each chat turn's `new_message` has two parts.
  1. The user's text.
  2. A text part starting `CONTEXT v1` followed by JSON: the selected county, the selected shelter,
     and the scenario. The scenario includes the track, category, cutoff, affected county FIPS
     codes, affected shelter IDs and the top 20 receiving shelter IDs.
  The readiness agent's instruction says to treat this part as context, not as a question.
- **Highlighting answer references (FR-014)**: the frontend collects every `shelter_id` and
  `county_fips` that appears in `functionResponse` payloads during the turn, and highlights them.
  This is deterministic and needs no parsing of prose. It relies on dependency D2.
- **Live vs registry labeling (FR-013)**:
  - Text covered by a `groundingSupports[].segment` is marked **live**. Everything else is
    **registry or agent reasoning**.
  - `segment.startIndex` can be null, in which case it is treated as 0 (README note).
  - The sources (`groundingChunks[].maps` `title` and `uri`) are rendered right after each
    supported segment (FR-012).
  - The label "Google Maps" is rendered unmodified, in a `translate="no"` span.
  - Nothing from grounding is stored except `placeId`, held in memory for the session.

## R9. Access control (Clarification Q5)

- **Decision**:
  - Deploy one Cloud Run service with **IAP enabled directly on Cloud Run**
    (`gcloud run deploy --iap`).
  - Allow users by granting `roles/iap.httpsResourceAccessor` to each Google account or group. To
    add or remove a person, change IAM; no redeploy is needed (FR-024).
  - Set `--no-allow-unauthenticated` and `--min-instances=1`.
- **Rationale**: Requests are refused at the door, before any data loads or agent call (FR-023).
  Serving everything from one origin means one gate.
- **Alternatives considered**: Firebase Auth with a hand-built allow-list. Rejected: more code, and
  the list would live in app config.

## R10. Correction to the spec: disability figure is a survey estimate, not modeled

- **Finding**: `vulnerability_tracts.pct_disability` is CDC SVI `EP_DISABL`, which is an **ACS
  survey estimate**, not a CDC PLACES model output. The modeled measures in the table are
  `pct_mobility`, `pct_selfcare` and `pct_indeplive`.
- **Decision**:
  - Show `pct_disability`, labeled *"ACS survey estimate (via CDC SVI)"*.
  - Aggregate it to the county as a population-weighted mean over tracts with values, and report
    how many tracts that covers.
  - Update spec FR-003a to say "labeled with its source and estimate type" instead of "labeled as a
    modeled estimate".
- **People aggregation**:
  - `households_no_vehicle` is summed per county.
  - The 65+ share is `SUM(pop_65_plus) / SUM(total_pop)`.
  - Tract-to-county mapping is `county_fips = LEFT(geo_id, 5)`.

## Accessibility and observability (outstanding low-impact items from clarify)

- Counties are focusable with the keyboard (`tabindex`), and focus triggers the same summary as
  hover. Each summary is announced through an `aria-live` region.
- The agent service logs request latency and the event types per turn to Cloud Logging, which is
  the default on Cloud Run. Nothing user-identifying beyond what IAP already logs.
