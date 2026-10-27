# C4 scenario engine: scope

Draft, 2026-10-27. The product framing is still being finalized by Zain; components below are named by what they compute.

## Problem statement

In August, with hurricane season ahead and no storm in sight, a Georgia county emergency manager has three weeks to decide what to fix before the season (C4 `README.md:143-160, 538`). The decisions that matter most for medically fragile residents (who loses power, where they can go, whether that place has a generator, whether dialysis continues) are made against storms that have not formed yet, from records that are often blank.

The engine answers three questions for her county, from data, with honest ranges:

1. **How often, and how badly, will the power go out this season?** Across every storm path that has reached Georgia, weighted by how often it happens.
2. **Who does that put at risk, and is there somewhere for them to go?** Power-dependent residents and dialysis patients, against medical shelter seats and dialysis chairs within reach.
3. **Which missing record, if filled, would change the answer most?** The fix list, ranked by how much each unknown moves the number of people left uncovered.

## In scope

| Area | What is built | Data |
|---|---|---|
| Storm climatology | Annual rates by origin (Gulf, up the Florida peninsula, Atlantic Georgia coast, overland from the west, Carolinas) from storms within 250 km of Georgia since 1950 | IBTrACS |
| Storm event set | About 2,000 simulated storms: past tracks per origin with wind-field data, intensity drawn from that origin's history, small position shifts | IBTrACS 2001+ with wind radii |
| County wind exposure | Peak wind, hours above 34/50/64 kt, closest distance, from a parametric wind field | computed |
| Outage model | Hierarchical model on 27 storms (2018-2025), 226 GA+FL counties; a new storm draws a fresh storm effect, so the range is honest | EAGLE-I, `scenario_storm_county_exposure` |
| Demand | Power-dependent residents (Medicare equipment users) and dialysis patients per county, times outage share | HHS emPOWER |
| Supply | Medical shelter seats (generator recorded vs not recorded) and dialysis stations within 100 km | `shelters_clean`, `dialysis_centers_flow_staging` |
| Season outputs | Per county: chance of losing at least 25% of customers in a season; people affected in a typical and a 1-in-10 season; people not covered | `evac_prod.scenario_season_county` |
| Fix list | Swing in uncovered people when each unknown is set low vs high | `evac_prod.scenario_fix_ranking` |
| Drill-down | `scenario(origin, category, landfall)` for one storm, with ranges and an outside-the-data flag | `agent/scenario/` |
| Agent | Two tools: `run_scenario`, `season_risk_and_fixes`; Maps grounding verifies the receiving sites | deployed agent |

## Out of scope

| Out | Why |
|---|---|
| Live operations, dispatch, any active storm | Maps grounding terms forbid emergency response; this is preparedness planning |
| Forecasting a real storm's track | NHC's job; we model plausible storms, not this week's |
| Individual people or addresses | County counts only (privacy rule) |
| Storm surge, rainfall flooding, tornado damage as separate hazards | No time to model; SLOSH zones are shown as context only |
| Grid restoration time per county | Peak outage only; restore duration is a later layer |
| Microscopic traffic simulation, individual route choice | Not calibratable in time. Movement is three layers instead (below) |
| Florida's own residents | Florida evacuees enter only as a share of Georgia seats they take |
| Nursing-home evacuate vs shelter-in-place | Generator status is unrecorded; it appears as a fix-list item, not a modelled decision |
| Wind-model accuracy beyond the parametric field | No observed wind hindcasts; the model is checked against outages instead |

## Movement and congestion

| Layer | What | Source |
|---|---|---|
| Live drive time | County to shortlisted receiving site, computed live per request, never stored (Maps terms) | Routes API |
| Evacuation congestion | Routes time x (1 + 0.15 (v/c)^4); capacity about 2,000 veh/h/lane, I-16 contraflow; load = background + county departures + Florida inflow by origin (Gulf to I-75; peninsula to I-75 and I-95; Atlantic to I-16 and I-95), low/base/high | g-flow corridor model; GDOT Milton I-75 surge as direction check |
| Storm deadline | Travel must finish before tropical-storm winds reach the county (bridges close); arrival hour from each simulated track | event set |

Season risk uses the deadline and straight-line reach; the single-storm drill-down adds live Routes and congestion.

## Longitudinal data: does change over time matter?

It matters, and there are four distinct time effects. The data can measure one of them.

| Effect | Matters? | What the data shows | How we handle it |
|---|---|---|---|
| **Grid hardening / utility practice** (outages per unit of wind falling over time) | Yes, in principle | Not detectable: across the 27 storms, held-out error has no trend by year (slope +0.002 outage share per year, correlation 0.11). Eight years is too short and the big storms cluster in 2018 and 2023-24 | Not modelled. Claim: "the model assumes the grid responds as it did in 2018-2025" |
| **Customer and population growth** (denominator drift) | Small | Shares use EAGLE-I's 2024 customer count for every year, so 2018 shares are understated by roughly the growth since then | Accepted; noted in the claims doc. Fix: year-specific EAGLE-I customer counts (`mcc_customers` exists for one year only) |
| **Data coverage changes** | Yes | EAGLE-I county data before 2018 is unreliable | Pre-2018 outages excluded from training; pre-2018 tracks still used for storm rates |
| **Climate trend in storm frequency or intensity** | Yes, for rates | Rates are averaged over 1950-2025 | Sensitivity in the fix list: rates from 1950-2025 vs 2000-2025. We do not claim a trend |
| **Within-storm dynamics** (soil saturation, storms back to back, Helene into Milton) | Yes for single events | 54 Milton rows were carryover from Helene; we flag carryover and drop it | Treated as label noise. Back-to-back storms in one season are counted as separate events, not compounding |
| **Panel structure** (same counties, storm after storm) | Yes | County identity explains about 20% of outage variance | The model's county effect pools each county's history, so a county that repeatedly over-performs its wind gets credit, shrunk toward the average |

The panel structure is the one place longitudinal data pays off now: each county has up to 27 storms, and the hierarchical model uses that history directly. The rest are named as assumptions rather than modelled, because the data cannot separate them from storm-to-storm noise.
