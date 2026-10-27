"""Session-start map data, served through the agent without an LLM call (research R2).

The frontend sends exactly LOAD_MAP_DATA_COMMAND on a dedicated session. Returning Content from a
before_agent_callback ends the turn with that content, so the root model is never invoked.
CHECK_WHEELCHAIR_COMMAND works the same way for the on-demand Google Maps wheelchair check.
"""

from __future__ import annotations

import json
import os

from google.genai import types

from . import map_data, wheelchair_check

LOAD_MAP_DATA_COMMAND = "LOAD_MAP_DATA v1"
CHECK_WHEELCHAIR_COMMAND = "CHECK_WHEELCHAIR v1"


def _user_text(callback_context) -> str:
    content = getattr(callback_context, "user_content", None)
    if not content or not content.parts:
        return ""
    return "".join(p.text or "" for p in content.parts).strip()


def load_map_data_callback(callback_context) -> types.Content | None:
    if _user_text(callback_context) != LOAD_MAP_DATA_COMMAND:
        return None
    try:
        payload = _map_data()
    except Exception as exc:  # surfaced to the frontend's failed state, never as partial data
        payload = {"schema": map_data.SCHEMA, "error": f"{type(exc).__name__}: {exc}"}
    return types.Content(role="model", parts=[types.Part(text=json.dumps(payload))])


def _map_data() -> dict:
    return map_data.get_georgia_map_data(
        os.environ["GOOGLE_CLOUD_PROJECT"], os.environ.get("EVAC_DATASET", "evac_prod")
    )


def check_wheelchair_callback(callback_context) -> types.Content | None:
    """`CHECK_WHEELCHAIR v1 ["<shelter_id>", ...]`: names and addresses come from our own
    registry payload, never from the request, and only blank wheelchair records are checked."""
    text = _user_text(callback_context)
    if not text.startswith(CHECK_WHEELCHAIR_COMMAND + " "):
        return None
    try:
        ids = json.loads(text[len(CHECK_WHEELCHAIR_COMMAND):])
        if not isinstance(ids, list):
            raise ValueError("expected a JSON list of shelter ids")
        wanted = {str(i) for i in ids}
        shelters = [
            s for s in _map_data()["shelters"]
            if s["shelter_id"] in wanted and s["wheelchair_accessible"] == "UNRECORDED"
        ]
        body = {"results": wheelchair_check.check_wheelchair(shelters)}
    except Exception as exc:
        body = {"error": f"{type(exc).__name__}: {exc}"}
    return types.Content(role="model", parts=[types.Part(text=json.dumps(body))])
