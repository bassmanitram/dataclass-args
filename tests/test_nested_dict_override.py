"""
Tests for dict field property override in nested dataclasses.

This tests the feature where dict fields inside nested dataclasses
get override arguments with proper prefix handling.
"""

import json
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict

import pytest

from dataclass_args import GenericConfigBuilder, build_config, cli_nested


class TestNestedDictOverride:
    """Test override arguments for dict fields in nested dataclasses."""

    def test_override_arg_generated_with_prefix(self):
        """Test that override argument is generated with custom prefix."""

        @dataclass
        class ModelConfig:
            temperature: float = 0.7
            model_config: Dict[str, Any] = None

        @dataclass
        class Config:
            name: str = "app"
            model: ModelConfig = cli_nested(prefix="mc-", default_factory=ModelConfig)

        builder = GenericConfigBuilder(Config)

        # Check that override argument exists
        flat_fields = builder._flatten_nested_fields()
        override_found = False
        for cli_name, mapping in flat_fields.items():
            if mapping.get("nested_field") == "model_config":
                info = mapping["nested_info"]
                # Should have override_name
                assert "override_name" in info
                override_found = True
                break

        assert override_found, "model_config field should be in flattened fields"

    def test_override_arg_generated_without_prefix(self):
        """Test that override argument is generated with no prefix."""

        @dataclass
        class ModelConfig:
            temperature: float = 0.7
            model_config: Dict[str, Any] = None

        @dataclass
        class Config:
            name: str = "app"
            model: ModelConfig = cli_nested(prefix="", default_factory=ModelConfig)

        builder = GenericConfigBuilder(Config)

        # Check that override argument exists
        flat_fields = builder._flatten_nested_fields()
        override_found = False
        for cli_name, mapping in flat_fields.items():
            if mapping.get("nested_field") == "model_config":
                info = mapping["nested_info"]
                # Should have override_name
                assert "override_name" in info
                override_found = True
                break

        assert override_found, "model_config field should be in flattened fields"

    def test_override_parsing_with_prefix(self):
        """Test parsing override arguments with custom prefix."""

        @dataclass
        class ModelConfig:
            temperature: float = 0.7
            model_config: Dict[str, Any] = None

        @dataclass
        class Config:
            name: str = "app"
            model: ModelConfig = cli_nested(prefix="mc-", default_factory=ModelConfig)

        # Create temp JSON file
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump({"max_tokens": 1000}, f)
            temp_file = f.name

        try:
            import argparse

            builder = GenericConfigBuilder(Config)
            parser = argparse.ArgumentParser()
            builder.add_arguments(parser)

            # Parse with override
            parsed = parser.parse_args(
                [
                    "--mc-model-config",
                    temp_file,
                    "--mc-mc",
                    "temperature:0.9",
                    "--mc-mc",
                    "top_p:0.95",
                ]
            )

            # Check that override values are captured
            assert hasattr(parsed, "mc_mc"), "Override key 'mc_mc' not in parsed args"
            assert parsed.mc_mc == ["temperature:0.9", "top_p:0.95"]
        finally:
            Path(temp_file).unlink()

    def test_override_parsing_without_prefix(self):
        """Test parsing override arguments with no prefix."""

        @dataclass
        class ModelConfig:
            temperature: float = 0.7
            model_config: Dict[str, Any] = None

        @dataclass
        class Config:
            name: str = "app"
            model: ModelConfig = cli_nested(prefix="", default_factory=ModelConfig)

        # Create temp JSON file
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump({"max_tokens": 1000}, f)
            temp_file = f.name

        try:
            import argparse

            builder = GenericConfigBuilder(Config)
            parser = argparse.ArgumentParser()
            builder.add_arguments(parser)

            # Parse with override
            parsed = parser.parse_args(
                [
                    "--model-config",
                    temp_file,
                    "--mc",
                    "temperature:0.9",
                ]
            )

            # Check that override values are captured
            assert hasattr(parsed, "mc"), "Override key 'mc' not in parsed args"
            assert parsed.mc == ["temperature:0.9"]
        finally:
            Path(temp_file).unlink()

    def test_help_text_for_override(self):
        """Test that override argument has proper help text."""

        @dataclass
        class ModelConfig:
            model_config: Dict[str, Any] = None

        @dataclass
        class Config:
            model: ModelConfig = cli_nested(prefix="mc-", default_factory=ModelConfig)

        import argparse

        builder = GenericConfigBuilder(Config)
        parser = argparse.ArgumentParser()
        builder.add_arguments(parser)

        # Find override argument
        override_action = None
        for action in parser._actions:
            if "--mc-mc" in action.option_strings:
                override_action = action
                break

        assert override_action is not None, "Override argument not found"
        assert "property override" in override_action.help
        assert "key.path:value" in override_action.help

    def test_multiple_dict_fields_in_nested(self):
        """Test multiple dict fields in same nested dataclass."""

        @dataclass
        class Config:
            model_config: Dict[str, Any] = None
            tool_config: Dict[str, Any] = None

        @dataclass
        class AppConfig:
            agent: Config = cli_nested(prefix="agent-", default_factory=Config)

        import argparse

        builder = GenericConfigBuilder(AppConfig)
        parser = argparse.ArgumentParser()
        builder.add_arguments(parser)

        # Should have both override arguments
        arg_names = set()
        for action in parser._actions:
            arg_names.update(action.option_strings)

        assert "--agent-mc" in arg_names, "model_config override not found"
        assert "--agent-tc" in arg_names, "tool_config override not found"

    def test_override_with_auto_prefix(self):
        """Test override with auto-generated prefix (field name)."""

        @dataclass
        class ModelConfig:
            model_config: Dict[str, Any] = None

        @dataclass
        class Config:
            # No prefix specified - should use field name as prefix
            model: ModelConfig = cli_nested(default_factory=ModelConfig)

        import argparse

        builder = GenericConfigBuilder(Config)
        parser = argparse.ArgumentParser()
        builder.add_arguments(parser)

        # Should have override with auto prefix
        arg_names = set()
        for action in parser._actions:
            arg_names.update(action.option_strings)

        # Auto prefix is "model-" (field name + dash)
        assert "--model-mc" in arg_names, "Override with auto prefix not found"
