"""
Annotations for controlling CLI field exposure.

Provides decorators and metadata for marking dataclass fields that should
be excluded from CLI argument generation or have special behaviors.
"""

from dataclasses import field
from typing import Any, Dict, List, Optional


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
    metadata = field_kwargs.pop("metadata", {})
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
    metadata = field_kwargs.pop("metadata", {})
    metadata["cli_include"] = True
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
    metadata = field_kwargs.pop("metadata", {})
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
        ValueError: If short is not a single character

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

    field_kwargs = kwargs.copy()
    metadata = field_kwargs.pop("metadata", {})
    metadata["cli_short"] = short
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
            # Simple choices
            environment: str = cli_choices(['dev', 'staging', 'prod'])
            size: str = cli_choices(['small', 'medium', 'large'], default='medium')

            # Combined with other annotations
            region: str = combine_annotations(
                cli_short('r'),
                cli_choices(['us-east-1', 'us-west-2', 'eu-west-1']),
                cli_help("AWS region"),
                default='us-east-1'
            )

        # Usage: --environment prod --size large --region us-west-2
        # Invalid: --environment invalid  # Error with valid choices shown
    """
    if not choices:
        raise ValueError("cli_choices requires at least one choice")

    field_kwargs = kwargs.copy()
    metadata = field_kwargs.pop("metadata", {})
    metadata["cli_choices"] = list(choices)  # Convert to list for consistency
    field_kwargs["metadata"] = metadata
    return field(**field_kwargs)


def cli_file_loadable(**kwargs) -> Any:
    """
    Mark a string field as file-loadable via '@' prefix.

    When a CLI argument value starts with '@', the remaining part is treated as a file path.
    The file is read as UTF-8 encoded text and used as the field value.

    Home directory expansion is supported: '~' expands to the user's home directory.

    Args:
        **kwargs: Additional field parameters (default, default_factory, etc.)

    Returns:
        Field object with file-loadable metadata

    Examples:
        Basic usage:

        >>> @dataclass
        ... class Config:
        ...     message: str = cli_file_loadable()
        ...     system_prompt: str = cli_file_loadable(default="You are a helpful assistant.")

        This generates fields with metadata:
            message:
                metadata={'cli_file_loadable': True}
            system_prompt:
                default="You are a helpful assistant."
                metadata={'cli_file_loadable': True}

        CLI usage:
            # Literal value
            --message "Hello, World!"

            # Load from absolute path
            --message "@/path/to/file.txt"

            # Load from home directory
            --message "@~/messages/welcome.txt"

            # Load from user's home
            --message "@~alice/shared/message.txt"

            # Load from relative path
            --message "@data/message.txt"

    Note:
        Only fields marked with cli_file_loadable() will process '@' as a file loading trigger.
        Regular string fields will treat '@' as a literal character.
    """
    field_kwargs = kwargs.copy()
    metadata = field_kwargs.pop("metadata", {})
    metadata["cli_file_loadable"] = True
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
    combined_metadata = field_kwargs.pop("metadata", {})

    # Extract metadata from each annotation
    for annotation in annotations:
        if hasattr(annotation, "metadata") and annotation.metadata:
            combined_metadata.update(annotation.metadata)

    field_kwargs["metadata"] = combined_metadata
    return field(**field_kwargs)


def is_cli_excluded(field_info: Dict[str, Any]) -> bool:
    """
    Check if a field should be excluded from CLI arguments.

    Args:
        field_info: Field information dictionary from GenericConfigBuilder

    Returns:
        True if field should be excluded from CLI
    """
    # Check for explicit CLI exclusion metadata
    field_obj = field_info.get("field_obj")
    if field_obj and hasattr(field_obj, "metadata"):
        return field_obj.metadata.get("cli_exclude", False)

    return False


def is_cli_included(field_info: Dict[str, Any]) -> bool:
    """
    Check if a field is explicitly marked for CLI inclusion.

    Args:
        field_info: Field information dictionary from GenericConfigBuilder

    Returns:
        True if field is explicitly marked for CLI inclusion
    """
    field_obj = field_info.get("field_obj")
    if field_obj and hasattr(field_obj, "metadata"):
        return field_obj.metadata.get("cli_include", False)

    return False


def is_cli_file_loadable(field_info: Dict[str, Any]) -> bool:
    """
    Check if a field is marked as file-loadable via '@' prefix.

    Args:
        field_info: Field information dictionary from GenericConfigBuilder

    Returns:
        True if field supports file loading via '@' prefix
    """
    field_obj = field_info.get("field_obj")
    if field_obj and hasattr(field_obj, "metadata"):
        return field_obj.metadata.get("cli_file_loadable", False)

    return False


def get_cli_short(field_info: Dict[str, Any]) -> Optional[str]:
    """
    Get short option character for a CLI argument.

    Args:
        field_info: Field information dictionary from GenericConfigBuilder

    Returns:
        Short option character if available, otherwise None
    """
    field_obj = field_info.get("field_obj")
    if field_obj and hasattr(field_obj, "metadata"):
        return field_obj.metadata.get("cli_short")
    return None


def get_cli_choices(field_info: Dict[str, Any]) -> Optional[List[Any]]:
    """
    Get restricted choices for a CLI argument.

    Args:
        field_info: Field information dictionary from GenericConfigBuilder

    Returns:
        List of valid choices if available, otherwise None
    """
    field_obj = field_info.get("field_obj")
    if field_obj and hasattr(field_obj, "metadata"):
        return field_obj.metadata.get("cli_choices")
    return None


def get_cli_help(field_info: Dict[str, Any]) -> str:
    """
    Get custom help text for a CLI argument.

    Args:
        field_info: Field information dictionary from GenericConfigBuilder

    Returns:
        Custom help text if available, otherwise empty string
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

    Examples:
        @dataclass
        class CopyArgs:
            # Required positional
            source: str = cli_positional(help="Source file")
            dest: str = cli_positional(help="Destination file")

            # Optional flag
            recursive: bool = cli_short('r', default=False)

        # Usage: prog source.txt dest.txt -r

        @dataclass
        class GitCommit:
            # Required command
            command: str = cli_positional(help="Git command")

            # Variable files (must be last!)
            files: List[str] = cli_positional(nargs='+', help="Files to commit")

            # Optional message
            message: str = cli_short('m', default="")

        # Usage: prog commit file1.py file2.py -m "Message"

        @dataclass
        class PlotPoint:
            # Exact count
            coordinates: List[float] = cli_positional(
                nargs=2,
                metavar='X Y',
                help="X and Y coordinates"
            )

            # Optional label
            label: str = cli_positional(nargs='?', default='', help="Point label")

        # Usage: prog 1.5 2.5 "Point A"
        # Usage: prog 1.5 2.5  # Uses default label

        @dataclass
        class Convert:
            # With combine_annotations
            input: str = combine_annotations(
                cli_positional(),
                cli_help("Input file to convert")
            )

            output: str = combine_annotations(
                cli_positional(nargs='?'),
                cli_help("Output file (default: stdout)"),
                default='stdout'
            )

    See Also:
        POSITIONAL_LIST_CONFLICTS.md for detailed discussion of constraints
    """
    field_kwargs = kwargs.copy()
    metadata = field_kwargs.pop("metadata", {})
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


def is_cli_positional(field_info: Dict[str, Any]) -> bool:
    """
    Check if a field is marked as a positional CLI argument.

    Args:
        field_info: Field information dictionary from GenericConfigBuilder

    Returns:
        True if field is a positional argument
    """
    field_obj = field_info.get("field_obj")
    if field_obj and hasattr(field_obj, "metadata"):
        return field_obj.metadata.get("cli_positional", False)
    return False


def get_cli_positional_nargs(field_info: Dict[str, Any]) -> Optional[Any]:
    """
    Get nargs value for a positional CLI argument.

    Args:
        field_info: Field information dictionary from GenericConfigBuilder

    Returns:
        nargs value if specified, otherwise None (meaning exactly one)
    """
    field_obj = field_info.get("field_obj")
    if field_obj and hasattr(field_obj, "metadata"):
        return field_obj.metadata.get("cli_positional_nargs")
    return None


def get_cli_positional_metavar(field_info: Dict[str, Any]) -> Optional[str]:
    """
    Get metavar for a positional CLI argument.

    Args:
        field_info: Field information dictionary from GenericConfigBuilder

    Returns:
        Metavar string if specified, otherwise None
    """
    field_obj = field_info.get("field_obj")
    if field_obj and hasattr(field_obj, "metadata"):
        return field_obj.metadata.get("cli_positional_metavar")
    return None
