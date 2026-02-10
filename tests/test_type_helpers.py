"""Unit tests for type checking helper functions."""

import unittest
from collections import UserDict, UserList
from typing import Dict, List

from kognic.auth.serde import _is_dict_type, _is_list_type


class TestTypeHelpers(unittest.TestCase):
    def test_is_list_type_with_list(self):
        self.assertTrue(_is_list_type(list))

    def test_is_list_type_with_List(self):
        self.assertTrue(_is_list_type(List))

    def test_is_list_type_with_List_generic(self):
        self.assertTrue(_is_list_type(List[str]))

    def test_is_list_type_with_list_generic(self):
        self.assertTrue(_is_list_type(list[str]))

    def test_is_list_type_with_UserList(self):
        self.assertTrue(_is_list_type(UserList))

    def test_is_list_type_with_dict(self):
        self.assertFalse(_is_list_type(dict))

    def test_is_dict_type_with_dict(self):
        self.assertTrue(_is_dict_type(dict))

    def test_is_dict_type_with_Dict(self):
        self.assertTrue(_is_dict_type(Dict))

    def test_is_dict_type_with_Dict_generic(self):
        self.assertTrue(_is_dict_type(Dict[str, str]))

    def test_is_dict_type_with_dict_generic(self):
        self.assertTrue(_is_dict_type(dict[str, str]))

    def test_is_dict_type_with_UserDict(self):
        self.assertTrue(_is_dict_type(UserDict))

    def test_is_dict_type_with_list(self):
        self.assertFalse(_is_dict_type(list))


if __name__ == "__main__":
    unittest.main()
