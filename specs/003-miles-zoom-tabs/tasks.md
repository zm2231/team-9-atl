# Tasks: Miles/Kilometres Toggle, Map Zoom and a Tabbed Side Panel

**Input**: Design documents from `/specs/003-miles-zoom-tabs/`
**Prerequisites**: [plan.md](plan.md), [spec.md](spec.md), [research.md](research.md), [data-model.md](data-model.md), [contracts/](contracts/), [quickstart.md](quickstart.md)

**Tests**: Included. The plan names the test files, and the project ships with Vitest and Playwright suites that this feature breaks (rail-based Details tests, "80 km" assertions). Write each story's tests first and watch them fail.

**Organization**: One phase per user story, in spec priority order. All paths are relative to the repository root. All work is in `frontend/`.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependency on an unfinished task)
- **[Story]**: US1 = units, US2 = tabbed panel, US3 = zoom

---

## Phase 1: Setup

**Purpose**: Add the new dependencies and confirm the baseline is green.

- [X] T001 Add `d3-zoom@3.0.0` and `d3-selection@3.0.0` to `dependencies`, and `@types/d3-zoom` and `@types/d3-selection` to `devDependencies`, in frontend/package.json by running `cd frontend && npm install --save-exact d3-zoom@3.0.0 d3-selection@3.0.0 && npm install --save-dev @types/d3-zoom @types/d3-selection`. Commit the updated frontend/package-lock.json too.
- [X] T002 Run `cd frontend && npm test && npx tsc -b` and record that the baseline passes before any change. If anything fails, stop and report it rather than continuing.

---

## Phase 2: Foundational

**Purpose**: None needed. No data, agent or schema work blocks the stories (plan: frontend-only, km stays canonical), so the constitution's notebook-validation task does not apply because no data path changes. Each story below can start once Phase 1 is done.

**Checkpoint**: Phase 1 is green, so user stories can begin.

---

## Phase 3: User Story 1 - Miles by default, with a toggle to kilometres (Priority: P1) 🎯 MVP

**Goal**: Every app-computed distance shows in the selected unit (mi or km). Miles is the default on a first visit. The choice is remembered in the browser. Stored values stay in km.

**Independent Test**: With `VITE_MOCK_AGENT=1 npm run dev`, draw a track. The reach reads "50 mi", the affected summary and receiving list read mi, and the header reads `mi*`. Switch to km: everything reads km, the reach reads "80 km", and the receiving list is identical. Reload and km is still selected.

### Tests for User Story 1 (write first, must fail)

- [X] T003 [P] [US1] Create frontend/tests/unit/units.test.ts covering the contract in specs/003-miles-zoom-tabs/contracts/unit-preference-storage.md and research R2/R3. Test these:
  - `KM_PER_MI === 1.609344`.
  - `formatDistance(80, "mi") === "50 mi"`, `formatDistance(80, "km") === "80 km"`, `formatDistance(0.3, "mi") === "<1 mi"`, `formatDistance(0, "km") === "0 km"`.
  - `sliderRange("mi")` deep-equals `{min:16,max:124,step:1}` and `sliderRange("km")` deep-equals `{min:25,max:200,step:5}`.
  - `toKm(50,"mi")` ≈ 80.4672, and `toKm(80,"km") === 80`.
  - `loadUnit` returns "mi" for null storage, a missing key, `"KM"`, `"miles"`, or a `getItem` that throws, and returns "km" for a stored `"km"`.
  - `saveUnit` writes the bare string under `gsr.distanceUnit.v1` and returns true, and returns false without throwing when `setItem` throws or storage is null.
- [X] T004 [P] [US1] Create frontend/tests/component/ReachSlider.test.tsx. Render `ReachSlider` with `unit="mi"`, `value={80}`, and an `onChange` spy.
  - Assert the visible text contains "50 mi" and the slider has accessible name "Within reach cutoff in miles", with min 16, max 124 and step 1.
  - Fire a change to 60 and assert `onChange` was called with ≈96.56 (km).
  - Re-render with `unit="km"`. Assert "80 km", accessible name "Within reach cutoff in kilometres", and min 25, max 200, step 5.
  - Re-render with `value={80.4672}` and `unit="km"`. Assert "80 km" is shown and `onChange` was not called (switching units never changes the reach).
