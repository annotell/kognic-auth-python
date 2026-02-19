import json
import time
import unittest
from unittest import mock

from kognic.auth.cli.token_cache import (
    EXPIRY_MARGIN_SECONDS,
    SERVICE_NAME,
    _make_key,
    clear_token,
    load_cached_token,
    save_token,
)


def _make_token(*, expires_in=3600, extra=None):
    """Create a realistic token dict."""
    now = time.time()
    token = {
        "access_token": "eyJ.test.token",
        "token_type": "bearer",
        "expires_in": expires_in,
        "expires_at": now + expires_in,
    }
    if extra:
        token.update(extra)
    return token


class MakeKeyTest(unittest.TestCase):
    def test_format(self):
        key = _make_key("https://auth.app.kognic.com", "my-client-id")
        self.assertEqual(key, "https://auth.app.kognic.com:my-client-id")

    def test_different_servers_produce_different_keys(self):
        key1 = _make_key("https://auth.app.kognic.com", "client-1")
        key2 = _make_key("https://auth.demo.kognic.com", "client-1")
        self.assertNotEqual(key1, key2)


class KeyringAvailableTest(unittest.TestCase):
    @mock.patch("keyring.get_keyring")
    def test_keyring_available(self, mock_get_keyring):
        from kognic.auth.cli.token_cache import _keyring_available

        mock_get_keyring.return_value = mock.MagicMock(__class__=type("SecretService", (), {}))
        self.assertTrue(_keyring_available())

    @mock.patch("keyring.get_keyring")
    def test_keyring_fail_backend(self, mock_get_keyring):
        from kognic.auth.cli.token_cache import _keyring_available

        class FailKeyring:
            pass

        mock_get_keyring.return_value = FailKeyring()
        self.assertFalse(_keyring_available())


class LoadCachedTokenTest(unittest.TestCase):
    @mock.patch("kognic.auth.cli.token_cache._keyring_available", return_value=False)
    def test_keyring_not_available(self, _):
        result = load_cached_token("https://auth.app.kognic.com", "client-1")
        self.assertIsNone(result)

    @mock.patch("keyring.get_password", return_value=None)
    @mock.patch("kognic.auth.cli.token_cache._keyring_available", return_value=True)
    def test_not_found(self, _, mock_get):
        result = load_cached_token("https://auth.app.kognic.com", "client-1")
        self.assertIsNone(result)
        mock_get.assert_called_once_with(SERVICE_NAME, "https://auth.app.kognic.com:client-1")

    @mock.patch("keyring.get_password")
    @mock.patch("kognic.auth.cli.token_cache._keyring_available", return_value=True)
    def test_valid_token(self, _, mock_get):
        token = _make_token(expires_in=3600)
        mock_get.return_value = json.dumps(token)
        result = load_cached_token("https://auth.app.kognic.com", "client-1")
        self.assertIsNotNone(result)
        self.assertEqual(result["access_token"], "eyJ.test.token")

    @mock.patch("keyring.get_password")
    @mock.patch("kognic.auth.cli.token_cache._keyring_available", return_value=True)
    def test_expired_token(self, _, mock_get):
        token = _make_token(expires_in=-100)
        mock_get.return_value = json.dumps(token)
        result = load_cached_token("https://auth.app.kognic.com", "client-1")
        self.assertIsNone(result)

    @mock.patch("keyring.get_password")
    @mock.patch("kognic.auth.cli.token_cache._keyring_available", return_value=True)
    def test_token_within_margin(self, _, mock_get):
        token = _make_token(expires_in=EXPIRY_MARGIN_SECONDS - 1)
        mock_get.return_value = json.dumps(token)
        result = load_cached_token("https://auth.app.kognic.com", "client-1")
        self.assertIsNone(result)

    @mock.patch("keyring.get_password")
    @mock.patch("kognic.auth.cli.token_cache._keyring_available", return_value=True)
    def test_no_expires_at(self, _, mock_get):
        token = {"access_token": "eyJ.test.token", "token_type": "bearer"}
        mock_get.return_value = json.dumps(token)
        result = load_cached_token("https://auth.app.kognic.com", "client-1")
        self.assertIsNone(result)

    @mock.patch("keyring.get_password")
    @mock.patch("kognic.auth.cli.token_cache._keyring_available", return_value=True)
    def test_corrupt_json(self, _, mock_get):
        mock_get.return_value = "not valid json!!!"
        result = load_cached_token("https://auth.app.kognic.com", "client-1")
        self.assertIsNone(result)

    @mock.patch("keyring.get_password", side_effect=Exception("keyring error"))
    @mock.patch("kognic.auth.cli.token_cache._keyring_available", return_value=True)
    def test_keyring_error(self, _, mock_get):
        result = load_cached_token("https://auth.app.kognic.com", "client-1")
        self.assertIsNone(result)

    @mock.patch("keyring.get_password")
    @mock.patch("kognic.auth.cli.token_cache._keyring_available", return_value=True)
    def test_includes_refresh_token(self, _, mock_get):
        token = _make_token(extra={"refresh_token": "refresh-abc"})
        mock_get.return_value = json.dumps(token)
        result = load_cached_token("https://auth.app.kognic.com", "client-1")
        self.assertIsNotNone(result)
        self.assertEqual(result["refresh_token"], "refresh-abc")


class SaveTokenTest(unittest.TestCase):
    @mock.patch("kognic.auth.cli.token_cache._keyring_available", return_value=False)
    def test_keyring_not_available(self, _):
        # Should not raise
        save_token("https://auth.app.kognic.com", "client-1", _make_token())

    @mock.patch("keyring.set_password")
    @mock.patch("kognic.auth.cli.token_cache._keyring_available", return_value=True)
    def test_saves_to_keyring(self, _, mock_set):
        token = _make_token()
        save_token("https://auth.app.kognic.com", "client-1", token)
        mock_set.assert_called_once_with(
            SERVICE_NAME,
            "https://auth.app.kognic.com:client-1",
            json.dumps(token),
        )

    @mock.patch("keyring.set_password", side_effect=Exception("write failed"))
    @mock.patch("kognic.auth.cli.token_cache._keyring_available", return_value=True)
    def test_save_error_silenced(self, _, mock_set):
        # Should not raise
        save_token("https://auth.app.kognic.com", "client-1", _make_token())


class ClearTokenTest(unittest.TestCase):
    @mock.patch("kognic.auth.cli.token_cache._keyring_available", return_value=False)
    def test_keyring_not_available(self, _):
        # Should not raise
        clear_token("https://auth.app.kognic.com", "client-1")

    @mock.patch("keyring.delete_password")
    @mock.patch("kognic.auth.cli.token_cache._keyring_available", return_value=True)
    def test_clears_from_keyring(self, _, mock_delete):
        clear_token("https://auth.app.kognic.com", "client-1")
        mock_delete.assert_called_once_with(
            SERVICE_NAME,
            "https://auth.app.kognic.com:client-1",
        )

    @mock.patch("keyring.delete_password", side_effect=Exception("delete failed"))
    @mock.patch("kognic.auth.cli.token_cache._keyring_available", return_value=True)
    def test_clear_error_silenced(self, _, mock_delete):
        # Should not raise
        clear_token("https://auth.app.kognic.com", "client-1")


if __name__ == "__main__":
    unittest.main()
