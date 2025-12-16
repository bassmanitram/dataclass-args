"""Tests for TypeInspector utility class."""

from typing import Any, Dict, List, Optional, Union

import pytest

from dataclass_args.type_inspector import TypeInspector


class TestGetOriginAndArgs:
    """Test get_origin_and_args method."""

    def test_list_type(self):
        origin, args = TypeInspector.get_origin_and_args(List[str])
        assert origin is list
        assert args == (str,)

    def test_dict_type(self):
        origin, args = TypeInspector.get_origin_and_args(Dict[str, int])
        assert origin is dict
        assert args == (str, int)

    def test_optional_type(self):
        origin, args = TypeInspector.get_origin_and_args(Optional[int])
        assert origin is Union
        assert int in args
        assert type(None) in args

    def test_plain_type(self):
        origin, args = TypeInspector.get_origin_and_args(str)
        assert origin is None
        assert args == ()


class TestIsOptional:
    """Test is_optional method."""

    def test_optional_type(self):
        assert TypeInspector.is_optional(Optional[str])
        assert TypeInspector.is_optional(Optional[int])

    def test_union_with_none(self):
        assert TypeInspector.is_optional(Union[str, None])
        assert TypeInspector.is_optional(Union[int, str, None])

    def test_non_optional(self):
        assert not TypeInspector.is_optional(str)
        assert not TypeInspector.is_optional(int)
        assert not TypeInspector.is_optional(List[str])

    def test_union_without_none(self):
        assert not TypeInspector.is_optional(Union[str, int])


class TestUnwrapOptional:
    """Test unwrap_optional method."""

    def test_unwrap_optional_str(self):
        assert TypeInspector.unwrap_optional(Optional[str]) == str

    def test_unwrap_optional_int(self):
        assert TypeInspector.unwrap_optional(Optional[int]) == int

    def test_unwrap_optional_list(self):
        assert TypeInspector.unwrap_optional(Optional[List[str]]) == List[str]

    def test_unwrap_union_with_none(self):
        result = TypeInspector.unwrap_optional(Union[str, None])
        assert result == str

    def test_non_optional_unchanged(self):
        assert TypeInspector.unwrap_optional(str) == str
        assert TypeInspector.unwrap_optional(int) == int


class TestIsListType:
    """Test is_list_type method."""

    def test_list_type(self):
        assert TypeInspector.is_list_type(List[str])
        assert TypeInspector.is_list_type(List[int])
        assert TypeInspector.is_list_type(List[List[str]])

    def test_non_list(self):
        assert not TypeInspector.is_list_type(str)
        assert not TypeInspector.is_list_type(Dict[str, int])
        assert not TypeInspector.is_list_type(Optional[str])


class TestIsDictType:
    """Test is_dict_type method."""

    def test_dict_type(self):
        assert TypeInspector.is_dict_type(Dict[str, int])
        assert TypeInspector.is_dict_type(Dict[str, Any])

    def test_non_dict(self):
        assert not TypeInspector.is_dict_type(str)
        assert not TypeInspector.is_dict_type(List[str])
        assert not TypeInspector.is_dict_type(Optional[str])


class TestGetListElementType:
    """Test get_list_element_type method."""

    def test_list_str(self):
        assert TypeInspector.get_list_element_type(List[str]) == str

    def test_list_int(self):
        assert TypeInspector.get_list_element_type(List[int]) == int

    def test_nested_list(self):
        assert TypeInspector.get_list_element_type(List[List[str]]) == List[str]

    def test_non_list(self):
        assert TypeInspector.get_list_element_type(str) is None
        assert TypeInspector.get_list_element_type(Dict[str, int]) is None


class TestGetDictTypes:
    """Test get_dict_types method."""

    def test_dict_str_int(self):
        key_type, value_type = TypeInspector.get_dict_types(Dict[str, int])
        assert key_type == str
        assert value_type == int

    def test_dict_str_any(self):
        key_type, value_type = TypeInspector.get_dict_types(Dict[str, Any])
        assert key_type == str
        assert value_type == Any

    def test_non_dict(self):
        key_type, value_type = TypeInspector.get_dict_types(str)
        assert key_type is None
        assert value_type is None


class TestIsNestedList:
    """Test is_nested_list method."""

    def test_nested_list(self):
        assert TypeInspector.is_nested_list(List[List[str]])
        assert TypeInspector.is_nested_list(List[List[int]])

    def test_single_list(self):
        assert not TypeInspector.is_nested_list(List[str])
        assert not TypeInspector.is_nested_list(List[int])

    def test_non_list(self):
        assert not TypeInspector.is_nested_list(str)
        assert not TypeInspector.is_nested_list(Dict[str, int])


class TestGetNestedListElementType:
    """Test get_nested_list_element_type method."""

    def test_nested_list_str(self):
        assert TypeInspector.get_nested_list_element_type(List[List[str]]) == str

    def test_nested_list_int(self):
        assert TypeInspector.get_nested_list_element_type(List[List[int]]) == int

    def test_single_list(self):
        assert TypeInspector.get_nested_list_element_type(List[str]) is None

    def test_non_list(self):
        assert TypeInspector.get_nested_list_element_type(str) is None
