"""
Utility functions for dataclass CLI configuration.
"""

import dataclasses
import json
import tomllib
from pathlib import Path
from typing import Any, Dict, Union

try:
    import yaml

    HAS_YAML = True
except ImportError:  # pragma: no cover
    HAS_YAML = False  # pragma: no cover

# TOML support comes from the standard library (tomllib, Python 3.11+)
HAS_TOML = True


STRUCTURED_FILE_EXTENSIONS = (".json", ".yaml", ".yml", ".toml")


def looks_like_structured_file(value: str) -> bool:
    """
    Check whether a string looks like a path to a structured config file.

    Args:
        value: String to check

    Returns:
        True if the string ends in .json, .yaml, .yml or .toml
    """
    return value.endswith(STRUCTURED_FILE_EXTENSIONS)


def copy_containers(value: Any) -> Any:
    """
    Recursively copy dict and list containers; all other objects are returned as-is.

    Unlike copy.deepcopy, scalars, tuples, dataclass instances, callables and
    other pre-built objects keep their identity.

    Args:
        value: Value to copy

    Returns:
        A copy of dict/list containers (at every depth), otherwise `value` itself
    """
    if isinstance(value, dict):
        return {k: copy_containers(v) for k, v in value.items()}
    if isinstance(value, list):
        return [copy_containers(v) for v in value]
    return value


def _merge_value(base_value: Any, override_value: Any) -> Any:
    """Merge two values at one key: dicts recurse, anything else is overridden."""
    if isinstance(base_value, dict) and isinstance(override_value, dict):
        return deep_merge(base_value, override_value)
    return copy_containers(override_value)


def deep_merge(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    """
    Return a new dict: `override` recursively merged onto `base`.

    Rules:
    - Where both values are dicts, they are merged recursively.
    - Any other combination (scalar, list, None, dataclass instance, ...) is
      won by `override`. An explicit None clears a value; lists replace.
    - Keys only in `base` are carried through. Key order: `base` keys first,
      then new `override` keys.
    - Every dict and list in the result is a new container at every depth
      (dicts inside lists too); other objects are shared by reference. The
      inputs are never mutated.
    - Keys are not normalised ("db-host" and "db_host" differ).

    Args:
        base: Dict to merge onto
        override: Dict whose values win

    Returns:
        A new merged dict

    Example:
        >>> deep_merge({"db": {"host": "h", "port": 1}}, {"db": {"port": 2}})
        {'db': {'host': 'h', 'port': 2}}
    """
    result: Dict[str, Any] = {}
    for key, base_value in base.items():
        if key in override:
            result[key] = _merge_value(base_value, override[key])
        else:
            result[key] = copy_containers(base_value)
    for key, value in override.items():
        if key not in base:
            result[key] = copy_containers(value)
    return result


def fresh_field_default(field_obj: "dataclasses.Field[Any]") -> Any:
    """
    Return a fresh default for a dataclass field.

    Uses default_factory() when set, otherwise a container copy of the plain
    default, so the result is never shared with the dataclass definition.

    Args:
        field_obj: The dataclasses.Field to read the default from

    Returns:
        A fresh default value, or dataclasses.MISSING if the field has none
    """
    if field_obj.default_factory is not dataclasses.MISSING:
        return field_obj.default_factory()
    if field_obj.default is not dataclasses.MISSING:
        return copy_containers(field_obj.default)
    return dataclasses.MISSING


_UNPARSED = object()  # sentinel: auto-detection attempt did not parse the content


def _read_text_file(path: Path, file_path: Union[str, Path]) -> str:
    """Read a UTF-8 text file, converting I/O problems to ValueError."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    except UnicodeDecodeError:
        raise ValueError(f"File is not valid UTF-8: {file_path}")
    except IOError as e:
        raise ValueError(f"Cannot read file: {file_path}") from e


def _parse_json(content: str, file_path: Union[str, Path]) -> Any:
    """Parse JSON content, raising ValueError on invalid input."""
    try:
        return json.loads(content)
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON in {file_path}: {e}") from e


def _parse_yaml(content: str, file_path: Union[str, Path]) -> Any:
    """Parse YAML content, raising ValueError if unavailable or invalid."""
    if not HAS_YAML:
        raise ValueError(
            f"YAML support not available. Install with: pip install 'dataclass-args[yaml]'"
        )
    try:
        return yaml.safe_load(content) or {}
    except yaml.YAMLError as e:
        raise ValueError(f"Invalid YAML in {file_path}: {e}") from e


def _parse_toml(content: str, file_path: Union[str, Path]) -> Any:
    """Parse TOML content, raising ValueError if unavailable or invalid."""
    if not HAS_TOML:
        raise ValueError(
            f"TOML support not available. Install with: pip install 'dataclass-args[toml]'"
        )
    try:
        return tomllib.loads(content)
    except Exception as e:  # tomllib exceptions vary
        raise ValueError(f"Invalid TOML in {file_path}: {e}") from e


_PARSERS_BY_SUFFIX = {
    ".json": _parse_json,
    ".yaml": _parse_yaml,
    ".yml": _parse_yaml,
    ".toml": _parse_toml,
}


def _try_json(content: str) -> Any:
    """Auto-detection attempt: JSON, or _UNPARSED."""
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        return _UNPARSED


def _try_yaml(content: str) -> Any:
    """Auto-detection attempt: YAML (if available), or _UNPARSED."""
    if not HAS_YAML:
        return _UNPARSED
    try:
        return yaml.safe_load(content) or {}
    except yaml.YAMLError:
        return _UNPARSED


def _try_toml(content: str) -> Any:
    """Auto-detection attempt: TOML (if available), or _UNPARSED."""
    if not HAS_TOML:
        return _UNPARSED
    try:
        return tomllib.loads(content)
    except Exception:  # nosec B110
        return _UNPARSED


def _auto_detect_format(content: str, file_path: Union[str, Path]) -> Any:
    """Parse content of unknown format, trying JSON, then YAML, then TOML."""
    for attempt in (_try_json, _try_yaml, _try_toml):
        result = attempt(content)
        if result is not _UNPARSED:
            return result

    # If all fail, provide helpful error
    supported_formats = ["JSON"]
    if HAS_YAML:
        supported_formats.append("YAML")
    if HAS_TOML:
        supported_formats.append("TOML")

    raise ValueError(
        f"Could not parse {file_path} as any supported format. "
        f"Supported formats: {', '.join(supported_formats)}. "
        f"Install additional format support with: pip install 'dataclass-args[yaml,toml]'"
    )


def load_structured_file(file_path: Union[str, Path]) -> Dict[str, Any]:
    """
    Load structured data from JSON, YAML, or TOML file.

    Automatically detects file format based on extension and attempts to parse.

    Args:
        file_path: Path to the configuration file

    Returns:
        Dictionary containing the parsed configuration

    Raises:
        FileNotFoundError: If file doesn't exist
        ValueError: If file format is unsupported or parsing fails
    """
    path = Path(file_path)

    if not path.exists():
        raise FileNotFoundError(f"Configuration file not found: {file_path}")

    if not path.is_file():
        raise ValueError(f"Path is not a file: {file_path}")

    content = _read_text_file(path, file_path)

    # Known extension: strict parser; otherwise auto-detect the format
    parser = _PARSERS_BY_SUFFIX.get(path.suffix.lower())
    if parser is not None:
        return parser(content, file_path)
    return _auto_detect_format(content, file_path)
