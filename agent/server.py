"""One Cloud Run service: the ADK API plus the built frontend, from the same origin (plan R1, R9)."""

import os
from pathlib import Path

from fastapi.staticfiles import StaticFiles
from google.adk.cli.fast_api import get_fast_api_app

from guard import RequestGuard

AGENTS_DIR = Path(__file__).resolve().parent
FRONTEND_DIST = Path(os.environ.get("FRONTEND_DIST", AGENTS_DIR.parent / "frontend" / "dist"))


def _export_traces_to_cloud() -> None:
    """ADK's trace_to_cloud needs its dev UI (web=True), so set the global tracer provider here."""
    from opentelemetry import trace
    from opentelemetry.exporter.cloud_trace import CloudTraceSpanExporter
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor

    provider = TracerProvider(resource=Resource.create({"service.name": "evac-readiness-agent"}))
    provider.add_span_processor(
        BatchSpanProcessor(CloudTraceSpanExporter(project_id=os.environ["GOOGLE_CLOUD_PROJECT"]))
    )
    trace.set_tracer_provider(provider)


if os.environ.get("TRACE_TO_CLOUD") == "true":
    _export_traces_to_cloud()

app = get_fast_api_app(
    agents_dir=str(AGENTS_DIR),
    web=False,
    session_service_uri=None,  # in-memory sessions; nothing is persisted
    use_local_storage=False,
    max_llm_calls=16,
)
api_prefixes = {route.path.split("/")[1] for route in app.routes}

# Mounted last so /apps, /run and /run_sse resolve to the ADK routes first.
if FRONTEND_DIST.is_dir():
    app.mount("/", StaticFiles(directory=FRONTEND_DIST, html=True), name="frontend")

app.add_middleware(RequestGuard, api_prefixes=api_prefixes,
                   password=os.environ.get("ACCESS_PASSWORD"))

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", "8080")))
