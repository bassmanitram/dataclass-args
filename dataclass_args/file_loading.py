"""
File loading utilities for CLI parameters.

Provides functionality to load string content from files when CLI values
start with the '@' prefix.
"""

import os
from pathlib import Path
from typing import Any, Dict

from .exceptions import FileLoadingError


def is_file_loadable_value(value: Any) -> bool:
    """
    Check if a value is a file-loadable string (starts with '@').

    Args:
        value: Value to check

    Returns:
        True if value is a string starting with '@'
    """
    return isinstance(value, str) and value.startswith("@")


def load_file_content(file_path: str) -> str:
    """
    Load content from a file as UTF-8 encoded text.

    Supports ~ expansion for user home directory paths.

    Args:
        file_path: Path to the file to load (supports ~ for home directory)

    Returns:
        File content as string

    Raises:
        FileLoadingError: If file cannot be read or decoded

    Examples:
        >>> load_file_content("~/config.txt")  # Expands to /home/user/config.txt
        >>> load_file_content("~alice/file.txt")  # Expands to /home/alice/file.txt
        >>> load_file_content("/absolute/path.txt")  # Unchanged
        >>> load_file_content("relative/path.txt")  # Unchanged
    """
    try:
        # Expand ~ to user's home directory
        path_obj = Path(file_path).expanduser()

        # Check if file exists
        if not path_obj.exists():
            raise FileLoadingError(f"File not found: {file_path}")

        # Check if it's actually a file
        if not path_obj.is_file():
            raise FileLoadingError(f"Path is not a file: {file_path}")

        # Check if file is readable
        if not os.access(path_obj, os.R_OK):
            raise FileLoadingError(f"File is not readable: {file_path}")

        # Read file content
        try:
            with open(path_obj, "r", encoding="utf-8") as f:
                return f.read()
        except UnicodeDecodeError as e:
            raise FileLoadingError(f"Cannot decode file as UTF-8: {file_path}") from e
        except IOError as e:
            raise FileLoadingError(f"Error reading file: {file_path}") from e

    except (TypeError, ValueError) as e:
        raise FileLoadingError(f"Invalid file path: {file_path}") from e


def process_file_loadable_value(
    value: Any, field_name: str, field_info: Dict[str, Any] = None
) -> str:
    """
    Process a potentially file-loadable value.

    If the value starts with '@', treats the rest as a file path and loads the content.
    Otherwise, returns the value as-is.

    Args:
        value: The value to process (should be a string)
        field_name: Name of the field (for error messages)
        field_info: Optional field information dict to check if field is file-loadable

    Returns:
        The processed string value

    Raises:
        FileLoadingError: If file loading fails
        ValueError: If value format is invalid
    """
    if not isinstance(value, str):
        return value

    if not value.startswith("@"):
        return value

    # If field_info is provided, check if field is marked as file-loadable
    if field_info is not None:
        from .annotations import is_cli_file_loadable

        if not is_cli_file_loadable(field_info):
            # Field is not marked as file-loadable, return value as-is
            return value

    # Extract file path (everything after '@')
    file_path = value[1:]

    if not file_path:
        raise ValueError(f"Empty file path for field '{field_name}' (value: '{value}')")

    try:
        return load_file_content(file_path)
    except FileLoadingError as e:
        raise ValueError(f"Failed to process field '{field_name}': {e}") from e
