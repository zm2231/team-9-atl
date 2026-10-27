# Implementation Plan: Georgia Shelter Readiness Map

**Branch**: `001-georgia-shelter-map` | **Date**: 2026-10-27 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/001-georgia-shelter-map/spec.md`

## Summary

A single-page React app for Georgia emergency planners. It shows:

- all 159 counties as a hoverable map, with each shelter's flags as Yes / No / Not recorded;
- people figures for each county;
- a chat panel that talks to the ADK backend agent, with Google Maps sources and live vs
  registry labels;
- a hurricane simulation. The user draws a track and picks Category 1–5. The app works out which
  counties and shelters fall in the impact band, then lists receiving shelters: those within an
  adjustable reach cutoff (starting at 80 km), sorted by capacity.

All shelter and county data comes **through the agent service**, as decided in the Clarifications.
At session start the frontend sends a fixed command to the agent. A `before_agent_callback`
recognises it and returns structured Georgia data straight from an agent tool, without calling the
LLM. Chat questions use the normal LLM path.

The frontend and the agent are served from **one Cloud Run service**. Google Identity-Aware Proxy
(IAP) sits in front of it, so only allow-listed Google accounts can get in. Allowed accounts are
managed in IAM, with no redeploy.

## Technical Context

**Language/Version**: TypeScript 5.x (frontend); Python 3.12 (agent service)
**Primary Dependencies**:
- Frontend: React 18.3, Vite 5, d3-geo and topojson-client (map rendering), @turf/turf
  (simulation geometry), us-atlas (county boundaries)
- Agent service: google-adk (FastAPI app via `get_fast_api_app`), google-cloud-bigquery
**Storage**: BigQuery `<project>.evacuation_readiness` (read-only). A static Georgia county-boundary
asset is bundled in the frontend. Nothing is persisted by this feature; sessions are in-memory.
**Testing**:
- Frontend: Vitest with React Testing Library and jsdom, plus one Playwright smoke test against a
  mocked agent (MSW)
- Agent service: pytest
**Target Platform**: Desktop browsers (latest Chrome, Edge, Firefox, Safari); Cloud Run (Linux
container)
**Project Type**: Web application, with a frontend and an agent service in one deployable unit
**Performance Goals**:
- Hover summary in under 0.5 s (SC-004)
- Map data ready in 20 s or less (SC-004a)
- Simulation update in 2 s or less (SC-005)
- Cutoff change in 1 s or less (SC-005a)
**Constraints**:
- No basemap tile service. That avoids extra licenses and keys.
- Store no Maps content except `place_id`.
- No individual-level data.
- Gemini 3.x on the agent side.
- The Cloud Run minimum instance count is set to 1, so the demo never waits for a cold start.
**Scale/Scope**: About 1,792 Georgia shelters, 159 counties and about 2,800 tracts aggregated to
counties. Fewer than 20 allow-listed users, one at a time.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| # | Gate (constitution) | Status | How this plan meets it |
|---|---|---|---|
| 1 | Three-state flags; an automated check that blank never renders as "no" (I) | ✅ PASS | The wire format uses `"YES" \| "NO" \| "UNRECORDED"`, never booleans (data-model §Flag). The agent tool maps BigQuery `NULL` to `UNRECORDED`. Vitest and pytest cases cover SC-003 |
| 2 | Maps grounding changes output; fresh and historical labeled; attribution compliant (II) | ✅ PASS (frontend part) | Grounded segments are labeled *live* from `groundingSupports`. Everything else is labeled *registry*. Sources render directly after each supported segment, with the words "Google Maps" in `translate="no"`. Making grounding **change a ranking** is the agent's job (dependency **D1**, below) |
| 3 | Every figure names its source and scale; "reachable" is a documented parameter (III) | ✅ PASS | Every displayed number carries a `source` label (data-model §SourcedValue). The reach cutoff is a visible slider that defaults to 80 km. Distances are labeled straight-line |
| 4 | No individual-level data; licenses recorded (IV) | ✅ PASS | Only aggregate tables are used, with no `org_poc_*` columns. us-atlas is ISC-licensed and derived from public-domain Census cartographic boundaries (research R3) |
| 5 | No prohibited ranking inputs; equity audit run (V) | ✅ PASS (with task) | The receiving list ranks on capacity and distance only. The audit task in quickstart §5 joins a scenario's receiving shelters to tract demographics and records the numbers |
| 6 | Validation run; WARNs reviewed; defect guards; no federal rows edited (VI) | ✅ PASS (with task) | The Georgia notebook validation run is a foundational task. Capacities below 0 or above 100,000 are flagged, not dropped. SVI `-999` values become nulls. County comes from coordinates (`county_fips`) |
| 7 | Output maps to the four Readiness Brief segments, with a counted "could not tell you" (VII) | ✅ PASS | County summary covers who cannot leave. Shelter details and the receiving list cover where they would go. Surge-zone and suspect flags cover what to fix. Unrecorded counts appear everywhere |

**Dependencies on the readiness-agent feature (not violations):**
- **D1**: the agent must actually act on what Maps grounding returns.
- **D2**: the agent's tools must return `shelter_id` values so the frontend can highlight the
  shelters an answer refers to (contracts §3).

**Post-design re-check (after Phase 1)**: all gates still pass. The design added nothing that weakens
a gate. The only addition is the bundled county asset, justified under Complexity Tracking.

## Project Structure

### Documentation (this feature)

```text
specs/001-georgia-shelter-map/
├── plan.md              # This file
├── research.md          # Phase 0: decisions R1–R10
├── data-model.md        # Phase 1: entities and the wire format
├── quickstart.md        # Phase 1: run locally, deploy, validate, equity audit
├── contracts/
│   ├── agent-interface.md      # How the frontend talks to the agent service
│   └── map-data.schema.json    # JSON Schema for the session-start map data payload
└── tasks.md             # Phase 2 (/speckit-tasks; not created here)
```

### Source Code (repository root)

```text
agent/
├── readiness_agent/            # ADK app (the root LLM agent itself belongs to the readiness-agent feature)
│   ├── __init__.py
│   ├── agent.py                # root_agent; registers before_agent_callback
│   ├── map_data.py             # get_georgia_map_data(): BigQuery → MapData payload (this feature)
│   └── callbacks.py            # handles the LOAD_MAP_DATA command and skips the LLM (this feature)
├── server.py                   # get_fast_api_app() and a mount of frontend/dist at "/"
├── requirements.txt
└── tests/
    ├── test_map_data.py        # tri-state, suspect capacity, -999, county aggregation
    ├── test_callbacks.py       # the command bypasses the LLM; other messages pass through
    └── test_server.py          # LOAD_MAP_DATA over the real ADK /run route