- [X] T005 [P] [US1] Update frontend/tests/component/ReceivingList.test.tsx. Keep the existing km assertions but render with the store's `unit: "km"` through `StoreProvider initial`. Add a case with `unit: "mi"` asserting the heading contains "within 124 mi" for cutoff 200, the empty text contains "No shelters within 16 mi" for cutoff 25, the column header reads `mi*`, and a row with `distance_km.value = 40` shows "25 mi".
- [X] T006 [P] [US1] Create frontend/tests/e2e/units.spec.ts (Playwright, mocked agent, same setup as frontend/tests/e2e/smoke.spec.ts). The test covers:
  - On a fresh context, the "Distance unit" radiogroup has "Miles" checked and "Within reach:" contains "50 mi".
  - Draw a track the way smoke.spec.ts does, and note the receiving-list row count.
  - Click "Kilometres". "Within reach:" contains "80 km", the affected-summary heading contains "km either side", and the receiving row count is unchanged.
  - `page.reload()`. "Kilometres" is still checked.
- [X] T007 [P] [US1] Update the store tests in frontend/tests/unit/historyReducer.test.ts (or a new frontend/tests/unit/unitReducer.test.ts if that file is unrelated). Assert that `setUnit` changes `state.unit`, and that `openScenario` on a saved scenario with `cutoff_km: 120` leaves `state.unit` unchanged and `scenario.cutoff_km === 120`.

### Implementation for User Story 1

- [X] T008 [US1] Create frontend/src/lib/units.ts. It is pure, with no React and no `window`, matching the header-comment style of frontend/src/lib/history.ts. It exports:
  - `type DistanceUnit = "mi" | "km"`
  - `UNIT_STORAGE_KEY = "gsr.distanceUnit.v1"`
  - `KM_PER_MI = 1.609344`
  - `fromKm(km, unit)` and `toKm(value, unit)`
  - `formatDistance(km, unit)`: rounds to a whole number with `Math.round`. A value greater than 0 that rounds to 0 gives `"<1 mi"` / `"<1 km"`.
  - `unitLabel(unit)`, returning "mi" or "km", and `unitName(unit)`, returning "miles" or "kilometres"
  - `sliderRange(unit)`: km gives `{min: CUTOFF_MIN_KM, max: CUTOFF_MAX_KM, step: 5}`, imported from frontend/src/lib/simulation.ts. mi gives `{min: Math.ceil(CUTOFF_MIN_KM / KM_PER_MI), max: Math.floor(CUTOFF_MAX_KM / KM_PER_MI), step: 1}`.
  - `loadUnit(storage: Storage | null): DistanceUnit` and `saveUnit(storage: Storage | null, unit): boolean`, both with try/catch per the contract.

  Make T003 pass.
- [X] T009 [US1] Update frontend/src/state/store.tsx:
  - Add `unit: DistanceUnit` to `State`, with `"mi"` in `initialState`.
  - Add the action `{ type: "setUnit"; unit: DistanceUnit }` and its reducer case.
  - In `StoreProvider`, initialise with `useReducer(reducer, { ...initialState, ...initial }, (s) => ({ ...s, unit: initial?.unit ?? loadUnit(browserStorage()) }))`. `browserStorage` is a local try/catch around `window.localStorage`, the same as frontend/src/state/useHistoryPersistence.ts.
  - Add a `useEffect` in `StoreProvider` that calls `saveUnit(browserStorage(), state.unit)` when `state.unit` changes, skipping the first run.

  Make T007 pass.
