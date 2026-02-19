"""Unit tests for BaseApiClient (sync client)."""

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from kognic.auth._sunset import DATETIME_FMT, handle_sunset


class TestSunsetHeaderHandling(unittest.TestCase):
    def _make_mock_response(self, url: str, headers: dict, method: str = "GET"):
        response = MagicMock()
        response.request.url = url
        response.request.method = method
        response.headers = headers
        response.status_code = 200
        return response

    def test_no_sunset_header(self):
        response = self._make_mock_response("https://api.example.com/v1/test", {})
        # Should not log anything
        with patch("kognic.auth._sunset.logger") as mock_logger:
            handle_sunset(response)
            mock_logger.warning.assert_not_called()
            mock_logger.error.assert_not_called()

    def test_sunset_header_logs_warning_when_far(self):
        # Sunset date far in the future (> 2 weeks)
        from datetime import datetime, timedelta

        future_date = datetime.now() + timedelta(days=30)
        sunset_str = future_date.strftime(DATETIME_FMT)

        response = self._make_mock_response("https://api.example.com/v1/sunset-test", {"sunset-date": sunset_str})

        with patch("kognic.auth._sunset.logger") as mock_logger:
            handle_sunset(response)
            mock_logger.warning.assert_called_once()
            call_args = mock_logger.warning.call_args[0][0]
            self.assertIn("deprecated", call_args)
            self.assertIn("sunset-test", call_args)

    def test_sunset_header_logs_error_when_close(self):
        # Sunset date close (< 2 weeks)
        from datetime import datetime, timedelta

        close_date = datetime.now() + timedelta(days=7)
        sunset_str = close_date.strftime(DATETIME_FMT)

        response = self._make_mock_response("https://api.example.com/v1/sunset-test", {"sunset-date": sunset_str})

        with patch("kognic.auth._sunset.logger") as mock_logger:
            handle_sunset(response)
            mock_logger.error.assert_called_once()


class TestBaseApiClient(unittest.TestCase):
    @patch("kognic.auth.requests.base_client.RequestsAuthSession")
    def test_session_lazy_init(self, mock_session_class):
        from kognic.auth.requests.base_client import BaseApiClient

        mock_instance = MagicMock()
        mock_instance.session = MagicMock()
        mock_session_class.return_value = mock_instance

        client = BaseApiClient(auth=("test", "secret"))

        # Session should not be created yet
        self.assertIsNone(client._session)

        # Access session to trigger lazy init
        _ = client.session

        # Now session should be created
        mock_session_class.assert_called_once()

    @patch("kognic.auth.requests.base_client.RequestsAuthSession")
    def test_client_name_auto(self, mock_session_class):
        from kognic.auth.requests.base_client import BaseApiClient

        mock_instance = MagicMock()
        mock_instance.session = MagicMock()
        mock_session_class.return_value = mock_instance

        class MyCustomClient(BaseApiClient):
            pass

        client = MyCustomClient(auth=("test", "secret"))
        self.assertEqual(client._client_name, "MyCustomClient")


