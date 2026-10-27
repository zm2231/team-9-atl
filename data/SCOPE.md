# C4 scenario engine: scope

Draft for team review, 2026-10-27. The framing is not final until Zain confirms it, so components are named by what they compute.

## Who it is for

A Georgia county emergency manager in August, with no storm in sight and about three weeks to report what to fix before the season (C4 `README.md:143-160, 538`). The tool is for planning in the weeks before the season. It is not for use during an active storm.

## Problem

Before the season, a county has to decide who will lose power, where those residents can go, whether that place has a generator, and whether dialysis patients can keep their treatments. Those decisions are made before any storm has formed, from records that are often blank: generators are recorded at 3 of Georgia's 14 medical shelters, and no shelter in the registry is recorded as safe to occupy before landfall. The current map draws a fixed-width band around a drawn track, labelled illustrative. It cannot show how severe the outage will be, how confident the estimate is, or which missing record matters most.

## What it answers

1. For a storm the operator draws or picks, each county's share of customers without power as a range, and the number of power-dependent residents and dialysis patients in those counties.
2. Where those people can go: medical shelter seats and dialysis chairs within reach, with live drive times, a range for evacuation traffic, and the surge zone closing as the storm arrives.
3. Over a whole season, how often each county loses power to at least 25% of its customers, and how many people are affected in a typical year and in a 1-in-10 year.
4. Which unknowns to resolve first: generator status, dialysis surge capacity, Florida inflow and the model's own bias, ranked by how much each changes the number of people left without a powered seat or a dialysis chair.

## In scope

| Lane | What is built | Data | Output |
|---|---|---|---|
| A. Engine | Hourly wind at every county from a storm track, using a parametric wind field. A hierarchical outage model fitted on 27 storms (2018-2025) across 226 GA and FL counties. Each new storm gets a storm effect drawn from the spread seen across past storms, so the range includes storm-to-storm variation. Takes the operator's drawn track, or an origin with a category, and flags tracks with no comparable past storm | IBTrACS tracks, g-grid `county_storm_outages`, emPOWER | `run_scenario` tool; package in `agent/readiness_agent/scenario/` |
| B. Season | About 2,000 simulated storms: past tracks by origin, intensity drawn from that origin's history, small position shifts, weighted by how often each origin has reached Georgia since 1950 | IBTrACS since 1950; track templates since 2001 | `evac_prod.scenario_season_county`, `evac_prod.scenario_fix_ranking`; `season_county_risk` and `gap_sensitivity` tools |
| C. Frontend | Counties coloured by modelled outage (median, with the range on hover and a legend); "affected" defined as at least 10% outage; the surge zone for the chosen category; preset historical tracks; ranked unknowns in the existing "could not tell" panel; a season view | tool responses, map data | changes in `frontend/src` (see `FRONTEND_ALIGNMENT.md`) |
| D. Movement | Live drive time to the shortlisted sites, corridor delay from g-flow's load estimates, and the wind and surge deadlines described below | Routes API, g-flow `corridor_vc.json`, evacuation order history, SLOSH | fields on `run_scenario` results |
| E. Verification | Tests that run without credentials, a back-test of the season model against 2018-2025, codex-review until SHIP, the demo flow checked in the browser, and the claims doc updated as numbers change | all of the above | PR to `main`; `CLAIMS.md` |

## Out of scope

| Out | Why |
|---|---|
| Live operations, dispatch, any active storm | Google's terms forbid using Grounding with Google Maps for emergency response. This tool is for planning weeks ahead |
| Forecasting a real storm's track | That is NHC's job. We model storms that could plausibly happen |
| Individuals or addresses | County counts only |
| Rain flooding and tornadoes as modelled hazards | We have no hourly flood or tornado data to model them with. Past NCEI reports are shown per county as context. Surge is in scope |
| How long restoration takes | The model predicts peak outage only |
| Car-by-car traffic and individual route choice | We have no vehicle-level or origin-destination data to calibrate it. Corridor traffic is rebuilt from past evacuations instead |
| Florida's own residents | Florida evacuees enter only as the share of Georgia capacity they take |
| Modelling whether nursing homes evacuate or shelter in place | Nursing-home generator status is not recorded, so it appears in the ranked unknowns instead |
| Wind accuracy beyond the parametric field | We have no observed wind data; the model is checked against outages instead |
| Storing Routes or Maps results | Google Maps Platform terms; both are computed live per request |

