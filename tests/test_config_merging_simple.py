"""
Simplified tests for configuration merging with base_configs parameter.

Focuses on core functionality that works reliably.
"""

import json
import tempfile
from dataclasses import dataclass
from pathlib import Path

import pytest

from dataclass_args import build_config
from dataclass_args.exceptions import ConfigurationError


@dataclass
class SimpleConfig:
    """Simple config without booleans to avoid argparse edge cases."""

    name: str
    count: int = 10
    region: str = "us-east-1"


def test_single_file_base_config():
    """Should load config from single file path."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump({"name": "from-file", "count": 50, "region": "eu-west-1"}, f)
        path = f.name

    try:
        config = build_config(
            SimpleConfig,
            args=["--name", "override"],  # Override name
            base_configs=path,
        )

        assert config.name == "override"  # CLI wins
        assert config.count == 50  # From file
        assert config.region == "eu-west-1"  # From file
    finally:
        Path(path).unlink()


def test_single_dict_base_config():
    """Should use config from single dict."""
    config = build_config(
        SimpleConfig,
        args=[],  # No CLI overrides
        base_configs={"name": "from-dict", "count": 75},
    )

    assert config.name == "from-dict"
    assert config.count == 75


def test_mixed_list_base_configs():
    """Should handle list mixing files and dicts."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump({"name": "file1", "count": 20}, f)
        file1_path = f.name

    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump({"count": 30, "region": "ap-south-1"}, f)
        file2_path = f.name

    try:
        config = build_config(
            SimpleConfig,
            args=[],
            base_configs=[
                file1_path,  # File
                {"count": 25},  # Dict (overrides file1)
                file2_path,  # File (overrides dict)
            ],
        )

        assert config.name == "file1"  # From file1
        assert config.count == 30  # From file2 (last wins)
        assert config.region == "ap-south-1"  # From file2
    finally:
        Path(file1_path).unlink()
        Path(file2_path).unlink()


def test_merge_order_priority():
    """Should respect merge order: base_configs → --config → CLI."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump({"name": "config-file", "count": 100}, f)
        config_path = f.name

    try:
        config = build_config(
            SimpleConfig,
            args=["--config", config_path, "--region", "us-west-2"],
            base_configs={"name": "base", "count": 50},
        )

        assert config.name == "config-file"  # --config wins over base_configs
        assert config.count == 100  # --config wins
        assert config.region == "us-west-2"  # CLI wins
    finally:
        Path(config_path).unlink()


def test_cli_overrides_everything():
    """CLI args should have highest priority."""
    config = build_config(
        SimpleConfig,
        args=["--name", "cli", "--count", "999"],
        base_configs={"name": "base", "count": 50, "region": "eu-west-1"},
    )

    assert config.name == "cli"  # CLI overrides base_configs
    assert config.count == 999  # CLI overrides base_configs
    assert config.region == "eu-west-1"  # From base_configs (not overridden)


def test_invalid_base_configs_type():
    """Should raise error for invalid base_configs type."""
    with pytest.raises(ConfigurationError, match="must be str, dict, or list"):
        build_config(SimpleConfig, args=["--name", "test"], base_configs=123)


def test_file_not_found():
    """Should raise error for non-existent file."""
    with pytest.raises(ConfigurationError, match="Failed to load base_configs"):
        build_config(
            SimpleConfig, args=["--name", "test"], base_configs="/nonexistent/file.json"
        )


def test_invalid_list_item():
    """Should raise error for invalid item in base_configs list."""
    with pytest.raises(
        ConfigurationError, match="base_configs\\[1\\] must be str or dict"
    ):
        build_config(
            SimpleConfig,
            args=["--name", "test"],
            base_configs=[{"count": 10}, 123, {"region": "us-east-1"}],
        )


def test_empty_base_configs():
    """Should handle None and empty list."""
    config1 = build_config(SimpleConfig, args=["--name", "test"], base_configs=None)
    config2 = build_config(SimpleConfig, args=["--name", "test"], base_configs=[])

    assert config1.name == "test"
    assert config2.name == "test"


def test_real_world_multi_env():
    """Test realistic multi-environment scenario."""
    # Company defaults
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump({"name": "app", "count": 1, "region": "us-east-1"}, f)
        base_path = f.name

    # Prod overrides
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump({"count": 5, "region": "eu-west-1"}, f)
        prod_path = f.name

    # User config
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump({"region": "ap-south-1"}, f)
        user_path = f.name

    try:
        config = build_config(
            SimpleConfig,
            args=["--config", user_path, "--name", "final-app"],
            base_configs=[base_path, prod_path],
        )

        assert config.name == "final-app"  # CLI
        assert config.count == 5  # From prod
        assert config.region == "ap-south-1"  # From user config
    finally:
        Path(base_path).unlink()
        Path(prod_path).unlink()
        Path(user_path).unlink()
