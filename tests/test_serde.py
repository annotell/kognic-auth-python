"""Unit tests for serialization and deserialization utilities."""

import unittest
from typing import Dict

from httpx import Response

from kognic.auth._serde import deserialize, serialize_body


class TestSerializeBody(unittest.TestCase):
    def test_serialize_none(self):
        self.assertIsNone(serialize_body(None))

    def test_serialize_dict(self):
        data = {"key": "value"}
        self.assertEqual(serialize_body(data), data)

    def test_serialize_nested_dict(self):
        data = {"key": {"nested_key": "value"}}
        self.assertEqual(serialize_body(data), data)

    def test_serialize_list(self):
        data = ["apa", "bepa"]
        self.assertEqual(serialize_body(data), data)

    def test_serialize_str_raises(self):
        with self.assertRaises(ValueError):
            serialize_body('{"key": "value"}')

    def test_serialize_bytes_raises(self):
        with self.assertRaises(ValueError):
            serialize_body(b'{"key": "value"}')

    def test_serialize_object_with_method(self):
        class MyModel:
            def serialize_to_json(self):
                return {"serialized": True}

        self.assertEqual(serialize_body(MyModel()), {"serialized": True})

    def test_serialize_unsupported_type_raises(self):
        class UnsupportedType:
            pass

        with self.assertRaises(TypeError):
            serialize_body(UnsupportedType())


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


if __name__ == "__main__":
    unittest.main()
