# Scenarios: what changes in the app

Read against `main` at e5e6640. Contract for the tool itself: [contracts/run-scenario.md](contracts/run-scenario.md).

## 1. Agent API (this PR)

| Change | Where | Notes |
|---|---|---|
| New tool `run_scenario` | `agent/readiness_agent/scenario_tools.py` | Reads the drawn track and category from `CONTEXT v1`; or matches past storms to `lat`, `lon`, `heading_deg`, `date`, `intensity_kt`. Returns `affected_county_fips`, `affected_shelter_ids`, `receiving_top` (same names as the `CONTEXT v1` scenario), plus `scenario`, `statewide`, `counties`, `receiving`, `source` |
| New tool `season_county_risk` | same | `{counties: [...], source}` from `evac_prod.scenario_season_county` |
| New tool `gap_sensitivity` | same | `{gaps: [...], source}` from `evac_prod.scenario_fix_ranking` |
| Scenario package | `agent/readiness_agent/scenario/` | numpy only; model, tracks and site data under `data/` (under 5 MB) |
| Instructions | `agent.py` | The screen's band and receiving list stay "illustrative"; `run_scenario` figures are "modelled ranges"; the agent names which one it quotes |
| Dependency | `agent/requirements.txt` | `numpy` pinned |

No change to `LOAD_MAP_DATA v1`, `map-data/v1`, `CONTEXT v1` or the existing tools.

## 2. Frontend (UI team)

Every new tool result carries `county_fips` and `shelter_id`, so highlighting works today with no change. To show the modelled numbers:

| # | Change | Reads | Where it fits |
|---|---|---|---|
| F1 | Keep the latest `run_scenario` result from the chat stream (`functionResponse.name == "run_scenario"`), like `record_live_check` | `functionResponse.response` | `ChatPanel.tsx`, `store.tsx` |
| F2 | County fill by `counties[].outage_share.p50`, with p10-p90 in the hover card and a legend reading "Modelled: scenario range from 27 past storms" | `counties[]` | `CountyLayer.tsx`, `Legend.tsx` |
| F3 | When a modelled result is present, "affected" comes from `affected_county_fips` (at least 10% outage in at least half the draws) instead of the band intersection; the band stays as the drawn track | `affected_county_fips` | `state/scenario.tsx` |
| F4 | Scenario summary card: people at risk (power-dependent, oxygen, dialysis, facility beds) as p10 / p50 / p90; the `likelihood` line ("about once every N years since 1950"); a badge when `support` is `outside_labeled_support` | `statewide`, `scenario.likelihood`, `scenario.support` | `AffectedSummary.tsx` |
| F5 | Receiving list: when a modelled result has `receiving`, show drive minutes (`status` live or straight-line), evacuation delay low / base / high, and whether the trip beats the winds; otherwise keep today's straight-line list | `receiving.sites[]` | `ReceivingList.tsx` (`ValueKind` already has `live`) |
| F6 | Surge zone layer for the chosen category | `agent/readiness_agent/scenario/data/surge_zones.geojson`, served as a static file or bundled | `MapView.tsx` |
| F7 | "What we could not tell you": add the scenario's ranked unknowns and the `outside_labeled_support` note | `gap_sensitivity` result | `CouldNotTell.tsx` |
| F8 | Position mode: click a point, set heading and date, ask "what if a storm is here"; the chat sends those in the question and the agent calls `run_scenario(lat, lon, ...)` | none new | `ScenarioControls.tsx` |
| F9 | Season view toggle: county fill by `p_outage25_per_year` or `uncovered_1in10` | `season_county_risk` | lead's call: chat tool now, or an optional `season` block in `map-data` later |

## 3. Contract updates

| File | Change |
|---|---|
| `specs/001-georgia-shelter-map/contracts/agent-interface.md` | Add the three tools to "Tools whose results the frontend reads" with their shapes, and `functionResponse.name == "run_scenario"` as the event the frontend keeps |
| `specs/002-scenarios/contracts/run-scenario.md` | The full input and output contract (this PR) |
| `CONTEXT v1` | Unchanged. If the frontend later sends position-mode inputs as structured context, add an optional `scenario.position {lat, lon, heading_deg, date, intensity_kt}`; optional fields need no version bump |

## 4. Outputs that feed report generation

A county readiness report is assembled from tool results only. Each section names its tool, the fields it uses and its `source`, so every figure in the report is traceable.

| Report section | Tool | Fields |
|---|---|---|
| Who cannot leave | `build_readiness_brief` | `vulnerable_tracts`, `medical_dependency` |
| How often the power goes out here | `season_county_risk` | `p_outage25_per_year`, `power_dependent_affected_typical`, `power_dependent_affected_1in10` |
| The storm patterns that matter for this county | `run_scenario` per pattern | `scenario.likelihood`, `scenario.past_storms_used`, `counties[]` row for the county |
| People at risk in those storms | `run_scenario` | `counties[].power_dependent`, `oxygen_users`, `home_health_users`, `dialysis_patients`, facility beds, all as ranges |
| Where they would go, and whether it holds up | `run_scenario` (selected county) + `get_shelters` + Maps grounding + `record_live_check` | `receiving.sites[]`, `receiving.lacking_shelter, receiving.needing_transport`, live check status |
| What to fix before the season | `gap_sensitivity` + `build_readiness_brief` | `gaps[]` ranked by swing with `record_to_collect`; shelters to verify |
| What we could not tell you | all of the above | `could_not_tell`, `support`, censored emPOWER counts, every `assumptions` entry |

Report rules:
- Figures carry their `source` and are labelled registry, survey, simulated or live.
- Modelled figures are written as ranges with the label "scenario range from 27 past storms".
- Likelihood is historical frequency since 1950, never a forecast.
- Assumptions from corridor loads (g-flow, all marked assumption) and our 4x delay cap are named as assumptions.

## 5. Order of work

1. This PR: tools, package, contract (agent side). Highlighting works on merge.
2. UI team: F1-F5 first (the modelled result on the map and in the side panel), then F6-F8.
3. F9 after the lead decides where the season view lives.
