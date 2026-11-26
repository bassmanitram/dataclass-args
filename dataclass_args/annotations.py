"""
Annotations for controlling CLI field exposure.

Provides decorators and metadata for marking dataclass fields that should
be excluded from CLI argument generation or have special behaviors.
"""

from dataclasses import field
from typing import Any, Callable, Dict, List, Optional

# ============================================================================
# Unified Metadata Accessor
# ============================================================================


class _FieldMetadata:
    """
    Unified accessor for field metadata.

    Internal class that eliminates duplication across all get_cli_* and is_cli_*
    functions.
    All these functions share the same pattern: extract field_obj, check metadata,
    return value.
    """

    @staticmethod
    def get(field_info: Dict[str, Any], key: str, default: Any = None) -> Any:
        """
        Get metadata value from field_info dict.

        Args:
            field_info: Field information dictionary from GenericConfigBuilder
            key: Metadata key to retrieve
            default: Default value if key not found

        Returns:
            Metadata value or default
        """
        field_obj = field_info.get("field_obj")
        if field_obj and hasattr(field_obj, "metadata"):
            return field_obj.metadata.get(key, default)
        return default

    @staticmethod
    def get_bool(field_info: Dict[str, Any], key: str) -> bool:
        """Get boolean metadata value (defaults to False)."""
        return _FieldMetadata.get(field_info, key, False)


def _own_metadata(field_kwargs: Dict[str, Any]) -> Dict[str, Any]:
    """
    Pop ``metadata`` from field kwargs as a new dict.

    The caller's mapping is copied, never mutated, so one metadata dict can be
    shared between fields (and a read-only mapping works too).
    """
    return dict(field_kwargs.pop("metadata", None) or {})


# ============================================================================
# CLI Annotation Decorators
# ============================================================================


def cli_exclude(**kwargs) -> Any:
    """
    Mark a dataclass field to be excluded from CLI arguments.

    This is a convenience function that adds metadata to a dataclass field
    to indicate it should not be exposed as a CLI argument.

    Args:
        **kwargs: Additional field parameters (default, default_factory, etc.)

    Returns:
        Field object with CLI exclusion metadata

    Example:
        @dataclass
        class Config:
            public_field: str                    # Will be CLI argument
            private_field: str = cli_exclude()   # Won't be CLI argument
            secret: str = cli_exclude(default="hidden")  # Won't be CLI argument
    """
    field_kwargs = kwargs.copy()
    metadata = _own_metadata(field_kwargs)
    metadata["cli_exclude"] = True
    field_kwargs["metadata"] = metadata
    return field(**field_kwargs)


def cli_include(**kwargs) -> Any:
    """
    Explicitly mark a dataclass field to be included in CLI arguments.

    This is useful when using include-only mode or for documentation purposes.

    Args:
        **kwargs: Additional field parameters (default, default_factory, etc.)

    Returns:
        Field object with CLI inclusion metadata

    Example:
        @dataclass
        class Config:
            included_field: str = cli_include()
            other_field: str = "default"  # Included by default anyway
    """
    field_kwargs = kwargs.copy()
    metadata = _own_metadata(field_kwargs)
    metadata["cli_include"] = True
    field_kwargs["metadata"] = metadata
    return field(**field_kwargs)


def cli_nested(prefix: Optional[str] = None, **kwargs) -> Any:
    """
    Mark a nested dataclass field for CLI flattening.

    When applied to a nested dataclass field, its fields are flattened into
    the parent's CLI namespace with an optional prefix to avoid collisions.

    Args:
        prefix: Prefix for nested field CLI arguments:
                - "" (empty string): No prefix, flatten completely
                - "custom": Use custom prefix (e.g., "w" -> --w-field)
                - None (default): Auto-prefix with field name
                  (e.g., "wrapper" -> --wrapper-field)
                Underscores become hyphens, as in field names
                ("my_db" -> --my-db-field).
        **kwargs: Additional field parameters (default, default_factory, etc.)

    Returns:
        Field object with cli_nested metadata

    Note:
        - When prefix="", collision detection ensures no field name conflicts
        - Short options of nested fields only apply when the composed prefix is ""
        - Mixed flat and nested fields are fully supported
        - Nesting works at any depth; prefixes compose (--outer-inner-field)
        - Give the field a default_factory so it has a value when no source
          sets it; required fields of the nested class must then be supplied
          by a config source or the CLI
    """
    field_kwargs = kwargs.copy()
    metadata = _own_metadata(field_kwargs)
    metadata["cli_nested"] = True
    metadata["cli_nested_prefix"] = prefix
    field_kwargs["metadata"] = metadata
    return field(**field_kwargs)


