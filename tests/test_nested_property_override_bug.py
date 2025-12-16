"""
Test for bug: Property overrides not applied with cli_nested.

Bug report: Property overrides are not being applied to Dict fields when
those fields are inside a cli_nested() dataclass.

The override ARGUMENTS are generated correctly and PARSED correctly,
but the override VALUES are not APPLIED to the final config.

The issue is that _apply_cli_overrides() skips nested dataclass fields,
and _reconstruct_nested_fields() only handles file loading for dicts,
not property overrides.
"""

import json
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional

import pytest

from dataclass_args import build_config, cli_nested


class TestNestedPropertyOverrideBug:
    """Test cases demonstrating the property override bug with cli_nested."""

    def test_yacba_scenario_no_prefix(self):
        """
        Reproduce the exact YACBA scenario from bug report.

        This is the most critical test case - when prefix="" the override
        arguments ARE generated (--mc) and ARE parsed, but the values
        are NOT applied to the final config.
        """

        @dataclass
        class AgentFactoryConfig:
            """Simulates strands-agent-factory's AgentFactoryConfig."""

            model_config: Optional[Dict[str, Any]] = None

        @dataclass
        class YacbaConfig:
            """Simulates YACBA's config structure."""

            agent: AgentFactoryConfig = cli_nested(prefix="")

        # Command: yacba --mc temperature:0.7
        # The --mc argument exists (from model_config -> mc abbreviation)
        config = build_config(YacbaConfig, ["--mc", "temperature:0.7"])

        # Expected: agent.model_config should be {"temperature": 0.7}
        # Actual BUG: agent.model_config is None
        assert config.agent is not None
        assert (
            config.agent.model_config is not None
        ), "BUG: model_config is None - override was not applied"
        assert config.agent.model_config == {"temperature": 0.7}

    def test_override_with_prefix(self):
        """Property overrides should work with cli_nested(prefix='agent-')."""

        @dataclass
        class AgentConfig:
            model: str = "gpt-4"
            model_config: Optional[Dict[str, Any]] = None

        @dataclass
        class AppConfig:
            agent: AgentConfig = cli_nested(prefix="agent-")

        # This should apply the override to agent.model_config
        # CLI: --agent-mc temperature:0.7
        config = build_config(AppConfig, ["--agent-mc", "temperature:0.7"])

        # BUG: This currently fails - model_config is None
        assert config.agent is not None
        assert (
            config.agent.model_config is not None
        ), "BUG: model_config is None - override was not applied"
        assert config.agent.model_config == {"temperature": 0.7}

    def test_multiple_overrides_no_prefix(self):
        """Multiple property overrides should accumulate correctly."""

        @dataclass
        class NestedConfig:
            settings: Optional[Dict[str, Any]] = None

        @dataclass
        class TopConfig:
            nested: NestedConfig = cli_nested(prefix="")

        # Multiple overrides via --s (abbreviation of settings)
        config = build_config(TopConfig, ["--s", "key1:value1", "--s", "key2:value2"])

        # BUG: settings is None instead of {"key1": "value1", "key2": "value2"}
        assert config.nested is not None
        assert (
            config.nested.settings is not None
        ), "BUG: settings is None - overrides were not applied"
        assert config.nested.settings == {"key1": "value1", "key2": "value2"}

    def test_override_with_file_loading_no_prefix(self):
        """Property overrides should work alongside file loading."""

        @dataclass
        class NestedConfig:
            settings: Optional[Dict[str, Any]] = None

        @dataclass
        class TopConfig:
            nested: NestedConfig = cli_nested(prefix="")

        # Create temp config file
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump({"base_key": "base_value"}, f)
            config_file = f.name

        try:
            # Load from file AND apply override
            # --settings loads file, --s applies override
            config = build_config(
                TopConfig, ["--settings", config_file, "--s", "override_key:override"]
            )

            # BUG: File loading works, but override is NOT applied
            assert config.nested is not None
            assert config.nested.settings is not None
            assert (
                config.nested.settings["base_key"] == "base_value"
            ), "File loading should work"
            assert (
                "override_key" in config.nested.settings
            ), "BUG: Override key missing - override was not applied"
            assert config.nested.settings["override_key"] == "override"
        finally:
            Path(config_file).unlink()

    def test_override_flat_field_works(self):
        """Control test: Property overrides work for non-nested dict fields."""

        @dataclass
        class TopConfig:
            settings: Optional[Dict[str, Any]] = None

        # This should work (and currently does)
        # --s is the abbreviation for settings
        config = build_config(TopConfig, ["--s", "key:value"])

        assert config.settings is not None
        assert config.settings == {"key": "value"}

    def test_override_only_no_file_no_prefix(self):
        """Test override-only (no file) with no prefix."""

        @dataclass
        class NestedConfig:
            data: Optional[Dict[str, Any]] = None

        @dataclass
        class TopConfig:
            nested: NestedConfig = cli_nested(prefix="")

        # Only override, no file loading
        # --d is abbreviation for data
        config = build_config(TopConfig, ["--d", "key:value"])

        # BUG: data is None instead of {"key": "value"}
        assert config.nested is not None
        assert (
            config.nested.data is not None
        ), "BUG: data is None - override without file failed"
        assert config.nested.data == {"key": "value"}
