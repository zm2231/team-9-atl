# C4 claims: what we can and cannot say

As of 2026-10-27. Every claim names its evidence. "Can say" means the evidence is in hand and checked; "cannot say" means the data does not support it, and the line to use instead. Data sources are listed in `c4-data-inventory.md`.

## 1. Storm history and warning time

| Can say | Evidence |
|---|---|
| 37 named storms passed within 250 km of Georgia from 2014 to 2025; 27 of them from 2018 on | IBTrACS `storm_tracks_ibtracs`, `min(dist_ga_km) < 250` |
| Georgia typically gets about 39 hours from the first tropical watch to tropical-storm winds (median over 18 storms, range 23 to 50) | g-flow's recomputation from `nws_tropical_alerts` and NHC onset |
| Gulf Panhandle storms gave less warning (Zeta 32 h, Isaias 27 h) | same |
| Irma's coastal evacuation was first reported 96 h before tropical-storm winds; it took effect about 35 h before; I-16 contraflow 35 h before. Dorian: effective 41 h, contraflow 21 h | `ga_evacuation_orders` (governor releases) vs NHC onset, g-flow |

| Cannot say | Say instead |
|---|---|
| "Warning time is the same regardless of origin" | Median 39 h; Gulf Panhandle storms run shorter |
| A typical "orders come 59 to 72 h out" figure | Three cited storms only (Matthew, Irma, Dorian); timing varies from 9 h to 96 h |
| Evacuation clearance times for Georgia zones | Not available: HES clearance times sit in HURREVAC, which is EM-only |

## 2. Power outages

| Can say | Evidence |
|---|---|
| Helene left 1,100,015 Georgia customers out at its peak (2024-09-27 13:15 UTC); Irma about 1.30 M | EAGLE-I 15-minute county data |
| Outage share rises with modelled wind at the county: correlation 0.4 to 0.9 within the larger storms (Ian 0.89, Idalia 0.83, Sally 0.76, Zeta 0.75, Michael 0.59, Helene 0.43) | `features_v2.parquet` |
| On 27 storms (2018 to 2025) across 226 GA and FL counties, on g-grid's `county_storm_outages` labels (6,075 rows, 27 suspect rows dropped), predicting each storm with that storm held out, the model's mean error is 0.042 outage share, against 0.062 for always predicting the average | `outage_model_metrics.json` (engine lane) and an independent refit, `loso_grid.json`, agree to 0.001 |
| The 10th to 90th percentile range contains 78% of held-out counties (target 80%), 75% on Helene, Idalia and Michael; for 26 of 27 storms the statewide average falls inside the range | same |
| The spread between storms is estimated from the data (0.71 on the logit scale), not set by hand | same, `tau_storm` |

| Cannot say | Say instead |
|---|---|
| "The model predicts major storms accurately" | It under-predicts the big ones by about half: Helene observed 0.28 vs predicted 0.19, Michael 0.19 vs 0.10, Idalia 0.14 vs 0.08. Zeta 0.10 vs 0.03, and Zeta is outside the range. Treat the upper end of the range as the planning number for a major storm |
| "The hierarchical model beats boosted trees" | They tie: 0.0415 vs 0.0414 overall, 0.135 vs 0.136 on the three biggest storms. We use the hierarchical model because it gives a range, not because it is more accurate |
| "80% confidence interval" | "Scenario range from 27 past storms"; it held 77% of counties out of sample, 70 to 75% on the major storms |
| Anything about a direct Atlantic landfall on the Georgia coast | No trustworthy example exists (Matthew 2016 and Irma 2017 predate reliable county data). Flag such scenarios as outside the data |
| Outage by date, season, utility hardening, soil moisture or tree cover | Not in the model; 27 storms cannot separate these |
| Outages before 2018 | EAGLE-I county data before 2018 is unreliable; used for nothing |

### Season view and fix ranking

