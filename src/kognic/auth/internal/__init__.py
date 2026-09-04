"""Internal helpers. Not part of the public API."""

from typing import Optional, Protocol


class KeyringModule(Protocol):
    """The subset of the optional ``keyring`` module this package uses."""

    def get_password(self, service_name: str, username: str) -> Optional[str]: ...

    def set_password(self, service_name: str, username: str, password: str) -> None: ...

    def delete_password(self, service_name: str, username: str) -> None: ...
