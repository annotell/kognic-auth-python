"""Base API client V2 using requests/OAuth2 session."""

from __future__ import annotations

import logging
import os
import threading
from threading import Lock
from typing import TYPE_CHECKING, Any, Callable, Optional, Union
from weakref import WeakValueDictionary

if TYPE_CHECKING:
    from typing import Self

import requests
from requests import Session
from requests.adapters import HTTPAdapter, Retry

from kognic.auth import DEFAULT_HOST, DEFAULT_TOKEN_ENDPOINT_RELPATH
from kognic.auth._sunset import handle_sunset
from kognic.auth._user_agent import get_user_agent
from kognic.auth.credentials_parser import resolve_credentials
from kognic.auth.env_config import DEFAULT_ENV_CONFIG_FILE_PATH, load_kognic_env_config
from kognic.auth.requests.auth_session import RequestsAuthSession
from kognic.auth.requests.bearer_auth import KognicBearerAuth
from kognic.auth.serde import serialize_body

logger = logging.getLogger(__name__)


DEFAULT_RETRY = Retry(total=3, connect=3, read=3, backoff_factor=0.5, status_forcelist=[502, 503, 504])


def _check_response(resp: requests.Response):
    """Handle sunset headers and raise for status with enhanced error messages."""
    handle_sunset(resp)
    try:
        resp.raise_for_status()
    except requests.HTTPError as e:
        try:
            js = resp.json()
            err_message = js.get("message", js)
        except ValueError:
            err_message = resp.text
        raise requests.HTTPError(
            f"Got HttpError with status={resp.status_code} in call to {resp.url}.\n"
            f"Got error in response: '{err_message}'",
            response=resp,
            request=resp.request,
        ) from e


def _set_session_user_agent(session: Session, client_name: Optional[str] = None):
    """Set the User-Agent header for the session, including the client name if provided."""
    session.headers["User-Agent"] = get_user_agent(f"requests/{requests.__version__}", client_name)


def _monkey_patch_send(session: Session, json_serializer: Callable[[Any], Any]):
    """
    Monkey patch to serialize JSON and validate paths
    :param session:
    :param json_serializer:
    :return:
    """
    vanilla_prep = session.prepare_request

    def prepare_request(req, *args, **kwargs):
        if req.url.startswith("/"):
            raise ValueError(f"Path must not start with /, got {req.url}")

        # Accept anything jsonable as json, serialize it
        if req.json is not None:
            req.json = json_serializer(req.json)

        return vanilla_prep(req, *args, **kwargs)

    session.prepare_request = prepare_request

    # Monkey patch to always raise for status and handle errors
    vanilla_send = session.send

    def send_request(req, *args, **kwargs):
        resp = vanilla_send(req, *args, **kwargs)
        _check_response(resp)
        return resp

    session.send = send_request


def create_session(
    *,
    auth: Optional[Union[str, os.PathLike, tuple]] = None,
    auth_host: str = DEFAULT_HOST,
    auth_token_endpoint: str = DEFAULT_TOKEN_ENDPOINT_RELPATH,
    client_name: Optional[str] = None,
    json_serializer: Callable[[Any], Any] = serialize_body,
    initial_token: Optional[dict] = None,
    on_token_updated: Optional[Callable[[dict], None]] = None,
    token_provider: Optional[RequestsAuthSession] = None,
) -> Session:
    """Create a requests session with enhancements.

    - OAuth2 authentication with automatic token refresh
    - Automatic JSON serialization for jsonable objects
    - Default retry logic for transient errors
    - Sunset header handling
    - Always call raise_for_status with enhanced error messages

    Args:
        auth: Authentication credentials - path to credentials file or (client_id, client_secret) tuple
        auth_host: Authentication server base URL
        auth_token_endpoint: Relative path to token endpoint
        client_name: Name added to User-Agent header
        json_serializer: Callable to serialize request bodies. Defaults to serialize_body.
        initial_token: Pre-fetched token dict to inject, skipping the initial network fetch if valid.
        on_token_updated: Callback invoked with the new token dict whenever a fresh token is fetched.
        token_provider: Explicit token provider to use. When given, auth/initial_token/on_token_updated
            are ignored. Multiple sessions sharing one provider share the same token lifecycle.

    Returns:
        Configured requests Session
    """
    if token_provider is None:
        token_provider = RequestsAuthSession(
            auth=auth,
            host=auth_host,
            token_endpoint=auth_token_endpoint,
            initial_token=initial_token,
            on_token_updated=on_token_updated,
        )

    session = requests.Session()
    session.auth = KognicBearerAuth(token_provider)
    _set_session_user_agent(session, client_name)
    _monkey_patch_send(session, json_serializer)
    session.mount("http://", HTTPAdapter(max_retries=DEFAULT_RETRY))
    session.mount("https://", HTTPAdapter(max_retries=DEFAULT_RETRY))
    return session


