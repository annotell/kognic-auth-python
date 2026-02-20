import json
import time
import unittest
from unittest import mock

from kognic.auth.internal.token_cache import KeyringTokenCache
from kognic.auth.internal.token_cache._base import EXPIRY_MARGIN_SECONDS, SERVICE_NAME, make_key


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


def _cache_no_keyring() -> KeyringTokenCache:
    cache = KeyringTokenCache()
    cache._keyring = lambda: None
    return cache


def _cache_with_keyring(mock_kr) -> KeyringTokenCache:
    cache = KeyringTokenCache()
    cache._keyring = lambda: mock_kr
    return cache


class MakeKeyTest(unittest.TestCase):
    def test_format(self):
        key = make_key("https://auth.app.kognic.com", "my-client-id")
        self.assertEqual(key, "https://auth.app.kognic.com:my-client-id")

    def test_different_servers_produce_different_keys(self):
        key1 = make_key("https://auth.app.kognic.com", "client-1")
        key2 = make_key("https://auth.demo.kognic.com", "client-1")
        self.assertNotEqual(key1, key2)


class KeyringAvailableTest(unittest.TestCase):
    def test_keyring_available_when_valid_backend(self):
        cache = KeyringTokenCache()
        mock_kr = mock.MagicMock()
        mock_kr.get_keyring.return_value = mock.MagicMock()
        with mock.patch.dict("sys.modules", {"keyring": mock_kr}):
            result = cache._keyring()
        self.assertIsNotNone(result)

    def test_keyring_unavailable_when_fail_backend(self):
        cache = KeyringTokenCache()

        class FailKeyring:
            pass

        mock_kr = mock.MagicMock()
        mock_kr.get_keyring.return_value = FailKeyring()
        with mock.patch.dict("sys.modules", {"keyring": mock_kr}):
            result = cache._keyring()
        self.assertIsNone(result)


class LoadCachedTokenTest(unittest.TestCase):
    def test_keyring_not_available(self):
        result = _cache_no_keyring().load("https://auth.app.kognic.com", "client-1")
        self.assertIsNone(result)

    def test_not_found(self):
        mock_kr = mock.MagicMock()
        mock_kr.get_password.return_value = None
        result = _cache_with_keyring(mock_kr).load("https://auth.app.kognic.com", "client-1")
        self.assertIsNone(result)
        mock_kr.get_password.assert_called_once_with(SERVICE_NAME, "https://auth.app.kognic.com:client-1")

    def test_valid_token(self):
        token = _make_token(expires_in=3600)
        mock_kr = mock.MagicMock()
        mock_kr.get_password.return_value = json.dumps(token)
        result = _cache_with_keyring(mock_kr).load("https://auth.app.kognic.com", "client-1")
        self.assertIsNotNone(result)
        self.assertEqual(result["access_token"], "eyJ.test.token")

    def test_expired_token(self):
        token = _make_token(expires_in=-100)
        mock_kr = mock.MagicMock()
        mock_kr.get_password.return_value = json.dumps(token)
        result = _cache_with_keyring(mock_kr).load("https://auth.app.kognic.com", "client-1")
        self.assertIsNone(result)

    def test_token_within_margin(self):
        token = _make_token(expires_in=EXPIRY_MARGIN_SECONDS - 1)
        mock_kr = mock.MagicMock()
        mock_kr.get_password.return_value = json.dumps(token)
        result = _cache_with_keyring(mock_kr).load("https://auth.app.kognic.com", "client-1")
        self.assertIsNone(result)

    def test_no_expires_at(self):
        token = {"access_token": "eyJ.test.token", "token_type": "bearer"}
        mock_kr = mock.MagicMock()
        mock_kr.get_password.return_value = json.dumps(token)
        result = _cache_with_keyring(mock_kr).load("https://auth.app.kognic.com", "client-1")
        self.assertIsNone(result)

    def test_corrupt_json(self):
        mock_kr = mock.MagicMock()
        mock_kr.get_password.return_value = "not valid json!!!"
        result = _cache_with_keyring(mock_kr).load("https://auth.app.kognic.com", "client-1")
        self.assertIsNone(result)

    def test_keyring_error(self):
        mock_kr = mock.MagicMock()
        mock_kr.get_password.side_effect = Exception("keyring error")
        result = _cache_with_keyring(mock_kr).load("https://auth.app.kognic.com", "client-1")
        self.assertIsNone(result)

    def test_includes_refresh_token(self):
        token = _make_token(extra={"refresh_token": "refresh-abc"})
        mock_kr = mock.MagicMock()
        mock_kr.get_password.return_value = json.dumps(token)
        result = _cache_with_keyring(mock_kr).load("https://auth.app.kognic.com", "client-1")
        self.assertIsNotNone(result)
        self.assertEqual(result["refresh_token"], "refresh-abc")


class SaveTokenTest(unittest.TestCase):
    def test_keyring_not_available(self):
        # Should not raise
        _cache_no_keyring().save("https://auth.app.kognic.com", "client-1", _make_token())

    def test_saves_to_keyring(self):
        token = _make_token()
        mock_kr = mock.MagicMock()
        _cache_with_keyring(mock_kr).save("https://auth.app.kognic.com", "client-1", token)
        mock_kr.set_password.assert_called_once_with(
            SERVICE_NAME,
            "https://auth.app.kognic.com:client-1",
            json.dumps(token),
        )

    def test_save_error_silenced(self):
        mock_kr = mock.MagicMock()
        mock_kr.set_password.side_effect = Exception("write failed")
        # Should not raise
        _cache_with_keyring(mock_kr).save("https://auth.app.kognic.com", "client-1", _make_token())


class ClearTokenTest(unittest.TestCase):
    def test_keyring_not_available(self):
        # Should not raise
        _cache_no_keyring().clear("https://auth.app.kognic.com", "client-1")

    def test_clears_from_keyring(self):
        mock_kr = mock.MagicMock()
        _cache_with_keyring(mock_kr).clear("https://auth.app.kognic.com", "client-1")
        mock_kr.delete_password.assert_called_once_with(
            SERVICE_NAME,
            "https://auth.app.kognic.com:client-1",
        )

    def test_clear_error_silenced(self):
        mock_kr = mock.MagicMock()
        mock_kr.delete_password.side_effect = Exception("delete failed")
        # Should not raise
        _cache_with_keyring(mock_kr).clear("https://auth.app.kognic.com", "client-1")


if __name__ == "__main__":
    unittest.main()
