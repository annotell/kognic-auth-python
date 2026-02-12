import json
import unittest
from unittest import mock

from kognic.auth import DEFAULT_HOST
from kognic.auth.cli import create_parser, main
from kognic.auth.cli.call import run as call_run
from kognic.auth.config import Context


class CliParserTest(unittest.TestCase):
    def test_default_server(self):
        parser = create_parser()
        args = parser.parse_args(["get-access-token"])
        self.assertIsNone(args.server)
        self.assertIsNone(args.credentials)
        self.assertIsNone(args.context_name)

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

    def test_get_access_token_with_context(self):
        parser = create_parser()
        args = parser.parse_args(["get-access-token", "--context", "demo"])
        self.assertEqual(args.context_name, "demo")

    def test_no_command_shows_help(self):
        with mock.patch("builtins.print"):
            result = main([])
        self.assertEqual(result, 0)


class CliMainTest(unittest.TestCase):
    @mock.patch("kognic.auth.cli.get_access_token.RequestsAuthSession")
    def test_main_prints_token(self, mock_session_class):
        mock_session = mock.MagicMock()
        mock_session.access_token = "test-access-token-123"
        mock_session_class.return_value = mock_session

        with mock.patch("builtins.print") as mock_print:
            result = main(["get-access-token"])

        self.assertEqual(result, 0)
        mock_print.assert_called_once_with("test-access-token-123")
        mock_session_class.assert_called_once_with(auth=None, host=DEFAULT_HOST)

    @mock.patch("kognic.auth.cli.get_access_token.RequestsAuthSession")
    def test_main_with_credentials_file(self, mock_session_class):
        mock_session = mock.MagicMock()
        mock_session.access_token = "token-from-file"
        mock_session_class.return_value = mock_session

        with mock.patch("builtins.print") as mock_print:
            result = main(["get-access-token", "--credentials", "/path/to/creds.json"])

        self.assertEqual(result, 0)
        mock_print.assert_called_once_with("token-from-file")
        mock_session_class.assert_called_once_with(auth="/path/to/creds.json", host=DEFAULT_HOST)

    @mock.patch("kognic.auth.cli.get_access_token.RequestsAuthSession")
    def test_main_with_custom_server(self, mock_session_class):
        mock_session = mock.MagicMock()
        mock_session.access_token = "custom-server-token"
        mock_session_class.return_value = mock_session

        with mock.patch("builtins.print") as mock_print:
            result = main(["get-access-token", "--server", "https://custom.server"])

        self.assertEqual(result, 0)
        mock_print.assert_called_once_with("custom-server-token")
        mock_session_class.assert_called_once_with(auth=None, host="https://custom.server")

    @mock.patch("kognic.auth.cli.get_access_token.RequestsAuthSession")
    def test_main_with_all_options(self, mock_session_class):
        mock_session = mock.MagicMock()
        mock_session.access_token = "full-options-token"
        mock_session_class.return_value = mock_session

        with mock.patch("builtins.print"):
            result = main(["get-access-token", "--server", "https://my.server", "--credentials", "creds.json"])

        self.assertEqual(result, 0)
        mock_session_class.assert_called_once_with(auth="creds.json", host="https://my.server")

    @mock.patch("kognic.auth.cli.get_access_token.RequestsAuthSession")
    def test_main_file_not_found(self, mock_session_class):
        mock_session_class.side_effect = FileNotFoundError("Could not find Api Credentials file at /bad/path.json")

        with mock.patch("builtins.print") as mock_print:
            result = main(["get-access-token", "--credentials", "/bad/path.json"])

        self.assertEqual(result, 1)
        mock_print.assert_called_once()
        self.assertIn("Error:", mock_print.call_args[0][0])

    @mock.patch("kognic.auth.cli.get_access_token.RequestsAuthSession")
    def test_main_value_error(self, mock_session_class):
        mock_session_class.side_effect = ValueError("Bad auth credentials")

        with mock.patch("builtins.print") as mock_print:
            result = main(["get-access-token"])

        self.assertEqual(result, 1)
        mock_print.assert_called_once()
        self.assertIn("Error:", mock_print.call_args[0][0])

    @mock.patch("kognic.auth.cli.get_access_token.RequestsAuthSession")
    def test_main_generic_exception(self, mock_session_class):
        mock_session_class.side_effect = Exception("Network error")

        with mock.patch("builtins.print") as mock_print:
            result = main(["get-access-token"])

        self.assertEqual(result, 1)
        mock_print.assert_called_once()
        self.assertIn("Error fetching token:", mock_print.call_args[0][0])

    @mock.patch("kognic.auth.cli.get_access_token.RequestsAuthSession")
    @mock.patch("kognic.auth.cli.get_access_token.load_config")
    def test_main_with_context(self, mock_load_config, mock_session_class):
        from kognic.auth.config import Config

        mock_load_config.return_value = Config(
            contexts={
                "demo": Context(
                    name="demo",
                    host="demo.kognic.com",
                    auth_server="https://auth.demo.kognic.com",
                    credentials="/path/to/demo-creds.json",
                ),
            },
        )
        mock_session = mock.MagicMock()
        mock_session.access_token = "demo-token"
        mock_session_class.return_value = mock_session

        with mock.patch("builtins.print") as mock_print:
            result = main(["get-access-token", "--context", "demo"])

        self.assertEqual(result, 0)
        mock_print.assert_called_once_with("demo-token")
        mock_session_class.assert_called_once_with(
            auth="/path/to/demo-creds.json",
            host="https://auth.demo.kognic.com",
        )

    @mock.patch("kognic.auth.cli.get_access_token.RequestsAuthSession")
    @mock.patch("kognic.auth.cli.get_access_token.load_config")
    def test_main_with_context_server_override(self, mock_load_config, mock_session_class):
        from kognic.auth.config import Config

        mock_load_config.return_value = Config(
            contexts={
                "demo": Context(
                    name="demo",
                    host="demo.kognic.com",
                    auth_server="https://auth.demo.kognic.com",
                    credentials="/path/to/demo-creds.json",
                ),
            },
        )
        mock_session = mock.MagicMock()
        mock_session.access_token = "override-token"
        mock_session_class.return_value = mock_session

        with mock.patch("builtins.print"):
            result = main(["get-access-token", "--context", "demo", "--server", "https://custom.server"])

        self.assertEqual(result, 0)
        mock_session_class.assert_called_once_with(
            auth="/path/to/demo-creds.json",
            host="https://custom.server",
        )

    def test_main_with_unknown_context(self):
        with mock.patch("kognic.auth.cli.get_access_token.load_config") as mock_load_config:
            from kognic.auth.config import Config

            mock_load_config.return_value = Config()

            with mock.patch("builtins.print") as mock_print:
                result = main(["get-access-token", "--context", "nonexistent"])

        self.assertEqual(result, 1)
        mock_print.assert_called_once()
        self.assertIn("Unknown context", mock_print.call_args[0][0])


