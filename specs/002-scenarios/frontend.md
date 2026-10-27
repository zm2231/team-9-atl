# Scenarios: frontend spec

For the UI team. Builds on PR #10, which adds the agent tools. Tool contract: [contracts/run-scenario.md](contracts/run-scenario.md). Overview of every change: [plan.md](plan.md).

Nothing here is required for PR #10 to work. Once it merges, any `county_fips` or `shelter_id` in a scenario tool result is already highlighted by `collectReferences`. This spec covers showing the modelled numbers themselves.

A real `run_scenario` result is in `frontend/tests/mocks/runScenario.fixture.json`. It is a category 4 track drawn from the Gulf through Albany, with Dougherty (13095) selected. Routes was off when it was generated, so drive times are `straight_line`; Maps terms do not allow storing live Routes results.

## Wording rules

These come from the claims doc, and the agent follows the same ones.

| Shown | Label |
|---|---|
| Any modelled range | "Modelled · scenario range from 27 past storms" |
| Today's band, its affected counties and receiving list | "Illustrative scenario, not a forecast" (unchanged) |
| `scenario.likelihood` | "Storms like this since 1950: about once every N years". Never "chance of this storm" or "forecast" |
| `support == "outside_labeled_support"` | Badge: "Outside the data: no past storm like this has trustworthy outage records" |
| `status` contains `censored_count` | "At least N" (emPOWER suppresses small counts) |
| `drive_minutes.status == "straight_line"` | "≈ N min (straight-line estimate)" |
| `drive_minutes.status == "live"` | "N min (live, Google Routes)" |

## Types (`lib/types.ts`)

```ts
export interface Band { p10: number; p50: number; p90: number }

export interface ScenarioCounty {
  county_fips: string;
  county_name: string;
  outage_share: Band;
  peak_wind_kt: number;
  hours_ts_winds: number;
  ts_winds_arrive_h: number | null;
  power_dependent: { residents: number; at_risk: Band };
  oxygen_users: { residents: number; at_risk: Band };
  home_health_users: { residents: number; at_risk: Band };
  dialysis_patients: { patients: number; centres: number; stations: number; centres_down: boolean };
  nursing_home_beds: number;
  assisted_living_beds: number;
  in_surge_zone: { shelter_ids: string[]; dialysis_ccns: string[] };
  status: ("modelled" | "outside_labeled_support" | "censored_count")[];
}

export interface ReceivingSite {
  kind: "medical_shelter" | "dialysis_centre";
  shelter_id?: string;
  seats?: number | null;
  ccn?: string;
  stations?: number | null;
  name: string | null;
  county_fips: string | null;
  generator: "YES" | "NO" | "UNRECORDED";
  straight_line_km: number;
  drive_minutes: { value: number; status: "live" | "straight_line" };
  evacuation_delay_minutes: { low: number; base: number; high: number };
  corridor: string | null;
  arrives_before_ts_winds: boolean | null;
}

export interface Likelihood {
  matching_storms: number;
  years: [number, number];
  per_year: number;
  return_period_years: number | null;
  p_at_least_one_per_season: number;
  per_year_range80: [number, number];
  example_storms: string[];
}

export interface ModelledScenario {
  affected_county_fips: string[];
  affected_shelter_ids: string[];
  receiving_top: string[];
  scenario: {
    source: "drawn_track" | "matched_past_storms";
    origin: string;
    category: number | null;
    month: number;
    past_storms_used: string[];
    match: { matched: number; share_reaching_georgia_100km: number } | null;
    likelihood: Likelihood;
    support: "within_labeled_support" | "outside_labeled_support";
    range_label: string;
    assumptions: Record<string, string | number>;
  };
  statewide: {
    counties_affected: Band;
    counties_affected_in_most_draws: number;
    power_dependent_at_risk: Band;
    oxygen_users_at_risk: Band;
    dialysis_patients_at_risk: Band;
    facility_beds_exposed: Band;
  };
  counties: ScenarioCounty[];
  receiving: {
    sites: ReceivingSite[];
    shortfall: { seeking_powered_seat: number; generator_recorded_seats_in_time: number; uncovered: number };
    drive_time_source: "live" | "straight_line";
  } | null;
  source: string;
}
```

A status result (`{status, message, source}`, with no `scenario` key) is not a `ModelledScenario`, so do not store it. The agent explains it in chat.

## State

