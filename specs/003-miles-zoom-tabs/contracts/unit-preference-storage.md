# Contract: Distance unit preference in browser storage

**Key**: `gsr.distanceUnit.v1`
**Storage**: `window.localStorage` (per browser and origin)
**Value**: the bare string `mi` or `km`. It is not JSON-encoded.

## Read: `loadUnit(storage: Storage | null): "mi" | "km"`

| Stored value | Result |
|---|---|
| `"mi"` | `"mi"` |
| `"km"` | `"km"` |
| missing (`null`) | `"mi"` |
| anything else (`"miles"`, `"KM"`, `"{}"`, …) | `"mi"`, and the stored value is left untouched |
| `storage` is `null`, or `getItem` throws | `"mi"` |

## Write: `saveUnit(storage: Storage | null, unit): boolean`

- Calls `setItem("gsr.distanceUnit.v1", unit)`. Returns `true` on success.
- Returns `false` when `storage` is `null` or `setItem` throws, for example on a quota error or in private mode. The app keeps working with the in-memory choice for this visit, and no notice is shown.

## Guarantees

- The unit is never written into `gsr.scenarioHistory.v1`, and reopening a scenario never changes it (FR-003).
- No other module reads or writes this key.
