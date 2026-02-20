import json
import time
import unittest
from pathlib import Path
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

    def test_token_cache_default(self):
        parser = create_parser()
        args = parser.parse_args(["get-access-token"])
        self.assertEqual(args.token_cache, "auto")

    def test_token_cache_none(self):
        parser = create_parser()
        args = parser.parse_args(["get-access-token", "--token-cache", "none"])
        self.assertEqual(args.token_cache, "none")

    def test_token_cache_choices(self):
        parser = create_parser()
        for choice in ("auto", "keyring", "file", "none"):
            args = parser.parse_args(["get-access-token", "--token-cache", choice])
            self.assertEqual(args.token_cache, choice)


class CliMainTest(unittest.TestCase):
    def _make_provider(self, access_token):
        provider = mock.MagicMock()
        provider.ensure_token.return_value = {"access_token": access_token}
        return provider

    @mock.patch("kognic.auth.cli.get_access_token.make_token_provider")
    def test_main_prints_token(self, mock_make_provider):
        mock_make_provider.return_value = self._make_provider("test-access-token-123")

        with mock.patch("builtins.print") as mock_print:
            result = main(["get-access-token", "--token-cache", "none"])

        self.assertEqual(result, 0)
        mock_print.assert_called_once_with("test-access-token-123")

    @mock.patch("kognic.auth.cli.get_access_token.make_token_provider")
    def test_main_with_credentials_file(self, mock_make_provider):
        mock_make_provider.return_value = self._make_provider("token-from-file")

        with mock.patch("builtins.print") as mock_print:
            result = main(["get-access-token", "--credentials", "/path/to/creds.json", "--token-cache", "none"])

        self.assertEqual(result, 0)
        mock_print.assert_called_once_with("token-from-file")
        mock_make_provider.assert_called_once_with(
            auth="/path/to/creds.json",
            auth_host=DEFAULT_HOST,
            token_cache=None,
        )

    @mock.patch("kognic.auth.cli.get_access_token.make_token_provider")
    def test_main_with_custom_server(self, mock_make_provider):
        mock_make_provider.return_value = self._make_provider("custom-server-token")

        with mock.patch("builtins.print") as mock_print:
            result = main(["get-access-token", "--server", "https://custom.server", "--token-cache", "none"])

        self.assertEqual(result, 0)
        mock_print.assert_called_once_with("custom-server-token")
        mock_make_provider.assert_called_once_with(
            auth=None,
            auth_host="https://custom.server",
            token_cache=None,
        )

    @mock.patch("kognic.auth.cli.get_access_token.make_token_provider")
    def test_main_with_all_options(self, mock_make_provider):
        mock_make_provider.return_value = self._make_provider("full-options-token")

        with mock.patch("builtins.print"):
            result = main(
                [
                    "get-access-token",
                    "--server",
                    "https://my.server",
                    "--credentials",
                    "creds.json",
                    "--token-cache",
                    "none",
                ]
            )

        self.assertEqual(result, 0)
        mock_make_provider.assert_called_once_with(
            auth="creds.json",
            auth_host="https://my.server",
            token_cache=None,
        )

    @mock.patch("kognic.auth.cli.get_access_token.make_token_provider")
    def test_main_file_not_found(self, mock_make_provider):
        mock_make_provider.side_effect = FileNotFoundError("Could not find Api Credentials file at /bad/path.json")

        with mock.patch("builtins.print") as mock_print:
            result = main(["get-access-token", "--credentials", "/bad/path.json", "--token-cache", "none"])

        self.assertEqual(result, 1)
        self.assertIn("Error:", mock_print.call_args[0][0])

    @mock.patch("kognic.auth.cli.get_access_token.make_token_provider")
    def test_main_value_error(self, mock_make_provider):
        mock_make_provider.side_effect = ValueError("Bad auth credentials")

        with mock.patch("builtins.print") as mock_print:
            result = main(["get-access-token", "--token-cache", "none"])

        self.assertEqual(result, 1)
        self.assertIn("Error:", mock_print.call_args[0][0])

    @mock.patch("kognic.auth.cli.get_access_token.make_token_provider")
    def test_main_generic_exception(self, mock_make_provider):
        mock_make_provider.side_effect = Exception("Network error")

        with mock.patch("builtins.print") as mock_print:
            result = main(["get-access-token", "--token-cache", "none"])

        self.assertEqual(result, 1)
        self.assertIn("Error fetching token:", mock_print.call_args[0][0])

    @mock.patch("kognic.auth.cli.get_access_token.make_token_provider")
    @mock.patch("kognic.auth.cli.get_access_token.load_kognic_env_config")
    def test_main_with_context(self, mock_load_config, mock_make_provider):
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
        mock_make_provider.return_value = self._make_provider("demo-token")

        with mock.patch("builtins.print") as mock_print:
            result = main(["get-access-token", "--env", "demo", "--token-cache", "none"])

        self.assertEqual(result, 0)
        mock_print.assert_called_once_with("demo-token")
        mock_make_provider.assert_called_once_with(
            auth="/path/to/demo-creds.json",
            auth_host="https://auth.demo.kognic.com",
            token_cache=None,
        )

    @mock.patch("kognic.auth.cli.get_access_token.make_token_provider")
    @mock.patch("kognic.auth.cli.get_access_token.load_kognic_env_config")
    def test_main_with_context_server_override(self, mock_load_config, mock_make_provider):
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
        mock_make_provider.return_value = self._make_provider("override-token")

        with mock.patch("builtins.print"):
            result = main(
                ["get-access-token", "--env", "demo", "--server", "https://custom.server", "--token-cache", "none"]
            )

        self.assertEqual(result, 0)
        mock_make_provider.assert_called_once_with(
            auth="/path/to/demo-creds.json",
            auth_host="https://custom.server",
            token_cache=None,
        )

    def test_main_with_unknown_context(self):
        with mock.patch("kognic.auth.cli.get_access_token.load_kognic_env_config") as mock_load_config:
            from kognic.auth.env_config import KognicEnvConfig

            mock_load_config.return_value = KognicEnvConfig()

            with mock.patch("builtins.print") as mock_print:
                result = main(["get-access-token", "--env", "nonexistent"])

        self.assertEqual(result, 1)
        self.assertIn("nonexistent", mock_print.call_args[0][0])