| Can say | Evidence |
|---|---|
| 202 storms since 1950 came within 250 km of Georgia, 2.6 a year; the season view simulates 2,000 storms from them over 20,000 seasons | `evac_prod.scenario_season_county` (159 rows), season lane `build_season.py` |
| In a 1-in-10 season, about 11,300 power-dependent Georgians are in counties losing power, and about 2,170 are left without a powered seat or a dialysis chair (base assumptions) | same |
| The unknown that moves that 2,170 most is the share of power-dependent residents who would seek a shelter seat (1,212 to 4,154 between 10% and 40%), then unrecorded shelter generators (817 to 2,174). Storm rates, dialysis surge capacity, the model's major-storm bias and Florida inflow each move it by 300 or less | `evac_prod.scenario_fix_ranking` (6 rows) |

| Cannot say | Say instead |
|---|---|
| "The season model matches recent history" | Back-test on 2018 to 2025: 71% of counties fall inside the model's 10th-90th range for storms causing at least 25% outage (target 80%, not met). Statewide the model expects 74 such county-storms (63 to 85) where 200 happened. 2018 to 2025 had 3.4 storms a year against 2.6 long-run, and the outage model under-predicts Helene and Michael. The season view understates a period like 2018 to 2025 |
| "1-in-10 means a 10% chance this year" | It is the 90th percentile of 20,000 simulated seasons drawn from 1950 to 2026 storm rates, with no climate-trend adjustment |
| County 1-in-10 figures add up to the statewide 1-in-10 | They do not: counties peak in different seasons (sum 2,805 vs statewide 2,174) |

## 3. People who depend on power and on treatment

| Can say | Evidence |
|---|---|
| 18,026 Georgia Medicare dialysis patients; 346 dialysis centres with 5,956 stations | HHS emPOWER (live), CMS facility data; `c4-capabilities/out/summary.json` |
| The 6 coastal counties have 820 dialysis patients on 256 stations (3.2 per station) | same, `regions` |
| Only 17 centres in 9 counties offer a late shift; a third of Georgians live more than 50 km from one | same |
| Power-dependent residents are counted by county | emPOWER |

| Cannot say | Say instead |
|---|---|
| Which block or address power-dependent residents live in | County counts only, by design (privacy) |
| "Outage share x power-dependent residents = people who lose power-dependent care" | It is a planning estimate that assumes outages fall evenly across a county |
| Spare dialysis chairs on a given day | Stations and shift structure are known; chair occupancy is not |

## 4. Shelters

| Can say | Evidence |
|---|---|
| Georgia has 14 medical shelters with 4,594 seats; none in the 6 coastal counties; 43% of Georgians live more than 50 km from one | `summary.json` |
| Generators are recorded for 3 of them (1,187 seats) | same |
| No Georgia shelter in the registry is recorded as safe to occupy before landfall | `shelters` field `pre_landfall_shelter` |
| Red Cross Georgia: 5,500+ people in 40 shelters on one night of Irma (2017-09-11) | [Red Cross](https://www.redcross.org/local/georgia/about-us/news-and-events/news/Hurricane-Irma-Red-Cross-and-community-partners-shelter-over-108000-people-overnight.html) |
| 847 people over Michael's response (11 shelters); 680+ over Helene's (35 shelters) | [Michael](https://www.redcross.org/local/georgia/about-us/news-and-events/press-releases/georgia-relief-efforts-transition.html), [Helene](https://www.redcross.org/local/georgia/about-us/news-and-events/news/ruins-recovery-hope-georgia-one-year-after-hurricane-helene.html) |

| Cannot say | Say instead |
|---|---|
| How full any shelter got in a past storm | No shelter-level history exists; FEMA NSS keeps only each shelter's latest activation |
| Michael or Helene "peak" shelter population | Those are totals over the response, not one night |
| A generator is absent where the record is blank | "Not recorded" |
| A shelter is open, accessible or still exists today | Only from a live Google Maps check, per site |

## 5. Movement and traffic

| Can say | Evidence |
|---|---|
| Georgia has 27 GEMA evacuation zones, 32 contraflow intersections, GDOT's official hurricane routes and the I-16 contraflow plan | `evac_prod.ext_ga_*` |

| Cannot say | Say instead |
|---|---|
| Travel times during a past evacuation | No observed corridor travel times; g-flow's corridor model is an estimate, labelled as one |
| How many Floridians will come to Georgia | A swept assumption, not data |
