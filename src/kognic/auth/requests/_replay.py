"""Sending a request again after it was sent once."""

from __future__ import annotations

import requests
from requests.exceptions import UnrewindableBodyError
from requests.utils import rewind_body


def rewind_for_replay(req: requests.PreparedRequest) -> bool:
    """Make the body of a sent request ready to be sent again, and report whether that worked.

    A stream body is rewound to where requests recorded it started. A body that cannot be
    sent again in full, such as a generator, is never replayed.
    """
    if req.body is None or isinstance(req.body, (bytes, str)):
        return True
    try:
        rewind_body(req)
    except (UnrewindableBodyError, ValueError):
        return False
    return True
