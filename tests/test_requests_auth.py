"""Tests for requests-layer token refresh and 401 retry behaviour."""

import io
import threading
import unittest
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Callable, Dict, Iterator, List, NamedTuple, Optional
from unittest.mock import MagicMock, patch

import requests
from authlib.common.errors import AuthlibBaseError

from kognic.auth.credentials_parser import ApiCredentials
from kognic.auth.requests.auth_session import _FixedSession
from kognic.auth.requests.base_client import create_session, make_token_provider


def _creds_with_scopes(scopes):
    """Return ApiCredentials that declare the given scopes."""
    return ApiCredentials(
        client_id="test-id",
        client_secret="test-secret",
        email="test@kognic.com",
        user_id=1,
        issuer="test-issuer",
        scopes=scopes,
    )


class TestMakeTokenProviderScopeResolution(unittest.TestCase):
    """The requested scope depends on how None vs an empty list interact with credentials-file scopes."""

    def test_explicit_scopes_override_credentials_scopes(self):
        provider = make_token_provider(auth=_creds_with_scopes(["api:read"]), scopes=["api:write"])
        self.assertEqual(provider.oauth_session.scope, "api:write")

    def test_multiple_scopes_are_space_joined(self):
        provider = make_token_provider(auth=_creds_with_scopes(["api:read"]), scopes=["api:read", "api:write"])
        self.assertEqual(provider.oauth_session.scope, "api:read api:write")

    def test_none_scopes_fall_back_to_credentials_scopes(self):
        provider = make_token_provider(auth=_creds_with_scopes(["api:read"]), scopes=None)
        self.assertEqual(provider.oauth_session.scope, "api:read")

    def test_empty_scopes_suppress_credentials_fallback(self):
        # An empty list is not None, so the credentials-file fallback is skipped and no scope is requested.
        # This is why kog forwards `env.scopes or None` rather than the raw (possibly empty) list.
        provider = make_token_provider(auth=_creds_with_scopes(["api:read"]), scopes=[])
        self.assertIsNone(provider.oauth_session.scope)


def _make_fixed_session():
    """Return a _FixedSession with dummy credentials and no network calls."""
    return _FixedSession(
        client_id="test-id",
        client_secret="test-secret",
        token_endpoint_auth_method="client_secret_post",
        grant_type="client_credentials",
    )


class _TokenProvider:
    """Hands out a new token after each invalidation, and counts the invalidations."""

    def __init__(self):
        self.issued = 0
        self.invalidations = 0
        self._token = None

    def ensure_token(self) -> dict:
        if self._token is None:
            self.issued += 1
            self._token = {"access_token": f"token-{self.issued}"}
        return self._token

    def invalidate_token(self) -> None:
        self.invalidations += 1
        self._token = None


class _Received(NamedTuple):
    path: str
    authorization: Optional[str]
    body: bytes


class _RecordingHandler(BaseHTTPRequestHandler):
    """Records the Authorization header and body of each request, then answers each path with
    the next reply from its route, repeating the last one."""

    protocol_version = "HTTP/1.1"
    # Ends a read that waits for body bytes the client announced but never sends.
    timeout = 1
    routes: Dict[str, List[Callable[["_RecordingHandler"], None]]]
    received: List[_Received]

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
        hits = sum(1 for r in self.received if r.path == self.path)
        self.received.append(_Received(self.path, self.headers.get("Authorization"), self._read_body()))
        replies = self.routes[self.path]
        replies[min(hits, len(replies) - 1)](self)

    do_GET = _respond
    do_PUT = _respond

    def log_message(self, format, *args):  # noqa: A002
        """Silence per-request stderr logging so test output stays pristine."""


def _status(status: int) -> Callable[[_RecordingHandler], None]:
    def reply(handler: _RecordingHandler):
        body = b'{"message": "reply"}'
        handler.send_response(status)
        handler.send_header("Content-Type", "application/json")
        handler.send_header("Content-Length", str(len(body)))
        handler.end_headers()
        handler.wfile.write(body)

    return reply


def _redirect(location: str) -> Callable[[_RecordingHandler], None]:
    def reply(handler: _RecordingHandler):
        handler.send_response(307)
        handler.send_header("Location", location)
        handler.send_header("Content-Length", "0")
        handler.end_headers()

    return reply


@contextmanager
def _server(routes: Dict[str, List[Callable[[_RecordingHandler], None]]]) -> Iterator[tuple[str, List[_Received]]]:
    """Serve ``routes`` on a local server, yielding its base URL and the requests it received."""
    received: List[_Received] = []
    handler: Callable = type("_Handler", (_RecordingHandler,), {"routes": routes, "received": received})
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}", received
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


UPLOAD = b"0123456789" * 100


