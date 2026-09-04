"""Serialization and deserialization utilities for HTTP request/response bodies."""

from typing import Any, Dict, List, Optional, TypeGuard

ENVELOPED_KEY = "data"


def is_json_object(value: Any) -> TypeGuard[Dict[str, Any]]:
    """Narrow a decoded-JSON value to an object. isinstance alone leaves the item types unknown."""
    return isinstance(value, dict)


def is_json_array(value: Any) -> TypeGuard[List[Any]]:
    """Narrow a decoded-JSON value to an array. isinstance alone leaves the item types unknown."""
    return isinstance(value, list)


def serialize_body(body: Any) -> Any:
    """Serialize request body to JSON-compatible format.

    Supports:
    - None, dict, list, primitives (passed through)

    Raises:
        ValueError: If body is str or bytes at top level (not supported as request body)
        TypeError: If body type is not supported
    """
    if body is None:
        return None
    if isinstance(body, (str, bytes)):
        raise ValueError("str and bytes data is not supported")
    return _serialize_value(body)


def _serialize_value(value: Any) -> Any:
    """Recursively serialize a value (used internally for container contents)."""
    if value is None:
        return None
    if isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, bytes):
        raise ValueError("bytes data is not supported")
    if is_json_object(value):
        return {k: _serialize_value(v) for k, v in value.items()}
    if is_json_array(value):
        return [_serialize_value(item) for item in value]
    raise TypeError(f"Cannot serialize value of type {type(value).__name__}. Expected dict, list, or primitive.")


def deserialize(
    response: Any,
    enveloped_key: Optional[str] = ENVELOPED_KEY,
) -> Any:
    """Deserialize a response from the API.

    Designed to work with httpx and requests response objects by duck typing.

    Args:
        response: Response object (with .json() method) or dict/list
        enveloped_key: By Kognic convention, data is enveloped in a key.
            Default is 'data'. Set to None to skip envelope extraction.

    Returns:
        Deserialized data as raw dict/list

    Raises:
        ValueError: If enveloped_key is specified but not found in response
    """
    # Extract JSON from response object or use directly if already a dict/list
    try:
        response_json = response.json()
    except AttributeError:
        response_json = response

    # Extract data from envelope if specified
    if enveloped_key is not None:
        if enveloped_key not in response_json:
            raise ValueError(
                f"Expected enveloped key '{enveloped_key}' not found in response json. "
                f"Found keys: {response_json.keys()}"
            )
        return response_json[enveloped_key]

    return response_json
