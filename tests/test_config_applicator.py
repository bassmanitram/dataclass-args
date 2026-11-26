"""Tests for ConfigApplicator utility class."""

import argparse

import pytest

from dataclass_args.config_applicator import ConfigApplicator
from dataclass_args.exceptions import ConfigurationError


class TestApplyBaseConfigs:
    """Test apply_base_configs method."""

    def test_empty_list(self):
        result = ConfigApplicator.apply_base_configs([])
        assert result == {}

    def test_single_config(self):
        result = ConfigApplicator.apply_base_configs([{"key": "value"}])
        assert result == {"key": "value"}

    def test_multiple_configs_merge(self):
        result = ConfigApplicator.apply_base_configs(
            [
                {"a": 1, "b": 2},
                {"b": 3, "c": 4},
            ]
        )
        assert result == {"a": 1, "b": 3, "c": 4}

    def test_later_overrides_earlier(self):
        result = ConfigApplicator.apply_base_configs(
            [
                {"key": "first"},
                {"key": "second"},
                {"key": "third"},
            ]
        )
        assert result == {"key": "third"}

    def test_invalid_type_raises_error(self):
        with pytest.raises(ConfigurationError, match="must contain dictionaries"):
            ConfigApplicator.apply_base_configs([{"valid": True}, "invalid"])

    def test_non_dict_raises_error(self):
        with pytest.raises(ConfigurationError, match="got <class 'list'>"):
            ConfigApplicator.apply_base_configs([["not", "a", "dict"]])


class TestApplyConfigFile:
    """Test apply_config_file method."""

    def test_no_config_file(self):
        config = {"existing": "value"}
        args = argparse.Namespace(config=None)
        result = ConfigApplicator.apply_config_file(config, args, "config")
        assert result == {"existing": "value"}

    def test_config_file_merges(self, tmp_path):
        import json

        config_file = tmp_path / "config.json"
        config_file.write_text(json.dumps({"new": "from_file"}))

        config = {"existing": "value"}
        args = argparse.Namespace(config=str(config_file))
        result = ConfigApplicator.apply_config_file(config, args, "config")

        assert result == {"existing": "value", "new": "from_file"}

    def test_config_file_overrides(self, tmp_path):
        import json

        config_file = tmp_path / "config.json"
        config_file.write_text(json.dumps({"key": "from_file"}))

        config = {"key": "original"}
        args = argparse.Namespace(config=str(config_file))
        result = ConfigApplicator.apply_config_file(config, args, "config")

        assert result == {"key": "from_file"}

    def test_missing_file_raises_error(self):
        config = {}
        args = argparse.Namespace(config="/nonexistent/file.json")

        with pytest.raises(ConfigurationError, match="Failed to load config file"):
            ConfigApplicator.apply_config_file(config, args, "config")


class TestApplyPropertyOverrides:
    """Test apply_property_overrides method."""

    def test_simple_override(self):
        target = {}
        ConfigApplicator.apply_property_overrides(target, ["key:value"])
        assert target == {"key": "value"}

    def test_nested_override(self):
        target = {}
        ConfigApplicator.apply_property_overrides(target, ["outer.inner:value"])
        assert target == {"outer": {"inner": "value"}}

    def test_deep_nested_override(self):
        target = {}
        ConfigApplicator.apply_property_overrides(target, ["a.b.c.d:value"])
        assert target == {"a": {"b": {"c": {"d": "value"}}}}

    def test_multiple_overrides(self):
        target = {}
        ConfigApplicator.apply_property_overrides(
            target,
            [
                "key1:value1",
                "key2:value2",
                "nested.key:value3",
            ],
        )
        assert target == {
            "key1": "value1",
            "key2": "value2",
            "nested": {"key": "value3"},
        }

    def test_override_existing(self):
        target = {"key": "old"}
        ConfigApplicator.apply_property_overrides(target, ["key:new"])
        assert target == {"key": "new"}

    def test_invalid_format_raises_error(self):
        target = {}
        with pytest.raises(ValueError, match="Invalid override"):
            ConfigApplicator.apply_property_overrides(target, ["no_colon_here"])

    def test_numeric_values(self):
        target = {}
        ConfigApplicator.apply_property_overrides(
            target,
            [
                "count:42",
                "price:19.99",
                "enabled:true",
            ],
        )
        assert target == {"count": 42, "price": 19.99, "enabled": True}


class TestSetNestedProperty:
    """Test set_nested_property method."""

    def test_simple_property(self):
        target = {}
        ConfigApplicator.set_nested_property(target, "key", "value")
        assert target == {"key": "value"}

    def test_nested_property(self):
        target = {}
        ConfigApplicator.set_nested_property(target, "outer.inner", "value")
        assert target == {"outer": {"inner": "value"}}

    def test_creates_intermediate_dicts(self):
        target = {}
        ConfigApplicator.set_nested_property(target, "a.b.c", "value")
        assert target == {"a": {"b": {"c": "value"}}}

    def test_non_dict_parent_raises_error(self):
        target = {"key": "string_value"}
        with pytest.raises(ValueError, match="not a dictionary"):
            ConfigApplicator.set_nested_property(target, "key.nested", "value")


