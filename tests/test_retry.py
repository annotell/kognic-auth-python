"""Retry behaviour of the sync and async API clients.

Both clients retry transient 5xx responses for idempotent methods only. Methods outside
``RETRYABLE_METHODS`` — POST and PATCH — surface the first failure to the caller, so a
request that may have taken effect server-side is never replayed without the caller asking.

The sync client also has a cut-off retry: a cut-off response to an idempotent method is
retried, up to the same number of attempts. Only a replayable body is sent again, and only the
outermost send of a call retries, replaying the whole request from the original URL so that a
redirect is followed again. ``stream=True`` responses are not covered, since the body is read
after the call returns.

Timing is deliberately not asserted here: the sync backoff belongs to urllib3 and pinning it
would couple these tests to urllib3 internals. Sleeps are stubbed out for speed only.
"""

from __future__ import annotations

import asyncio
import io
import threading
import time
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Callable, Dict, Iterator, List, Optional

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
    monkeypatch.setattr(time, "sleep", lambda _seconds: None)


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


class _CuttingOffHandler(_CountingHandler):
    """Sends headers announcing a full body, then cuts the connection mid-body for the first
    ``cut_offs`` requests, like a peer resetting the connection while streaming a response."""

    cut_offs: int

    def _respond(self):
        self.sequence.next_status()
        body = b'{"message": "complete"}'
        cut_off = self.sequence.count <= self.cut_offs
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Connection", "close")
        self.end_headers()
        self.wfile.write(body[:5] if cut_off else body)
        self.close_connection = True

    do_GET = _respond
    do_POST = _respond
    do_PUT = _respond


def _sync_cut_off_attempts(method: str, cut_offs: int) -> tuple[int, Optional[int]]:
    """Issue one request against a server that cuts off the first ``cut_offs`` responses."""
    sequence = _StatusSequence([200])
    handler: Callable = type("_Handler", (_CuttingOffHandler,), {"sequence": sequence, "cut_offs": cut_offs})
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        session = create_session(token_provider=_StubTokenProvider())
        try:
            resp = session.request(method, f"http://127.0.0.1:{server.server_port}/resource")
        except requests.exceptions.ChunkedEncodingError:
            return sequence.count, None
        return sequence.count, resp.status_code
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


class _RecordingCuttingOffHandler(_CuttingOffHandler):
    """Reads and records each request body before answering like ``_CuttingOffHandler``."""

    # Ends a read that waits for body bytes the client announced but never sends.
    timeout = 1
    received: List[bytes]

    def _read_body(self) -> bytes:
        if self.headers.get("Transfer-Encoding", "").lower() == "chunked":
            body = b""
            while True:
                size = int(self.rfile.readline().split(b";")[0], 16)
                if size == 0:
                    while self.rfile.readline() not in (b"\r\n", b""):
                        pass
                    return body
                body += self.rfile.read(size)
                self.rfile.readline()
        return self.rfile.read(int(self.headers.get("Content-Length", 0)))

    def _respond(self):
        self.received.append(self._read_body())
        super()._respond()

    do_PUT = _respond


def _sync_cut_off_upload(body, cut_offs: int) -> tuple[List[bytes], object]:
    """PUT ``body`` to a server that cuts off the first ``cut_offs`` responses.

    Returns ``(received, outcome)``: the body the server read on each attempt, and either the
    response status or the exception that reached the caller.
    """
    received: List[bytes] = []
    handler: Callable = type(
        "_Handler",
        (_RecordingCuttingOffHandler,),
        {"sequence": _StatusSequence([200]), "cut_offs": cut_offs, "received": received},
    )
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        session = create_session(token_provider=_StubTokenProvider())
        try:
            resp = session.put(f"http://127.0.0.1:{server.server_port}/resource", data=body, timeout=1)
        except requests.RequestException as error:
            return received, error
        return received, resp.status_code
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


UPLOAD = b"0123456789" * 100

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

    def test_get_with_cut_off_response_is_retried(self):
        attempts, status = _sync_cut_off_attempts("GET", MAX_RETRIES)
        assert attempts == TOTAL_ATTEMPTS
        assert status == 200

    def test_get_with_cut_off_response_raises_when_attempts_are_exhausted(self):
        attempts, status = _sync_cut_off_attempts("GET", TOTAL_ATTEMPTS)
        assert attempts == TOTAL_ATTEMPTS
        assert status is None

    def test_put_with_cut_off_response_is_retried(self):
        attempts, status = _sync_cut_off_attempts("PUT", MAX_RETRIES)
        assert attempts == TOTAL_ATTEMPTS
        assert status == 200

    def test_post_with_cut_off_response_is_not_retried(self):
        attempts, status = _sync_cut_off_attempts("POST", 1)
        assert attempts == 1
        assert status is None


