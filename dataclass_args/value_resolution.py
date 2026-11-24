"""
Value resolution: process raw values, validate ranges, apply cli_resolve.

This module handles stages 5, 7, and part of 8 of the config resolution pipeline:
    5. Resolve raw values (@file loading for base_configs scalar values)
    7. Validate append ranges (min_args/max_args enforcement)
    8. Resolve fields (cli_resolve transformations)

Responsibilities:
    - Process @file references in base_configs/config file values
    - Validate append field min/max argument counts
    - Apply cli_resolve transformations
"""

import argparse
from typing import Any, Dict

from .annotations import (
    get_cli_append_max_args,
    get_cli_append_min_args,
    get_cli_resolver,
    is_cli_append,
    is_cli_resolve,
)
from .exceptions import ConfigurationError
from .file_loading import process_file_loadable_value


class ValueResolver:
    """
    Resolves raw values and applies field-level transformations.

    Handles:
    - Raw value resolution: @file loading for base_configs
    - Append validation: min/max args enforcement
    - cli_resolve application: Transform values via resolver functions
    """

    def __init__(self, config_fields: Dict[str, Dict[str, Any]]):
        """
        Initialize value resolver.

        Args:
            config_fields: Dictionary of analyzed field information
        """
        self.config_fields = config_fields

    def resolve_raw_values(
        self, config: Dict[str, Any], args: argparse.Namespace
    ) -> Dict[str, Any]:
        """
        Process raw values in config_dict that weren't touched by CLI overrides.

        Values from base_configs or config files may contain:
        - @file references (for cli_file_loadable string fields)

        These need the same processing that CLI values get. Dict-field file
        path strings are not handled here: they are loaded when each layer
        enters the pipeline (see LayerNormalizer). We skip fields that
        already had a CLI value (those were processed in apply_cli_overrides).

        Args:
            config: Configuration dictionary after CLI overrides
            args: Parsed CLI arguments (to detect which fields had CLI values)

        Returns:
            Configuration dictionary with all raw values resolved
        """
        for field_name, info in self.config_fields.items():
            if info.get("is_nested_dataclass", False):
                continue

            # Skip if CLI already provided a value (it was processed in apply_cli_overrides)
            cli_value = self._get_cli_value(args, field_name)
            if cli_value is not None:
                continue

            # Check if there's a value in config_dict to process
            value = config.get(field_name)
            if value is None:
                continue

            # Process based on field type (same logic as CLI overrides)
            # Lists need no processing; dict-field file refs were loaded at layer intake
            if not (info["is_list"] or info["is_dict"]):
                self._resolve_raw_scalar_value(config, field_name, info, value)

        return config

    def _resolve_raw_scalar_value(
        self, config: Dict[str, Any], field_name: str, info: Dict[str, Any], value: Any
    ) -> None:
        """Resolve a raw scalar field value from base_configs/config file."""
        if not isinstance(value, str):
            return  # Non-strings don't need resolution
        try:
            processed = process_file_loadable_value(value, field_name, info)
            config[field_name] = processed
        except (ValueError, Exception) as e:
            raise ConfigurationError(
                f"Failed to process field '{field_name}': {e}"
            ) from e

    def _get_cli_value(self, args: argparse.Namespace, field_name: str) -> Any:
        """Get CLI value for a field from parsed arguments."""
        arg_name = field_name.replace("-", "_")
        return getattr(args, arg_name, None)

    def validate_append_ranges(self, config_dict: Dict[str, Any]) -> None:
        """
        Validate min/max argument counts for append fields.

        Args:
            config_dict: Configuration dictionary after CLI parsing

        Raises:
            ConfigurationError: If any append field violates min/max constraints
        """
        for field_name, info in self.config_fields.items():
            if not is_cli_append(info):
                continue

            min_args = get_cli_append_min_args(info)
            max_args = get_cli_append_max_args(info)

            # Skip if no range validation specified
            if min_args is None or max_args is None:
                continue

            field_value = config_dict.get(field_name)
            if not field_value:
                continue  # Empty is OK (validated by required/optional)

            # Validate each occurrence
            for i, occurrence in enumerate(field_value):
                self._validate_single_append_range(
                    field_name, i, occurrence, min_args, max_args
                )

    def _validate_single_append_range(
        self, field_name: str, index: int, occurrence: Any, min_args: int, max_args: int
    ) -> None:
        """
        Validate a single append field occurrence.

        Args:
            field_name: Name of the field
            index: Index of the occurrence (0-based)
            occurrence: The occurrence value to validate
            min_args: Minimum number of arguments expected
            max_args: Maximum number of arguments expected

        Raises:
            ConfigurationError: If the occurrence violates min/max constraints
        """
        # Normalize to list
        if not isinstance(occurrence, list):
            occurrence = [occurrence]

        arg_count = len(occurrence)

        if arg_count < min_args:
            raise ConfigurationError(
                f"Field '{field_name}' occurrence #{index+1}: "
                f"Expected at least {min_args} argument(s), got {arg_count}. "
                f"Each occurrence must have between {min_args} and {max_args} argument(s)."
            )

        if arg_count > max_args:
            raise ConfigurationError(
                f"Field '{field_name}' occurrence #{index+1}: "
                f"Expected at most {max_args} argument(s), got {arg_count}. "
                f"Each occurrence must have between {min_args} and {max_args} argument(s)."
            )

    def resolve_fields(self, config_dict: Dict[str, Any]) -> Dict[str, Any]:
        """
        Apply resolver functions to cli_resolve fields.

        For each field annotated with cli_resolve, calls the resolver function
        on the assembled raw value. Skips None values (resolver not called).

        Args:
            config_dict: Configuration dictionary after all merging stages

        Returns:
            Configuration dictionary with resolved field values

        Raises:
            ConfigurationError: If resolver raises an exception (wraps non-ConfigurationError)
        """
        for field_name, info in self.config_fields.items():
            if not is_cli_resolve(info):
                continue

            value = config_dict.get(field_name)
            if value is None:
                continue  # None bypass: resolver never called for None

            resolver = get_cli_resolver(info)
            if resolver is None:
                continue  # pragma: no cover - safety guard for mypy
            config_dict[field_name] = self._apply_resolver(field_name, resolver, value)

        return config_dict

    @staticmethod
    def _apply_resolver(field_name: str, resolver: Any, value: Any) -> Any:
        """Call a cli_resolve resolver, wrapping non-ConfigurationError failures."""
        try:
            return resolver(value)
        except ConfigurationError:
            raise  # Re-raise without wrapping
        except Exception as e:
            raise ConfigurationError(
                f"Failed to resolve field '{field_name}': {e}"
            ) from e
