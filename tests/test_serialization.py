"""Unit tests for serialization utilities."""

import unittest

from kognic.auth.serde import serialize_body


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

    def test_serialize_unsupported_type_raises(self):
        class UnsupportedType:
            pass

        with self.assertRaises(TypeError):
            serialize_body(UnsupportedType())

    def test_serialize_dict_with_strings(self):
        data = {"key": "value", "nested": {"inner": "string"}}
        self.assertEqual(serialize_body(data), data)

    def test_serialize_list_with_strings(self):
        data = ["a", "b", "c"]
        self.assertEqual(serialize_body(data), data)

    def test_serialize_mixed_list(self):
        data = ["string", 42, {"key": "value"}]
        result = serialize_body(data)
        self.assertEqual(result, ["string", 42, {"key": "value"}])


if __name__ == "__main__":
    unittest.main()
