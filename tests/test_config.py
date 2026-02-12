import json
import tempfile
import unittest
from pathlib import Path

from kognic.auth import DEFAULT_HOST
from kognic.auth.env_config import Environment, KognicEnvConfig, load_kognic_env_config, resolve_environment


class LoadConfigTest(unittest.TestCase):
    def test_missing_file_returns_empty_config(self):
        config = load_kognic_env_config("/nonexistent/path/config.json")
        self.assertEqual(config.environments, {})
        self.assertIsNone(config.default_environment)

    def test_valid_config(self):
        data = {
            "environments": {
                "production": {
                    "host": "app.kognic.com",
                    "auth_server": "https://auth.app.kognic.com",
                    "credentials": "~/creds.json",
                },
                "demo": {
                    "host": "demo.kognic.com",
                    "auth_server": "https://auth.demo.kognic.com",
                },
            },
            "default_environment": "production",
        }
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(data, f)
            f.flush()
            config = load_kognic_env_config(f.name)

        Path(f.name).unlink()

        self.assertEqual(len(config.environments), 2)
        self.assertEqual(config.default_environment, "production")

        prod = config.environments["production"]
        self.assertEqual(prod.name, "production")
        self.assertEqual(prod.host, "app.kognic.com")
        self.assertEqual(prod.auth_server, "https://auth.app.kognic.com")
        self.assertTrue(prod.credentials.endswith("creds.json"))
        self.assertNotIn("~", prod.credentials)

        demo = config.environments["demo"]
        self.assertIsNone(demo.credentials)

    def test_invalid_json_raises(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            f.write("not valid json{")
            f.flush()
            with self.assertRaises(json.JSONDecodeError):
                load_kognic_env_config(f.name)
        Path(f.name).unlink()

    def test_empty_contexts(self):
        data = {"environments": {}}
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(data, f)
            f.flush()
            config = load_kognic_env_config(f.name)
        Path(f.name).unlink()

        self.assertEqual(config.environments, {})
        self.assertIsNone(config.default_environment)


class ResolveEnvironmentTest(unittest.TestCase):
    def setUp(self):
        self.config = KognicEnvConfig(
            environments={
                "production": Environment(
                    name="production",
                    host="app.kognic.com",
                    auth_server="https://auth.app.kognic.com",
                    credentials="/path/to/prod-creds.json",
                ),
                "demo": Environment(
                    name="demo",
                    host="demo.kognic.com",
                    auth_server="https://auth.demo.kognic.com",
                    credentials="/path/to/demo-creds.json",
                ),
            },
            default_environment="production",
        )

    def test_explicit_env(self):
        env = resolve_environment(self.config, "https://anything.com/v1/foo", "demo")
        self.assertEqual(env.name, "demo")

    def test_explicit_env_unknown_raises(self):
        with self.assertRaises(ValueError) as cm:
            resolve_environment(self.config, "https://anything.com", "nonexistent")
        self.assertIn("Unknown environment", str(cm.exception))

    def test_exact_host_match(self):
        env = resolve_environment(self.config, "https://app.kognic.com/v1/projects")
        self.assertEqual(env.name, "production")

    def test_subdomain_match(self):
        env = resolve_environment(self.config, "https://api.app.kognic.com/v1/projects")
        self.assertEqual(env.name, "production")

    def test_demo_exact_match(self):
        env = resolve_environment(self.config, "https://demo.kognic.com/v1/projects")
        self.assertEqual(env.name, "demo")

    def test_demo_subdomain_match(self):
        env = resolve_environment(self.config, "https://api.demo.kognic.com/v1/projects")
        self.assertEqual(env.name, "demo")

    def test_default_environment_fallback(self):
        env = resolve_environment(self.config, "https://unknown.example.com/v1/foo")
        self.assertEqual(env.name, "production")

    def test_no_config_fallback(self):
        empty_config = KognicEnvConfig()
        env = resolve_environment(empty_config, "https://app.kognic.com/v1/projects")
        self.assertEqual(env.name, "default")
        self.assertEqual(env.auth_server, DEFAULT_HOST)
        self.assertIsNone(env.credentials)

    def test_no_default_no_match_falls_back_to_default_auth(self):
        config = KognicEnvConfig(
            environments={
                "demo": Environment(
                    name="demo",
                    host="demo.kognic.com",
                    auth_server="https://auth.demo.kognic.com",
                ),
            },
            default_environment=None,
        )
        env = resolve_environment(config, "https://unknown.example.com/v1/foo")
        self.assertEqual(env.name, "default")
        self.assertEqual(env.auth_server, DEFAULT_HOST)


if __name__ == "__main__":
    unittest.main()
