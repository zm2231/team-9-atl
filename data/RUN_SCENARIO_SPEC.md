# `run_scenario`: inputs and outputs

Draft, 2026-10-27. A Python function tool on the readiness agent. It does all the arithmetic; the model only decides when to call it and explains what comes back.

## Inputs

The drawn track and category come from the `CONTEXT v1` part of the user's message (read through ADK's `tool_context.user_content`), so the model never has to copy coordinates. The arguments below cover the cases where there is no drawn track, or where the operator names something in chat.

| Input | Type | Required | Default | Notes |
|---|---|---|---|---|
| drawn track | GeoJSON LineString | no | from `CONTEXT v1` `scenario.track` | Used when present |
| `category` | int 0-5 | no | `CONTEXT v1` `scenario.category`, else 3 | 0 = tropical storm |
| `origin` | `gulf`, `florida_peninsula`, `atlantic_ga`, `overland_west`, `carolinas` | no | classified from the track's entry point | Without a drawn track, past tracks from this origin are used |
| `landfall_lat`, `landfall_lon` | float | no | none | Shifts the past tracks to this point |
| `county_fips` | string | no | `CONTEXT v1` `county_fips` | The selected county; turns on the receiving-site section |
| `case` | `low`, `base`, `high` | no | `base` | Traffic and relocation assumptions |

The model is fixed (27 storms, 2018-2025) and the random seed is fixed, so the same inputs always give the same numbers.

## Output

### `scenario` (one object)

| Field | Meaning |
|---|---|
| `source` | `drawn_track` or `past_tracks` |
| `origin`, `category` | As used |
| `past_storms_used` | Names and years of the past tracks behind the range, e.g. `Michael 2018` |
| `support` | `within_labeled_support`, or `outside_labeled_support` when no past storm from this origin reached this intensity with trustworthy outage data (every Atlantic-coast hurricane today) |
| `range_label` | Always "scenario range from 27 past storms"; the range held 77% of counties when tested on storms left out |
| `assumptions` | Each stated value used: share of power-dependent residents who seek a powered seat, the outage level at which a dialysis centre counts as down, the "affected" threshold, traffic case |

### `statewide` (one object; each count as p10 / p50 / p90)

| Field | Definition |
|---|---|
| `counties_affected` | Counties with median outage at least 10% |
| `power_dependent_at_risk` | Sum over counties of Medicare residents on electricity-dependent equipment × outage share |
| `oxygen_users_at_risk` | Same, for oxygen services |
| `dialysis_patients_at_risk` | Dialysis patients in counties where outage reaches the dialysis-down threshold, or whose county's centres sit in the surge zone |
| `facility_beds_exposed` | Nursing-home and assisted-living beds in counties at or above the threshold (generator status not recorded, so all are counted as exposed) |

### `counties` (list; the 20 with the most people at risk, plus the selected county)

| Field | Definition | Source |
|---|---|---|
| `county_fips`, `county_name` | | Census |
| `outage_share` | p10 / p50 / p90 share of customers without power | outage model |
| `peak_wind_kt`, `hours_ts_winds` | Modelled peak wind; hours of tropical-storm winds | wind field |
| `ts_winds_arrive_h` | Hours from the start of the scenario until tropical-storm winds reach the county: the deadline for moving people | track |
| `power_dependent` | Residents on electricity-dependent equipment, and p10 / p50 / p90 at risk | HHS emPOWER |
| `oxygen_users` | Oxygen users, and at risk | HHS emPOWER |
| `home_health_users` | Home-health users, and at risk | HHS emPOWER |
| `dialysis_patients` | Patients, centres and stations in the county, and whether the centres count as down | emPOWER, CMS |
| `nursing_home_beds`, `assisted_living_beds` | Beds in the county; generator recorded / not recorded | CMS, GaMap2Care (aggregated) |
| `in_surge_zone` | Medical shelters and dialysis centres in the county inside the category's surge zone | NOAA SLOSH |
| `status` | `modelled`, plus `outside_labeled_support` or `censored_count` where emPOWER suppresses small counts | |

### `receiving` (only when a county is selected)

Medical shelters and dialysis centres that stay usable: outside counties at the dialysis-down threshold, and outside the surge zone. Sorted by drive time.

| Field | Definition |
|---|---|
| `shelter_id` or `ccn`, `name`, `county_fips` | Site identity; the frontend highlights these |
| `seats` or `stations`, `generator` | Capacity; generator as `YES`, `NO` or `UNRECORDED` |
| `straight_line_km` | Always present |
| `drive_minutes` | Live from Routes, with `status`: `live` or `straight_line` when Routes fails |
| `evacuation_delay_minutes` | low / base / high, from g-flow's corridor load for this origin, multiplier capped at 4 |
| `arrives_before_ts_winds` | Whether the base-case trip finishes before tropical-storm winds reach the starting county |
| `shortfall` | For the selected county: power-dependent residents expected to seek a powered seat versus generator-recorded seats reachable in time |

The agent then grounds the top receiving sites with Google Maps and drops or flags any that no longer exist or are not what the record says.

## Statewide totals behind the "people at risk" fields

From `evac_prod.power_dependent_counties_clean` (HHS emPOWER, Medicare beneficiaries). Some small-county counts are suppressed and flagged `power_dependent_is_censored`, so these are lower bounds:

| Group | Georgia total |
|---|---:|
| Electricity-dependent medical equipment | 106,561 |
| Oxygen services | 26,090 |
| Dialysis (ESRD) | 18,026 |
| Home health services | 15,648 |

## Not in the output

Individuals or addresses; restoration time; rain flooding and tornadoes; any stored Routes or Maps result.
