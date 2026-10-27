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
| `sites_off` | list of `shelter_id` or `ccn` | no | `CONTEXT v1` `scenario.site_overrides.off` | Operator what-if: the site takes nobody |
| `assume_generator` | list of `shelter_id` | no | `CONTEXT v1` `scenario.site_overrides.assume_generator` | Operator what-if: the shelter's seats count as powered. On a shelter recorded `UNRECORDED` it confirms a generator; on one recorded `NO` it models adding one. Each site carries `generator_assumption` (`confirm_unrecorded` or `add_where_recorded_no`); season results carry `generator_assumptions` per id. `county_plan`'s generator section assumes only `UNRECORDED` |

A one-off scenario is conditional: it uses only the past storms that were at a similar place, heading, time of year and strength, and reports what share of them went on to reach Georgia. The season view for a county (`season_county_risk`) is unconditional: it uses every storm since 1950 that came within 250 km of Georgia, weighted by how often each kind occurs.

The model is fixed (35 storms, 2016-2025, from `ext_eaglei_county_storm_2014_2025`) and the random seed is fixed, so the same inputs always give the same numbers.

## Output

### Top-level fields shared with `CONTEXT v1`

These reuse the names of the scenario object the frontend already sends, so the map can apply a modelled result the same way it applies its own band:

| Field | Meaning |
|---|---|
| `affected_county_fips` | Counties at or above 10% outage in at least half of the simulated draws |
| `affected_shelter_ids` | Medical shelters in those counties or inside the chosen category's surge zone |
| `receiving_top` | `shelter_id` of the receiving medical shelters in rank order (selected county only), for `get_shelters`. Dialysis centres appear only in `receiving.sites`, identified by `ccn` |


### `scenario` (one object)

| Field | Meaning |
|---|---|
| `source` | `drawn_track` or `matched_past_storms` |
| `match` | For matched storms: how many matched, and the share that came within 100 km of Georgia |
| `origin`, `category` | As used |
| `past_storms_used` | Names and years of the past tracks behind the range, e.g. `Michael 2018` |
| `likelihood` | How often this kind of storm has happened since 1950: `matching_storms`, `years`, `per_year`, `return_period_years`, `p_at_least_one_per_season`, an 80% range on the yearly rate, and up to five example storms. Historical frequency only: not a forecast, no climate-trend adjustment |
| `support` | `within_labeled_support`, or `outside_labeled_support` when no past storm from this origin reached this intensity with trustworthy outage data (every Atlantic-coast hurricane today) |
| `range_label` | "scenario range from N past storms", N read from `outage_model_metrics.json` (35); the range held 79% of counties when tested on storms left out |
| `assumptions` | Each stated value used: share of power-dependent residents who seek a powered seat, the outage level at which a dialysis centre counts as down, the "affected" threshold, traffic case |

### `statewide` (one object; each count as p10 / p50 / p90)

| Field | Definition |
|---|---|
| `counties_affected` | In each simulated draw, the number of counties at or above 10% outage; reported as p10 / p50 / p90 across draws |
| `counties_affected_in_most_draws` | A single count: counties at or above 10% outage in at least half of the draws. Equals the length of `affected_county_fips` |
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
| `dialysis_patients` | `patients`, `centres`, `stations` in the county, and `centres_down` (median outage at or above the dialysis-down threshold) | emPOWER, CMS |
| `nursing_home_beds`, `assisted_living_beds` | Beds in the county; generator recorded / not recorded | CMS, GaMap2Care (aggregated) |
| `in_surge_zone` | `shelter_ids` and `dialysis_ccns` in the county inside the chosen category's surge zone (empty when no category) | NOAA SLOSH |
| `status` | List: `modelled`, plus `outside_labeled_support` when the scenario is, and `censored_count` where emPOWER suppresses small counts | |

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
| `lacking_shelter` | `seeking_powered_seat`, `powered_seats_reachable` (generator recorded or assumed, regardless of timing), `no_powered_seat` |
| `needing_transport` | `cannot_arrive_in_time`: seekers who could be seated, but only at sites whose base-case trip ends after tropical-storm winds arrive |
| `baseline`, `delta` | Present when switches are set: the same two blocks with no switches, and the difference |
| `ignored_ids` | Switch ids that match no site |

The two needs are never added together: one person can be in both. Per county, `needing_transport.no_vehicle` (p10/p50/p90) is power-dependent residents at risk × the county's no-vehicle share among households headed by someone 65+ (ACS 2023 B25045); `no_vehicle_low` uses all households. `statewide` carries the same sums.

The agent then grounds the top receiving sites with Google Maps and drops or flags any that no longer exist or are not what the record says.

## Statewide totals behind the "people at risk" fields

From `evac_prod.power_dependent_counties_clean` (HHS emPOWER, Medicare beneficiaries). Some small-county counts are suppressed and flagged `power_dependent_is_censored`, so these are lower bounds:

