"""Unit tests for deserialization utilities."""

import unittest

from httpx import Response

from kognic.auth.serde import deserialize


class TestDeserialize(unittest.TestCase):
    def test_deserialize_to_raw(self):
        resp = Response(200, json={"data": {"key": "value"}})
        val = deserialize(resp)
        self.assertEqual(val, {"key": "value"})

    def test_deserialize_with_custom_envelope_key(self):
        resp = {"custom_key": {"key": "value"}}
        val = deserialize(resp, enveloped_key="custom_key")
        self.assertEqual(val, {"key": "value"})

    def test_deserialize_from_dict(self):
        resp = {"data": {"key": "value"}}
        val = deserialize(resp)
        self.assertEqual(val, {"key": "value"})

    def test_deserialize_list(self):
        resp = Response(200, json={"data": [1, 2, 3]})
        val = deserialize(resp)
        self.assertEqual(val, [1, 2, 3])

    def test_deserialize_list_of_dicts(self):
        resp = Response(200, json={"data": [{"key": "value"}]})
        val = deserialize(resp)
        self.assertEqual(val, [{"key": "value"}])

    def test_deserialize_empty_list(self):
        resp = Response(200, json={"data": []})
        val = deserialize(resp)
        self.assertEqual(val, [])

    def test_deserialize_no_envelope(self):
        resp = Response(200, json={"key": "value"})
        val = deserialize(resp, enveloped_key=None)
        self.assertEqual(val, {"key": "value"})

    def test_deserialize_missing_envelope_key_raises(self):
        resp = Response(200, json={"wrong_key": {"key": "value"}})
        with self.assertRaises(ValueError) as context:
            deserialize(resp)
        self.assertIn("Expected enveloped key 'data' not found", str(context.exception))


if __name__ == "__main__":
    unittest.main()
