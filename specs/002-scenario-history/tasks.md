# Tasks: Scenario History

**Input**: Design documents from `/specs/002-scenario-history/`
**Prerequisites**: [plan.md](plan.md), [spec.md](spec.md), [research.md](research.md), [data-model.md](data-model.md), [contracts/](contracts/), [quickstart.md](quickstart.md)

**Tests**: Included where the spec's success criteria need automated proof:
- SC-002 / SC-003: restore and re-simulation fidelity
- SC-005: nothing computed and no Maps content stored
- SC-006 / SC-007: no loss on New simulation or reload

**Scope**: frontend only (`frontend/`). There are no agent or server changes.

**Organization**: US1 and US2 are P1, US3 is P2 (spec.md).

## Format: `[ID] [P?] [Story] Description`

## Path Conventions

- Source: `frontend/src/`
- Tests: `frontend/tests/unit`, `frontend/tests/component`, `frontend/tests/e2e`

---

## Phase 1: Setup

- [X] T001 Confirm a green baseline before changing anything: run `cd frontend && npx tsc -b && npx vitest run`. Every existing test must pass. Record the count in this task's checkbox note. *(48 passed, 2026-10-27.)*

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: The pure history module, the track-to-county helper, store state and actions, and persistence. Every story depends on these.

- [X] T002 [P] Create `frontend/src/lib/history.ts` (pure, with no React and no `window` access). It exports:
  - **Constants**: `STORAGE_KEY = "gsr.scenarioHistory.v1"`, `MAX_SCENARIOS = 50`, `MAX_QUESTIONS = 100`
  - **Types**: `SavedQuestion { text: string; asked_at: string }` and `SavedScenario { id; name; nameIsCustom; track: LineString | Point; category: Category; cutoff_km: number; questions: SavedQuestion[]; created_at; updated_at; last_opened_at }`, exactly matching `specs/002-scenario-history/contracts/history-storage.schema.json`
  - `isValidDocument(x: unknown): x is { version: 1; scenarios: SavedScenario[] }`: a hand-written check mirroring the schema. It rejects any unknown key at any level (`additionalProperties: false`), more than 50 scenarios, a category outside 1–5, a cutoff outside 25–200, and names over 80 characters
  - `loadHistory(storage: Pick<Storage, "getItem"> | null): { scenarios: SavedScenario[]; available: boolean }`:
    - `available` is false when `storage` is null or `getItem` throws
    - returns an empty list, and never throws, on missing or invalid JSON
    - sorts by `last_opened_at` descending
  - `saveHistory(storage: Pick<Storage, "setItem"> | null, scenarios: SavedScenario[]): boolean`: writes `JSON.stringify({version: 1, scenarios})`, and returns false if storage is null or `setItem` throws
  - `capHistory(list: SavedScenario[], currentId: string | null): { list: SavedScenario[]; evicted: SavedScenario | null }`: while the length is over `MAX_SCENARIOS`, it removes the entry with the oldest `last_opened_at` whose id is not `currentId`
  - `defaultName(category: Category, countyNames: string[]): string`, giving:
    - `"Cat N · First → Last"` when there are two or more counties
    - `"Cat N · Only"` for one county
    - `"Cat N · offshore"` for none
  - `abbreviateCounties(names: string[]): string`: the first three joined by ", ", plus " +N" when there are more
  - `relativeTime(iso: string, now: Date): string`: e.g. "just now", "5 min ago", "2 h ago", "Oct 27"
- [X] T003 [P] Add `countiesAlongTrack(track: LineString | Point): string[]` to `frontend/src/lib/simulation.ts`:
  1. For a `Point`, return the GA county that contains it (`booleanPointInPolygon` over `gaCounties.features`), or `[]`.
  2. For a `LineString`, sample a point every 2 km with `turf.length` and `turf.along`, always including both endpoints.
  3. Map each sample to the containing GA county FIPS, skipping samples that are offshore or outside Georgia.
  4. Drop consecutive duplicates and return the ordered FIPS list.

  Import `gaCounties` from `./geo`.
