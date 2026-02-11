"""Base async API client V2 using httpx/OAuth2 client."""

import asyncio
import logging
from typing import Any, Callable, Optional, Union

import httpx

from kognic.auth import DEFAULT_HOST, DEFAULT_TOKEN_ENDPOINT_RELPATH
from kognic.auth._sunset import handle_sunset
from kognic.auth._user_agent import get_user_agent
from kognic.auth.httpx.async_client import HttpxAuthAsyncClient
from kognic.auth.serde import serialize_body

logger = logging.getLogger(__name__)


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
    - Retry logic for transient errors (502, 503, 504)
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
        auth: Optional[Union[str, tuple]] = None,
        client_id: Optional[str] = None,
        client_secret: Optional[str] = None,
        auth_host: str = DEFAULT_HOST,
        token_endpoint: str = DEFAULT_TOKEN_ENDPOINT_RELPATH,
        client_name: Optional[str] = "auto",
        json_serializer: Callable[[Any], Any] = serialize_body,
    ):
        """Initialize the async API client.

        Args:
            auth: Authentication credentials - path to credentials file or (client_id, client_secret) tuple
            client_id: OAuth2 client ID (alternative to auth)
            client_secret: OAuth2 client secret (alternative to auth)
            auth_host: Authentication server base URL
            token_endpoint: Relative path to token endpoint
            client_name: Name added to User-Agent. Use "auto" for class name, None for no name.
            json_serializer: Callable to serialize request bodies. Defaults to serialize_body.
        """
        if client_name == "auto":
            client_name = self.__class__.__name__

        # Use a custom transport to set the number of retries for connection errors
        transport = httpx.AsyncHTTPTransport(retries=3)

        headers = {"User-Agent": get_user_agent(f"python-httpx/{httpx.__version__}", client_name)}

        super().__init__(
            auth=auth,
            client_id=client_id,
            client_secret=client_secret,
            host=auth_host,
            token_endpoint=token_endpoint,
            transport=transport,
            headers=headers,
        )

        # Monkey patch the request method to handle sunset, errors and custom error handling
        client_request = self._oauth_client.request

        async def request(method, url, **kwargs):
            # Accept anything jsonable as json, serialize it
            json = kwargs.pop("json", None)
            if json is not None:
                kwargs["json"] = json_serializer(json)

            # Wrap the request in simple retry logic for transient errors
            async def call_with_simple_retry(attempts):
                resp = await client_request(method, url, **kwargs)
                if attempts == 0:
                    return resp
                if resp.status_code in (502, 503, 504):
                    logger.warning(f"Server {resp.status_code} error for request to url={url}\nRetrying in 5s...")
                    await asyncio.sleep(5)
                    return await call_with_simple_retry(attempts - 1)
                return resp

            resp = await call_with_simple_retry(3)

            handle_sunset(resp)
            _handle_http_error(resp)
            return resp

        self._oauth_client.request = request

    async def __aenter__(self) -> "BaseAsyncApiClient":
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Async context manager exit."""
        await self.close()
