"""Tests for the keyring-based credential store."""

import json
import unittest
from unittest import mock

from kognic.auth.credentials_parser import ApiCredentials
from kognic.auth.internal.credentials_store import (
    DEFAULT_PROFILE,
    SERVICE_NAME,
    clear_credentials,
    load_credentials,
    save_credentials,
)

FULL_CREDS_DICT = {
    "clientId": "my-id",
    "clientSecret": "my-secret",
    "email": "test@kognic.com",
    "userId": 1,
    "issuer": "auth.kognic.test",
}

FULL_CREDS = ApiCredentials(
    client_id="my-id",
    client_secret="my-secret",
    email="test@kognic.com",
    user_id=1,
    issuer="auth.kognic.test",
)


def _mock_keyring(get_password=None, set_password=None, delete_password=None):
    """Return a mock keyring module wired to the given side effects / return values."""
    kr = mock.MagicMock()
    if get_password is not None:
        kr.get_password.return_value = get_password
    if set_password is not None:
        kr.set_password.side_effect = set_password
    if delete_password is not None:
        kr.delete_password.side_effect = delete_password
    kr.get_keyring.return_value = mock.MagicMock()  # non-fail backend
    return kr


class LoadCredentialsTest(unittest.TestCase):
    def test_no_keyring_returns_none(self):
        with mock.patch("kognic.auth.internal.credentials_store._get_keyring", return_value=None):
            self.assertIsNone(load_credentials())

    def test_not_stored_returns_none(self):
        kr = _mock_keyring(get_password=None)
        with mock.patch("kognic.auth.internal.credentials_store._get_keyring", return_value=kr):
            self.assertIsNone(load_credentials())
        kr.get_password.assert_called_once_with(SERVICE_NAME, DEFAULT_PROFILE)

    def test_stored_credentials_returned(self):
        data = json.dumps(FULL_CREDS_DICT)
        kr = _mock_keyring(get_password=data)
        with mock.patch("kognic.auth.internal.credentials_store._get_keyring", return_value=kr):
            result = load_credentials()
        self.assertIsInstance(result, ApiCredentials)
        self.assertEqual(result.client_id, "my-id")
        self.assertEqual(result.client_secret, "my-secret")
        self.assertEqual(result.email, "test@kognic.com")
        self.assertEqual(result.user_id, 1)
        self.assertEqual(result.issuer, "auth.kognic.test")

    def test_custom_profile(self):
        data = json.dumps(FULL_CREDS_DICT)
        kr = _mock_keyring(get_password=data)
        with mock.patch("kognic.auth.internal.credentials_store._get_keyring", return_value=kr):
            load_credentials(profile="demo")
        kr.get_password.assert_called_once_with(SERVICE_NAME, "demo")

    def test_corrupt_json_returns_none(self):
        kr = _mock_keyring(get_password="not-json")
        with mock.patch("kognic.auth.internal.credentials_store._get_keyring", return_value=kr):
            self.assertIsNone(load_credentials())

    def test_keyring_error_returns_none(self):
        kr = mock.MagicMock()
        kr.get_password.side_effect = Exception("keyring exploded")
        with mock.patch("kognic.auth.internal.credentials_store._get_keyring", return_value=kr):
            self.assertIsNone(load_credentials())


class SaveCredentialsTest(unittest.TestCase):
    def test_no_keyring_raises(self):
        with mock.patch("kognic.auth.internal.credentials_store._get_keyring", return_value=None):
            with self.assertRaises(RuntimeError) as ctx:
                save_credentials(FULL_CREDS)
            self.assertIn("keyring", str(ctx.exception).lower())

    def test_stores_in_keyring(self):
        kr = mock.MagicMock()
        with mock.patch("kognic.auth.internal.credentials_store._get_keyring", return_value=kr):
            save_credentials(FULL_CREDS)
        kr.set_password.assert_called_once_with(
            SERVICE_NAME,
            DEFAULT_PROFILE,
            json.dumps(FULL_CREDS_DICT),
        )

    def test_custom_profile(self):
        kr = mock.MagicMock()
        with mock.patch("kognic.auth.internal.credentials_store._get_keyring", return_value=kr):
            save_credentials(FULL_CREDS, profile="demo")
        kr.set_password.assert_called_once_with(
            SERVICE_NAME,
            "demo",
            json.dumps(FULL_CREDS_DICT),
        )


class ClearCredentialsTest(unittest.TestCase):
    def test_no_keyring_does_not_raise(self):
        with mock.patch("kognic.auth.internal.credentials_store._get_keyring", return_value=None):
            clear_credentials()  # should not raise

    def test_clears_from_keyring(self):
        kr = mock.MagicMock()
        with mock.patch("kognic.auth.internal.credentials_store._get_keyring", return_value=kr):
            clear_credentials()
        kr.delete_password.assert_called_once_with(SERVICE_NAME, DEFAULT_PROFILE)

    def test_error_silenced(self):
        kr = mock.MagicMock()
        kr.delete_password.side_effect = Exception("gone already")
        with mock.patch("kognic.auth.internal.credentials_store._get_keyring", return_value=kr):
            clear_credentials()  # should not raise


if __name__ == "__main__":
    unittest.main()
