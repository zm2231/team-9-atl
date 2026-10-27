# Data Model: Scenario History

Persisted shape: [contracts/history-storage.schema.json](contracts/history-storage.schema.json).
Only user inputs are stored (FR-002, FR-003, FR-004, FR-016).

## SavedScenario (persisted)

| Field | Type | Rule |
|---|---|---|
| `id` | string | `crypto.randomUUID()`, unique, never reused |
| `name` | string | 1–80 chars. Default from R5 until renamed |
| `nameIsCustom` | boolean | true after a user rename. While false, the name follows the track and category |
| `track` | GeoJSON `LineString` \| `Point` | The thinned track (feature-001 `thinTrack`), with coordinates in [lon, lat] |
| `category` | 1–5 | |
| `cutoff_km` | number | 25–200, step 5 |
| `questions` | SavedQuestion[] | In asked order. At most 100 per scenario; beyond that, the oldest is dropped |
| `created_at` | ISO string | Set when the track is first drawn |
| `updated_at` | ISO string | Set on every change |
| `last_opened_at` | ISO string | Set on create and on every open. Drives list order and eviction |

**Never stored**: band, affected counties or shelters, receiving list, summaries, distances,
agent answers, grounding metadata or Maps content.

## SavedQuestion (persisted)

| Field | Type | Rule |
|---|---|---|
| `text` | string | 1–2000 chars, exactly what the user sent (not the `CONTEXT v1` part) |
| `asked_at` | ISO string | |

## HistoryDocument (persisted, `localStorage["gsr.scenarioHistory.v1"]`)

`{ version: 1, scenarios: SavedScenario[] }`, with at most 50 scenarios. On load, a document that
fails validation is ignored (and left untouched), and the history starts empty in memory. One bad
entry never breaks the app.

## Store additions (in memory, `frontend/src/state/store.tsx`)

| Field | Type | Meaning |
|---|---|---|
| `history` | SavedScenario[] | Mirror of the persisted list |
| `currentScenarioId` | string \| null | The scenario being explored. null after New simulation until a track is drawn |
| `resimulatedAt` | string \| null | Set when a scenario is opened from history. Cleared on New simulation or a new draw |
| `historyAvailable` | boolean | false when storage threw, which drives the "can't be saved" note |
| `notice` | string \| null | One-off message, e.g. an eviction |

## State transitions

```text
                 draw (no current)                    redraw / category / cutoff / ask / rename
   [no scenario] ───────────────────▶ [current: S] ──────────────────────────────────▶ [current: S] (same id, saved)
        ▲                                   │
        │  New simulation                   │ open T from History
        └───────────────────────────────────┤──────────────────────▶ [current: T, resimulatedAt=now]
                                            │ delete S (current)
                                            └──────────────────────▶ [no scenario]
```

| Action | Effect |
|---|---|
| `setTrack` | If `currentScenarioId` is null, create a SavedScenario (evicting if full) and make it current. Otherwise replace the current scenario's track. Either way, update the default name if not custom, set `updated_at`, and clear `resimulatedAt` |
| `setCategory` / `setCutoff` | Update the current scenario, if any (the same id) |
| `chatStart` | If there is a current scenario, append `{text, asked_at}` |
| `newSimulation` | Clear the scenario, chat and `resimulatedAt`; set `currentScenarioId` to null; reset the agent session. Replaces the old `resetScenario` |
| `openScenario(id)` | Load the saved inputs into `scenario`, set `currentScenarioId = id`, `last_opened_at = now`, `resimulatedAt = now`, clear chat, reset the agent session |
| `renameScenario(id, name)` | Set `name` and `nameIsCustom = true` |
| `deleteScenario(id)` | Remove it. If it was current, behave like `newSimulation` |
| `historyLoaded(list, available)` | Set once at start from storage |
