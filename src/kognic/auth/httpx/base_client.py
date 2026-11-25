"""Base async API client V2 using httpx/OAuth2 client."""

from __future__ import annotations

import asyncio
import logging
import os
from collections.abc import Mapping
from contextvars import ContextVar
from typing import TYPE_CHECKING, Any, Callable, List, Optional, Union

from kognic.auth.credentials_parser import ANY_AUTH_TYPE

if TYPE_CHECKING:
    from typing import Self

import httpx

from kognic.auth import (
    DEFAULT_HOST,
    DEFAULT_TOKEN_ENDPOINT_RELPATH,
    MAX_RETRIES,
    RETRY_STATUS_CODES,
    RETRYABLE_METHODS,
    retry_delay,
)
from kognic.auth._sunset import SunsetHandler, default_sunset_handler, handle_sunset
from kognic.auth._user_agent import get_user_agent
from kognic.auth.env_config import DEFAULT_ENV_CONFIG_FILE_PATH, load_kognic_env_config
from kognic.auth.httpx.async_client import HttpxAuthAsyncClient
from kognic.auth.serde import serialize_body

logger = logging.getLogger(__name__)

_DEFAULT_SUNSET_HANDLER: SunsetHandler = default_sunset_handler()


# The request wrappers with a call in progress in the current task.
_calls_in_progress: ContextVar[frozenset] = ContextVar("kognic_auth_calls_in_progress", default=frozenset())


def _has_replayable_body(kwargs: dict) -> bool:
    """Whether the body of a request can be sent again in full. JSON always can.

    httpx sends a ``data`` value that is not a mapping as raw content, so it counts as a body.
    """
    content = kwargs.get("content")
    data = kwargs.get("data")
    return (
        (content is None or isinstance(content, (bytes, str)))
        and (data is None or isinstance(data, Mapping))
        and not kwargs.get("files")
    )


def _handle_http_error(resp: httpx.Response):
    """Try to get the error message from the response and raise with that message."""
    try:
        resp.raise_for_status()
    except httpx.HTTPStatusError as e:
        try:
            js = resp.json()
            err_message = js.get("message", js)
        except ValueError:
            err_message = resp.text
        full_msg = (
            f"Got HttpError with status={resp.status_code} in call to {resp.url}.\n"
            f"Got error in response: '{err_message}'"
        )
        raise httpx.HTTPStatusError(full_msg, request=resp.request, response=resp) from e


