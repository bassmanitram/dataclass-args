"""
Configuration application utilities.

Consolidates logic for applying configurations from various sources.
"""

import argparse
from typing import Any, Dict, List

from .exceptions import ConfigurationError
from .utils import load_structured_file


class ConfigApplicator:
    """
    Apply configurations from various sources (base configs, files, CLI overrides).

    Consolidates repeated patterns in _apply_* methods.
    """

    @staticmethod
    def apply_base_configs(base_configs: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Apply base configuration dictionaries in order.

        Args:
            base_configs: List of configuration dictionaries to merge in order

        Returns:
            Merged configuration dictionary

        Note:
            Each config is applied sequentially with shallow merge.
            Later configs override earlier ones.
        """
        config = {}

        for base_config in base_configs:
            if not isinstance(base_config, dict):
                raise ConfigurationError(
                    f"base_configs must contain dictionaries, got {type(base_config)}"
                )
            config.update(base_config)

        return config

    @staticmethod
    def apply_config_file(
        config: Dict[str, Any],
        args: argparse.Namespace,
        base_config_name: str,
    ) -> Dict[str, Any]:
        """
        Load and merge configuration from --config file argument.

        Args:
            config: Current configuration dictionary
            args: Parsed CLI arguments
            base_config_name: Name of the config file argument

        Returns:
            Updated configuration dictionary with file config merged

        Raises:
            ConfigurationError: If file cannot be loaded
        """
        base_config_value = getattr(args, base_config_name.replace("-", "_"), None)

        if base_config_value:
            try:
                file_config = load_structured_file(base_config_value)
                config.update(file_config)
            except Exception as e:
                raise ConfigurationError(
                    f"Failed to load config file '{base_config_value}': {e}"
                ) from e

        return config

    @staticmethod
    def apply_property_overrides(
        target_dict: Dict[str, Any], overrides: List[str]
    ) -> None:
        """
        Apply property path overrides to target dictionary.

        Args:
            target_dict: Dictionary to apply overrides to (modified in place)
            overrides: List of "key.path:value" override strings

        Raises:
            ValueError: If override format is invalid
        """
        for override in overrides:
            if ":" not in override:
                raise ValueError(
                    f"Invalid override format: {override} (expected key.path:value)"
                )

            path, value_str = override.split(":", 1)
            ConfigApplicator._set_nested_property(target_dict, path, value_str)

    @staticmethod
    def _set_nested_property(target: Dict[str, Any], path: str, value_str: str) -> None:
        """
        Set nested property using dot notation.

        Args:
            target: Target dictionary
            path: Property path (e.g., "outer.inner.key")
            value_str: String value to parse and set
        """
        keys = path.split(".")
        current = target

        # Navigate to parent
        for key in keys[:-1]:
            if key not in current:
                current[key] = {}
            elif not isinstance(current[key], dict):
                raise ValueError(
                    f"Cannot set nested property: {key} is not a dictionary"
                )
            current = current[key]

        # Parse and set value
        final_key = keys[-1]
        current[final_key] = ConfigApplicator._parse_value(value_str)

    @staticmethod
    def _parse_value(value_str: str) -> Any:
        """
        Parse string value to appropriate type.

        Tries JSON parsing first (for numbers, bools, etc.), falls back to string.
        """
        import json

        try:
            return json.loads(value_str)
        except json.JSONDecodeError:
            return value_str