- [X] T004 [P] Add `export function resetChatSession(): void { chatSession = null; }` to `frontend/src/lib/agentClient.ts`, with a comment explaining that the next question starts a fresh agent session (research R6).
- [X] T005 Extend `frontend/src/state/store.tsx` per data-model.md §Store additions and §State transitions.
  - **State**: add `history: SavedScenario[]` (initially `[]`), `currentScenarioId: string | null`, `resimulatedAt: string | null`, `historyAvailable: boolean` (initially `true`), `notice: string | null`.
  - **Actions** (each takes an optional `now?: string`, defaulting to `new Date().toISOString()`, so tests are deterministic):
    - `historyLoaded { scenarios; available }`
    - `newSimulation`: **replaces `resetScenario`**. It clears `scenario`, `chat` and `highlight`, and sets `resimulatedAt = null` and `currentScenarioId = null`. Update the one caller in `ScenarioControls.tsx` in T009.
    - `openScenario { id }`
    - `renameScenario { id; name }` (trim; ignore empty names)
    - `deleteScenario { id }`
    - `dismissNotice`
  - **Changes to existing cases**:
    - `setTrack`: if `currentScenarioId` is null, create a SavedScenario with `id = crypto.randomUUID()`, the default name from `defaultName(category, countiesAlongTrack(track).map(fips → countyNames.get(fips)))`, `questions: []` and all timestamps = now, then prepend it and run `capHistory`. If something was evicted, set `notice = "History is full: removed '<name>' (least recently opened)"`. Otherwise, replace the current entry's `track` and `updated_at`, and recompute its name unless `nameIsCustom`. Always set `resimulatedAt = null`.
    - `setCategory` / `setCutoff`: also update the current entry (same id), recomputing the default name for a category change unless `nameIsCustom`.
    - `chatStart`: when `currentScenarioId` is set, append `{ text: exchange.question, asked_at: now }` to that entry (keep only the last `MAX_QUESTIONS`).
    - `openScenario`: set `scenario = {track, category, cutoff_km}` from the entry, `currentScenarioId = id`, entry `last_opened_at = now`, `resimulatedAt = now`, and clear `chat`, `highlight`, `selectedShelterId` and `drawing`.
    - `deleteScenario`: remove the entry. If it was current, also apply the `newSimulation` effects.
  - Import `countyNames` from `../lib/geo`.
- [X] T006 Create `frontend/src/state/useHistoryPersistence.ts`, the only code that touches `window.localStorage`:
  - read `localStorage` inside `try/catch`, treating a throw as `null` storage
  - on mount, dispatch `historyLoaded(loadHistory(storage))` exactly once
  - after that, a `useEffect` on `state.history` (skipping the run before loading has finished) calls `saveHistory`. If it returns false, dispatch `historyLoaded` with `available: false` and the current list, so the UI can say history can't be saved.
  - call the hook once at the top of `App` in `frontend/src/App.tsx`
- [X] T007 [P] Write `frontend/tests/unit/history.test.ts` against T002, using a fake `Storage` object:
  - (a) save then load round-trips and sorts by `last_opened_at`
  - (b) invalid JSON, a wrong version or an unknown key yield an empty list and do not throw
  - (c) `getItem` / `setItem` throwing gives `available: false` and a `false` return
  - (d) `capHistory` evicts the least recently opened, never the current one
  - (e) `defaultName` covers all three shapes
  - (f) `abbreviateCounties` with 5 names gives "A, B, C +2"
  - (g) **SC-005**: build a fully used history (draw, questions, rename), serialize it, and assert that `JSON.stringify` contains none of `"groundingMetadata"`, `"maps"`, `"uri"`, `"title"`, `"receiving"`, `"affected"`, `"band"`, `"capacity"`, `"Google Maps"`