class BaseAsyncApiClient(HttpxAuthAsyncClient):
    """Base async API client with OAuth2 authentication using httpx.

    Extends HttpxAuthAsyncClient with:
    - Automatic JSON serialization
    - Retry logic for transient errors (502, 503, 504) on idempotent methods only; POST and
      PATCH surface the first failure so the caller decides whether repeating is safe
    - Cut-off retry: a response whose connection closes or resets before the body is complete
      (``httpx.RemoteProtocolError`` or ``httpx.ReadError``) is retried for idempotent methods
      and the token request. Only the outermost request call retries it, so a token refresh
      inside an API call is replayed as part of the whole request. Read timeouts are not retried.
    - One budget: status retries and cut-off retries share a count, for at most 4 attempts per
      call, waiting 0s, 1s and 2s between them. The last error or response reaches the caller.
    - Only a replayable body is sent again: ``json``, ``content`` that is bytes or str, ``data``
      that is a mapping, and no ``files``. With any other body there is no retry of any kind.
      Requests made with ``stream()`` are not retried.
    - Sunset header handling
    - Enhanced error messages

    The interface is consistent with httpx - use the underlying client methods.
    Calls return the response object. Use response.json() to get the data.

    Example:
        async with BaseAsyncApiClient() as client:
            session = await client.session
            response = await session.get("https://api.app.kognic.com/v1/resources")
            data = response.json()
    """

    def __init__(
        self,
        *,
        auth: ANY_AUTH_TYPE = None,
        auth_host: str = DEFAULT_HOST,
        auth_token_endpoint: str = DEFAULT_TOKEN_ENDPOINT_RELPATH,
        client_name: Optional[str] = "auto",
        json_serializer: Callable[[Any], Any] = serialize_body,
        sunset_handler: Optional[SunsetHandler] = _DEFAULT_SUNSET_HANDLER,
        scopes: Optional[List[str]] = None,
        **kwargs,
    ):
        """Initialize the async API client.

        Args:
            auth: Authentication credentials - path to credentials file or (client_id, client_secret) tuple
            auth_host: Authentication server base URL
            auth_token_endpoint: Relative path to token endpoint
            client_name: Name added to User-Agent. Use "auto" for class name, None for no name.
            json_serializer: Callable to serialize request bodies. Defaults to serialize_body.
            sunset_handler: Callable invoked with ``(sunset_date, method, url)`` when a sunset header
                is detected. Defaults to logging a warning or error. Pass ``None`` to disable.
            scopes: OAuth2 scopes to request, e.g. ["api:read", "api:write"].
            **kwargs: Additional arguments passed to the underlying httpx client (e.g. timeout, verify).
        """
        if client_name == "auto":
            client_name = self.__class__.__name__

        # Use a custom transport to set the number of retries for connection errors
        kwargs.setdefault("transport", httpx.AsyncHTTPTransport(retries=MAX_RETRIES))

        headers = kwargs.pop("headers", {})
        headers.setdefault("User-Agent", get_user_agent(f"python-httpx/{httpx.__version__}", client_name))

        super().__init__(
            auth=auth,
            host=auth_host,
            token_endpoint=auth_token_endpoint,
            scopes=scopes,
            headers=headers,
            **kwargs,
        )

        # Monkey patch the request method to handle sunset, errors and custom error handling
        client_request = self._oauth_client.request
        token_url = self.token_url

        async def request(method, url, **kwargs):
            if isinstance(url, str) and url.startswith("/"):
                raise ValueError(f"Path must not start with /, got {url}")

            # Accept anything jsonable as json, serialize it
            json = kwargs.pop("json", None)
            if json is not None:
                kwargs["json"] = json_serializer(json)

            method_is_retryable = method.upper() in RETRYABLE_METHODS or str(url) == token_url
            retries = MAX_RETRIES if method_is_retryable and _has_replayable_body(kwargs) else 0

            # A token refresh inside an API call comes back through this wrapper. Only the
            # outermost call retries a cut-off response, replaying the whole request.
            active = _calls_in_progress.get()
            outermost = request not in active
            outer_calls = _calls_in_progress.set(active | {request})
            try:
                for retry_number in range(1, retries + 1):
                    try:
                        resp = await client_request(method, url, **kwargs)
                    except (httpx.RemoteProtocolError, httpx.ReadError) as e:
                        if not outermost:
                            raise
                        reason = f"Cut-off response ({e})"
                    else:
                        if resp.status_code not in RETRY_STATUS_CODES:
                            break
                        reason = f"Server {resp.status_code} error"
                    delay = retry_delay(retry_number)
                    logger.warning(f"{reason} for request to url={url}\nRetrying in {delay}s...")
                    await asyncio.sleep(delay)
                else:
                    resp = await client_request(method, url, **kwargs)
            finally:
                _calls_in_progress.reset(outer_calls)

            handle_sunset(resp, sunset_handler)
            _handle_http_error(resp)
            return resp

        self._oauth_client.request = request

    async def __aenter__(self) -> Self:
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Async context manager exit."""
        await self.close()

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
            Configured BaseAsyncApiClient instance.
        """
        config_file_path = env_config_path or DEFAULT_ENV_CONFIG_FILE_PATH
        cfg = load_kognic_env_config(config_file_path)
        if env not in cfg.environments:
            raise ValueError(f"Unknown environment: {env} not found in config at {config_file_path}")
        resolved = cfg.environments[env]
        kwargs.setdefault("auth", resolved.credentials)
        kwargs["auth_host"] = resolved.auth_server
        if resolved.scopes and "scopes" not in kwargs:
            kwargs["scopes"] = resolved.scopes
        return cls(**kwargs)
