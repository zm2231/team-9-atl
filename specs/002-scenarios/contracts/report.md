# Report contract v1

One JSON shape for four scopes. The frontend renders `report`; the agent writes from it.

| Scope | Tool call | `subject` |
|---|---|---|
| `county` | `county_plan(county_fips, outlook)` → `.report` | `county_fips`, `county_name` |
| `state` | `state_plan(outlook)` → `.report` | `county_fips: null`, `county_name: "Georgia"` |
| `run` | `run_scenario(..., draws=N, run_index=i)` → `.report` | `runs: {n, seed, run_index}`, `scenario`, `county_fips` |
| `runs` | `run_scenario(..., draws=N)` → `.report` | `runs: {n, seed, run_index: null}`, `scenario`, `county_fips` |

`run` is one simulated outcome, the storm the simulation plays. `runs` aggregates N of them. Run `i` of `runs` with the same `draws` and seed is the same storm.

```
report = {
  report_version: 1,
  scope: "county" | "state" | "run" | "runs",
  subject: {...},
  season: {outlook, label, storms_per_year, note, auto?} | null,   // null for run scopes
  sections: {who_cannot_leave, power_outage, people_at_risk, where_they_would_go,
             what_to_fix, storm_history, planner_updates, could_not_tell, audit},
  source: string
}
section = {status: "ok" | "not_determined" | "not_applicable", source, figures: [figure],
           items: [object], note: string | null, reason?: string}
figure  = {key, label, unit, provenance: "registry" | "survey" | "simulated" | "live" | "planner-reported",
           source, value: number | null, range: object | null,
           range_kind: "season" | "runs" | null}
```

- A figure has a `value`, or a `range`, never both. `range_kind: "season"` ranges are `{typical, one_in_10, one_in_100}` across simulated seasons. `"runs"` ranges are `{p10, p50, p90}` across the N runs.
- Sections always appear in the order above. `not_applicable` means the scope does not have that section, for example `audit` at state scope. `not_determined` means it should exist but could not be filled; `reason` says why.
- Lacking shelter and needing transport are separate figures and are never added together.
- `items` are section-specific records: tracts and facilities, destinations, fix lists, labelled storms, worst events, audit rows. Render them as tables; every row carries its own fields.

Fixtures, from real runs on 27 Oct 2026 (Dougherty, long_run; Gulf track, category 3, `draws=20`, `run_index=7`): `frontend/tests/mocks/report.{county,state,run,runs}.fixture.json`.
