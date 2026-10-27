# Evacuation readiness agent

This folder is the ADK service behind the Georgia shelter map in [`../frontend`](../frontend). `server.py`
serves the ADK API and the built frontend from one origin. The app is `readiness_agent`:

- `agent.py`: Gemini 3 with Grounding with Google Maps, the purpose-built BigQuery tools in
  `evacuation_tools.py`, and the Google-managed BigQuery MCP server (read-only `execute_sql_readonly`).
- `map_data.py`: `GET /map-data` (in `server.py`) serves the shelters, tracts and counties for the map
  from memory, gzipped; it is built from BigQuery when the service starts and refreshed in the
  background every 10 minutes, with no model call or session. `callbacks.py` answers the
  `CHECK_WHEELCHAIR v1` command the same way. See
  [`specs/001-georgia-shelter-map`](../specs/001-georgia-shelter-map/) for the contract.

Everything reads dataset `evac_prod` (`EVAC_DATASET`). The runtime identity needs
`roles/mcp.toolUser`, `roles/bigquery.jobUser`, `roles/bigquery.dataViewer` and `roles/aiplatform.user`;
`deploy/setup_gcp.sh` grants them to the Cloud Run service account. Deployment: `deploy/README.md`.

## Live Google Maps shelter checks

`check_shelter_google_maps(shelter_id)` reads the shelter's `latitude` and
`longitude` from the configured `shelters_clean` table, then calls the Places
API (New) Text Search with the shelter name, address and a 250 m location bias.
It returns nearby candidate listings, sorted by distance, with each candidate's
`business_status` (`OPERATIONAL`, `CLOSED_TEMPORARILY`,
`CLOSED_PERMANENTLY`, or `UNKNOWN`) and `opening_hours_status` (`open_now`,
`closed_now`, or `not_available`), plus the Google Maps link and check time.
The tool does not assume the closest listing is a match: compare its name,
address and distance with the registry record, and report unknown if the match
is ambiguous.

To enable it:

1. Enable **Places API (New)** in the Google Cloud project and create an API key
   restricted to Places API. The project must have billing enabled for Places
   requests.
2. For local development, set `GOOGLE_MAPS_API_KEY` in the ignored `agent/.env`
   file (see `.env.example`). Never commit the key.
3. For Cloud Run, `deploy/setup_gcp.sh` enables Places API, creates the
   `maps-places-api-key` Secret Manager secret if needed, and grants the runtime
   service account access. Add the restricted key as a secret version before
   deploying; `deploy/deploy.sh` exposes it to the process as
   `GOOGLE_MAPS_API_KEY`.

The Places response is fetched on every tool call and is not cached or saved.
`open_now` means only that the Google Maps business listing says it is open at
the time of the request. It does **not** mean the shelter is accepting evacuees,
has available beds, or will be open during a storm. Missing opening hours are
`not_available`, not closed. A live answer should identify its specific
candidate and include Google Maps attribution immediately after the statement;
the existing Grounding with Google Maps tool provides source metadata for the UI.
Only the selected `place_id` is retained in a `record_live_check` result.

## Running it locally

```bash
# agent service (Python 3.12+), uses ADC from `gcloud auth application-default login`
cd agent && python -m venv .venv && .venv/bin/pip install -r requirements-dev.txt
cp .env.example .env
.venv/bin/uvicorn server:app --port 8000
.venv/bin/python -m pytest            # no credentials needed

# frontend, in another shell
cd frontend && npm ci && npm run dev  # proxies /apps, /run, /run_sse to :8000
VITE_MOCK_AGENT=1 npm run dev         # or: run against a mocked agent, no backend needed
npm test && npx playwright test
```

## Challenge brief

The rest of this file is the challenge packet's guidance for this folder.

## What has to be true of what you build here

- **An ADK agent**, in Python.
- **At least one tool you built yourself.** A Python function tool, or one you defined in MCP
  Toolbox—either counts. The obvious candidate wraps a shelter query. The more valuable one holds
  the logic that is not a single query: deciding what "reachable" means for a household with no
  vehicle, weighing an unrecorded accessibility flag against a recorded one, turning a list of
  tracts into a readiness brief with a recommendation attached. Consuming only prebuilt generic
  tools and calling that your design does not count.
