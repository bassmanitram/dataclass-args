"""
Field analysis and validation for dataclass CLI generation.

This module inspects dataclass field definitions (types, defaults, metadata
annotations) and produces a normalized dictionary of field information that
drives all downstream processing — argument registration, config resolution,
and collision detection.

Data Flow:
    Dataclass Type
        → analyze_config_fields()
            → For each field: type inspection, nested detection, default extraction
            → Filtering (cli_exclude), resolve compatibility checks
            → Positional argument validation
        → Dict[field_name, field_info]  (consumed by ArgumentRegistry, ConfigResolver)

Key Concepts:
    - field_info dict: Normalized representation of one field with keys like
      'type', 'is_list', 'is_dict', 'is_nested_dataclass', 'cli_name', etc.
    - Collision detection: Ensures flattened nested fields don't produce
      duplicate CLI argument names or short options.
    - Positional constraints: At most one greedy positional (nargs='*'/'+'),
      must be last.
"""

import collections
import types
from collections import abc
from dataclasses import MISSING, fields, is_dataclass
from typing import (
    Any,
    Dict,
    List,
    Optional,
    Tuple,
    Type,
    Union,
    get_args,
    get_origin,
    get_type_hints,
)

from .annotations import (
    LIST_MERGE_MODES,
    get_cli_list_merge,
    get_cli_nested_prefix,
    get_cli_override_name,
    get_cli_positional_nargs,
    get_cli_short,
    is_cli_append,
    is_cli_excluded,
    is_cli_extend,
    is_cli_file_loadable,
    is_cli_nested,
    is_cli_positional,
    is_cli_resolve,
)
from .exceptions import ConfigBuilderError
from .nested_processor import NestedFieldProcessor, mapping_source
from .type_inspector import TypeInspector

_CONTAINER_TYPES = (
    list,
    tuple,
    set,
    frozenset,
    dict,
    collections.deque,
    abc.Collection,
    abc.Container,
    abc.Iterable,
    abc.Sequence,
    abc.MutableSequence,
    abc.Set,
    abc.MutableSet,
    abc.Mapping,
    abc.MutableMapping,
)
_UNION_ORIGINS = (Union, types.UnionType)


def _is_scalar_element(element: Any) -> bool:
    """
    Whether a list element type is scalar (a single CLI token per element).

    Containers (list, tuple, set, frozenset, dict, collection ABCs) and
    dataclasses are not scalar. A Union/Optional is scalar when every
    non-None member is.
    """
    origin = get_origin(element)
    if origin in _UNION_ORIGINS:
        return all(
            _is_scalar_element(member)
            for member in get_args(element)
            if member is not type(None)
        )
    base = origin if origin is not None else element
    if base in _CONTAINER_TYPES:
        return False
    return not (isinstance(element, type) and is_dataclass(element))


def _describe_type(element: Any) -> str:
    """Render a type readably (no ``typing.`` prefix)."""
    if isinstance(element, type) and get_origin(element) is None:
        return element.__qualname__
    return repr(element).replace("typing.", "")


def compose_override_name(info: Dict[str, Any], prefix: str) -> str:
    """
    Compute the override argument name of a dict field under a (composed) prefix.

    Args:
        info: Field info dict containing override_name
        prefix: Composed prefix of the nested fields (empty string = no prefix)

    Returns:
        Override argument name (e.g., "--mc" or "--agent-mc")
    """
    if prefix == "":
        return info.get("override_name", "")
    base_override = info.get("override_name", "").lstrip("--")
    return f"--{prefix}{base_override}" if base_override else f"--{prefix}override"


