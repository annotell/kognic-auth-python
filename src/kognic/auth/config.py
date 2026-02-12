import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

from kognic.auth import DEFAULT_HOST

DEFAULT_CONFIG_PATH = str(Path("~") / ".config" / "kognic" / "config.json")


@dataclass
class Context:
    name: str
    host: str
    auth_server: str
    credentials: Optional[str] = None


@dataclass
class Config:
    contexts: dict = field(default_factory=dict)
    default_context: Optional[str] = None


def load_config(path: str = DEFAULT_CONFIG_PATH) -> Config:
    """Load config from JSON file. Returns empty Config if file doesn't exist."""
    expanded = Path(path).expanduser()
    if not expanded.exists():
        return Config()

    data = json.loads(expanded.read_text())

    contexts = {}
    for name, ctx_data in data.get("contexts", {}).items():
        credentials = ctx_data.get("credentials")
        if credentials:
            credentials = str(Path(credentials).expanduser())
        contexts[name] = Context(
            name=name,
            host=ctx_data["host"],
            auth_server=ctx_data["auth_server"],
            credentials=credentials,
        )

    return Config(
        contexts=contexts,
        default_context=data.get("default_context"),
    )


def resolve_context(config: Config, url: str, context_name: Optional[str] = None) -> Context:
    """Resolve which context to use for a given URL.

    Resolution order:
    1. Explicit context_name (--context flag)
    2. Exact host match from URL
    3. Subdomain suffix match from URL
    4. default_context from config
    5. Fallback to default auth server with no credentials file
    """
    # Explicit context name
    if context_name:
        if context_name not in config.contexts:
            raise ValueError(f"Unknown context: {context_name}")
        return config.contexts[context_name]

    # Domain matching
    parsed = urlparse(url)
    hostname = parsed.hostname or ""

    # Exact match
    for ctx in config.contexts.values():
        if hostname == ctx.host:
            return ctx

    # Subdomain suffix match
    for ctx in config.contexts.values():
        if hostname.endswith("." + ctx.host):
            return ctx

    # Default context fallback
    if config.default_context and config.default_context in config.contexts:
        return config.contexts[config.default_context]

    # No config at all — use default auth server with env var credentials
    return Context(
        name="default",
        host="app.kognic.com",
        auth_server=DEFAULT_HOST,
        credentials=None,
    )