- **At least one Google-managed MCP server, consumed.** Do not author your own—use BigQuery's
  built-in server or the [MCP Toolbox for Databases](https://github.com/googleapis/mcp-toolbox).
- **Deployed to Google Cloud**—Agent Runtime or Cloud Run, your choice.
- **Your required differentiator: Grounding with Google Maps, genuinely used.** Your agent must
  call it and act on what comes back. Naming it in a slide does not count, and neither does calling
  it once for decoration in a flow that would give the same answer without it.

## Your model choice decides your architecture

**On Gemini 2.5 and older**, a built-in tool cannot share an agent with a function tool of your own:

```
400 INVALID_ARGUMENT—"Unable to submit request because Multiple tools are supported
only when they are all search tools."
```

**On Gemini 3.x it works.** Verified 2026-08-09: `google_maps_grounding` and a BigQuery function
tool in one ADK agent, run end to end, both firing in a single turn. The same request on
`gemini-2.5-flash` still returns the 400.

**Use a 3.x model and keep one agent.** If you pin an older one, you need two, and it is a fine
architecture either way:

- a **maps agent** holding `google_maps_grounding` and nothing else
- your **root agent** holding your function tools, an MCP server, and the maps agent wrapped in
  `AgentTool`

`GoogleMapsGroundingTool` takes no constructor arguments and does not accept
`bypass_multi_tools_limit`, so on an older model the sub-agent is the only route. `google_maps` and
`google_search` coexist on any model.

**Ignore this warning**—it appears once per turn and means nothing here:
`Tools at indices [0] are not compatible with automatic function calling (AFC). AFC is disabled.`
ADK runs its own function-calling loop.

## What Grounding with Google Maps will and will not do

| Will | Will not |
|---|---|
| Find places, addresses, ratings, opening hours | Give you a drive time unless `routing` is in `grounding_types` |
| Tell you whether somewhere is open **right now** | Know anything in our tables—who lives nearby, wheelchair flags, generators |
| Tell you a place has closed, or been renamed | Answer anything but English |
| Say honestly when it does not know | Answer an *area* question about accessibility |

**Accessibility depends on how you ask.** An area question gets you nothing. **One named building at
one address** got a definite answer 5 times out of 8 in our testing, and agreed with FEMA 4 times
out of 5 where both had a view. Iterating over your candidate shelters one at a time is a real
strategy and almost nobody will try it.

Routing is available too: add `routing` to `grounding_types` alongside `places` and the same grounded
call returns drive times and directions ([Routing—Find Directions](https://docs.cloud.google.com/gemini-enterprise-agent-platform/models/grounding/grounding-with-google-maps#routing-find-directions)).
That is the add-on that turns the straight-line distances in our tables into something a planner can
use—the tables themselves carry straight-line distance only. Routing is newer than the rest of the
feature, so if you build on it, test it early. Five to eight seconds per grounded call is normal,
not a bug.

Attribution is a requirement, not a nicety: display the Google Maps sources immediately after the
content they support, viewable within one user interaction, with the words "Google Maps" unmodified
and `translate="no"`. You may keep `place_id` and `review_id`; you may not cache, store or export
the rest of what comes back.

## The thing worth remembering while you build

**Our data knows what a place *is*. Maps knows whether it is *still there*. Neither knows whether it
works for the person you are trying to help.**

FEMA's file is a historical registry. We checked fifteen Florida shelters against Google Maps:
**fourteen still exist, one had been renamed** (same building, new name—a name-only lookup misses
it). So the value of a runtime check is not finding rubble, it is catching the ones that moved or
changed, and knowing what a place is *now*.

The accessibility gap is the harder one. For roughly two thirds of American shelters **nobody has
written it down**, and no amount of grounding creates a record that does not exist.

An agent that reports "no accessible shelters nearby" when it means "nobody recorded any" has
stated a fact about paperwork as a fact about buildings. An agent that says *"eleven of these I can
speak to, sixty-four nobody has assessed"* is more useful, more honest, and will score better.

See the README's "Six defects you will meet" for the data traps and Section 13 of the notebook for
the constraints.