class TestBaseApiClientFromEnv(unittest.TestCase):
    def _write_config(self, data):
        f = tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False)
        json.dump(data, f)
        f.flush()
        f.close()
        return f.name

    @patch("kognic.auth.requests.base_client.RequestsAuthSession")
    def test_from_env_sets_auth_and_host(self, mock_session_class):
        from kognic.auth.requests.base_client import BaseApiClient

        mock_instance = MagicMock()
        mock_instance.session = MagicMock()
        mock_session_class.return_value = mock_instance

        config_path = self._write_config(
            {
                "environments": {
                    "demo": {
                        "host": "demo.kognic.com",
                        "auth_server": "https://auth.demo.kognic.com",
                        "credentials": "/tmp/demo-creds.json",
                    }
                }
            }
        )
        try:
            client = BaseApiClient.from_env("demo", env_config_path=config_path)
            self.assertEqual(client._auth, "/tmp/demo-creds.json")
            self.assertEqual(client._auth_host, "https://auth.demo.kognic.com")
        finally:
            Path(config_path).unlink()

    @patch("kognic.auth.requests.base_client.RequestsAuthSession")
    def test_explicit_auth_overrides_env_credentials(self, mock_session_class):
        from kognic.auth.requests.base_client import BaseApiClient

        mock_instance = MagicMock()
        mock_instance.session = MagicMock()
        mock_session_class.return_value = mock_instance

        config_path = self._write_config(
            {
                "environments": {
                    "demo": {
                        "host": "demo.kognic.com",
                        "auth_server": "https://auth.demo.kognic.com",
                        "credentials": "/tmp/demo-creds.json",
                    }
                }
            }
        )
        try:
            client = BaseApiClient.from_env("demo", env_config_path=config_path, auth=("my-id", "my-secret"))
            self.assertEqual(client._auth, ("my-id", "my-secret"))
            self.assertEqual(client._auth_host, "https://auth.demo.kognic.com")
        finally:
            Path(config_path).unlink()

    def test_unknown_env_raises(self):
        from kognic.auth.requests.base_client import BaseApiClient

        config_path = self._write_config({"environments": {}})
        try:
            with self.assertRaises(ValueError) as cm:
                BaseApiClient.from_env("nonexistent", env_config_path=config_path)
            self.assertIn("Unknown environment", str(cm.exception))
        finally:
            Path(config_path).unlink()

    @patch("kognic.auth.requests.base_client.RequestsAuthSession")
    def test_from_env_works_on_subclass(self, mock_session_class):
        from kognic.auth.requests.base_client import BaseApiClient

        mock_instance = MagicMock()
        mock_instance.session = MagicMock()
        mock_session_class.return_value = mock_instance

        class MyClient(BaseApiClient):
            pass

        config_path = self._write_config(
            {
                "environments": {
                    "demo": {
                        "host": "demo.kognic.com",
                        "auth_server": "https://auth.demo.kognic.com",
                        "credentials": "/tmp/demo-creds.json",
                    }
                }
            }
        )
        try:
            client = MyClient.from_env("demo", env_config_path=config_path)
            self.assertIsInstance(client, MyClient)
            self.assertEqual(client._client_name, "MyClient")
        finally:
            Path(config_path).unlink()


