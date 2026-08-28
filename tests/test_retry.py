"""Retry behaviour of the sync and async API clients.

Both clients retry transient 5xx responses for idempotent methods only. Methods outside
``RETRYABLE_METHODS`` — POST and PATCH — surface the first failure to the caller, so a
request that may have taken effect server-side is never replayed without the caller asking.

Timing is deliberately not asserted here: the sync backoff belongs to urllib3 and pinning it
would couple these tests to urllib3 internals. Sleeps are stubbed out for speed only.
"""

from __future__ import annotations

import asyncio
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Callable, List, Optional

import httpx
import pytest
import requests
import urllib3.util.retry

from kognic.auth import MAX_RETRIES, RETRYABLE_METHODS
from kognic.auth.httpx.base_client import BaseAsyncApiClient
from kognic.auth.requests.auth_session import RequestsAuthSession
from kognic.auth.requests.base_client import DEFAULT_RETRY, create_session

TOTAL_ATTEMPTS = MAX_RETRIES + 1

# Far-future expiry so authlib never attempts a token refresh during a test.
_NEVER_EXPIRES = 32503680000


@pytest.fixture(autouse=True)
def _no_sleeping(monkeypatch):
    """Remove real backoff delays so the suite stays fast.

    Only the number of attempts is under test, never the delay between them.
    """

    async def _async_noop(_seconds):
        return None

    monkeypatch.setattr(asyncio, "sleep", _async_noop)
    monkeypatch.setattr(urllib3.util.retry.Retry, "sleep", lambda self, response=None: None)


class _StatusSequence:
    """Replays a fixed sequence of status codes, repeating the last one once exhausted."""

    def __init__(self, statuses: List[int]):
        self._statuses = list(statuses)
        self._index = 0
        self.count = 0

    def next_status(self) -> int:
        self.count += 1
        status = self._statuses[min(self._index, len(self._statuses) - 1)]
        self._index += 1
        return status


def _async_client(sequence: _StatusSequence) -> BaseAsyncApiClient:
    """Build an async client whose transport replays ``sequence`` instead of hitting the network."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(sequence.next_status(), json={"message": "transient"})

    client = BaseAsyncApiClient(auth=("client-id", "client-secret"), transport=httpx.MockTransport(handler))
    client._oauth_client.token = {
        "access_token": "access-token",
        "token_type": "Bearer",
        "expires_at": _NEVER_EXPIRES,
    }
    return client


async def _async_attempts(method: str, statuses: List[int]) -> tuple[int, Optional[int]]:
    """Issue one request and report how many attempts reached the transport.

    Returns ``(attempts, status)`` where status is None if the call raised.
    """
    sequence = _StatusSequence(statuses)
    client = _async_client(sequence)
    try:
        session = await client.session
        try:
            resp = await session.request(method, "https://example.invalid/resource")
        except httpx.HTTPStatusError:
            return sequence.count, None
        return sequence.count, resp.status_code
    finally:
        await client.close()


class _CountingHandler(BaseHTTPRequestHandler):
    """Serves a caller-supplied status sequence and counts every request received."""

    sequence: _StatusSequence

    def _respond(self):
        status = self.sequence.next_status()
        body = b'{"message": "transient"}'
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    do_GET = _respond
    do_POST = _respond
    do_PUT = _respond
    do_PATCH = _respond

    def log_message(self, format, *args):  # noqa: A002
        """Silence per-request stderr logging so test output stays pristine."""


class _StubTokenProvider:
    """Minimal stand-in for RequestsAuthSession; the tests never exercise token refresh."""

    def ensure_token(self) -> dict:
        return {"access_token": "access-token"}

    def invalidate_token(self) -> None:
        raise AssertionError("token invalidation is not expected in retry tests")


def _sync_attempts(method: str, statuses: List[int]) -> tuple[int, Optional[int]]:
    """Issue one request against a local server and report how many attempts it received."""
    sequence = _StatusSequence(statuses)
    handler: Callable = type("_Handler", (_CountingHandler,), {"sequence": sequence})
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        session = create_session(token_provider=_StubTokenProvider())
        url = f"http://127.0.0.1:{server.server_port}/resource"
        try:
            resp = session.request(method, url)
        except (requests.HTTPError, requests.exceptions.RetryError):
            return sequence.count, None
        return sequence.count, resp.status_code
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


ALWAYS_503 = [503]
RECOVERS_ON_LAST_ATTEMPT = [503, 503, 503, 200]


class TestAsyncRetry:
    async def test_post_is_not_retried(self):
        attempts, status = await _async_attempts("POST", ALWAYS_503)
        assert attempts == 1
        assert status is None

    async def test_lowercase_post_is_not_retried(self):
        attempts, _ = await _async_attempts("post", ALWAYS_503)
        assert attempts == 1

    async def test_patch_is_not_retried(self):
        attempts, _ = await _async_attempts("PATCH", ALWAYS_503)
        assert attempts == 1

    async def test_get_is_retried_until_attempts_are_exhausted(self):
        attempts, status = await _async_attempts("GET", ALWAYS_503)
        assert attempts == TOTAL_ATTEMPTS
        assert status is None

    async def test_get_returns_the_first_success(self):
        attempts, status = await _async_attempts("GET", RECOVERS_ON_LAST_ATTEMPT)
        assert attempts == TOTAL_ATTEMPTS
        assert status == 200

    async def test_put_is_retried(self):
        attempts, _ = await _async_attempts("PUT", ALWAYS_503)
        assert attempts == TOTAL_ATTEMPTS


class TestSyncRetry:
    def test_post_is_not_retried(self):
        attempts, status = _sync_attempts("POST", ALWAYS_503)
        assert attempts == 1
        assert status is None

    def test_patch_is_not_retried(self):
        attempts, _ = _sync_attempts("PATCH", ALWAYS_503)
        assert attempts == 1

    def test_get_is_retried_until_attempts_are_exhausted(self):
        attempts, status = _sync_attempts("GET", ALWAYS_503)
        assert attempts == TOTAL_ATTEMPTS
        assert status is None

    def test_get_returns_the_first_success(self):
        attempts, status = _sync_attempts("GET", RECOVERS_ON_LAST_ATTEMPT)
        assert attempts == TOTAL_ATTEMPTS
        assert status == 200

    def test_put_is_retried(self):
        attempts, _ = _sync_attempts("PUT", ALWAYS_503)
        assert attempts == TOTAL_ATTEMPTS


async def _async_token_fetch_attempts(statuses: List[int]) -> tuple[int, bool]:
    """Fetch a token against a failing auth server, reporting attempts and whether it succeeded."""
    sequence = _StatusSequence(statuses)

    def handler(request: httpx.Request) -> httpx.Response:
        status = sequence.next_status()
        if status == 200:
            return httpx.Response(200, json={"access_token": "granted", "token_type": "Bearer", "expires_in": 3600})
        return httpx.Response(status, json={"message": "transient"})

    client = BaseAsyncApiClient(auth=("client-id", "client-secret"), transport=httpx.MockTransport(handler))
    try:
        try:
            await client.session
        except httpx.HTTPStatusError:
            return sequence.count, False
        return sequence.count, True
    finally:
        await client.close()


def _sync_token_fetch(statuses: List[int]) -> tuple[int, Optional[requests.RequestException]]:
    """Fetch a token against a failing local auth server.

    Points the API and auth host at one server and counts every request it receives. With an
    always-failing sequence that is the token-fetch attempt count, since no resource request is
    ever reached. Returns ``(attempts, error)`` where error is what reached the caller.
    """
    sequence = _StatusSequence(statuses)
    handler: Callable = type("_Handler", (_CountingHandler,), {"sequence": sequence})
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        host = f"http://127.0.0.1:{server.server_port}"
        session = create_session(auth=("client-id", "client-secret"), auth_host=host)
        try:
            session.get(f"{host}/resource")
        except requests.RequestException as error:
            return sequence.count, error
        return sequence.count, None
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def _auth_session_caller_attempts(method: str, statuses: List[int]) -> int:
    """Count the attempts a caller's own request makes through ``RequestsAuthSession.session``."""
    sequence = _StatusSequence(statuses)
    handler: Callable = type("_Handler", (_CountingHandler,), {"sequence": sequence})
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        host = f"http://127.0.0.1:{server.server_port}"
        provider = RequestsAuthSession(
            auth=("client-id", "client-secret"),
            host=host,
            initial_token={
                "access_token": "access-token",
                "token_type": "Bearer",
                "expires_at": _NEVER_EXPIRES,
            },
        )
        try:
            provider.session.request(method, f"{host}/resource")
        except requests.RequestException:
            pass
        return sequence.count
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