class CallParserTest(unittest.TestCase):
    def test_call_basic(self):
        parser = create_parser()
        args = parser.parse_args(["call", "https://app.kognic.com/v1/projects"])
        self.assertEqual(args.command, "call")
        self.assertEqual(args.method, "GET")
        self.assertEqual(args.url, "https://app.kognic.com/v1/projects")
        self.assertIsNone(args.data)
        self.assertIsNone(args.headers)
        self.assertIsNone(args.context_name)

    def test_call_with_method(self):
        parser = create_parser()
        args = parser.parse_args(["call", "-X", "POST", "https://app.kognic.com/v1/projects"])
        self.assertEqual(args.method, "POST")

    def test_call_with_data(self):
        parser = create_parser()
        args = parser.parse_args(["call", "https://app.kognic.com/v1/projects", "-X", "POST", "-d", '{"name": "test"}'])
        self.assertEqual(args.method, "POST")
        self.assertEqual(args.data, '{"name": "test"}')

    def test_call_with_headers(self):
        parser = create_parser()
        args = parser.parse_args(
            [
                "call",
                "https://app.kognic.com/v1/projects",
                "-H",
                "Accept: application/json",
                "-H",
                "X-Custom: value",
            ]
        )
        self.assertEqual(args.headers, ["Accept: application/json", "X-Custom: value"])

    def test_call_with_context(self):
        parser = create_parser()
        args = parser.parse_args(["call", "https://demo.kognic.com/v1/projects", "--context", "demo"])
        self.assertEqual(args.context_name, "demo")

    def test_call_with_config(self):
        parser = create_parser()
        args = parser.parse_args(["call", "https://app.kognic.com/v1/projects", "--config", "/custom/config.json"])
        self.assertEqual(args.config, "/custom/config.json")


