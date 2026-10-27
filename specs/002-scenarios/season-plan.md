# Scenarios: season outlook, batch view and the county plan

Draft for team review. The agent side is built on branch `scenario-outlook`, which is stacked on PR #10.

## Who uses it, and when

A county emergency manager at the start of the season, before any storm. They can work in two places:

1. **Chat (one-off runs).** They ask the agent, for example "plan for this year's outlook" or "what if the Glynn shelter is off and Chatham's shelter gets a generator?" The agent runs the season or a single storm with those switches and answers from the results.
2. **Batch view (second window).** Every precomputed combination of outlook × switch set × case, side by side, for the state and for each county. No model call is needed to browse it. A "Plan for this county" action produces the county plan.

## Season outlooks

| Outlook | Storm rate from | Label |
|---|---|---|
| `long_run` | All storms within 250 km of Georgia, 1950-2025 | "Long-run average since 1950" |
| `recent` | 2000-2025 | "Recent rates (2000-2025)" |
| `la_nina` / `neutral` / `el_nino` | Storms in years with that Aug-Oct ENSO state (NOAA ONI) | "Seasons like this one (El Niño)", etc. |
| `noaa_aug_2026` | `long_run` × 10/14 | "Scaled to NOAA's August 2026 outlook (assumption)" |

Measured Georgia storms per year: La Niña 3.22 (18 seasons), neutral 2.50 (38), El Niño 2.35 (20). The ENSO effect matches the forecasters' reasoning but is not statistically firm on Georgia alone (p = 0.16). Every outlook is labelled as conditioned on history, never as a forecast. The page states whether the conditional back-test beats the long-run one.

## How many simulations

| Run | Size | Where | Time |
|---|---|---|---|
| Season batch (production) | 2,000 simulated storms, 20,000 simulated seasons, per outlook × switch set × case | Offline build, written to BigQuery (`scenario_season_county`, `scenario_batch`) | Minutes, rerun when data or settings change |
| Agent season rerun with switches | The same 2,000 storms, 5,000 seasons resampled, with only the shelter and dialysis allocation recomputed | In the agent, `season_county_risk` with switches | Target under 3 s (measured value goes here) |
| Agent single storm | 400 outage draws spread across up to 40 matched past tracks, or the one drawn track | In the agent, `run_scenario` | Under 1 s plus live Routes |

## Batch view (frontend)

| Element | Data |
|---|---|
| Outlook picker, switch-set picker (baseline / all unrecorded generators confirmed / Category 3 coastal shelters off), case picker (low / base / high) | `scenario_batch` |
| Statewide tiles: power-dependent affected, lacking shelter (no powered seat, no dialysis chair), needing transport (no vehicle), each as typical and 1-in-10 | `scenario_batch` statewide rows |
| County map: fill by lacking shelter in a 1-in-10 season. Hover shows all values | `scenario_batch` county rows |
| Comparison strip: the selected setting against baseline long-run, as ±delta | two rows of `scenario_batch` |
| "Plan for this county" sends the chat message "Plan the season for <county> under <outlook>" | agent `county_plan` |

The view reads the table through the agent's map-data path or a new read-only block. The lead owns `map_data.py` and decides which.

## County plan (report)

Assembled by the `county_plan(county_fips, outlook)` tool from tool results only. Every figure has its source and a label: registry, survey, simulated or live.

1. Who cannot leave (`build_readiness_brief`)
2. How often the power goes out here, under this outlook and long-run (`season_county_risk`)
3. People lacking shelter and people needing transport, typical and 1-in-10 (`season_county_risk`)
4. What the switches change: generators confirmed, coastal shelters off (`scenario_batch`)
5. Where they would go and whether it holds up (`run_scenario` for the county's most likely storm pattern, with live checks)
6. What to fix first (`gap_sensitivity`)
7. What we could not tell you

The agent writes the prose. Numbers come only from the tool.
