"""Protocol definitions for URL, Request, and Response types."""

from typing import Any, Mapping, Optional, Protocol, Union, runtime_checkable


@runtime_checkable
class Url(Protocol):
    """Protocol for URL objects (httpx URL)."""

    @property
    def scheme(self) -> str: ...

    @property
    def host(self) -> str: ...

    @property
    def path(self) -> str: ...


@runtime_checkable
class Request(Protocol):
    """Protocol for HTTP request objects."""

    @property
    def method(self) -> Optional[str]: ...

    @property
    def url(self) -> Union[str, Url, None]: ...


@runtime_checkable
class Response(Protocol):
    """Protocol for HTTP response objects."""

    @property
    def headers(self) -> Mapping[str, str]: ...

    @property
    def request(self) -> Request: ...

    def json(self) -> Any: ...


class SupportsStatusCode(Protocol):
    """Protocol for anything carrying an HTTP status code."""

    @property
    def status_code(self) -> int: ...