- [X] T010 [P] [US1] Create frontend/src/components/scenario/UnitToggle.tsx. It renders `role="radiogroup"` with `aria-label="Distance unit"` and two `role="radio"` buttons: visible text "mi" with `aria-label="Miles"`, and "km" with `aria-label="Kilometres"`. Each has `aria-checked` and a roving `tabIndex`. Left/Right arrows switch the selection. It dispatches `setUnit` from `useStore`, and is never disabled (contracts/ui-controls.md).
- [X] T011 [US1] Update frontend/src/components/scenario/ReachSlider.tsx:
  - Add a `unit: DistanceUnit` prop.
  - Use `sliderRange(unit)` for min, max and step.
  - Set the input `value` to `Math.round(fromKm(value, unit) / step) * step`.
  - In `onChange`, call `onChange(toKm(Number(e.target.value), unit))`.
  - The label shows `Within reach: <strong>{formatDistance(value, unit)}</strong> (straight-line)`, and the aria-label is `` `Within reach cutoff in ${unitName(unit)}` ``.

  Make T004 pass.
- [X] T012 [US1] Update frontend/src/components/scenario/ScenarioControls.tsx to render `<UnitToggle />` after `ReachSlider` and pass `unit={state.unit}` to `ReachSlider`.
- [X] T013 [P] [US1] Update frontend/src/components/scenario/AffectedSummary.tsx. Replace `{scenario.half_width_km} km either side` with `{formatDistance(scenario.half_width_km, state.unit)} either side`.
- [X] T014 [P] [US1] Update frontend/src/components/scenario/ReceivingList.tsx. Use `state.unit` with `formatDistance` for:
  - the empty-state text "No shelters within {cutoff} …"
  - the heading "{n} shelters within {cutoff} …"
  - each row's distance cell, `formatDistance(r.distance_km.value ?? 0, unit)`
  - the column header, which becomes `` `${unitLabel(unit)}*` ``, keeping `title="Distance (straight-line)"`

  Make T005 pass.
- [X] T015 [US1] Run `grep -rnE "\bkm\b|kilomet" frontend/src --include=*.tsx`. Confirm no user-visible "km" string remains outside frontend/src/lib/units.ts. Identifiers and comments are fine, and frontend/src/components/chat/ChatPanel.tsx still sends `cutoff_km` in km (research R13). Fix any stragglers.
- [X] T016 [US1] Update frontend/tests/e2e/smoke.spec.ts line ~42 and frontend/tests/e2e/history.spec.ts line ~89. The default is now miles, so the assertions become `"50 mi"` and the miles equivalent of 120 km (`"75 mi"`), or click "Kilometres" first and keep the km text. Run `npx playwright test units.spec.ts smoke.spec.ts history.spec.ts` with T006 passing.

**Checkpoint**: US1 is shippable by itself. The Details rail still exists at this point.

---

## Phase 4: User Story 2 - Chat and Details in one tabbed panel (Priority: P2)

**Goal**: One always-open side panel with "Chat" and "Details" tabs. It opens on Chat. Switching keeps input, scroll position and streaming. A "new details" marker clears when Details is opened. The rail is removed.

**Independent Test**: Load the app. One panel shows with Chat selected. Type without sending, switch to Details and back, and the text is still there. On Chat, click a county: Details gets a dot and its name gains "(new details available)". Open Details and the dot clears.

### Tests for User Story 2 (write first, must fail)

- [X] T017 [P] [US2] Create frontend/tests/unit/sidePanelReducer.test.ts against `reducer` and `initialState` from frontend/src/state/store.tsx:
  - The initial `sideTab === "chat"` and `detailsUnseen === false`.
  - Each of `selectCounty`, `selectShelter`, `setTrack`, `setCategory`, `setCutoff` and `openScenario` sets `detailsUnseen` true while on chat.
  - The same actions leave it false when `sideTab === "details"`.
  - `hover` never sets it.
  - `setSideTab("details")` clears it, and `setSideTab("chat")` does not set it.
