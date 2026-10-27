# Contract: UI controls (roles, names, behaviour)

Tests (Testing Library, Playwright) query by these roles and names, so they are part of the
contract.

## Unit toggle (in `ScenarioControls`)

| Element | Role | Accessible name | Notes |
|---|---|---|---|
| group | `radiogroup` | "Distance unit" | Always enabled, even before a track is drawn |
| option | `radio` | "Miles" | Visible text `mi`; `aria-checked` matches the selected unit |
| option | `radio` | "Kilometres" | Visible text `km` |

- Clicking an option, or pressing an arrow key inside the group, dispatches `setUnit`.
- Every app-computed distance on screen updates in the same render.

## Reach slider

| Element | Role | Accessible name |
|---|---|---|
| range | `slider` | "Within reach cutoff in miles" or "Within reach cutoff in kilometres" |

- The visible label is `Within reach: <N mi|N km> (straight-line)`.
- The range runs 16–124 step 1 in miles, or 25–200 step 5 in km. It always emits kilometres (research R3).

## Side panel tabs (`SidePanel`)

| Element | Role | Accessible name | State |
|---|---|---|---|
| list | `tablist` | "Side panel" | |
| tab | `tab` | "Chat" | `aria-selected`, `aria-controls="panel-chat"` |
| tab | `tab` | "Details", or "Details (new details available)" while the marker shows | `aria-selected`, `aria-controls="panel-details"` |
| panel | `tabpanel` | labelled by its tab | the inactive panel has `hidden` |

- The panel opens on Chat on every load.
- Left/Right arrows move to and select the other tab. Home/End select the first or last tab.
- The marker dot has class `side-tab__dot` and `aria-hidden="true"`.
- There is no collapse, hide or resize control (FR-013).

## Map zoom controls (overlay, top-right of the map)

| Element | Role | Accessible name | Disabled when |
|---|---|---|---|
| button | `button` | "Zoom in" | k ≥ 8 |
| button | `button` | "Zoom out" | k ≤ 1 |
| button | `button` | "Reset view" | k = 1 and no pan offset |

- Each zoom click scales by 1.5× about the centre of the view. Reset returns to the whole state.
- Mouse wheel and trackpad pinch over the map zoom about the pointer within 1–8×, and the page does not scroll while the pointer is over the map.
- Double-click does nothing.
- Dragging pans the map only while track drawing is off. A drag never also selects the county or shelter it ended on.
- The svg carries `data-zoom-k` with the current scale, for tests.
