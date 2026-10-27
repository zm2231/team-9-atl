# Feature Specification: Miles/Kilometres Toggle, Map Zoom and a Tabbed Side Panel

**Feature Branch**: `003-miles-zoom-tabs`
**Created**: 2026-10-27
**Status**: Draft
**Input**: User description: "can we change the KM to Miles? Also, we need a Zoom in and Zoom out icon that lets us zoom in and out of the map. Also, can we make the chat window and the summary (the thing we previously collapsed) in the same component with tabs that allows the user to swtich between both?"

## Readiness Scenario & Data Honesty *(mandatory)*

**Scenario**: Our agent helps a **county emergency manager** in **Georgia** **read hurricane scenario results in the units they plan in, look closely at crowded parts of the state, and move between the agent's answers and the scenario details** before **the peak of hurricane season (September)**.
**Track / State**: Shelter Readiness / Georgia (GA), building on features 001 (Georgia Shelter Readiness Map) and 002 (Scenario History).
**Brief segments served**:
- Where they would go: receiving-shelter distances and the reach cutoff, shown in miles or kilometres as the user chooses
- What to fix: zooming in makes clustered shelters and small counties possible to tell apart
- What we could not tell you: stays in the Details tab, one click from the chat
**Unrecorded handling**: No change. This feature reads no new flag fields. Yes / No / Not recorded counts show the same way in the Details tab as they do in today's details panel.
**World vs paperwork**: Distances are still straight-line and still labelled as straight-line. Switching units changes only the unit shown, not what the figure measures. Zooming changes only the view, not any figure.
**What we could not tell you**: Straight-line distances are not road distances or drive times. Saying so stays next to every distance, as it does today. The agent's chat answers are not converted and keep whatever unit the agent wrote.

## Clarifications

### Session 2026-10-27

- Q: Should the agent's chat answers use miles too? → A: No. The agent is unchanged; the UI does the conversion, and the user can toggle between miles and kilometres.
- Q: Should the unit choice be remembered? → A: Yes, in this browser across reloads and visits; miles only on a first visit. It is not saved per scenario.
- Q: Can the tabbed panel be collapsed? → A: No. It is always open and cannot be collapsed or resized.
- Q: Zoom with the mouse wheel and trackpad pinch too, or only the buttons? → A: Buttons, plus mouse wheel and trackpad pinch zooming toward the pointer, plus drag to pan when zoomed in.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Miles by default, with a toggle to kilometres (Priority: P1)

