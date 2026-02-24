"""Unit tests for credentials_parser module."""

import json
import os
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from kognic.auth.credentials_parser import (
    ApiCredentials,
    _check_expiry,
    get_credentials_from_env,
    parse_credentials,
    resolve_credentials,
)

VALID_CREDENTIALS_DICT = {
    "clientId": "test_id",
    "clientSecret": "test_secret",
    "email": "test@kognic.com",
    "userId": 1,
    "issuer": "auth.kognic.test",
}


class TestParseCredentials(unittest.TestCase):
    def test_parse_from_dict(self):
        creds = parse_credentials(VALID_CREDENTIALS_DICT)
        self.assertEqual(creds.client_id, "test_id")
        self.assertEqual(creds.client_secret, "test_secret")
        self.assertEqual(creds.email, "test@kognic.com")
        self.assertEqual(creds.user_id, 1)
        self.assertEqual(creds.issuer, "auth.kognic.test")

    def test_parse_from_file(self, tmp_path=None):
        import tempfile

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(VALID_CREDENTIALS_DICT, f)
            f.flush()
            path = f.name

        try:
            creds = parse_credentials(path)
            self.assertEqual(creds.client_id, "test_id")
            self.assertEqual(creds.client_secret, "test_secret")
        finally:
            Path(path).unlink()

    def test_parse_file_not_found(self):
        with self.assertRaises(FileNotFoundError):
            parse_credentials("/nonexistent/path/creds.json")

    def test_parse_missing_key_raises(self):
        incomplete = {"clientId": "test_id", "clientSecret": "test_secret"}
        with self.assertRaises(KeyError) as ctx:
            parse_credentials(incomplete)
        self.assertIn("email", str(ctx.exception))

    def test_parse_stores_created_and_expires(self):
        data = {
            **VALID_CREDENTIALS_DICT,
            "created": "2026-01-01T00:00:00.000000Z",
            "expires": "2099-01-01T00:00:00.000000Z",
        }
        creds = parse_credentials(data)
        self.assertEqual(creds.created, datetime(2026, 1, 1, tzinfo=timezone.utc))
        self.assertEqual(creds.expires, datetime(2099, 1, 1, tzinfo=timezone.utc))

    def test_parse_does_not_check_expiry(self):
        """parse_credentials should not raise even if expires is in the past."""
        data = {**VALID_CREDENTIALS_DICT, "expires": "2000-01-01T00:00:00.000000Z"}
        creds = parse_credentials(data)
        self.assertEqual(creds.expires, datetime(2000, 1, 1, tzinfo=timezone.utc))

    def test_parse_malformed_expires_returns_none(self):
        data = {**VALID_CREDENTIALS_DICT, "expires": "not-a-date"}
        creds = parse_credentials(data)
        self.assertIsNone(creds.expires)


class TestGetCredentialsFromEnv(unittest.TestCase):
    @patch.dict(os.environ, {}, clear=True)
    @patch("kognic.auth.credentials_parser.credentials_store.load_credentials", return_value=None)
    def test_no_env_vars_returns_none(self, _):
        client_id, client_secret = get_credentials_from_env()
        self.assertIsNone(client_id)
        self.assertIsNone(client_secret)

    @patch.dict(os.environ, {}, clear=True)
    @patch(
        "kognic.auth.credentials_parser.credentials_store.load_credentials",
        return_value=ApiCredentials(
            client_id="kr_id", client_secret="kr_secret", email="a@b.com", user_id=1, issuer="i", name="name"
        ),
    )
    def test_falls_back_to_keyring(self, _):
        client_id, client_secret = get_credentials_from_env()
        self.assertEqual(client_id, "kr_id")
        self.assertEqual(client_secret, "kr_secret")

    @patch.dict(os.environ, {"KOGNIC_CLIENT_ID": "env_id", "KOGNIC_CLIENT_SECRET": "env_secret"}, clear=True)
    @patch("kognic.auth.credentials_parser.credentials_store.load_credentials")
    def test_env_vars_take_precedence_over_keyring(self, mock_load):
        client_id, client_secret = get_credentials_from_env()
        self.assertEqual(client_id, "env_id")
        self.assertEqual(client_secret, "env_secret")
        mock_load.assert_not_called()

    @patch.dict(os.environ, {"KOGNIC_CLIENT_ID": "env_id", "KOGNIC_CLIENT_SECRET": "env_secret"}, clear=True)
    def test_client_id_and_secret_env_vars(self):
        client_id, client_secret = get_credentials_from_env()
        self.assertEqual(client_id, "env_id")
        self.assertEqual(client_secret, "env_secret")

    def test_kognic_credentials_file(self):
        import tempfile

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(VALID_CREDENTIALS_DICT, f)
            path = f.name

        try:
            with patch.dict(os.environ, {"KOGNIC_CREDENTIALS": path}, clear=True):
                client_id, client_secret = get_credentials_from_env()
                self.assertEqual(client_id, "test_id")
                self.assertEqual(client_secret, "test_secret")
        finally:
            Path(path).unlink()

    @patch.dict(
        os.environ,
        {"KOGNIC_CREDENTIALS": "/nonexistent.json", "KOGNIC_CLIENT_ID": "fallback_id"},
        clear=True,
    )
    def test_kognic_credentials_takes_precedence_over_client_id(self):
        with self.assertRaises(FileNotFoundError):
            get_credentials_from_env()


