"""
Argparse argument registration from analyzed field information.

This module translates field_info dictionaries (produced by FieldAnalyzer)
into argparse arguments. Each field type maps to a specific argparse pattern:

    Field Type          → argparse Pattern
    ─────────────────────────────────────────────────
    bool                → --flag / --no-flag (BooleanOptionalAction-like)
    str, int, float     → --name VALUE (with type= converter)
    List[T]             → --name V1 V2 V3 (nargs='+')
    List[T] + append    → --name V (action='append', repeatable)
    Dict[str, Any]      → --name FILE + --abbrev KEY:VALUE (property overrides)
    positional          → VALUE (no -- prefix, position-based)
    nested dataclass    → flattened with prefix: --prefix-field

Data Flow:
    field_info dicts (from FieldAnalyzer)
        → add_arguments(parser)
            → Positional arguments added first (argparse requirement)
            → Optional arguments added second
            → Each dispatches to type-specific handler
        → Populated ArgumentParser (ready for parse_args)
"""

import argparse
from typing import (
    Any,
    Callable,
    Dict,
    List,
    Optional,
    Tuple,
    Type,
    get_args,
    get_origin,
)

from .annotations import (
    get_cli_append_max_args,
    get_cli_append_metavar,
    get_cli_append_min_args,
    get_cli_append_nargs,
    get_cli_choices,
    get_cli_help,
    get_cli_positional_metavar,
    get_cli_positional_nargs,
    get_cli_short,
    is_cli_append,
    is_cli_extend,
    is_cli_positional,
)
from .append_action import RangeAppendAction
from .exceptions import ConfigBuilderError
from .field_analyzer import FieldAnalyzer, compose_override_name
from .nested_processor import mapping_source
from .option_collisions import check_option_collisions, plan_option_strings


class _ChoicesAllowingNothing(List[Any]):
    """
    Choices for a ``nargs="*"`` positional that also accept "nothing typed".

    argparse runs its choices check on the default (or the empty list) even
    when nothing was typed, which would reject the SUPPRESS marker or ``[]``
    on every Python version. Typed values are still checked normally.
    """

    def __contains__(self, item: object) -> bool:
        return (
            item is argparse.SUPPRESS
            or (isinstance(item, list) and not item)
            or super().__contains__(item)
        )


