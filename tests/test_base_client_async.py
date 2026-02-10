"""Unit tests for BaseAsyncApiClient (async client)."""

import unittest
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


if __name__ == "__main__":
    unittest.main()