- [X] T018 [P] [US2] Create frontend/tests/component/SidePanel.test.tsx to replace frontend/tests/component/DetailsPanel.test.tsx, deleting that file and reusing its render helpers and fixtures. Cover:
  - There is a tablist named "Side panel" with tabs "Chat" (selected) and "Details".
  - Clicking Details shows the details tabpanel and hides the chat tabpanel.
  - Type "hello" into the chat input, switch to Details and back, and the input value is "hello".
  - Dispatch `selectCounty` while on Chat. The Details tab's accessible name becomes "Details (new details available)" and `.side-tab__dot` exists. Clicking it removes both.
  - ArrowRight on the Chat tab selects Details, and Home selects Chat.
  - No element named /Show details|Hide/ exists.
- [X] T019 [US2] Update frontend/tests/e2e/smoke.spec.ts (lines ~11–15) and frontend/tests/e2e/history.spec.ts (line ~94). Replace `getByRole("button", { name: /Show details/ })` with `getByRole("tab", { name: /^Details/ })`, and update the comments to say Details is a tab.

### Implementation for User Story 2

- [X] T020 [US2] Update frontend/src/state/store.tsx:
  - Remove `detailsOpen` and the `setDetailsOpen` action.
  - Add `sideTab: "chat" | "details"` (initial `"chat"`) and `detailsUnseen: boolean` (initial `false`).
  - Add the action `{ type: "setSideTab"; tab: "chat" | "details" }`, which sets the tab and clears `detailsUnseen` when the tab is details.
  - Wrap the reducer so that after `selectCounty`, `selectShelter`, `setTrack`, `setCategory`, `setCutoff` or `openScenario` it sets `detailsUnseen: true` if `state.sideTab === "chat"`. One post-step keeps each case untouched.

  Make T017 pass.
- [X] T021 [US2] Update frontend/src/components/summary/DetailsPanel.tsx so it renders only the content: `ShelterDetails`/`CountySummary`, then `AffectedSummary` and `ReceivingList` when a scenario exists, then `CouldNotTell`. Delete the rail branch, the `side__header`, the Hide button and the `detailsOpen` use, and update the doc comment.
- [X] T022 [US2] Update frontend/src/components/chat/ChatPanel.tsx:
  - Add an `active: boolean` prop.
  - Keep the log's `scrollTop` in a ref. When `active` turns false, save `logRef.current.scrollTop`. When it turns true, restore it with `useLayoutEffect`.
  - Keep the existing scroll-to-bottom on `state.chat` change, but only while `active`.
  - Remove the panel's own outer heading if `SidePanel` now supplies the tab label, keeping the "Earlier questions" and History sections.
- [X] T023 [US2] Create frontend/src/components/SidePanel.tsx with this structure:
  - `<aside className="side-panel">` containing a `role="tablist"` with `aria-label="Side panel"` and two `role="tab"` buttons.
  - The tabs have ids `tab-chat` and `tab-details`, `aria-controls` set to `panel-chat` / `panel-details`, `aria-selected` from `state.sideTab`, and a roving `tabIndex`.
  - The Details tab gets `aria-label="Details (new details available)"` and a `<span className="side-tab__dot" aria-hidden="true" />` while `state.detailsUnseen`.
  - Keyboard handling on the tablist: ArrowLeft/ArrowRight toggle, Home picks Chat and End picks Details. Each dispatches `setSideTab` and focuses the new tab.
  - Two `role="tabpanel"` divs, `aria-labelledby` their tab, both always rendered, with the inactive one `hidden`. One holds `<ChatPanel active={state.sideTab === "chat"} />` and the other `<DetailsPanel />`.

  Make T018 pass.
- [X] T024 [US2] Update frontend/src/App.tsx to replace `<DetailsPanel />` and `<ChatPanel />` with `<SidePanel />` and update the imports.
- [X] T025 [US2] Update frontend/src/styles/app.css:
  - Change the `.layout` grid to `grid-template-columns: minmax(420px, 1fr) 400px`.
  - Remove the `.details-rail` and `.details-rail__dot` rules, plus `.side` and `.side__header` if they are now unused.
  - Add `.side-panel` (flex column, full height, border-left, `var(--panel)` background), `.side-panel [role="tablist"]` (a row of two equal tabs with a bottom border), `[role="tab"][aria-selected="true"]` (bold, accent underline), `.side-tab__dot` (8 px circle in `var(--warn)`), and `[role="tabpanel"]` (flex 1, `overflow: auto`, `min-height: 0`).
  - Add `@media (max-width: 900px) { .layout { grid-template-columns: 1fr; grid-auto-rows: minmax(420px, auto); } }` so the panel stacks below the map (research R12).
  - Re-check the chat input still sits at the bottom of the Chat tab.
