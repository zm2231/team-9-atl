"""Session-start map data, served through the agent without an LLM call (research R2).

The frontend sends exactly LOAD_MAP_DATA_COMMAND on a dedicated session. Returning Content from a
before_agent_callback ends the turn with that content, so the model is never invoked.
"""

from __future__ import annotations

import json
import os

from google.genai import types

from . import map_data

LOAD_MAP_DATA_COMMAND = "LOAD_MAP_DATA v1"


def _user_text(callback_context) -> str:
    content = getattr(callback_context, "user_content", None)
    if not content or not content.parts:
        return ""
    return "".join(p.text or "" for p in content.parts).strip()


def load_map_data_callback(callback_context) -> types.Content | None:
    if _user_text(callback_context) != LOAD_MAP_DATA_COMMAND:
        return None
    try:
        payload = map_data.get_georgia_map_data(
            os.environ["GOOGLE_CLOUD_PROJECT"],
            os.environ.get("BQ_DATASET", "evacuation_readiness"),
        )
    except Exception as exc:  # surfaced to the frontend's failed state, never as partial data
        payload = {"schema": map_data.SCHEMA, "error": f"{type(exc).__name__}: {exc}"}
    return types.Content(role="model", parts=[types.Part(text=json.dumps(payload))])
