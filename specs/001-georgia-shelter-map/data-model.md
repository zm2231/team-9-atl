# Data Model: Georgia Shelter Readiness Map

Entities come from [spec.md](spec.md) §Key Entities. Field names are the **wire format** that the
agent sends to the frontend (contracts). TypeScript and Python types mirror them exactly.

## Flag

```text
Flag = "YES" | "NO" | "UNRECORDED"
```

- The only mapping is BigQuery `TRUE` → `YES`, `FALSE` → `NO`, `NULL` → `UNRECORDED`. It lives in
  `agent/readiness_agent/map_data.py`.
- The frontend MUST NOT convert a Flag to a boolean anywhere. Display: Yes / No / **Not recorded**.
  Not recorded uses a distinct neutral pattern, never the "No" color.

## SourcedValue

Every number shown to the user carries where it came from (Constitution III).

| Field | Type | Notes |
|---|---|---|
| `value` | number \| null | null means there is no data. It is shown as "no data", never as 0 |
| `source` | string | MUST name the dataset **and the source table** (Constitution III), e.g. `"FEMA NSS registry · shelters"`, `"ACS 5-yr · vulnerability_tracts"`, `"ACS survey estimate via CDC SVI · vulnerability_tracts"`. Simulation values use `"Simulation (straight-line) · shelters"` |
| `kind` | `"registry"` \| `"survey"` \| `"live"` \| `"simulation"` | Drives the label style (FR-013, FR-019, SC-008) |
| `coverage` | string? | e.g. `"412 of 415 tracts"` when an aggregate has gaps |

## Shelter

Source: `shelters`. It is a registry record and is never edited (FR-008).

| Field | Type | From | Validation / notes |
|---|---|---|---|
| `shelter_id` | string | `shelter_id` | Unique key |
| `name` | string | `shelter_name` | |
| `address` | string | `address_1`, `city`, `zip` | |
| `county_fips` | string \| null | `county_fips` (derived from coordinates) | Null or not `13***` means `location_disagrees` |
| `county_name` | string | `county_name`, falling back to `county_parish` | |
| `lat`, `lon` | number | `latitude`, `longitude` | |
| `evacuation_capacity` | number \| null | `evacuation_capacity` | |
| `post_impact_capacity` | number \| null | `post_impact_capacity` | |
| `usage` | string \| null | `usage` | EVAC / POST as published, shown verbatim; null means "Not recorded" |
| `wheelchair_accessible` | Flag | | |
| `generator_onsite` | Flag | | |
| `is_medical` | Flag | `population_code` contains `MEDICAL` | `UNRECORDED` if `population_code` is null |
| `in_surge_slosh_area` | Flag | | |
| `quality_flags` | (`"suspect_capacity"` \| `"location_disagrees"`)[] | | Suspect if capacity < 0 or > 100,000 (research R7) |
| `live_check` | LiveCheck? | Filled at runtime from chat grounding only | In memory, never persisted |

**LiveCheck** (session memory only): `status` (`exists` \| `renamed` \| `closed` \| `unknown`),
`checked_at` (ISO timestamp), `place_id`, and `sources` (`{title, uri}[]`, rendered and never
stored).

## County

Source: aggregates over `shelters` and `vulnerability_tracts`. Geometry comes from the bundled
asset.

| Field | Type | Rule |
|---|---|---|
| `county_fips` | string | 5-digit, `13***`; joins to the TopoJSON feature `id` |
| `name` | string | |
| `shelter_count` | number | Shelters with this `county_fips` |
| `capacity_total` | SourcedValue | Sum of `evacuation_capacity` **excluding** suspect shelters |
| `capacity_total_incl_suspect` | SourcedValue | Including them (FR-007) |
| `capacity_excluded` | `{shelter_id, name}[]` | The shelters left out of `capacity_total`. Whenever it is non-empty, the UI MUST show its count and names next to the total (FR-007, Constitution VI) |
| `wheelchair` / `generator` / `medical` | `{yes, no, unrecorded}` counts | Always all three (FR-003) |
| `in_surge` | `{yes, no, unrecorded}` | Always all three (FR-003) |
| `households_no_vehicle` | SourcedValue | `SUM` over tracts, kind `survey` |
| `share_65_plus` | SourcedValue | `SUM(pop_65_plus)/SUM(total_pop)`, kind `survey` |
| `share_disability` | SourcedValue | Population-weighted mean of `pct_disability`, with `-999` → null and the coverage noted |
| `centroid` | `[lon, lat]` | Computed in the frontend from geometry (R6) |

A county with `shelter_count = 0` displays "No shelters on file".

## MapData (session-start payload)

`{ schema: "map-data/v1", state: "GA", generated_at, shelters: Shelter[], counties: County[],
notes: string[] }`. The full JSON Schema is
[contracts/map-data.schema.json](contracts/map-data.schema.json). `notes` holds the agent's
"could not tell you" items for the state as a whole, e.g. *"1,344 of 1,792 shelters have no
wheelchair-access record"*.

## HurricaneScenario (frontend state, session only)

| Field | Type | Rule |
|---|---|---|
| `track` | GeoJSON `LineString` \| `Point` | From the drag. Points thinned to ≥ 5 km apart |
| `category` | 1–5 | Default 3 |
| `half_width_km` | number | From the R5 table, derived from category |
| `band` | GeoJSON `Polygon` | `buffer(track, half_width_km)` |
| `cutoff_km` | number | Default 80, range 25–200 |
| `affected_county_fips` | string[] | Counties that intersect the band |
| `affected_shelter_ids` | string[] | Shelters inside the band |
| `receiving` | ReceivingEntry[] | Computed (R6) |

**State transitions**: `none` → (drag starts) `drawing` → (drag ends) `active` →
(category, cutoff or track changed) `active` (recomputed) → (reset) `none`. Recomputing happens
only when a drag ends, not on every pointer move (FR-016/018).

## ReceivingEntry

| Field | Type | Rule |
|---|---|---|
| `shelter_id` | string | Never in `affected_shelter_ids` (SC-005b) |
| `rank` | number | 1-based, by the R6 order |
| `distance_km` | SourcedValue | kind `simulation`, labeled "straight-line" |
| `nearest_affected_county` | string | FIPS of the county whose center is used |
| `reason` | string | e.g. "Largest recorded capacity within 80 km; wheelchair access not recorded" |

Also derived: `unrecorded_wheelchair_count` across the list (FR-018c), and an empty-state message
when the list is empty (edge case).

## ChatExchange (session only)

| Field | Type |
|---|---|
| `question` | string |
| `context` | `{county_fips?, shelter_id?, scenario?}` (contracts §3) |
| `status` | `pending` \| `streaming` \| `done` \| `failed` |
| `segments` | `{text, kind: "live" \| "registry", sources?: {title, uri}[]}[]` |
| `referenced_shelter_ids`, `referenced_county_fips` | string[] (from `functionResponse` payloads) |