- [X] T026 [US2] Run `grep -rn "detailsOpen\|setDetailsOpen\|details-rail" frontend/src frontend/tests` and remove every remaining reference. Then run `cd frontend && npm test && npx tsc -b && npx playwright test smoke.spec.ts history.spec.ts`.

**Checkpoint**: US1 and US2 both work. The map is wider than with the old collapsed rail (SC-004).

---

## Phase 5: User Story 3 - Zoom in and out of the map (Priority: P3)

**Goal**: +, − and Reset buttons, wheel and pinch zoom about the pointer (1–8×), and drag-to-pan when not drawing. Georgia can't leave the view. Markers and strokes keep their on-screen size. Track drawing stays accurate. No double-click zoom. The view resets on reload and on reopening a scenario.

**Independent Test**: + is enabled and − is disabled at the start. Wheel over Savannah keeps Savannah under the pointer, and the page doesn't scroll. Dragging pans without selecting a county. In drawing mode a drag draws, and the track lands under the pointer at 4×. Reset and reopening a scenario both return to the whole state.

### Tests for User Story 3 (write first, must fail)

- [X] T027 [P] [US3] Create frontend/tests/e2e/zoom.spec.ts (Playwright, mocked agent). Read the scale from the svg's `data-zoom-k` and cover:
  - **Buttons:** at the start "Zoom out" and "Reset view" are disabled and "Zoom in" is enabled. Clicking "Zoom in" makes k ≈ 1.5. Clicking it until disabled makes k = 8.
  - **Wheel:** reset, then move the mouse to the screen position of a known shelter circle from the fixture via `locator('[data-shelter-id="…"] circle').boundingBox()`. Record `window.scrollY`, then `page.mouse.wheel(0, -400)`. k > 1, the same circle's bounding-box centre is within 3 px of the pointer, and `window.scrollY` is unchanged.
  - **Limit:** at k = 8, another wheel-in keeps k = 8 and the page does not scroll.
  - **Double-click:** at k = 1, double-clicking the map keeps k = 1.
  - **Pan:** at k = 2 with drawing off, a drag of 100 px changes the transform, and the county under the drag's end is not `.county--selected`.
  - **Constant size:** at k = 4 a shelter circle's bounding-box width matches its width at k = 1 within 1 px.
  - **Draw under zoom:** at k = 4, turn on drawing and drag from point A to B. The `.track` path's bounding box starts within 5 px of A.
  - **Reset on reopen:** reset, zoom in, then reopen a saved scenario from History. k = 1.

### Implementation for User Story 3

- [X] T028 [US3] Update frontend/src/components/map/MapView.tsx (research R7, R10, R11):
  - Add `transform` state, initially `zoomIdentity`, and a `zoomRef` holding `zoom<SVGSVGElement, unknown>()` with these settings:
    - `.scaleExtent([1, 8])`
    - `.extent([[0,0],[width,height]])` and `.translateExtent([[0,0],[width,height]])`
    - `.filter((e) => e.type === "wheel" || (!drawingRef.current && !e.button && e.type !== "dblclick"))`
    - `.on("zoom", (e) => setTransform(e.transform))`
  - Attach it in an effect with `select(svgRef.current).call(z).on("dblclick.zoom", null)`. Keep a `drawingRef` synced from `state.drawing`.
  - Wrap `CountyLayer`, `TrackDrawer`'s map content and `ShelterLayer` in `<g transform={transform.toString()}>`.
  - Add `transform` and `k: transform.k` to the `MapGeometry` context value.
  - Set `data-zoom-k={transform.k}` on the svg.
  - Export `zoomBy(factor)` and `resetZoom()` through a small context, or as props to `ZoomControls`, using `select(svg).call(z.scaleBy, factor)` and `select(svg).call(z.transform, zoomIdentity)`.
