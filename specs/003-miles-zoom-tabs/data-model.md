# Data Model: Miles/Kilometres Toggle, Map Zoom and a Tabbed Side Panel

**Feature**: 003-miles-zoom-tabs | **Date**: 2026-10-27

No BigQuery, agent or history-schema changes. Every change is front-end state.

## DistanceUnit

| Field | Type | Rules |
|---|---|---|
| value | `"mi" \| "km"` | Default `"mi"`. Anything else read from storage falls back to `"mi"`. |

- **Lives in**: store field `unit`, and mirrored to `localStorage["gsr.distanceUnit.v1"]` as the bare string (see [contracts/unit-preference-storage.md](contracts/unit-preference-storage.md)).
- **Lifecycle**: read once, synchronously, when `StoreProvider` starts. Written on every `setUnit`. Never part of a `SavedScenario`.

## Reach cutoff (unchanged shape)

| Field | Type | Rules |
|---|---|---|
| `cutoff_km` | number | 25 ≤ value ≤ 200. **Always kilometres.** May now hold a non-integer, for example 80.4672 when set from the miles slider. Rounded only for display. |

- The existing 002 validation (`typeof number`, 25–200) already accepts non-integers, so saved history needs no migration.
- The display value is `formatDistance(cutoff_km, unit)`.

## Other distances (unchanged shape, display-only conversion)

| Field | Where | Display |
|---|---|---|
| `half_width_km` | `HurricaneScenario`, from `HALF_WIDTH_KM` | `formatDistance(half_width_km, unit)` in AffectedSummary |
| `distance_km.value` | `ReceivingShelter` | `formatDistance(value, unit)` in ReceivingList cells; the column header is `mi*` / `km*` |

## Store state changes (`src/state/store.tsx`)

| Change | Field | Type | Initial |
|---|---|---|---|
| added | `unit` | `DistanceUnit` | `loadUnit(storage)` → `"mi"` on a first visit |
| added | `sideTab` | `"chat" \| "details"` | `"chat"` (never saved, FR-009) |
| added | `detailsUnseen` | boolean | `false` |
| removed | `detailsOpen` | boolean | n/a |

### Actions

| Action | Effect |
|---|---|
| `setUnit { unit }` | `state.unit = unit`. The persistence side effect saves it. |
| `setSideTab { tab }` | `state.sideTab = tab`. If `tab === "details"`, sets `detailsUnseen = false`. |
| removed: `setDetailsOpen` | Replaced by `setSideTab`. |

### detailsUnseen transitions

```text
                    selectCounty | selectShelter | setTrack |
                    setCategory  | setCutoff     | openScenario
   [seen] ──────────────────────(while sideTab = chat)────────────────▶ [unseen]
     ▲                                                                     │
     └──────────────────────── setSideTab("details") ──────────────────────┘
```

While `sideTab === "details"`, these actions leave `detailsUnseen` false, because the user is looking at the result. `hover` never sets it.

## Map view (component state in `MapView`, never stored)

| Field | Type | Rules |
|---|---|---|
| `transform` | d3 `ZoomTransform` `{k, x, y}` | 1 ≤ k ≤ 8. Translation clamped so the Georgia extent always fills the view. Identity on load and when a scenario is reopened (`resimulatedAt` changes). |

`MapGeometry` context gains `transform` (for pointer inversion) and `k` (for constant-size markers). Its existing fields `projection`, `path`, `width` and `height` are unchanged.
