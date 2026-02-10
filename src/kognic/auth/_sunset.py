"""Sunset header handling for deprecated API endpoints."""

import logging
from datetime import datetime
from typing import TYPE_CHECKING, Optional, Union

if TYPE_CHECKING:
    from ._protocols import Response, Url

SUNSET_HEADER = "sunset-date"
SUNSET_DIFF_THRESHOLD = 14 * 60 * 60 * 24  # two weeks

# Expected format of sunset date, e.g. 2024-02-22T16:21:20.880547Z
DATETIME_FMT = "%Y-%m-%dT%H:%M:%S.%fZ"

logger = logging.getLogger(__name__)


def handle_sunset(response: "Response") -> None:
    """Check for Sunset header and log warnings/errors.

    Args:
        response: The HTTP response object (requests.Response or httpx.Response)
    """
    sunset_string = response.headers.get(SUNSET_HEADER)
    sunset_date = _parse_date(sunset_string) if sunset_string else None
    if not sunset_date:
        return None

    now = datetime.now()
    diff = sunset_date - now

    log_method = logger.warning if diff.total_seconds() > SUNSET_DIFF_THRESHOLD else logger.error
    log_method(
        f"Endpoint has been deprecated and will be removed at {sunset_date}. Please update your client. "
        f"Endpoint: {response.request.method} {_parse_url(response.request.url)}"
    )


def _parse_date(date: str) -> Optional[datetime]:
    """Parse sunset date string to datetime."""
    try:
        return datetime.strptime(date, DATETIME_FMT)
    except ValueError:
        return None


def _parse_url(url: Union[str, "Url"]) -> str:
    """Extract clean URL without query parameters."""
    if isinstance(url, str):
        return url.split("?")[0]
    return f"{url.scheme}://{url.host}{url.path}"