- [X] T008 [P] Add `countiesAlongTrack` cases to `frontend/tests/unit/simulation.test.ts`:
  - the existing `glynnTrack` (offshore `[-80.8, 31.0]` to inland `[-82.0, 31.4]`) returns a non-empty list, in order from the coast inland, that includes `13127` (Glynn) and has no consecutive duplicates. Reversing the track's coordinates reverses the list.
  - a `Point` inside Cobb returns `["13067"]`
  - a sea-only track returns `[]`

**Checkpoint**: `npx vitest run` passes, and the history module and helpers are proven without UI.

---

## Phase 3: User Story 1 - Keep a scenario when starting a new one (Priority: P1) 🎯 MVP

**Goal**: A scenario is saved the moment its track is drawn and on every change, survives reloads, and **New simulation** starts a fresh one. The list is visible in the chat column.

**Independent Test**: Draw a track and ask a question. Reload: it's still listed with its question. Press New simulation: the map clears and the entry remains. Redraw, category and cutoff never add entries.

- [X] T009 [US1] In `frontend/src/components/scenario/ScenarioControls.tsx`, replace the `Reset` button with **`New simulation`**:
  - on click, dispatch `newSimulation` and call `resetChatSession()`
  - it is visible when `state.scenario` or `state.currentScenarioId` is set
  - leave the draw toggle, category picker and slider unchanged; they update the current scenario through the reducer
- [X] T010 [US1] Create `frontend/src/components/chat/HistorySection.tsx` (contracts/history-ui.md §History section; list only, with management added in US3):
  - **Header**: `<button aria-expanded aria-controls="history-list">` showing `History ({n}) ▸` when collapsed and `▾` when expanded, collapsed by default (local `useState`)
  - **Expanded**: `<ul id="history-list">` of `state.history`, newest `last_opened_at` first. Each item is `<button data-testid="history-item">` showing the name, a `Cat {n}` badge, `abbreviateCounties(countiesAlongTrack(track) → names)` and `relativeTime(last_opened_at, now)`, with `aria-current="true"` plus the class `history-item--current` when `id === state.currentScenarioId`
  - **Empty list**: "No saved scenarios yet. Draw a hurricane track to start one."
  - **Footer**: `state.historyAvailable ? "Saved in this browser only" : "History can't be saved in this browser"`
  - item clicks are wired in US2 (T014)
  - add styles to `frontend/src/styles/app.css`: `.history`, `.history__header`, `.history-item`, `.history-item--current` (left border `var(--live)`), and `.history__note` (muted, 11px)
- [X] T011 [US1] Mount `<HistorySection />` at the top of the chat column in `frontend/src/components/chat/ChatPanel.tsx`, above the `chat__log` div, and make sure it doesn't scroll away with the log. Confirm `ask()` dispatches `chatStart` with only the question text, so the `CONTEXT v1` JSON is never saved (data-model SavedQuestion).
- [X] T012 [P] [US1] Write `frontend/tests/unit/historyReducer.test.ts` against `reducer` from `store.tsx`, with fixed `now` values:
  - (a) `setTrack` with no current scenario creates one entry with a default name and makes it current
  - (b) a second `setTrack`, `setCategory(4)` and `setCutoff(120)` keep the same single id and update the fields, and the name changes with the category while not custom
  - (c) `chatStart` appends the question text only
  - (d) `newSimulation` keeps the entry, sets `currentScenarioId` to null and clears `scenario` and `chat`, and no entry exists for the next scenario until `setTrack`
  - (e) with 50 entries, a new `setTrack` evicts the least recently opened, sets `notice` and never evicts the current one
  - (f) **SC-006**: 20 scripted `setTrack → chatStart → newSimulation` cycles leave 20 entries
