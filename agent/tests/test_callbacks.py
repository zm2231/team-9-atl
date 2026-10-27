import json
from types import SimpleNamespace

from google.genai import types

from readiness_agent import callbacks


def ctx(text):
    return SimpleNamespace(user_content=types.Content(role="user", parts=[types.Part(text=text)]))


MAP = {"schema": "map-data/v1", "shelters": [
    {"shelter_id": "1", "name": "Blank School", "address": "1 Main St", "wheelchair_accessible": "UNRECORDED"},
    {"shelter_id": "2", "name": "Known School", "address": "2 Main St", "wheelchair_accessible": "YES"},
]}


def test_wheelchair_check_only_sends_blank_records_from_our_payload(monkeypatch):
    monkeypatch.setenv("GOOGLE_CLOUD_PROJECT", "p")
    monkeypatch.setattr(callbacks.map_data, "get_georgia_map_data", lambda project, dataset: MAP)
    seen = []
    monkeypatch.setattr(callbacks.wheelchair_check, "check_wheelchair",
                        lambda shelters: seen.extend(shelters) or [{"shelter_id": "1"}])
    out = callbacks.check_wheelchair_callback(ctx('CHECK_WHEELCHAIR v1 ["1", "2", "999"]'))
    assert json.loads(out.parts[0].text) == {"results": [{"shelter_id": "1"}]}
    assert [s["name"] for s in seen] == ["Blank School"]


def test_wheelchair_check_bad_body_is_an_error_not_a_crash(monkeypatch):
    out = callbacks.check_wheelchair_callback(ctx('CHECK_WHEELCHAIR v1 {"id": 1}'))
    assert "error" in json.loads(out.parts[0].text)
    assert callbacks.check_wheelchair_callback(ctx("CHECK_WHEELCHAIR")) is None
    assert callbacks.check_wheelchair_callback(ctx("LOAD_MAP_DATA v1")) is None
