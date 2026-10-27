# `run_scenario`: inputs and outputs

Contract for the `run_scenario` tool, 2026-10-27. A Python function tool on the readiness agent. It does all the arithmetic; the model only decides when to call it and explains what comes back.

## Inputs

The drawn track and category come from the `CONTEXT v1` part of the user's message (read through ADK's `tool_context.user_content`), so the model never has to copy coordinates. The arguments below cover the cases where there is no drawn track, or where the operator names something in chat.

| Input | Type | Required | Default | Notes |
|---|---|---|---|---|
| drawn track | GeoJSON LineString | no | from `CONTEXT v1` `scenario.track` | When present, the storm follows it |
| `lat`, `lon` | float | no | none | Where the storm is at the moment being explored. Without a drawn track, the tool finds past storms that passed within 300 km of this point |
| `heading_deg` | float | no | none | Direction of travel; matched past storms are within 45 degrees of it |
| `date` | ISO date | no | today's month | Matched past storms are within a month of it |
| `intensity_kt` | float | no | none | Storm strength at that point; matched past storms are within 20 kt of it and keep their own later strength |
| `category` | int 0-5 | no | `CONTEXT v1` `scenario.category` | For a drawn track, sets the storm's strength. For matched storms, an optional override that rescales them |
| `county_fips` | string | no | `CONTEXT v1` `county_fips` | The selected county; turns on the receiving-site section |
| `case` | `low`, `base`, `high` | no | `base` | Traffic and relocation assumptions |

A one-off scenario is conditional: it uses only the past storms that were at a similar place, heading, time of year and strength, and reports what share of them went on to reach Georgia. The season view for a county (`season_county_risk`) is unconditional: it uses every storm since 1950 that came within 250 km of Georgia, weighted by how often each kind occurs.

The model is fixed (27 storms, 2018-2025) and the random seed is fixed, so the same inputs always give the same numbers.

## Output

### Top-level fields shared with `CONTEXT v1`

These reuse the names of the scenario object the frontend already sends, so the map can apply a modelled result the same way it applies its own band:

| Field | Meaning |
|---|---|
| `affected_county_fips` | Counties whose median outage is at least 10% |
| `affected_shelter_ids` | Medical shelters in those counties or inside the chosen category's surge zone |
| `receiving_top` | `shelter_id` or `ccn` of the receiving sites in rank order (selected county only) |


### `scenario` (one object)

| Field | Meaning |
|---|---|
| `source` | `drawn_track` or `matched_past_storms` |
| `match` | For matched storms: how many matched, and the share that came within 100 km of Georgia |
| `origin`, `category` | As used |
| `past_storms_used` | Names and years of the past tracks behind the range, e.g. `Michael 2018` |
| `likelihood` | How often this kind of storm has happened since 1950: `matching_storms`, `years`, `per_year`, `return_period_years`, `p_at_least_one_per_season`, an 80% range on the yearly rate, and up to five example storms. Historical frequency only: not a forecast, no climate-trend adjustment |
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