class FieldAnalyzer:
    """
    Analyzes and validates dataclass fields for CLI argument generation.

    Responsible for:
    - Type inspection and categorization
    - Field naming (CLI names, override names)
    - Validation of field annotations and constraints
    - Detection of field collisions
    """

    def __init__(self, config_class: Type):
        """
        Initialize field analyzer for a dataclass.

        Args:
            config_class: Dataclass type to analyze

        Raises:
            ConfigBuilderError: If config_class is not a dataclass
        """
        if not is_dataclass(config_class):
            raise ConfigBuilderError(
                f"config_class must be a dataclass, got {config_class}"
            )
        self.config_class = config_class

    def should_include_field(self, field_name: str, field_info: Dict[str, Any]) -> bool:
        """Determine if a field should be included in CLI arguments."""

        # init=False fields can't be passed to the constructor, so they can't
        # be configured at all
        field_obj = field_info.get("field_obj")
        if field_obj is not None and not field_obj.init:
            return False

        # Apply annotation filter
        if is_cli_excluded(field_info):
            return False

        # Default: include all fields
        return True

    def analyze_config_fields(self) -> Dict[str, Dict[str, Any]]:
        """Analyze dataclass fields for type information."""
        fields_info = {}
        type_hints = get_type_hints(self.config_class)

        for field_obj in fields(self.config_class):
            field_info = self._analyze_single_field(field_obj, type_hints)

            # Only include field if it passes filtering
            if self.should_include_field(field_obj.name, field_info):
                fields_info[field_obj.name] = field_info

        # Validate positional arguments
        self.validate_positional_arguments(fields_info)

        return fields_info

    def _analyze_single_field(
        self, field_obj: Any, type_hints: Dict[str, Type]
    ) -> Dict[str, Any]:
        """
        Analyze a single field and return its info dictionary.

        Extracts type information, nested dataclass metadata, and default values.
        This is the core analysis function that builds the normalized field_info
        representation used throughout the pipeline.

        Args:
            field_obj: The dataclass field object
            type_hints: Type hints dictionary for the class

        Returns:
            Dictionary containing field analysis information
        """
        field_type = type_hints.get(field_obj.name, field_obj.type)

        # Determine field category
        is_optional = TypeInspector.is_optional(field_type)
        if is_optional:
            # Extract the non-None type from Optional[T]
            field_type = TypeInspector.unwrap_optional(field_type)

        origin, args = TypeInspector.get_origin_and_args(field_type)
        is_list = TypeInspector.is_list_type(field_type)
        is_dict = TypeInspector.is_dict_type(field_type)

        # Check if this is a nested dataclass with cli_nested annotation
        is_nested_dataclass, nested_prefix = self._determine_nested_prefix(
            field_type, field_obj
        )

        # Extract default value or factory
        default_value = self._extract_default_value(field_obj)
        has_default = (
            field_obj.default is not MISSING or field_obj.default_factory is not MISSING
        )

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
            "has_default": has_default,
            "cli_name": self.field_to_cli_name(field_obj.name),
            "override_name": self.field_to_override_name(field_obj.name, field_obj),
            "field_obj": field_obj,  # Include field object for metadata access
        }

        # Check for cli_resolve and validate/force appropriate behavior
        self._apply_resolve_overrides(field_info, field_obj, is_list)

        # Check for cli_list_merge and validate it against the field type
        self._validate_list_merge(field_obj, field_info)

        # Check for cli_extend and validate it against the field
        self._validate_extend(field_obj, field_info)

        return field_info

    def _validate_extend(self, field_obj: Any, field_info: Dict[str, Any]) -> None:
        """
        Validate a cli_extend annotation against the field.

        Raises:
            ConfigBuilderError: Naming the field, if the annotation is invalid
        """
        if not is_cli_extend(field_info):
            return
        problems = self._extend_problems(field_info)
        if problems:
            raise ConfigBuilderError(
                f"Field '{field_obj.name}': cli_extend {'; '.join(problems)}"
            )

    @staticmethod
    def _extend_problems(field_info: Dict[str, Any]) -> List[str]:
        """List what is wrong with a cli_extend field (empty when valid)."""
        conflicts = [
            name
            for name, check in (
                ("cli_append", is_cli_append),
                ("cli_positional", is_cli_positional),
                ("cli_exclude", is_cli_excluded),
            )
            if check(field_info)
        ]
        problems = [f"cannot be combined with {name}" for name in conflicts]
        if not field_info["is_list"]:
            problems.append("is only valid on List[T] or Optional[List[T]] fields")
        else:
            problem = FieldAnalyzer._element_problem(field_info)
            if problem:
                problems.append(problem)
        return problems

    @staticmethod
    def _element_problem(field_info: Dict[str, Any]) -> Optional[str]:
        """Describe a non-scalar list element type, or return None."""
        if not field_info["args"]:
            return None
        element = field_info["args"][0]
        if _is_scalar_element(element):
            return None
        problem = f"requires scalar list elements; got {_describe_type(element)}"
        if get_origin(element) is list or element is list:
            problem += "; use cli_append(nargs=...) to collect sub-lists"
        return problem

    def _validate_list_merge(self, field_obj: Any, field_info: Dict[str, Any]) -> None:
        """
        Validate a cli_list_merge annotation against the field's type.

        Raises:
            ConfigBuilderError: Naming the field, if the annotation is invalid
        """
        rule = get_cli_list_merge(field_info)
        if rule is None:
            return
        problem = self._list_merge_problem(rule, field_info)
        if problem:
            raise ConfigBuilderError(
                f"Field '{field_obj.name}': cli_list_merge {problem}"
            )

    @staticmethod
    def _list_merge_problem(
        rule: Dict[str, Any], field_info: Dict[str, Any]
    ) -> Optional[str]:
        """Describe what is wrong with a cli_list_merge rule, or return None."""
        if rule.get("mode") not in LIST_MERGE_MODES:
            return (
                f"mode must be one of {list(LIST_MERGE_MODES)}, "
                f"got {rule.get('mode')!r}"
            )
        if field_info["is_nested_dataclass"] or is_cli_nested(field_info):
            return (
                "cannot be used on a cli_nested field; annotate the fields "
                "inside the nested dataclass instead"
            )
        if field_info["is_list"]:
            return "'paths' is only valid on dict fields" if rule.get("paths") else None
        if field_info["is_dict"]:
            return None if rule.get("paths") else "on a dict field requires 'paths'"
        return "is only valid on list or dict fields"

    def build_list_merge_rules(self) -> Dict[Tuple[str, ...], str]:
        """
        Build the list-merge rule map for this dataclass and everything nested in it.

        Every field is read from the dataclass metadata (including cli_exclude
        fields), recursing into cli_nested classes at any depth.

        Returns:
            Map of full key path (e.g. ("mid", "skills", "roots")) to mode
        """
        rules: Dict[Tuple[str, ...], str] = {}
        self._collect_list_merge_rules(self.config_class, (), rules)
        return rules

    def _collect_list_merge_rules(
        self,
        config_class: Type,
        prefix: Tuple[str, ...],
        rules: Dict[Tuple[str, ...], str],
    ) -> None:
        """Add the rules of `config_class` (and its nested classes) under `prefix`."""
        analyzer = FieldAnalyzer(config_class)
        type_hints = get_type_hints(config_class)
        for field_obj in fields(config_class):
            info = analyzer._analyze_single_field(field_obj, type_hints)
            path = prefix + (field_obj.name,)
            if info["is_nested_dataclass"]:
                self._collect_list_merge_rules(info["type"], path, rules)
                continue
            rule = get_cli_list_merge(info)
            if rule is None:
                continue
            for suffix in self._rule_suffixes(rule):
                rules[path + suffix] = rule["mode"]

    def build_field_leaf_map(self) -> Dict[Tuple[str, ...], Any]:
        """
        Map every dataclass field leaf path to its dataclasses.Field.

        A field leaf is a non-cli_nested field at the top level or under a chain
        of cli_nested fields (``name``, ``mid.w``, ``mid.inner.opts``). All
        init=True fields are included, cli_exclude fields too; init=False
        fields can't be configured, so they are left out.
        """
        leaves: Dict[Tuple[str, ...], Any] = {}
        self._collect_field_leaves(self.config_class, (), leaves)
        return leaves

    def _collect_field_leaves(
        self,
        config_class: Type,
        prefix: Tuple[str, ...],
        leaves: Dict[Tuple[str, ...], Any],
    ) -> None:
        """Add the field leaves of `config_class` (and nested ones) under `prefix`."""
        analyzer = FieldAnalyzer(config_class)
        type_hints = get_type_hints(config_class)
        for field_obj in fields(config_class):
            if not field_obj.init:
                continue
            info = analyzer._analyze_single_field(field_obj, type_hints)
            path = prefix + (field_obj.name,)
            if info["is_nested_dataclass"]:
                self._collect_field_leaves(info["type"], path, leaves)
            else:
                leaves[path] = field_obj

    @staticmethod
    def _rule_suffixes(rule: Dict[str, Any]) -> list:
        """Key-path suffixes a rule applies to: () for a list field, else each path."""
        if not rule.get("paths"):
            return [()]
        return [tuple(path.split(".")) for path in rule["paths"]]

    def _determine_nested_prefix(
        self, field_type: Type, field_obj: Any
    ) -> Tuple[bool, Optional[str]]:
        """
        Determine if field is a nested dataclass and compute its prefix.

        Nested dataclass fields with cli_nested annotation are "flattened" into
        the parent CLI namespace. The prefix determines how their names are
        prefixed to avoid collisions (e.g., agent-name, model-type).

        Args:
            field_type: The type of the field
            field_obj: The dataclass field object

        Returns:
            Tuple of (is_nested_dataclass, nested_prefix)
        """
        if not is_dataclass(field_type):
            return False, None

        # Check if it has cli_nested annotation
        temp_info = {"field_obj": field_obj}
        is_nested_dataclass = is_cli_nested(temp_info)

        if not is_nested_dataclass:
            return False, None

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
                f"{prefix_value}-" if not prefix_value.endswith("-") else prefix_value
            )

        return True, nested_prefix

    def _extract_default_value(self, field_obj: Any) -> Any:
        """
        Extract the default value from a field object.

        Handles both direct defaults (field: int = 42) and default factories
        (field: list = field(default_factory=list)).

        Args:
            field_obj: The dataclass field object

        Returns:
            The default value, or None if no default
        """
        has_default = field_obj.default is not MISSING
        has_default_factory = field_obj.default_factory is not MISSING

        if has_default:
            return field_obj.default
        elif has_default_factory and callable(field_obj.default_factory):
            # Call factory to get default value
            return field_obj.default_factory()
        else:
            return None

    def _apply_resolve_overrides(
        self, field_info: Dict[str, Any], field_obj: Any, is_list: bool
    ) -> None:
        """
        Apply cli_resolve annotation overrides to field info.

        cli_resolve fields undergo post-load transformation via a resolver function.
        For non-list fields, we force dict behavior to enable file loading + property
        overrides (the dict is passed to the resolver for transformation).

        Args:
            field_info: Field info dictionary to modify
            field_obj: The dataclass field object
            is_list: Whether the field is a list type
        """
        temp_info = {"field_obj": field_obj}
        if not is_cli_resolve(temp_info):
            return

        self.validate_resolve_compatibility(field_obj, temp_info)
        if is_list:
            # List field: keep list behavior, resolver transforms entire list
            pass
        else:
            # Non-list field: force dict behavior (file path + overrides)
            field_info["is_dict"] = True
            field_info["is_list"] = False

    def validate_resolve_compatibility(
        self, field_obj: Any, temp_info: Dict[str, Any]
    ) -> None:
        """
        Validate that cli_resolve is not combined with incompatible annotations.

        Args:
            field_obj: The dataclass field object
            temp_info: Temporary field info dict for metadata access

        Raises:
            ConfigBuilderError: If incompatible annotations are detected
        """
        incompatible = []
        if is_cli_positional(temp_info):
            incompatible.append("cli_positional")
        if is_cli_nested(temp_info):
            incompatible.append("cli_nested")
        if is_cli_append(temp_info):
            incompatible.append("cli_append")
        if is_cli_excluded(temp_info):
            incompatible.append("cli_exclude")
        if is_cli_file_loadable(temp_info):
            incompatible.append("cli_file_loadable")

        if incompatible:
            raise ConfigBuilderError(
                f"Field '{field_obj.name}': cli_resolve cannot be combined with "
                f"{', '.join(incompatible)}"
            )

    def validate_positional_arguments(
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
                "Only one positional list argument allowed, found "
                f"{len(positional_list_fields)}: {', '.join(field_names)}. "
                "Use optional lists with flags for additional lists:\n"
                f"  Example: field: List[str] = cli_short('f')  # Use --field instead"
            )

        # Rule 2: Positional list must be last
        if positional_list_fields:
            self._validate_positional_list_is_last(
                positional_fields, positional_list_fields
            )

    def _validate_positional_list_is_last(
        self,
        positional_fields: list,
        positional_list_fields: list,
    ) -> None:
        """
        Validate that positional list field is the last positional argument.

        This is an argparse requirement: greedy positionals consume all remaining
        arguments, so nothing can come after them.

        Args:
            positional_fields: List of all positional fields
            positional_list_fields: List of positional list fields

        Raises:
            ConfigBuilderError: If positional list is not last
        """
        list_field_name, list_nargs = positional_list_fields[0]
        list_field_index = self._find_positional_list_index(
            positional_fields, list_field_name
        )

        # Check if there are any positionals after the list
        if list_field_index < len(positional_fields) - 1:
            later_fields = [
                name for name, _ in positional_fields[list_field_index + 1 :]
            ]
            raise ConfigBuilderError(
                f"Positional list argument '{list_field_name}' "
                f"(nargs='{list_nargs}') must be last.\n"
                "Found positional argument(s) after it: "
                f"{', '.join(repr(f) for f in later_fields)}.\n"
                f"Consider making them optional arguments with flags:\n"
                f"  Example: {later_fields[0]}: str = "
                f"cli_short('{later_fields[0][0]}', default='value')"
            )

    def _find_positional_list_index(
        self, positional_fields: list, list_field_name: str
    ) -> int:
        """
        Find the index of the positional list field.

        Args:
            positional_fields: List of all positional fields
            list_field_name: Name of the list field to find

        Returns:
            Index of the list field
        """
        return next(
            i
            for i, (name, _) in enumerate(positional_fields)
            if name == list_field_name
        )

    def field_to_cli_name(self, field_name: str) -> str:
        """Convert field name to CLI argument name."""
        return "--" + field_name.replace("_", "-")

    def field_to_override_name(self, field_name: str, field_obj: Any = None) -> str:
        """
        Convert field name to override argument name.

        Uses cli_override_name annotation if present, otherwise generates
        an abbreviation from the first letter of each underscore-separated word.

        Args:
            field_name: The dataclass field name
            field_obj: Optional field object to check for cli_override_name annotation

        Returns:
            Override argument name with -- prefix (e.g., '--sc', '--sk')
        """
        # Check for explicit override name annotation
        if field_obj is not None:
            temp_info = {"field_obj": field_obj}
            custom_name = get_cli_override_name(temp_info)
            if custom_name is not None:
                return "--" + custom_name

        # Fall back to algorithmic abbreviation
        words = field_name.split("_")
        if len(words) == 1:
            return "--" + field_name[0]
        else:
            return "--" + "".join(word[0] for word in words if word)

    def flatten_nested_fields(
        self, config_fields: Dict[str, Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Flatten nested fields (delegates to NestedFieldProcessor)."""
        processor = NestedFieldProcessor(self.config_class, config_fields)
        return processor.flatten()

    def validate_nested_collisions(
        self, config_fields: Dict[str, Dict[str, Any]]
    ) -> None:
        """
        Validate that there are no field name collisions when flattening nested
        dataclasses.

        Raises:
            ConfigBuilderError: If collisions are detected
        """
        flat_fields = self.flatten_nested_fields(config_fields)
        cli_names = self._collect_nested_cli_names(flat_fields)

        if cli_names["collisions"]:  # pragma: no cover
            self._raise_nested_collision_error(cli_names["collisions"])

    def _collect_nested_cli_names(self, flat_fields: Dict[str, Any]) -> Dict[str, Any]:
        """
        Collect CLI names and detect collisions.

        Iterates through flattened fields to build a map of CLI names. If the same
        CLI name appears twice, records it as a collision. This is a secondary
        safeguard; the primary detection happens in NestedFieldProcessor.

        Args:
            flat_fields: Flattened field mappings

        Returns:
            Dictionary with 'names' (mapping) and 'collisions' (list)
        """
        # Check for duplicate CLI names
        # NOTE: This collision detection is a secondary safeguard. The primary
        # detection is in NestedFieldProcessor._check_collision() which raises
        # during flatten_nested_fields(). This code is unreachable in practice.
        cli_names: Dict[str, Dict[str, Any]] = {}
        collisions: list = []

        for cli_name, mapping in flat_fields.items():
            if cli_name in cli_names:  # pragma: no cover
                # Collision detected
                prev_mapping = cli_names[cli_name]

                # Build descriptive collision info
                source1 = mapping_source(mapping)
                source2 = mapping_source(prev_mapping)

                collisions.append((cli_name, source1, source2))
            else:
                cli_names[cli_name] = mapping

        return {"names": cli_names, "collisions": collisions}

    def _raise_nested_collision_error(self, collisions: list) -> None:
        """
        Raise a detailed error about nested field collisions.

        Args:
            collisions: List of collision tuples (cli_name, source1, source2)

        Raises:
            ConfigBuilderError: Always raises with detailed message
        """
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

    def validate_short_option_collisions(
        self, config_fields: Dict[str, Dict[str, Any]]
    ) -> None:
        """
        Validate that there are no short option collisions when nested fields have no
        prefix.

        Short options are only checked for nested fields with empty prefix (prefix="").
        Nested fields with non-empty prefix do not support short options.

        Raises:
            ConfigBuilderError: If short option collisions are detected
        """
        flat_fields = self.flatten_nested_fields(config_fields)
        short_options, collisions = self._collect_short_options(flat_fields)

        if collisions:
            self._raise_short_option_collision_error(collisions)

    def _collect_short_options(
        self, flat_fields: Dict[str, Any]
    ) -> Tuple[Dict[str, Tuple[str, str]], list]:
        """
        Collect short options and detect collisions.

        Builds a map of short options to their source fields. Short options are
        single-character flags (e.g., -h, -v) that can be used as aliases for
        long options. Multiple fields with the same short option cause collisions.

        Args:
            flat_fields: Flattened field mappings

        Returns:
            Tuple of (short_options dict, collisions list)
        """
        # Map short option -> (cli_name, source_description)
        short_options: Dict[str, tuple[str, str]] = {}
        collisions: list = []

        for cli_name, mapping in flat_fields.items():
            short = self._mapping_short_option(mapping)
            if short:
                self._check_short_option_collision(
                    short, cli_name, mapping_source(mapping), short_options, collisions
                )

        return short_options, collisions

    @staticmethod
    def _mapping_short_option(mapping: Dict[str, Any]) -> Optional[str]:
        """
        Return the short option a flat mapping registers, if any.

        Nested fields only support short options when their composed prefix is
        empty; nested dataclass containers themselves have none.
        """
        if mapping.get("parent_field"):
            if mapping["prefix"] != "":
                return None
            return get_cli_short(mapping["nested_info"])
        info = mapping["field_info"]
        if info.get("is_nested_dataclass", False):
            return None
        return get_cli_short(info)

    def _check_short_option_collision(
        self,
        short: str,
        cli_name: str,
        source: str,
        short_options: Dict[str, Tuple[str, str]],
        collisions: list,
    ) -> None:
        """
        Check for and record a short option collision.

        Args:
            short: The short option character
            cli_name: CLI name for the field
            source: Source description for the field
            short_options: Dictionary of existing short options
            collisions: List to append collision info to
        """
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

    def _raise_short_option_collision_error(self, collisions: list) -> None:
        """
        Raise a detailed error about short option collisions.

        Args:
            collisions: List of collision tuples

        Raises:
            ConfigBuilderError: Always raises with detailed message
        """
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

    def validate_override_name_collisions(
        self, config_fields: Dict[str, Dict[str, Any]]
    ) -> None:
        """
        Detect and report override name collisions between dict fields.

        Two dict fields that generate the same override abbreviation (e.g.,
        sandbox_config and skills_config both → --sc) will cause argparse
        to raise an error. This method detects the collision early with a
        clear error message.

        Args:
            config_fields: Analyzed field information dictionary

        Raises:
            ConfigBuilderError: If two dict fields share the same override name
        """
        seen: Dict[str, str] = {}
        for field_name, info in config_fields.items():
            if info.get("is_dict", False):
                self._record_override_name(
                    seen, info.get("override_name", ""), field_name
                )

        # Dict fields inside nested dataclasses (at any depth) use the composed prefix
        flat_fields = self.flatten_nested_fields(config_fields)
        for mapping in flat_fields.values():
            nested_info = mapping.get("nested_info")
            if nested_info is not None and nested_info.get("is_dict", False):
                override = compose_override_name(nested_info, mapping["prefix"])
                self._record_override_name(seen, override, mapping_source(mapping))

    @staticmethod
    def _record_override_name(seen: Dict[str, str], override: str, source: str) -> None:
        """Record an override name, raising if another field already uses it."""
        if not override:
            return
        if override in seen:
            raise ConfigBuilderError(
                f"Override name collision detected:\n"
                f"  {override}\n"
                f"    - {seen[override]}\n"
                f"    - {source}\n"
                f"Use cli_override_name() to set a custom override for one of them."
            )
        seen[override] = source

    def validate_nested_cycles(self, config_fields: Dict[str, Dict[str, Any]]) -> None:
        """
        Reject cli_nested dataclasses that contain themselves.

        A nested class that appears again on its own ancestor chain (A.b: B,
        B.a: A) would flatten forever.

        Args:
            config_fields: Analyzed field information for the top-level dataclass

        Raises:
            ConfigBuilderError: Naming the chain, e.g. "A.b -> B.a -> A"
        """
        self._walk_nested_chain(
            self.config_class, config_fields, [self.config_class], []
        )

    def _walk_nested_chain(
        self,
        owner: type,
        config_fields: Dict[str, Dict[str, Any]],
        ancestors: list,
        steps: list,
    ) -> None:
        """Depth-first walk over nested dataclass fields, tracking the ancestors."""
        for field_name, info in config_fields.items():
            if not info.get("is_nested_dataclass", False):
                continue
            nested_class = info["type"]
            chain = steps + [f"{owner.__name__}.{field_name}"]
            if nested_class in ancestors:
                raise ConfigBuilderError(
                    "Circular cli_nested reference: "
                    f"{' -> '.join(chain + [nested_class.__name__])}"
                )
            self._walk_nested_chain(
                nested_class,
                FieldAnalyzer(nested_class).analyze_config_fields(),
                ancestors + [nested_class],
                chain,
            )
