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

    def test_serialize_object_with_serialize_to_json(self):
        class MyModel:
            def to_json(self):
                return {"serialized": True}

        self.assertEqual(serialize_body(MyModel()), {"serialized": True})

    def test_serialize_object_with_to_dict(self):
        class MyModel:
            def to_dict(self):
                return {"key": "value"}

        self.assertEqual(serialize_body(MyModel()), {"key": "value"})

    def test_serialize_to_json_takes_precedence_over_to_dict(self):
        class MyModel:
            def to_json(self):
                return {"from": "to_json"}

            def to_dict(self):
                return {"from": "to_dict"}

        self.assertEqual(serialize_body(MyModel()), {"from": "to_json"})

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

    def test_serialize_nested_object_in_dict(self):
        class Inner:
            def to_dict(self):
                return {"inner": "value"}

        data = {"outer": Inner()}
        result = serialize_body(data)
        self.assertEqual(result, {"outer": {"inner": "value"}})

    def test_serialize_nested_object_in_list(self):
        class Item:
            def __init__(self, name):
                self.name = name

            def to_dict(self):
                return {"name": self.name}

        data = [Item("a"), Item("b")]
        result = serialize_body(data)
        self.assertEqual(result, [{"name": "a"}, {"name": "b"}])

    def test_serialize_deeply_nested(self):
        class Inner:
            def to_dict(self):
                return {"level": "inner"}

        class Outer:
            def __init__(self):
                self.inner = Inner()

            def to_dict(self):
                return {"level": "outer", "child": self.inner}

        result = serialize_body(Outer())
        self.assertEqual(result, {"level": "outer", "child": {"level": "inner"}})

    def test_serialize_mixed_list(self):
        class Item:
            def to_dict(self):
                return {"type": "object"}

        data = ["string", 42, Item(), {"key": "value"}]
        result = serialize_body(data)
        self.assertEqual(result, ["string", 42, {"type": "object"}, {"key": "value"}])


if __name__ == "__main__":
    unittest.main()