def cli_help(help_text: str, **kwargs) -> Any:
    """
    Add custom help text for a CLI argument.

    Args:
        help_text: Custom help text for the CLI argument
        **kwargs: Additional field parameters

    Returns:
        Field object with help text metadata

    Example:
        @dataclass
        class Config:
            host: str = cli_help("Database host address")
            port: int = cli_help("Database port number", default=5432)
    """
    field_kwargs = kwargs.copy()
    metadata = _own_metadata(field_kwargs)
    metadata["cli_help"] = help_text
    field_kwargs["metadata"] = metadata
    return field(**field_kwargs)


def cli_short(short: str, **kwargs) -> Any:
    """
    Add short-form option for a CLI argument.

    Args:
        short: Single character for short option (e.g., 'n' for -n)
        **kwargs: Additional field parameters

    Returns:
        Field object with short option metadata

    Raises:
        ValueError: If short is not a single character, or is '-' or whitespace

    Example:
        @dataclass
        class Config:
            name: str = cli_short('n')
            host: str = cli_short('H', default="localhost")
            port: int = cli_short('p', default=8080)

        # Usage: -n MyApp -H 0.0.0.0 -p 9000
        # or:    --name MyApp --host 0.0.0.0 --port 9000
        # mixed: -n MyApp --host 0.0.0.0 -p 9000
    """
    if not isinstance(short, str) or len(short) != 1:
        raise ValueError(f"Short option must be a single character, got: {repr(short)}")
    if short == "-" or short.isspace():
        raise ValueError(f"Short option can't be '-' or whitespace, got: {repr(short)}")

    field_kwargs = kwargs.copy()
    metadata = _own_metadata(field_kwargs)
    metadata["cli_short"] = short
    field_kwargs["metadata"] = metadata
    return field(**field_kwargs)


def cli_override_name(name: str, **kwargs) -> Any:
    """
    Specify a custom override argument name for dict fields.

    Dict fields automatically get an abbreviated override argument (e.g.,
    sandbox_config → --sc) for property overrides like --sc key:value.
    When two fields generate the same abbreviation, use this annotation
    to resolve the collision.

    Args:
        name: Custom override abbreviation (without -- prefix)
        **kwargs: Additional field parameters

    Returns:
        Field object with override name metadata

    Raises:
        ValueError: If name is empty, starts with '-' or contains whitespace

    Example:
        @dataclass
        class Config:
            # → --sc (auto)
            sandbox_config: dict = field(default_factory=dict)
            # → --sk (explicit)
            skills_config: dict = cli_override_name("sk", default_factory=dict)
    """
    if not isinstance(name, str) or not name:
        raise ValueError(f"Override name must be a non-empty string, got: {repr(name)}")
    if name.startswith("-") or any(c.isspace() for c in name):
        raise ValueError(
            "Override name is given without the leading '--' and can't contain "
            f"whitespace, got: {repr(name)}"
        )

    field_kwargs = kwargs.copy()
    metadata = _own_metadata(field_kwargs)
    metadata["cli_override_name"] = name
    field_kwargs["metadata"] = metadata
    return field(**field_kwargs)


def cli_choices(choices: List[Any], **kwargs) -> Any:
    """
    Restrict field to a specific set of valid choices.

    Args:
        choices: List of valid values for the field
        **kwargs: Additional field parameters

    Returns:
        Field object with choices metadata

    Raises:
        ValueError: If choices is empty

    Example:
        @dataclass
        class Config:
            environment: str = cli_choices(['dev', 'staging', 'prod'])
            size: str = cli_choices(['small', 'medium', 'large'], default='medium')
    """
    if not choices:
        raise ValueError("cli_choices requires at least one choice")

    field_kwargs = kwargs.copy()
    metadata = _own_metadata(field_kwargs)
    metadata["cli_choices"] = list(choices)  # Convert to list for consistency
    field_kwargs["metadata"] = metadata
    return field(**field_kwargs)