class TestSyncCutOffRetryRequestBody:
    """A cut-off retry only sends a replayable body again, and always sends all of it."""

    def test_generator_body_is_not_retried(self):
        def chunks():
            yield UPLOAD[:500]
            yield UPLOAD[500:]

        received, outcome = _sync_cut_off_upload(chunks(), cut_offs=1)
        assert received == [UPLOAD]
        assert isinstance(outcome, requests.exceptions.ChunkedEncodingError)

    def test_stream_body_is_sent_in_full_on_retry(self):
        received, outcome = _sync_cut_off_upload(io.BytesIO(UPLOAD), cut_offs=1)
        assert received == [UPLOAD, UPLOAD]
        assert outcome == 200

    def test_stream_body_is_resent_from_where_the_upload_started(self):
        stream = io.BytesIO(b"skipped" + UPLOAD)
        stream.seek(len(b"skipped"))
        received, outcome = _sync_cut_off_upload(stream, cut_offs=1)
        assert received == [UPLOAD, UPLOAD]
        assert outcome == 200

    def test_bytes_body_is_sent_in_full_on_retry(self):
        received, outcome = _sync_cut_off_upload(UPLOAD, cut_offs=1)
        assert received == [UPLOAD, UPLOAD]
        assert outcome == 200

    def test_stream_that_cannot_be_rewound_is_not_retried(self):
        class _ClosesOnceRead(io.BytesIO):
            def read(self, *args):
                data = super().read(*args)
                if not data:
                    self.close()
                return data

        received, outcome = _sync_cut_off_upload(_ClosesOnceRead(UPLOAD), cut_offs=1)
        assert received == [UPLOAD]
        assert isinstance(outcome, requests.exceptions.ChunkedEncodingError)


SUNSET_DATE = "2099-01-01T00:00:00Z"


class _RoutingHandler(BaseHTTPRequestHandler):
    """Answers each path with the next reply from its route, repeating the last one, and counts
    the hits on every path.

    A reply is a callable that writes the whole response, so it can also cut the response off.
    """

    protocol_version = "HTTP/1.1"
    timeout = 1
    routes: Dict[str, List[Callable[["_RoutingHandler"], None]]]
    hits: Dict[str, int]

    def _respond(self):
        hit = self.hits.get(self.path, 0)
        self.hits[self.path] = hit + 1
        replies = self.routes[self.path]
        replies[min(hit, len(replies) - 1)](self)

    do_GET = _respond
    do_POST = _respond
    do_PUT = _respond
    do_DELETE = _respond

    def log_message(self, format, *args):  # noqa: A002
        """Silence per-request stderr logging so test output stays pristine."""


def _complete(status: int = 200, sunset: Optional[str] = None) -> Callable[[_RoutingHandler], None]:
    def reply(handler: _RoutingHandler):
        body = b'{"message": "complete"}'
        handler.send_response(status)
        handler.send_header("Content-Type", "application/json")
        handler.send_header("Content-Length", str(len(body)))
        if sunset:
            handler.send_header("sunset-date", sunset)
        handler.end_headers()
        handler.wfile.write(body)

    return reply


def _redirect(location: str, status: int = 302, sunset: Optional[str] = None) -> Callable[[_RoutingHandler], None]:
    def reply(handler: _RoutingHandler):
        handler.send_response(status)
        handler.send_header("Location", location)
        handler.send_header("Content-Length", "0")
        if sunset:
            handler.send_header("sunset-date", sunset)
        handler.end_headers()

    return reply


def _cut_off(handler: _RoutingHandler):
    """Announces a full body in Content-Length, then closes the connection after part of it."""
    body = b'{"message": "complete"}'
    handler.send_response(200)
    handler.send_header("Content-Type", "application/json")
    handler.send_header("Content-Length", str(len(body)))
    handler.send_header("Connection", "close")
    handler.end_headers()
    handler.wfile.write(body[:5])
    handler.close_connection = True


def _chunked_cut_off(handler: _RoutingHandler):
    """Sends one chunk of a chunked body, then closes the connection before the terminating
    chunk, like the production incident behind the cut-off retry."""
    handler.send_response(200)
    handler.send_header("Content-Type", "application/json")
    handler.send_header("Transfer-Encoding", "chunked")
    handler.send_header("Connection", "close")
    handler.end_headers()
    handler.wfile.write(b'5\r\n{"mes\r\n')
    handler.close_connection = True