_provider_pool: WeakValueDictionary[tuple, RequestsAuthSession] = WeakValueDictionary()
_provider_pool_lock = threading.Lock()


def _get_shared_provider(
    auth: Optional[Union[str, os.PathLike, tuple]],
    auth_host: str,
    auth_token_endpoint: str,
) -> RequestsAuthSession:
    """Return a shared RequestsAuthSession for the given credentials, creating one if needed.

    Providers are keyed by (client_id, auth_host, auth_token_endpoint) and held weakly,
    so they are GC'd once no BaseApiClient instances reference them.
    """
    try:
        client_id, client_secret = resolve_credentials(auth)
    except Exception:
        client_id, client_secret = None, None

    if not client_id or not client_secret:
        return RequestsAuthSession(auth=auth, host=auth_host, token_endpoint=auth_token_endpoint)

    key = (client_id, auth_host, auth_token_endpoint)
    with _provider_pool_lock:
        provider = _provider_pool.get(key)
        if provider is None:
            provider = RequestsAuthSession(
                auth=(client_id, client_secret),
                host=auth_host,
                token_endpoint=auth_token_endpoint,
            )
            _provider_pool[key] = provider
    return provider


class BaseApiClient:
    """Base API client with OAuth2 authentication using requests.

    Provides a requests Session with:
    - OAuth2 authentication with automatic token refresh
    - Automatic JSON serialization
    - Retry logic for transient errors (502, 503, 504)
    - Sunset header handling
    - Enhanced error messages

    Clients with the same credentials and auth host automatically share a token provider,
    so only one token fetch occurs across all instances with those credentials.

    The interface is consistent with requests - use session.get(), session.post(), etc.
    Calls return the response object. Use response.json() to get the data.

    Example:
        client = BaseApiClient()
        response = client.session.get("https://api.app.kognic.com/v1/resources")
        data = response.json()
    """

    def __init__(
        self,
        *,
        auth: Optional[Union[str, os.PathLike, tuple]] = None,
        auth_host: str = DEFAULT_HOST,
        auth_token_endpoint: str = DEFAULT_TOKEN_ENDPOINT_RELPATH,
        client_name: Optional[str] = "auto",
        json_serializer: Callable[[Any], Any] = serialize_body,
        token_provider: Optional[RequestsAuthSession] = None,
    ):
        """Initialize the API client.

        Args:
            auth: Authentication credentials - path to credentials file or (client_id, client_secret) tuple
            auth_host: Authentication server base URL
            auth_token_endpoint: Relative path to token endpoint
            client_name: Name added to User-Agent. Use "auto" for class name, None for no name.
            json_serializer: Callable to serialize request bodies. Defaults to serialize_body.
            token_provider: Explicit token provider to share across clients. When omitted, a shared
                provider is looked up (or created) by credentials + auth_host.
        """
        self._session: Optional[Session] = None
        self._auth = auth
        self._auth_host = auth_host
        self._auth_token_endpoint = auth_token_endpoint
        self._json_serializer = json_serializer
        self._token_provider = token_provider
        self._lock = Lock()

        if client_name == "auto":
            client_name = self.__class__.__name__
        self._client_name = client_name

    @property
    def session(self) -> Session:
        """Get the authenticated requests Session.

        Session is lazily initialized on first access.
        """
        if self._session is None:
            with self._lock:
                if self._session is None:
                    provider = self._token_provider or _get_shared_provider(
                        self._auth, self._auth_host, self._auth_token_endpoint
                    )
                    self._session = create_session(
                        token_provider=provider,
                        client_name=self._client_name,
                        json_serializer=self._json_serializer,
                    )
        return self._session

    @classmethod
    def from_env(
        cls,
        env: str,
        *,
        env_config_path: Union[str, os.PathLike] = "",
        **kwargs,
    ) -> Self:
        """Create a client from a named environment in the config file.

        Args:
            env: Environment name to look up in the config file.
            env_config_path: Path to config file. Defaults to ~/.config/kognic/environments.json.
            **kwargs: Additional arguments passed to the constructor (e.g. client_name, json_serializer).

        Returns:
            Configured BaseApiClient instance.
        """

        config_file_path = env_config_path or DEFAULT_ENV_CONFIG_FILE_PATH
        cfg = load_kognic_env_config(config_file_path)
        if env not in cfg.environments:
            raise ValueError(f"Unknown environment: {env} not found in config at {config_file_path}")
        resolved = cfg.environments[env]
        kwargs.setdefault("auth", resolved.credentials)
        kwargs["auth_host"] = resolved.auth_server
        return cls(**kwargs)