- [X] T029 [US3] In frontend/src/components/map/MapView.tsx, add Safari pinch support (research R8). In an effect, add non-passive `gesturestart` / `gesturechange` / `gestureend` listeners on the svg that call `preventDefault()`. On `gesturechange`, call `z.scaleBy(select(svg), e.scale / lastScale, pointer)`, where `pointer` is the event's client position mapped into svg coordinates, then set `lastScale = e.scale`. Reset `lastScale = 1` on `gesturestart`. Type the events locally, since `GestureEvent` isn't in lib.dom for every TS version.
- [X] T030 [US3] In frontend/src/components/map/MapView.tsx, handle resize and reopen (research R11):
  - **Resize:** when `size` changes, scale the transform's x and y by the width and height ratios, keep k, update the zoom's `extent` / `translateExtent`, and re-apply with `z.transform`, which clamps.
  - **Reopen:** add an effect on `state.resimulatedAt` that calls `resetZoom()` when it changes to a non-null value.
- [X] T031 [P] [US3] Create frontend/src/components/map/ZoomControls.tsx, absolutely positioned over the top-right of `.map`. It has three `<button type="button" className="btn zoom-btn">` elements:
  - `aria-label="Zoom in"` with text "+", disabled when `k >= 8 - 1e-6`
  - `aria-label="Zoom out"` with text "−", disabled when `k <= 1 + 1e-6`
  - `aria-label="Reset view"` with text "⟲", disabled when `k <= 1 + 1e-6 && x === 0 && y === 0`

  Clicks call `zoomBy(1.5)`, `zoomBy(1 / 1.5)` and `resetZoom()`. Render it inside `MapView`'s `.map` div, after the svg.
- [X] T032 [US3] Update frontend/src/components/map/TrackDrawer.tsx (research R10):
  - In `toLonLat`, after computing the viewBox `[x, y]`, apply `transform.invert([x, y])` from `useMapGeometry()` before `projection.invert`.
  - Move the `draw-overlay` `<rect>` out of the transformed `<g>` by splitting the component into `TrackLayer`, which holds the band, track, glyph and live polyline and renders inside the zoomed group, and `DrawOverlay`, which holds the rect and renders after the zoomed group, untransformed.
  - Draw the live polyline points inside the zoomed group as today.
  - Update MapView.tsx to render both parts.
- [X] T033 [US3] Update frontend/src/components/map/ShelterLayer.tsx (research R9):
  - Memoise `projected = useMemo(() => shelters.map((s) => [s, projection([s.lon, s.lat])]), [shelters, projection])`.
  - Take `k` from `useMapGeometry()` and use `r = 3.2 / k`, surge ring radius `(3.2 + 2.2) / k`, and label offsets divided by k.
  - Render the `!` and `?` `<text>` with `transform={`translate(${x},${y}) scale(${1 / k})`}` and offsets relative to 0,0.

  In frontend/src/components/map/TrackDrawer.tsx, give the storm glyph the same `scale(1/k)` treatment.
- [X] T034 [US3] Update frontend/src/styles/app.css:
  - Add `vector-effect: non-scaling-stroke` to `.county`, `.track`, `.band`, `.shelter`, `.shelter-surge`.
  - Make `.map` `position: relative` and give it `touch-action: none` and `overscroll-behavior: contain`.
  - Add `.zoom-controls { position: absolute; top: 8px; right: 8px; display: flex; flex-direction: column; gap: 4px; }` and `.zoom-btn { width: 32px; height: 32px; }` using the existing `--panel` / `--border` tokens.
  - Add `.map:not(.map--drawing) svg { cursor: grab; }`.
- [X] T035 [US3] Run `cd frontend && npx tsc -b && npm test && npx playwright test zoom.spec.ts` until T027 passes. Then check by hand in Safari, if one is available, that a trackpad pinch zooms the map and not the page. If Safari isn't available, record that it wasn't checked. **Result (2026-10-27):** Chromium e2e passes (7 zoom tests). The Safari trackpad pinch path (research R8) was not checked by hand: there is no Safari session in this environment.