Dockerfile                      # repo root, so `gcloud run deploy --source .` finds it (H3)

frontend/
├── index.html
├── package.json
├── vite.config.ts              # dev proxy: /apps, /run, /run_sse → localhost:8000
├── scripts/
│   └── build-ga-counties.mjs   # us-atlas → src/assets/ga-counties.topo.json (FIPS 13***)
├── src/
│   ├── main.tsx
│   ├── App.tsx                 # layout: map | side panel (summary / scenario) | chat
│   ├── state/                  # useReducer store: mapData, hover, selection, scenario, chat
│   ├── lib/
│   │   ├── agentClient.ts      # session create, loadMapData, streamChat (SSE over fetch)
│   │   ├── flags.ts            # Flag type, label/color, counting helpers
│   │   ├── simulation.ts       # band per category, affected set, receiving list
│   │   └── grounding.ts        # split answer text into live and registry segments with sources
│   ├── components/
│   │   ├── map/                # CountyLayer, ShelterLayer, TrackDrawer, Legend
│   │   ├── summary/            # CountySummary, ShelterDetails
│   │   ├── scenario/           # CategoryPicker, ReachSlider, AffectedSummary, ReceivingList
│   │   └── chat/               # ChatPanel, AnswerView, SourceList
│   └── assets/ga-counties.topo.json
└── tests/
    ├── unit/                   # flags, simulation, grounding, aggregation display
    ├── component/              # CountySummary, ReceivingList, AnswerView
    └── e2e/smoke.spec.ts       # Playwright with MSW-mocked agent
```

**Structure Decision**: a web application split into `frontend/` and `agent/`. They are deployed as
**one Cloud Run service**: FastAPI serves the ADK API and the built frontend from the same origin.
That means one IAP gate, no CORS, and one URL for judges. The empty `agent/` directory is where the
challenge expects the agent to live. This feature adds only the map-data tool, the command
callback and the server wrapper. The LLM agent's reasoning, tools and grounding behaviour belong to
the separate readiness-agent feature.

## Complexity Tracking

| Item | Why needed | Simpler alternative rejected because |
|---|---|---|
| County boundaries bundled as a static asset instead of fetched from BigQuery through the agent | FR-008b requires county outlines to render **before** and **without** the agent's data load. That cannot happen if the outlines come from the agent | Fetching `geo_us_boundaries.counties` through the agent would leave a blank map during the slowest step of the demo and on any agent failure. The asset is public-domain geometry, not challenge data, so "data lives in BigQuery" still holds for every figure |
| A command handled in `before_agent_callback` | The Clarifications require map data to go through the agent. An LLM round-trip that re-emits about 400 KB of shelter data would be slow, costly and could change from run to run | A separate REST endpoint was rejected in the Clarifications (Q1 → C). Having the LLM call a tool and echo its output would not reliably meet SC-004a or the faithfulness rules in Principle VI |
