"""Sunset header handling for deprecated API endpoints."""

import logging
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Callable, Optional, Union

if TYPE_CHECKING:
    from ._protocols import Response, Url

SUNSET_HEADER = "sunset-date"

# Expected formats of sunset date
DATETIME_FMT = "%Y-%m-%dT%H:%M:%S.%fZ"
DATETIME_FMT_NO_MICRO = "%Y-%m-%dT%H:%M:%SZ"

logger = logging.getLogger(__name__)

SunsetHandler = Callable[[datetime, str, str], None]


def default_sunset_handler(threshold_days: int = 14) -> SunsetHandler:
    """Return a sunset handler that logs a warning or error based on time until sunset.

    Args:
        threshold_days: Days remaining before the sunset date at which the log level
            escalates from warning to error. Defaults to 14.

    Returns:
        A callable ``(sunset_date, method, url) -> None`` that logs the deprecation notice.

    Example::

        from kognic.auth import default_sunset_handler
        client = BaseApiClient(sunset_handler=default_sunset_handler(threshold_days=30))
    """
    threshold_seconds = threshold_days * 60 * 60 * 24

    def handler(sunset_date: datetime, method: str, url: str) -> None:
        now = datetime.now(tz=timezone.utc)
        diff = sunset_date - now
        log_method = logger.warning if diff.total_seconds() > threshold_seconds else logger.error
        log_method(
            f"Endpoint has been deprecated and will be removed at {sunset_date}. Please update your client. "
            f"Endpoint: {method} {url}"
        )

    return handler


_default_handler: SunsetHandler = default_sunset_handler()


def handle_sunset(response: "Response", handler: Optional[SunsetHandler] = _default_handler) -> None:
    """Check for Sunset header and invoke the handler if present.

    Args:
        response: The HTTP response object (requests.Response or httpx.Response)
        handler: Callable invoked with ``(sunset_date, method, url)``. Pass ``None`` to disable.
    """
    if handler is None:
        return
    sunset_string = response.headers.get(SUNSET_HEADER)
    sunset_date = _parse_date(sunset_string) if sunset_string else None
    if not sunset_date:
        return

    handler(sunset_date, response.request.method, _parse_url(response.request.url))


def _parse_date(date: str) -> Optional[datetime]:
    """Parse sunset date string to UTC datetime."""
    for fmt in (DATETIME_FMT, DATETIME_FMT_NO_MICRO):
        try:
            return datetime.strptime(date, fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return None


def _parse_url(url: Union[str, "Url"]) -> str:
    """Extract clean URL without query parameters."""
    if isinstance(url, str):
        return url.split("?")[0]
    return f"{url.scheme}://{url.host}{url.path}"
