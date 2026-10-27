# Implementation Plan: Scenario History

**Branch**: `002-scenario-history` | **Date**: 2026-10-27 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/002-scenario-history/spec.md`

## Summary

Keep a browser-local history of hurricane scenarios, like a chat history.

- **Saving**: a scenario is saved the moment its track is drawn, and every change after that is saved immediately: a redraw, category, reach cutoff, a new question, or a rename.
- **Reopening**: a scenario restores its inputs (track, category, cutoff) and **re-simulates** everything with the existing feature-001 simulation code against the shelter data loaded in this session. It also starts a fresh agent conversation and lists the earlier questions, each with a one-click "Ask again".
- **What is stored**: only the user's inputs and question text. No results, no answers and no Google Maps content.
- **Where it lives**: a collapsible **History** section at the top of the chat column. A **New simulation** button replaces Reset.

This is a frontend-only change. The agent, contracts and server are untouched.

## Technical Context

**Language/Version**: TypeScript 5.x (frontend only)
**Primary Dependencies**: the existing React 18.3, Vite 5, @turf/turf and d3-geo. No new runtime dependencies.
**Storage**: browser `localStorage`, key `gsr.scenarioHistory.v1`. It holds a versioned JSON document (contracts/history-storage.schema.json). In-memory fallback when storage is unavailable (private mode, quota, disabled).
**Testing**: Vitest + React Testing Library (unit and component); Playwright e2e against the MSW mock (reload persistence, new, reopen).
**Target Platform**: desktop browsers, the same as feature 001
**Project Type**: web application (frontend change within the feature-001 structure)
**Performance Goals**:
- reopen to results in ≤ 2 s once map data has loaded (SC-004); the simulation already runs in under 100 ms
- a history write in under 5 ms
**Constraints**:
- store nothing computed and no Google Maps content (FR-003, FR-004, Constitution II)
- at most 50 scenarios (FR-014)
- must work when storage throws
**Scale/Scope**: up to 50 scenarios × a thinned track of tens to a few hundred points, plus up to roughly 50 short questions each. Well under 1 MB, far below localStorage limits.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| # | Gate | Status | How this plan meets it |
|---|---|---|---|
| 1 | Three-state flags; blank never shown as "no" (I) | ✅ PASS | Reopened scenarios reuse the feature-001 components and `simulation.ts`, unchanged. No flag is stored, so none can be stale or converted |
| 2 | Grounding acted on, attribution compliant, nothing but place IDs stored (II) | ✅ PASS | History stores no answers or Maps content (FR-003, FR-004, FR-016). A test serializes the stored document and asserts it has no result fields, `groundingMetadata`, `maps`, `uri` or `title` (SC-005). Re-asking produces fresh, attributed answers |
| 3 | Figures name their source; "reachable" documented (III) | ✅ PASS | No figures are stored. Reopened results carry the same source labels as fresh ones, plus a "Re-simulated at HH:MM from current data" label (FR-008) |
| 4 | No individual-level data; licenses (IV) | ✅ PASS | The stored inputs are a track, two settings, a name and the user's own question text, kept in their own browser and never transmitted (FR-015). The History section says "Saved in this browser only". No new datasets |
| 5 | No prohibited ranking inputs; equity audit (V) | ✅ PASS (N/A) | No new ranking. Re-simulation uses the existing receiving rule |
| 6 | Validation; never overwrite a federal record (VI) | ✅ PASS | Results are always recomputed from loaded registry data, never stored or edited. Suspect-capacity handling is unchanged |
| 7 | Brief segments; counted "could not tell you" (VII) | ✅ PASS | `CouldNotTell` is recomputed for the reopened scenario. The spec's own limitation (past results cannot be shown) is stated in the Readiness section |

**Post-design re-check**: all gates still pass. The storage schema has no field that could hold a result or Maps content, and the schema test enforces it.

## Project Structure

### Documentation (this feature)

```text
specs/002-scenario-history/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── history-storage.schema.json   # The persisted document (localStorage)
│   └── history-ui.md                 # UI behaviour contract: History section, New simulation, reopen
└── tasks.md                          # /speckit-tasks
```

### Source Code (changes within the feature-001 frontend)

```text
frontend/src/
├── lib/
│   ├── history.ts            # NEW: SavedScenario types, load/save (versioned, validated), cap/evict, default naming
│   └── simulation.ts         # + countiesAlongTrack(track): ordered GA county FIPS the track line crosses
├── state/
│   ├── store.tsx             # + history, currentScenarioId, resimulatedAt, notice; actions (see data-model)
│   └── useHistoryPersistence.ts  # NEW: loads once, writes on every history change (try/catch)
├── components/
│   ├── chat/
│   │   ├── ChatPanel.tsx     # + <HistorySection/> at the top; saves each asked question; "Ask again" list
│   │   ├── HistorySection.tsx    # NEW: collapsible list, current highlighted, rename, delete (confirm)
│   │   └── EarlierQuestions.tsx  # NEW: the reopened scenario's questions with "Ask again"
│   ├── scenario/
│   │   ├── ScenarioControls.tsx  # Reset → "New simulation"
│   │   └── AffectedSummary.tsx   # + "Re-simulated at HH:MM from current data" when reopened
│   └── …
└── lib/agentClient.ts        # + resetChatSession(): the next chat starts a fresh agent session

frontend/tests/
├── unit/history.test.ts            # load/save/validate/cap/evict/naming; storage-throws fallback; SC-005 scan
├── unit/historyReducer.test.ts     # draw → saved; redraw/category/cutoff → same id; new → no entry until draw
├── component/HistorySection.test.tsx
└── e2e/history.spec.ts             # draw → ask → reload → still listed → New → reopen → re-simulated
```

**Structure Decision**: this is a frontend-only extension of the feature-001 app. History logic lives in one pure module (`lib/history.ts`), so it is testable without React or a browser. Persistence is a single hook, the only code that touches `localStorage`. No agent, server or contract changes are needed.

## Complexity Tracking

No constitution violations, so nothing needs justifying.