## Hazards over time

Each hazard takes effect at the hour the storm reaches it, so sites and roads drop out in the order the storm reaches them.

| Hazard | How it enters | When | Data |
|---|---|---|---|
| Wind and power | County outage range from the model | The hour tropical-storm winds reach each county | IBTrACS, EAGLE-I |
| Storm surge | Shelters and dialysis centres inside the chosen category's surge zone drop out, and coastal road segments in the zone close | From the hour tropical-storm winds reach the coast. Water can arrive earlier, so this timing is a stated assumption | NOAA SLOSH, Georgia basin, Cat 1-5 |
| Rain flooding, tornadoes | Context only | none | NCEI Storm Events |

## Movement and congestion

| Layer | What | Source |
|---|---|---|
| Live drive time | From the county to each shortlisted receiving site, computed per request and never stored. Any error falls back to straight-line distance with status `straight_line` | Routes API. Cloud Run sends `ROUTES_API_KEY` (Secret Manager); local runs fall back to application default credentials |
| Evacuation traffic | Drive time is multiplied by 1 + 0.15 × (load / capacity)^4, capped at 4. Load against capacity comes from g-flow for I-75 south, I-16 (with contraflow) and I-95, by storm origin, in low, base and high cases. In the base case, a Gulf storm loads I-75 south to 2.04 times capacity and a peninsula storm loads I-16 to 1.50 | g-flow `corridor_vc.json` (every value marked as an assumption) |
| Check against history | The base case should match the direction of what Georgia measured: GDOT recorded I-75 northbound 342% above normal the evening before Milton's landfall and 280% the next morning, and I-95 264% above normal. Departure timing follows past order timelines: Irma's order was first reported 96 h before tropical-storm winds and took effect at 35 h; Dorian's took effect at 41 h, with contraflow at 21 h | GDOT, `ga_evacuation_orders` |
| Storm deadline | Travel has to finish before tropical-storm winds reach the county, or before surge closes the road | each simulated track; SLOSH |

The season view uses the deadline and straight-line distance, because Routes results cannot be stored. The single-storm view adds live drive times and traffic delay.

## Agent architecture

The plan builds on the agent already deployed from `main`.

The product stays a single ADK agent. Gemini 3 can run Grounding with Google Maps and our own function tools in the same agent; the challenge packet verified this end to end (`agent/README.md`), and `main` already works this way. Adding sub-agents would put another model step between the tools and the answer, where numbers can be reworded, and would slow the demo. If the model were ever pinned to Gemini 2.5, the fallback is the packet's pattern: a Maps-only sub-agent wrapped in `AgentTool`.

The agent needs custom tools, and the challenge requires them. The challenge requires at least one tool we built ourselves, either a Python function tool or one defined in MCP Toolbox, plus at least one Google-managed MCP server consumed rather than authored: BigQuery's built-in server or the MCP Toolbox for Databases (`agent/README.md`). So the custom tools come in two forms:

1. Python function tools that wrap BigQuery and the scenario model. The four on `main` already do this; `run_scenario`, `season_county_risk` and `gap_sensitivity` are new. Each returns `county_fips`, which the frontend already highlights, and `run_scenario`'s per-county results drive the new outage colour layer, so the tools update the map as well as the chat.
2. Optionally, MCP Toolbox for Databases tools: parameterized BigQuery queries defined in `tools.yaml` and served by Google's Toolbox server. This gives custom tools over MCP without writing our own server, but it needs a separate Toolbox service deployed, so it is an add-on if time allows.

