"""Protocol definitions for URL, Request, Response and CLI subparser types."""

import argparse
from typing import Any, Dict, Mapping, Optional, Protocol, Union, runtime_checkable


# Members are read-only properties: mutable attributes are invariant, which would reject
# the concrete requests/httpx types (CaseInsensitiveDict vs Dict, PreparedRequest vs Request).
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
    """Protocol for HTTP request objects.

    requests' PreparedRequest leaves method and url unset until it is prepared, hence Optional.
    """

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

    def json(self) -> Dict[str, Any]: ...


class SubParsers(Protocol):
    """The subset of argparse's subparsers action the CLI uses.

    argparse only exposes it as the private ``_SubParsersAction``, so match structurally.
    """

    def add_parser(self, name: str, **kwargs: Any) -> argparse.ArgumentParser: ...