class CliCacheTest(unittest.TestCase):
    """Tests for token caching in get-access-token."""

    def _make_token(self, access_token="cached-token-abc"):
        return {
            "access_token": access_token,
            "expires_at": time.time() + 3600,
            "expires_in": 3600,
            "token_type": "bearer",
        }

    @mock.patch("kognic.auth.cli.get_access_token.make_token_provider")
    @mock.patch("kognic.auth.cli.get_access_token.make_cache")
    def test_cache_hit_injects_token_into_provider(self, mock_make_cache, mock_make_provider):
        """make_cache is called with 'auto' and its result is passed to make_token_provider."""
        mock_cache = mock.MagicMock()
        mock_make_cache.return_value = mock_cache

        provider = mock.MagicMock()
        provider.ensure_token.return_value = {"access_token": "cached-token-abc"}
        mock_make_provider.return_value = provider

        with mock.patch("builtins.print") as mock_print:
            result = main(["get-access-token"])

        self.assertEqual(result, 0)
        mock_make_cache.assert_called_once_with("auto")
        mock_make_provider.assert_called_once_with(
            auth=mock.ANY,
            auth_host=mock.ANY,
            token_cache=mock_cache,
        )
        mock_print.assert_called_once_with("cached-token-abc")

    @mock.patch("kognic.auth.cli.get_access_token.make_token_provider")
    @mock.patch("kognic.auth.cli.get_access_token.make_cache")
    def test_no_cache_passes_none_to_provider(self, mock_make_cache, mock_make_provider):
        """--token-cache none results in make_cache returning None and provider receiving None."""
        mock_make_cache.return_value = None

        provider = mock.MagicMock()
        provider.ensure_token.return_value = {"access_token": "fresh-token"}
        mock_make_provider.return_value = provider

        with mock.patch("builtins.print"):
            result = main(["get-access-token", "--token-cache", "none"])

        self.assertEqual(result, 0)
        mock_make_cache.assert_called_once_with("none")
        mock_make_provider.assert_called_once_with(
            auth=mock.ANY,
            auth_host=mock.ANY,
            token_cache=None,
        )

    @mock.patch("kognic.auth.cli.get_access_token.make_token_provider")
    @mock.patch("kognic.auth.cli.get_access_token.make_cache")
    def test_cache_mode_forwarded(self, mock_make_cache, mock_make_provider):
        """--token-cache keyring passes 'keyring' to make_cache."""
        mock_make_cache.return_value = mock.MagicMock()
        provider = mock.MagicMock()
        provider.ensure_token.return_value = {"access_token": "t"}
        mock_make_provider.return_value = provider

        with mock.patch("builtins.print"):
            main(["get-access-token", "--token-cache", "keyring"])

        mock_make_cache.assert_called_once_with("keyring")


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

    def test_kog_token_cache_default(self):
        parser = create_kog_parser()
        args = parser.parse_args(["get", "https://app.kognic.com/v1/projects"])
        self.assertEqual(args.token_cache, "auto")

    def test_kog_token_cache_none(self):
        parser = create_kog_parser()
        args = parser.parse_args(["get", "https://app.kognic.com/v1/projects", "--token-cache", "none"])
        self.assertEqual(args.token_cache, "none")


