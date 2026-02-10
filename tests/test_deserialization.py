"""Unit tests for deserialization utilities."""

import unittest
from typing import Dict

from httpx import Response

from kognic.auth.serde import deserialize


class TestDeserialize(unittest.TestCase):
    def test_deserialize_to_Dict(self):
        resp = Response(200, json={"data": {"key": "value"}})
        val = deserialize(resp, cls=Dict[str, str])
        self.assertEqual(val, {"key": "value"})

    def test_deserialize_to_dict(self):
        resp = Response(200, json={"data": {"key": "value"}})
        val = deserialize(resp, cls=dict[str, str])
        self.assertEqual(val, {"key": "value"})

    def test_deserialize_to_raw(self):
        resp = Response(200, json={"data": {"key": "value"}})
        val = deserialize(resp, cls=None)
        self.assertEqual(val, {"key": "value"})

    def test_deserialize_with_custom_envelope_key(self):
        resp = {"custom_key": {"key": "value"}}
        val = deserialize(resp, cls=Dict[str, str], enveloped_key="custom_key")
        self.assertEqual(val, {"key": "value"})

    def test_deserialize_from_dict(self):
        resp = {"data": {"key": "value"}}
        val = deserialize(resp, cls=Dict[str, str])
        self.assertEqual(val, {"key": "value"})

    def test_deserialize_to_list(self):
        resp = Response(200, json={"data": [1, 2, 3]})
        val = deserialize(resp, cls=list[int])
        self.assertEqual(val, [1, 2, 3])

    def test_deserialize_to_list_of_dicts(self):
        resp = Response(200, json={"data": [{"key": "value"}]})
        val = deserialize(resp, cls=list[Dict[str, str]])
        self.assertEqual(val, [{"key": "value"}])

    def test_deserialize_empty_list(self):
        resp = Response(200, json={"data": []})
        val = deserialize(resp, cls=list[Dict[str, str]])
        self.assertEqual(val, [])

    def test_deserialize_no_envelope(self):
        resp = Response(200, json={"key": "value"})
        val = deserialize(resp, cls=None, enveloped_key=None)
        self.assertEqual(val, {"key": "value"})

    def test_deserialize_missing_envelope_key_raises(self):
        resp = Response(200, json={"wrong_key": {"key": "value"}})
        with self.assertRaises(ValueError) as context:
            deserialize(resp, cls=None)
        self.assertIn("Expected enveloped key 'data' not found", str(context.exception))

    def test_deserialize_to_class_with_from_dict(self):
        class MyModel:
            def __init__(self, key: str):
                self.key = key

            @classmethod
            def from_dict(cls, data: dict):
                return cls(key=data["key"])

        resp = Response(200, json={"data": {"key": "value"}})
        result = deserialize(resp, cls=MyModel)
        self.assertIsInstance(result, MyModel)
        self.assertEqual(result.key, "value")

    def test_deserialize_to_class_with_from_json(self):
        class MyModel:
            def __init__(self, key: str):
                self.key = key

            @classmethod
            def from_json(cls, data: dict):
                return cls(key=data["key"])

        resp = Response(200, json={"data": {"key": "value"}})
        result = deserialize(resp, cls=MyModel)
        self.assertIsInstance(result, MyModel)
        self.assertEqual(result.key, "value")

    def test_deserialize_list_to_class_with_from_dict(self):
        class MyModel:
            def __init__(self, key: str):
                self.key = key

            @classmethod
            def from_dict(cls, data: dict):
                return cls(key=data["key"])

        resp = Response(200, json={"data": [{"key": "a"}, {"key": "b"}]})
        result = deserialize(resp, cls=list[MyModel])
        self.assertIsInstance(result, list)
        self.assertEqual(len(result), 2)
        self.assertIsInstance(result[0], MyModel)
        self.assertEqual(result[0].key, "a")
        self.assertEqual(result[1].key, "b")

    def test_deserialize_list_to_class_with_from_json(self):
        class MyModel:
            def __init__(self, key: str):
                self.key = key

            @classmethod
            def from_json(cls, data: dict):
                return cls(key=data["key"])

        resp = Response(200, json={"data": [{"key": "x"}, {"key": "y"}]})
        result = deserialize(resp, cls=list[MyModel])
        self.assertIsInstance(result, list)
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0].key, "x")
        self.assertEqual(result[1].key, "y")

    def test_deserialize_empty_list_to_class(self):
        class MyModel:
            @classmethod
            def from_dict(cls, data: dict):
                return cls()

        resp = Response(200, json={"data": []})
        result = deserialize(resp, cls=list[MyModel])
        self.assertEqual(result, [])

    def test_deserialize_unsupported_class_raises(self):
        class UnsupportedModel:
            pass

        resp = Response(200, json={"data": {"key": "value"}})
        with self.assertRaises(TypeError) as context:
            deserialize(resp, cls=UnsupportedModel)
        self.assertIn("Cannot deserialize to UnsupportedModel", str(context.exception))
        self.assertIn("from_dict()", str(context.exception))


if __name__ == "__main__":
    unittest.main()