class TestProviderPool(unittest.TestCase):
    def setUp(self):
        import kognic.auth.requests.base_client as bc

        bc._provider_pool.clear()

    def tearDown(self):
        import kognic.auth.requests.base_client as bc

        bc._provider_pool.clear()

    def _make_clients(self, mock_session, n=2, **kwargs):
        from kognic.auth.requests.base_client import BaseApiClient

        clients = [BaseApiClient(**kwargs) for _ in range(n)]
        for c in clients:
            _ = c.session
        return clients

    @patch("kognic.auth.requests.base_client.requests.Session")
    @patch("kognic.auth.requests.base_client.RequestsAuthSession")
    @patch("kognic.auth.requests.base_client.resolve_credentials", return_value=("id1", "secret1"))
    def test_same_credentials_share_provider(self, _resolve, mock_ras, mock_session):
        self._make_clients(mock_session, n=2, auth=("id1", "secret1"))

        mock_ras.assert_called_once()
        self.assertEqual(len(mock_session.return_value.mount.call_args_list), 4)  # 2x per session

    @patch("kognic.auth.requests.base_client.requests.Session")
    @patch("kognic.auth.requests.base_client.RequestsAuthSession")
    @patch(
        "kognic.auth.requests.base_client.resolve_credentials",
        side_effect=lambda auth, *a, **kw: auth,
    )
    def test_different_credentials_get_different_providers(self, _resolve, mock_ras, mock_session):
        from kognic.auth.requests.base_client import BaseApiClient

        c1 = BaseApiClient(auth=("id1", "secret1"))
        c2 = BaseApiClient(auth=("id2", "secret2"))
        _ = c1.session
        _ = c2.session

        self.assertEqual(mock_ras.call_count, 2)

    @patch("kognic.auth.requests.base_client.requests.Session")
    @patch("kognic.auth.requests.base_client.RequestsAuthSession")
    @patch("kognic.auth.requests.base_client.resolve_credentials", return_value=("id1", "secret1"))
    def test_different_auth_host_gets_different_provider(self, _resolve, mock_ras, mock_session):
        from kognic.auth.requests.base_client import BaseApiClient

        c1 = BaseApiClient(auth=("id1", "secret1"), auth_host="https://auth.a.kognic.com")
        c2 = BaseApiClient(auth=("id1", "secret1"), auth_host="https://auth.b.kognic.com")
        _ = c1.session
        _ = c2.session

        self.assertEqual(mock_ras.call_count, 2)

    @patch("kognic.auth.requests.base_client.requests.Session")
    @patch("kognic.auth.requests.base_client.RequestsAuthSession")
    @patch("kognic.auth.requests.base_client.resolve_credentials", return_value=("id1", "secret1"))
    def test_cache_type_is_part_of_pool_key(self, _resolve, mock_ras, mock_session):
        from kognic.auth.internal.token_cache import FileTokenCache
        from kognic.auth.requests.base_client import BaseApiClient

        c1 = BaseApiClient(auth=("id1", "secret1"))
        c2 = BaseApiClient(auth=("id1", "secret1"), token_cache=FileTokenCache())
        _ = c1.session
        _ = c2.session

        self.assertEqual(mock_ras.call_count, 2)

    @patch("kognic.auth.requests.base_client.requests.Session")
    @patch("kognic.auth.requests.base_client.RequestsAuthSession")
    @patch("kognic.auth.requests.base_client.resolve_credentials", return_value=("id1", "secret1"))
    def test_explicit_token_provider_bypasses_pool(self, mock_resolve, mock_ras, mock_session):
        from kognic.auth.requests.base_client import BaseApiClient, _provider_pool

        explicit = MagicMock()
        client = BaseApiClient(auth=("id1", "secret1"), token_provider=explicit)
        _ = client.session

        self.assertEqual(len(_provider_pool), 0)
        mock_ras.assert_not_called()
        mock_resolve.assert_not_called()

    @patch("kognic.auth.requests.base_client.requests.Session")
    @patch("kognic.auth.requests.base_client.RequestsAuthSession")
    @patch("kognic.auth.requests.base_client.resolve_credentials", return_value=("id1", "secret1"))
    def test_pool_entry_alive_while_client_referenced(self, _resolve, mock_ras, mock_session):
        from kognic.auth.requests.base_client import (
            DEFAULT_HOST,
            DEFAULT_TOKEN_ENDPOINT_RELPATH,
            BaseApiClient,
            _provider_pool,
        )

        client = BaseApiClient(auth=("id1", "secret1"))
        _ = client.session

        pool_key = ("id1", DEFAULT_HOST, DEFAULT_TOKEN_ENDPOINT_RELPATH, type(None))
        self.assertIn(pool_key, _provider_pool)
        _ = client  # keep alive

    def test_provider_gc_when_all_clients_deleted(self):
        import gc
        import weakref

        from kognic.auth.requests.base_client import (
            DEFAULT_HOST,
            DEFAULT_TOKEN_ENDPOINT_RELPATH,
            BaseApiClient,
            _provider_pool,
        )

        # Use side_effect so each call returns a fresh object with no external strong references
        with patch(
            "kognic.auth.requests.base_client.resolve_credentials",
            return_value=("id-gc", "secret-gc"),
        ):
            with patch(
                "kognic.auth.requests.base_client.RequestsAuthSession",
                side_effect=lambda **kw: MagicMock(),
            ):
                client = BaseApiClient(auth=("id-gc", "secret-gc"))
                session = client.session
                pool_key = ("id-gc", DEFAULT_HOST, DEFAULT_TOKEN_ENDPOINT_RELPATH, type(None))
                provider_ref = weakref.ref(_provider_pool[pool_key])
                self.assertIsNotNone(provider_ref())

                del session, client
                gc.collect()
                gc.collect()  # two passes for cycles from _monkey_patch_send closures

                self.assertIsNone(provider_ref())


if __name__ == "__main__":
    unittest.main()
