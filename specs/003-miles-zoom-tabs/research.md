# Research: Miles/Kilometres Toggle, Map Zoom and a Tabbed Side Panel

**Feature**: 003-miles-zoom-tabs | **Date**: 2026-10-27

Each entry: Decision, Rationale, Alternatives considered. Together these form the decision log the
constitution asks for.

## R1. Where distances are stored: kilometres stay canonical

**Decision**: Every distance in state, saved history (`gsr.scenarioHistory.v1`), simulation code
and the chat context sent to the agent stays in kilometres (`cutoff_km`, `half_width_km`,
`distance_km`). Miles exist only at the display edge: one pure module, `src/lib/units.ts`,
converts and formats.

**Rationale**: FR-006 and FR-007 say the unit must not change any result, and the agent is out of
scope (FR-007, clarification Q1). Keeping one canonical unit means the history schema, the 002
validation (25 ≤ `cutoff_km` ≤ 200), the simulation tests and the agent contract all stay as they
are. Saved scenarios reopen unchanged with no migration (FR-007a, SC-002).

**Alternatives considered**: storing the cutoff in the selected unit, which needs a history
schema change and a migration, and risks drift on every round trip. Storing miles as canonical,
which needs the same migration and changes the agent context for no gain.

## R2. Conversion and rounding

**Decision**: `KM_PER_MI = 1.609344`, the exact international mile. `formatDistance(km, unit)`
returns a whole number plus the unit label (`"50 mi"`, `"80 km"`). A value that rounds to 0 but is
greater than 0 shows `"<1 mi"` / `"<1 km"`. Values are never rounded before they are stored.

**Rationale**: Whole numbers match today's display (`Math.round(distance_km)`). Rounding only for
display means switching units back and forth never changes the reach (spec edge case).

**Alternatives considered**: one decimal place, which is noisier and suggests a precision a
straight-line distance does not have. `Intl.NumberFormat` with `unit: "mile"`, whose output varies
by locale ("50 mi" vs "50 mile") and makes test text unstable.

## R3. Reach slider in each unit

**Decision**: The slider's own scale follows the selected unit, but it always emits kilometres.

- **km**: min 25, max 200, step 5. Unchanged.
- **mi**: min 16, max 124, step 1. That is ⌈25 / 1.609344⌉ to ⌊200 / 1.609344⌋, so every position
  lies inside the 25–200 km range. On change the slider emits `mi × 1.609344` km.
- The thumb shows the rounded current value. The default 80 km shows as "50 mi" and does not
  change until the user moves the slider.
- `aria-label` names the unit: "Within reach cutoff in miles" / "… in kilometres".

**Rationale**: FR-004 asks for the same range in either unit with whole-number display. Emitting
km keeps R1. A value set in miles (for example 80.47 km) and shown in km mode reads "80 km", and
the browser snaps only the thumb's position, not the stored value, because a controlled range
input does not fire `onChange` when it sanitises its value.

**Alternatives considered**: rounding the stored km to the slider step on each unit switch. That
breaks "switching back and forth never changes the reach".

## R4. Remembering the unit choice

**Decision**: New `localStorage` key `gsr.distanceUnit.v1` holding the bare string `"mi"` or
`"km"`. A pure `loadUnit(storage)` / `saveUnit(storage, unit)` pair lives in `src/lib/units.ts`.
Anything missing, unreadable or unexpected falls back to `"mi"`. The store reads the key
synchronously in `StoreProvider`'s initializer, so the first paint is already in the right unit.
`setUnit` writes it straight away. Every storage access is wrapped in try/catch, as 002 does.

**Rationale**: Clarification Q2 says browser-wide, not per scenario. Reading synchronously avoids
a flash of miles for a km user. A separate key keeps the unit out of the history document, so
FR-003's "not saved with a scenario" holds by construction.

**Alternatives considered**: adding the unit to the history document, which mixes a preference
into scenario data and needs a schema change. Loading in an effect, as the history hook does,
which causes a visible unit flip on first paint.

## R5. Tabbed panel: keep both tabs mounted

**Decision**: A new `SidePanel` component renders a WAI-ARIA tablist (`role="tablist"`, two
`role="tab"` buttons, two `role="tabpanel"` regions). Both `ChatPanel` and the Details content stay
mounted all the time. The inactive panel gets the `hidden` attribute.

- The chat log's `scrollTop` is saved when Chat is hidden and restored when it is shown, because
  `display: none` can reset scroll position.
- Keyboard: Left/Right arrows move between tabs, Home/End jump to the first or last, and the
  selected tab has `tabIndex=0`, the other `-1` (automatic activation).

**Rationale**: FR-011 asks that switching tabs keep typed-but-unsent text (local `useState` in
`ChatPanel`), scroll position, and any answer still streaming. Unmounting would lose the first
two, and the streaming loop would keep dispatching into a component that is no longer there.
Mounting both is the least code and the least risk.

**Alternatives considered**: lifting the chat input and scroll position into the store so the
panel can unmount. More state and more actions for no user benefit. CSS `visibility` stacking,
which keeps hidden content in the accessibility tree unless more ARIA is added.

## R6. Tab state and the "new details" marker

**Decision**: The store replaces `detailsOpen: boolean` with `sideTab: "chat" | "details"`
(initially `"chat"`, never saved) and `detailsUnseen: boolean`.

- The reducer sets `detailsUnseen = true` when `sideTab === "chat"` and any of these actions changes
  what Details shows: `selectCounty`, `selectShelter`, `setTrack`, `setCategory`, `setCutoff`,
  `openScenario`.
- `setSideTab` with `"details"` clears it.
- The Details tab shows a dot, and its accessible name becomes "Details (new details available)".