class TestResolveCredentials(unittest.TestCase):
    def test_auth_tuple(self):
        client_id, client_secret = resolve_credentials(auth=("tuple_id", "tuple_secret"))
        self.assertEqual(client_id, "tuple_id")
        self.assertEqual(client_secret, "tuple_secret")

    def test_auth_tuple_wrong_length_raises(self):
        with self.assertRaises(ValueError) as ctx:
            resolve_credentials(auth=("only_one",))
        self.assertIn("tuple", str(ctx.exception))

    def test_explicit_client_id_and_secret(self):
        client_id, client_secret = resolve_credentials(client_id="explicit_id", client_secret="explicit_secret")
        self.assertEqual(client_id, "explicit_id")
        self.assertEqual(client_secret, "explicit_secret")

    def test_auth_and_client_id_raises(self):
        with self.assertRaises(ValueError) as ctx:
            resolve_credentials(auth=("id", "secret"), client_id="other_id", client_secret="other_secret")
        self.assertIn("Choose either", str(ctx.exception))

    def test_auth_file_path(self):
        import tempfile

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(VALID_CREDENTIALS_DICT, f)
            path = f.name

        try:
            client_id, client_secret = resolve_credentials(auth=path)
            self.assertEqual(client_id, "test_id")
            self.assertEqual(client_secret, "test_secret")
        finally:
            Path(path).unlink()

    @patch.dict(os.environ, {"KOGNIC_CLIENT_ID": "env_id", "KOGNIC_CLIENT_SECRET": "env_secret"}, clear=True)
    def test_falls_back_to_env(self):
        client_id, client_secret = resolve_credentials()
        self.assertEqual(client_id, "env_id")
        self.assertEqual(client_secret, "env_secret")

    @patch.dict(os.environ, {}, clear=True)
    @patch("kognic.auth.credentials_parser.credentials_store.load_credentials", return_value=None)
    def test_no_credentials_returns_none(self, _):
        client_id, client_secret = resolve_credentials()
        self.assertIsNone(client_id)
        self.assertIsNone(client_secret)

    def test_auth_non_json_path_raises(self):
        with self.assertRaises(ValueError) as ctx:
            resolve_credentials(auth="/some/path/creds.yaml")
        self.assertIn("must be json", str(ctx.exception))

    def test_auth_api_credentials(self):
        creds = ApiCredentials(
            client_id="id",
            client_secret="secret",
            email="a@b.com",
            user_id=1,
            issuer="issuer",
            name="name",
        )
        client_id, client_secret = resolve_credentials(auth=creds)
        self.assertEqual(client_id, "id")
        self.assertEqual(client_secret, "secret")

    def test_auth_unsupported_type_raises(self):
        with self.assertRaises(ValueError):
            resolve_credentials(auth=12345)

    def test_auth_dict(self):
        client_id, client_secret = resolve_credentials(auth=VALID_CREDENTIALS_DICT)
        self.assertEqual(client_id, "test_id")
        self.assertEqual(client_secret, "test_secret")

    @patch(
        "kognic.auth.credentials_parser.credentials_store.load_credentials",
        return_value=ApiCredentials(
            client_id="kr_id", client_secret="kr_secret", email="a@b.com", user_id=1, issuer="i", name="name"
        ),
    )
    def test_auth_keyring_uri(self, mock_load):
        client_id, client_secret = resolve_credentials(auth="keyring://myprofile")
        self.assertEqual(client_id, "kr_id")
        self.assertEqual(client_secret, "kr_secret")
        mock_load.assert_called_once_with("myprofile")

    @patch("kognic.auth.credentials_parser.credentials_store.load_credentials", return_value=None)
    def test_auth_keyring_uri_not_found_raises(self, _):
        with self.assertRaises(ValueError) as ctx:
            resolve_credentials(auth="keyring://missing-profile")
        self.assertIn("missing-profile", str(ctx.exception))


def _make_creds(**kwargs) -> ApiCredentials:
    return ApiCredentials(
        client_id="id",
        client_secret="secret",
        email="a@b.com",
        user_id=1,
        issuer="issuer",
        **kwargs,
    )


class TestCheckExpiry(unittest.TestCase):
    def test_no_expires_field(self):
        _check_expiry(_make_creds())  # should not raise

    def test_future_expires(self):
        _check_expiry(_make_creds(expires=datetime(2099, 1, 1, tzinfo=timezone.utc)))  # should not raise

    def test_expired_raises(self):
        with self.assertRaises(ValueError) as ctx:
            _check_expiry(_make_creds(expires=datetime(2000, 1, 1, tzinfo=timezone.utc)))
        self.assertIn("expired", str(ctx.exception))

    def test_expired_with_time(self):
        with self.assertRaises(ValueError):
            _check_expiry(_make_creds(expires=datetime(2000, 6, 15, 12, 34, 56, 123456, tzinfo=timezone.utc)))


if __name__ == "__main__":
    unittest.main()