def cli_file_loadable(**kwargs) -> Any:
    """
    Mark a string field as file-loadable via '@' prefix.

    When a CLI argument value starts with '@', the remaining part is treated as a file
    path.
    The file is read as UTF-8 encoded text and used as the field value.

    Home directory expansion is supported: '~' expands to the user's home directory.

    Args:
        **kwargs: Additional field parameters (default, default_factory, etc.)

    Returns:
        Field object with file-loadable metadata

    Note:
        Only fields marked with cli_file_loadable() will process '@' as a file loading
        trigger.
        Regular string fields will treat '@' as a literal character.
    """
    field_kwargs = kwargs.copy()
    metadata = _own_metadata(field_kwargs)
    metadata["cli_file_loadable"] = True
    field_kwargs["metadata"] = metadata
    return field(**field_kwargs)


def _validate_append_args(
    nargs: Optional[Any], min_args: Optional[int], max_args: Optional[int]
) -> None:
    """Validate the argument-count parameters of cli_append."""
    # Validate mutually exclusive parameters
    if nargs is not None and (min_args is not None or max_args is not None):
        raise ValueError(
            "cli_append: 'nargs' and 'min_args'/'max_args' are mutually exclusive. "
            "Use either nargs for standard argparse behavior, or min_args/max_args "
            "for range validation."
        )

    # Validate min_args/max_args must be used together
    if (min_args is not None) != (max_args is not None):
        raise ValueError(
            "cli_append: 'min_args' and 'max_args' must be used together. "
            f"Got min_args={min_args}, max_args={max_args}"
        )

    # Validate range constraints
    if min_args is not None and max_args is not None:
        _validate_append_range(min_args, max_args)


def _validate_append_range(min_args: int, max_args: int) -> None:
    """Validate the min_args/max_args range of cli_append."""
    if min_args < 1:
        raise ValueError(f"cli_append: 'min_args' must be >= 1, got {min_args}")
    if max_args < min_args:
        raise ValueError(
            f"cli_append: 'max_args' ({max_args}) must be >= min_args ({min_args})"
        )


def cli_append(
    nargs: Optional[Any] = None,
    min_args: Optional[int] = None,
    max_args: Optional[int] = None,
    metavar: Optional[str] = None,
    **kwargs,
) -> Any:
    """
    Mark a field for append action - allows repeating the option multiple times.

    Each occurrence of the option collects its arguments into a sub-list,
    and all sub-lists are collected into the final list.

    Args:
        nargs: Number of arguments per option occurrence (traditional argparse style)
               None = exactly one (each -f takes 1 arg)
               '?' = zero or one
               '*' = zero or more
               '+' = one or more
               int = exact count (e.g., 2 for pairs)
               Mutually exclusive with min_args/max_args
        min_args: Minimum arguments per occurrence (e.g., 1 for "at least 1")
                  Must be used together with max_args
                  Mutually exclusive with nargs
        max_args: Maximum arguments per occurrence (e.g., 2 for "at most 2")
                  Must be used together with min_args
                  Mutually exclusive with nargs
        metavar: Name for display in help text (e.g., "FILE [MIMETYPE]")
        **kwargs: Additional field parameters (default_factory, etc.)

    Returns:
        Field object with append metadata

    Note:
        - Always use default_factory=list for append fields
        - Cannot be combined with cli_positional()
    """
    _validate_append_args(nargs, min_args, max_args)

    field_kwargs = kwargs.copy()
    metadata = _own_metadata(field_kwargs)
    metadata["cli_append"] = True

    optional_metadata = {
        "cli_append_nargs": nargs,
        "cli_append_metavar": metavar,
        "cli_append_min_args": min_args,
        "cli_append_max_args": max_args,
    }
    metadata.update(
        {key: value for key, value in optional_metadata.items() if value is not None}
    )

    # Move 'help' to metadata if present (dataclass field() doesn't accept it)
    if "help" in field_kwargs:
        metadata["cli_help"] = field_kwargs.pop("help")

    field_kwargs["metadata"] = metadata
    return field(**field_kwargs)