**Checkpoint**: All three stories work independently and together.

---

## Phase 6: Polish & Cross-Cutting Concerns

- [X] T036 [P] Update the doc comments that mention the collapsed details panel or km-only display in frontend/src/state/store.tsx, frontend/src/components/summary/DetailsPanel.tsx and frontend/src/components/scenario/ReachSlider.tsx so they describe the tabs and units accurately.
- [X] T037 Constitution gate I re-check: run the existing flag tests (`npm test -- flags`). Open the Details tab for a county with UNRECORDED wheelchair records and confirm "Not recorded" still shows, not "No".
- [X] T038 Constitution gate III re-check: confirm every distance in both units still says "straight-line", in the slider label, the receiving list header `title` and the heading text.
- [X] T039 Run the full suite: `cd frontend && npm run lint && npx tsc -b && npm test && npx playwright test`. Fix any failures.
- [X] T040 Walk through every step in specs/003-miles-zoom-tabs/quickstart.md with `VITE_MOCK_AGENT=1 npm run dev` and note any step that does not behave as written.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: start immediately. T002 depends on T001.
- **Foundational (Phase 2)**: empty.
- **US1 (Phase 3)**: depends on Phase 1.
- **US2 (Phase 4)**: depends on Phase 1. It shares frontend/src/state/store.tsx (T009 and T020) and the e2e files (T016 and T019) with US1, so run it after US1 or merge those edits carefully.
- **US3 (Phase 5)**: depends on T001 (d3-zoom) only. It touches no files US1 or US2 touch except frontend/src/styles/app.css (T025 and T034, different rules) and the History reopen used in T027.
- **Polish (Phase 6)**: after the stories you ship.

### Within each story

Tests first and failing, then pure lib and state, then components, then wiring, then e2e green.

- **US1**: T008 → T009 → (T010, T013, T014 in parallel) → T011 → T012 → T015 → T016
- **US2**: T020 → (T021, T022 in parallel) → T023 → T024 → T025 → T026
- **US3**: T028 → (T029, T030, T031 in parallel; T029 and T030 edit the same file, so do them one after the other if you're working alone) → T032 → T033 → T034 → T035

### Parallel Opportunities

- T003–T007 (US1 tests) are all in separate files.
- T017 and T018 (US2 tests). T027 (US3 test) can be written alongside US1.
- T010, T013, T014 (separate components).
- T031 alongside T029/T030.
- US3 as a whole can run alongside US1 or US2 with a second developer.

---

## Parallel Example: User Story 1

```bash
# Tests together:
Task: "T003 units.test.ts"
Task: "T004 ReachSlider.test.tsx"
Task: "T005 ReceivingList.test.tsx (mi cases)"
Task: "T006 e2e/units.spec.ts"

# After T008–T009, components together:
Task: "T010 UnitToggle.tsx"
Task: "T013 AffectedSummary.tsx"
Task: "T014 ReceivingList.tsx"
```

## Parallel Example: User Story 3 alongside User Story 2

```bash
Developer A: T017 → T026 (tabs)
Developer B: T027 → T035 (zoom)
```

---

## Implementation Strategy

### MVP first (User Story 1)

1. Phase 1 (T001–T002).
2. Phase 3 (T003–T016). Stop and check: units toggle, persist, and leave results identical.
3. Ship or demo. The rail and the unzoomable map are still as they were.

### Incremental delivery

1. US1 gives miles with a km toggle.
2. US2 gives the tabbed panel and a wider map.
3. US3 gives zoom and pan.
4. Phase 6 adds the gate re-checks and the full suite.

---

## Notes

- km stays canonical everywhere in state, history and the agent context. Only `units.ts` converts, and only for display.
- Don't change `agent/`, `gsr.scenarioHistory.v1`, or `buildContext` in frontend/src/components/chat/ChatPanel.tsx.
- Commit after each checkpoint.
