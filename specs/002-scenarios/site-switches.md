# Scenarios: switching sites on and off, and shelter vs transport need

Draft for team review. Builds on PR #10 (`run_scenario`, the season tables) and [frontend.md](frontend.md).

## 1. What the operator can do

Two switches, on any medical shelter (`shelter_id`) or dialysis centre (`ccn`):

| Switch | Effect in the model | Planning question it answers |
|---|---|---|
| Off | The site takes nobody: no seats, no chairs | "What if this shelter doesn't open, or floods?" |
| Assume generator | The shelter's seats count as powered, as if its generator were recorded `YES` | "What if we confirm or install a generator here?" This is the second-largest unknown in the fix ranking (817 to 2,174 people uncovered) |

Sites with no switch set keep their registry values.

## 2. Inputs

| Where | Field | Notes |
|---|---|---|
| `CONTEXT v1` | `scenario.site_overrides: {off: string[], assume_generator: string[]}` | Optional field, so `CONTEXT v1` needs no version bump. The map sends it whenever any switch is set |
| `run_scenario` arguments | `sites_off: list[str]`, `assume_generator: list[str]` | For chat ("what if the Brunswick shelter is closed?"). Merged with the context values |
| `season_county_risk` arguments | same two | See section 4 |

IDs that match no site are returned in `ignored_ids` rather than raising an error.

## 3. Outputs: two different needs

Today `receiving.shortfall` and the season table's `uncovered` mix two different problems. They are split as follows:

| Field | Meaning | Computed from |
|---|---|---|
| `lacking_shelter.no_powered_seat` | Power-dependent residents expected to seek a powered seat who find no generator-recorded seat they can reach before tropical-storm winds | Relocation share × power-dependent at risk, minus seats allocated within reach (`allocate` in `build_season.py`; `shortfall` in `receiving.py`) |
| `lacking_shelter.no_dialysis_chair` | Dialysis patients displaced (county at 50%+ outage, or centre in the surge zone) who find no chair within reach | As in `build_season.py` today |
| `needing_transport.no_vehicle` | People at risk who live in households without a vehicle and cannot drive themselves to any site | Power-dependent at risk × the county's no-vehicle share among households headed by someone 65 or older (ACS 2023 5-year table B25045, by county). The all-household share is the low case |
| `needing_transport.cannot_arrive_in_time` | Seekers whose drive time plus evacuation delay (base case) to their nearest open powered seat is longer than the time until tropical-storm winds reach their county | `receiving.sites[].arrives_before_ts_winds`, per county |

Rules:
- The two needs are reported side by side and never added together, because one person can be in both. If a single "people needing help" figure is wanted, it is `max(lacking_shelter, needing_transport)` per county as a lower bound, labelled as such.
- `no_vehicle` uses the 65+ householder rate because emPOWER counts Medicare beneficiaries, who are mostly 65 or older. In Georgia, 8.6% of households headed by someone 65+ have no vehicle, against 5.9% of all households. By county, the 65+ rate is a median 1.31× the all-household rate (10th-90th percentile 0.63× to 1.93×). This replaces a hand-set multiplier.
- Both rates still undercount people who live in a household with a car but cannot drive (because of disability, or because the car leaves with someone else). ACS has no county table crossing vehicles with disability. National travel data reports a higher zero-vehicle rate for 65+ adults with travel-limiting disabilities; that figure is not verified here, and it is a candidate for a stated high case.
- Need for ambulance or stretcher transport is not in our data. It goes in "What we could not tell you".

With switches set, every figure above is returned twice: `baseline` (registry values) and `with_switches`, plus `delta`. The operator sees what the change does, not just the new total.

## 4. Season view with switches

The season tables are precomputed, so a switch cannot change them directly. Plan:

1. In `build_season.py`, save each simulated event's per-county seekers and displaced dialysis patients to `scenario/data/season_events.npz`. This is 2,000 events × 159 counties × 2 values as float32, about 2.5 MB, inside the 5 MB data budget. Also save the event-to-season index.
2. `season_county_risk` with switches reruns only the allocation step (`allocate` with the site mask) over the saved events in numpy, then recomputes typical and 1-in-10 values. Target: under 2 s. Measure it before promising it.
3. Without switches it reads BigQuery as today.

## 5. Frontend

| Component | Change |
|---|---|
| `ShelterDetails.tsx` | Two toggles on a selected medical shelter or dialysis centre: "Off in scenario" and "Assume generator" (shelters only). A switched site gets a marker on the map |
| `state/store.tsx` | `siteOverrides: {off: Set<string>, assume_generator: Set<string>}`, a `toggleSite` action, and a reset. Changing a switch clears the stored modelled result, as a new track does |
| `ChatPanel.tsx` | Sends `scenario.site_overrides` in `CONTEXT v1` |
| `ReceivingList.tsx` / `AffectedSummary.tsx` | Show "Lacking shelter" and "Needing transport" as two separate rows. With switches set, show baseline → with switches (±delta) |
| Label | "Operator what-if: N sites switched" on every figure that used switches |

## 6. Tests

- Switching off every site within reach of a county raises `no_powered_seat` to equal the number of seekers.
- Assume generator on an `UNRECORDED` shelter lowers `no_powered_seat` by at most its seats.
- An unknown ID lands in `ignored_ids`, and nothing raises.
- `baseline` with no switches equals today's output.
- The season rerun with no switches reproduces the BigQuery table values.

## 7. Prior art

| Practice | What it does | What we take from it |
|---|---|---|
| Hurricane Evacuation Studies (USACE, FEMA, NOAA; Georgia's was updated by Dewberry for the USACE Savannah District) | A batch study per state, every few years. It estimates evacuating population, public shelter demand, the transportation-dependent population, and clearance times, from behavioral surveys and Census data | The batch side: the season build plays this role. NHC training gives HES public shelter planning rates of 3-8% of evacuees on the coast and 10% inland, which are a reference point for our 10/20/40% relocation share among power-dependent residents |
| HURREVAC (FEMA, NHC) | An operational tool that applies the HES numbers to a live forecast, with decision timelines and clearance times | The one-off side: `run_scenario` with switches. We use it for planning only, because Maps terms rule out emergency response |
| Transit-dependent population estimates (post-Katrina research; GAO-07-44) | Zero-vehicle households from Census/ACS, with errors of up to ±30% at small scales. The GAO found those left behind were largely older, disabled and low-income people without cars | Use ACS by age, and report the need as a range, not a point |
| HAZUS (FEMA) | Reports displaced households and short-term shelter requirements as separate outputs | Supports reporting "lacking shelter" and "needing transport" separately |

## 8. One-off runs, batch runs, and learning

| Mode | Who runs it | What it does |
|---|---|---|
| One-off | The agent, at the operator's request | `run_scenario` with the operator's switches: "what if this shelter is off, or that one has a generator?" Answers in seconds |
| Batch | The season build, offline | Runs every simulated storm across the whole state and ranks places and unknowns (`scenario_season_county`, `scenario_fix_ranking`). Named switch sets ("all unrecorded generators confirmed", "coastal shelters closed") are precomputed here rather than recomputed live |
| Learning (later) | After each season | Add the season's storms and EAGLE-I county outages to the labels, refit the hierarchical model (new storms update the storm-effect spread and county effects), rerun the back-test, and publish the change in coverage. Shelter use and live-check results recorded during the season can later calibrate the relocation share. This needs storage of our own outcomes, not of Maps or Routes results |

## 9. Open decisions

1. Vehicle access: proposal is ACS 65+ householder share as base and the all-household share as low, as above. Whether to add a disability high case once its source is verified.
2. Season view switches: proposal is that the demo uses live switches in the single-storm view only, and the batch precomputes named switch sets (section 8), so section 4's live rerun waits.
3. Map highlighting: proposal is that a switched-off site shows as "off in this scenario" (its own marker) rather than "affected", since affected means hit by the storm.