class CallApiTest(unittest.TestCase):
    def _make_parsed(
        self,
        method="GET",
        url="https://app.kognic.com/v1/projects",
        data=None,
        headers=None,
        config="/nonexistent/config.json",
        context_name=None,
    ):
        parser = create_parser()
        args = ["call", url]
        if method != "GET":
            args.extend(["-X", method])
        if data:
            args.extend(["-d", data])
        if headers:
            for h in headers:
                args.extend(["-H", h])
        args.extend(["--config", config])
        if context_name:
            args.extend(["--context", context_name])
        return parser.parse_args(args)

    @mock.patch("kognic.auth.cli.call.resolve_context")
    @mock.patch("kognic.auth.cli.call.load_config")
    @mock.patch("kognic.auth.cli.call.RequestsAuthSession")
    def test_call_api_get_success(self, mock_session_class, mock_load_config, mock_resolve_context):
        mock_load_config.return_value = mock.MagicMock()
        mock_resolve_context.return_value = Context(
            name="default",
            host="app.kognic.com",
            auth_server="https://auth.app.kognic.com",
            credentials=None,
        )
        mock_session = mock.MagicMock()
        mock_response = mock.MagicMock()
        mock_response.ok = True
        mock_response.headers = {"Content-Type": "application/json"}
        mock_response.json.return_value = {"projects": []}
        mock_session.session.request.return_value = mock_response
        mock_session_class.return_value = mock_session

        parsed = self._make_parsed()
        with mock.patch("builtins.print") as mock_print:
            result = call_run(parsed)

        self.assertEqual(result, 0)
        mock_session.session.request.assert_called_once_with(
            method="GET",
            url="https://app.kognic.com/v1/projects",
            json=None,
            headers=None,
        )
        mock_print.assert_called_once_with(json.dumps({"projects": []}, indent=2))

    @mock.patch("kognic.auth.cli.call.resolve_context")
    @mock.patch("kognic.auth.cli.call.load_config")
    @mock.patch("kognic.auth.cli.call.RequestsAuthSession")
    def test_call_api_post_with_data(self, mock_session_class, mock_load_config, mock_resolve_context):
        mock_load_config.return_value = mock.MagicMock()
        mock_resolve_context.return_value = Context(
            name="default",
            host="app.kognic.com",
            auth_server="https://auth.app.kognic.com",
            credentials=None,
        )
        mock_session = mock.MagicMock()
        mock_response = mock.MagicMock()
        mock_response.ok = True
        mock_response.headers = {"Content-Type": "application/json"}
        mock_response.json.return_value = {"id": 1}
        mock_session.session.request.return_value = mock_response
        mock_session_class.return_value = mock_session

        parsed = self._make_parsed(method="POST", data='{"name": "test"}')
        with mock.patch("builtins.print"):
            result = call_run(parsed)

        self.assertEqual(result, 0)
        mock_session.session.request.assert_called_once_with(
            method="POST",
            url="https://app.kognic.com/v1/projects",
            json={"name": "test"},
            headers={"Content-Type": "application/json"},
        )

    @mock.patch("kognic.auth.cli.call.resolve_context")
    @mock.patch("kognic.auth.cli.call.load_config")
    @mock.patch("kognic.auth.cli.call.RequestsAuthSession")
    def test_call_api_with_custom_headers(self, mock_session_class, mock_load_config, mock_resolve_context):
        mock_load_config.return_value = mock.MagicMock()
        mock_resolve_context.return_value = Context(
            name="default",
            host="app.kognic.com",
            auth_server="https://auth.app.kognic.com",
            credentials=None,
        )
        mock_session = mock.MagicMock()
        mock_response = mock.MagicMock()
        mock_response.ok = True
        mock_response.headers = {"Content-Type": "text/plain"}
        mock_response.text = "OK"
        mock_session.session.request.return_value = mock_response
        mock_session_class.return_value = mock_session

        parsed = self._make_parsed(headers=["Accept: text/plain", "X-Custom: value"])
        with mock.patch("builtins.print"):
            result = call_run(parsed)

        self.assertEqual(result, 0)
        mock_session.session.request.assert_called_once_with(
            method="GET",
            url="https://app.kognic.com/v1/projects",
            json=None,
            headers={"Accept": "text/plain", "X-Custom": "value"},
        )

    @mock.patch("kognic.auth.cli.call.resolve_context")
    @mock.patch("kognic.auth.cli.call.load_config")
    @mock.patch("kognic.auth.cli.call.RequestsAuthSession")
    def test_call_api_error_status(self, mock_session_class, mock_load_config, mock_resolve_context):
        mock_load_config.return_value = mock.MagicMock()
        mock_resolve_context.return_value = Context(
            name="default",
            host="app.kognic.com",
            auth_server="https://auth.app.kognic.com",
            credentials=None,
        )
        mock_session = mock.MagicMock()
        mock_response = mock.MagicMock()
        mock_response.ok = False
        mock_response.headers = {"Content-Type": "application/json"}
        mock_response.json.return_value = {"error": "not found"}
        mock_session.session.request.return_value = mock_response
        mock_session_class.return_value = mock_session

        parsed = self._make_parsed()
        with mock.patch("builtins.print"):
            result = call_run(parsed)

        self.assertEqual(result, 1)

    def test_call_api_invalid_json_data(self):
        parsed = self._make_parsed(data="not json")
        with mock.patch("builtins.print") as mock_print:
            result = call_run(parsed)

        self.assertEqual(result, 1)
        error_output = mock_print.call_args[0][0]
        self.assertIn("Invalid JSON data", error_output)

    def test_call_api_invalid_header_format(self):
        parsed = self._make_parsed(headers=["BadHeader"])
        with mock.patch("builtins.print") as mock_print:
            result = call_run(parsed)

        self.assertEqual(result, 1)
        error_output = mock_print.call_args[0][0]
        self.assertIn("Invalid header format", error_output)

    @mock.patch("kognic.auth.cli.call.resolve_context")
    @mock.patch("kognic.auth.cli.call.load_config")
    @mock.patch("kognic.auth.cli.call.RequestsAuthSession")
    def test_call_api_plain_text_response(self, mock_session_class, mock_load_config, mock_resolve_context):
        mock_load_config.return_value = mock.MagicMock()
        mock_resolve_context.return_value = Context(
            name="default",
            host="app.kognic.com",
            auth_server="https://auth.app.kognic.com",
            credentials=None,
        )
        mock_session = mock.MagicMock()
        mock_response = mock.MagicMock()
        mock_response.ok = True
        mock_response.headers = {"Content-Type": "text/plain"}
        mock_response.text = "Hello World"
        mock_session.session.request.return_value = mock_response
        mock_session_class.return_value = mock_session

        parsed = self._make_parsed()
        with mock.patch("builtins.print") as mock_print:
            result = call_run(parsed)

        self.assertEqual(result, 0)
        mock_print.assert_called_once_with("Hello World")

    @mock.patch("kognic.auth.cli.call.resolve_context")
    @mock.patch("kognic.auth.cli.call.load_config")
    def test_call_api_uses_context_credentials(self, mock_load_config, mock_resolve_context):
        mock_load_config.return_value = mock.MagicMock()
        mock_resolve_context.return_value = Context(
            name="demo",
            host="demo.kognic.com",
            auth_server="https://auth.demo.kognic.com",
            credentials="/path/to/demo-creds.json",
        )

        with mock.patch("kognic.auth.cli.call.RequestsAuthSession") as mock_session_class:
            mock_session = mock.MagicMock()
            mock_response = mock.MagicMock()
            mock_response.ok = True
            mock_response.headers = {"Content-Type": "text/plain"}
            mock_response.text = "ok"
            mock_session.session.request.return_value = mock_response
            mock_session_class.return_value = mock_session

            parsed = self._make_parsed(url="https://demo.kognic.com/v1/projects")
            with mock.patch("builtins.print"):
                call_run(parsed)

            mock_session_class.assert_called_once_with(
                auth="/path/to/demo-creds.json",
                host="https://auth.demo.kognic.com",
            )


if __name__ == "__main__":
    unittest.main()