@contextmanager
def _routing_server(routes: Dict[str, List[Callable[[_RoutingHandler], None]]]) -> Iterator[tuple[str, Dict[str, int]]]:
    """Serve ``routes`` on a local server, yielding its base URL and the hits per path."""
    hits: Dict[str, int] = {}
    handler: Callable = type("_Handler", (_RoutingHandler,), {"routes": routes, "hits": hits})
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}", hits
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


class TestSyncCutOffRetryOncePerCall:
    """Only the outermost send of a call retries a cut-off response and checks the responses.

    A retry replays the whole request from the original URL, so a redirect is followed again.
    """

    def test_redirect_to_a_cut_off_response_makes_four_attempts_on_each_url(self):
        routes = {"/start": [_redirect("/target")], "/target": [_cut_off]}
        with _routing_server(routes) as (base, hits):
            session = create_session(token_provider=_StubTokenProvider())
            with pytest.raises(requests.exceptions.ChunkedEncodingError):
                session.get(f"{base}/start", timeout=1)
        assert hits == {"/start": TOTAL_ATTEMPTS, "/target": TOTAL_ATTEMPTS}

    def test_sunset_handler_sees_each_response_of_a_redirect_once(self):
        seen: List[tuple[str, str]] = []
        routes = {"/start": [_redirect("/target", sunset=SUNSET_DATE)], "/target": [_complete(sunset=SUNSET_DATE)]}
        with _routing_server(routes) as (base, _):
            session = create_session(
                token_provider=_StubTokenProvider(),
                sunset_handler=lambda _date, method, url: seen.append((method, url)),
            )
            session.get(f"{base}/start", timeout=1)
        assert seen == [("GET", f"{base}/start"), ("GET", f"{base}/target")]

    def test_redirect_to_an_error_raises_one_enhanced_http_error(self):
        routes = {"/start": [_redirect("/target")], "/target": [_complete(status=404)]}
        with _routing_server(routes) as (base, hits):
            session = create_session(token_provider=_StubTokenProvider())
            with pytest.raises(requests.HTTPError) as error:
                session.get(f"{base}/start", timeout=1)
        assert error.value.response.status_code == 404
        assert "Got HttpError with status=404" in str(error.value)
        assert hits == {"/start": 1, "/target": 1}

    def test_post_redirected_to_a_cut_off_get_is_not_retried(self):
        routes = {"/start": [_redirect("/target", status=303)], "/target": [_cut_off]}
        with _routing_server(routes) as (base, hits):
            session = create_session(token_provider=_StubTokenProvider())
            with pytest.raises(requests.exceptions.ChunkedEncodingError):
                session.post(f"{base}/start", timeout=1)
        assert hits == {"/start": 1, "/target": 1}

    def test_another_session_used_inside_a_response_hook_still_retries(self):
        routes = {"/outer": [_complete()], "/inner": [_cut_off, _complete()]}
        with _routing_server(routes) as (base, hits):
            outer = create_session(token_provider=_StubTokenProvider())
            inner = create_session(token_provider=_StubTokenProvider())
            inner_statuses: List[int] = []

            def call_inner(resp, **_kwargs):
                inner_statuses.append(inner.get(f"{base}/inner", timeout=1).status_code)
                return resp

            outer.get(f"{base}/outer", hooks={"response": call_inner}, timeout=1)
        assert inner_statuses == [200]
        assert hits == {"/outer": 1, "/inner": 2}


class TestSyncCutOffRetryResponseShapes:
    def test_chunked_response_cut_off_before_its_terminator_is_retried(self):
        routes = {"/resource": [_chunked_cut_off, _complete()]}
        with _routing_server(routes) as (base, hits):
            session = create_session(token_provider=_StubTokenProvider())
            resp = session.get(f"{base}/resource", timeout=1)
        assert resp.status_code == 200
        assert resp.json() == {"message": "complete"}
        assert hits == {"/resource": 2}

    def test_streamed_response_is_not_retried_and_raises_when_read(self):
        routes = {"/resource": [_cut_off, _complete()]}
        with _routing_server(routes) as (base, hits):
            session = create_session(token_provider=_StubTokenProvider())
            resp = session.get(f"{base}/resource", stream=True, timeout=1)
            with resp, pytest.raises(requests.exceptions.ChunkedEncodingError):
                _ = resp.content
        assert hits == {"/resource": 1}

    def test_delete_answered_with_404_after_a_retry_raises_the_404(self):
        routes = {"/resource": [_cut_off, _complete(status=404)]}
        with _routing_server(routes) as (base, hits):
            session = create_session(token_provider=_StubTokenProvider())
            with pytest.raises(requests.HTTPError) as error:
                session.delete(f"{base}/resource", timeout=1)
        assert error.value.response.status_code == 404
        assert hits == {"/resource": 2}


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
