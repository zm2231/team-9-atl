# C4 scenario engine: scope

Draft for team review, 2026-10-27. Framing is not final until Zain confirms it. Components are named by what they compute.

## Who it is for

A Georgia county emergency manager in August, with no storm in sight and about three weeks to report what to fix before the season (C4 `README.md:143-160, 538`). This is preparedness planning, not operations.

## Problem

The hardest pre-season calls for medically fragile residents are: who loses power, where they can go, whether that place has a generator, and whether dialysis continues. These calls are made against storms that have not formed yet, from records that are often blank. Today the map shows a fixed-width illustrative band. It cannot say how bad the outage gets, how sure we are, or which missing record matters most.

## What it answers

1. **For a storm the operator draws or picks:** each county's share of customers without power, as a range, plus the power-dependent residents and dialysis patients that puts at risk.
2. **Where they can go:** medical shelter seats and dialysis chairs within reach, with live drive times and an evacuation-traffic range.
3. **Across a whole season:** how often each county loses at least a quarter of its power, and how many people are affected in a typical year and a 1-in-10 year.
4. **What to fix first:** the unknowns (generator status, dialysis surge capacity, Florida inflow, the model's own bias) ranked by how much each one changes the number of people left without a powered seat or a chair.

## In scope

| Lane | What is built | Data | Output |
|---|---|---|---|
| A. Engine | Hourly wind at every county from a storm track (parametric wind field). Hierarchical outage model fitted on 27 storms (2018-2025) across 226 GA and FL counties. A new storm draws a fresh storm effect, so the range is honest. Accepts the operator's drawn track or a named origin with a category, and flags tracks with no comparable past storm | IBTrACS tracks, g-grid `county_storm_outages`, emPOWER | `run_scenario` tool; package in `agent/readiness_agent/scenario/` |
| B. Season | About 2,000 simulated storms: past tracks by origin, intensity from that origin's history, small position shifts, weighted by how often each origin reaches Georgia (since 1950) | IBTrACS since 1950, templates since 2001 | `evac_prod.scenario_season_county`, `evac_prod.scenario_fix_ranking`; `season_county_risk` and `gap_sensitivity` tools |
| C. Frontend | County colour by modelled outage (median, range on hover, legend), "affected" defined as at least 10% outage, preset historical tracks, ranked fix list in the existing "could not tell" panel, season view | tool responses, map data | changes in `frontend/src` (see `FRONTEND_ALIGNMENT.md`) |
| D. Movement | Live drive time to the shortlisted sites (Routes API, never stored, falls back to straight-line). Evacuation congestion multiplier by origin and corridor. Storm deadline: travel must finish before tropical-storm winds arrive | Routes API, g-flow `corridor_vc.json`, simulated tracks | fields on `run_scenario` results |
| E. Verification | Tests that run without credentials, a back-test of the season model against 2018-2025, a codex-review loop until SHIP, the demo flow checked in the browser, the claims doc kept in step with the numbers | all of the above | PR to `main`; `CLAIMS.md` |

## Out of scope

| Out | Why |
|---|---|
| Live operations, dispatch, any active storm | Maps grounding terms forbid emergency response; this is planning weeks ahead |
| Forecasting a real storm's track | NHC's job; we model plausible storms |
| Individuals or addresses | County counts only |
| Rain flooding and tornadoes as modelled hazards | No time-resolved data we can model in time; NCEI reports shown as context. Surge is in scope, tied to the storm clock |
| How long restoration takes | Peak outage only |
| Car-by-car traffic, individual route choice | Cannot be calibrated; corridor traffic is replayed from past evacuations instead |
| Florida's own residents | Florida evacuees enter only as a share of Georgia capacity they take |
| Modelling the nursing-home evacuate-or-stay decision | Generator status is unrecorded; it is a fix-list item |
| Wind accuracy beyond the parametric field | No observed wind data; the model is checked against outages instead |
| Storing Routes or Maps results | Maps terms; computed live per request |

## Hazards over time

| Hazard | How it enters | Clock | Data |
|---|---|---|---|
| Wind and power | County outage range from the model | Hour tropical-storm winds reach each county | IBTrACS, EAGLE-I |
| Storm surge | Shelters and dialysis centres in the chosen category's surge zone drop out; coastal route segments in the zone close | At tropical-storm wind arrival on the coast | NOAA SLOSH Georgia basin, Cat 1-5 |
| Rain flooding, tornadoes | Context only | none | NCEI Storm Events |

## Movement and congestion

| Layer | What | Source |
|---|---|---|
| Live drive time | County to shortlisted receiving site, live per request, never stored | Routes API (enabled; Cloud Run account needs `serviceusage.serviceUsageConsumer`) |
| Evacuation traffic, replayed from history | Corridor queue on I-75 S, I-16 (contraflow), I-95: departures timed from past order timelines (Irma first reported 96 h before TS winds, effective 35 h, contraflow 35 h; Dorian 41 h / 21 h), surge size from GDOT measurements (Milton I-75 NB +280% / +342%, I-95 +264%), normal volume from GDOT counts (to pull). Queue = previous + arrivals - capacity, never below zero; low/base/high | `ga_evacuation_orders`, GDOT, g-flow corridor model |
| Storm deadline | Travel must finish before tropical-storm winds reach the county | each simulated track |

The season view uses the deadline and straight-line reach. The single-storm view adds live Routes and congestion.

## Agent architecture (built on what is deployed)

- **One ADK agent, not multi-agent.** Gemini 3 runs Maps grounding and function tools in one agent (verified in `agent/README.md`, already true on `main`). A Maps-only sub-agent in `AgentTool` is the fallback only if the model is pinned to 2.5.
- **No custom MCP server.** The challenge requires consuming a Google-managed MCP server (BigQuery's, already wired) and says not to author one. Our logic ships as Python function tools.
- **Existing:** `google_maps_grounding`, BigQuery MCP `execute_sql_readonly`, four function tools, `before_agent_callback` for map data.
- **New:** `run_scenario` (numpy engine, reads the drawn track from `CONTEXT v1`, live Routes), `season_county_risk`, `gap_sensitivity`.
- **Numbers come from tools, never the model.** The model picks tools, explains, and acts on Maps grounding.

## What the numbers can and cannot claim

Full list in `CLAIMS.md`. The ones that shape the demo:

- The outage range held 77% of counties when each storm was predicted with it left out (target 80%). Call it a "scenario range from 27 past storms", not a confidence interval.
- The model under-predicts major storms by about half (Helene, Michael, Idalia, Zeta). For a major storm, plan to the top of the range.
- No trustworthy example of a direct Atlantic hurricane landfall on Georgia exists. Those scenarios are flagged as outside the data.
- Shelter fill history does not exist below statewide Red Cross totals.

## Changes over time

| Effect | What the data shows | Handling |
|---|---|---|
| Grid hardening | No trend detectable: held-out error by year has slope +0.002, correlation 0.11 over 27 storms | Not modelled; stated assumption that the grid behaves as in 2018-2025 |
| Customer growth | Every year uses 2024 customer counts | Accepted and disclosed |
| Data coverage | County outage data before 2018 is unreliable | Excluded from training; older tracks still set storm rates |
| Climate trend in storm rates | Rates averaged 1950-2025 | Gap sensitivity compares 1950-2025 with 2000-2025; no trend claimed |
| Back-to-back storms | Carry-over from one storm into the next window | Flagged and dropped; storms count separately |
| Same counties hit repeatedly | County identity explains about 20% of outage variation | The model's county effect uses each county's history, pulled toward the average |

## Success check

- Each storm is predicted with that storm held out: 10th-90th range holds at least 75% of held-out counties.
- Season back-test: for at least 80% of counties, the observed 2018-2025 count of storms causing 25%+ outage falls inside the model's 10th-90th range.
- The deployed agent answers a drawn-track scenario in under 10 seconds and a season question in under 5. Routes failure degrades to straight-line and never fails a turn.
- Replayed traffic base case reproduces the direction and rough size of GDOT's measured Milton surge on I-75.
- `pytest -q` passes without credentials, and codex-review returns SHIP.

## Timeline to the 16:15 freeze

| By | Lane | Milestone | Cut if late |
|---|---|---|---|
| 14:00 | A | `run_scenario` working on drawn tracks, tests green | Named origins only |
| 14:40 | B | Season table and gap ranking in `evac_prod` | Season table without gap ranking |
| 14:45 | D | Congestion multiplier from g-flow | Fixed low/base/high multipliers, labelled |
| 15:15 | C | Outage colour layer and legend | Highlights only (already works) |
| 15:30 | E | PR open, codex-review | |
| 16:00 | all | Merged and deployed, demo walked in the browser | |

## Open decisions

1. Product framing and what the demo leads with (Zain).
2. Season view: an optional `season` block in `map-data` versus a chat tool (lead, as owner of `map_data.py`).
3. Cloud Run permission for Routes (lead, `deploy/setup_gcp.sh`).
