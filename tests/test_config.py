import json
import tempfile
import unittest
from pathlib import Path

from kognic.auth import DEFAULT_HOST
from kognic.auth.config import Config, Context, load_config, resolve_context


class LoadConfigTest(unittest.TestCase):
    def test_missing_file_returns_empty_config(self):
        config = load_config("/nonexistent/path/config.json")
        self.assertEqual(config.contexts, {})
        self.assertIsNone(config.default_context)

    def test_valid_config(self):
        data = {
            "contexts": {
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
            "default_context": "production",
        }
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(data, f)
            f.flush()
            config = load_config(f.name)

        Path(f.name).unlink()

        self.assertEqual(len(config.contexts), 2)
        self.assertEqual(config.default_context, "production")

        prod = config.contexts["production"]
        self.assertEqual(prod.name, "production")
        self.assertEqual(prod.host, "app.kognic.com")
        self.assertEqual(prod.auth_server, "https://auth.app.kognic.com")
        self.assertTrue(prod.credentials.endswith("creds.json"))
        self.assertNotIn("~", prod.credentials)

        demo = config.contexts["demo"]
        self.assertIsNone(demo.credentials)

    def test_invalid_json_raises(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            f.write("not valid json{")
            f.flush()
            with self.assertRaises(json.JSONDecodeError):
                load_config(f.name)
        Path(f.name).unlink()

    def test_empty_contexts(self):
        data = {"contexts": {}}
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(data, f)
            f.flush()
            config = load_config(f.name)
        Path(f.name).unlink()

        self.assertEqual(config.contexts, {})
        self.assertIsNone(config.default_context)


class ResolveContextTest(unittest.TestCase):
    def setUp(self):
        self.config = Config(
            contexts={
                "production": Context(
                    name="production",
                    host="app.kognic.com",
                    auth_server="https://auth.app.kognic.com",
                    credentials="/path/to/prod-creds.json",
                ),
                "demo": Context(
                    name="demo",
                    host="demo.kognic.com",
                    auth_server="https://auth.demo.kognic.com",
                    credentials="/path/to/demo-creds.json",
                ),
            },
            default_context="production",
        )

    def test_explicit_context(self):
        ctx = resolve_context(self.config, "https://anything.com/v1/foo", "demo")
        self.assertEqual(ctx.name, "demo")

    def test_explicit_context_unknown_raises(self):
        with self.assertRaises(ValueError) as cm:
            resolve_context(self.config, "https://anything.com", "nonexistent")
        self.assertIn("Unknown context", str(cm.exception))

    def test_exact_host_match(self):
        ctx = resolve_context(self.config, "https://app.kognic.com/v1/projects")
        self.assertEqual(ctx.name, "production")

    def test_subdomain_match(self):
        ctx = resolve_context(self.config, "https://api.app.kognic.com/v1/projects")
        self.assertEqual(ctx.name, "production")

    def test_demo_exact_match(self):
        ctx = resolve_context(self.config, "https://demo.kognic.com/v1/projects")
        self.assertEqual(ctx.name, "demo")

    def test_demo_subdomain_match(self):
        ctx = resolve_context(self.config, "https://api.demo.kognic.com/v1/projects")
        self.assertEqual(ctx.name, "demo")

    def test_default_context_fallback(self):
        ctx = resolve_context(self.config, "https://unknown.example.com/v1/foo")
        self.assertEqual(ctx.name, "production")

    def test_no_config_fallback(self):
        empty_config = Config()
        ctx = resolve_context(empty_config, "https://app.kognic.com/v1/projects")
        self.assertEqual(ctx.name, "default")
        self.assertEqual(ctx.auth_server, DEFAULT_HOST)
        self.assertIsNone(ctx.credentials)

    def test_no_default_no_match_falls_back_to_default_auth(self):
        config = Config(
            contexts={
                "demo": Context(
                    name="demo",
                    host="demo.kognic.com",
                    auth_server="https://auth.demo.kognic.com",
                ),
            },
            default_context=None,
        )
        ctx = resolve_context(config, "https://unknown.example.com/v1/foo")
        self.assertEqual(ctx.name, "default")
        self.assertEqual(ctx.auth_server, DEFAULT_HOST)


if __name__ == "__main__":
    unittest.main()
