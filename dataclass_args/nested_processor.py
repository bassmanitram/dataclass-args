"""
Nested dataclass field processing.

Handles flattening of nested dataclass fields to CLI arguments
and reconstruction from flat args back to nested structure. Nested dict CLI
values are combined with the layer value one level deep (default) or
recursively, per the build's ``merge_strategy``.
"""

import argparse
from dataclasses import MISSING, fields, is_dataclass
from typing import Any, Dict, Tuple

from .annotations import is_cli_resolve
from .config_applicator import ConfigApplicator, InvalidOverrideError
from .exceptions import ConfigBuilderError, ConfigurationError
from .file_loading import process_file_loadable_value
from .merge_strategy import MergeContext, combine_dicts
from .provenance import CLI_LAYER, override_observer
from .utils import (
    DictStringAction,
    cli_name_to_dest,
    copy_containers,
    describe_missing,
    dict_string_action,
    fresh_field_default,
    invalid_dict_string_message,
    load_structured_file,
    missing_required_fields,
)


def mapping_source(mapping: Dict[str, Any]) -> str:
    """Describe where a flat-field mapping comes from (dotted: ``mid.inner.v``)."""
    if mapping.get("path"):
        return ".".join(mapping["path"])
    if mapping.get("parent_field"):
        return f"{mapping['parent_field']}.{mapping['nested_field']}"
    return mapping.get("field_name", "unknown")


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
        Flatten nested dataclass fields (at any depth) to CLI argument mappings.

        Returns:
            Dict mapping flat CLI names to their metadata including:
            - parent_field: Name of the top-level ancestor field (None for flat fields)
            - nested_field: Name of the leaf field in its own dataclass
            - nested_info: Field info of the leaf
            - prefix: Composed prefix (each level's prefix, top down)
            - path: Tuple of field names from the top-level field to the leaf
            - field_info: Field info for flat fields (if not nested)
        """
        # Import here to avoid circular dependency
        from .builder import GenericConfigBuilder

        flat_fields: Dict[str, Dict[str, Any]] = {}

        for field_name, info in self.config_fields.items():
            if info.get("is_nested_dataclass", False):
                # Flatten nested dataclass fields
                self._flatten_nested_class(
                    flat_fields, (field_name,), info, GenericConfigBuilder, ""
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
        ctx: MergeContext = MergeContext(),
    ) -> Dict[str, Any]:
        """
        Reconstruct nested dataclass instances (at any depth) from layers and CLI args.

        Args:
            config: Current configuration dictionary
            args: Parsed CLI arguments with flat nested fields
            flat_fields: Flattened field mapping from flatten()
            ctx: Merge context (default: shallow)

        Returns:
            Configuration dict with nested dataclass instances reconstructed
        """
        # CLI values as a tree keyed by path: nested_data["mid"]["inner"]["v"]
        nested_data: Dict[str, Any] = {}

        for cli_name, mapping in flat_fields.items():
            if mapping.get("parent_field"):
                self._process_nested_field(
                    nested_data, cli_name, mapping, args, config, ctx
                )

        for field_name, info in self.config_fields.items():
            if info.get("is_nested_dataclass", False):
                config[field_name] = self._reconstruct_nested_instance(
                    config.get(field_name),
                    info["type"],
                    nested_data.get(field_name, {}),
                    field_name,
                )

        return config

    # ========================================================================
    # Flatten Helper Methods
    # ========================================================================

    def _flatten_nested_class(
        self,
        flat_fields: Dict,
        path: Tuple[str, ...],
        info: Dict[str, Any],
        builder_class,
        parent_prefix: str,
    ) -> None:
        """Flatten a nested dataclass; recurse into nested dataclasses it contains."""
        nested_class = info["type"]
        prefix = parent_prefix + info["nested_prefix"]

        nested_builder = builder_class(nested_class)

        for nested_field_name, nested_info in nested_builder._config_fields.items():
            leaf_path = path + (nested_field_name,)
            if nested_info.get("is_nested_dataclass", False):
                self._flatten_nested_class(
                    flat_fields, leaf_path, nested_info, builder_class, prefix
                )
                continue

            # Build flat CLI name with the composed prefix
            flat_cli_name = self._build_flat_cli_name(nested_field_name, prefix)

            # Check for collision
            self._check_collision(flat_fields, flat_cli_name, leaf_path)

            # Add to flat fields
            flat_fields[flat_cli_name] = {
                "parent_field": path[0],
                "nested_field": nested_field_name,
                "nested_info": nested_info,
                "prefix": prefix,
                "parent_info": info,
                "path": leaf_path,
            }

    def _add_flat_field(
        self, flat_fields: Dict, field_name: str, info: Dict[str, Any]
    ) -> None:
        """Add a regular flat field to mapping."""
        cli_name = info["cli_name"]

        # Check for collision
        if cli_name in flat_fields:  # pragma: no cover
            prev_mapping = flat_fields[cli_name]
            source1 = self._get_field_source(prev_mapping)

            raise ConfigBuilderError(
                f"Field name collision detected:\n\n"
                f"  {cli_name}\n"
                f"    - {source1}\n"
                f"    - {field_name}\n\n"
                "This should not happen with non-nested fields. "
                "Please report this bug."
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
        leaf_path: Tuple[str, ...],
    ) -> None:
        """Check for CLI name collision."""
        if cli_name in flat_fields:
            prev_mapping = flat_fields[cli_name]
            source1 = self._get_field_source(prev_mapping)
            source2 = ".".join(leaf_path)
            parent_field = leaf_path[0]

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
        """Get the dotted source name from mapping."""
        return mapping_source(mapping)

    # ========================================================================
    # Reconstruct Helper Methods
    # ========================================================================

    def _process_nested_field(
        self,
        nested_data: Dict[str, Any],
        cli_name: str,
        mapping: Dict[str, Any],
        args: argparse.Namespace,
        config: Dict[str, Any],
        ctx: MergeContext = MergeContext(),
    ) -> None:
        """Process a single nested leaf from CLI args into the CLI value tree."""
        path = mapping["path"]
        nested_field = mapping["nested_field"]
        nested_info = mapping["nested_info"]

        # Read the value back from the dest the registry gave this option
        cli_value = getattr(args, cli_name_to_dest(cli_name), None)

        # The tree node holding the leaf's siblings
        parent_data = self._tree_node(nested_data, path[:-1])

        # Process the value
        if cli_value is not None:
            self._process_cli_value(
                parent_data, nested_field, nested_info, cli_value, path, config, ctx
            )

        # Handle property overrides for dict fields
        if nested_info["is_dict"]:
            self._process_dict_overrides(
                parent_data, nested_field, nested_info, mapping, args, config, ctx
            )

    @staticmethod
    def _tree_node(
        nested_data: Dict[str, Any], path: Tuple[str, ...]
    ) -> Dict[str, Any]:
        """Return (creating as needed) the CLI value tree node at `path`."""
        node = nested_data
        for key in path:
            node = node.setdefault(key, {})
        return node

    def _process_cli_value(
        self,
        parent_data: Dict,
        nested_field: str,
        nested_info: Dict[str, Any],
        cli_value: Any,
        path: Tuple[str, ...],
        config: Dict[str, Any],
        ctx: MergeContext = MergeContext(),
    ) -> None:
        """Process CLI value based on field type."""
        dotted = ".".join(path)
        if nested_info["is_list"]:
            parent_data[nested_field] = cli_value
            self._record_cli(ctx, path, cli_value)
        elif nested_info["is_dict"]:
            self._process_dict_cli_value(
                parent_data, nested_field, nested_info, cli_value, path, config, ctx
            )
        else:
            # Process file-loadable values
            try:
                processed_value = process_file_loadable_value(
                    cli_value, nested_field, nested_info
                )
                parent_data[nested_field] = processed_value
            except (ValueError, Exception) as e:
                raise ConfigurationError(
                    f"Failed to process nested field '{dotted}': {e}"
                ) from e
            self._record_cli(ctx, path, processed_value)

    @staticmethod
    def _record_cli(ctx: MergeContext, path: Tuple[str, ...], value: Any) -> None:
        """Record a CLI-supplied value for provenance (a no-op when it's off)."""
        if ctx.recorder is not None:
            ctx.recorder.record_value(CLI_LAYER, path, value)

    def _process_dict_cli_value(
        self,
        parent_data: Dict,
        nested_field: str,
        nested_info: Dict[str, Any],
        cli_value: Any,
        path: Tuple[str, ...],
        config: Dict[str, Any],
        ctx: MergeContext = MergeContext(),
    ) -> None:
        """
        Process a CLI value for a nested dict field.

        A structured-file path or a dict is combined with the layer value
        (never with the dataclass default) using the build's merge strategy:
        one-level (default) or deep. Any other string is an error for a plain
        dict field and passes through for a cli_resolve field; other values
        pass through.
        """
        loaded = self._dict_cli_value_as_dict(cli_value, nested_info, path)
        if loaded is None:
            parent_data[nested_field] = cli_value
            self._record_cli(ctx, path, cli_value)
            return

        # Provenance records what the CLI supplied (the loaded dict), not the merge
        self._record_cli(ctx, path, loaded)
        layer_value = self._layer_value(config, path)
        if isinstance(layer_value, dict):
            parent_data[nested_field] = combine_dicts(
                copy_containers(layer_value), loaded, ctx
            )
        else:
            parent_data[nested_field] = loaded

    def _dict_cli_value_as_dict(
        self, cli_value: Any, nested_info: Dict[str, Any], path: Tuple[str, ...]
    ) -> Any:
        """
        Return the dict a CLI value stands for, or None if it passes through.

        Raises:
            ConfigurationError: For a string that can't be a plain dict
                field's value, or a file that can't be loaded
        """
        if isinstance(cli_value, dict):
            return copy_containers(cli_value)
        if not isinstance(cli_value, str):
            return None
        action = dict_string_action(cli_value, is_cli_resolve(nested_info))
        if action == DictStringAction.INVALID:
            raise ConfigurationError(
                invalid_dict_string_message(cli_value, ".".join(path))
            )
        if action == DictStringAction.LOAD:
            return self._load_nested_dict_file(cli_value, path)
        return None

    @staticmethod
    def _load_nested_dict_file(path_str: str, path: Tuple[str, ...]) -> Dict[str, Any]:
        """Load a nested dict field from a structured file, wrapping failures."""
        try:
            return load_structured_file(path_str)
        except Exception as e:
            raise ConfigurationError(
                f"Failed to load dictionary config for nested field "
                f"'{'.'.join(path)}' from {path_str}: {e}"
            ) from e

    @staticmethod
    def _layer_value(config: Dict[str, Any], path: Tuple[str, ...]) -> Any:
        """
        Return the value a layer set at `path`, or MISSING.

        Walks `config` through dicts and dataclass instances; at any step where
        the value is neither, the result is MISSING.
        """
        value: Any = config
        for key in path:
            if isinstance(value, dict):
                value = value.get(key, MISSING)
            elif is_dataclass(value) and not isinstance(value, type):
                value = getattr(value, key, MISSING)
            else:
                return MISSING
        return value

    def _effective_nested_value(
        self,
        config: Dict[str, Any],
        path: Tuple[str, ...],
        nested_info: Dict[str, Any],
    ) -> Any:
        """
        Return a private copy of a nested sub-field's effective value.

        The layer value if any layer set it, otherwise a fresh dataclass
        default, otherwise MISSING.
        """
        value = self._layer_value(config, path)
        if value is MISSING:
            value = fresh_field_default(nested_info["field_obj"])
        return copy_containers(value)

    def _process_dict_overrides(
        self,
        parent_data: Dict,
        nested_field: str,
        nested_info: Dict[str, Any],
        mapping: Dict[str, Any],
        args: argparse.Namespace,
        config: Dict[str, Any],
        ctx: MergeContext = MergeContext(),
    ) -> None:
        """Process property overrides for dict fields."""
        if not nested_info.get("override_name", ""):
            return
        # Local import: field_analyzer imports this module
        from .field_analyzer import compose_override_name

        # Override option with the composed prefix, read back from its dest
        override = compose_override_name(nested_info, mapping.get("prefix", ""))
        override_value = getattr(args, cli_name_to_dest(override), None)
        if not override_value:
            return

        path = mapping["path"]
        target = self._override_target(
            parent_data, nested_field, nested_info, path, config
        )
        observer = override_observer(ctx, path, target)
        try:
            ConfigApplicator.apply_property_overrides(target, override_value, observer)
        except InvalidOverrideError as e:
            file_option = self._build_flat_cli_name(nested_field, mapping["prefix"])
            raise ConfigurationError(
                e.describe(".".join(path), override, file_option)
            ) from e
        except Exception as e:
            raise ConfigurationError(
                f"Failed to apply property overrides for nested field "
                f"'{'.'.join(path)}': {e}"
            ) from e
        parent_data[nested_field] = target

    def _override_target(
        self,
        parent_data: Dict,
        nested_field: str,
        nested_info: Dict[str, Any],
        path: Tuple[str, ...],
        config: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Choose the dict a nested property override edits.

        The value already built from the CLI if any, otherwise a copy of the
        effective value (None or no value starts empty).
        """
        if nested_field in parent_data:
            target = parent_data[nested_field]
        else:
            target = self._effective_nested_value(config, path, nested_info)
        if target is None or target is MISSING:
            return {}
        if not isinstance(target, dict):
            raise ConfigurationError(
                f"Cannot apply property overrides to field "
                f"'{'.'.join(path)}': "
                f"value is already a {type(target).__name__}, not a dict."
            )
        return target

    def _reconstruct_nested_instance(
        self,
        layer_value: Any,
        nested_class: type,
        cli_subtree: Dict[str, Any],
        dotted: str,
    ) -> Any:
        """
        Reconstruct a nested dataclass instance, recursing into nested sub-fields.

        Args:
            layer_value: What the layers hold for this level (dict, instance,
                None or absent)
            nested_class: The dataclass to build
            cli_subtree: CLI values for this level, keyed by field name (nested
                sub-fields hold their own subtree)
            dotted: Dotted path of this field, for error messages

        Returns:
            An instance of `nested_class`

        Raises:
            ConfigurationError: If the layer value has an invalid type or the
                instance cannot be created
        """
        values = self._layer_to_values(layer_value, nested_class, dotted)

        for name, info in self._class_fields(nested_class).items():
            if info.get("is_nested_dataclass", False):
                sub_tree = cli_subtree.get(name, {})
                if name in values or sub_tree:
                    values[name] = self._reconstruct_nested_instance(
                        values.get(name), info["type"], sub_tree, f"{dotted}.{name}"
                    )
            elif name in cli_subtree:
                values[name] = cli_subtree[name]

        missing = missing_required_fields(nested_class, values)
        if missing:
            raise ConfigurationError(
                f"Failed to create nested dataclass {nested_class.__name__} "
                f"for field '{dotted}': {describe_missing(missing)}"
            )
        try:
            return nested_class(**values)
        except Exception as e:
            raise ConfigurationError(
                f"Failed to create nested dataclass {nested_class.__name__} "
                f"for field '{dotted}': {e}"
            ) from e

    @staticmethod
    def _layer_to_values(
        layer_value: Any, nested_class: type, dotted: str
    ) -> Dict[str, Any]:
        """
        Turn a layer value into a private dict of constructor values.

        Containers are copied; sub-instances are kept (and rebuilt by the caller
        when they are nested fields), never deep-copied or flattened to dicts.
        """
        if layer_value is None:
            return {}
        if isinstance(layer_value, dict):
            return dict(layer_value)
        if is_dataclass(layer_value) and not isinstance(layer_value, type):
            return {
                f.name: copy_containers(getattr(layer_value, f.name))
                for f in fields(nested_class)
                if f.init
            }
        raise ConfigurationError(
            f"Nested field '{dotted}' expects a dict or "
            f"{nested_class.__name__} instance, got {type(layer_value).__name__}"
        )

    @staticmethod
    def _class_fields(nested_class: type) -> Dict[str, Dict[str, Any]]:
        """Analyze the CLI-visible fields of a nested dataclass."""
        # Import here to avoid circular dependency
        from .field_analyzer import FieldAnalyzer

        return FieldAnalyzer(nested_class).analyze_config_fields()
