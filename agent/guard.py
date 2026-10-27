"""Request guard so the service can run without IAP: an optional shared password, only the routes
the frontend calls, bounded request bodies, and per-client plus global rate limits on agent runs."""

import base64
import hmac
import json
import re
from collections.abc import Iterable
from urllib.parse import urlsplit

from limits import RateLimitItem, parse_many
from limits.storage import MemoryStorage
from limits.strategies import MovingWindowRateLimiter

MAX_BODY_BYTES = 64 * 1024
CLIENT_RUN_LIMITS = "10/minute;120/hour"
CLIENT_SESSION_LIMITS = "30/hour"
GLOBAL_RUN_LIMITS = "60/minute;600/hour"

_SESSION_CREATE = re.compile(r"^/apps/readiness_agent/users/[A-Za-z0-9_-]{1,64}/sessions$")
_RUN_PATHS = {"/run", "/run_sse"}


class RequestGuard:
    def __init__(
        self,
        app,
        api_prefixes: Iterable[str],
        client_run_limits: str = CLIENT_RUN_LIMITS,
        client_session_limits: str = CLIENT_SESSION_LIMITS,
        global_run_limits: str = GLOBAL_RUN_LIMITS,
        password: str | None = None,
    ):
        self._app = app
        self._password = password.encode() if password else None
        self._api_prefixes = frozenset(api_prefixes)
        self._limiter = MovingWindowRateLimiter(MemoryStorage())
        self._client_run = parse_many(client_run_limits)
        self._client_session = parse_many(client_session_limits)
        self._global_run = parse_many(global_run_limits)

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await _respond(send, 404, "not found")
            return
        method, path = scope["method"], scope["path"]

        if self._password and not self._authorized(scope):
            await _respond(send, 401, "password required",
                           [(b"www-authenticate", b'Basic realm="Shelter readiness", charset="UTF-8"')])
            return

        if path.split("/")[1] not in self._api_prefixes:
            if method in ("GET", "HEAD"):
                await self._app(scope, receive, send)
            else:
                await _respond(send, 405, "method not allowed")
            return

        if method == "GET" and path == "/health":
            await self._app(scope, receive, send)
            return
        if method != "POST" or not (path in _RUN_PATHS or _SESSION_CREATE.match(path)):
            await _respond(send, 404, "not found")
            return

        if not _same_origin(scope):
            await _respond(send, 403, "origin not allowed")
            return

        client = _client_ip(scope)
        if path in _RUN_PATHS:
            checks = [(item, "client", client) for item in self._client_run]
            checks += [(item, "global", "all") for item in self._global_run]
        else:
            checks = [(item, "session", client) for item in self._client_session]
        if not self._hit(checks):
            await _respond(send, 429, "too many requests", [(b"retry-after", b"60")])
            return

        body = b""
        more = True
        while more:
            message = await receive()
            if message["type"] == "http.disconnect":
                return
            body += message.get("body", b"")
            more = message.get("more_body", False)
            if len(body) > MAX_BODY_BYTES:
                await _respond(send, 413, "request too large")
                return

        replayed = False

        async def replay():
            nonlocal replayed
            if not replayed:
                replayed = True
                return {"type": "http.request", "body": body, "more_body": False}
            return await receive()

        await self._app(scope, replay, send)

    def _authorized(self, scope) -> bool:
        for name, value in scope["headers"]:
            if name == b"authorization" and value[:6].lower() == b"basic ":
                try:
                    _, _, given = base64.b64decode(value[6:]).partition(b":")
                except ValueError:
                    return False
                return hmac.compare_digest(given, self._password)
        return False

    def _hit(self, checks: list[tuple[RateLimitItem, str, str]]) -> bool:
        if not all(self._limiter.test(item, scope, key) for item, scope, key in checks):
            return False
        for item, scope, key in checks:
            self._limiter.hit(item, scope, key)
        return True


def _header(scope, name: bytes) -> str | None:
    for key, value in scope["headers"]:
        if key == name:
            return value.decode("latin-1")
    return None


def _same_origin(scope) -> bool:
    origin = _header(scope, b"origin")
    return origin is None or urlsplit(origin).netloc == _header(scope, b"host")


def _client_ip(scope) -> str:
    # Cloud Run's front end appends the connecting address after anything the client sent, so the
    # last entry is the one a client cannot forge.
    forwarded = _header(scope, b"x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[-1].strip()
    return (scope.get("client") or ("unknown",))[0]


async def _respond(send, status: int, detail: str, headers: list[tuple[bytes, bytes]] = ()):
    body = json.dumps({"detail": detail}).encode()
    await send({
        "type": "http.response.start",
        "status": status,
        "headers": [(b"content-type", b"application/json"), *headers],
    })
    await send({"type": "http.response.body", "body": body})
