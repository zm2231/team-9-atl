import base64

import pytest
from fastapi.testclient import TestClient
from starlette.applications import Starlette
from starlette.responses import PlainTextResponse
from starlette.routing import Route

from guard import MAX_BODY_BYTES, RequestGuard


async def ok(request):
    await request.body()
    return PlainTextResponse("ok")


def guarded(**kwargs):
    inner = Starlette(routes=[
        Route("/run", ok, methods=["POST"]),
        Route("/apps/readiness_agent/users/{uid}/sessions", ok, methods=["GET", "POST"]),
        Route("/docs", ok),
        Route("/health", ok),
        Route("/", ok, methods=["GET", "POST"]),
    ])
    return TestClient(RequestGuard(inner, api_prefixes={"run", "apps", "docs", "health"}, **kwargs))


def test_only_frontend_routes_reach_the_app():
    client = guarded()
    assert client.post("/run", content=b"{}").status_code == 200
    assert client.post("/apps/readiness_agent/users/u-1/sessions").status_code == 200
    assert client.get("/health").status_code == 200
    assert client.get("/").status_code == 200
    assert client.get("/docs").status_code == 404
    assert client.get("/apps/readiness_agent/users/u-1/sessions").status_code == 404
    assert client.post("/apps/other_app/users/u-1/sessions").status_code == 404
    assert client.post("/").status_code == 405


def test_body_over_limit_is_rejected():
    client = guarded()
    assert client.post("/run", content=b"x" * (MAX_BODY_BYTES + 1)).status_code == 413


def test_runs_are_limited_per_client_and_globally():
    client = guarded(client_run_limits="2/minute", global_run_limits="3/minute")
    a = {"x-forwarded-for": "203.0.113.1"}
    a_spoofing = {"x-forwarded-for": "6.6.6.6,203.0.113.1"}
    b = {"x-forwarded-for": "203.0.113.2"}
    assert [client.post("/run", headers=h).status_code for h in (a, a_spoofing, a)] == [200, 200, 429]
    assert client.post("/run", headers=b).status_code == 200
    assert client.post("/run", headers=b).status_code == 429


def test_cross_origin_runs_are_refused_before_counting():
    client = guarded(global_run_limits="1/minute")
    elsewhere = {"origin": "https://elsewhere.example"}
    assert [client.post("/run", headers=elsewhere).status_code for _ in range(3)] == [403] * 3
    assert client.post("/run", headers={"origin": "http://testserver"}).status_code == 200


@pytest.mark.parametrize("password,status", [(None, 401), ("wrong", 401), ("s3cret", 200)])
def test_password_gate(password, status):
    client = guarded(password="s3cret")
    headers = {}
    if password:
        headers["authorization"] = "Basic " + base64.b64encode(f"judge:{password}".encode()).decode()
    response = client.get("/", headers=headers)
    assert response.status_code == status
    if status == 401:
        assert response.headers["www-authenticate"].startswith("Basic")


def test_cross_origin_post_is_refused_by_adk(monkeypatch, tmp_path):
    monkeypatch.setenv("GOOGLE_CLOUD_PROJECT", "p")
    monkeypatch.setenv("FRONTEND_DIST", str(tmp_path / "missing"))
    import server

    client = TestClient(server.app)
    response = client.post("/apps/readiness_agent/users/u1/sessions",
                           headers={"origin": "https://elsewhere.example"})
    assert response.status_code == 403
    assert "access-control-allow-origin" not in response.headers
    assert client.get("/openapi.json").status_code == 404
