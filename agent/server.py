"""One Cloud Run service: the ADK API plus the built frontend, from the same origin (plan R1, R9)."""

import gzip
import json
import os
import threading
import time
from pathlib import Path

from fastapi import Request
from fastapi.responses import JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from google.adk.cli.fast_api import get_fast_api_app

from guard import RequestGuard
from readiness_agent import map_data

SESSION_TTL = "604800s"
MAP_DATA_MAX_AGE = 600

AGENTS_DIR = Path(__file__).resolve().parent
FRONTEND_DIST = Path(os.environ.get("FRONTEND_DIST", AGENTS_DIR.parent / "frontend" / "dist"))


def _export_traces_to_cloud() -> None:
    """ADK's trace_to_cloud needs its dev UI (web=True), so set the global tracer provider here."""
    from opentelemetry import trace
    from opentelemetry.exporter.cloud_trace import CloudTraceSpanExporter
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor

    provider = TracerProvider(resource=Resource.create({"service.name": "georgia-shelter-readiness"}))
    provider.add_span_processor(
        BatchSpanProcessor(CloudTraceSpanExporter(project_id=os.environ["GOOGLE_CLOUD_PROJECT"]))
    )
    trace.set_tracer_provider(provider)


def _register_expiring_agent_engine_sessions() -> None:
    """Chats go to Agent Engine with a 7-day TTL instead of its 365-day default."""
    from google.adk.cli.service_registry import get_service_registry
    from google.adk.sessions.vertex_ai_session_service import VertexAiSessionService

    class ExpiringSessions(VertexAiSessionService):
        async def create_session(self, **kwargs):
            kwargs.setdefault("ttl", SESSION_TTL)
            return await super().create_session(**kwargs)

    def factory(uri: str, **_):
        _, project, _, location, _, engine_id = uri.removeprefix("agentengine://").split("/")
        return ExpiringSessions(project=project, location=location, agent_engine_id=engine_id)

    get_service_registry().register_session_service("agentengine", factory)


if os.environ.get("TRACE_TO_CLOUD") == "true":
    _export_traces_to_cloud()
if os.environ.get("SESSION_SERVICE_URI", "").startswith("agentengine://"):
    _register_expiring_agent_engine_sessions()

app = get_fast_api_app(
    agents_dir=str(AGENTS_DIR),
    web=False,
    session_service_uri=os.environ.get("SESSION_SERVICE_URI"),
    use_local_storage=False,
    max_llm_calls=16,
)
_map = {"body": b"", "gz": b"", "at": 0.0}
_map_lock = threading.Lock()


def _refresh_map_data(wait: bool = False) -> None:
    if not _map_lock.acquire(blocking=wait):
        return
    try:
        payload = map_data.get_georgia_map_data(
            os.environ["GOOGLE_CLOUD_PROJECT"], os.environ.get("EVAC_DATASET", "evac_prod")
        )
        body = json.dumps(payload, separators=(",", ":")).encode()
        _map.update(body=body, gz=gzip.compress(body, 6), at=time.monotonic())
    finally:
        _map_lock.release()


@app.get("/map-data")
def get_map_data(request: Request):
    """Shelters, tracts and counties for the map, from memory; refreshed in the background."""
    if not _map["body"]:
        try:
            _refresh_map_data(wait=True)
        except Exception as exc:
            return JSONResponse({"schema": map_data.SCHEMA, "error": f"{type(exc).__name__}: {exc}"}, 503)
    elif time.monotonic() - _map["at"] > MAP_DATA_MAX_AGE:
        threading.Thread(target=_refresh_map_data, daemon=True).start()
    headers = {"cache-control": "private, max-age=300"}
    if "gzip" in request.headers.get("accept-encoding", ""):
        return Response(_map["gz"], media_type="application/json", headers=headers | {"content-encoding": "gzip"})
    return Response(_map["body"], media_type="application/json", headers=headers)


if os.environ.get("K_SERVICE"):
    threading.Thread(target=_refresh_map_data, daemon=True).start()

api_prefixes = {route.path.split("/")[1] for route in app.routes}

# Mounted last so /apps, /run and /run_sse resolve to the ADK routes first.
if FRONTEND_DIST.is_dir():
    app.mount("/", StaticFiles(directory=FRONTEND_DIST, html=True), name="frontend")

app.add_middleware(RequestGuard, api_prefixes=api_prefixes,
                   password=os.environ.get("ACCESS_PASSWORD"))

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", "8080")))