- [X] T013 [US1] Write `frontend/tests/e2e/history.spec.ts`, test "survives reload and New simulation" (mock agent, same setup as `smoke.spec.ts`):
  1. Draw the Glynn track (copy the drag helper from `smoke.spec.ts`), then open History: there is 1 `history-item` with `aria-current="true"` whose name starts with "Cat 3 ·".
  2. Ask a question.
  3. `page.reload()`, then wait for the shelters. History still has 1 item.
  4. Click **New simulation**: the map has no `.band`, and History still shows 1 item with no `aria-current`.
  5. Assert `localStorage["gsr.scenarioHistory.v1"]` (via `page.evaluate`) contains the question text and does not contain "Google Maps" or "groundingMetadata" (SC-005, SC-007).

**Checkpoint**: Nothing is lost on reload or New simulation. This is the MVP.

---

## Phase 4: User Story 2 - Reopen a past scenario and see current results (Priority: P1)

**Goal**: Clicking an entry restores its track, category and cutoff. All results are re-simulated and labelled as such, and earlier questions can be asked again.

**Independent Test**: Save scenario A, start B, then reopen A. The track, category and cutoff match, "Re-simulated at …" shows, the lists are recomputed, and Earlier questions offers Ask again.

- [X] T014 [US2] In `frontend/src/components/chat/HistorySection.tsx`, wire item clicks: when `id !== state.currentScenarioId`, dispatch `openScenario({ id })` and call `resetChatSession()`. Clicking the current item does nothing. Disable items while a chat answer is streaming (`state.chat.some(c => c.status === "pending" || c.status === "streaming")`).
- [X] T015 [P] [US2] In `frontend/src/components/scenario/AffectedSummary.tsx`, when `state.resimulatedAt` is set, render `<div className="small" data-testid="resimulated">Re-simulated at {HH:MM} from current data</div>` under the illustrative badge (FR-008).
- [X] T016 [US2] Create `frontend/src/components/chat/EarlierQuestions.tsx`. It takes the props `questions: SavedQuestion[]`, `onAsk(text)` and `disabled`, and renders the card `data-testid="earlier-questions"` with the heading "Earlier questions in this scenario", one row per question (the text plus `relativeTime(asked_at)`), and an **Ask again** button per row. Then in `ChatPanel.tsx`, render it at the top of `chat__log` when the current scenario has questions, `state.resimulatedAt` is set, and `state.chat` is empty, passing `ask` as `onAsk`. It hides once a question has been asked in this session.
- [X] T017 [P] [US2] Write `frontend/tests/component/HistorySection.test.tsx`, rendering inside `StoreProvider` and `ScenarioProvider` with `initial` history of 2 scenarios:
  - collapsed by default with "History (2)"
  - expanding lists 2 items newest first
  - the current one has `aria-current="true"`
  - clicking the other dispatches open: `currentScenarioId` changes, which you can observe via the `aria-current` move
  - the footer says "Saved in this browser only", and with `historyAvailable: false` it says "History can't be saved in this browser"
- [X] T018 [P] [US2] Write `frontend/tests/component/EarlierQuestions.test.tsx`: it renders each question and clicking Ask again calls `onAsk` with the exact text.
- [X] T019 [US2] Add the test "reopen re-simulates" to `frontend/tests/e2e/history.spec.ts`:
  1. Draw Glynn, set Cat 4, set the slider to 120, and ask a question.
  2. Press New simulation, then draw a second track across Chatham.
  3. Open History and click the older item.
  4. Assert: the Cat 4 button has `aria-pressed="true"`, the slider shows "120 km", `.band` exists, the `resimulated` test id is visible after opening Details, `earlier-questions` contains the question, and clicking **Ask again** produces a new answer with Google Maps sources (SC-002, FR-007 to FR-009).

**Checkpoint**: US1 and US2 together give the full save-and-reopen loop.

---

## Phase 5: User Story 3 - Manage the history list (Priority: P2)

**Goal**: Rename and delete scenarios, and see the eviction notice.

**Independent Test**: Create three scenarios, rename one, delete one, and check the names, count and order.