def cli_extend(**kwargs) -> Any:
    """
    Mark a list field so a repeated option accumulates its values.

    Without this annotation, repeating a list option keeps only the last
    occurrence (argparse ``store``). With it, every occurrence extends the
    list: ``-t a -t b`` and ``-t a b`` both give ``['a', 'b']``. The final
    list replaces earlier layers as a whole, as any CLI value does.

    Args:
        **kwargs: Additional field parameters (default_factory, etc.)

    Returns:
        Field object with extend metadata

    Note:
        - Only valid on List[T] / Optional[List[T]] fields with scalar elements
        - Cannot be combined with cli_append, cli_positional or cli_exclude
        - Use cli_append(nargs=...) to keep each occurrence as a sub-list
    """
    field_kwargs = kwargs.copy()
    metadata = _own_metadata(field_kwargs)
    metadata["cli_extend"] = True

    # Move 'help' to metadata if present (dataclass field() doesn't accept it)
    if "help" in field_kwargs:
        metadata["cli_help"] = field_kwargs.pop("help")

    field_kwargs["metadata"] = metadata
    return field(**field_kwargs)


LIST_MERGE_APPEND = "append"
LIST_MERGE_APPEND_UNIQUE = "append_unique"
LIST_MERGE_MODES = (LIST_MERGE_APPEND, LIST_MERGE_APPEND_UNIQUE)


def _validate_list_merge_paths(paths: Optional[List[str]]) -> None:
    """Validate the dotted paths given to cli_list_merge."""
    if paths is None:
        return
    if len(paths) == 0:
        raise ValueError("cli_list_merge: 'paths' must not be an empty list")
    for path in paths:
        if not isinstance(path, str) or "" in path.split("."):
            raise ValueError(
                f"cli_list_merge: invalid path {path!r} "
                "(must be non-empty dotted segments, e.g. 'policy.denied')"
            )


def cli_list_merge(mode: str, paths: Optional[List[str]] = None, **kwargs) -> Any:
    """
    Mark a field so that lists at its location are combined, not replaced.

    The rule only acts when a ``ConfigLayer(..., list_merge="rules")`` layer (or
    ``build_config_from_dict(..., config_list_merge="rules")``) is merged with
    ``merge_strategy="deep"``, and only where both layers hold a list there.
    CLI values and the --config file always replace.

    Args:
        mode: "append" (earlier list + later list) or "append_unique" (earlier
              list + later elements not already present, compared with ==)
        paths: For dict-typed fields, the dotted paths inside the dict whose
               lists are combined (e.g. ["roots", "policy.denied"]). Must be
               omitted for list-typed fields.
        **kwargs: Additional field parameters (default_factory, etc.)

    Returns:
        Field object with list-merge metadata

    Raises:
        ValueError: If mode is invalid, or paths is empty or has an empty segment

    Note:
        Cannot be used on a cli_nested field: annotate the fields inside the
        nested dataclass instead (rules apply at any nesting depth).
    """
    if mode not in LIST_MERGE_MODES:
        raise ValueError(
            f"cli_list_merge: mode must be one of {list(LIST_MERGE_MODES)}, "
            f"got {mode!r}"
        )
    _validate_list_merge_paths(paths)

    field_kwargs = kwargs.copy()
    metadata = _own_metadata(field_kwargs)
    metadata["cli_list_merge"] = {
        "mode": mode,
        "paths": list(paths) if paths else None,
    }
    field_kwargs["metadata"] = metadata
    return field(**field_kwargs)


def cli_resolve(resolver: Callable[[Any], Any], **kwargs) -> Any:
    """
    Mark a field for post-load resolution.

    After the raw value is assembled from all configuration sources (base_configs,
    config file, CLI arguments), the resolver function transforms it into the
    final field value.

    For non-list fields: treated as dict-loadable during parsing (supports file
    paths and property overrides), regardless of declared type annotation.

    For list fields: retains natural list parsing behavior (nargs), and the
    resolver receives the assembled list.

    Args:
        resolver: Callable that transforms raw value -> final value.
                  NOT called if raw value is None.
                  Should handle pass-through for pre-built objects if needed.
        **kwargs: Additional field parameters (default, default_factory, etc.)

    Returns:
        Field object with resolver metadata

    Raises:
        ValueError: If resolver is not callable

    Examples:
        Dict field (loaded from config file):

        >>> def resolve_sandbox(value):
        ...     if isinstance(value, dict):
        ...         sandbox_type = value.pop("type")
        ...         return create_sandbox(sandbox_type, **value)
        ...     return value  # Pre-built object pass-through
        >>>
        >>> @dataclass
        ... class AppConfig:
        ...     sandbox: Optional[SandboxBase] = combine_annotations(
        ...         cli_resolve(resolver=resolve_sandbox),
        ...         cli_help("Sandbox configuration"),
        ...         default=None,
        ...     )

        List field (parsed from CLI values):

        >>> def resolve_paths(value):
        ...     if isinstance(value, list):
        ...         return [expand_glob(v) for v in value]
        ...     return value
        >>>
        >>> @dataclass
        ... class Config:
        ...     files: List[str] = combine_annotations(
        ...         cli_resolve(resolver=resolve_paths),
        ...         default_factory=list,
        ...     )

    Note:
        - Compatible with: cli_help, cli_short, cli_choices, combine_annotations
        - Incompatible with: cli_positional, cli_nested, cli_append,
          cli_exclude, cli_file_loadable
        - In nested dataclasses: accepted but resolver is NOT called (value stays raw)
        - Resolver exceptions are wrapped in ConfigurationError with field context
        - ConfigurationError raised by resolver is re-raised without wrapping
        - For list fields: resolver receives the full list (not individual elements)
        - None bypass: resolver never called when value is None
    """
    if not callable(resolver):
        raise ValueError(
            f"cli_resolve: 'resolver' must be callable, got {type(resolver).__name__}"
        )

    field_kwargs = kwargs.copy()
    metadata = _own_metadata(field_kwargs)
    metadata["cli_resolve"] = True
    metadata["cli_resolver"] = resolver
    field_kwargs["metadata"] = metadata
    return field(**field_kwargs)


