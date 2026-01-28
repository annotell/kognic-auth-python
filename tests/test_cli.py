import unittest
from unittest import mock

from kognic.auth import DEFAULT_HOST
from kognic.auth.cli import create_parser, main


class CliParserTest(unittest.TestCase):
    def test_default_server(self):
        parser = create_parser()
        args = parser.parse_args(["get-access-token"])
        self.assertEqual(args.server, DEFAULT_HOST)
        self.assertIsNone(args.credentials)

    def test_custom_server(self):
        parser = create_parser()
        args = parser.parse_args(["get-access-token", "--server", "https://custom.auth.server"])
        self.assertEqual(args.server, "https://custom.auth.server")

    def test_credentials_file(self):
        parser = create_parser()
        args = parser.parse_args(["get-access-token", "--credentials", "/path/to/creds.json"])
        self.assertEqual(args.credentials, "/path/to/creds.json")

    def test_all_options(self):
        parser = create_parser()
        args = parser.parse_args(
            ["get-access-token", "--server", "https://my.server", "--credentials", "my_creds.json"]
        )
        self.assertEqual(args.server, "https://my.server")
        self.assertEqual(args.credentials, "my_creds.json")

    def test_no_command_shows_help(self):
        with mock.patch("builtins.print"):
            result = main([])
        self.assertEqual(result, 0)


class CliMainTest(unittest.TestCase):
    @mock.patch("kognic.auth.requests.auth_session.RequestsAuthSession")
    def test_main_prints_token(self, mock_session_class):
        mock_session = mock.MagicMock()
        mock_session.access_token = "test-access-token-123"
        mock_session_class.return_value = mock_session

        with mock.patch("builtins.print") as mock_print:
            result = main(["get-access-token"])

        self.assertEqual(result, 0)
        mock_print.assert_called_once_with("test-access-token-123")
        mock_session_class.assert_called_once_with(auth=None, host=DEFAULT_HOST)

    @mock.patch("kognic.auth.requests.auth_session.RequestsAuthSession")
    def test_main_with_credentials_file(self, mock_session_class):
        mock_session = mock.MagicMock()
        mock_session.access_token = "token-from-file"
        mock_session_class.return_value = mock_session

        with mock.patch("builtins.print") as mock_print:
            result = main(["get-access-token", "--credentials", "/path/to/creds.json"])

        self.assertEqual(result, 0)
        mock_print.assert_called_once_with("token-from-file")
        mock_session_class.assert_called_once_with(auth="/path/to/creds.json", host=DEFAULT_HOST)

    @mock.patch("kognic.auth.requests.auth_session.RequestsAuthSession")
    def test_main_with_custom_server(self, mock_session_class):
        mock_session = mock.MagicMock()
        mock_session.access_token = "custom-server-token"
        mock_session_class.return_value = mock_session

        with mock.patch("builtins.print") as mock_print:
            result = main(["get-access-token", "--server", "https://custom.server"])

        self.assertEqual(result, 0)
        mock_print.assert_called_once_with("custom-server-token")
        mock_session_class.assert_called_once_with(auth=None, host="https://custom.server")

    @mock.patch("kognic.auth.requests.auth_session.RequestsAuthSession")
    def test_main_with_all_options(self, mock_session_class):
        mock_session = mock.MagicMock()
        mock_session.access_token = "full-options-token"
        mock_session_class.return_value = mock_session

        with mock.patch("builtins.print"):
            result = main(["get-access-token", "--server", "https://my.server", "--credentials", "creds.json"])

        self.assertEqual(result, 0)
        mock_session_class.assert_called_once_with(auth="creds.json", host="https://my.server")

    @mock.patch("kognic.auth.requests.auth_session.RequestsAuthSession")
    def test_main_file_not_found(self, mock_session_class):
        mock_session_class.side_effect = FileNotFoundError("Could not find Api Credentials file at /bad/path.json")

        with mock.patch("builtins.print") as mock_print:
            result = main(["get-access-token", "--credentials", "/bad/path.json"])

        self.assertEqual(result, 1)
        mock_print.assert_called_once()
        self.assertIn("Error:", mock_print.call_args[0][0])

    @mock.patch("kognic.auth.requests.auth_session.RequestsAuthSession")
    def test_main_value_error(self, mock_session_class):
        mock_session_class.side_effect = ValueError("Bad auth credentials")

        with mock.patch("builtins.print") as mock_print:
            result = main(["get-access-token"])

        self.assertEqual(result, 1)
        mock_print.assert_called_once()
        self.assertIn("Error:", mock_print.call_args[0][0])

    @mock.patch("kognic.auth.requests.auth_session.RequestsAuthSession")
    def test_main_generic_exception(self, mock_session_class):
        mock_session_class.side_effect = Exception("Network error")

        with mock.patch("builtins.print") as mock_print:
            result = main(["get-access-token"])

        self.assertEqual(result, 1)
        mock_print.assert_called_once()
        self.assertIn("Error fetching token:", mock_print.call_args[0][0])


if __name__ == "__main__":
    unittest.main()
