"""Serialization and deserialization utilities for HTTP request/response bodies."""

from typing import Any, Dict, List, Optional, Type, Union

ENVELOPED_KEY = "data"


def serialize_body(body: Any) -> Any:
    """Serialize request body to JSON-compatible format.

    Supports:
    - None, dict, list, primitives (passed through)
    - Objects with to_json() or to_dict method (duck typing)
    - Nested objects inside containers are recursively serialized

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
    if isinstance(value, dict):
        return {k: _serialize_value(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_serialize_value(item) for item in value]
    if hasattr(value, "to_json") and callable(value.to_json):
        return _serialize_value(value.to_json())
    if hasattr(value, "to_dict") and callable(value.to_dict):
        return _serialize_value(value.to_dict())
    raise TypeError(
        f"Cannot serialize value of type {type(value).__name__}. Expected dict, list, primitive, or Serializable."
    )


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

    # For basic types (dict, list without inner type), return the data as-is
    if cls in (dict, list):
        return data

    # Handle generic types like Dict[str, str] or list[MyModel]
    origin = getattr(cls, "__origin__", None)
    if origin is dict:
        return data

    # Handle list[SomeClass] - deserialize each item
    if origin is list:
        args = getattr(cls, "__args__", ())
        if not args:
            return data
        inner_cls = args[0]
        # If inner type is a basic type, return as-is
        if inner_cls in (dict, list, str, int, float, bool) or getattr(inner_cls, "__origin__", None) is not None:
            return data
        # Deserialize each item using inner class
        return [_deserialize_object(item, inner_cls) for item in data]

    # Single object deserialization
    return _deserialize_object(data, cls)


def _deserialize_object(data: Any, cls: Type) -> Any:
    """Deserialize a single object using duck-typed from_dict/from_json."""
    if hasattr(cls, "from_dict") and callable(cls.from_dict):
        return cls.from_dict(data)

    if hasattr(cls, "from_json") and callable(cls.from_json):
        return cls.from_json(data)

    raise TypeError(
        f"Cannot deserialize to {cls.__name__}. " f"Class must have a from_dict() or from_json() class method."
    )
