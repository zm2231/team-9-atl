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
| `needing_transport.no_vehicle` | People at risk who live in households without a vehicle and cannot drive themselves to any site | Power-dependent at risk × the county's no-vehicle share. The share is population-weighted `pct_no_vehicle` from `vulnerability_tracts_clean` (ACS) |
| `needing_transport.cannot_arrive_in_time` | Seekers whose drive time plus evacuation delay (base case) to their nearest open powered seat is longer than the time until tropical-storm winds reach their county | `receiving.sites[].arrives_before_ts_winds`, per county |

Rules:
- The two needs are reported side by side and never added together, because one person can be in both. If a single "people needing help" figure is wanted, it is `max(lacking_shelter, needing_transport)` per county as a lower bound, labelled as such.
- `no_vehicle` assumes power-dependent Medicare residents lack a vehicle at the same rate as their county. Older and disabled residents are likely less able to drive, so the figure probably understates the need. It is labelled an assumption, and its multiplier is open decision 1.
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

## 7. Open decisions

1. The `no_vehicle` multiplier: the county share alone (low), or low / base / high cases, for example 1×, 1.5×, 2×. These multipliers are not from data, so the team needs to choose and label them.
2. Whether the season view needs switches for the demo, or the single-storm view is enough. Section 4 is the extra work.
3. Whether a switched site should also drop out of the map's `affected_shelter_ids` highlighting, or stay highlighted with its marker.