class ArgumentRegistry:
    """
    Registers dataclass fields as CLI arguments with argparse.

    Handles:
    - Positional arguments
    - Optional arguments (short and long forms)
    - Boolean flags
    - List arguments with nargs
    - Dict arguments with file loading and property overrides
    - Append-action arguments
    """

    def __init__(
        self, field_analyzer: FieldAnalyzer, config_fields: Dict[str, Dict[str, Any]]
    ):
        """
        Initialize argument registry.

        Args:
            field_analyzer: FieldAnalyzer instance for field flattening
            config_fields: Dictionary of analyzed field information
        """
        self.field_analyzer = field_analyzer
        self.config_fields = config_fields

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

        # Get flattened fields (handles nested dataclasses)
        flat_fields = self.field_analyzer.flatten_nested_fields(self.config_fields)

        # Fail fast on any option-string clash, before registering anything
        check_option_collisions(
            plan_option_strings(
                self,
                flat_fields,
                base_config_name,
                getattr(parser, "add_help", True),
            )
        )

        # Base config file argument
        parser.add_argument(f"--{base_config_name}", type=str, help=base_config_help)

        # Add positional arguments first, then optional arguments
        self._add_positional_arguments(parser, flat_fields)
        self._add_optional_arguments(parser, flat_fields)

    def _add_positional_arguments(
        self, parser: argparse.ArgumentParser, flat_fields: Dict[str, Any]
    ) -> None:
        """
        Add positional arguments to parser.

        Args:
            parser: ArgumentParser to add arguments to
            flat_fields: Flattened field mappings
        """
        # IMPORTANT: Add positional arguments first (argparse requirement)
        # Note: Positional arguments in nested dataclasses are not supported
        for cli_name, mapping in flat_fields.items():
            if mapping.get("parent_field"):
                # Nested field - check for unsupported positional
                info = mapping["nested_info"]
                if is_cli_positional(info):
                    raise ConfigBuilderError(
                        f"Positional arguments in nested dataclasses are not supported.\n"
                        f"Field: {mapping_source(mapping)}\n"
                        f"Use regular fields or optional arguments instead."
                    )
            else:
                # Regular field
                field_name = mapping["field_name"]
                info = mapping["field_info"]
                if is_cli_positional(info):
                    self.add_positional_argument(parser, field_name, info)

    def _add_optional_arguments(
        self, parser: argparse.ArgumentParser, flat_fields: Dict[str, Any]
    ) -> None:
        """
        Add optional arguments to parser.

        Args:
            parser: ArgumentParser to add arguments to
            flat_fields: Flattened field mappings
        """
        for cli_name, mapping in flat_fields.items():
            if mapping.get("parent_field"):
                self._add_nested_optional_argument(parser, cli_name, mapping)
            else:
                self._add_flat_optional_argument(parser, mapping)

    def _add_nested_optional_argument(
        self, parser: argparse.ArgumentParser, cli_name: str, mapping: Dict[str, Any]
    ) -> None:
        """Add a nested (flattened) field as an optional argument with its prefixed name."""
        info = mapping["nested_info"]
        if is_cli_positional(info):
            return
        parent = ".".join(mapping["path"][:-1])
        self.add_argument(
            parser, mapping["nested_field"], info, cli_name, mapping["prefix"], parent
        )

    def _add_flat_optional_argument(
        self, parser: argparse.ArgumentParser, mapping: Dict[str, Any]
    ) -> None:
        """Add a regular field as an optional argument (nested dataclasses are skipped)."""
        info = mapping["field_info"]
        if is_cli_positional(info) or info.get("is_nested_dataclass", False):
            return
        self.add_argument(parser, mapping["field_name"], info)

    def add_positional_argument(
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

        # Get type converter
        arg_type = self._get_positional_argument_type(info)

        # Build kwargs
        kwargs = self._build_positional_kwargs(
            help_text, metavar, nargs, choices, arg_type
        )

        parser.add_argument(arg_name, **kwargs)

    def _get_positional_argument_type(
        self, info: Dict[str, Any]
    ) -> Callable[[str], Any]:
        """
        Get the type converter for a positional argument.

        Args:
            info: Field information dictionary

        Returns:
            Type converter function
        """
        if info["is_list"]:
            return self._list_element_converter(info)
        return self.get_argument_type(info["type"])

    def _build_positional_kwargs(
        self,
        help_text: str,
        metavar: str,
        nargs: Optional[str],
        choices: Optional[List[Any]],
        arg_type: Callable[[str], Any],
    ) -> Dict[str, Any]:
        """
        Build kwargs dictionary for positional argument.

        The dataclass default is never given to argparse: a value typed on the
        CLI must be distinguishable from "nothing typed", so layer values are
        not overridden by a default. The dataclass applies its own default at
        instantiation.

        Args:
            help_text: Help text for the argument
            metavar: Metavar for display
            nargs: nargs value (optional)
            choices: Valid choices (optional)
            arg_type: Type converter function

        Returns:
            Dictionary of kwargs for add_argument
        """
        kwargs: Dict[str, Any] = {
            "help": help_text,
            "metavar": metavar,
        }

        if nargs is not None:
            kwargs["nargs"] = nargs

        if choices:
            kwargs["choices"] = (
                _ChoicesAllowingNothing(choices) if nargs == "*" else choices
            )

        # Type handling: for list-like nargs, type applies to each element
        kwargs["type"] = arg_type

        # "*" with nothing typed must leave the attribute absent. "?" keeps
        # argparse's None default instead: SUPPRESS would make Python <= 3.11
        # run the type converter / choices check on the SUPPRESS marker.
        if nargs == "*":
            kwargs["default"] = argparse.SUPPRESS

        return kwargs

    def add_argument(
        self,
        parser: argparse.ArgumentParser,
        field_name: str,
        info: Dict[str, Any],
        cli_name: Optional[str] = None,
        prefix: str = "",
        parent_field: Optional[str] = None,
    ) -> None:
        """
        Add CLI argument for a field (unified handler for flat and nested fields).

        Args:
            parser: ArgumentParser to add arguments to
            field_name: Field name (for boolean dest and default help text)
            info: Field info dict
            cli_name: Pre-computed CLI name (for nested fields), uses info["cli_name"] if None
            prefix: Prefix for nested fields (empty string = no prefix)
            parent_field: Parent field name for nested fields (for help text context)
        """
        # Boolean fields handled separately
        if info["type"] == bool:
            self._add_boolean_field(parser, field_name, info, cli_name)
            return

        # Non-boolean fields
        self._add_non_boolean_field(
            parser, field_name, info, cli_name, prefix, parent_field
        )

    def _add_boolean_field(
        self,
        parser: argparse.ArgumentParser,
        field_name: str,
        info: Dict[str, Any],
        cli_name: Optional[str],
    ) -> None:
        """
        Add boolean field argument.

        Args:
            parser: ArgumentParser to add arguments to
            field_name: Field name
            info: Field info dict
            cli_name: Pre-computed CLI name for nested fields
        """
        if cli_name:
            # Nested boolean - update cli_name in info
            field_name = cli_name.lstrip("-").replace("-", "_")
            nested_info = dict(info)
            nested_info["cli_name"] = cli_name
            self.add_boolean_argument(parser, field_name, nested_info)
        else:
            self.add_boolean_argument(parser, field_name, info)

    def _add_non_boolean_field(
        self,
        parser: argparse.ArgumentParser,
        field_name: str,
        info: Dict[str, Any],
        cli_name: Optional[str],
        prefix: str,
        parent_field: Optional[str],
    ) -> None:
        """
        Add non-boolean field argument.

        Args:
            parser: ArgumentParser to add arguments to
            field_name: Field name
            info: Field info dict
            cli_name: Pre-computed CLI name (for nested fields)
            prefix: Prefix for nested fields
            parent_field: Parent field name for nested fields
        """
        # Get CLI name and short option
        cli_name, short_option = self._resolve_cli_name_and_short(
            cli_name, info, prefix
        )
        arg_names = self.build_arg_names(cli_name, short_option)

        # Build help text
        help_text = self._resolve_help_text(info, parent_field, field_name)
        choices = get_cli_choices(info)

        # Dispatch by field characteristics
        self._dispatch_field_type(
            parser, arg_names, info, help_text, choices, cli_name, prefix
        )

    def _dispatch_field_type(
        self,
        parser: argparse.ArgumentParser,
        arg_names: List[str],
        info: Dict[str, Any],
        help_text: str,
        choices: Optional[List[Any]],
        cli_name: str,
        prefix: str,
    ) -> None:
        """
        Dispatch field to appropriate handler based on type.

        Args:
            parser: ArgumentParser to add arguments to
            arg_names: List of argument names (short and/or long)
            info: Field info dict
            help_text: Help text for the argument
            choices: Optional list of valid choices
            cli_name: CLI name for the field
            prefix: Prefix for nested fields
        """
        # Handle append fields
        if is_cli_append(info):
            help_text = self.build_help_text(help_text, choices)
            self.add_append_argument(parser, arg_names, info, help_text, choices)
            return

        # Handle by type
        if info["is_list"]:
            self.add_list_field(parser, arg_names, info, help_text, choices)
        elif info["is_dict"]:
            override_name = self._compute_dict_override_name(info, cli_name, prefix)
            self.add_dict_field(parser, arg_names, help_text, override_name)
        else:
            self.add_scalar_field(parser, arg_names, info, help_text, choices)

    def _resolve_cli_name_and_short(
        self, cli_name: Optional[str], info: Dict[str, Any], prefix: str
    ) -> Tuple[str, Optional[str]]:
        """
        Resolve CLI name and short option for an argument.

        Args:
            cli_name: Pre-computed CLI name (for nested fields)
            info: Field info dict
            prefix: Prefix for nested fields (empty string = no prefix)

        Returns:
            Tuple of (cli_name, short_option)
        """
        # Get CLI name
        if cli_name is None:
            cli_name = info["cli_name"]

        # Get short option (only if no prefix for nested)
        short_option = get_cli_short(info) if prefix == "" or not cli_name else None

        return cli_name, short_option

    def _resolve_help_text(
        self, info: Dict[str, Any], parent_field: Optional[str], field_name: str
    ) -> str:
        """
        Resolve help text for an argument.

        Args:
            info: Field info dict
            parent_field: Parent field name for nested fields
            field_name: Field name

        Returns:
            Help text string
        """
        custom_help = get_cli_help(info)
        if custom_help:
            return custom_help
        elif parent_field:
            return f"{parent_field}.{field_name}"
        else:
            return field_name

    def _compute_dict_override_name(
        self, info: Dict[str, Any], cli_name: str, prefix: str
    ) -> str:
        """
        Compute override name for dict fields.

        Args:
            info: Field info dict
            cli_name: CLI name for the field
            prefix: Prefix for nested fields

        Returns:
            Override argument name
        """
        # For nested fields, compute override name with prefix
        if cli_name != info["cli_name"]:  # Is nested
            override_name = self.compute_override_name(info, prefix)
        else:  # Is flat
            override_name = info["override_name"]
        return override_name

    def add_append_argument(
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
        # Get append metadata
        append_nargs = get_cli_append_nargs(info)
        metavar = get_cli_append_metavar(info)
        min_args = get_cli_append_min_args(info)
        max_args = get_cli_append_max_args(info)

        # If min/max specified, override nargs to '+' for flexible parsing
        if min_args is not None and max_args is not None:
            append_nargs = "+"

        # Get type converter
        arg_type = self._get_append_argument_type(info)

        # Build kwargs
        kwargs = self._build_append_kwargs(
            arg_type,
            help_text,
            append_nargs,
            metavar,
            choices,
            min_args,
            max_args,
        )

        parser.add_argument(*arg_names, **kwargs)

    def _get_append_argument_type(self, info: Dict[str, Any]) -> Callable[[str], Any]:
        """
        Get the type converter for an append argument.

        Args:
            info: Field information dictionary

        Returns:
            Type converter function
        """
        if info["is_list"]:
            return self._list_element_converter(info)
        return self.get_argument_type(info["type"])

    def _build_append_kwargs(
        self,
        arg_type: Callable[[str], Any],
        help_text: str,
        append_nargs: Optional[str],
        metavar: Optional[str],
        choices: Optional[List[Any]],
        min_args: Optional[int],
        max_args: Optional[int],
    ) -> Dict[str, Any]:
        """
        Build kwargs dictionary for append argument.

        The dataclass default is never given to argparse (default=SUPPRESS), so
        nothing typed leaves the attribute absent and layer values are not
        overridden by it.

        Args:
            arg_type: Type converter function
            help_text: Help text for the argument
            append_nargs: nargs value for append (optional)
            metavar: Metavar for display (optional)
            choices: Valid choices (optional)
            min_args: Minimum arguments per occurrence (optional)
            max_args: Maximum arguments per occurrence (optional)

        Returns:
            Dictionary of kwargs for add_argument
        """
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

        kwargs["default"] = argparse.SUPPRESS

        return kwargs

    def add_boolean_argument(
        self, parser: argparse.ArgumentParser, field_name: str, info: Dict[str, Any]
    ) -> None:
        """Add boolean flag argument with positive and negative forms."""
        cli_name = info["cli_name"]
        dest_name = field_name.replace("-", "_")

        # Get short option and build arg names
        short_option = get_cli_short(info)
        positive_args = self.build_arg_names(cli_name, short_option)

        # Get help text and default
        custom_help = get_cli_help(info)
        help_text = custom_help if custom_help else field_name
        negative_help = f"Disable {cli_name}" if custom_help else f"Disable {help_text}"
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
            help=negative_help,
        )

    def get_argument_type(self, field_type: Type) -> Callable[[str], Any]:
        """Get appropriate argparse type for field type."""
        # Note: bool is handled separately in add_boolean_argument
        if field_type in (int, float, str):
            return field_type
        # For complex types, use string and let validation handle it
        return str

    def _list_element_converter(self, info: Dict[str, Any]) -> Callable[[str], Any]:
        """
        Get the converter for the elements of a list field.

        Shared by option, positional and append list fields so they cannot
        drift apart. For List[T] the converter is that of T; for
        List[List[T]] (inner list handled by nargs) it is that of the inner T.

        Args:
            info: Field information dictionary of a list field

        Returns:
            Type converter function (str when the element type is unknown)
        """
        if not info["args"]:
            return str
        element_type = info["args"][0]
        if get_origin(element_type) is list:
            inner_args = get_args(element_type)
            return self.get_argument_type(inner_args[0]) if inner_args else str
        return self.get_argument_type(element_type)

    # ========================================================================
    # Helper Methods for Argument Generation
    # ========================================================================

    def build_arg_names(
        self, cli_name: str, short_option: Optional[str] = None
    ) -> List[str]:
        """
        Build argument names list with optional short option.

        Args:
            cli_name: Long-form CLI name (e.g., "--host")
            short_option: Optional short option character (e.g., "h")

        Returns:
            List of argument names, short option first if present
        """
        arg_names = []
        if short_option:
            arg_names.append(f"-{short_option}")
        arg_names.append(cli_name)
        return arg_names

    def build_help_text(
        self,
        base_help: str,
        choices: Optional[List[Any]] = None,
        extra_suffix: Optional[str] = None,
    ) -> str:
        """
        Build help text with optional choices and suffix.

        Args:
            base_help: Base help text
            choices: Optional list of valid choices
            extra_suffix: Optional suffix to append

        Returns:
            Complete help text
        """
        help_text = base_help
        if choices:
            choices_str = ", ".join(str(c) for c in choices)
            help_text += f" (choices: {choices_str})"
        if extra_suffix:
            help_text += f" {extra_suffix}"
        return help_text

    def compute_override_name(self, info: Dict[str, Any], prefix: str) -> str:
        """
        Compute override argument name for dict fields.

        Args:
            info: Field info dict containing override_name
            prefix: Prefix for nested fields (empty string = no prefix)

        Returns:
            Override argument name (e.g., "--mc" or "--agent-mc")
        """
        return compose_override_name(info, prefix)

    def add_list_field(
        self,
        parser: argparse.ArgumentParser,
        arg_names: List[str],
        info: Dict[str, Any],
        help_text: str,
        choices: Optional[List[Any]] = None,
    ) -> None:
        """Add list field argument with appropriate nargs."""
        if info["is_optional"]:
            nargs_val = "*"
            count_text = "zero or more"
        else:
            nargs_val = "+"
            count_text = "one or more"

        extend = is_cli_extend(info)
        suffix = "; repeatable" if extend else ""
        final_help = self.build_help_text(
            help_text, choices, f"(specify {count_text} values{suffix})"
        )
        kwargs: Dict[str, Any] = {}
        if extend:
            # default stays None: omitted means "not given", and argparse then
            # starts each extend from a fresh list (never a default or layer)
            kwargs["action"] = "extend"
        parser.add_argument(
            *arg_names,
            nargs=nargs_val,
            type=self._list_element_converter(info),
            choices=choices,
            help=final_help,
            **kwargs,
        )

    def add_dict_field(
        self,
        parser: argparse.ArgumentParser,
        arg_names: List[str],
        help_text: str,
        override_name: str,
    ) -> None:
        """Add dict field argument with file path and override support."""
        dict_help = (
            f"{help_text} configuration file path"
            if help_text
            else "configuration file path"
        )
        parser.add_argument(*arg_names, type=str, help=dict_help)

        if override_name:
            override_help = (
                f"{help_text} property override (format: key.path:value)"
                if help_text
                else "property override (format: key.path:value)"
            )
            parser.add_argument(override_name, action="append", help=override_help)

    def add_scalar_field(
        self,
        parser: argparse.ArgumentParser,
        arg_names: List[str],
        info: Dict[str, Any],
        help_text: str,
        choices: Optional[List[Any]] = None,
    ) -> None:
        """Add scalar field argument."""
        arg_type = self.get_argument_type(info["type"])
        final_help = self.build_help_text(help_text, choices)
        parser.add_argument(*arg_names, type=arg_type, choices=choices, help=final_help)
