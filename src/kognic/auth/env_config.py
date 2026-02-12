import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

from kognic.auth import DEFAULT_HOST

DEFAULT_ENV_CONFIG_FILE_PATH = str(Path("~") / ".config" / "kognic" / "config.json")


@dataclass
class Environment:
    name: str
    host: str
    auth_server: str
    credentials: Optional[str] = None


@dataclass
class KognicEnvConfig:
    environments: dict = field(default_factory=dict)
    default_environment: Optional[str] = None


def load_kognic_env_config(path: str = DEFAULT_ENV_CONFIG_FILE_PATH) -> KognicEnvConfig:
    """Load config from JSON file. Returns empty Config if file doesn't exist."""
    expanded = Path(path).expanduser()
    if not expanded.exists():
        return KognicEnvConfig()

    data = json.loads(expanded.read_text())

    environments = {}
    for name, env_data in data.get("environments", {}).items():
        credentials = env_data.get("credentials")
        if credentials:
            credentials = str(Path(credentials).expanduser())
        environments[name] = Environment(
            name=name,
            host=env_data["host"],
            auth_server=env_data["auth_server"],
            credentials=credentials,
        )

    return KognicEnvConfig(
        environments=environments,
        default_environment=data.get("default_environment"),
    )


def resolve_environment(config: KognicEnvConfig, url: str, env_name: Optional[str] = None) -> Environment:
    """Resolve which environment to use for a given URL.

    Resolution order:
    1. Explicit env_name (--env flag)
    2. Exact host match from URL
    3. Subdomain suffix match from URL
    4. default_environment from config
    5. Fallback to default auth server with no credentials file
    """
    # Explicit env name
    if env_name:
        if env_name not in config.environments:
            raise ValueError(f"Unknown environment: {env_name}")
        return config.environments[env_name]

    # Domain matching
    parsed = urlparse(url)
    hostname = parsed.hostname or ""

    # Exact match
    for env in config.environments.values():
        if hostname == env.host:
            return env

    # Subdomain suffix match
    for env in config.environments.values():
        if hostname.endswith("." + env.host):
            return env

    # Default environment fallback
    if config.default_environment and config.default_environment in config.environments:
        return config.environments[config.default_environment]

    # No config at all — use default auth server with env var credentials
    return Environment(
        name="default",
        host="app.kognic.com",
        auth_server=DEFAULT_HOST,
        credentials=None,
    )
