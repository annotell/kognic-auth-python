"""Serialization and deserialization utilities for HTTP request/response bodies."""

from typing import Any, Dict, List, Optional, Type, Union

ENVELOPED_KEY = "data"


def serialize_body(body: Any) -> Any:
    """Serialize request body to JSON-compatible format.

    Supports:
    - None, dict, list, primitives (passed through)
    - Objects with serialize_to_json() method (duck typing)

    Raises:
        ValueError: If body is str or bytes (not supported)
        TypeError: If body type is not supported
    """
    if body is None:
        return None
    if isinstance(body, (str, bytes)):
        raise ValueError("str and bytes data is not supported")
    if isinstance(body, (dict, list, int, float, bool)):
        return body
    if hasattr(body, "serialize_to_json") and callable(body.serialize_to_json):
        return body.serialize_to_json()
    raise TypeError(f"Cannot serialize body of type {type(body).__name__}. Expected dict, list, or Serializable.")


def deserialize(
    response: Union[Any, Dict[str, Any], List],
    cls: Optional[Type] = None,
    enveloped_key: Optional[str] = ENVELOPED_KEY,
) -> Any:
    """Deserialize a response from the API.

    Designed to work with httpx and requests response objects by duck typing.

    Args:
        response: Response object (with .json() method) or dict/list
        cls: Optional type hint for the expected return type. For basic types
            (dict, list) the data is returned as-is. For model classes,
            kognic-common must be installed.
        enveloped_key: By Kognic convention, data is enveloped in a key.
            Default is 'data'. Set to None to skip envelope extraction.

    Returns:
        Deserialized data

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
        data = response_json[enveloped_key]
    else:
        data = response_json

    # Return raw data if no class specified
    if cls is None:
        return data

    # For basic types, just return the data (type hints are not enforced at runtime)
    if cls in (dict, list) or getattr(cls, "__origin__", None) in (dict, list):
        return data
