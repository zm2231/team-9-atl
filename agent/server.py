"""One Cloud Run service: the ADK API plus the built frontend, from the same origin (plan R1, R9)."""

import os
from pathlib import Path

from fastapi.staticfiles import StaticFiles
from google.adk.cli.fast_api import get_fast_api_app

AGENTS_DIR = Path(__file__).resolve().parent
FRONTEND_DIST = Path(os.environ.get("FRONTEND_DIST", AGENTS_DIR.parent / "frontend" / "dist"))

app = get_fast_api_app(
    agents_dir=str(AGENTS_DIR),
    web=False,
    session_service_uri=None,  # in-memory sessions; nothing is persisted
    use_local_storage=False,
)

# Mounted last so /apps, /run and /run_sse resolve to the ADK routes first.
if FRONTEND_DIST.is_dir():
    app.mount("/", StaticFiles(directory=FRONTEND_DIST, html=True), name="frontend")

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", "8080")))