def combine_annotations(*annotations, **field_kwargs) -> Any:
    """
    Combine multiple CLI annotations into a single field.

    Args:
        *annotations: List of annotation functions (cli_help, cli_file_loadable, etc.)
        **field_kwargs: Additional field parameters

    Returns:
        Field object with combined metadata

    Example:
        @dataclass
        class Config:
            message: str = combine_annotations(
                cli_help("Message content"),
                cli_file_loadable(),
                default="Default message"
            )

            # With short option
            name: str = combine_annotations(
                cli_short('n'),
                cli_help("Application name")
            )

            # With choices
            region: str = combine_annotations(
                cli_short('r'),
                cli_choices(['us-east', 'us-west']),
                cli_help("Region"),
                default='us-east'
            )
    """
    combined_metadata = _own_metadata(field_kwargs)

    # Extract metadata from each annotation
    for annotation in annotations:
        if hasattr(annotation, "metadata") and annotation.metadata:
            combined_metadata.update(annotation.metadata)

    field_kwargs["metadata"] = combined_metadata
    return field(**field_kwargs)


def cli_positional(
    nargs: Optional[Any] = None, metavar: Optional[str] = None, **kwargs
) -> Any:
    """
    Mark a dataclass field as a positional CLI argument.

    Positional arguments don't use -- prefix and are matched by position.

    IMPORTANT CONSTRAINTS:
    - At most ONE positional field can use nargs='*' or '+'
    - If present, positional list must be the LAST positional argument
    - For multiple lists, use optional arguments with flags instead

    Args:
        nargs: Number of arguments
               None = exactly one (required)
               '?' = zero or one (optional)
               '*' = zero or more (list, optional)
               '+' = one or more (list, required)
               int = exact count (list)
        metavar: Name for display in help text (default: FIELD_NAME)
        **kwargs: Additional field parameters (default, default_factory, etc.)

    Returns:
        Field object with positional metadata

    See Also:
        docs/research/POSITIONAL_LIST_CONFLICTS.md for a detailed discussion
        of these constraints
    """
    field_kwargs = kwargs.copy()
    metadata = _own_metadata(field_kwargs)
    metadata["cli_positional"] = True

    if nargs is not None:
        metadata["cli_positional_nargs"] = nargs

    if metavar is not None:
        metadata["cli_positional_metavar"] = metavar

    # Move 'help' to metadata (dataclass field() doesn't accept it)
    if "help" in field_kwargs:
        metadata["cli_help"] = field_kwargs.pop("help")

    field_kwargs["metadata"] = metadata
    return field(**field_kwargs)


# ============================================================================
# Metadata Helper Functions
# ============================================================================


def is_cli_excluded(field_info: Dict[str, Any]) -> bool:
    """Check if a field should be excluded from CLI arguments."""
    return _FieldMetadata.get_bool(field_info, "cli_exclude")


def is_cli_included(field_info: Dict[str, Any]) -> bool:
    """Check if a field is explicitly marked for CLI inclusion."""
    return _FieldMetadata.get_bool(field_info, "cli_include")