class TestKognicBearerAuthHandle401(unittest.TestCase):
    """A 401 is answered with a fresh token and one re-send, but only for a request that still
    carries its Bearer header, and only with a replayable body."""

    def test_401_from_another_host_after_a_redirect_is_raised_without_sending_the_token(self):
        provider = _TokenProvider()
        with _server({"/target": [_status(401)]}) as (other, other_received):
            with _server({"/start": [_redirect(f"{other}/target")]}) as (base, _):
                session = create_session(token_provider=provider)
                with self.assertRaises(requests.HTTPError) as error:
                    session.get(f"{base}/start", timeout=1)

        self.assertEqual(error.exception.response.status_code, 401)
        self.assertEqual([r.authorization for r in other_received], [None])
        self.assertEqual(provider.invalidations, 0)
        self.assertEqual(provider.issued, 1)

    def test_401_from_the_called_host_is_answered_with_a_fresh_token(self):
        provider = _TokenProvider()
        with _server({"/resource": [_status(401), _status(200)]}) as (base, received):
            session = create_session(token_provider=provider)
            resp = session.get(f"{base}/resource", timeout=1)

        self.assertEqual(resp.status_code, 200)
        self.assertEqual([r.status_code for r in resp.history], [401])
        self.assertEqual([r.authorization for r in received], ["Bearer token-1", "Bearer token-2"])
        self.assertEqual(provider.invalidations, 1)

    def test_401_after_a_redirect_on_the_same_host_is_answered_with_a_fresh_token(self):
        provider = _TokenProvider()
        routes = {"/start": [_redirect("/target")], "/target": [_status(401), _status(200)]}
        with _server(routes) as (base, received):
            session = create_session(token_provider=provider)
            resp = session.get(f"{base}/start", timeout=1)

        self.assertEqual(resp.status_code, 200)
        self.assertEqual(
            [(r.path, r.authorization) for r in received],
            [("/start", "Bearer token-1"), ("/target", "Bearer token-1"), ("/target", "Bearer token-2")],
        )

    def test_stream_body_is_sent_in_full_when_resent(self):
        provider = _TokenProvider()
        with _server({"/resource": [_status(401), _status(200)]}) as (base, received):
            session = create_session(token_provider=provider)
            resp = session.put(f"{base}/resource", data=io.BytesIO(UPLOAD), timeout=1)

        self.assertEqual(resp.status_code, 200)
        self.assertEqual([r.body for r in received], [UPLOAD, UPLOAD])

    def test_generator_body_is_not_resent_and_the_next_call_gets_a_fresh_token(self):
        def chunks():
            yield UPLOAD[:500]
            yield UPLOAD[500:]

        provider = _TokenProvider()
        routes = {"/resource": [_status(401), _status(200)], "/next": [_status(200)]}
        with _server(routes) as (base, received):
            session = create_session(token_provider=provider)
            with self.assertRaises(requests.HTTPError) as error:
                session.put(f"{base}/resource", data=chunks(), timeout=1)
            session.get(f"{base}/next", timeout=1)

        self.assertEqual(error.exception.response.status_code, 401)
        self.assertEqual(
            [(r.path, r.authorization, r.body) for r in received],
            [("/resource", "Bearer token-1", UPLOAD), ("/next", "Bearer token-2", b"")],
        )
        self.assertEqual(provider.invalidations, 1)


class TestFixedSessionRefreshToken(unittest.TestCase):
    def test_authlib_invalid_token_calls_fetch_token(self):
        session = _make_fixed_session()
        err = AuthlibBaseError(error="invalid_token", description="expired")

        with patch.object(session.__class__.__bases__[0], "refresh_token", side_effect=err):
            with patch.object(session, "fetch_token", return_value={"access_token": "new"}) as mock_fetch:
                session.refresh_token("https://auth.kognic.com/token")

        mock_fetch.assert_called_once()

    def test_authlib_other_error_reraises(self):
        session = _make_fixed_session()
        err = AuthlibBaseError(error="server_error", description="oops")

        with patch.object(session.__class__.__bases__[0], "refresh_token", side_effect=err):
            with self.assertRaises(AuthlibBaseError) as cm:
                session.refresh_token("https://auth.kognic.com/token")

        self.assertEqual(cm.exception.error, "server_error")

    def test_http_401_invalid_token_calls_fetch_token(self):
        session = _make_fixed_session()
        http_resp = MagicMock(spec=requests.Response)
        http_resp.status_code = 401
        http_resp.json.return_value = {"error": "invalid_token"}
        http_err = requests.exceptions.HTTPError(response=http_resp)

        with patch.object(session.__class__.__bases__[0], "refresh_token", side_effect=http_err):
            with patch.object(session, "fetch_token", return_value={"access_token": "new"}) as mock_fetch:
                session.refresh_token("https://auth.kognic.com/token")

        mock_fetch.assert_called_once()

    def test_http_401_other_error_reraises(self):
        session = _make_fixed_session()
        http_resp = MagicMock(spec=requests.Response)
        http_resp.status_code = 401
        http_resp.json.return_value = {"error": "access_denied"}
        http_err = requests.exceptions.HTTPError(response=http_resp)

        with patch.object(session.__class__.__bases__[0], "refresh_token", side_effect=http_err):
            with self.assertRaises(requests.exceptions.HTTPError):
                session.refresh_token("https://auth.kognic.com/token")

    def test_http_non_401_reraises(self):
        session = _make_fixed_session()
        http_resp = MagicMock(spec=requests.Response)
        http_resp.status_code = 500
        http_resp.json.return_value = {"error": "invalid_token"}
        http_err = requests.exceptions.HTTPError(response=http_resp)

        with patch.object(session.__class__.__bases__[0], "refresh_token", side_effect=http_err):
            with self.assertRaises(requests.exceptions.HTTPError):
                session.refresh_token("https://auth.kognic.com/token")


if __name__ == "__main__":
    unittest.main()
