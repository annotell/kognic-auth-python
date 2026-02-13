"""Unit tests for User-Agent handling."""

import unittest

from kognic.auth import __version__
from kognic.auth._user_agent import _PY_VERSION, get_user_agent


class TestGetUserAgent(unittest.TestCase):
    def test_basic_user_agent(self):
        ua = get_user_agent("requests/2.31.0")
        self.assertEqual(ua, f"kognic-auth/{__version__} python/{_PY_VERSION} requests/2.31.0")

    def test_user_agent_with_client_name(self):
        ua = get_user_agent("python-httpx/0.28.1", "MyClient")
        self.assertEqual(ua, f"kognic-auth/{__version__} python/{_PY_VERSION} python-httpx/0.28.1 MyClient")

    def test_user_agent_with_none_client_name(self):
        ua = get_user_agent("requests/2.31.0", None)
        self.assertEqual(ua, f"kognic-auth/{__version__} python/{_PY_VERSION} requests/2.31.0")

    def test_user_agent_with_empty_client_name(self):
        ua = get_user_agent("requests/2.31.0", "")
        # Empty string is falsy, so no client name appended
        self.assertEqual(ua, f"kognic-auth/{__version__} python/{_PY_VERSION} requests/2.31.0")


if __name__ == "__main__":
    unittest.main()