| Where | Change |
|---|---|
| `lib/chatFold.ts` | Add `modelled?: ModelledScenario` to `Fold`. In `foldEvent`, when `part.functionResponse.name === "run_scenario"` and the response has a `scenario` key, set `modelled` to the response. The last one in a turn wins |
| `state/store.tsx` | `State.modelled: ModelledScenario \| null`. Action `{ type: "modelledScenario"; result: ModelledScenario }`. `setTrack`, `setCategory` and `resetScenario` clear it, because a new track makes the old result stale |
| `components/chat/ChatPanel.tsx` | After the stream ends, dispatch `modelledScenario` when `acc.modelled` is set, alongside the existing `liveCheck` dispatches |
| `state/scenario.tsx` | When `state.modelled` is set, `affected_county_fips` and `affected_shelter_ids` come from it, and the band stays as the drawn shape. Without it, keep today's band intersection |

## Components

| # | Component | Behaviour | Data |
|---|---|---|---|
| F2 | `CountyLayer.tsx` | When `modelled` is set, fill each county in `modelled.counties` on a 5-step sequential ramp by `outage_share.p50`: <5%, 5-10%, 10-25%, 25-50%, ≥50%. Counties not in the list stay unfilled. The hover card shows "Outage p10-p90: a%-b% (median c%)", "Power-dependent at risk: p10-p90", and tropical-storm winds arriving in N h | `counties[]` |
| F2 | `Legend.tsx` | Ramp swatches with the "Modelled · scenario range from 27 past storms" label. Only shown when `modelled` is set | |
| F4 | `AffectedSummary.tsx` | When `modelled` is set, add a card above the existing one. People at risk statewide (power-dependent, oxygen, dialysis, facility beds), each as "median (p10-p90)". Counties affected: `counties_affected_in_most_draws`. Likelihood line. `past_storms_used` when the source is `matched_past_storms`, with `match.share_reaching_georgia_100km` as "N% of these reached Georgia". The outside-the-data badge when the scenario is outside the data | `statewide`, `scenario` |
| F5 | `ReceivingList.tsx` | When `modelled.receiving` exists, list its `sites` in the given order: kind icon, name, seats or stations, generator flag (yes / no / not recorded), drive time with its status label, "+low/base/high min evacuation traffic", and a deadline marker. The marker shows ✓ when `arrives_before_ts_winds` is true, ✗ when false, and "unknown" when null. Under the list: "N seeking a powered seat · M generator-recorded seats reachable in time · K uncovered". Otherwise keep today's list | `receiving` |
| F6 | `MapView.tsx` | Surge layer for the chosen category from `agent/readiness_agent/scenario/data/surge_zones.geojson` (1.4 MB; copy it to `frontend/public/` or import it). Toggle, off by default. Label: "NOAA SLOSH maximum of maximums, Category N" | static file |
| F7 | `CouldNotTell.tsx` | When `modelled` is set, add the outside-the-data note, any `censored_count` counties, and "Drive times are straight-line estimates" when `drive_time_source` is `straight_line` | `scenario`, `counties`, `receiving` |
| F8 | `ScenarioControls.tsx` | Position mode: click the map to set a point, then pick a heading (8-way) and a month. A "What if a storm is here?" button sends a chat question that contains lat, lon, heading and date in words, for example "What if a storm is at 25.5, -86.5 heading north on 2026-09-15?". No `CONTEXT v1` change is needed | none |
| F9 | Season view | Waiting on the lead's decision: a chat-only tool, or an optional `season` block in `map-data` | `season_county_risk` |

## Tests

| Test | Checks |
|---|---|
| `tests/unit/chatFold.test.ts` | Folding the fixture as a `run_scenario` `functionResponse` sets `modelled`. A `{status, message, source}` response does not set it. A second `run_scenario` in the same turn replaces the first |
| `tests/unit/store.test.ts` | `modelledScenario` stores the result, and `setTrack`, `setCategory` and `resetScenario` clear it |
| `tests/component/AffectedSummary.test.tsx` | With the fixture, shows the median with its range for power-dependent residents at risk, the likelihood line, and no outside-the-data badge. With `support` changed to outside, shows the badge |
| `tests/component/ReceivingList.test.tsx` | With the fixture, every drive time is labelled "straight-line estimate" and the shortfall line renders. With no `receiving`, today's list renders |
| `tests/component/CountyLayer.test.tsx` | Dougherty (13095) gets the fill class for its `p50` band |

## Order

F1 (state) → F2 → F4 → F5 first, so the modelled result reaches the map and the side panel. Then F7, F6 and F8. F9 comes after the lead's decision.
