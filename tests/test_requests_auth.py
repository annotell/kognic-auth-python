"""Tests for requests-layer token refresh and 401 retry behaviour."""

import unittest
from unittest.mock import MagicMock, patch

import requests
from authlib.common.errors import AuthlibBaseError

from kognic.auth.requests.auth_session import _FixedSession
from kognic.auth.requests.bearer_auth import KognicBearerAuth


def _make_fixed_session():
    """Return a _FixedSession with dummy credentials and no network calls."""
    return _FixedSession(
        client_id="test-id",
        client_secret="test-secret",
        token_endpoint_auth_method="client_secret_post",
        grant_type="client_credentials",
    )


class TestKognicBearerAuthCall(unittest.TestCase):
    def test_injects_bearer_token(self):
        provider = MagicMock()
        provider.ensure_token.return_value = {"access_token": "tok-abc"}

        auth = KognicBearerAuth(provider)
        prepared = MagicMock()
        prepared.headers = {}

        result = auth(prepared)

        self.assertEqual(prepared.headers["Authorization"], "Bearer tok-abc")
        prepared.register_hook.assert_called_once_with("response", auth._handle_401)
        self.assertIs(result, prepared)


class TestKognicBearerAuthHandle401(unittest.TestCase):
    def _make_auth(self, new_token="fresh-token"):
        provider = MagicMock()
        provider.ensure_token.return_value = {"access_token": new_token}
        return KognicBearerAuth(provider), provider

    def _make_401_response(self):
        # Don't use spec=requests.Response; `connection` is an internal attribute
        # not listed in the public API so spec would block it.
        resp = MagicMock()
        resp.status_code = 401
        resp.content = b""
        copied_prep = MagicMock()
        copied_prep.headers = {}  # real dict so __setitem__ is observable
        resp.request.copy.return_value = copied_prep
        retry_resp = MagicMock()
        retry_resp.history = []
        resp.connection.send.return_value = retry_resp
        return resp, retry_resp

    def test_non_401_passes_through(self):
        auth, provider = self._make_auth()
        resp = MagicMock(spec=requests.Response)
        resp.status_code = 200

        result = auth._handle_401(resp)

        self.assertIs(result, resp)
        provider.invalidate_token.assert_not_called()

    def test_401_invalidates_token(self):
        auth, provider = self._make_auth()
        resp, _ = self._make_401_response()

        auth._handle_401(resp)

        provider.invalidate_token.assert_called_once()

    def test_401_retries_with_new_token(self):
        auth, provider = self._make_auth("brand-new-token")
        resp, retry_resp = self._make_401_response()

        result = auth._handle_401(resp)

        # ensure_token called twice: once in __call__ (not here), once in _handle_401
        provider.ensure_token.assert_called_once()
        copied = resp.request.copy.return_value
        self.assertEqual(copied.headers["Authorization"], "Bearer brand-new-token")
        resp.connection.send.assert_called_once_with(copied)
        self.assertIs(result, retry_resp)

    def test_401_original_response_appended_to_history(self):
        auth, _ = self._make_auth()
        resp, retry_resp = self._make_401_response()

        auth._handle_401(resp)

        self.assertIn(resp, retry_resp.history)

    def test_401_passes_kwargs_to_send(self):
        auth, _ = self._make_auth()
        resp, retry_resp = self._make_401_response()

        auth._handle_401(resp, timeout=5, verify=False)

        _, kwargs = resp.connection.send.call_args
        self.assertEqual(kwargs.get("timeout"), 5)
        self.assertFalse(kwargs.get("verify"))


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