class TestTokenFetchRetry:
    """The token endpoint is replayable: a client credentials grant leaves no state behind.

    It is the one POST both clients retry, so a transient auth-server failure does not take
    down every caller holding a client.
    """

    async def test_async_token_fetch_is_retried(self):
        attempts, _ = await _async_token_fetch_attempts(ALWAYS_503)
        assert attempts == TOTAL_ATTEMPTS

    async def test_async_token_fetch_recovers(self):
        attempts, succeeded = await _async_token_fetch_attempts(RECOVERS_ON_LAST_ATTEMPT)
        assert attempts == TOTAL_ATTEMPTS
        assert succeeded

    def test_sync_token_fetch_is_retried(self):
        attempts, _ = _sync_token_fetch(ALWAYS_503)
        assert attempts == TOTAL_ATTEMPTS

    def test_sync_token_fetch_surfaces_the_auth_server_response(self):
        # An exhausted retry must hand back the auth server's own failure, not a urllib3
        # RetryError, so the caller can read why authentication failed.
        _, error = _sync_token_fetch(ALWAYS_503)
        assert isinstance(error, requests.HTTPError)
        assert error.response is not None
        assert error.response.status_code == 503
        assert "transient" in error.response.text

    def test_caller_post_through_the_auth_session_is_not_retried(self):
        # The token retry is mounted on the token URL, so a caller's own POST through the same
        # session keeps the default policy and is never replayed.
        assert _auth_session_caller_attempts("POST", ALWAYS_503) == 1


class TestSharedPolicy:
    def test_sync_retry_policy_uses_the_shared_method_set(self):
        # Identity, not equality: urllib3's own default happens to hold the same methods, so
        # only an identity check proves the sync client is driven by the shared constant.
        assert DEFAULT_RETRY.allowed_methods is RETRYABLE_METHODS

    def test_non_idempotent_methods_are_excluded(self):
        assert "POST" not in RETRYABLE_METHODS
        assert "PATCH" not in RETRYABLE_METHODS
