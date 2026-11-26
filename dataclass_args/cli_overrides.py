"""
CLI override processing: apply CLI arguments with field-type-specific handling.

This module handles stages 3-4 of the config resolution pipeline:
    3. Apply CLI argument overrides → merged Dict (per-field processing)
    4. Property overrides for dict fields (--field-prop key:value syntax)

Responsibilities:
    - Get CLI values from argparse.Namespace
    - Apply field-type-specific processing (lists, dicts, scalars)
    - Load files for dict fields (.json/.yaml/.yml/.toml paths) and combine them
      with the existing value: one-level (default) or deep per merge_strategy
    - Process @file references for cli_file_loadable fields
    - Apply property overrides (--field-prop) to dict fields
"""

import argparse
from typing import Any, Dict

from .annotations import is_cli_resolve
from .config_applicator import ConfigApplicator, InvalidOverrideError
from .exceptions import ConfigurationError
from .file_loading import process_file_loadable_value
from .merge_strategy import MergeContext, combine_dicts
from .provenance import CLI_LAYER, override_observer
from .utils import (
    DictStringAction,
    cli_name_to_dest,
    dict_string_action,
    fresh_field_default,
    invalid_dict_string_message,
    load_structured_file,
)


class CliOverrideProcessor:
    """
    Processes CLI argument overrides with field-type-specific handling.

    Handles:
    - List fields: Replace config values with CLI values
    - Dict fields: Load from file paths or use directly, merge with existing
    - Scalar fields: Process @file references for cli_file_loadable
    - Property overrides: Apply key:value overrides to dict fields
    """

    def __init__(self, config_fields: Dict[str, Dict[str, Any]]):
        """
        Initialize CLI override processor.

        Args:
            config_fields: Dictionary of analyzed field information
        """
        self.config_fields = config_fields

    def apply_cli_overrides(
        self,
        config: Dict[str, Any],
        args: argparse.Namespace,
        ctx: MergeContext = MergeContext(),
    ) -> Dict[str, Any]:
        """
        Apply CLI argument overrides to configuration.

        Args:
            config: Current configuration dictionary
            args: Parsed CLI arguments
            ctx: Merge context (default: shallow)

        Returns:
            Final configuration dictionary with CLI overrides applied

        Raises:
            ConfigurationError: If CLI argument processing fails

        Note:
            Only processes fields included in the dataclass (not excluded).
            Handles special cases: lists, dicts, file-loadable fields, property
                overrides, append actions.
        """
        # Only process fields that were included in CLI
        # Skip nested dataclass fields (handled by reconstruct_nested_fields)
        for field_name, info in self.config_fields.items():
            if info.get("is_nested_dataclass", False):
                continue

            cli_value = self._get_cli_value(args, field_name)
            if cli_value is not None:
                self._apply_field_override(config, field_name, info, cli_value, ctx)

            self._apply_property_overrides_for_field(
                config, field_name, info, args, ctx
            )

        return config

    def _get_cli_value(self, args: argparse.Namespace, field_name: str) -> Any:
        """Get CLI value for a field from parsed arguments."""
        arg_name = field_name.replace("-", "_")
        return getattr(args, arg_name, None)

    def _apply_field_override(
        self,
        config: Dict[str, Any],
        field_name: str,
        info: Dict[str, Any],
        cli_value: Any,
        ctx: MergeContext = MergeContext(),
    ) -> None:
        """Apply CLI override for a field based on its type."""
        if info["is_list"]:
            self._apply_list_override(config, field_name, cli_value)
        elif info["is_dict"]:
            # Dict field (or cli_resolve field): load a file path, or use a dict
            self._apply_dict_override(config, field_name, info, cli_value, ctx)
            return
        else:
            # Scalar field OR cli_resolve field: pass through (handles @file, scalars,
            # and resolver inputs)
            self._apply_scalar_override(config, field_name, info, cli_value)
        self._record_cli(ctx, field_name, config[field_name])

    @staticmethod
    def _record_cli(ctx: MergeContext, field_name: str, value: Any) -> None:
        """Record a CLI-supplied value for provenance (a no-op when it's off)."""
        if ctx.recorder is not None:
            ctx.recorder.record_value(CLI_LAYER, (field_name,), value)

    def _apply_list_override(
        self, config: Dict[str, Any], field_name: str, cli_value: Any
    ) -> None:
        """Apply list override - CLI values replace config values."""
        # CLI values replace config values (standard argparse behavior)
        # With nargs='+' or '*', cli_value is already a list
        # With action='append', cli_value is a list of sub-lists (if nargs specified) or
        # list of values
        config[field_name] = cli_value

    def _apply_dict_override(
        self,
        config: Dict[str, Any],
        field_name: str,
        info: Dict[str, Any],
        cli_value: Any,
        ctx: MergeContext = MergeContext(),
    ) -> None:
        """
        Apply dict override - load from file if string, use directly if dict.

        A dict (or loaded file) is combined with the existing dict value using
        the build's merge strategy: one-level (default) or deep. Any other
        string is an error for a plain dict field, and passes through for a
        cli_resolve field (its resolver may accept strings). Values of any
        other type pass through unchanged.
        """
        if isinstance(cli_value, str):
            action = dict_string_action(cli_value, is_cli_resolve(info))
            if action == DictStringAction.INVALID:
                raise ConfigurationError(
                    invalid_dict_string_message(cli_value, field_name)
                )
            dict_config = (
                self._load_dict_file(field_name, cli_value)
                if action == DictStringAction.LOAD
                else cli_value
            )
        else:
            dict_config = cli_value
        if not isinstance(dict_config, dict):
            # A cli_resolve string, or a value of any other type: used as given
            config[field_name] = dict_config
            self._record_cli(ctx, field_name, dict_config)
            return

        # Provenance records what the CLI supplied (the loaded dict), not the merge
        self._record_cli(ctx, field_name, dict_config)
        existing = config.get(field_name, {})
        if isinstance(existing, dict):
            config[field_name] = combine_dicts(existing, dict_config, ctx)
        else:
            config[field_name] = dict_config

    @staticmethod
    def _load_dict_file(field_name: str, path: str) -> Dict[str, Any]:
        """Load a dict field's file, wrapping failures with the field name."""
        try:
            return load_structured_file(path)
        except Exception as e:
            raise ConfigurationError(
                f"Failed to load dictionary config for field '{field_name}' "
                f"from {path}: {e}"
            ) from e

    def _apply_scalar_override(
        self,
        config: Dict[str, Any],
        field_name: str,
        info: Dict[str, Any],
        cli_value: Any,
    ) -> None:
        """Apply scalar override - process file-loadable fields if value is string."""
        try:
            if isinstance(cli_value, str):
                processed_value = process_file_loadable_value(
                    cli_value, field_name, info
                )
            else:
                processed_value = cli_value
            config[field_name] = processed_value
        except (ValueError, Exception) as e:
            raise ConfigurationError(
                f"Failed to process field '{field_name}': {e}"
            ) from e

    @staticmethod
    def _property_override_target(
        config: Dict[str, Any], field_name: str, info: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Choose the dict that property overrides edit.

        The layer value if present, a fresh copy of the dataclass default if no
        layer set the field, and an empty dict after an explicit None.
        """
        if field_name not in config:
            default = fresh_field_default(info["field_obj"])
            return default if isinstance(default, dict) else {}
        existing = config[field_name]
        return {} if existing is None else existing

    def _apply_property_overrides_for_field(
        self,
        config: Dict[str, Any],
        field_name: str,
        info: Dict[str, Any],
        args: argparse.Namespace,
        ctx: MergeContext = MergeContext(),
    ) -> None:
        """Apply property overrides for dict fields."""
        if not info["is_dict"]:
            return

        override_value = getattr(args, cli_name_to_dest(info["override_name"]), None)
        if not override_value:
            return

        # Protection for dict fields holding pre-built objects or plain strings
        existing = config.get(field_name)
        if existing is not None and not isinstance(existing, dict):
            raise ConfigurationError(
                f"Cannot apply property overrides to field '{field_name}': "
                f"value is already a {type(existing).__name__}, not a dict."
            )

        config[field_name] = self._property_override_target(config, field_name, info)

        target = config[field_name]
        observer = override_observer(ctx, (field_name,), target)

        try:
            ConfigApplicator.apply_property_overrides(target, override_value, observer)
        except InvalidOverrideError as e:
            raise ConfigurationError(
                e.describe(field_name, info["override_name"], info["cli_name"])
            ) from e
        except Exception as e:
            raise ConfigurationError(
                f"Failed to apply property overrides for field '{field_name}': {e}"
            ) from e