class CallApiTest(unittest.TestCase):
    def _make_parsed(
        self,
        method="get",
        url="https://app.kognic.com/v1/projects",
        data=None,
        headers=None,
        env_config_file_path="/nonexistent/config.json",
        env_name=None,
        token_cache="none",
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
        args.extend(["--token-cache", token_cache])
        return parser.parse_args(args)

    @mock.patch("kognic.auth.cli.api_request.resolve_environment")
    @mock.patch("kognic.auth.cli.api_request.load_kognic_env_config")
    @mock.patch("kognic.auth.cli.api_request.create_session")
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
    @mock.patch("kognic.auth.cli.api_request.create_session")
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
    @mock.patch("kognic.auth.cli.api_request.create_session")
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
    @mock.patch("kognic.auth.cli.api_request.create_session")
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
        self.assertIn("Invalid JSON data", mock_print.call_args[0][0])

    def test_call_api_invalid_header_format(self):
        parsed = self._make_parsed(headers=["BadHeader"])
        with mock.patch("builtins.print") as mock_print:
            result = call_run(parsed)

        self.assertEqual(result, 1)
        self.assertIn("Invalid header format", mock_print.call_args[0][0])

    @mock.patch("kognic.auth.cli.api_request.resolve_environment")
    @mock.patch("kognic.auth.cli.api_request.load_kognic_env_config")
    @mock.patch("kognic.auth.cli.api_request.create_session")
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
    @mock.patch("kognic.auth.cli.api_request.create_session")
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
    @mock.patch("kognic.auth.cli.api_request.create_session")
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
    @mock.patch("kognic.auth.cli.api_request.create_session")
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
    @mock.patch("kognic.auth.cli.api_request.create_session")
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

    @mock.patch("kognic.auth.cli.api_request.resolve_environment")
    @mock.patch("kognic.auth.cli.api_request.load_kognic_env_config")
    @mock.patch("kognic.auth.cli.api_request.create_session")
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
    @mock.patch("kognic.auth.cli.api_request.create_session")
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
    @mock.patch("kognic.auth.cli.api_request.create_session")
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
    @mock.patch("kognic.auth.cli.api_request.create_session")
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
    @mock.patch("kognic.auth.cli.api_request.create_session")
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
    @mock.patch("kognic.auth.cli.api_request.create_session")
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
    @mock.patch("kognic.auth.cli.api_request.create_session")
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
    @mock.patch("kognic.auth.cli.api_request.create_session")
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
    @mock.patch("kognic.auth.cli.api_request.create_session")
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
    @mock.patch("kognic.auth.cli.api_request.create_session")
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
    @mock.patch("kognic.auth.cli.api_request.create_session")
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

        with (
            mock.patch("kognic.auth.cli.api_request.make_token_provider") as mock_make_provider,
            mock.patch("kognic.auth.cli.api_request.create_session") as mock_create_session,
        ):
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

            mock_make_provider.assert_called_once_with(
                auth="/path/to/demo-creds.json",
                auth_host="https://auth.demo.kognic.com",
                token_cache=None,
            )


class KogCacheTest(unittest.TestCase):
    """Tests for token caching in kog command."""

    @mock.patch("kognic.auth.cli.api_request.resolve_environment")
    @mock.patch("kognic.auth.cli.api_request.load_kognic_env_config")
    @mock.patch("kognic.auth.cli.api_request.create_session")
    @mock.patch("kognic.auth.cli.api_request.make_token_provider")
    def test_kog_token_cache_none_forwarded(
        self, mock_make_provider, mock_create_session, mock_load_config, mock_resolve_environment
    ):
        """--token-cache none is forwarded as token_cache=None to make_token_provider."""
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
                "--token-cache",
                "none",
            ]
        )
        with mock.patch("builtins.print"):
            call_run(parsed)

        mock_make_provider.assert_called_once_with(
            auth=None,
            auth_host="https://auth.app.kognic.com",
            token_cache=None,
        )

    @mock.patch("kognic.auth.cli.api_request.resolve_environment")
    @mock.patch("kognic.auth.cli.api_request.load_kognic_env_config")
    @mock.patch("kognic.auth.cli.api_request.make_token_provider")
    @mock.patch("kognic.auth.cli.api_request.make_cache")
    def test_kog_uses_cached_token(
        self, mock_make_cache, mock_make_provider, mock_load_config, mock_resolve_environment
    ):
        """When a cached token is available, it is injected via make_token_provider."""
        mock_load_config.return_value = mock.MagicMock()
        mock_resolve_environment.return_value = Environment(
            name="default",
            host="app.kognic.com",
            auth_server="https://auth.app.kognic.com",
            credentials="/path/to/creds.json",
        )

        mock_cache = mock.MagicMock()
        mock_make_cache.return_value = mock_cache

        mock_provider = mock.MagicMock()
        mock_make_provider.return_value = mock_provider

        mock_session = mock.MagicMock()
        mock_response = mock.MagicMock()
        mock_response.ok = True
        mock_response.headers = {"Content-Type": "application/json"}
        mock_response.json.return_value = {"result": "ok"}
        mock_session.request.return_value = mock_response

        with mock.patch("kognic.auth.cli.api_request.create_session", return_value=mock_session):
            parser = create_kog_parser()
            parsed = parser.parse_args(
                ["get", "https://app.kognic.com/v1/projects", "--env-config-file-path", "/nonexistent/config.json"]
            )
            with mock.patch("builtins.print"):
                result = call_run(parsed)

        self.assertEqual(result, 0)
        mock_make_cache.assert_called_once_with("auto")
        mock_make_provider.assert_called_once_with(
            auth="/path/to/creds.json",
            auth_host="https://auth.app.kognic.com",
            token_cache=mock_cache,
        )


