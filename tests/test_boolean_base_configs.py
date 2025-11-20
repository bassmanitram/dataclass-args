"""
Tests for boolean field handling with base_configs.

This module tests that boolean fields from base_configs are preserved correctly
when not overridden by CLI flags.
"""

import tempfile
from dataclasses import dataclass
from pathlib import Path

import pytest

from dataclass_args import build_config


@dataclass
class BoolConfig:
    """Test config with various boolean fields."""

    debug: bool = False
    verbose: bool = True
    enabled: bool = False
    disabled: bool = True


class TestBooleanFromDict:
    """Test boolean values from base_configs dict."""

    def test_bool_true_overrides_false_default(self):
        """Boolean True from dict overrides False default."""
        config = build_config(BoolConfig, args=[], base_configs={"debug": True})
        assert config.debug is True

    def test_bool_false_overrides_true_default(self):
        """Boolean False from dict overrides True default."""
        config = build_config(BoolConfig, args=[], base_configs={"verbose": False})
        assert config.verbose is False

    def test_multiple_bool_overrides(self):
        """Multiple boolean overrides from dict."""
        config = build_config(
            BoolConfig,
            args=[],
            base_configs={
                "debug": True,
                "verbose": False,
                "enabled": True,
                "disabled": False,
            },
        )
        assert config.debug is True
        assert config.verbose is False
        assert config.enabled is True
        assert config.disabled is False

    def test_partial_bool_overrides(self):
        """Some fields from dict, others use defaults."""
        config = build_config(
            BoolConfig, args=[], base_configs={"debug": True, "enabled": True}
        )
        assert config.debug is True  # from dict
        assert config.verbose is True  # default
        assert config.enabled is True  # from dict
        assert config.disabled is True  # default


class TestBooleanFromFile:
    """Test boolean values from base_configs file."""

    def test_bool_from_json_file(self):
        """Boolean values from JSON file."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            f.write('{"debug": true, "verbose": false}')
            config_file = f.name

        try:
            config = build_config(BoolConfig, args=[], base_configs=config_file)
            assert config.debug is True
            assert config.verbose is False
        finally:
            Path(config_file).unlink()

    def test_bool_from_yaml_file(self):
        """Boolean values from YAML file."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write("debug: true\nverbose: false\n")
            config_file = f.name

        try:
            config = build_config(BoolConfig, args=[], base_configs=config_file)
            assert config.debug is True
            assert config.verbose is False
        finally:
            Path(config_file).unlink()


class TestBooleanCLIOverride:
    """Test that CLI arguments override base_configs."""

    def test_cli_flag_overrides_dict(self):
        """CLI --flag overrides dict value."""
        config = build_config(
            BoolConfig, args=["--debug"], base_configs={"debug": False}
        )
        assert config.debug is True

    def test_cli_no_flag_overrides_dict(self):
        """CLI --no-flag overrides dict value."""
        config = build_config(
            BoolConfig, args=["--no-verbose"], base_configs={"verbose": True}
        )
        assert config.verbose is False

    def test_multiple_cli_overrides(self):
        """Multiple CLI flags override dict values."""
        config = build_config(
            BoolConfig,
            args=["--debug", "--no-verbose", "--enabled"],
            base_configs={"debug": False, "verbose": True, "enabled": False},
        )
        assert config.debug is True
        assert config.verbose is False
        assert config.enabled is True


class TestBooleanMixed:
    """Test mixed scenarios: some CLI, some base_configs, some defaults."""

    def test_cli_partial_dict_rest(self):
        """Some from CLI, some from dict, some defaults."""
        config = build_config(
            BoolConfig,
            args=["--debug"],  # Only debug from CLI
            base_configs={
                "verbose": False,
                "enabled": True,
            },  # verbose and enabled from dict
        )
        assert config.debug is True  # from CLI
        assert config.verbose is False  # from dict
        assert config.enabled is True  # from dict
        assert config.disabled is True  # default

    def test_dict_without_cli_preserves_values(self):
        """Dict values preserved when no CLI flag for that field."""
        config = build_config(
            BoolConfig,
            args=["--enabled"],  # Only set enabled via CLI
            base_configs={
                "debug": True,  # Should be preserved
                "verbose": False,  # Should be preserved
            },
        )
        assert config.debug is True  # from dict (no CLI override)
        assert config.verbose is False  # from dict (no CLI override)
        assert config.enabled is True  # from CLI
        assert config.disabled is True  # default

    def test_cli_overrides_one_dict_preserves_others(self):
        """CLI overrides one field, dict values preserved for others."""
        config = build_config(
            BoolConfig,
            args=["--no-verbose"],  # Override only verbose
            base_configs={
                "debug": True,
                "verbose": True,  # Will be overridden
                "enabled": True,
            },
        )
        assert config.debug is True  # from dict
        assert config.verbose is False  # from CLI (overrides dict)
        assert config.enabled is True  # from dict


