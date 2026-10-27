# A4I2026-challenge-4-evacuation Development Guidelines

Auto-generated from all feature plans. Last updated: 2026-10-27

## Active Technologies
- Browser `localStorage` key `gsr.scenarioHistory.v1` for scenario history; no new dependencies (002-scenario-history)
- d3-zoom, d3-selection for map zoom/pan (003-miles-zoom-tabs)
- Browser `localStorage` key `gsr.distanceUnit.v1` for the mi/km preference; distances stay km in state and history (003-miles-zoom-tabs)

- TypeScript 5.x, React 18.3, Vite 5, d3-geo, @turf/turf (frontend) (001-georgia-shelter-map)
- Python 3.12, google-adk, google-cloud-bigquery (agent service) (001-georgia-shelter-map)
- BigQuery `<project>.evacuation_readiness`, read-only (001-georgia-shelter-map)

## Project Structure

```text
agent/      ADK agent service (readiness_agent/, server.py, tests/)
frontend/   React app (src/, tests/, scripts/build-ga-counties.mjs)
specs/      Spec Kit feature specs, plans, contracts
notebooks/  Data load and validation (run for GA before building)
```

## Commands

- `cd agent && .venv/bin/python -m pytest` (no credentials needed)
- `cd frontend && npm test` · `npm run dev` · `npx playwright test`
- `cd frontend && VITE_MOCK_AGENT=1 npm run dev` runs the app against a mocked agent
- `cd frontend && npm run build:counties` regenerates the Georgia county asset

## Code Style

TypeScript 5.x and Python 3.12: follow standard conventions. Flags are always
`"YES" | "NO" | "UNRECORDED"`, never booleans (see `.specify/memory/constitution.md`).

## Recent Changes
- 003-miles-zoom-tabs: Planned mi/km toggle (display-only), map zoom/pan with d3-zoom, and a tabbed Chat/Details side panel
- 002-scenario-history: Planned browser-local scenario history (inputs only; results re-simulated on reopen)

- 001-georgia-shelter-map: Added the Georgia shelter map frontend and the agent map-data path

<!-- MANUAL ADDITIONS START -->
<!-- MANUAL ADDITIONS END -->