class TestListIndexOverrides:
    """Test list index and append support in property overrides."""

    def test_set_list_element_by_index(self):
        target = {"items": ["a", "b", "c"]}
        ConfigApplicator.set_nested_property(target, "items.1", "new")
        assert target == {"items": ["a", "new", "c"]}

    def test_set_first_list_element(self):
        target = {"items": ["old"]}
        ConfigApplicator.set_nested_property(target, "items.0", "new")
        assert target == {"items": ["new"]}

    def test_nested_property_in_list_element(self):
        target = {"data": [{"name": "old", "value": 1}]}
        ConfigApplicator.set_nested_property(target, "data.0.name", "new")
        assert target == {"data": [{"name": "new", "value": 1}]}

    def test_deep_nested_list_navigation(self):
        target = {"a": [{"b": [{"c": "old"}]}]}
        ConfigApplicator.set_nested_property(target, "a.0.b.0.c", "new")
        assert target == {"a": [{"b": [{"c": "new"}]}]}

    def test_append_to_list(self):
        target = {"items": ["a", "b"]}
        ConfigApplicator.set_nested_property(target, "items.+", "c")
        assert target == {"items": ["a", "b", "c"]}

    def test_append_parsed_value(self):
        target = {"nums": [1, 2]}
        ConfigApplicator.set_nested_property(target, "nums.+", "3")
        assert target == {"nums": [1, 2, 3]}

    def test_append_to_empty_list(self):
        target = {"items": []}
        ConfigApplicator.set_nested_property(target, "items.+", "first")
        assert target == {"items": ["first"]}

    def test_index_out_of_range_raises(self):
        target = {"items": ["a"]}
        with pytest.raises(ValueError, match="List index out of range"):
            ConfigApplicator.set_nested_property(target, "items.5", "val")

    def test_index_out_of_range_in_navigation_raises(self):
        target = {"data": [{"name": "a"}]}
        with pytest.raises(ValueError, match="List index out of range"):
            ConfigApplicator.set_nested_property(target, "data.3.name", "val")

    def test_non_numeric_key_on_list_raises(self):
        target = {"items": ["a", "b"]}
        with pytest.raises(ValueError, match="non-numeric key"):
            ConfigApplicator.set_nested_property(target, "items.foo", "val")

    def test_dict_with_numeric_key_unchanged(self):
        """Backward compat: numeric key on dict stays a string dict key."""
        target = {"items": {}}
        ConfigApplicator.set_nested_property(target, "items.0", "value")
        assert target == {"items": {"0": "value"}}

    def test_plus_on_dict_is_string_key(self):
        """+ on a dict creates a string key, not an append."""
        target = {"config": {}}
        ConfigApplicator.set_nested_property(target, "config.+", "value")
        assert target == {"config": {"+": "value"}}

    def test_apply_overrides_with_list_index(self):
        """End-to-end via apply_property_overrides."""
        target = {"items": ["a", "b"], "data": [{"name": "old"}]}
        ConfigApplicator.apply_property_overrides(
            target, ["items.0:new", "data.0.name:updated"]
        )
        assert target == {"items": ["new", "b"], "data": [{"name": "updated"}]}

    def test_apply_overrides_with_append(self):
        """End-to-end append via apply_property_overrides."""
        target = {"tags": ["python"]}
        ConfigApplicator.apply_property_overrides(target, ["tags.+:cli", "tags.+:tool"])
        assert target == {"tags": ["python", "cli", "tool"]}


class TestParseValue:
    """Test parse_value method."""

    def test_parse_string(self):
        assert ConfigApplicator.parse_value('"hello"') == "hello"
        assert ConfigApplicator.parse_value("plain") == "plain"

    def test_parse_int(self):
        assert ConfigApplicator.parse_value("42") == 42
        assert ConfigApplicator.parse_value("-10") == -10

    def test_parse_float(self):
        assert ConfigApplicator.parse_value("3.14") == 3.14
        assert ConfigApplicator.parse_value("-0.5") == -0.5

    def test_parse_bool(self):
        assert ConfigApplicator.parse_value("true") is True
        assert ConfigApplicator.parse_value("false") is False

    def test_parse_null(self):
        assert ConfigApplicator.parse_value("null") is None

    def test_parse_list(self):
        assert ConfigApplicator.parse_value("[1, 2, 3]") == [1, 2, 3]

    def test_parse_dict(self):
        assert ConfigApplicator.parse_value('{"key": "value"}') == {"key": "value"}

    def test_non_json_returns_string(self):
        assert ConfigApplicator.parse_value("not json") == "not json"
        assert ConfigApplicator.parse_value("hello world") == "hello world"
