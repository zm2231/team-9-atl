"""Contract §1–2 through the real ADK routes: the map-data command never reaches the model."""

import json

from fastapi.testclient import TestClient

from readiness_agent import callbacks


def test_load_map_data_over_run(monkeypatch, tmp_path):
    monkeypatch.setenv("GOOGLE_CLOUD_PROJECT", "p")
    monkeypatch.setenv("FRONTEND_DIST", str(tmp_path / "missing"))
    monkeypatch.setattr(callbacks.map_data, "get_georgia_map_data",
                        lambda project, dataset: {"schema": "map-data/v1", "state": "GA"})
    import server

    client = TestClient(server.app)
    sid = client.post("/apps/readiness_agent/users/u1/sessions").json()["id"]
    events = client.post("/run", json={
        "app_name": "readiness_agent", "user_id": "u1", "session_id": sid,
        "new_message": {"role": "user", "parts": [{"text": "LOAD_MAP_DATA v1"}]},
    })
    assert events.status_code == 200, events.text
    last = [e for e in events.json() if e.get("author") == "readiness_agent"][-1]
    assert json.loads(last["content"]["parts"][0]["text"])["schema"] == "map-data/v1"
