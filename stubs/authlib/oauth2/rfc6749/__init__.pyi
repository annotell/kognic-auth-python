from typing import Any

class OAuth2Token(dict[str, Any]):
    def is_expired(self, leeway: int = 60) -> bool | None: ...
