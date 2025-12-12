"""
Generic configuration builder for dataclass types from CLI arguments.

Provides type-aware parsing of command-line arguments and merging
with optional base configuration files for any dataclass.
"""

import argparse
import json
import sys
from dataclasses import MISSING, fields, is_dataclass
from typing import Any, Callable, Dict, List, Optional, Type, Union

# Import typing utilities with Python 3.8+ compatibility
try:
    from typing import (  # type: ignore[attr-defined,no-redef]
        get_args,
        get_origin,
        get_type_hints,
    )
except ImportError:
    from typing_extensions import get_args, get_origin, get_type_hints  # type: ignore[assignment,no-redef]  # noqa: E501

from .annotations import (
    get_cli_append_max_args,
    get_cli_append_metavar,
    get_cli_append_min_args,
    get_cli_append_nargs,
    get_cli_choices,
    get_cli_help,
    get_cli_nested_prefix,
    get_cli_positional_metavar,
    get_cli_positional_nargs,
    get_cli_short,
    is_cli_append,
    is_cli_excluded,
    is_cli_nested,
    is_cli_positional,
)
from .append_action import RangeAppendAction
from .exceptions import ConfigBuilderError, ConfigurationError
from .file_loading import process_file_loadable_value
from .formatter import RangeAppendHelpFormatter
from .utils import load_structured_file

# Type alias for base_configs parameter
BaseConfigInput = Union[str, Dict[str, Any], List[Union[str, Dict[str, Any]]]]


