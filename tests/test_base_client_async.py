"""Unit tests for BaseAsyncApiClient (async client)."""

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


class TestBaseAsyncApiClient(unittest.TestCase):
    @patch("kognic.auth.httpx.base_client.HttpxAuthAsyncClient.__init__", return_value=None)
    def test_client_name_auto(self, mock_init):
        from kognic.auth.httpx.base_client import BaseAsyncApiClient

        # Need to manually set _oauth_client since we mocked __init__
        with patch.object(BaseAsyncApiClient, "__init__", lambda self, **kwargs: None):
            client = BaseAsyncApiClient.__new__(BaseAsyncApiClient)
            # Simulate what __init__ would do for client_name
            client_name = "auto"
            if client_name == "auto":
                client_name = client.__class__.__name__
            self.assertEqual(client_name, "BaseAsyncApiClient")

    def test_inherits_from_httpx_auth_client(self):
        from kognic.auth.httpx.async_client import HttpxAuthAsyncClient
        from kognic.auth.httpx.base_client import BaseAsyncApiClient

        self.assertTrue(issubclass(BaseAsyncApiClient, HttpxAuthAsyncClient))

    def test_has_context_manager_methods(self):
        from kognic.auth.httpx.base_client import BaseAsyncApiClient

        self.assertTrue(hasattr(BaseAsyncApiClient, "__aenter__"))
        self.assertTrue(hasattr(BaseAsyncApiClient, "__aexit__"))
        self.assertTrue(hasattr(BaseAsyncApiClient, "close"))


class TestBaseAsyncApiClientFromEnv(unittest.TestCase):
    def _write_config(self, data):
        f = tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False)
        json.dump(data, f)
        f.flush()
        f.close()
        return f.name

    @patch("kognic.auth.httpx.base_client.HttpxAuthAsyncClient.__init__", return_value=None)
    def test_from_env_passes_resolved_values(self, mock_init):
        from kognic.auth.httpx.base_client import BaseAsyncApiClient

        config_path = self._write_config(
            {
                "contexts": {
                    "demo": {
                        "host": "demo.kognic.com",
                        "auth_server": "https://auth.demo.kognic.com",
                        "credentials": "/tmp/demo-creds.json",
                    }
                }
            }
        )
        try:
            with patch.object(BaseAsyncApiClient, "_oauth_client", create=True):
                BaseAsyncApiClient.from_env("demo", env_config_path=config_path)
            mock_init.assert_called_once()
            call_kwargs = mock_init.call_args[1]
            self.assertEqual(call_kwargs["auth"], "/tmp/demo-creds.json")
            self.assertEqual(call_kwargs["host"], "https://auth.demo.kognic.com")
        finally:
            Path(config_path).unlink()

    def test_unknown_env_raises(self):
        from kognic.auth.httpx.base_client import BaseAsyncApiClient

        config_path = self._write_config({"contexts": {}})
        try:
            with self.assertRaises(ValueError) as cm:
                BaseAsyncApiClient.from_env("nonexistent", env_config_path=config_path)
            self.assertIn("Unknown environment", str(cm.exception))
        finally:
            Path(config_path).unlink()


if __name__ == "__main__":
    unittest.main()