class TestBooleanDefaultBehavior:
    """Test that defaults work correctly without base_configs or CLI."""

    def test_no_args_no_config_uses_defaults(self):
        """No args, no config uses dataclass defaults."""
        config = build_config(BoolConfig, args=[])
        assert config.debug is False
        assert config.verbose is True
        assert config.enabled is False
        assert config.disabled is True

    def test_empty_dict_uses_defaults(self):
        """Empty dict uses dataclass defaults."""
        config = build_config(BoolConfig, args=[], base_configs={})
        assert config.debug is False
        assert config.verbose is True


class TestBooleanConfigFilePlusCLI:
    """Test --config file argument combined with CLI flags."""

    def test_config_file_plus_cli_override(self):
        """--config file combined with CLI override."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            f.write('{"debug": true, "verbose": false}')
            config_file = f.name

        try:
            config = build_config(
                BoolConfig,
                args=["--config", config_file, "--debug"],  # CLI overrides
            )
            # CLI explicitly set debug=True (same as file, but from CLI)
            assert config.debug is True
            # File set verbose=False
            assert config.verbose is False
        finally:
            Path(config_file).unlink()

    def test_base_configs_plus_config_file_plus_cli(self):
        """Hierarchy: base_configs < --config file < CLI."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            f.write('{"verbose": false}')
            config_file = f.name

        try:
            config = build_config(
                BoolConfig,
                args=["--config", config_file, "--enabled"],
                base_configs={"debug": True},  # Lowest priority
            )
            assert config.debug is True  # from base_configs
            assert config.verbose is False  # from --config file
            assert config.enabled is True  # from CLI
        finally:
            Path(config_file).unlink()


class TestBooleanEdgeCases:
    """Test edge cases for boolean handling."""

    def test_bool_explicitly_set_to_default_via_cli(self):
        """CLI flag explicitly sets value to match default."""
        # Default is debug=False, explicitly set --no-debug
        config = build_config(
            BoolConfig,
            args=["--no-debug"],  # Explicitly False
            base_configs={"debug": True},  # Try to override
        )
        # CLI should win even though it matches default
        assert config.debug is False

    def test_bool_both_positive_and_negative_flags(self):
        """Last flag wins if both positive and negative specified."""
        config = build_config(
            BoolConfig,
            args=["--debug", "--no-debug"],  # Conflicting flags
        )
        # argparse behavior: last one wins
        assert config.debug is False

    def test_all_false_values(self):
        """All booleans set to False."""
        config = build_config(
            BoolConfig,
            args=[],
            base_configs={
                "debug": False,
                "verbose": False,
                "enabled": False,
                "disabled": False,
            },
        )
        assert config.debug is False
        assert config.verbose is False
        assert config.enabled is False
        assert config.disabled is False

    def test_all_true_values(self):
        """All booleans set to True."""
        config = build_config(
            BoolConfig,
            args=[],
            base_configs={
                "debug": True,
                "verbose": True,
                "enabled": True,
                "disabled": True,
            },
        )
        assert config.debug is True
        assert config.verbose is True
        assert config.enabled is True
        assert config.disabled is True


class TestBooleanMultipleBasConfigs:
    """Test boolean handling with multiple base_configs."""

    def test_list_of_dicts_later_overrides_earlier(self):
        """Later dict in list overrides earlier dict."""
        config = build_config(
            BoolConfig,
            args=[],
            base_configs=[
                {"debug": True, "verbose": False},
                {"debug": False},  # Overrides debug only
            ],
        )
        assert config.debug is False  # from second dict
        assert config.verbose is False  # from first dict

    def test_file_and_dict_combination(self):
        """Mix files and dicts in base_configs list."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            f.write('{"debug": true}')
            config_file = f.name

        try:
            config = build_config(
                BoolConfig,
                args=[],
                base_configs=[
                    config_file,  # File first
                    {"verbose": False},  # Dict second
                ],
            )
            assert config.debug is True  # from file
            assert config.verbose is False  # from dict
        finally:
            Path(config_file).unlink()