| Group | Georgia total |
|---|---:|
| Electricity-dependent medical equipment | 106,561 |
| Oxygen services | 26,090 |
| Dialysis (ESRD) | 18,026 |
| Home health services | 15,648 |

## Status results

When the tool cannot run a scenario it returns `{status, message, source}` instead, with no numbers:

| `status` | When |
|---|---|
| `needs_track_or_position` | No drawn track with two or more valid points, and no `lat`/`lon` |
| `bad_date` | `date` is not `YYYY-MM-DD` |
| `no_matching_past_storms` | No storm since 1950 matches the position, heading and month |

A `CONTEXT v1` part that is not a JSON object, a malformed track, or a category outside 0-5 is ignored rather than raising.

## Not in the output

Individuals or addresses; restoration time; rain flooding and tornadoes; any stored Routes or Maps result.

## Related tools

| Tool | Returns |
|---|---|
| `season_county_risk(county_fips, limit, outlook, sites_off, assume_generator, case, seats_override, stations_override, add_sites)` | Season risk under an outlook: `long_run` (default), `recent`, `la_nina`, `neutral`, `el_nino`, `noaa_aug_2026` (an outside forecast input that cites NOAA; scales the storm count by 10/14 and reweights events by category so the Cat 1+ and Cat 3+ shares move by NOAA's hurricane and major ratios). Each result carries `outlook_note` with that outlook's 2018-2025 back-test, `severity` (Cat 1+ and Cat 3+ shares of events) and `probability` (`p_lacking_shelter_any`, `p_lacking_shelter_50`, `p_no_dialysis_chair_any`, labelled "share of simulated seasons"). Always reruns the saved 3,200-event season live (about 0.2 s) so planner updates and what-ifs apply |
| `county_plan(county_fips, outlook)` | One call: `readiness_brief` (from `build_readiness_brief`), `power_outage_frequency` under the outlook and the long run, `generator_switch_effect` (every unrecorded medical-shelter generator assumed), and `audit` (the brief's ranked tracts against the rest of the state, from ACS B03002, audit only). Any section that fails is `{status: "not_determined"}` |
| `record_site_update(site_kind, site_id, field, value, source, source_date)` | Stores one planner-reported fact in `scenario_site_updates` (parameterised INSERT; the only table any tool writes). `site_kind`: `medical_shelter` or `dialysis`; `field`: `generator` (YES, NO, UNRECORDED), `seats`, `stations`, `open` (true or false), `lat`, `lon` (inside Georgia), `name`, `county_fips` (one of Georgia's 159). `source` is one of `county_ema`, `gema`, `site_visit`, `facility_call`, `state_registry`, `planner_review`, with an optional `source_date`; no free text is stored. A `site_id` not in the registry is an added site; a medical shelter needs `lat`, `lon`, `seats` and `generator`, a dialysis centre `lat`, `lon` and `stations`. Returns `{status: "recorded", update_id, ...}` or `{status: "invalid", message}` |
| `recommend_sites(outlook, county_fips, limit, lat, lon, seats)` | Candidate medical-shelter sites ranked by modelled reduction in people lacking shelter (statewide, or for `county_fips`): the 11 medical shelters without a recorded generator upgraded with their recorded seats, general shelters (not medical, outside every SLOSH category, capacity at least 500) converted with 100 powered seats, and new 100-seat sites at each county's population centre. Each has before/after/reduction (1-in-10 and typical), `counties_helped`, `p_helps` (share of simulated seasons in which it helps, same seasons before and after) and `expected_reduction_per_year`. `lat`, `lon`, `seats` add a planner-proposed site. `best_combination_of_3` is picked one site at a time, rerunning after each pick, because reductions do not add up. `label`: "modelled reduction; assumes N powered seats ...; straight-line reach of 100 km" |

### Planner site updates

Every `run_scenario`, `season_county_risk`, `county_plan` and `recommend_sites` call reads `scenario_site_updates` (capped at 100 MB billed). The latest row per site and field wins. Registry values are never overwritten: results carry `planner_updates.changes`, each with `registry`, `planner` and `label` ("planner-reported (entered_by, date)"). Closed sites are switched off; added sites get straight-line reach of 100 km and surge "unknown, treated as not flooded". If the read fails, results use registry values only and `planner_updates.status` is `registry_only`, with a message saying so.

Per-request what-ifs sit next to `sites_off` and `assume_generator` on `run_scenario` and `season_county_risk`: `seats_override {shelter_id: n}`, `stations_override {ccn: n}`, `add_sites [{lat, lon, seats, generator}]`. Invalid values go to `ignored_ids` and are never applied.

### Season interface for other modules

`season.run_season(..., as_of_date=None, custom=None)`: `as_of_date` keeps only storms whose closest approach to Georgia falls after that month and day (`as_of.share_of_season_remaining`; about 5% after 27 October). `outlook="custom"` with `custom={storms_per_year, hurricane_share, major_share, source}` reweights events to those shares; it is an internal interface, not a tool argument. `season.season_remaining_share(as_of_date)` returns the share alone.
