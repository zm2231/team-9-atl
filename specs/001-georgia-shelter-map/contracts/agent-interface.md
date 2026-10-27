# Contract: Frontend ↔ Agent Service

There is one origin, behind IAP. Paths are the standard ADK FastAPI routes (research R1). The app
name is `readiness_agent`. The user ID is a random per-browser-tab UUID, because identity is
already enforced by IAP and the app keeps no user state.

## 1. Sessions

```
POST /apps/readiness_agent/users/{user_id}/sessions          → 200 { "id": "<session_id>", ... }
```

The frontend creates **two** sessions per tab: `mapSession` (used once for data) and `chatSession`.

## 2. Session-start map data (FR-008a)

```
POST /run
{
  "app_name": "readiness_agent",
  "user_id": "<user_id>",
  "session_id": "<mapSession>",
  "new_message": { "role": "user", "parts": [ { "text": "LOAD_MAP_DATA v1" } ] }
}
→ 200 [ Event, ... ]
```

- The agent's `before_agent_callback` matches the text exactly, `LOAD_MAP_DATA v1`, and replies
  with **one** event whose `content.parts[0].text` is a JSON document that validates against
  [map-data.schema.json](map-data.schema.json).
- **No LLM call is made** for this request.
- The frontend takes the last event with author `readiness_agent`, parses the text, and checks that
  `schema == "map-data/v1"`.
- **Failure**: a non-200 status, an unparseable payload, a schema mismatch, or a timeout over 20 s
  (SC-004a). The frontend shows the FR-008b error state with Retry and never shows partial counts.
- Hovering never triggers a request. The payload is held for the session.

## 3. Chat turn (FR-010–FR-015)

```
POST /run_sse
{
  "app_name": "readiness_agent",
  "user_id": "<user_id>",
  "session_id": "<chatSession>",
  "streaming": true,
  "new_message": {
    "role": "user",
    "parts": [
      { "text": "<the user's question>" },
      { "text": "CONTEXT v1 {\"county_fips\":\"13067\",\"shelter_id\":null,\"scenario\":{...}}" }
    ]
  }
}
→ text/event-stream of `data: <Event JSON>`
```

The `scenario` object, when present, holds `track` (GeoJSON), `category`, `cutoff_km`,
`affected_county_fips[]`, `affected_shelter_ids[]` and `receiving_top[]` (the first 20 shelter IDs
in rank order).

**What the frontend reads from each Event:**

| Event field | Used for |
|---|---|
| `content.parts[].text` (author = agent, `partial` true or false) | Answer text, assembled in order |
| `content.parts[].functionResponse.response` | Any `shelter_id` or `county_fips` values found, recursively, go into `referenced_*` and are highlighted (FR-014) |
| `groundingMetadata.groundingChunks[].maps` `{uri, title, placeId}` | Sources (FR-012). `placeId` is held in memory only |
| `groundingMetadata.groundingSupports[]` `{segment{startIndex?, endIndex, text}, groundingChunkIndices[]}` | Marks spans as live (FR-013). A null `startIndex` is treated as 0 |
| `content.parts[].functionResponse.response.live_check` `{shelter_id, status, place_id, checked_at}` | From the `record_live_check` tool. `status` is `exists`, `renamed`, `closed` or `unknown`. The frontend keeps only `status`, `place_id` and the time, and marks `renamed`/`closed` shelters on the map |
| `error` / `error_details` | ADK `/run_sse` mid-stream failure (verified in ADK 2.13). Shows the failed state with Retry (FR-015) |
| `errorCode` / `errorMessage` | Model-side error on an event. Shows the failed state with Retry (FR-015) |

**Tools whose results the frontend reads** (`agent/readiness_agent/evacuation_tools.py`). Every
result carries a `source` naming its dataset and table (Constitution III):

| Tool | Result | Used for |
|---|---|---|
| `assess_shelter_accessibility(state, county, county_fips, limit)` | `{shelters: shelter_record[], wheelchair: {yes,no,unrecorded}, source}` | Highlighting (`shelter_id`, `county_fips`) |
| `get_shelters(shelter_ids)` | `{shelters: shelter_record[], source}`, in the order given, at most 25 | The `CONTEXT v1` `shelter_id`, scenario `receiving_top` and `affected_shelter_ids` |
| `find_vulnerable_tracts(state, county, county_fips, limit)` | `{tracts: [...], source}` | Highlighting (`county_fips`) |
| `find_power_dependent_counties(state, county, county_fips, limit)` | `{counties: [...], source}` | Highlighting (`county_fips`). County-level only |
| `build_readiness_brief(county_fips, tract_limit, destination_limit)` | `{county_fips, who_cannot_leave, where_they_would_go, what_to_fix, could_not_tell}` | Highlighting (`shelter_id` in destinations), counted "what we could not tell you" |
| `record_live_check(shelter_id, status, place_id)` | `{live_check: {...}}` | The discrepancy marker (spec edge case, FR-008) |

`shelter_record` is the same shape as a map-data `Shelter` (`agent/readiness_agent/map_data.py`),
with flags as `YES`/`NO`/`UNRECORDED`.

**What this feature requires of the readiness agent (dependencies D1 and D2):**

1. Tool results that concern shelters or counties include `shelter_id` or `county_fips`.
2. The agent treats the `CONTEXT v1` part as context, not as a question, and it may mention the
   scenario.
3. Accessibility statements keep the Yes / No / Not recorded distinction (Constitution I).
4. Grounded output changes or annotates a result (Constitution II). Rendering it correctly is this
   feature's job.

## 4. Access (FR-023, FR-024)

- IAP rejects unauthenticated or non-allow-listed requests before they reach the service. The
  browser gets IAP's sign-in or denial page. The app never loads.
- Allow-list changes are made by granting or revoking `roles/iap.httpsResourceAccessor`. They need
  no code change or redeploy.

## 5. Versioning

- `LOAD_MAP_DATA v1`, `CONTEXT v1` and `map-data/v1` are versioned strings.
- A breaking change to the payload bumps all three together.
- The frontend refuses any schema version it does not know.
