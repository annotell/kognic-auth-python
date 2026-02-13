"""Protocol definitions for URL, Request, and Response types."""

from typing import Dict, Protocol, Union, runtime_checkable


@runtime_checkable
class Url(Protocol):
    """Protocol for URL objects (httpx URL)."""

    scheme: str
    host: str
    path: str


@runtime_checkable
class Request(Protocol):
    """Protocol for HTTP request objects."""

    method: str
    url: Union[str, Url]


@runtime_checkable
class Response(Protocol):
    """Protocol for HTTP response objects."""

    headers: Dict[str, str]
    request: Request

    def json(self) -> dict:
        raise NotImplementedError
