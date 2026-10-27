# Implementation Plan: Miles/Kilometres Toggle, Map Zoom and a Tabbed Side Panel

**Branch**: `003-miles-zoom-tabs` | **Date**: 2026-10-27 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/003-miles-zoom-tabs/spec.md`

## Summary

This feature makes three front-end changes. Nothing changes in the agent, BigQuery or the history
schema.

1. **Units**: every app-computed distance shows in miles or kilometres, chosen with a toggle that
   defaults to miles and is remembered in the browser. Kilometres stay the stored unit everywhere,
   and one pure `units.ts` module converts at the display edge.
2. **Tabs**: Chat and Details merge into one always-open `SidePanel` with ARIA tabs. Both tabs stay
   mounted, so typed text, scroll position and streaming survive a switch. A "new details" marker
   replaces the old rail.
3. **Zoom**: `d3-zoom` on the map svg gives +, − and reset buttons, wheel and pinch zoom toward the
   pointer, and drag-to-pan within 1–8×. Markers and strokes keep their on-screen size, and
   pointer input is inverted through the zoom transform so track drawing stays accurate.

## Technical Context

**Language/Version**: TypeScript 5.x, React 18.3
**Primary Dependencies**: Vite 5, d3-geo, @turf/turf (existing). New: `d3-zoom@3.0.0` and `d3-selection@3.0.0` (+ `@types/d3-zoom`, `@types/d3-selection`), see research R7
**Storage**: Browser `localStorage` key `gsr.distanceUnit.v1` (new). `gsr.scenarioHistory.v1` is unchanged
**Testing**: Vitest + Testing Library (unit and component), Playwright (e2e) with `VITE_MOCK_AGENT=1`
**Target Platform**: Evergreen desktop browsers (Chrome, Edge, Firefox, Safari), served from the existing Cloud Run service
**Project Type**: Web application (frontend change only)
**Performance Goals**: A unit switch, zoom step or pan frame updates in under 250 ms with every Georgia shelter drawn (SC-006). In practice this aims for an interactive frame rate
**Constraints**: No agent or contract change. Saved history must reopen without migration. Wheel zoom must not scroll the page while the pointer is over the map
**Scale/Scope**: One state's shelters (hundreds of map markers) and 159 counties. About 12 source files and 8 test files touched

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Gate | Status | Notes |
|---|---|---|
| 1. Three-state flags, blank ≠ "no" (I) | Pass, untouched | No flag logic changes. Details content moves into a tab unchanged, so Yes / No / Not recorded counts render as before. The existing flag tests keep running. |
| 2. Maps grounding changes output; fresh/historical labels; attribution (II) | Pass, untouched | Chat and attribution rendering move into the Chat tab unchanged. Agent text is not rewritten (FR-007), so attribution placement is preserved. |
| 3. Every figure names source and scale; "reachable" is a documented parameter (III) | Pass | Every distance stays labelled straight-line in either unit. "Reachable" is still the one visible slider over the documented 25–200 km range. The miles view of it is defined in research R3. |
| 4. No individual-level data; licences recorded (IV) | Pass | Only a unit string is stored. No new data. `d3-zoom` and `d3-selection` are ISC-licensed, the same as the existing `d3-geo`. |
| 5. No prohibited ranking inputs; equity audit (V) | N/A | No ranking change. Unit conversion is display-only and leaves the receiving list identical (FR-006). |
| 6. Validation run, defect guards, no federal edits (VI) | N/A | No data path change. |
| 7. Maps to the Readiness Brief segments, counted "could not tell you" (VII) | Pass | Where they would go (distances), What to fix (zoom into clusters), and What we could not tell you stays in Details. The new limitation, that agent text is not unit-converted, is stated in the spec. |

**Decision log** (constitution, workflow section):

| Decision | Reason |
|---|---|
| km stays canonical | Unit is display-only, so there is no migration and no agent change (R1) |
| Miles by default, remembered per browser | Georgia planners work in miles; clarification Q2 (R4) |
| Slider runs 16–124 mi | Keeps every position inside the documented 25–200 km reach (R3) |
| d3-zoom | Tested gesture, clamping and click-suppression logic in the same family as d3-geo (R7) |
| Both tabs stay mounted | Keeps chat input, scroll position and streaming across switches with the least code (R5) |

**Post-design re-check (after Phase 1)**: all gates unchanged. Nothing in the data model or the
contracts touches flags, rankings, grounding or stored data beyond the unit string.

## Project Structure

### Documentation (this feature)

```text
specs/003-miles-zoom-tabs/
├── plan.md              # This file
├── research.md          # Phase 0: R1–R13 decisions
├── data-model.md        # Phase 1: store, unit and map-view state
├── quickstart.md        # Phase 1: run and verify
├── contracts/
│   ├── ui-controls.md               # roles, names and behaviour of the toggle, tabs and zoom
│   └── unit-preference-storage.md   # gsr.distanceUnit.v1
├── checklists/requirements.md
└── tasks.md             # Phase 2 (/speckit.tasks, not created here)
```

### Source Code (repository root)

```text
frontend/
├── package.json                         # + d3-zoom, d3-selection (+ @types)
├── src/
│   ├── App.tsx                          # DetailsPanel + ChatPanel → <SidePanel/>
│   ├── lib/
│   │   └── units.ts                     # NEW: KM_PER_MI, toDisplay, formatDistance, slider ranges, loadUnit/saveUnit
│   ├── state/
│   │   └── store.tsx                    # unit, sideTab, detailsUnseen; setUnit, setSideTab; remove detailsOpen
│   ├── components/
│   │   ├── SidePanel.tsx                # NEW: tablist; both panels mounted, inactive one hidden
│   │   ├── chat/ChatPanel.tsx           # `active` prop: save and restore log scrollTop
│   │   ├── summary/DetailsPanel.tsx     # content only: rail, header and hide button removed
│   │   ├── scenario/
│   │   │   ├── UnitToggle.tsx           # NEW: mi | km radiogroup
│   │   │   ├── ScenarioControls.tsx     # adds <UnitToggle/>
│   │   │   ├── ReachSlider.tsx          # unit-aware range, still emits km
│   │   │   ├── AffectedSummary.tsx      # formatDistance(half_width_km)
│   │   │   └── ReceivingList.tsx        # formatDistance on heading, empty text, header and cells
│   │   └── map/
│   │       ├── MapView.tsx              # d3-zoom, transform <g>, Safari gesture events, resize rescale, reset on reopen
│   │       ├── ZoomControls.tsx         # NEW: Zoom in / Zoom out / Reset view
│   │       ├── ShelterLayer.tsx         # r / k; memoised projected points; labels scaled by 1/k
│   │       └── TrackDrawer.tsx          # transform.invert before projection.invert; overlay outside the zoomed <g>
│   └── styles/app.css                   # 2-column grid, tabs, zoom overlay, non-scaling-stroke, ≤900px stacking; remove .details-rail
└── tests/
    ├── unit/units.test.ts               # NEW: conversion, formatting, <1, slider bounds, load/save fallbacks
    ├── unit/sidePanelReducer.test.ts    # NEW: sideTab and detailsUnseen transitions
    ├── component/SidePanel.test.tsx     # NEW: replaces DetailsPanel.test.tsx (tabs, marker, keyboard, input survives)
    ├── component/ReachSlider.test.tsx   # NEW: mi/km labels, emits km, round-trip stability
    ├── component/ReceivingList.test.tsx # updated: both units
    ├── e2e/smoke.spec.ts                # updated: Details tab instead of the rail; "50 mi"
    ├── e2e/history.spec.ts              # updated: reopened reach in miles; Details tab
    ├── e2e/units.spec.ts                # NEW: toggle and persistence across reload
    └── e2e/zoom.spec.ts                 # NEW: buttons, limits, wheel at pointer, no page scroll, pan, draw under zoom, reset
```

**Structure Decision**: Web application layout, with changes confined to `frontend/`. `agent/` is
untouched, because the chat context still carries `cutoff_km` in kilometres (research R13).

## Complexity Tracking

No constitution violations to justify.