class CredentialsCommandTest(unittest.TestCase):
    def test_put_stores_credentials(self):
        import json
        import tempfile

        creds = {
            "clientId": "test-client-id",
            "clientSecret": "test-secret",
            "email": "test@kognic.com",
            "userId": 1,
            "issuer": "auth.kognic.test",
        }
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(creds, f)
            path = f.name

        try:
            with mock.patch("kognic.auth.cli.credentials.save_credentials") as mock_save:
                result = main(["credentials", "put", path])
            self.assertEqual(result, 0)
            args, kwargs = mock_save.call_args
            self.assertEqual(args[0].client_id, "test-client-id")
            self.assertEqual(args[0].client_secret, "test-secret")
            self.assertEqual(args[1], "default")
        finally:
            Path(path).unlink()

    def test_put_custom_profile(self):
        import json
        import tempfile

        creds = {
            "clientId": "id",
            "clientSecret": "secret",
            "email": "e@kognic.com",
            "userId": 1,
            "issuer": "issuer",
        }
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(creds, f)
            path = f.name

        try:
            with mock.patch("kognic.auth.cli.credentials.save_credentials") as mock_save:
                result = main(["credentials", "put", path, "--env", "demo"])
            self.assertEqual(result, 0)
            args, kwargs = mock_save.call_args
            self.assertEqual(args[0].client_id, "id")
            self.assertEqual(args[0].client_secret, "secret")
            self.assertEqual(args[1], "demo")
        finally:
            Path(path).unlink()

    def test_put_missing_file_returns_error(self):
        result = main(["credentials", "put", "/nonexistent/creds.json"])
        self.assertEqual(result, 1)

    def test_get_returns_credentials(self):
        from kognic.auth.credentials_parser import ApiCredentials

        fake_creds = ApiCredentials(
            client_id="my-id",
            client_secret="my-secret",
            email="user@kognic.com",
            user_id=42,
            issuer="auth.kognic.com",
        )
        with mock.patch("kognic.auth.cli.credentials.load_credentials", return_value=fake_creds):
            with mock.patch("builtins.print") as mock_print:
                result = main(["credentials", "get"])
        self.assertEqual(result, 0)
        output = json.loads(mock_print.call_args[0][0])
        self.assertEqual(output["clientId"], "my-id")
        self.assertEqual(output["clientSecret"], "my-secret")
        self.assertEqual(output["email"], "user@kognic.com")
        self.assertEqual(output["userId"], 42)
        self.assertEqual(output["issuer"], "auth.kognic.com")

    def test_get_custom_profile(self):
        from kognic.auth.credentials_parser import ApiCredentials

        fake_creds = ApiCredentials(
            client_id="demo-id",
            client_secret="demo-secret",
            email="demo@kognic.com",
            user_id=1,
            issuer="auth.kognic.com",
        )
        with mock.patch("kognic.auth.cli.credentials.load_credentials", return_value=fake_creds) as mock_load:
            result = main(["credentials", "get", "--env", "demo"])
        self.assertEqual(result, 0)
        mock_load.assert_called_once_with("demo")

    def test_get_not_found_returns_error(self):
        with mock.patch("kognic.auth.cli.credentials.load_credentials", return_value=None):
            result = main(["credentials", "get"])
        self.assertEqual(result, 1)

    def test_delete_removes_credentials(self):
        with mock.patch("kognic.auth.cli.credentials.clear_credentials") as mock_clear:
            result = main(["credentials", "delete"])
        self.assertEqual(result, 0)
        mock_clear.assert_called_once_with("default")

    def test_delete_custom_profile(self):
        with mock.patch("kognic.auth.cli.credentials.clear_credentials") as mock_clear:
            result = main(["credentials", "delete", "--env", "demo"])
        self.assertEqual(result, 0)
        mock_clear.assert_called_once_with("demo")

    def test_no_subcommand_prints_help(self):
        with mock.patch("builtins.print"):
            result = main(["credentials"])
        self.assertEqual(result, 0)


if __name__ == "__main__":
    unittest.main()