What we do not do is write our own MCP server; the agent already consumes BigQuery's (`execute_sql_readonly`).

| Tool | Kind | Status |
|---|---|---|
| `google_maps_grounding` | Google built-in | exists |
| `execute_sql_readonly` | Google-managed BigQuery MCP | exists |
| `find_vulnerable_tracts`, `assess_shelter_accessibility`, `find_power_dependent_counties`, `build_readiness_brief` | Python function tools | exist |
| `before_agent_callback` (map data, no model call) | ADK callback | exists |
| `run_scenario`: reads the drawn track from `CONTEXT v1`, runs the numpy engine, calls Routes live | Python function tool | new |
| `season_county_risk`, `gap_sensitivity` | Python function tools reading `evac_prod` | new |
| Parameterized BigQuery queries in `tools.yaml` | MCP Toolbox for Databases | optional |

Every number comes from a tool or a table. The model chooses which tools to call, explains the results, and acts on what Maps grounding returns, for example dropping or flagging a receiving site that no longer exists or is not what the record says.

## What the numbers can and cannot claim

The full list is in `CLAIMS.md`. These four shape the demo:

- The outage range held 77% of counties when each storm was predicted with that storm left out (target 80%). Call it a "scenario range from 27 past storms", not a confidence interval.
- The model under-predicts major storms by about half (Helene, Michael, Idalia, Zeta). For a major storm, plan to the top of the range.
- There is no trustworthy outage record for a direct Atlantic hurricane landfall on Georgia, so those scenarios are flagged as outside the data.
- Shelter fill history exists only as statewide Red Cross totals.

## Changes over time

| Effect | What the data shows | Handling |
|---|---|---|
| Grid hardening | No trend detectable: held-out error by year has slope +0.002 and correlation 0.11 across 27 storms | Not modelled. Stated assumption: the grid behaves as it did in 2018-2025 |
| Customer growth | Every year uses 2024 customer counts | Accepted and disclosed |
| Data coverage | County outage data before 2018 is unreliable | Excluded from training; older tracks still set storm rates |
| Climate trend in storm rates | Rates are averaged over 1950-2025 | Gap sensitivity compares 1950-2025 with 2000-2025; no trend is claimed |
| Back-to-back storms | Outages from one storm can carry into the next storm's window | Those rows are flagged and dropped; storms count separately |
| Same counties hit repeatedly | County identity explains about 20% of outage variation | The model's county effect uses each county's history, pulled toward the statewide average |

## Success check

- With each storm held out, the 10th-90th percentile range holds at least 75% of counties.
- Season back-test: for at least 80% of counties, the observed 2018-2025 count of storms causing at least 25% outage falls inside the model's 10th-90th percentile range.
- The traffic base case matches the direction of GDOT's measured Milton surge on I-75.
- The deployed agent answers a drawn-track scenario in under 10 seconds and a season question in under 5. A Routes failure falls back to straight-line distance without failing the turn.
- `pytest -q` passes without credentials, and codex-review returns SHIP.

## Timeline to the 16:15 freeze

| By | Lane | Milestone | Cut if late |
|---|---|---|---|
| 14:00 | A | `run_scenario` working on drawn tracks, tests passing | Named origins only |
| 14:40 | B | Season table and gap ranking in `evac_prod` | Season table without gap ranking |
| 14:45 | D | Corridor delay from g-flow, surge closure | Fixed low/base/high multipliers, labelled as assumptions |
| 15:15 | C | Outage colour layer, surge zone, legend | County highlights only (already working) |
| 15:30 | E | PR open, codex-review | |
| 16:00 | all | Merged, deployed, demo walked in the browser | |

## Open decisions

1. Product framing and what the demo leads with (Zain).
2. Season view: an optional `season` block in `map-data`, or a chat tool (lead, as owner of `map_data.py`).
3. Whether to pull GDOT traffic counts for normal-day corridor volume (lane D).
