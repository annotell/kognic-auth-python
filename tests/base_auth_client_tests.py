import datetime
import unittest

from kognic.auth.base.auth_client import AuthClient


class TestAuthClient(AuthClient):
    def __init__(self, token: dict):
        self._token = token

    @property
    def token(self):
        return self._token


class AuthClientTests(unittest.TestCase):
    def test_auth_client(self):
        expires_at = 1729670977
        expect = datetime.datetime(2024, 10, 23, 8, 9, 37, tzinfo=datetime.timezone.utc)
        client = TestAuthClient(token={"expires_at": expires_at, "expires_in": 3600})
        self.assertEqual(client.expires_at, expect)