def is_cli_nested(field_info: Dict[str, Any]) -> bool:
    """Check if a field is marked for nested dataclass flattening."""
    return _FieldMetadata.get_bool(field_info, "cli_nested")


def get_cli_nested_prefix(field_info: Dict[str, Any]) -> Optional[str]:
    """
    Get prefix for nested dataclass CLI arguments.

    Returns:
        - "" (empty string): No prefix
        - "custom": Custom prefix
        - None: Auto-prefix with field name (default)
    """
    return _FieldMetadata.get(field_info, "cli_nested_prefix")


def is_cli_file_loadable(field_info: Dict[str, Any]) -> bool:
    """Check if a field is marked as file-loadable via '@' prefix."""
    return _FieldMetadata.get_bool(field_info, "cli_file_loadable")


def is_cli_append(field_info: Dict[str, Any]) -> bool:
    """Check if a field uses append action for repeated options."""
    return _FieldMetadata.get_bool(field_info, "cli_append")


def is_cli_extend(field_info: Dict[str, Any]) -> bool:
    """Check if a list field accumulates repeated options (cli_extend)."""
    return _FieldMetadata.get_bool(field_info, "cli_extend")


def is_cli_positional(field_info: Dict[str, Any]) -> bool:
    """Check if a field is marked as a positional CLI argument."""
    return _FieldMetadata.get_bool(field_info, "cli_positional")


def is_cli_resolve(field_info: Dict[str, Any]) -> bool:
    """Check if a field is marked for post-load resolution."""
    return _FieldMetadata.get_bool(field_info, "cli_resolve")


def get_cli_resolver(field_info: Dict[str, Any]) -> Optional[Callable]:
    """Get the resolver callable for a cli_resolve field."""
    return _FieldMetadata.get(field_info, "cli_resolver")


def get_cli_short(field_info: Dict[str, Any]) -> Optional[str]:
    """Get short option character for a CLI argument."""
    return _FieldMetadata.get(field_info, "cli_short")


def get_cli_choices(field_info: Dict[str, Any]) -> Optional[List[Any]]:
    """Get restricted choices for a CLI argument."""
    return _FieldMetadata.get(field_info, "cli_choices")


def get_cli_list_merge(field_info: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Get the list-merge rule ({"mode": ..., "paths": ...}) of a field, if any."""
    return _FieldMetadata.get(field_info, "cli_list_merge")


def get_cli_append_nargs(field_info: Dict[str, Any]) -> Optional[Any]:
    """Get nargs value for an append CLI argument."""
    return _FieldMetadata.get(field_info, "cli_append_nargs")


def get_cli_append_metavar(field_info: Dict[str, Any]) -> Optional[str]:
    """Get metavar for an append CLI argument."""
    return _FieldMetadata.get(field_info, "cli_append_metavar")


def get_cli_append_min_args(field_info: Dict[str, Any]) -> Optional[int]:
    """Get minimum arguments for an append CLI argument."""
    return _FieldMetadata.get(field_info, "cli_append_min_args")


def get_cli_append_max_args(field_info: Dict[str, Any]) -> Optional[int]:
    """Get maximum arguments for an append CLI argument."""
    return _FieldMetadata.get(field_info, "cli_append_max_args")


def get_cli_positional_nargs(field_info: Dict[str, Any]) -> Optional[Any]:
    """Get nargs value for a positional CLI argument."""
    return _FieldMetadata.get(field_info, "cli_positional_nargs")


def get_cli_positional_metavar(field_info: Dict[str, Any]) -> Optional[str]:
    """Get metavar for a positional CLI argument."""
    return _FieldMetadata.get(field_info, "cli_positional_metavar")


def get_cli_override_name(field_info: Dict[str, Any]) -> Optional[str]:
    """Get custom override name for a dict field."""
    return _FieldMetadata.get(field_info, "cli_override_name")


def get_cli_help(field_info: Dict[str, Any]) -> str:
    """
    Get custom help text for a CLI argument.

    Automatically adds file-loadable hint if applicable.
    """
    field_obj = field_info.get("field_obj")
    if field_obj and hasattr(field_obj, "metadata"):
        help_text = field_obj.metadata.get("cli_help", "")

        # Add file-loadable hint to help text if applicable
        if field_obj.metadata.get("cli_file_loadable", False):
            if help_text:
                help_text += " (supports @file.txt to load from file)"
            else:
                help_text = "supports @file.txt to load from file"

        return help_text

    return ""
