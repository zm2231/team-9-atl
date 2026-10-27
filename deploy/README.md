# Deploying the agent

The ADK agent in `agent/` runs on Cloud Run as `evac-readiness-agent` (project `qwiklabs-gcp-04-edc952746633`, region `us-east1`).

- Live URL: https://evac-readiness-agent-hcodkdjhka-ue.a.run.app
- It serves the shelter map at `/` and the ADK REST API at `/apps`, `/run` and `/run_sse` (app `readiness_agent`).
- Every push to `main` that touches `agent/`, `frontend/`, `deploy/`, `Dockerfile` or the workflow redeploys through `.github/workflows/deploy-agent.yml`. It can also be run by hand from the Actions tab.

## Access

`deploy/access.sh team|public` picks who can open the service. Deploys keep whichever mode is set.

- `team`: Identity-Aware Proxy sign-in for the Google accounts in `deploy/iap_members.txt`. To add someone, add a line and rerun the script. Accounts outside the lab organization also need the IAP OAuth consent screen set to External in the Cloud Console.
- `public`: no sign-in. The browser asks for a shared password (any user name), stored in Secret Manager as `access-password`.

Either way, `agent/guard.py` admits only the requests the frontend makes (static files, session create, `/run`, `/run_sse`, `/health`), caps request bodies at 64 KB and refuses cross-origin requests, and rate-limits agent runs per client (10 a minute, 120 an hour) and overall (60 a minute, 600 an hour). Counters live in the one instance's memory and start over when it restarts, so the per-minute limits are the firm ones. ADK repeats the origin check and sends no CORS headers, each run is capped at 16 model calls, and Cloud Run runs at most one instance.

## How it fits together

| Piece | What it does |
|---|---|
| `Dockerfile` | Builds `frontend/` with Node, then a Python 3.12 image runs `agent/server.py` (uvicorn), which serves the ADK API and the built frontend |
| `deploy/config.sh` | Project, region, service and account names, shared by both scripts |
| `deploy/setup_gcp.sh` | One-time, idempotent: Artifact Registry repo `team9`, runtime account `evac-agent-run` (BigQuery read, Vertex AI, MCP, Routes key), deployer account `github-deployer`, Workload Identity Federation for GitHub Actions on `main`, then `access.sh team` |
| `deploy/access.sh` | Switches between IAP sign-in and public with a shared password |
| `deploy/deploy.sh [tag]` | Build for linux/amd64, push to Artifact Registry, deploy to Cloud Run |

GitHub Actions authenticates with Workload Identity Federation; there is no service-account key. Only pushes to `main` of `zm2231/team-9-atl` can assume the deployer. Repository variables `GCP_WIF_PROVIDER` and `GCP_DEPLOY_SA` hold the two identifiers that `setup_gcp.sh` prints.

## Deploy by hand

```
gcloud auth login && gcloud config set project qwiklabs-gcp-04-edc952746633
deploy/deploy.sh
```

Needs Docker and an account that can push to Artifact Registry and deploy to Cloud Run.

## Run locally

```
See `agent/README.md`.
```

Routes API: Cloud Run gets `ROUTES_API_KEY` from Secret Manager secret `routes-api-key`, a key restricted to `routes.googleapis.com`. Send it as `X-Goog-Api-Key`. Drive times are fetched live and never stored.

Live shelter status: enable Places API (New), create an API key restricted to
`places.googleapis.com`, and add it as a new version of Secret Manager secret
`maps-places-api-key` before deploying:

```
gcloud secrets versions add maps-places-api-key \
  --project qwiklabs-gcp-04-edc952746633 \
  --data-file=/path/to/restricted-places-api-key
```

`deploy/setup_gcp.sh` enables Places API and grants the runtime service account
access to this secret. `deploy/deploy.sh` injects it as `GOOGLE_MAPS_API_KEY`.
The Maps lookup reports Google Maps listing status and opening hours only; it
cannot confirm that a shelter is accepting evacuees or has capacity.

Tracing: Cloud Run sets `TRACE_TO_CLOUD=true`, so ADK exports a span for each agent run, model call and tool call to Cloud Trace (console: Trace explorer). Locally it is off unless you set the variable.

Runtime settings (both `.env` and Cloud Run): `GOOGLE_GENAI_USE_VERTEXAI=TRUE`, `GOOGLE_CLOUD_LOCATION=global` (Gemini 3 models are served from `global`), `MODEL_NAME=gemini-3-flash-preview`, `EVAC_DATASET=evac_prod`.

## Data

The agent reads `evac_prod`, a copy of the team's data that changes only when someone runs `deploy/refresh_evac_prod.sh`. The script copies snapshots of `evacuation_readiness` (`*_clean`, `*_flow_staging`) and all of `hurricane_history` into it; rerun it after either source changes. Tables are copied one at a time, so run it when nobody is mid-demo. Other inputs and model outputs are loaded into `evac_prod` directly, and the refresh script leaves them alone.

The scenario tools read three tables that `refresh_evac_prod.sh` does not create: `scenario_season_county` (one row per county per outlook), `scenario_fix_ranking` and `scenario_batch` (every outlook × switch set × case, statewide and per county). Build or rebuild them with `cd agent && python -m readiness_agent.scenario.build.build_season` (needs BigQuery access; queries are capped at 100 MB billed). `gap_sensitivity` returns `status: "error"` with its `source` until they exist. `python -m readiness_agent.scenario.build.build_siting` writes `scenario_siting` (candidate medical-shelter sites ranked by modelled reduction, read by `recommend_sites`), refreshes `data/siting_candidates.json` and creates the empty `scenario_site_updates` table that `record_site_update` writes to; it needs `shapely` and BigQuery access, and its query is capped at 100 MB billed.