class GenericConfigBuilder:
    """
    Builds dataclass instances from CLI arguments and optional base config file.

    Supports any dataclass type with:
    - Optional base config file loading
    - Type-aware CLI argument parsing
    - List parameter accumulation
    - Object parameter file loading with property overrides
    - File-loadable string parameters via '@' prefix
    - Hierarchical merging of configuration sources
    - Field filtering via cli_exclude() annotations
    - Append action for repeatable options
    """

    def __init__(
        self,
        config_class: Type,
        description: Optional[str] = None,
    ):
        """
        Initialize builder for a specific dataclass type.

        Args:
            config_class: Dataclass type to build configurations for
            description: Optional description for ArgumentParser help text.
                        If not provided, uses "Build {ClassName} from CLI"

        Raises:
            ConfigBuilderError: If config_class is not a dataclass
        """
        if not is_dataclass(config_class):
            raise ConfigBuilderError(
                f"config_class must be a dataclass, got {config_class}"
            )

        self.config_class = config_class
        self.description = description
        self._config_fields = self._analyze_config_fields()

        # Validate nested dataclass field name collisions
        self._validate_nested_collisions()

        # Validate short option collisions (for nested fields with no prefix)
        self._validate_short_option_collisions()

    def _should_include_field(
        self, field_name: str, field_info: Dict[str, Any]
    ) -> bool:
        """Determine if a field should be included in CLI arguments."""

        # Apply annotation filter
        if is_cli_excluded(field_info):
            return False

        # Default: include all fields
        return True

    def _analyze_config_fields(self) -> Dict[str, Dict[str, Any]]:
        """Analyze dataclass fields for type information."""
        fields_info = {}
        type_hints = get_type_hints(self.config_class)

        for field_obj in fields(self.config_class):
            field_type = type_hints.get(field_obj.name, field_obj.type)
            origin = get_origin(field_type)
            args = get_args(field_type)

            # Determine field category
            is_optional = origin is Union and type(None) in args
            if is_optional:
                # Extract the non-None type from Optional[T]
                field_type = next(arg for arg in args if arg is not type(None))
                origin = get_origin(field_type)
                args = get_args(field_type)

            is_list = origin is list
            is_dict = origin is dict

            # Check if this is a nested dataclass with cli_nested annotation
            is_nested_dataclass = False
            nested_prefix = None
            if is_dataclass(field_type):
                # Check if it has cli_nested annotation
                temp_info = {"field_obj": field_obj}
                is_nested_dataclass = is_cli_nested(temp_info)

                if is_nested_dataclass:
                    # Determine prefix
                    prefix_value = get_cli_nested_prefix(temp_info)
                    if prefix_value is None:
                        # Auto-prefix with field name
                        nested_prefix = f"{field_obj.name}-"
                    elif prefix_value == "":
                        # No prefix (flatten completely)
                        nested_prefix = ""
                    else:
                        # Custom prefix (ensure it ends with hyphen for consistency)
                        nested_prefix = (
                            f"{prefix_value}-"
                            if not prefix_value.endswith("-")
                            else prefix_value
                        )

            # Extract default value or factory
            has_default = field_obj.default is not MISSING
            has_default_factory = field_obj.default_factory is not MISSING
            default_value = None
            if has_default:
                default_value = field_obj.default
            elif has_default_factory and callable(field_obj.default_factory):
                # Call factory to get default value
                default_value = field_obj.default_factory()

            field_info = {
                "type": field_type,
                "origin": origin,
                "args": args,
                "is_optional": is_optional,
                "is_list": is_list,
                "is_dict": is_dict,
                "is_nested_dataclass": is_nested_dataclass,
                "nested_prefix": nested_prefix,
                "default": default_value,
                "has_default": has_default or has_default_factory,
                "cli_name": self._field_to_cli_name(field_obj.name),
                "override_name": self._field_to_override_name(field_obj.name),
                "field_obj": field_obj,  # Include field object for metadata access
            }

            # Only include field if it passes filtering
            if self._should_include_field(field_obj.name, field_info):
                fields_info[field_obj.name] = field_info

        # Validate positional arguments
        self._validate_positional_arguments(fields_info)

        return fields_info

    def _validate_positional_arguments(
        self, fields_info: Dict[str, Dict[str, Any]]
    ) -> None:
        """
        Validate positional argument constraints.

        Rules:
        1. At most ONE positional field can use nargs='*' or '+'
        2. If present, positional list must be the LAST positional argument

        Raises:
            ConfigBuilderError: If validation fails
        """
        positional_fields = []
        positional_list_fields = []

        for field_name, info in fields_info.items():
            if is_cli_positional(info):
                positional_fields.append((field_name, info))

                nargs = get_cli_positional_nargs(info)
                # Check if this is a "list" positional (greedy)
                if nargs in ("*", "+"):
                    positional_list_fields.append((field_name, nargs))

        # Rule 1: At most one positional list
        if len(positional_list_fields) > 1:
            field_names = [
                f"'{name}' (nargs='{nargs}')" for name, nargs in positional_list_fields
            ]
            raise ConfigBuilderError(
                f"Only one positional list argument allowed, found {len(positional_list_fields)}: "
                f"{', '.join(field_names)}. Use optional lists with flags for additional lists:\n"
                f"  Example: field: List[str] = cli_short('f')  # Use --field instead"
            )

        # Rule 2: Positional list must be last
        if positional_list_fields:
            list_field_name, list_nargs = positional_list_fields[0]
            list_field_index = next(
                i
                for i, (name, _) in enumerate(positional_fields)
                if name == list_field_name
            )

            # Check if there are any positionals after the list
            if list_field_index < len(positional_fields) - 1:
                later_fields = [
                    name for name, _ in positional_fields[list_field_index + 1 :]
                ]
                raise ConfigBuilderError(
                    f"Positional list argument '{list_field_name}' (nargs='{list_nargs}') must be last.\n"
                    f"Found positional argument(s) after it: {', '.join([repr(f) for f in later_fields])}.\n"
                    f"Consider making them optional arguments with flags:\n"
                    f"  Example: {later_fields[0]}: str = cli_short('{later_fields[0][0]}', default='value')"
                )

    def _field_to_cli_name(self, field_name: str) -> str:
        """Convert field name to CLI argument name."""
        return "--" + field_name.replace("_", "-")

    def _field_to_override_name(self, field_name: str) -> str:
        """Convert field name to override argument name."""
        # Use abbreviation for override arguments
        words = field_name.split("_")
        if len(words) == 1:
            return "--" + field_name[0]
        else:
            return "--" + "".join(word[0] for word in words if word)

    def _flatten_nested_fields(self) -> Dict[str, Any]:
        """
        Flatten nested dataclass fields into a single namespace.

        Returns:
            Dict mapping flat CLI names to their metadata including:
            - parent_field: Name of parent field (None for flat fields)
            - nested_field: Name of field in nested dataclass (None for flat fields)
            - nested_info: Field info from nested dataclass
            - prefix: Prefix used for this nested field
            - field_info: Field info for flat fields
        """
        flat_fields: Dict[str, Dict[str, Any]] = {}

        for field_name, info in self._config_fields.items():
            if info.get("is_nested_dataclass", False):
                # This is a nested dataclass - flatten its fields
                nested_class = info["type"]
                prefix = info["nested_prefix"]

                # Recursively analyze nested dataclass fields
                nested_builder = GenericConfigBuilder(nested_class)

                for (
                    nested_field_name,
                    nested_info,
                ) in nested_builder._config_fields.items():
                    # Build flat CLI name with prefix
                    if prefix == "":
                        # No prefix - flatten completely
                        flat_cli_name = f"--{nested_field_name.replace('_', '-')}"
                    else:
                        # With prefix
                        flat_cli_name = (
                            f"--{prefix}{nested_field_name.replace('_', '-')}"
                        )

                    # Check for collision before adding
                    if flat_cli_name in flat_fields:
                        # Collision detected - build error now
                        prev_mapping = flat_fields[flat_cli_name]
                        if prev_mapping.get("parent_field"):
                            source1 = f"{prev_mapping['parent_field']}.{prev_mapping['nested_field']}"
                        else:
                            source1 = prev_mapping["field_name"]
                        source2 = f"{field_name}.{nested_field_name}"

                        raise ConfigBuilderError(
                            f"Field name collision detected when flattening nested dataclasses:\n\n"
                            f"  {flat_cli_name}\n"
                            f"    - {source1}\n"
                            f"    - {source2}\n\n"
                            f"Solutions:\n"
                            f"  1. Add prefix to nested fields:\n"
                            f"     {field_name}: {nested_class.__name__} = cli_nested(prefix='n')\n"
                            f"  2. Rename conflicting fields\n"
                            f"  3. Use auto-prefix (don't specify prefix='')"
                        )

                    flat_fields[flat_cli_name] = {
                        "parent_field": field_name,
                        "nested_field": nested_field_name,
                        "nested_info": nested_info,
                        "prefix": prefix,
                        "parent_info": info,
                    }
            else:
                # Regular flat field
                cli_name = info["cli_name"]

                # Check for collision before adding
                if cli_name in flat_fields:
                    prev_mapping = flat_fields[cli_name]
                    if prev_mapping.get("parent_field"):
                        source1 = f"{prev_mapping['parent_field']}.{prev_mapping['nested_field']}"
                    else:
                        source1 = prev_mapping["field_name"]

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

        return flat_fields

    def _validate_nested_collisions(self) -> None:
        """
        Validate that there are no field name collisions when flattening nested dataclasses.

        Raises:
            ConfigBuilderError: If collisions are detected
        """
        flat_fields = self._flatten_nested_fields()

        # Check for duplicate CLI names
        cli_names: Dict[str, Dict[str, Any]] = {}
        collisions = []

        for cli_name, mapping in flat_fields.items():
            if cli_name in cli_names:
                # Collision detected
                prev_mapping = cli_names[cli_name]

                # Build descriptive collision info
                if mapping.get("parent_field"):
                    source1 = f"{mapping['parent_field']}.{mapping['nested_field']}"
                else:
                    source1 = mapping["field_name"]

                if prev_mapping.get("parent_field"):
                    source2 = (
                        f"{prev_mapping['parent_field']}.{prev_mapping['nested_field']}"
                    )
                else:
                    source2 = prev_mapping["field_name"]

                collisions.append((cli_name, source1, source2))
            else:
                cli_names[cli_name] = mapping

        if collisions:
            # Build error message
            error_lines = [
                "Field name collision detected when flattening nested dataclasses:",
                "",
            ]

            for cli_name, source1, source2 in collisions:
                error_lines.append(f"  {cli_name}")
                error_lines.append(f"    - {source1}")
                error_lines.append(f"    - {source2}")
                error_lines.append("")

            error_lines.extend(
                [
                    "Solutions:",
                    "  1. Add prefix to nested fields:",
                    "     nested: NestedClass = cli_nested(prefix='n')",
                    "  2. Rename conflicting fields",
                    "  3. Use auto-prefix (don't specify prefix='')",
                ]
            )

            raise ConfigBuilderError("\n".join(error_lines))

    def _validate_short_option_collisions(self) -> None:
        """
        Validate that there are no short option collisions when nested fields have no prefix.

        Short options are only checked for nested fields with empty prefix (prefix="").
        Nested fields with non-empty prefix do not support short options.

        Raises:
            ConfigBuilderError: If short option collisions are detected
        """
        flat_fields = self._flatten_nested_fields()

        # Map short option -> (cli_name, source_description)
        short_options: Dict[str, tuple[str, str]] = {}
        collisions = []

        for cli_name, mapping in flat_fields.items():
            if mapping.get("parent_field"):
                # Nested field - only check if no prefix
                prefix = mapping["prefix"]
                if prefix == "":
                    info = mapping["nested_info"]
                    short = get_cli_short(info)
                    if short:
                        source = f"{mapping['parent_field']}.{mapping['nested_field']}"
                        if short in short_options:
                            prev_cli_name, prev_source = short_options[short]
                            collisions.append(
                                (
                                    f"-{short}",
                                    cli_name,
                                    source,
                                    prev_cli_name,
                                    prev_source,
                                )
                            )
                        else:
                            short_options[short] = (cli_name, source)
            else:
                # Regular field
                info = mapping["field_info"]
                if not info.get("is_nested_dataclass", False):
                    short = get_cli_short(info)
                    if short:
                        source = mapping["field_name"]
                        if short in short_options:
                            prev_cli_name, prev_source = short_options[short]
                            collisions.append(
                                (
                                    f"-{short}",
                                    cli_name,
                                    source,
                                    prev_cli_name,
                                    prev_source,
                                )
                            )
                        else:
                            short_options[short] = (cli_name, source)

        if collisions:
            # Build error message
            error_lines = ["Short option collision detected:", ""]

            for short_opt, cli_name1, source1, cli_name2, source2 in collisions:
                error_lines.append(f"  {short_opt}")
                error_lines.append(f"    - {source1} ({cli_name1})")
                error_lines.append(f"    - {source2} ({cli_name2})")
                error_lines.append("")

            error_lines.extend(
                [
                    "Solutions:",
                    "  1. Remove short option from one of the fields",
                    "  2. Use different short options",
                    "  3. Add prefix to nested field:",
                    "     nested: NestedClass = cli_nested(prefix='n')",
                ]
            )

            raise ConfigBuilderError("\n".join(error_lines))

    def add_arguments(
        self,
        parser: argparse.ArgumentParser,
        base_config_name: str = "config",
        base_config_help: str = "Base configuration file (JSON, YAML, or TOML)",
    ) -> None:
        """
        Add all dataclass arguments to parser.

        Args:
            parser: ArgumentParser to add arguments to
            base_config_name: Name for base config file argument
            base_config_help: Help text for base config file argument
        """

        # Base config file argument
        parser.add_argument(f"--{base_config_name}", type=str, help=base_config_help)

        # Get flattened fields (handles nested dataclasses)
        flat_fields = self._flatten_nested_fields()

        # IMPORTANT: Add positional arguments first (argparse requirement)
        # Note: Positional arguments in nested dataclasses are not supported
        for cli_name, mapping in flat_fields.items():
            if mapping.get("parent_field"):
                # Nested field - check for unsupported positional
                info = mapping["nested_info"]
                if is_cli_positional(info):
                    raise ConfigBuilderError(
                        f"Positional arguments in nested dataclasses are not supported.\n"
                        f"Field: {mapping['parent_field']}.{mapping['nested_field']}\n"
                        f"Use regular fields or optional arguments instead."
                    )
            else:
                # Regular field
                field_name = mapping["field_name"]
                info = mapping["field_info"]
                if is_cli_positional(info):
                    self._add_positional_argument(parser, field_name, info)

        # Then add optional arguments
        for cli_name, mapping in flat_fields.items():
            if mapping.get("parent_field"):
                # Nested field - add with prefixed CLI name
                info = mapping["nested_info"]
                prefix = mapping["prefix"]
                if not is_cli_positional(info):
                    self._add_nested_field_argument(parser, cli_name, info, prefix)
            else:
                # Regular field - skip if nested dataclass
                field_name = mapping["field_name"]
                info = mapping["field_info"]
                if not is_cli_positional(info) and not info.get(
                    "is_nested_dataclass", False
                ):
                    self._add_field_argument(parser, field_name, info)

    def _add_positional_argument(
        self, parser: argparse.ArgumentParser, field_name: str, info: Dict[str, Any]
    ) -> None:
        """Add positional argument to parser."""
        # Positional arguments use the field name directly (no -- prefix)
        arg_name = field_name

        # Get nargs from metadata
        nargs = get_cli_positional_nargs(info)

        # Get metavar from metadata or default to uppercase field name
        metavar = get_cli_positional_metavar(info)
        if not metavar:
            metavar = field_name.upper()

        # Get help text
        help_text = get_cli_help(info) or f"{field_name}"

        # Get choices if specified
        choices = get_cli_choices(info)

        # Get type converter - for lists, need to convert element type
        if info["is_list"] and info["args"]:
            # Get the element type from List[T]
            element_type = info["args"][0]
            arg_type = self._get_argument_type(element_type)
        else:
            arg_type = self._get_argument_type(info["type"])

        # Build kwargs
        # Build kwargs with explicit type for mypy
        kwargs: Dict[str, Any] = {
            "help": help_text,
            "metavar": metavar,
        }

        if nargs is not None:
            kwargs["nargs"] = nargs

        if choices:
            kwargs["choices"] = choices

        # Type handling: for list-like nargs, type applies to each element
        kwargs["type"] = arg_type

        # Add default if specified and nargs allows it
        if nargs in ("?", "*"):
            default = info.get("default")
            if default is not None:
                kwargs["default"] = default

        parser.add_argument(arg_name, **kwargs)

    def _add_nested_field_argument(
        self,
        parser: argparse.ArgumentParser,
        cli_name: str,
        info: Dict[str, Any],
        prefix: str = "",
    ) -> None:
        """
        Add CLI argument for a nested dataclass field.

        Args:
            parser: ArgumentParser to add arguments to
            cli_name: Pre-computed CLI name with prefix (e.g., "--w-retry-count")
            info: Field info from nested dataclass analysis
            prefix: Prefix used for this nested field (empty string = no prefix)

        Note:
            - Positional arguments in nested fields are NOT supported
            - Short options ARE supported when prefix is empty (prefix="")
            - Short options are NOT supported when prefix is non-empty
        """
        # Get short option if prefix is empty (no prefix = allow short options)
        short_option = None
        if prefix == "":
            short_option = get_cli_short(info)

        # Build argument names list
        arg_names = []
        if short_option:
            arg_names.append(f"-{short_option}")
        arg_names.append(cli_name)

        # Special handling for boolean fields
        if info["type"] == bool:
            # Extract field name from cli_name (remove -- prefix and convert to snake_case)
            field_name = cli_name.lstrip("-").replace("-", "_")
            # Need to update info with the prefixed cli_name
            nested_info = dict(info)
            nested_info["cli_name"] = cli_name
            self._add_boolean_argument(parser, field_name, nested_info)
            return

        # Get custom help text from annotations or use default
        custom_help = get_cli_help(info)
        help_text = custom_help if custom_help else f"nested field"

        # Get restricted choices if specified
        choices = get_cli_choices(info)
        if choices:
            choices_str = ", ".join(str(c) for c in choices)
            if help_text:
                help_text += f" (choices: {choices_str})"
            else:
                help_text = f"choices: {choices_str}"

        # Check if this is an append field
        if is_cli_append(info):
            # For append fields, use arg_names
            self._add_append_argument(parser, arg_names, info, help_text, choices)
            return

        if info["is_list"]:
            # List parameters accept multiple values after a single flag
            if info["is_optional"]:
                nargs_val = "*"
                help_text += " (specify zero or more values)"
            else:
                nargs_val = "+"
                help_text += " (specify one or more values)"

            parser.add_argument(
                *arg_names, nargs=nargs_val, choices=choices, help=help_text
            )
        elif info["is_dict"]:
            # Dict parameters are file paths
            dict_help = (
                f"{help_text} configuration file path"
                if help_text
                else "configuration file path"
            )
            parser.add_argument(*arg_names, type=str, help=dict_help)

            # Add override argument for dict fields in nested dataclasses
            # Calculate override name with same prefix logic as main argument
            if prefix == "":
                # No prefix - use override_name from info directly
                override_name = info.get("override_name", "")
            else:
                # With prefix - apply prefix to the override abbreviation
                # info["override_name"] is like "--mc" (abbreviation from nested field)
                base_override = info.get("override_name", "").lstrip("--")
                if base_override:
                    override_name = f"--{prefix}{base_override}"
                else:
                    # Fallback shouldn't happen, but handle it
                    override_name = f"--{prefix}override"

            if override_name:
                override_help = (
                    f"{help_text} property override (format: key.path:value)"
                    if help_text
                    else "property override (format: key.path:value)"
                )
                parser.add_argument(
                    override_name,
                    action="append",
                    help=override_help,
                )
        else:
            # Simple scalar parameters
            arg_type = self._get_argument_type(info["type"])
            parser.add_argument(
                *arg_names, type=arg_type, choices=choices, help=help_text
            )

    def _add_field_argument(
        self, parser: argparse.ArgumentParser, field_name: str, info: Dict[str, Any]
    ) -> None:
        """Add CLI argument for a specific config field."""
        # Special handling for boolean fields
        if info["type"] == bool:
            self._add_boolean_argument(parser, field_name, info)
            return

        cli_name = info["cli_name"]

        # Get short option from metadata
        short_option = get_cli_short(info)

        # Build argument names list
        arg_names = []
        if short_option:
            arg_names.append(f"-{short_option}")  # Short comes first: -n
        arg_names.append(cli_name)  # Then long: --name

        # Get custom help text from annotations or use default
        custom_help = get_cli_help(info)
        help_text = custom_help if custom_help else f"{field_name}"

        # Get restricted choices if specified
        choices = get_cli_choices(info)
        if choices:
            # Add choices hint to help text
            choices_str = ", ".join(str(c) for c in choices)
            if help_text:
                help_text += f" (choices: {choices_str})"
            else:
                help_text = f"choices: {choices_str}"

        # Check if this is an append field
        if is_cli_append(info):
            self._add_append_argument(parser, arg_names, info, help_text, choices)
            return

        if info["is_list"]:
            # List parameters accept multiple values after a single flag
            # Use nargs='+' for required lists (one or more values)
            # Use nargs='*' for optional lists (zero or more values)
            if info["is_optional"]:
                nargs_val = "*"  # Zero or more values for Optional[List[T]]
                help_text += " (specify zero or more values)"
            else:
                nargs_val = "+"  # One or more values for List[T]
                help_text += " (specify one or more values)"

            parser.add_argument(
                *arg_names, nargs=nargs_val, choices=choices, help=help_text
            )
        elif info["is_dict"]:
            # Dict parameters are file paths
            dict_help = (
                f"{help_text} configuration file path"
                if help_text
                else "configuration file path"
            )
            parser.add_argument(*arg_names, type=str, help=dict_help)
            # Add override argument for dict fields (no short form for overrides)
            override_help = (
                f"{help_text} property override (format: key.path:value)"
                if help_text
                else "property override (format: key.path:value)"
            )
            parser.add_argument(
                info["override_name"],
                action="append",
                help=override_help,
            )
        else:
            # Simple scalar parameters
            arg_type = self._get_argument_type(info["type"])
            parser.add_argument(
                *arg_names, type=arg_type, choices=choices, help=help_text
            )

    def _add_append_argument(
        self,
        parser: argparse.ArgumentParser,
        arg_names: List[str],
        info: Dict[str, Any],
        help_text: str,
        choices: Optional[List[Any]],
    ) -> None:
        """
        Add append-action argument to parser.

        Supports repeated options where each occurrence collects its arguments.

        Args:
            parser: ArgumentParser to add arguments to
            arg_names: List of argument names (short and/or long form)
            info: Field information dictionary
            help_text: Help text for the argument
            choices: Optional list of valid choices
        """
        # Get nargs from metadata
        append_nargs = get_cli_append_nargs(info)

        # Get metavar from metadata
        metavar = get_cli_append_metavar(info)

        # Get min/max args from metadata
        min_args = get_cli_append_min_args(info)
        max_args = get_cli_append_max_args(info)

        # If min/max specified, override nargs to '+' for flexible parsing
        # Validation happens later in build_config()
        if min_args is not None and max_args is not None:
            append_nargs = "+"

        # Get type converter
        # For List[T], use T as the type
        # For List[List[T]], use T as the type (inner list handled by nargs)
        if info["is_list"] and info["args"]:
            element_type = info["args"][0]
            # Check if it's List[List[T]]
            element_origin = get_origin(element_type)
            if element_origin is list:
                # List[List[T]] - get inner type T
                element_args = get_args(element_type)
                if element_args:
                    arg_type = self._get_argument_type(element_args[0])
                else:
                    arg_type = str
            else:
                # List[T] - use T directly
                arg_type = self._get_argument_type(element_type)
        else:
            arg_type = self._get_argument_type(info["type"])

        # Build kwargs for argparse
        # Use custom action for min/max to enable clean metavar display
        if min_args is not None and max_args is not None:
            kwargs: Dict[str, Any] = {
                "action": RangeAppendAction,
                "type": arg_type,
                "help": help_text
                + f" (can be repeated, {min_args}-{max_args} args each)",
            }
        else:
            kwargs = {
                "action": "append",
                "type": arg_type,
                "help": help_text + " (can be repeated)",
            }

        if append_nargs is not None:
            kwargs["nargs"] = append_nargs

        if metavar is not None:
            kwargs["metavar"] = metavar

        if choices:
            kwargs["choices"] = choices

        # Add default
        default = info.get("default")
        if default is not None:
            kwargs["default"] = default

        parser.add_argument(*arg_names, **kwargs)

    def _add_boolean_argument(
        self, parser: argparse.ArgumentParser, field_name: str, info: Dict[str, Any]
    ) -> None:
        """Add boolean argument with positive and negative forms."""
        cli_name = info["cli_name"]
        dest_name = field_name.replace("-", "_")

        # Get short option from metadata
        short_option = get_cli_short(info)

        # Build argument names for positive form
        positive_args = []
        if short_option:
            positive_args.append(f"-{short_option}")
        positive_args.append(cli_name)

        # Get custom help text
        custom_help = get_cli_help(info)
        help_text = custom_help if custom_help else field_name

        # Get default value
        default_value = info.get("default", False)

        # Add positive form (--flag or -f)
        parser.add_argument(
            *positive_args,
            action="store_true",
            dest=dest_name,
            default=argparse.SUPPRESS,
            help=f"{help_text} (default: {default_value})",
        )

        # Add negative form (--no-flag)
        negative_name = f"--no-{field_name.replace('_', '-')}"
        parser.add_argument(
            negative_name,
            action="store_false",
            dest=dest_name,
            default=argparse.SUPPRESS,
            help=f"Disable {help_text}",
        )

    def _get_argument_type(self, field_type: Type) -> Callable[[str], Any]:
        """Get appropriate argparse type for field type."""
        # Note: bool is handled separately in _add_boolean_argument
        if field_type in (int, float, str):
            return field_type
        else:
            # For complex types, use string and let validation handle it
            return str

    def _validate_append_ranges(self, config_dict: Dict[str, Any]) -> None:
        """
        Validate min/max argument counts for append fields.

        Args:
            config_dict: Configuration dictionary after CLI parsing

        Raises:
            ConfigurationError: If any append field violates min/max constraints
        """
        for field_name, info in self._config_fields.items():
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
                # Normalize to list
                if not isinstance(occurrence, list):
                    occurrence = [occurrence]

                arg_count = len(occurrence)

                if arg_count < min_args:
                    raise ConfigurationError(
                        f"Field '{field_name}' occurrence #{i+1}: "
                        f"Expected at least {min_args} argument(s), got {arg_count}. "
                        f"Each occurrence must have between {min_args} and {max_args} argument(s)."
                    )

                if arg_count > max_args:
                    raise ConfigurationError(
                        f"Field '{field_name}' occurrence #{i+1}: "
                        f"Expected at most {max_args} argument(s), got {arg_count}. "
                        f"Each occurrence must have between {min_args} and {max_args} argument(s)."
                    )

    def build_config(
        self,
        args: argparse.Namespace,
        base_config_name: str = "config",
        base_configs: Optional[BaseConfigInput] = None,
    ) -> Any:
        """
        Build dataclass instance from parsed CLI arguments with hierarchical config merging.

        Configuration sources are merged in the following order (later sources override earlier):
        1. Programmatic base_configs (if provided) - files loaded and applied in order
        2. Config file from --config argument (if provided)
        3. CLI argument overrides

        Args:
            args: Parsed CLI arguments from argparse
            base_config_name: Name of the base config file argument (default: "config")
            base_configs: Optional base configuration(s) to apply before --config file.
                         Can be:
                         - str: Path to a single config file
                         - dict: A single configuration dictionary
                         - List[Union[str, dict]]: Multiple configs (files and/or dicts) applied in order

        Returns:
            Instance of the configured dataclass type

        Raises:
            ConfigurationError: If configuration is invalid or files cannot be loaded

        Example:
            # Single file path
            config = builder.build_config(args, base_configs='defaults.yaml')

            # Single dict
            config = builder.build_config(args, base_configs={'debug': True})

            # Mixed list
            config = builder.build_config(
                args,
                base_configs=[
                    'base.yaml',              # Load file
                    {'env': 'staging'},       # Use dict
                    'overrides.json',         # Load file
                ]
            )
        """

        # Stage 1: Normalize and apply base configs
        normalized_configs = self._normalize_base_configs(base_configs)
        config_dict = self._apply_base_configs(normalized_configs)

        # Stage 2: Apply config file from --config argument
        config_dict = self._apply_config_file(config_dict, args, base_config_name)

        # Stage 3: Apply CLI argument overrides
        config_dict = self._apply_cli_overrides(config_dict, args)

        # Stage 3.5: Reconstruct nested dataclass instances
        config_dict = self._reconstruct_nested_fields(config_dict, args)

        # Stage 3.75: Validate append field ranges (if min_args/max_args specified)
        self._validate_append_ranges(config_dict)
        # Stage 4: Create and return dataclass instance
        try:
            return self.config_class(**config_dict)
        except Exception as e:
            raise ConfigurationError(
                f"Failed to create {self.config_class.__name__}: {e}"
            ) from e

    def _normalize_base_configs(
        self, base_configs: Optional[BaseConfigInput]
    ) -> List[Dict[str, Any]]:
        """
        Normalize base_configs input to list of dicts.

        Accepts:
        - None: Returns empty list
        - str: Load file, return list with one dict
        - dict: Return list with one dict
        - list: Process each element (load files, keep dicts)

        Args:
            base_configs: Configuration input in various formats

        Returns:
            List of configuration dictionaries

        Raises:
            ConfigurationError: If file cannot be loaded or invalid type
        """
        if base_configs is None:
            return []

        # Single string path
        if isinstance(base_configs, str):
            try:
                return [load_structured_file(base_configs)]
            except Exception as e:
                raise ConfigurationError(
                    f"Failed to load base_configs from '{base_configs}': {e}"
                ) from e

        # Single dict
        if isinstance(base_configs, dict):
            return [base_configs]

        # List of strings and/or dicts
        if isinstance(base_configs, list):
            result = []
            for i, item in enumerate(base_configs):
                if isinstance(item, str):
                    try:
                        result.append(load_structured_file(item))
                    except Exception as e:
                        raise ConfigurationError(
                            f"Failed to load base_configs[{i}] from '{item}': {e}"
                        ) from e
                elif isinstance(item, dict):
                    result.append(item)
                else:
                    raise ConfigurationError(
                        f"base_configs[{i}] must be str or dict, got {type(item).__name__}"
                    )
            return result

        raise ConfigurationError(
            f"base_configs must be str, dict, or list, got {type(base_configs).__name__}"
        )

    def _apply_base_configs(self, base_configs: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Apply base configuration dictionaries in order.

        Args:
            base_configs: List of configuration dictionaries to merge in order

        Returns:
            Merged configuration dictionary

        Note:
            Each config in the list is applied sequentially with shallow merge.
            Later configs override earlier ones.
        """
        config = {}

        for base_config in base_configs:
            if not isinstance(base_config, dict):
                raise ConfigurationError(
                    f"base_configs must contain dictionaries, got {type(base_config)}"
                )
            # Shallow merge: later configs override earlier ones
            config.update(base_config)

        return config

    def _apply_config_file(
        self,
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
                # Merge file config into existing config (file overrides base_configs)
                config.update(file_config)
            except Exception as e:
                raise ConfigurationError(
                    f"Failed to load config file '{base_config_value}': {e}"
                ) from e

        return config

    def _reconstruct_nested_fields(
        self, config: Dict[str, Any], args: argparse.Namespace
    ) -> Dict[str, Any]:
        """
        Reconstruct nested dataclass instances from flat CLI arguments.

        Args:
            config: Current configuration dictionary
            args: Parsed CLI arguments with flat nested fields

        Returns:
            Configuration dict with nested dataclass instances reconstructed
        """
        # Get flattened field mapping
        flat_fields = self._flatten_nested_fields()

        # Group nested fields by parent
        nested_data: Dict[str, Dict[str, Any]] = {}

        for cli_name, mapping in flat_fields.items():
            if mapping.get("parent_field"):
                # This is a nested field
                parent_field = mapping["parent_field"]
                nested_field = mapping["nested_field"]
                nested_info = mapping["nested_info"]

                # Convert CLI name to arg name (remove -- and convert to underscores)
                arg_name = cli_name.lstrip("-").replace("-", "_")
                cli_value = getattr(args, arg_name, None)

                # Initialize nested data dict for this parent if needed
                if parent_field not in nested_data:
                    nested_data[parent_field] = {}

                # Process the value
                if cli_value is not None:
                    if nested_info["is_list"]:
                        nested_data[parent_field][nested_field] = cli_value
                    elif nested_info["is_dict"]:
                        # Load dict from file
                        try:
                            dict_config = load_structured_file(cli_value)
                            nested_data[parent_field][nested_field] = dict_config
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
                            nested_data[parent_field][nested_field] = processed_value
                        except (ValueError, Exception) as e:
                            raise ConfigurationError(
                                f"Failed to process nested field "
                                f"'{parent_field}.{nested_field}': {e}"
                            ) from e

        # Now reconstruct nested dataclass instances
        for field_name, info in self._config_fields.items():
            if info.get("is_nested_dataclass", False):
                nested_class = info["type"]

                # Start with existing config value (from base configs or defaults)
                if field_name in config and config[field_name] is not None:
                    # Convert existing instance to dict if needed
                    if is_dataclass(config[field_name]):
                        from dataclasses import asdict

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
                    config[field_name] = nested_class(**existing_dict)
                except Exception as e:
                    raise ConfigurationError(
                        f"Failed to create nested dataclass {nested_class.__name__} "
                        f"for field '{field_name}': {e}"
                    ) from e

        return config

    def _apply_cli_overrides(
        self, config: Dict[str, Any], args: argparse.Namespace
    ) -> Dict[str, Any]:
        """
        Apply CLI argument overrides to configuration.

        Args:
            config: Current configuration dictionary
            args: Parsed CLI arguments

        Returns:
            Final configuration dictionary with CLI overrides applied

        Raises:
            ConfigurationError: If CLI argument processing fails

        Note:
            Only processes fields included in the dataclass (not excluded).
            Handles special cases: lists, dicts, file-loadable fields, property overrides, append actions.
        """
        # Only process fields that were included in CLI
        # Skip nested dataclass fields (handled by _reconstruct_nested_fields)
        for field_name, info in self._config_fields.items():
            if info.get("is_nested_dataclass", False):
                continue
            # Convert CLI arg name back to field name
            arg_name = field_name.replace("-", "_")
            cli_value = getattr(args, arg_name, None)

            # Get override argument name for dict fields
            override_arg_name = info["override_name"][2:].replace("-", "_")
            override_value = getattr(args, override_arg_name, None)

            if cli_value is not None:
                if info["is_list"]:
                    # CLI values replace config values (standard argparse behavior)
                    # With nargs='+' or '*', cli_value is already a list
                    # With action='append', cli_value is a list of sub-lists (if nargs specified) or list of values
                    config[field_name] = cli_value
                elif info["is_dict"]:
                    # For dicts, load from file and merge with existing dict
                    try:
                        dict_config = load_structured_file(cli_value)
                        existing = config.get(field_name, {})
                        if isinstance(existing, dict):
                            existing.update(dict_config)
                            config[field_name] = existing
                        else:
                            config[field_name] = dict_config
                    except Exception as e:
                        raise ConfigurationError(
                            f"Failed to load dictionary config for field '{field_name}' from {cli_value}: {e}"
                        ) from e
                else:
                    # Simple override - check for file-loadable fields
                    try:
                        processed_value = process_file_loadable_value(
                            cli_value, field_name, info
                        )
                        config[field_name] = processed_value
                    except (ValueError, Exception) as e:
                        raise ConfigurationError(
                            f"Failed to process field '{field_name}': {e}"
                        ) from e

            # Apply property overrides for dict fields
            if info["is_dict"] and override_value:
                if field_name not in config:
                    config[field_name] = {}
                try:
                    self._apply_property_overrides(config[field_name], override_value)
                except Exception as e:
                    raise ConfigurationError(
                        f"Failed to apply property overrides for field '{field_name}': {e}"
                    ) from e

        return config

    def _apply_property_overrides(
        self, target_dict: Dict[str, Any], overrides: List[str]
    ) -> None:
        """Apply property path overrides to target dictionary."""
        for override in overrides:
            if ":" not in override:
                raise ValueError(
                    f"Invalid override format: {override} (expected key.path:value)"
                )

            path, value = override.split(":", 1)
            self._set_nested_property(target_dict, path, self._parse_value(value))

    def _set_nested_property(
        self, target: Dict[str, Any], path: str, value: Any
    ) -> None:
        """Set nested property using dot notation."""
        keys = path.split(".")
        current = target

        # Navigate to parent of target key
        for key in keys[:-1]:
            if key not in current:
                current[key] = {}
            current = current[key]

        # Set final value
        current[keys[-1]] = value

    def _parse_value(self, value_str: str) -> Any:
        """Parse string value to appropriate type."""
        # Try to parse as JSON first (handles numbers, booleans, etc.)
        try:
            return json.loads(value_str)
        except json.JSONDecodeError:
            # Return as string if not valid JSON
            return value_str


# Convenience functions


def build_config_from_cli(
    config_class: Type,
    args: Optional[List[str]] = None,
    base_config_name: str = "config",
    base_configs: Optional[BaseConfigInput] = None,
    description: Optional[str] = None,
) -> Any:
    """
    Build dataclass instance from CLI arguments with optional base configs.

    Configuration sources are merged in the following order (later sources override earlier):
    1. base_configs (if provided) - files loaded and applied in order
    2. Config file from --config argument (if provided)
    3. CLI argument overrides

    Args:
        config_class: Dataclass type to build
        args: Command-line arguments (defaults to sys.argv[1:])
        base_config_name: Name for base config file argument (default: "config")
        base_configs: Optional base configuration(s). Can be:
                     - str: Path to a single config file
                     - dict: A single configuration dictionary
                     - List[Union[str, dict]]: Multiple configs applied in order
        description: Optional description for ArgumentParser help text.
                    If not provided, uses "Build {ClassName} from CLI"

    Returns:
        Instance of config_class built from merged configurations

    Example:
        # Single file
        config = build_config_from_cli(MyConfig, base_configs='defaults.yaml')

        # Single dict
        config = build_config_from_cli(MyConfig, base_configs={'debug': True})

        # With custom description
        config = build_config_from_cli(
            MyConfig,
            description="Configure the application server"
        )

        # Mixed list
        config = build_config_from_cli(
            MyConfig,
            args=['--config', 'prod.yaml', '--name', 'override'],
            base_configs=[
                'company-defaults.yaml',
                {'team': 'platform'},
                'env-staging.json',
            ]
        )
    """
    if args is None:
        args = sys.argv[1:]

    builder = GenericConfigBuilder(config_class, description=description)

    desc = (
        builder.description
        if builder.description is not None
        else f"Build {config_class.__name__} from CLI"
    )
    parser = argparse.ArgumentParser(
        description=desc, formatter_class=RangeAppendHelpFormatter
    )
    builder.add_arguments(parser, base_config_name)

    parsed_args = parser.parse_args(args)
    return builder.build_config(parsed_args, base_config_name, base_configs)


def build_config(
    config_class: Type,
    args: Optional[List[str]] = None,
    base_configs: Optional[BaseConfigInput] = None,
    description: Optional[str] = None,
) -> Any:
    """
    Simplified convenience function to build dataclass from CLI arguments.

    Configuration sources are merged in the following order (later sources override earlier):
    1. base_configs (if provided) - files loaded and applied in order
    2. Config file from --config argument (if provided)
    3. CLI argument overrides

    Args:
        config_class: Dataclass type to build
        args: Command-line arguments (defaults to sys.argv[1:])
        base_configs: Optional base configuration(s). Can be:
                     - str: Path to a single config file
                     - dict: A single configuration dictionary
                     - List[Union[str, dict]]: Multiple configs applied in order
        description: Optional description for ArgumentParser help text.
                    If not provided, uses "Build {ClassName} from CLI"

    Returns:
        Instance of config_class built from merged configurations

    Example:
        # Simple usage
        config = build_config(Config)

        # With base config file
        config = build_config(Config, base_configs='defaults.yaml')

        # With custom description
        config = build_config(
            Config,
            description="My application configuration tool"
        )

        # With mixed sources
        config = build_config(
            Config,
            args=['--count', '100'],
            base_configs=[
                'base.yaml',
                {'environment': 'prod'},
            ]
        )
    """
    return build_config_from_cli(
        config_class, args, base_configs=base_configs, description=description
    )
