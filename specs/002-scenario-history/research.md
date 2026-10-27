# Research: Scenario History

Phase 0 decisions for [plan.md](plan.md). Technical Context had no open unknowns. These record the
choices and the alternatives considered.

## R1. Where history is stored (Clarification Q1: this browser only)

- **Decision**: `window.localStorage`, key `gsr.scenarioHistory.v1`, holding one JSON document
  `{version: 1, scenarios: SavedScenario[]}`. Every read and write is wrapped in `try/catch`. If
  storage is unavailable or throws (private mode, quota, disabled), history keeps working in
  memory for the session, and the History section shows "History can't be saved in this browser".
- **Rationale**: it is synchronous and small. It survives reloads and closed tabs (SC-007), and it
  never leaves the device (FR-015).
- **Alternatives considered**:
  - IndexedDB: more capacity than is needed, and an asynchronous API for under 1 MB of data.
  - sessionStorage: lost when the tab closes, which fails SC-007.
  - Server-side storage: rejected in the Clarifications (Q1 → A).

## R2. When writes happen (Clarification Q3 on save timing: continuously)

- **Decision**: the store holds `history` in memory. One `useHistoryPersistence` hook loads it once
  on start and writes the whole document after every change to `history`. A change happens when
  a track is drawn or redrawn, the category or cutoff changes, a question is asked, a scenario is
  renamed or deleted, or a scenario is opened. Writes are synchronous and never debounced, so a
  reload straight after a change keeps it.
- **Rationale**: there is a single writer and no partial updates. The full document is under
  1 MB and serializes in milliseconds.
- **Alternatives considered**: debounced writes. Rejected because a reload within the debounce
  window would lose the latest change, which breaks SC-007.

## R3. What a saved scenario contains (FR-002, FR-003, FR-004, FR-016)

- **Decision**: `id`, `name`, `nameIsCustom`, `track` (the already-thinned GeoJSON `LineString` or
  `Point`), `category`, `cutoff_km`, `questions: {text, asked_at}[]`, `created_at`,
  `last_opened_at`, `updated_at`. That's all.
- **Rationale**: these are the user's inputs only. The JSON Schema uses
  `additionalProperties: false` at every level, so results or Maps content cannot be added by
  accident. A unit test serializes a fully used history and checks it for forbidden keys (SC-005).
- **Alternatives considered**: storing results as a cache. Rejected because the spec requires
  re-simulation, and stored results could go stale.

## R4. Re-simulation (FR-007, FR-008, SC-003)

- **Decision**: reopening dispatches `openScenario(id)`, which puts the saved
  `{track, category, cutoff_km}` into `state.scenario`. The existing `ScenarioProvider` then
  recomputes the band, the affected set and the receiving list with `simulation.ts`, exactly as
  for a newly drawn track. `state.resimulatedAt` is set to now, and `AffectedSummary` shows
  "Re-simulated at HH:MM from current data".
- **Rationale**: there is one code path, so unchanged inputs and unchanged data give identical
  results (SC-003), and changed data shows up automatically.
- **If map data is not loaded yet**: the scenario inputs are applied anyway, and
  `ScenarioProvider` computes results as soon as `mapData` becomes ready (edge case).

## R5. Default names (FR-012) and the counties shown in the list

- **Decision**: add `countiesAlongTrack(track)` to `simulation.ts`.
  1. Sample the track every 2 km (`turf.along`), or take the single point for a click.
  2. Find the Georgia county that contains each sample.
  3. Remove consecutive duplicates, giving an ordered list of county FIPS codes.
- **Default name**: `"Cat {c} · {first} → {last}"`, or `"Cat {c} · {only}"` for one county, or
  `"Cat {c} · offshore"` when no county is crossed.
- **Updates**: the name is recomputed on redraw or category change while `nameIsCustom` is false.
  After a rename, the user's name is kept (spec Assumptions).
- **List entry**: shows `countiesAlongTrack` names, abbreviated to the first three plus "+N".

## R6. Agent conversation on New simulation and on reopen

- **Decision**: add `resetChatSession()` to `agentClient.ts`. It sets the module-level
  `chatSession` promise back to `null`, so the next question creates a new agent session.
  "New simulation" and "open scenario" both call it and clear `state.chat`.
- **Rationale**: the agent is not given earlier answers (spec Assumptions). A fresh session keeps
  the conversation from mixing two scenarios' contexts.

## R7. Cap and eviction (FR-014)

- **Decision**: when a new scenario would make 51, remove the scenario with the oldest
  `last_opened_at`, never the current one. Set `state.notice` to
  "History is full: removed '<name>' (least recently opened)". The History section shows the
  notice once, and it can be dismissed.

## R8. Accessibility (deferred from clarify)

- **Decision**: reuse the Details panel pattern.
  - The History header is a `<button aria-expanded aria-controls>`.
  - The list is a `<ul>`. Each entry is a button with `aria-current="true"` when it is the
    current scenario.
  - Rename is an inline `<input>` (Enter to save, Esc to cancel).
  - Delete asks for confirmation inline ("Delete 'name'? Delete / Cancel"), not with a native
    `confirm()`, so it is testable and keyboard friendly.

## Verification (2026-10-27)

- **Offline**: all checks pass. That covers the type check and lint, 80 Vitest tests (unit and component), the production build, and Playwright on the mock agent: `smoke.spec.ts` plus both `history.spec.ts` tests (reload and New simulation; reopen and re-simulate).
- **Real agent** (5173 → 8000, `evac_prod`): automated walk-through in a separate browser profile.
  - Map ready: 0.1 s. Drew the Glynn Category 3 track.
  - Asked "For this hurricane, what is the current shelter capacity?". It answered with no error, citing "FEMA NSS registry · shelters_clean".
  - Reloaded: History had 1 entry. Reopened it: the band was back in 0.07 s (SC-004 target 2 s), with the re-simulated note visible and the earlier question listed.
- **Implementation decisions from `/speckit-analyze`**:
  - H1: entries are validated one at a time, so one bad scenario never discards the rest. Question text is capped at 2,000 characters. An unreadable document is copied to `gsr.scenarioHistory.v1.bak` before it can be overwritten.
  - H2: Earlier questions stays available (collapsible) for the whole reopened session.
  - M2: a "Results re-simulated at …" note in the chat column, as well as in the Details panel.
  - M1: left as specified. After a reload, nothing is current until a scenario is picked from History.
  - M4: the History note says question text is saved in this browser.
