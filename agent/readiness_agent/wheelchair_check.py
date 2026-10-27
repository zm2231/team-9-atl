"""Live Google Maps check for shelters whose registry wheelchair record is blank.

One Gemini call with Grounding with Google Maps per shelter, asked by name and street address
(never an area question: the Maps probe showed those answer with unrelated places). The result is
a second, unverified source shown next to the registry's "not recorded"; it never becomes a
registry yes/no. Nothing is cached or stored here (FR-022): the frontend keeps it for the session.
"""

from __future__ import annotations

import os
import re
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from typing import Any, Mapping

MAX_SHELTERS = 3
_WORKERS = 5

PROMPT = """\
This is hurricane-shelter preparedness planning, not emergency response. Use Google Maps to look
up this one building:

  {name}, {address}

Answer in exactly these three lines and nothing else:
PLACE: same | renamed | gone | not_found
WHEELCHAIR: accessible_entrance | no_accessible_entrance | unknown
EVIDENCE: one short sentence saying what Google Maps lists, or "none"

Use accessible_entrance or no_accessible_entrance only if Google Maps lists a specific
wheelchair-accessibility attribute for this place. Otherwise answer unknown. Do not guess.
"""

_WHEELCHAIR_STATUS = {
    "accessible_entrance": "listed_accessible",
    "no_accessible_entrance": "listed_not_accessible",
}


def _field(text: str, name: str) -> str:
    m = re.search(rf"^\s*{name}\s*:\s*(.+)$", text, re.IGNORECASE | re.MULTILINE)
    return m.group(1).strip() if m else ""


def _sources(response: Any) -> list[dict]:
    out = []
    for cand in getattr(response, "candidates", None) or []:
        gm = getattr(cand, "grounding_metadata", None)
        for chunk in getattr(gm, "grounding_chunks", None) or []:
            maps = getattr(chunk, "maps", None)
            if maps and maps.uri:
                out.append({"title": maps.title or maps.uri, "uri": maps.uri,
                            "placeId": getattr(maps, "place_id", None)})
    return out


def parse(shelter_id: str, text: str, sources: list[dict]) -> dict:
    """Conservative coding: no Maps source, no claim. Exported for tests."""
    place = _field(text, "PLACE").lower().split()[0] if _field(text, "PLACE") else "not_found"
    wheelchair = (_field(text, "WHEELCHAIR").lower().split() or ["unknown"])[0]
    evidence = _field(text, "EVIDENCE")
    if not sources or place not in ("same", "renamed", "gone"):
        status, place = "not_found", "not_found"
    else:
        status = _WHEELCHAIR_STATUS.get(wheelchair, "no_info")
    return {
        "shelter_id": shelter_id,
        "status": status,
        "place": place,
        "evidence": "" if evidence.lower() in ("", "none") else evidence,
        "sources": sources,
        "checked_at": datetime.now(timezone.utc).isoformat(),
    }


def _check_one(client: Any, model: str, shelter: Mapping[str, Any]) -> dict:
    from google.genai import types

    sid = shelter["shelter_id"]
    try:
        response = client.models.generate_content(
            model=model,
            contents=PROMPT.format(name=shelter["name"], address=shelter.get("address") or "Georgia"),
            config=types.GenerateContentConfig(
                tools=[types.Tool(google_maps=types.GoogleMaps())], temperature=0
            ),
        )
        return parse(sid, response.text or "", _sources(response))
    except Exception as exc:  # one failed lookup must not sink the batch
        return {"shelter_id": sid, "status": "error", "place": "not_found", "evidence": "",
                "sources": [], "checked_at": datetime.now(timezone.utc).isoformat(),
                "error": f"{type(exc).__name__}: {exc}"}


def check_wheelchair(shelters: list[Mapping[str, Any]], client: Any = None) -> list[dict]:
    """Check up to MAX_SHELTERS shelters (dicts with shelter_id, name, address) in parallel."""
    if client is None:
        from google import genai

        client = genai.Client()
    model = os.getenv("MODEL_NAME", "gemini-3-flash-preview")
    batch = list(shelters)[:MAX_SHELTERS]
    with ThreadPoolExecutor(max_workers=_WORKERS) as pool:
        return list(pool.map(lambda s: _check_one(client, model, s), batch))
