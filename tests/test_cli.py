import json
import time
import unittest
from unittest import mock

from kognic.auth import DEFAULT_HOST
from kognic.auth.cli import create_parser, main
from kognic.auth.cli.api_request import _create_parser as create_kog_parser
from kognic.auth.cli.api_request import run as call_run
from kognic.auth.env_config import Environment


class CliParserTest(unittest.TestCase):
    def test_default_server(self):
        parser = create_parser()
        args = parser.parse_args(["get-access-token"])
        self.assertIsNone(args.server)
        self.assertIsNone(args.credentials)
        self.assertIsNone(args.env_name)

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
        args = parser.parse_args(["get-access-token", "--env", "demo"])
        self.assertEqual(args.env_name, "demo")

    def test_no_command_shows_help(self):
        with mock.patch("builtins.print"):
            result = main([])
        self.assertEqual(result, 0)

    def test_no_cache_flag(self):
        parser = create_parser()
        args = parser.parse_args(["get-access-token", "--no-cache"])
        self.assertTrue(args.no_cache)

    def test_no_cache_default_false(self):
        parser = create_parser()
        args = parser.parse_args(["get-access-token"])
        self.assertFalse(args.no_cache)


class CliMainTest(unittest.TestCase):
    @mock.patch("kognic.auth.cli.get_access_token.RequestsAuthSession")
    def test_main_prints_token(self, mock_session_class):
        mock_session = mock.MagicMock()
        mock_session.access_token = "test-access-token-123"
        mock_session_class.return_value = mock_session

        with mock.patch("builtins.print") as mock_print:
            result = main(["get-access-token", "--no-cache"])

        self.assertEqual(result, 0)
        mock_print.assert_called_once_with("test-access-token-123")
        mock_session_class.assert_called_once_with(auth=None, host=DEFAULT_HOST)

    @mock.patch("kognic.auth.cli.get_access_token.RequestsAuthSession")
    def test_main_with_credentials_file(self, mock_session_class):
        mock_session = mock.MagicMock()
        mock_session.access_token = "token-from-file"
        mock_session_class.return_value = mock_session

        with mock.patch("builtins.print") as mock_print:
            result = main(["get-access-token", "--credentials", "/path/to/creds.json", "--no-cache"])

        self.assertEqual(result, 0)
        mock_print.assert_called_once_with("token-from-file")
        mock_session_class.assert_called_once_with(auth="/path/to/creds.json", host=DEFAULT_HOST)

    @mock.patch("kognic.auth.cli.get_access_token.RequestsAuthSession")
    def test_main_with_custom_server(self, mock_session_class):
        mock_session = mock.MagicMock()
        mock_session.access_token = "custom-server-token"
        mock_session_class.return_value = mock_session

        with mock.patch("builtins.print") as mock_print:
            result = main(["get-access-token", "--server", "https://custom.server", "--no-cache"])

        self.assertEqual(result, 0)
        mock_print.assert_called_once_with("custom-server-token")
        mock_session_class.assert_called_once_with(auth=None, host="https://custom.server")

    @mock.patch("kognic.auth.cli.get_access_token.RequestsAuthSession")
    def test_main_with_all_options(self, mock_session_class):
        mock_session = mock.MagicMock()
        mock_session.access_token = "full-options-token"
        mock_session_class.return_value = mock_session

        with mock.patch("builtins.print"):
            result = main(
                ["get-access-token", "--server", "https://my.server", "--credentials", "creds.json", "--no-cache"]
            )

        self.assertEqual(result, 0)
        mock_session_class.assert_called_once_with(auth="creds.json", host="https://my.server")

    @mock.patch("kognic.auth.cli.get_access_token.RequestsAuthSession")
    def test_main_file_not_found(self, mock_session_class):
        mock_session_class.side_effect = FileNotFoundError("Could not find Api Credentials file at /bad/path.json")

        with mock.patch("builtins.print") as mock_print:
            result = main(["get-access-token", "--credentials", "/bad/path.json", "--no-cache"])

        self.assertEqual(result, 1)
        mock_print.assert_called_once()
        self.assertIn("Error:", mock_print.call_args[0][0])

    @mock.patch("kognic.auth.cli.get_access_token.RequestsAuthSession")
    def test_main_value_error(self, mock_session_class):
        mock_session_class.side_effect = ValueError("Bad auth credentials")

        with mock.patch("builtins.print") as mock_print:
            result = main(["get-access-token", "--no-cache"])

        self.assertEqual(result, 1)
        mock_print.assert_called_once()
        self.assertIn("Error:", mock_print.call_args[0][0])

    @mock.patch("kognic.auth.cli.get_access_token.RequestsAuthSession")
    def test_main_generic_exception(self, mock_session_class):
        mock_session_class.side_effect = Exception("Network error")

        with mock.patch("builtins.print") as mock_print:
            result = main(["get-access-token", "--no-cache"])

        self.assertEqual(result, 1)
        mock_print.assert_called_once()
        self.assertIn("Error fetching token:", mock_print.call_args[0][0])

    @mock.patch("kognic.auth.cli.get_access_token.RequestsAuthSession")
    @mock.patch("kognic.auth.cli.get_access_token.load_kognic_env_config")
    def test_main_with_context(self, mock_load_config, mock_session_class):
        from kognic.auth.env_config import KognicEnvConfig

        mock_load_config.return_value = KognicEnvConfig(
            environments={
                "demo": Environment(
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
            result = main(["get-access-token", "--env", "demo", "--no-cache"])

        self.assertEqual(result, 0)
        mock_print.assert_called_once_with("demo-token")
        mock_session_class.assert_called_once_with(
            auth="/path/to/demo-creds.json",
            host="https://auth.demo.kognic.com",
        )

    @mock.patch("kognic.auth.cli.get_access_token.RequestsAuthSession")
    @mock.patch("kognic.auth.cli.get_access_token.load_kognic_env_config")
    def test_main_with_context_server_override(self, mock_load_config, mock_session_class):
        from kognic.auth.env_config import KognicEnvConfig

        mock_load_config.return_value = KognicEnvConfig(
            environments={
                "demo": Environment(
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
            result = main(["get-access-token", "--env", "demo", "--server", "https://custom.server", "--no-cache"])

        self.assertEqual(result, 0)
        mock_session_class.assert_called_once_with(
            auth="/path/to/demo-creds.json",
            host="https://custom.server",
        )

    def test_main_with_unknown_context(self):
        with mock.patch("kognic.auth.cli.get_access_token.load_kognic_env_config") as mock_load_config:
            from kognic.auth.env_config import KognicEnvConfig

            mock_load_config.return_value = KognicEnvConfig()

            with mock.patch("builtins.print") as mock_print:
                result = main(["get-access-token", "--env", "nonexistent"])

        self.assertEqual(result, 1)
        mock_print.assert_called_once()
        self.assertIn("Unknown environment", mock_print.call_args[0][0])


class CliCacheTest(unittest.TestCase):
    """Tests for keyring token caching in get-access-token."""

    @mock.patch("kognic.auth.cli.get_access_token.RequestsAuthSession")
    @mock.patch("kognic.auth.cli.token_cache.load_cached_token")
    @mock.patch("kognic.auth.cli.token_cache._keyring_available", return_value=True)
    @mock.patch("kognic.auth.credentials_parser.resolve_credentials", return_value=("client-1", "secret"))
    def test_cache_hit_returns_cached_token(self, mock_resolve, mock_kr, mock_load, mock_session_class):
        mock_load.return_value = {
            "access_token": "cached-token-abc",
            "expires_at": time.time() + 3600,
            "expires_in": 3600,
            "token_type": "bearer",
        }

        with mock.patch("builtins.print") as mock_print:
            result = main(["get-access-token"])

        self.assertEqual(result, 0)
        mock_print.assert_called_once_with("cached-token-abc")
        mock_session_class.assert_not_called()

    @mock.patch("kognic.auth.cli.token_cache.save_token")
    @mock.patch("kognic.auth.cli.token_cache._keyring_available", return_value=True)
    @mock.patch("kognic.auth.cli.get_access_token.RequestsAuthSession")
    @mock.patch("kognic.auth.cli.token_cache.load_cached_token", return_value=None)
    @mock.patch("kognic.auth.credentials_parser.resolve_credentials", return_value=("client-1", "secret"))
    def test_cache_miss_saves_token(self, mock_resolve, mock_load, mock_session_class, mock_kr, mock_save):
        token_dict = {
            "access_token": "fresh-token",
            "expires_at": time.time() + 3600,
            "expires_in": 3600,
            "token_type": "bearer",
        }
        mock_session = mock.MagicMock()
        mock_session.access_token = "fresh-token"
        mock_session.token = token_dict
        mock_session.oauth_session.client_id = "client-1"
        mock_session_class.return_value = mock_session

        with mock.patch("builtins.print") as mock_print:
            result = main(["get-access-token"])

        self.assertEqual(result, 0)
        mock_print.assert_called_once_with("fresh-token")
        mock_save.assert_called_once_with(DEFAULT_HOST, "client-1", token_dict)

    @mock.patch("kognic.auth.cli.token_cache.save_token")
    @mock.patch("kognic.auth.cli.token_cache.load_cached_token")
    @mock.patch("kognic.auth.cli.get_access_token.RequestsAuthSession")
    def test_no_cache_skips_keyring(self, mock_session_class, mock_load, mock_save):
        mock_session = mock.MagicMock()
        mock_session.access_token = "no-cache-token"
        mock_session_class.return_value = mock_session

        with mock.patch("builtins.print") as mock_print:
            result = main(["get-access-token", "--no-cache"])

        self.assertEqual(result, 0)
        mock_print.assert_called_once_with("no-cache-token")
        mock_load.assert_not_called()
        mock_save.assert_not_called()

    @mock.patch("kognic.auth.cli.get_access_token.RequestsAuthSession")
    @mock.patch("kognic.auth.cli.token_cache.load_cached_token", return_value=None)
    @mock.patch("kognic.auth.credentials_parser.resolve_credentials", side_effect=FileNotFoundError("no file"))
    def test_cache_credential_resolve_failure_falls_through(self, mock_resolve, mock_load, mock_session_class):
        """If resolve_credentials fails during cache check, fall through to normal auth flow."""
        mock_session = mock.MagicMock()
        mock_session.access_token = "fallback-token"
        mock_session_class.return_value = mock_session

        with mock.patch("builtins.print") as mock_print:
            result = main(["get-access-token"])

        self.assertEqual(result, 0)
        mock_print.assert_called_once_with("fallback-token")
        mock_load.assert_not_called()


class KogParserTest(unittest.TestCase):
    def test_kog_basic(self):
        parser = create_kog_parser()
        args = parser.parse_args(["get", "https://app.kognic.com/v1/projects"])
        self.assertEqual(args.method, "get")
        self.assertEqual(args.url, "https://app.kognic.com/v1/projects")
        self.assertIsNone(args.data)
        self.assertIsNone(args.headers)
        self.assertIsNone(args.env_name)

    def test_kog_with_method(self):
        parser = create_kog_parser()
        args = parser.parse_args(["post", "https://app.kognic.com/v1/projects"])
        self.assertEqual(args.method, "post")

    def test_kog_with_data(self):
        parser = create_kog_parser()
        args = parser.parse_args(["post", "https://app.kognic.com/v1/projects", "-d", '{"name": "test"}'])
        self.assertEqual(args.method, "post")
        self.assertEqual(args.data, '{"name": "test"}')

    def test_kog_with_headers(self):
        parser = create_kog_parser()
        args = parser.parse_args(
            [
                "get",
                "https://app.kognic.com/v1/projects",
                "-H",
                "Accept: application/json",
                "-H",
                "X-Custom: value",
            ]
        )
        self.assertEqual(args.headers, ["Accept: application/json", "X-Custom: value"])

    def test_kog_with_env(self):
        parser = create_kog_parser()
        args = parser.parse_args(["get", "https://demo.kognic.com/v1/projects", "--env", "demo"])
        self.assertEqual(args.env_name, "demo")

    def test_kog_with_config(self):
        parser = create_kog_parser()
        args = parser.parse_args(
            ["get", "https://app.kognic.com/v1/projects", "--env-config-file-path", "/custom/config.json"]
        )
        self.assertEqual(args.env_config_file_path, "/custom/config.json")

    def test_kog_no_cache_flag(self):
        parser = create_kog_parser()
        args = parser.parse_args(["get", "https://app.kognic.com/v1/projects", "--no-cache"])
        self.assertTrue(args.no_cache)

    def test_kog_no_cache_default_false(self):
        parser = create_kog_parser()
        args = parser.parse_args(["get", "https://app.kognic.com/v1/projects"])
        self.assertFalse(args.no_cache)


class CallApiTest(unittest.TestCase):
    def _make_parsed(
        self,
        method="get",
        url="https://app.kognic.com/v1/projects",
        data=None,
        headers=None,
        env_config_file_path="/nonexistent/config.json",
        env_name=None,
        no_cache=True,
    ):
        parser = create_kog_parser()
        args = [method, url]
        if data:
            args.extend(["-d", data])
        if headers:
            for h in headers:
                args.extend(["-H", h])
        args.extend(["--env-config-file-path", env_config_file_path])
        if env_name:
            args.extend(["--env", env_name])
        if no_cache:
            args.append("--no-cache")
        return parser.parse_args(args)

    @mock.patch("kognic.auth.cli.api_request.resolve_environment")
    @mock.patch("kognic.auth.cli.api_request.load_kognic_env_config")
    @mock.patch("kognic.auth.cli.api_request._create_authenticated_session")
    def test_call_api_get_success(self, mock_create_session, mock_load_config, mock_resolve_environment):
        mock_load_config.return_value = mock.MagicMock()
        mock_resolve_environment.return_value = Environment(
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
        mock_session.request.return_value = mock_response
        mock_create_session.return_value = mock_session

        parsed = self._make_parsed()
        with mock.patch("builtins.print") as mock_print:
            result = call_run(parsed)

        self.assertEqual(result, 0)
        mock_session.request.assert_called_once_with(
            method="GET",
            url="https://app.kognic.com/v1/projects",
            json=None,
            headers=None,
        )
        mock_print.assert_called_once_with(json.dumps({"projects": []}, indent=2))

    @mock.patch("kognic.auth.cli.api_request.resolve_environment")
    @mock.patch("kognic.auth.cli.api_request.load_kognic_env_config")
    @mock.patch("kognic.auth.cli.api_request._create_authenticated_session")
    def test_call_api_post_with_data(self, mock_create_session, mock_load_config, mock_resolve_environment):
        mock_load_config.return_value = mock.MagicMock()
        mock_resolve_environment.return_value = Environment(
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
        mock_session.request.return_value = mock_response
        mock_create_session.return_value = mock_session

        parsed = self._make_parsed(method="post", data='{"name": "test"}')
        with mock.patch("builtins.print"):
            result = call_run(parsed)

        self.assertEqual(result, 0)
        mock_session.request.assert_called_once_with(
            method="POST",
            url="https://app.kognic.com/v1/projects",
            json={"name": "test"},
            headers={"Content-Type": "application/json"},
        )

    @mock.patch("kognic.auth.cli.api_request.resolve_environment")
    @mock.patch("kognic.auth.cli.api_request.load_kognic_env_config")
    @mock.patch("kognic.auth.cli.api_request._create_authenticated_session")
    def test_call_api_with_custom_headers(self, mock_create_session, mock_load_config, mock_resolve_environment):
        mock_load_config.return_value = mock.MagicMock()
        mock_resolve_environment.return_value = Environment(
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
        mock_session.request.return_value = mock_response
        mock_create_session.return_value = mock_session

        parsed = self._make_parsed(headers=["Accept: text/plain", "X-Custom: value"])
        with mock.patch("builtins.print"):
            result = call_run(parsed)

        self.assertEqual(result, 0)
        mock_session.request.assert_called_once_with(
            method="GET",
            url="https://app.kognic.com/v1/projects",
            json=None,
            headers={"Accept": "text/plain", "X-Custom": "value"},
        )

    @mock.patch("kognic.auth.cli.api_request.resolve_environment")
    @mock.patch("kognic.auth.cli.api_request.load_kognic_env_config")
    @mock.patch("kognic.auth.cli.api_request._create_authenticated_session")
    def test_call_api_error_status(self, mock_create_session, mock_load_config, mock_resolve_environment):
        mock_load_config.return_value = mock.MagicMock()
        mock_resolve_environment.return_value = Environment(
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
        mock_session.request.return_value = mock_response
        mock_create_session.return_value = mock_session

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

    @mock.patch("kognic.auth.cli.api_request.resolve_environment")
    @mock.patch("kognic.auth.cli.api_request.load_kognic_env_config")
    @mock.patch("kognic.auth.cli.api_request._create_authenticated_session")
    def test_call_api_plain_text_response(self, mock_create_session, mock_load_config, mock_resolve_environment):
        mock_load_config.return_value = mock.MagicMock()
        mock_resolve_environment.return_value = Environment(
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
        mock_session.request.return_value = mock_response
        mock_create_session.return_value = mock_session

        parsed = self._make_parsed()
        with mock.patch("builtins.print") as mock_print:
            result = call_run(parsed)

        self.assertEqual(result, 0)
        mock_print.assert_called_once_with("Hello World")

    @mock.patch("kognic.auth.cli.api_request.resolve_environment")
    @mock.patch("kognic.auth.cli.api_request.load_kognic_env_config")
    @mock.patch("kognic.auth.cli.api_request._create_authenticated_session")
    def test_call_api_jsonl_data_array(self, mock_create_session, mock_load_config, mock_resolve_environment):
        mock_load_config.return_value = mock.MagicMock()
        mock_resolve_environment.return_value = Environment(
            name="default",
            host="app.kognic.com",
            auth_server="https://auth.app.kognic.com",
            credentials=None,
        )
        mock_session = mock.MagicMock()
        mock_response = mock.MagicMock()
        mock_response.ok = True
        mock_response.headers = {"Content-Type": "application/json"}
        mock_response.json.return_value = {"data": [{"id": 1, "name": "a"}, {"id": 2, "name": "b"}]}
        mock_session.request.return_value = mock_response
        mock_create_session.return_value = mock_session

        parsed = self._make_parsed()
        parsed.output_format = "jsonl"
        with mock.patch("builtins.print") as mock_print:
            result = call_run(parsed)

        self.assertEqual(result, 0)
        self.assertEqual(mock_print.call_count, 2)
        mock_print.assert_any_call(json.dumps({"id": 1, "name": "a"}))
        mock_print.assert_any_call(json.dumps({"id": 2, "name": "b"}))

    @mock.patch("kognic.auth.cli.api_request.resolve_environment")
    @mock.patch("kognic.auth.cli.api_request.load_kognic_env_config")
    @mock.patch("kognic.auth.cli.api_request._create_authenticated_session")
    def test_call_api_jsonl_single_key_non_data(self, mock_create_session, mock_load_config, mock_resolve_environment):
        """When --format=jsonl is used and response has a single key holding a list, flatten it."""
        mock_load_config.return_value = mock.MagicMock()
        mock_resolve_environment.return_value = Environment(
            name="default",
            host="app.kognic.com",
            auth_server="https://auth.app.kognic.com",
            credentials=None,
        )
        mock_session = mock.MagicMock()
        mock_response = mock.MagicMock()
        mock_response.ok = True
        mock_response.headers = {"Content-Type": "application/json"}
        mock_response.json.return_value = {"projects": [{"id": 1}, {"id": 2}]}
        mock_session.request.return_value = mock_response
        mock_create_session.return_value = mock_session

        parsed = self._make_parsed()
        parsed.output_format = "jsonl"
        with mock.patch("builtins.print") as mock_print:
            result = call_run(parsed)

        self.assertEqual(result, 0)
        self.assertEqual(mock_print.call_count, 2)
        mock_print.assert_any_call(json.dumps({"id": 1}))
        mock_print.assert_any_call(json.dumps({"id": 2}))

    @mock.patch("kognic.auth.cli.api_request.resolve_environment")
    @mock.patch("kognic.auth.cli.api_request.load_kognic_env_config")
    @mock.patch("kognic.auth.cli.api_request._create_authenticated_session")
    def test_call_api_jsonl_multiple_keys(self, mock_create_session, mock_load_config, mock_resolve_environment):
        """When --format=jsonl is used but response has multiple keys, pretty-print as usual."""
        mock_load_config.return_value = mock.MagicMock()
        mock_resolve_environment.return_value = Environment(
            name="default",
            host="app.kognic.com",
            auth_server="https://auth.app.kognic.com",
            credentials=None,
        )
        mock_session = mock.MagicMock()
        mock_response = mock.MagicMock()
        mock_response.ok = True
        mock_response.headers = {"Content-Type": "application/json"}
        mock_response.json.return_value = {"data": [{"id": 1}], "total": 1}
        mock_session.request.return_value = mock_response
        mock_create_session.return_value = mock_session

        parsed = self._make_parsed()
        parsed.output_format = "jsonl"
        with mock.patch("builtins.print") as mock_print:
            result = call_run(parsed)

        self.assertEqual(result, 0)
        mock_print.assert_called_once_with(json.dumps({"data": [{"id": 1}], "total": 1}, indent=2))

    @mock.patch("kognic.auth.cli.api_request.resolve_environment")
    @mock.patch("kognic.auth.cli.api_request.load_kognic_env_config")
    @mock.patch("kognic.auth.cli.api_request._create_authenticated_session")
    def test_call_api_jsonl_top_level_list(self, mock_create_session, mock_load_config, mock_resolve_environment):
        """When --format=jsonl is used and response body is a list, flatten it."""
        mock_load_config.return_value = mock.MagicMock()
        mock_resolve_environment.return_value = Environment(
            name="default",
            host="app.kognic.com",
            auth_server="https://auth.app.kognic.com",
            credentials=None,
        )
        mock_session = mock.MagicMock()
        mock_response = mock.MagicMock()
        mock_response.ok = True
        mock_response.headers = {"Content-Type": "application/json"}
        mock_response.json.return_value = [{"id": 1}, {"id": 2}, {"id": 3}]
        mock_session.request.return_value = mock_response
        mock_create_session.return_value = mock_session

        parsed = self._make_parsed()
        parsed.output_format = "jsonl"
        with mock.patch("builtins.print") as mock_print:
            result = call_run(parsed)

        self.assertEqual(result, 0)
        self.assertEqual(mock_print.call_count, 3)
        mock_print.assert_any_call(json.dumps({"id": 1}))
        mock_print.assert_any_call(json.dumps({"id": 2}))
        mock_print.assert_any_call(json.dumps({"id": 3}))

    @mock.patch("kognic.auth.cli.api_request.resolve_environment")
    @mock.patch("kognic.auth.cli.api_request.load_kognic_env_config")
    @mock.patch("kognic.auth.cli.api_request._create_authenticated_session")
    def test_call_api_jsonl_empty_data(self, mock_create_session, mock_load_config, mock_resolve_environment):
        """When --format=jsonl is used and data is an empty list, nothing is printed."""
        mock_load_config.return_value = mock.MagicMock()
        mock_resolve_environment.return_value = Environment(
            name="default",
            host="app.kognic.com",
            auth_server="https://auth.app.kognic.com",
            credentials=None,
        )
        mock_session = mock.MagicMock()
        mock_response = mock.MagicMock()
        mock_response.ok = True
        mock_response.headers = {"Content-Type": "application/json"}
        mock_response.json.return_value = {"data": []}
        mock_session.request.return_value = mock_response
        mock_create_session.return_value = mock_session

        parsed = self._make_parsed()
        parsed.output_format = "jsonl"
        with mock.patch("builtins.print") as mock_print:
            result = call_run(parsed)

        self.assertEqual(result, 0)
        mock_print.assert_not_called()

    @mock.patch("kognic.auth.cli.api_request.resolve_environment")
    @mock.patch("kognic.auth.cli.api_request.load_kognic_env_config")
    @mock.patch("kognic.auth.cli.api_request._create_authenticated_session")
    def test_call_api_csv_data_array(self, mock_create_session, mock_load_config, mock_resolve_environment):
        mock_load_config.return_value = mock.MagicMock()
        mock_resolve_environment.return_value = Environment(
            name="default",
            host="app.kognic.com",
            auth_server="https://auth.app.kognic.com",
            credentials=None,
        )
        mock_session = mock.MagicMock()
        mock_response = mock.MagicMock()
        mock_response.ok = True
        mock_response.headers = {"Content-Type": "application/json"}
        mock_response.json.return_value = {"data": [{"id": 1, "name": "a"}, {"id": 2, "name": "b"}]}
        mock_session.request.return_value = mock_response
        mock_create_session.return_value = mock_session

        parsed = self._make_parsed()
        parsed.output_format = "csv"
        with mock.patch("builtins.print") as mock_print:
            result = call_run(parsed)

        self.assertEqual(result, 0)
        output = mock_print.call_args[0][0]
        lines = output.strip().split("\r\n")
        self.assertEqual(lines[0], "id,name")
        self.assertEqual(lines[1], "1,a")
        self.assertEqual(lines[2], "2,b")

    @mock.patch("kognic.auth.cli.api_request.resolve_environment")
    @mock.patch("kognic.auth.cli.api_request.load_kognic_env_config")
    @mock.patch("kognic.auth.cli.api_request._create_authenticated_session")
    def test_call_api_tsv_data_array(self, mock_create_session, mock_load_config, mock_resolve_environment):
        mock_load_config.return_value = mock.MagicMock()
        mock_resolve_environment.return_value = Environment(
            name="default",
            host="app.kognic.com",
            auth_server="https://auth.app.kognic.com",
            credentials=None,
        )
        mock_session = mock.MagicMock()
        mock_response = mock.MagicMock()
        mock_response.ok = True
        mock_response.headers = {"Content-Type": "application/json"}
        mock_response.json.return_value = {"data": [{"id": 1, "name": "a"}, {"id": 2, "name": "b"}]}
        mock_session.request.return_value = mock_response
        mock_create_session.return_value = mock_session

        parsed = self._make_parsed()
        parsed.output_format = "tsv"
        with mock.patch("builtins.print") as mock_print:
            result = call_run(parsed)

        self.assertEqual(result, 0)
        output = mock_print.call_args[0][0]
        lines = output.strip().split("\r\n")
        self.assertEqual(lines[0], "id\tname")
        self.assertEqual(lines[1], "1\ta")
        self.assertEqual(lines[2], "2\tb")

    @mock.patch("kognic.auth.cli.api_request.resolve_environment")
    @mock.patch("kognic.auth.cli.api_request.load_kognic_env_config")
    @mock.patch("kognic.auth.cli.api_request._create_authenticated_session")
    def test_call_api_table_data_array(self, mock_create_session, mock_load_config, mock_resolve_environment):
        mock_load_config.return_value = mock.MagicMock()
        mock_resolve_environment.return_value = Environment(
            name="default",
            host="app.kognic.com",
            auth_server="https://auth.app.kognic.com",
            credentials=None,
        )
        mock_session = mock.MagicMock()
        mock_response = mock.MagicMock()
        mock_response.ok = True
        mock_response.headers = {"Content-Type": "application/json"}
        mock_response.json.return_value = {"data": [{"id": 1, "name": "alice"}, {"id": 2, "name": "b"}]}
        mock_session.request.return_value = mock_response
        mock_create_session.return_value = mock_session

        parsed = self._make_parsed()
        parsed.output_format = "table"
        with mock.patch("builtins.print") as mock_print:
            result = call_run(parsed)

        self.assertEqual(result, 0)
        lines = [call[0][0] for call in mock_print.call_args_list]
        self.assertEqual(lines[0], "| id | name  |")
        self.assertEqual(lines[1], "|----|-------|")
        self.assertEqual(lines[2], "| 1  | alice |")
        self.assertEqual(lines[3], "| 2  | b     |")

    @mock.patch("kognic.auth.cli.api_request.resolve_environment")
    @mock.patch("kognic.auth.cli.api_request.load_kognic_env_config")
    @mock.patch("kognic.auth.cli.api_request._create_authenticated_session")
    def test_call_api_table_empty_data(self, mock_create_session, mock_load_config, mock_resolve_environment):
        """Table with empty list prints nothing."""
        mock_load_config.return_value = mock.MagicMock()
        mock_resolve_environment.return_value = Environment(
            name="default",
            host="app.kognic.com",
            auth_server="https://auth.app.kognic.com",
            credentials=None,
        )
        mock_session = mock.MagicMock()
        mock_response = mock.MagicMock()
        mock_response.ok = True
        mock_response.headers = {"Content-Type": "application/json"}
        mock_response.json.return_value = {"data": []}
        mock_session.request.return_value = mock_response
        mock_create_session.return_value = mock_session

        parsed = self._make_parsed()
        parsed.output_format = "table"
        with mock.patch("builtins.print") as mock_print:
            result = call_run(parsed)

        self.assertEqual(result, 0)
        mock_print.assert_not_called()

    @mock.patch("kognic.auth.cli.api_request.resolve_environment")
    @mock.patch("kognic.auth.cli.api_request.load_kognic_env_config")
    @mock.patch("kognic.auth.cli.api_request._create_authenticated_session")
    def test_call_api_csv_nested_values(self, mock_create_session, mock_load_config, mock_resolve_environment):
        """Nested dicts and lists are JSON-serialized in CSV output."""
        mock_load_config.return_value = mock.MagicMock()
        mock_resolve_environment.return_value = Environment(
            name="default",
            host="app.kognic.com",
            auth_server="https://auth.app.kognic.com",
            credentials=None,
        )
        mock_session = mock.MagicMock()
        mock_response = mock.MagicMock()
        mock_response.ok = True
        mock_response.headers = {"Content-Type": "application/json"}
        mock_response.json.return_value = {"data": [{"id": 1, "tags": ["a", "b"], "meta": {"key": "val"}}]}
        mock_session.request.return_value = mock_response
        mock_create_session.return_value = mock_session

        parsed = self._make_parsed()
        parsed.output_format = "csv"
        with mock.patch("builtins.print") as mock_print:
            result = call_run(parsed)

        self.assertEqual(result, 0)
        output = mock_print.call_args[0][0]
        lines = output.strip().split("\r\n")
        self.assertEqual(lines[0], "id,tags,meta")
        self.assertEqual(lines[1], '1,"[""a"", ""b""]","{""key"": ""val""}"')

    @mock.patch("kognic.auth.cli.api_request.resolve_environment")
    @mock.patch("kognic.auth.cli.api_request.load_kognic_env_config")
    @mock.patch("kognic.auth.cli.api_request._create_authenticated_session")
    def test_call_api_table_nested_values(self, mock_create_session, mock_load_config, mock_resolve_environment):
        """Nested dicts and lists are JSON-serialized in table output."""
        mock_load_config.return_value = mock.MagicMock()
        mock_resolve_environment.return_value = Environment(
            name="default",
            host="app.kognic.com",
            auth_server="https://auth.app.kognic.com",
            credentials=None,
        )
        mock_session = mock.MagicMock()
        mock_response = mock.MagicMock()
        mock_response.ok = True
        mock_response.headers = {"Content-Type": "application/json"}
        mock_response.json.return_value = {"data": [{"id": 1, "tags": ["a", "b"]}]}
        mock_session.request.return_value = mock_response
        mock_create_session.return_value = mock_session

        parsed = self._make_parsed()
        parsed.output_format = "table"
        with mock.patch("builtins.print") as mock_print:
            result = call_run(parsed)

        self.assertEqual(result, 0)
        lines = [call[0][0] for call in mock_print.call_args_list]
        self.assertEqual(lines[0], "| id | tags       |")
        self.assertEqual(lines[1], "|----|------------|")
        self.assertEqual(lines[2], '| 1  | ["a", "b"] |')

    @mock.patch("kognic.auth.cli.api_request.resolve_environment")
    @mock.patch("kognic.auth.cli.api_request.load_kognic_env_config")
    @mock.patch("kognic.auth.cli.api_request._create_authenticated_session")
    def test_call_api_csv_top_level_list(self, mock_create_session, mock_load_config, mock_resolve_environment):
        mock_load_config.return_value = mock.MagicMock()
        mock_resolve_environment.return_value = Environment(
            name="default",
            host="app.kognic.com",
            auth_server="https://auth.app.kognic.com",
            credentials=None,
        )
        mock_session = mock.MagicMock()
        mock_response = mock.MagicMock()
        mock_response.ok = True
        mock_response.headers = {"Content-Type": "application/json"}
        mock_response.json.return_value = [{"x": 10, "y": 20}, {"x": 30, "y": 40}]
        mock_session.request.return_value = mock_response
        mock_create_session.return_value = mock_session

        parsed = self._make_parsed()
        parsed.output_format = "csv"
        with mock.patch("builtins.print") as mock_print:
            result = call_run(parsed)

        self.assertEqual(result, 0)
        output = mock_print.call_args[0][0]
        lines = output.strip().split("\r\n")
        self.assertEqual(lines[0], "x,y")
        self.assertEqual(lines[1], "10,20")
        self.assertEqual(lines[2], "30,40")

    @mock.patch("kognic.auth.cli.api_request.resolve_environment")
    @mock.patch("kognic.auth.cli.api_request.load_kognic_env_config")
    @mock.patch("kognic.auth.cli.api_request._create_authenticated_session")
    def test_call_api_csv_sparse_keys(self, mock_create_session, mock_load_config, mock_resolve_environment):
        """CSV output includes all keys across all rows, with blanks for missing values."""
        mock_load_config.return_value = mock.MagicMock()
        mock_resolve_environment.return_value = Environment(
            name="default",
            host="app.kognic.com",
            auth_server="https://auth.app.kognic.com",
            credentials=None,
        )
        mock_session = mock.MagicMock()
        mock_response = mock.MagicMock()
        mock_response.ok = True
        mock_response.headers = {"Content-Type": "application/json"}
        mock_response.json.return_value = {"data": [{"id": 1, "name": "a"}, {"id": 2, "extra": "z"}]}
        mock_session.request.return_value = mock_response
        mock_create_session.return_value = mock_session

        parsed = self._make_parsed()
        parsed.output_format = "csv"
        with mock.patch("builtins.print") as mock_print:
            result = call_run(parsed)

        self.assertEqual(result, 0)
        output = mock_print.call_args[0][0]
        lines = output.strip().split("\r\n")
        self.assertEqual(lines[0], "id,name,extra")
        self.assertEqual(lines[1], "1,a,")
        self.assertEqual(lines[2], "2,,z")

    @mock.patch("kognic.auth.cli.api_request.resolve_environment")
    @mock.patch("kognic.auth.cli.api_request.load_kognic_env_config")
    @mock.patch("kognic.auth.cli.api_request._create_authenticated_session")
    def test_call_api_csv_empty_data(self, mock_create_session, mock_load_config, mock_resolve_environment):
        """CSV with empty list prints nothing."""
        mock_load_config.return_value = mock.MagicMock()
        mock_resolve_environment.return_value = Environment(
            name="default",
            host="app.kognic.com",
            auth_server="https://auth.app.kognic.com",
            credentials=None,
        )
        mock_session = mock.MagicMock()
        mock_response = mock.MagicMock()
        mock_response.ok = True
        mock_response.headers = {"Content-Type": "application/json"}
        mock_response.json.return_value = {"data": []}
        mock_session.request.return_value = mock_response
        mock_create_session.return_value = mock_session

        parsed = self._make_parsed()
        parsed.output_format = "csv"
        with mock.patch("builtins.print") as mock_print:
            result = call_run(parsed)

        self.assertEqual(result, 0)
        mock_print.assert_not_called()

    @mock.patch("kognic.auth.cli.api_request.resolve_environment")
    @mock.patch("kognic.auth.cli.api_request.load_kognic_env_config")
    @mock.patch("kognic.auth.cli.api_request._create_authenticated_session")
    def test_call_api_csv_not_flattenable(self, mock_create_session, mock_load_config, mock_resolve_environment):
        """CSV with non-flattenable response falls back to pretty JSON."""
        mock_load_config.return_value = mock.MagicMock()
        mock_resolve_environment.return_value = Environment(
            name="default",
            host="app.kognic.com",
            auth_server="https://auth.app.kognic.com",
            credentials=None,
        )
        mock_session = mock.MagicMock()
        mock_response = mock.MagicMock()
        mock_response.ok = True
        mock_response.headers = {"Content-Type": "application/json"}
        mock_response.json.return_value = {"a": 1, "b": 2}
        mock_session.request.return_value = mock_response
        mock_create_session.return_value = mock_session

        parsed = self._make_parsed()
        parsed.output_format = "csv"
        with mock.patch("builtins.print") as mock_print:
            result = call_run(parsed)

        self.assertEqual(result, 0)
        mock_print.assert_called_once_with(json.dumps({"a": 1, "b": 2}, indent=2))

    @mock.patch("kognic.auth.cli.api_request.resolve_environment")
    @mock.patch("kognic.auth.cli.api_request.load_kognic_env_config")
    def test_call_api_uses_context_credentials(self, mock_load_config, mock_resolve_environment):
        mock_load_config.return_value = mock.MagicMock()
        mock_resolve_environment.return_value = Environment(
            name="demo",
            host="demo.kognic.com",
            auth_server="https://auth.demo.kognic.com",
            credentials="/path/to/demo-creds.json",
        )

        with mock.patch("kognic.auth.cli.api_request._create_authenticated_session") as mock_create_session:
            mock_session = mock.MagicMock()
            mock_response = mock.MagicMock()
            mock_response.ok = True
            mock_response.headers = {"Content-Type": "text/plain"}
            mock_response.text = "ok"
            mock_session.request.return_value = mock_response
            mock_create_session.return_value = mock_session

            parsed = self._make_parsed(url="https://demo.kognic.com/v1/projects")
            with mock.patch("builtins.print"):
                call_run(parsed)

            mock_create_session.assert_called_once_with(
                auth="/path/to/demo-creds.json",
                auth_host="https://auth.demo.kognic.com",
                use_cache=False,
            )


class KogCacheTest(unittest.TestCase):
    """Tests for keyring token caching in kog command."""

    @mock.patch("kognic.auth.cli.api_request.resolve_environment")
    @mock.patch("kognic.auth.cli.api_request.load_kognic_env_config")
    @mock.patch("kognic.auth.requests.auth_session.RequestsAuthSession")
    @mock.patch("kognic.auth.cli.token_cache.load_cached_token")
    @mock.patch("kognic.auth.cli.token_cache._keyring_available", return_value=True)
    def test_kog_uses_cached_token(
        self, mock_kr, mock_load, mock_session_class, mock_load_config, mock_resolve_environment
    ):
        """When a cached token is available, kog injects it and skips the network fetch."""
        mock_load_config.return_value = mock.MagicMock()
        mock_resolve_environment.return_value = Environment(
            name="default",
            host="app.kognic.com",
            auth_server="https://auth.app.kognic.com",
            credentials="/path/to/creds.json",
        )

        cached_token = {
            "access_token": "cached-kog-token",
            "expires_at": time.time() + 3600,
            "expires_in": 3600,
            "token_type": "bearer",
        }
        mock_load.return_value = cached_token

        mock_auth_session = mock.MagicMock()
        mock_auth_session.oauth_session.client_id = "client-1"
        mock_auth_session.token = cached_token

        mock_raw_session = mock.MagicMock()
        mock_raw_session.headers = {}
        mock_response = mock.MagicMock()
        mock_response.ok = True
        mock_response.headers = {"Content-Type": "application/json"}
        mock_response.json.return_value = {"result": "ok"}
        mock_raw_session.request.return_value = mock_response
        mock_auth_session.session = mock_raw_session

        mock_session_class.return_value = mock_auth_session

        parser = create_kog_parser()
        parsed = parser.parse_args(
            ["get", "https://app.kognic.com/v1/projects", "--env-config-file-path", "/nonexistent/config.json"]
        )
        with mock.patch("builtins.print"):
            result = call_run(parsed)

        self.assertEqual(result, 0)
        mock_load.assert_called_once_with("https://auth.app.kognic.com", "client-1")

    @mock.patch("kognic.auth.cli.api_request.resolve_environment")
    @mock.patch("kognic.auth.cli.api_request.load_kognic_env_config")
    @mock.patch("kognic.auth.cli.api_request._create_authenticated_session")
    def test_kog_no_cache_passes_flag(self, mock_create_session, mock_load_config, mock_resolve_environment):
        """When --no-cache is passed, use_cache=False is forwarded."""
        mock_load_config.return_value = mock.MagicMock()
        mock_resolve_environment.return_value = Environment(
            name="default",
            host="app.kognic.com",
            auth_server="https://auth.app.kognic.com",
            credentials=None,
        )
        mock_session = mock.MagicMock()
        mock_response = mock.MagicMock()
        mock_response.ok = True
        mock_response.headers = {"Content-Type": "text/plain"}
        mock_response.text = "ok"
        mock_session.request.return_value = mock_response
        mock_create_session.return_value = mock_session

        parser = create_kog_parser()
        parsed = parser.parse_args(
            [
                "get",
                "https://app.kognic.com/v1/projects",
                "--env-config-file-path",
                "/nonexistent/config.json",
                "--no-cache",
            ]
        )
        with mock.patch("builtins.print"):
            call_run(parsed)

        mock_create_session.assert_called_once_with(
            auth=None,
            auth_host="https://auth.app.kognic.com",
            use_cache=False,
        )


if __name__ == "__main__":
    unittest.main()
