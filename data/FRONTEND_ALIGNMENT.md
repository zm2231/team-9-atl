# Frontend alignment: what changes to show the modelled scenario

Draft, 2026-10-27. Read against `main` at 9fc9fc7 (`frontend/src`, `specs/001-georgia-shelter-map/contracts/agent-interface.md`). Framing is still being finalized; this lists the work, not a decision.

## What the frontend does today

| Piece | Code | Behaviour |
|---|---|---|
| Map data | `LOAD_MAP_DATA v1` -> `agent/readiness_agent/map_data.py` | Shelters and county summaries, no LLM call |
| Scenario | `lib/simulation.ts`, `state/scenario.tsx` | Operator drags a track and picks category 1-5. A fixed-width band (`HALF_WIDTH_KM`, 30-100 km, labelled illustrative) marks "affected" counties and shelters |
| Receiving list | `receivingList()` | Shelters outside the band within the cutoff slider, by recorded capacity, straight-line distance |
| Chat | `agentClient.ts`, `ChatPanel.tsx` | Sends `CONTEXT v1` with the scenario (track, category, affected ids, receiving top 20). Any `county_fips` / `shelter_id` in a tool's `functionResponse` is collected and highlighted |

## Where the modelled engine plugs in

| # | Change | Owner | Why |
|---|---|---|---|
| 1 | `run_scenario` reads the drawn track and category straight from the `CONTEXT v1` part of the user message (ADK `tool_context.user_content`), so the model never copies coordinates | agent (scenario package) | The operator's drawn track becomes the scenario; no LLM arithmetic |
| 2 | Drawn track -> modelled storm: points every hour at a stated forward speed, wind and size by category, inland decay; the origin is classified from where the track enters, and the result is flagged `outside_labeled_support` when the data has no comparable storm | agent | Replaces the fixed band with county outage ranges |
| 3 | `run_scenario` response: per county `county_fips`, `outage_share_p10/p50/p90`, `power_dependent_affected_p50/p90`, `dialysis_patients_affected_p50`, `peak_wind_kt`, `range_label: "empirical scenario range"`, `support` | agent | Frontend already highlights any `county_fips` in a tool response |
| 4 | New map layer: colour counties by `outage_share_p50` from the latest `run_scenario` response, with p10-p90 in the hover card and a "Modelled from 27 storms, 2018-2025" legend | frontend | Today only the band is drawn; the model's numbers need a layer |
| 5 | "Affected" becomes p50 outage >= 10% (stated) instead of band intersection; the band stays as the drawn track's visual | frontend | One definition of affected across map, list and chat |
| 6 | Receiving list: for the selected county, the top sites get a live drive time (Routes API, `kind: "live"`, never stored). On any Routes error the row keeps straight-line distance with status `straight_line` | agent + frontend | `ValueKind` already has `live`; `distance_km` gains a sibling `drive_minutes` |
| 7 | Evacuation congestion: drive time x corridor multiplier by origin (g-flow `corridor_vc.json`, low/base/high), shown as a range | agent | Routes alone is normal traffic, not an evacuation |
| 8 | Season view: per county chance of losing at least 25% of customers in a season, typical and 1-in-10 people affected, people not covered. Either an optional `season` block on each county in `map-data` (no LLM call; map_data.py owner) or the `season_county_risk` tool | lead decides | Instant county colouring without a chat turn |
| 9 | Gap sensitivity: the ranked list of unknowns by how much each changes the uncovered count, rendered in `components/summary/CouldNotTell.tsx` | frontend | That component already holds "what we could not tell you" |
| 10 | Preset tracks: buttons that draw a historical analog (Helene 2024, Michael 2018, Idalia 2023, Irma 2017, an Atlantic-coast track) from the packaged `tracks.json` | frontend | Operators rarely draw realistic tracks freehand |

## Contract changes

- `CONTEXT v1` is unchanged; the tool reads it.
- `map-data/v1` gains an optional `season` object per county only if item 8 goes that way; optional fields do not need a version bump under the contract's rule (breaking changes only).
- New tool responses carry `county_fips` everywhere, so highlighting works with no frontend change.

## Data each layer reads

| Layer | Source |
|---|---|
| Outage model, tracks, counties, receiving sites | `agent/readiness_agent/scenario/data/` (built from `evac_prod`) |
| Season table, gap sensitivity | `evac_prod.scenario_season_county`, `evac_prod.scenario_fix_ranking` |
| Drive time | Routes API, live |
| Corridor congestion | g-flow `corridor_vc.json` |
