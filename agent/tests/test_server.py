"""The map payload is served from memory at GET /map-data, gzipped when asked, never via the model."""

import gzip
import json

from fastapi.testclient import TestClient

from readiness_agent import map_data


def test_map_data_endpoint_serves_cached_gzip(monkeypatch, tmp_path):
    monkeypatch.setenv("GOOGLE_CLOUD_PROJECT", "p")
    monkeypatch.setenv("FRONTEND_DIST", str(tmp_path / "missing"))
    calls = []

    def fake(project, dataset):
        calls.append(project)
        return {"schema": "map-data/v1", "state": "GA"}

    monkeypatch.setattr(map_data, "get_georgia_map_data", fake)
    import server

    server._map.update(body=b"", gz=b"", at=0.0)
    client = TestClient(server.app)
    first = client.get("/map-data", headers={"accept-encoding": "gzip"})
    assert first.status_code == 200
    assert json.loads(first.content)["schema"] == "map-data/v1"
    assert first.headers["content-encoding"] == "gzip"
    assert json.loads(gzip.decompress(server._map["gz"]))["state"] == "GA"
    client.get("/map-data")
    assert calls == ["p"]


def test_map_data_error_is_reported(monkeypatch, tmp_path):
    monkeypatch.setenv("GOOGLE_CLOUD_PROJECT", "p")
    monkeypatch.setenv("FRONTEND_DIST", str(tmp_path / "missing"))

    def boom(project, dataset):
        raise RuntimeError("table not found")

    monkeypatch.setattr(map_data, "get_georgia_map_data", boom)
    import server

    server._map.update(body=b"", gz=b"", at=0.0)
    res = TestClient(server.app).get("/map-data")
    assert res.status_code == 503
    assert "table not found" in res.json()["error"]