An emergency manager draws a hurricane track and sets how far evacuees can reasonably travel. Every distance the app shows on screen (the track's width either side, the reach cutoff, and the distance to each receiving shelter) is shown in miles, the unit they and their partner agencies plan in. A miles/kilometres toggle lets them switch every on-screen distance to kilometres and back, for example when comparing against a federal or partner figure given in km.

**Why this priority**: Georgia planners think and brief in miles, but some source figures arrive in kilometres. Showing one unit at a time, chosen by the user, avoids mental conversion and mistakes when results are passed on.

**Independent Test**: Draw a track, move the reach slider and open the receiving list in miles; flip the toggle to km and confirm every on-screen distance changes unit together and covers the same distance; flip back.

**Acceptance Scenarios**:

1. **Given** the app is opened for the first time, **When** the user looks at the reach control, **Then** it reads "Within reach: N mi (straight-line)" and the unit toggle shows miles selected.
2. **Given** a Category 3 track has been drawn, **When** the user reads the affected summary, **Then** the width either side of the track is shown in the selected unit.
3. **Given** a scenario with receiving shelters, **When** the user reads the receiving list, **Then** each shelter's distance and the list heading's cutoff are shown in the selected unit, still marked straight-line.
4. **Given** miles are selected and the reach is 50 mi, **When** the user switches to km, **Then** the reach reads 80 km, every other on-screen distance changes to km at once, and the affected counties and receiving list do not change.
5. **Given** the user asks the agent how far a shelter is, **When** the agent answers, **Then** the answer text is shown as the agent wrote it, without conversion.
6. **Given** the user switched to km and closed the app, **When** they open it again in the same browser, **Then** km is still selected.
7. **Given** a scenario saved before this change, **When** the user reopens it from history, **Then** its reach covers the same distance it did when it was saved, shown in the selected unit.

---

### User Story 2 - Chat and Details in one tabbed panel (Priority: P2)

Today the details summary sits in its own panel, collapsed to a thin rail by default, next to a separate chat panel. The user wants both in one panel with two tabs, **Chat** and **Details**, and switches between them with one click. The map keeps the space the extra panel used to take.

**Why this priority**: Two side-by-side panels squeeze the map, and a collapsed rail is easy to miss. Tabs keep both one click away and give the map more room.

**Independent Test**: Open the app, confirm one side panel with two tabs, switch between them, and confirm each tab shows what the old chat panel and old details panel showed.

**Acceptance Scenarios**:

1. **Given** the app is open, **When** it first loads, **Then** one side panel shows with the Chat tab selected, and the Details tab is visible next to it.
2. **Given** the Chat tab is selected, **When** the user clicks Details, **Then** the panel shows the county or shelter summary, the hurricane affected summary and receiving list (when a scenario exists) and "What we could not tell you".
3. **Given** the user has typed a question but not sent it, **When** they switch to Details and back to Chat, **Then** the typed text, the conversation and its scroll position are still there.
4. **Given** an answer is still streaming, **When** the user switches to Details, **Then** the answer keeps streaming and is complete when they come back.
5. **Given** the Chat tab is selected, **When** the user selects a county, selects a shelter or draws a track, **Then** the panel stays on Chat and the Details tab shows a marker saying new details are available.
6. **Given** the user is on the Details tab, **When** they reload the page, **Then** the panel opens on Chat again.

---

### User Story 3 - Zoom in and out of the map (Priority: P3)

The user clicks a zoom-in (+) button, or scrolls or pinches over the map, to see a crowded area, such as metro Atlanta or the coast, in more detail, and a zoom-out (−) button or the opposite scroll to step back. When zoomed in they can drag the map to move around, and a reset button returns to the whole state.

**Why this priority**: Shelters cluster tightly in some counties and are hard to tell apart or click at state scale. Zoom makes them usable, but the app still works without it.

**Independent Test**: Click zoom in, confirm the map gets larger around its centre, drag it to another area, click zoom out until the whole state shows again, and confirm the buttons stop at their limits.

**Acceptance Scenarios**:

1. **Given** the map shows all of Georgia, **When** the user clicks zoom in, **Then** the map enlarges around the centre of the view and the zoom-out button becomes available.
2. **Given** the map shows all of Georgia, **When** the user looks at zoom out, **Then** it is disabled, since the whole state is already in view.
3. **Given** the map is at its closest zoom, **When** the user looks at zoom in, **Then** it is disabled.
4. **Given** the map is zoomed in and track drawing is off, **When** the user drags the map, **Then** the view moves with the pointer and cannot be dragged so far that Georgia leaves the view.
5. **Given** the map is zoomed in, **When** the user clicks reset, **Then** the whole state is shown again.
6. **Given** the map is zoomed in, **When** the user hovers or clicks a county or shelter or draws a track, **Then** it behaves as at full-state view and the track lands where the pointer was.
7. **Given** the map is zoomed in, **When** the user looks at shelter dots, track lines and county borders, **Then** they keep the same on-screen size as at full-state view rather than growing with the zoom.
8. **Given** the map shows all of Georgia, **When** the user scrolls the mouse wheel up or pinches out with the pointer over Savannah, **Then** the map zooms in and Savannah stays under the pointer.
9. **Given** the map is at its farthest-out or closest zoom, **When** the user keeps scrolling the same way, **Then** the zoom stays at its limit, the map does not move, and the page does not scroll instead.
10. **Given** a keyboard-only user, **When** they tab to the zoom buttons, **Then** each has a readable name ("Zoom in", "Zoom out", "Reset view") and works with Enter or Space.

---

### Edge Cases

- If the browser cannot store the unit choice, for example in a private window with storage blocked, the app still works, opens in miles, and the toggle still works for that visit.
- A reach that is not a whole number of miles is shown rounded to the nearest mile. Switching units back and forth without moving the slider never changes the reach.
- A receiving shelter less than half a mile away shows "<1 mi" rather than "0 mi".
- When track drawing is on, dragging draws a track and does not move the map, as it does today.
- A fast run of wheel or pinch events zooms smoothly and stops at the limits. It never overshoots and snaps back.
- When the window is resized while zoomed in, the view stays on the same area and does not jump back to the whole state.
- When a narrow window cannot fit the map and the side panel next to each other, the panel keeps both tabs usable.
- The agent may state a distance in km while the screen shows miles. The chat text is not rewritten, so the two can differ in unit until a later feature passes the selected unit to the agent.

## Requirements *(mandatory)*

### Functional Requirements

**Units**

- **FR-001**: Every distance the app computes and shows on screen MUST be shown in one selected unit, miles ("mi") or kilometres ("km"). Those distances MUST NOT mix the two units (agent chat text excepted, see FR-007).
- **FR-002**: The user MUST be able to switch between miles and kilometres with a toggle that is always visible near the scenario controls. Switching MUST update every on-screen distance at once.
- **FR-003**: Miles MUST be the selected unit the first time the app is opened in a browser. After that, the app MUST remember the user's last choice in that browser across reloads and later visits. The unit MUST NOT be saved with a scenario, so reopening a scenario does not change it.
- **FR-004**: The reach cutoff MUST cover the same 25–200 km range in either unit (about 15–124 mi), default to 80 km (50 mi), and show whole numbers in the selected unit.
- **FR-005**: Receiving-shelter distances and the track's width either side MUST be shown as whole numbers in the selected unit and stay marked as straight-line.
- **FR-006**: Switching units MUST NOT change who counts as affected or which shelters are within reach. Only the label and number shown change.
- **FR-007**: The agent's chat answers MUST be shown as the agent wrote them. The agent, its tools and its data are not changed by this feature.
- **FR-007a**: Saved scenarios MUST reopen with the same reach they were saved with, whichever unit is selected when they are saved or reopened.

**Tabbed panel**

- **FR-008**: The chat and the details summary MUST share one side panel with two tabs labelled "Chat" and "Details".
- **FR-009**: The panel MUST open on the Chat tab when the app loads.
- **FR-010**: The Details tab MUST show everything the old details panel showed, in the same order.
- **FR-011**: Switching tabs MUST keep the chat's conversation, typed-but-unsent text, scroll position and any answer still streaming.
- **FR-012**: Selecting a county or shelter or drawing a track MUST NOT switch tabs on its own. When new details arrive while Chat is selected, the Details tab MUST show a "new details" marker that clears once Details is opened.
- **FR-013**: The tabbed panel MUST always be open beside the map, with no hide, collapse or resize control. The old collapsed details rail and its show/hide control MUST be removed.
- **FR-014**: The tabs MUST be usable by keyboard, and the selected tab MUST be announced to screen readers.

**Zoom**

- **FR-015**: The map MUST have visible zoom-in, zoom-out and reset-view buttons placed over a corner of the map.
- **FR-015a**: Scrolling the mouse wheel or pinching on a trackpad over the map MUST zoom the map toward the point under the pointer, within the same limits as the buttons. While the pointer is over the map, the wheel MUST zoom the map rather than scroll the page. Double-click MUST NOT zoom.
- **FR-016**: Each zoom click MUST change the scale by a fixed step about the centre of the current view.
- **FR-017**: Zoom MUST range from the whole of Georgia (the starting view and the farthest out) to 8 times that scale. Each button MUST be disabled at its limit.
- **FR-018**: When zoomed in and track drawing is off, the user MUST be able to drag to move the map, and the view MUST NOT move past Georgia's edges.
- **FR-019**: Hover, selection, highlighting and track drawing MUST land on the correct county, shelter and position at any zoom level.
- **FR-020**: Shelter markers, county borders and track lines MUST keep a constant on-screen size as the map zooms.
- **FR-021**: The zoom level and position MUST NOT be saved with a scenario. Reopening a scenario or reloading the page MUST start at the whole-state view.

### Key Entities

- **Reach cutoff**: How far evacuees can reasonably travel in a scenario. It holds one distance whatever unit is shown. Saved scenarios keep that distance and reopen with it.
- **Distance unit preference**: Miles or kilometres, chosen by the user. It applies to every on-screen distance and every scenario, and is remembered in the browser rather than saved with any scenario.
- **Map view**: The current zoom level and position. It lives only for the visit and is never saved.
- **Side panel tab**: Which tab, Chat or Details, is showing, plus whether Details has news the user has not seen. It lives only for the visit.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A review of every screen finds 0 places where an app-computed distance shows in a unit other than the selected one, in both mi and km.
- **SC-002**: For 10 saved scenarios made before the change, the reopened reach and receiving list match the originals exactly, in either unit.
- **SC-002a**: Switching units takes 1 click and changes every on-screen distance with no visible delay.
- **SC-003**: A user can go from the chat to the details for the selected county and back in 2 clicks or fewer, without losing any typed or streamed text.
- **SC-004**: With both tabs available, the map takes at least as much screen width as it did when the old details panel was collapsed.
- **SC-005**: In 5 test sessions, users can single out and click one shelter inside metro Atlanta's densest cluster after zooming, where they could not reliably do so at full-state view.
- **SC-006**: Every zoom and pan step updates the map in a way users see as immediate (under a quarter of a second) with all Georgia shelters shown.

## Assumptions

- Unit conversion happens only in what the app shows on screen. The agent is unchanged and its answers are not converted.
- The reach range keeps its current 25–200 km limits rather than being rounded to friendly mile values.
- Zoom is by buttons, mouse wheel and trackpad pinch, and the map moves by dragging. Because the wheel zooms the map while the pointer is over it, a user scrolling the page must move the pointer off the map. On narrow screens, where the map stacks above the panel, the page can still be scrolled by touch or from outside the map.
- A zoom step of 1.5× per click with a maximum of 8× is a reasonable default. The plan may adjust it.
- Chat opens by default because the chat was always visible and the details panel was collapsed by default. This keeps the default the user is used to.
- On narrow screens the tabbed panel stacks below the map. The app has no narrow-screen layout today, so this feature adds the one rule it needs.
- Saved history keeps working. Any change to how the cutoff is stored must read existing saved scenarios correctly.
- Kilometre figures inside the agent, such as the 16 km (10 mile) reach used by the readiness brief, are out of scope.
