import unittest

from kognic.auth import credentials_parser


class CredentialsParserTest(unittest.TestCase):
    def test_parse_credentials(self):
        p = {
            "clientId": "CLIENT_ID",
            "clientSecret": "SECRET",
            "email": "test@kognic.com",
            "userId": 1,
            "issuer": "auth.kognic.test",
        }
        creds = credentials_parser.parse_credentials(p)
        self.assertEqual(creds.client_id, "CLIENT_ID")
        self.assertEqual(creds.client_secret, "SECRET")
