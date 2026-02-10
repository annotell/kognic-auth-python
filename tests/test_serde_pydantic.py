"""Unit tests for Pydantic v2 integration with serde."""

import unittest
from typing import Optional

from httpx import Response
from pydantic import BaseModel

from kognic.auth.serde import deserialize, serialize_body


class SimpleModel(BaseModel):
    name: str
    value: int


class NestedModel(BaseModel):
    title: str
    item: SimpleModel


class OptionalFieldModel(BaseModel):
    name: str
    description: Optional[str] = None


class TestPydanticSerialization(unittest.TestCase):
    def test_serialize_pydantic_model(self):
        model = SimpleModel(name="test", value=42)
        result = serialize_body(model)
        self.assertEqual(result, {"name": "test", "value": 42})

    def test_serialize_nested_pydantic_model(self):
        model = NestedModel(title="parent", item=SimpleModel(name="child", value=1))
        result = serialize_body(model)
        self.assertEqual(result, {"title": "parent", "item": {"name": "child", "value": 1}})

    def test_serialize_pydantic_model_in_dict(self):
        data = {"model": SimpleModel(name="test", value=42)}
        result = serialize_body(data)
        self.assertEqual(result, {"model": {"name": "test", "value": 42}})

    def test_serialize_pydantic_model_in_list(self):
        data = [SimpleModel(name="a", value=1), SimpleModel(name="b", value=2)]
        result = serialize_body(data)
        self.assertEqual(result, [{"name": "a", "value": 1}, {"name": "b", "value": 2}])

    def test_serialize_pydantic_with_optional_field(self):
        model = OptionalFieldModel(name="test")
        result = serialize_body(model)
        self.assertEqual(result, {"name": "test", "description": None})


class TestPydanticDeserialization(unittest.TestCase):
    def test_deserialize_to_pydantic_model(self):
        resp = Response(200, json={"data": {"name": "test", "value": 42}})
        result = deserialize(resp, cls=SimpleModel)
        self.assertIsInstance(result, SimpleModel)
        self.assertEqual(result.name, "test")
        self.assertEqual(result.value, 42)

    def test_deserialize_list_to_pydantic_models(self):
        resp = Response(200, json={"data": [{"name": "a", "value": 1}, {"name": "b", "value": 2}]})
        result = deserialize(resp, cls=list[SimpleModel])
        self.assertIsInstance(result, list)
        self.assertEqual(len(result), 2)
        self.assertIsInstance(result[0], SimpleModel)
        self.assertEqual(result[0].name, "a")
        self.assertEqual(result[1].name, "b")

    def test_deserialize_nested_pydantic_model(self):
        resp = Response(200, json={"data": {"title": "parent", "item": {"name": "child", "value": 1}}})
        result = deserialize(resp, cls=NestedModel)
        self.assertIsInstance(result, NestedModel)
        self.assertEqual(result.title, "parent")
        self.assertIsInstance(result.item, SimpleModel)
        self.assertEqual(result.item.name, "child")

    def test_deserialize_pydantic_with_optional_field_missing(self):
        resp = Response(200, json={"data": {"name": "test"}})
        result = deserialize(resp, cls=OptionalFieldModel)
        self.assertIsInstance(result, OptionalFieldModel)
        self.assertEqual(result.name, "test")
        self.assertIsNone(result.description)

    def test_deserialize_pydantic_with_optional_field_present(self):
        resp = Response(200, json={"data": {"name": "test", "description": "desc"}})
        result = deserialize(resp, cls=OptionalFieldModel)
        self.assertEqual(result.description, "desc")

    def test_deserialize_empty_list_to_pydantic(self):
        resp = Response(200, json={"data": []})
        result = deserialize(resp, cls=list[SimpleModel])
        self.assertEqual(result, [])


if __name__ == "__main__":
    unittest.main()