- [X] T020 [US3] Add management to `frontend/src/components/chat/HistorySection.tsx`:
  - **Rename**: each item gets a small "Rename" button that swaps the name for an `<input aria-label="Scenario name" maxLength={80}>`. Enter dispatches `renameScenario`, Esc cancels, and blur saves.
  - **Delete**: a "Delete" button shows inline `Delete '<name>'?` with **Delete** and **Cancel** buttons. Confirming dispatches `deleteScenario`.
  - **Notice**: when `state.notice` is set, show it above the list with a "Dismiss" button that dispatches `dismissNotice`.
  - keep all controls keyboard reachable
- [X] T021 [P] [US3] Extend `frontend/tests/component/HistorySection.test.tsx`:
  - rename via Enter updates the shown name, and the entry's `nameIsCustom` becomes true. Check it through the store by re-rendering, then dispatching `setCategory` and verifying the name doesn't change.
  - Esc cancels
  - delete asks for confirmation, Cancel keeps the entry and Delete removes it
  - deleting the current entry clears the map scenario (`New simulation` button disappears)
  - the notice shows and dismisses

**Checkpoint**: All three stories work on their own.

---

## Phase 6: Polish & Cross-Cutting Concerns

- [X] T022 [P] Update `specs/001-georgia-shelter-map/spec.md` FR-020 ("The user MUST be able to remove or reset the simulated hurricane") by appending "(via **New simulation**, see feature 002)", and update any `Reset` mention in `specs/001-georgia-shelter-map/quickstart.md` §5.
- [X] T023 Run the full verification:
  - `cd frontend && npx tsc -b && npx eslint . && npx vitest run && npm run build`
  - run Playwright **on a spare port with the mock agent**, so the running real-agent app on 5173 is left alone. Use a temporary config extending `playwright.config.ts` with `baseURL` `http://localhost:5174` and `webServer` `VITE_MOCK_AGENT=1 npx vite --port 5174 --strictPort`, then delete it. Run both `smoke.spec.ts` and `history.spec.ts`.
  - capture a 1440×900 screenshot with History expanded (two entries, one current) to the session scratchpad and check the chat column layout
- [X] T024 Walk through `specs/002-scenario-history/quickstart.md` steps 1–9 against the real agent (`npm run dev` on 5173 with the agent on 8000), and record any issue in `specs/002-scenario-history/research.md` under "## Verification".

---

## Dependencies & Execution Order

- **Phase 1** comes before everything else.
- **Phase 2**:
  - T002, T003 and T004 run in parallel.
  - T005 needs T002 and T003. T006 needs T002 and T005.
  - T007 runs alongside T005, after T002. T008 runs after T003.
- **US1 (Phase 3)** needs Phase 2. T009, T010 and T012 can start together. T011 runs after T010. T013 runs after T009–T011.
- **US2 (Phase 4)** needs US1's T010 and T011. T015, T017 and T018 can run in parallel. T019 runs last.
- **US3 (Phase 5)** needs T010. It can run alongside US2.
- **Polish**: T022 can run anytime. T023 and T024 run last.

### Parallel Example: Foundational

```bash
Task: "T002 lib/history.ts"
Task: "T003 countiesAlongTrack in lib/simulation.ts"
Task: "T004 resetChatSession in lib/agentClient.ts"
```

### Parallel Example: User Story 2

```bash
Task: "T015 Re-simulated label in AffectedSummary.tsx"
Task: "T017 HistorySection component test"
Task: "T018 EarlierQuestions component test"
```

## Implementation Strategy

1. **MVP**: Phase 1, then Phase 2, then US1. Scenarios are never lost and are listed.
2. **Add US2**: reopen with re-simulation and Ask again. This is what makes history useful.
3. **Add US3**: rename, delete and the eviction notice.
4. **Polish**: doc touch-ups, full verification, and the real-agent walk-through.
