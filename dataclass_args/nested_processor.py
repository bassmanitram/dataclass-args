"""
Nested dataclass field processing.

Handles flattening of nested dataclass fields to CLI arguments
and reconstruction from flat args back to nested structure.
"""

import argparse
from dataclasses import asdict, is_dataclass
from typing import Any, Dict

from .config_applicator import ConfigApplicator
from .exceptions import ConfigBuilderError, ConfigurationError
from .file_loading import process_file_loadable_value
from .utils import load_structured_file


class NestedFieldProcessor:
    """
    Process nested dataclass fields - flatten and reconstruct.

    Consolidates the complex logic in _flatten_nested_fields and
    _reconstruct_nested_fields.
    """

    def __init__(self, config_class, config_fields: Dict[str, Dict[str, Any]]):
        """
        Initialize processor.

        Args:
            config_class: Parent dataclass type
            config_fields: Analyzed field information
        """
        self.config_class = config_class
        self.config_fields = config_fields

    def flatten(self) -> Dict[str, Dict[str, Any]]:
        """
        Flatten nested dataclass fields to CLI argument mappings.

        Returns:
            Dict mapping flat CLI names to their metadata including:
            - parent_field: Name of parent field (None for flat fields)
            - nested_field: Name of field in nested dataclass
            - nested_info: Field info from nested dataclass
            - prefix: Prefix used for this nested field
            - field_info: Field info for flat fields (if not nested)
        """
        # Import here to avoid circular dependency
        from .builder import GenericConfigBuilder

        flat_fields: Dict[str, Dict[str, Any]] = {}

        for field_name, info in self.config_fields.items():
            if info.get("is_nested_dataclass", False):
                # Flatten nested dataclass fields
                self._flatten_nested_class(
                    flat_fields, field_name, info, GenericConfigBuilder
                )
            else:
                # Regular flat field
                self._add_flat_field(flat_fields, field_name, info)

        return flat_fields

    def reconstruct(
        self,
        config: Dict[str, Any],
        args: argparse.Namespace,
        flat_fields: Dict[str, Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        Reconstruct nested dataclass instances from flat CLI arguments.

        Args:
            config: Current configuration dictionary
            args: Parsed CLI arguments with flat nested fields
            flat_fields: Flattened field mapping from flatten()

        Returns:
            Configuration dict with nested dataclass instances reconstructed
        """
        # Group nested fields by parent
        nested_data: Dict[str, Dict[str, Any]] = {}

        # Process all nested fields
        for cli_name, mapping in flat_fields.items():
            if mapping.get("parent_field"):
                self._process_nested_field(nested_data, cli_name, mapping, args)

        # Reconstruct nested dataclass instances
        for field_name, info in self.config_fields.items():
            if info.get("is_nested_dataclass", False):
                config[field_name] = self._reconstruct_nested_instance(
                    config, field_name, info, nested_data
                )

        return config

    # ========================================================================
    # Flatten Helper Methods
    # ========================================================================

    def _flatten_nested_class(
        self,
        flat_fields: Dict,
        field_name: str,
        info: Dict[str, Any],
        builder_class,
    ) -> None:
        """Flatten a single nested dataclass."""
        nested_class = info["type"]
        prefix = info["nested_prefix"]

        # Recursively analyze nested dataclass fields
        nested_builder = builder_class(nested_class)

        for nested_field_name, nested_info in nested_builder._config_fields.items():
            # Build flat CLI name with prefix
            flat_cli_name = self._build_flat_cli_name(nested_field_name, prefix)

            # Check for collision
            self._check_collision(
                flat_fields, flat_cli_name, field_name, nested_field_name
            )

            # Add to flat fields
            flat_fields[flat_cli_name] = {
                "parent_field": field_name,
                "nested_field": nested_field_name,
                "nested_info": nested_info,
                "prefix": prefix,
                "parent_info": info,
            }

    def _add_flat_field(
        self, flat_fields: Dict, field_name: str, info: Dict[str, Any]
    ) -> None:
        """Add a regular flat field to mapping."""
        cli_name = info["cli_name"]

        # Check for collision
        if cli_name in flat_fields:
            prev_mapping = flat_fields[cli_name]
            source1 = self._get_field_source(prev_mapping)

            raise ConfigBuilderError(
                f"Field name collision detected:\n\n"
                f"  {cli_name}\n"
                f"    - {source1}\n"
                f"    - {field_name}\n\n"
                f"This should not happen with non-nested fields. Please report this bug."
            )

        flat_fields[cli_name] = {
            "parent_field": None,
            "field_info": info,
            "field_name": field_name,
        }

    def _build_flat_cli_name(self, field_name: str, prefix: str) -> str:
        """Build CLI name with prefix."""
        base_name = field_name.replace("_", "-")
        if prefix == "":
            return f"--{base_name}"
        else:
            return f"--{prefix}{base_name}"

    def _check_collision(
        self,
        flat_fields: Dict,
        cli_name: str,
        parent_field: str,
        nested_field: str,
    ) -> None:
        """Check for CLI name collision."""
        if cli_name in flat_fields:
            prev_mapping = flat_fields[cli_name]
            source1 = self._get_field_source(prev_mapping)
            source2 = f"{parent_field}.{nested_field}"

            raise ConfigBuilderError(
                f"Field name collision detected when flattening nested dataclasses:\n\n"
                f"  {cli_name}\n"
                f"    - {source1}\n"
                f"    - {source2}\n\n"
                f"Solutions:\n"
                f"  1. Add prefix to nested fields:\n"
                f"     {parent_field}: NestedClass = cli_nested(prefix='n')\n"
                f"  2. Rename conflicting fields\n"
                f"  3. Use auto-prefix (don't specify prefix='')"
            )

    def _get_field_source(self, mapping: Dict[str, Any]) -> str:
        """Get source name from mapping."""
        if mapping.get("parent_field"):
            return f"{mapping['parent_field']}.{mapping['nested_field']}"
        else:
            return mapping.get("field_name", "unknown")

    # ========================================================================
    # Reconstruct Helper Methods
    # ========================================================================

    def _process_nested_field(
        self,
        nested_data: Dict[str, Dict[str, Any]],
        cli_name: str,
        mapping: Dict[str, Any],
        args: argparse.Namespace,
    ) -> None:
        """Process a single nested field from CLI args."""
        parent_field = mapping["parent_field"]
        nested_field = mapping["nested_field"]
        nested_info = mapping["nested_info"]

        # Convert CLI name to arg name
        arg_name = cli_name.lstrip("-").replace("-", "_")
        cli_value = getattr(args, arg_name, None)

        # Initialize nested data dict if needed
        if parent_field not in nested_data:
            nested_data[parent_field] = {}

        # Process the value
        if cli_value is not None:
            self._process_cli_value(
                nested_data[parent_field],
                nested_field,
                nested_info,
                cli_value,
                parent_field,
            )

        # Handle property overrides for dict fields
        if nested_info["is_dict"]:
            self._process_dict_overrides(
                nested_data[parent_field], nested_field, nested_info, mapping, args
            )

    def _process_cli_value(
        self,
        parent_data: Dict,
        nested_field: str,
        nested_info: Dict[str, Any],
        cli_value: Any,
        parent_field: str,
    ) -> None:
        """Process CLI value based on field type."""
        if nested_info["is_list"]:
            parent_data[nested_field] = cli_value
        elif nested_info["is_dict"]:
            # Load dict from file
            try:
                dict_config = load_structured_file(cli_value)
                parent_data[nested_field] = dict_config
            except Exception as e:
                raise ConfigurationError(
                    f"Failed to load dictionary config for nested field "
                    f"'{parent_field}.{nested_field}' from {cli_value}: {e}"
                ) from e
        else:
            # Process file-loadable values
            try:
                processed_value = process_file_loadable_value(
                    cli_value, nested_field, nested_info
                )
                parent_data[nested_field] = processed_value
            except (ValueError, Exception) as e:
                raise ConfigurationError(
                    f"Failed to process nested field "
                    f"'{parent_field}.{nested_field}': {e}"
                ) from e

    def _process_dict_overrides(
        self,
        parent_data: Dict,
        nested_field: str,
        nested_info: Dict[str, Any],
        mapping: Dict[str, Any],
        args: argparse.Namespace,
    ) -> None:
        """Process property overrides for dict fields."""
        # Get override argument name with prefix
        base_override = nested_info.get("override_name", "").lstrip("--")
        prefix = mapping.get("prefix", "")

        if base_override:
            # Apply prefix if present
            if prefix:
                override_arg_name = f"{prefix}{base_override}".replace("-", "_")
            else:
                override_arg_name = base_override.replace("-", "_")

            override_value = getattr(args, override_arg_name, None)
            if override_value:
                # Initialize dict if not already present
                if nested_field not in parent_data:
                    parent_data[nested_field] = {}

                # Apply property overrides
                try:
                    ConfigApplicator.apply_property_overrides(
                        parent_data[nested_field],
                        override_value,
                    )
                except Exception as e:
                    parent_field = mapping.get("parent_field", "unknown")
                    raise ConfigurationError(
                        f"Failed to apply property overrides for nested field "
                        f"'{parent_field}.{nested_field}': {e}"
                    ) from e

    def _reconstruct_nested_instance(
        self,
        config: Dict[str, Any],
        field_name: str,
        info: Dict[str, Any],
        nested_data: Dict[str, Dict[str, Any]],
    ):
        """Reconstruct a nested dataclass instance."""
        nested_class = info["type"]

        # Start with existing config value (from base configs or defaults)
        if field_name in config and config[field_name] is not None:
            # Convert existing instance to dict if needed
            if is_dataclass(config[field_name]):
                existing_dict = asdict(config[field_name])
            elif isinstance(config[field_name], dict):
                existing_dict = config[field_name].copy()
            else:
                existing_dict = {}
        else:
            existing_dict = {}

        # Merge CLI overrides
        if field_name in nested_data:
            existing_dict.update(nested_data[field_name])

        # Reconstruct nested dataclass instance
        try:
            return nested_class(**existing_dict)
        except Exception as e:
            raise ConfigurationError(
                f"Failed to create nested dataclass {nested_class.__name__} "
                f"for field '{field_name}': {e}"
            ) from e
