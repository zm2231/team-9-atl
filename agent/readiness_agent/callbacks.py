"""Agent callbacks: the on-demand Google Maps wheelchair check and the per-turn live-check cap.

The frontend sends CHECK_WHEELCHAIR_COMMAND on a dedicated session. Returning Content from a
before_agent_callback ends the turn with that content, so the root model is never invoked.
"""

from __future__ import annotations

import json
import os

from google.genai import types

from . import map_data, wheelchair_check

CHECK_WHEELCHAIR_COMMAND = "CHECK_WHEELCHAIR v1"
LIVE_CHECK_TOOL = "check_shelter_google_maps"
MAX_LIVE_CHECKS_PER_TURN = 3
_LIVE_CHECKS_KEY = "temp:live_checks"


def _user_text(callback_context) -> str:
    content = getattr(callback_context, "user_content", None)
    if not content or not content.parts:
        return ""
    return "".join(p.text or "" for p in content.parts).strip()


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


def cap_live_checks_callback(tool, args, tool_context) -> dict | None:
    """Each Places lookup takes seconds, so one turn live-checks at most MAX_LIVE_CHECKS_PER_TURN
    shelters; later calls in the same turn get a skipped result instead of a lookup."""
    if tool.name != LIVE_CHECK_TOOL:
        return None
    turn = tool_context.invocation_id
    seen = tool_context.state.get(_LIVE_CHECKS_KEY) or {}
    count = seen.get("count", 0) if seen.get("turn") == turn else 0
    if count >= MAX_LIVE_CHECKS_PER_TURN:
        return {
            "status": "skipped",
            "shelter_id": args.get("shelter_id"),
            "message": f"Live check limit reached: at most {MAX_LIVE_CHECKS_PER_TURN} shelters are "
                       "checked per question. Report this shelter as not live-checked.",
            "candidates": [],
            "source": "Google Maps · Places API (not checked; per-question limit)",
        }
    tool_context.state[_LIVE_CHECKS_KEY] = {"turn": turn, "count": count + 1}
    return None
