import json
from types import SimpleNamespace

from google.genai import types

from readiness_agent import callbacks


def ctx(text):
    return SimpleNamespace(user_content=types.Content(role="user", parts=[types.Part(text=text)]))


def test_command_returns_map_data_without_llm(monkeypatch):
    monkeypatch.setenv("GOOGLE_CLOUD_PROJECT", "p")
    monkeypatch.setattr(callbacks.map_data, "get_georgia_map_data",
                        lambda project, dataset: {"schema": "map-data/v1", "state": "GA"})
    out = callbacks.load_map_data_callback(ctx("LOAD_MAP_DATA v1"))
    assert json.loads(out.parts[0].text)["schema"] == "map-data/v1"


def test_other_messages_pass_through():
    assert callbacks.load_map_data_callback(ctx("load map data")) is None
    assert callbacks.load_map_data_callback(ctx("How many shelters are in Cobb County?")) is None
    assert callbacks.load_map_data_callback(SimpleNamespace(user_content=None)) is None


def test_bigquery_error_returns_error_payload(monkeypatch):
    monkeypatch.setenv("GOOGLE_CLOUD_PROJECT", "p")

    def boom(project, dataset):
        raise RuntimeError("table not found")

    monkeypatch.setattr(callbacks.map_data, "get_georgia_map_data", boom)
    body = json.loads(callbacks.load_map_data_callback(ctx("LOAD_MAP_DATA v1")).parts[0].text)
    assert body["schema"] == "map-data/v1"
    assert "table not found" in body["error"]


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