**Rationale**: FR-012 asks for a marker that clears once Details is opened. Today's rail shows the
dot whenever anything is selected, which never clears. Hover is excluded because it fires
constantly and would make the marker meaningless.

**Alternatives considered**: deriving "unseen" from a hash of the Details inputs compared with
the last one viewed. More code and harder to test.

## R7. Zoom engine: d3-zoom

**Decision**: Add `d3-zoom@3.0.0` and `d3-selection@3.0.0`, plus `@types/d3-zoom` and
`@types/d3-selection`. Attach one
zoom behaviour to the map `<svg>`, keep the current `ZoomTransform` in `MapView` state, and apply
it as `transform` on a single `<g>` that wraps the county, scenario and shelter layers. The
behaviour is configured as follows:

- `scaleExtent([1, 8])` (FR-017).
- `translateExtent([[0,0],[width,height]])` and `extent` set to the viewport, so Georgia can never
  be dragged out of view (FR-018).
- `filter`: wheel events always pass. Pointer drags pass only when `state.drawing` is false.
  Double-click is unbound (`.on("dblclick.zoom", null)`, FR-015a).
- `wheelDelta`: the d3 default, so Ctrl+wheel (which is how Chrome, Edge and Firefox report a
  trackpad pinch) zooms faster than a plain wheel, around the pointer.
- Buttons call `zoom.scaleBy(svg, 1.5)` and the reset button calls
  `zoom.transform(svg, zoomIdentity)`. Zoom-in is disabled when `k >= 8 - ε` and zoom-out when
  `k <= 1 + ε`.

**Rationale**: d3-zoom already handles pointer-anchored wheel and pinch zoom, touch pinch, drag,
extent clamping, and suppresses the click that ends a drag (`clickDistance`), so a pan never
selects a county by accident. It belongs to the same family as the `d3-geo` already in use, it is
small, and it is well tested. Getting gesture maths, clamping and click suppression right by hand
is where bugs would come from.

**Alternatives considered**: hand-rolled wheel and pointer handlers (~150 lines, re-implementing
clamping and click suppression, and more ways to get it wrong). An SVG `viewBox` animation
library. Switching the map to a tiled map library, which is far out of scope.

## R8. Safari trackpad pinch

**Decision**: On macOS Safari, a trackpad pinch arrives as `gesturestart` / `gesturechange` /
`gestureend` events, not Ctrl+wheel. `MapView` listens for `gesturechange` on the svg and turns
`event.scale` relative to the previous event into `zoom.scaleBy(svg, ratio, pointer)`. It calls
`preventDefault()` on the gesture events so Safari does not zoom the whole page.

**Rationale**: FR-015a requires pinch zoom, and d3-zoom does not handle WebKit gesture events.

**Alternatives considered**: ignoring Safari, which would break a stated requirement for Mac users
on Safari.

## R9. Constant on-screen size while zoomed (FR-020)

**Decision**:

- **Strokes**: county borders, the track, the band outline and the live track get
  `vector-effect: non-scaling-stroke` in CSS.
- **Shelter dots**: the zoom scale `k` goes through `MapGeometry` context. `ShelterLayer` divides
  `r`, the surge ring radius and its stroke by `k`.
- **Labels**: the `!` and `?` labels and the storm glyph are drawn with `transform="scale(1/k)"`
  around their own anchor.
- `ShelterLayer` memoises the projected `[x, y]` points per shelter, so a zoom frame re-renders
  only the attributes that depend on `k`.

**Rationale**: Markers that grow with zoom would cover each other, which defeats the point of
zooming into dense clusters (SC-005). `non-scaling-stroke` is supported by every evergreen browser.

**Alternatives considered**: drawing shelters in screen space, outside the transformed group, by
projecting through the transform every frame. That re-projects every point on every frame.

## R10. Pointer to map coordinates under zoom

**Decision**: `MapGeometry` exposes `transform`. `TrackDrawer.toLonLat` first maps client
coordinates to viewBox coordinates as it does today, then calls `transform.invert([x, y])`, then
`projection.invert`. The draw overlay `<rect>` moves outside the transformed group, so it always
covers the visible map whatever the zoom.

**Rationale**: FR-019 says a track must land where the pointer was at any zoom. Hover and click on
counties and shelters use native element events and need no change.

## R11. View reset and resize

**Decision**: The transform lives in `MapView` state only and is never saved (FR-021). It resets to
identity when the page loads and when a scenario is reopened. `MapView` watches
`state.resimulatedAt`, which `openScenario` sets.

On resize the base projection is fitted again, as it is today. The transform's translation is
scaled by `newWidth / oldWidth` and `newHeight / oldHeight`, and `k` is kept, so the view stays
over the same area (spec edge case). It is then clamped by the new `translateExtent`.

**Rationale**: Meets the reset requirement and the resize edge case with a few lines of code.

## R12. Layout and narrow screens

**Decision**: The `.layout` grid goes from `minmax(420px, 1fr) auto 400px` to
`minmax(420px, 1fr) 400px`. The old `auto` column held the details rail or panel. The map gains at
least the 32 px rail it used to share (SC-004). The `.details-rail` styles are removed.

The app has no narrow-screen rule today: the 420 px map minimum plus the side panels force a
horizontal scroll. This feature adds one `@media (max-width: 900px)` rule that stacks the map above
the side panel at full width, so both tabs stay usable (spec edge case). Nothing else about small
screens changes.

## R13. Agent and chat context

**Decision**: No agent change. `buildContext` keeps sending `cutoff_km`. Agent text renders as
written (FR-007). The spec's "What we could not tell you" note covers the unit mismatch this can
cause.
