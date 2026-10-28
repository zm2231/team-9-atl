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
    assert out is not None and out.parts
    assert json.loads(out.parts[0].text) == {"results": [{"shelter_id": "1"}]}
    assert [s["name"] for s in seen] == ["Blank School"]


def test_wheelchair_check_bad_body_is_an_error_not_a_crash(monkeypatch):
    out = callbacks.check_wheelchair_callback(ctx('CHECK_WHEELCHAIR v1 {"id": 1}'))
    assert out is not None and out.parts
    assert "error" in json.loads(out.parts[0].text)
    assert callbacks.check_wheelchair_callback(ctx("CHECK_WHEELCHAIR")) is None
    assert callbacks.check_wheelchair_callback(ctx("LOAD_MAP_DATA v1")) is None


def tool_ctx(invocation_id, state):
    return SimpleNamespace(invocation_id=invocation_id, state=state)


def test_live_checks_are_capped_per_turn_and_reset_on_the_next():
    maps, other = SimpleNamespace(name="check_shelter_google_maps"), SimpleNamespace(name="get_shelters")
    state = {}
    turn1 = [callbacks.cap_live_checks_callback(maps, {"shelter_id": str(i)}, tool_ctx("t1", state))
             for i in range(5)]
    assert turn1[:3] == [None, None, None]
    skipped = [r for r in turn1[3:] if r is not None]
    assert [(r["status"], r["shelter_id"]) for r in skipped] == [("skipped", "3"), ("skipped", "4")]
    assert callbacks.cap_live_checks_callback(other, {}, tool_ctx("t1", state)) is None
    assert callbacks.cap_live_checks_callback(maps, {"shelter_id": "9"}, tool_ctx("t2", state)) is None
