# Quickstart: Miles/Kilometres Toggle, Map Zoom and a Tabbed Side Panel

## Run

```bash
cd frontend
npm install                     # picks up d3-zoom and d3-selection
VITE_MOCK_AGENT=1 npm run dev   # no agent or credentials needed
```

Open http://localhost:5173.

## Check it by hand

1. **Units**
   - On a first visit (or after clearing site data), the toggle shows **mi** and the slider reads "Within reach: 50 mi (straight-line)".
   - Draw a track. The affected summary and receiving list show "mi", and the column header reads `mi*`.
   - Switch to **km**. Everything reads km, the reach reads 80 km, and the affected counties and receiving list are identical.
   - Reload. km is still selected.
   - Reopen a scenario saved before this branch. Its reach matches what it was.
2. **Tabs**
   - The panel opens on **Chat**. Type a question without sending it, switch to **Details** and back. The text is still there.
   - Send a question and switch to Details while it streams. Come back and the answer is complete.
   - While on Chat, click a county. The Details tab gets a dot and its name gains "(new details available)". Open Details and the dot clears.
3. **Zoom**
   - + is enabled and − is disabled at the start. Click + until + is disabled (8×).
   - Scroll or pinch over Savannah and Savannah stays under the pointer. The page does not scroll.
   - Drag to pan. Georgia cannot be dragged out of view, and the drag does not select a county.
   - Turn on track drawing. Dragging now draws, and the track lands under the pointer at any zoom.
   - Shelter dots and borders keep the same on-screen size at every zoom.
   - Click Reset view, then reopen a saved scenario. Both return to the whole state.
   - Double-click the map. Nothing zooms.

## Automated

```bash
cd frontend
npm test                 # unit and component: units.ts, unit storage, reducer tabs and marker, SidePanel, ReachSlider, ReceivingList
npx playwright test      # e2e: smoke and history updated for tabs and units, plus new zoom.spec.ts and units.spec.ts
```
