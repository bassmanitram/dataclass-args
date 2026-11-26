"""
Utility functions for dataclass CLI configuration.
"""

import dataclasses
import json
import tomllib
from enum import Enum, auto
from pathlib import Path
from typing import Any, Dict, List, Union

try:
    import yaml

    HAS_YAML = True
except ImportError:  # pragma: no cover
    HAS_YAML = False  # pragma: no cover

# TOML support comes from the standard library (tomllib, Python 3.11+)
HAS_TOML = True


STRUCTURED_FILE_EXTENSIONS = (".json", ".yaml", ".yml", ".toml")


class DictStringAction(Enum):
    """What to do with a string given to a dict field (`dict_string_action`)."""

    LOAD = auto()
    PASS_THROUGH = auto()
    INVALID = auto()


def cli_name_to_dest(cli_name: str) -> str:
    """
    Return the argparse ``dest`` for a generated long option name.

    The leading ``--`` is removed and the remaining hyphens become underscores,
    so a field's option maps back to the field name exactly (``--max-size`` ->
    ``max_size``, ``---private`` -> ``_private``). argparse's own derivation
    strips *every* leading hyphen, which loses a field name's leading
    underscore, so the library always passes this ``dest`` explicitly.

    Args:
        cli_name: Long option string starting with ``--``

    Returns:
        The attribute name used on the argparse Namespace
    """
    return cli_name[2:].replace("-", "_")


def flattened_field_name(cli_name: str) -> str:
    """
    Return the flattened field name behind a nested field's long option.

    Leading hyphens are stripped and the remaining hyphens become underscores
    (``--db-ssl`` -> ``db_ssl``). This is the name the negative boolean flag is
    built from; it is not the argparse ``dest`` (see `cli_name_to_dest`).

    Args:
        cli_name: Long option string starting with ``--``

    Returns:
        The flattened field name
    """
    return cli_name.lstrip("-").replace("-", "_")


def negative_flag_name(field_name: str) -> str:
    """
    Return the ``--no-`` form of a boolean field's option.

    The field name is hyphenated, so an underscored nested prefix gives
    ``--no-my-mid-in-enabled`` while the positive option keeps the prefix as
    written (``--my_mid-in-enabled``). This spelling is part of the 1.10.1
    interface.

    Args:
        field_name: The field's (flattened) name, e.g. ``db_ssl``

    Returns:
        The negative option (``--no-db-ssl``)
    """
    return "--no-" + field_name.replace("_", "-")


def escape_help(text: str) -> str:
    """
    Escape ``%`` so argparse shows help text literally.

    argparse applies %-formatting to every help string, so a bare ``%``
    (``"CPU usage in %"``) would crash ``--help`` with "incomplete format".

    Args:
        text: Help text as it should be displayed

    Returns:
        Text safe to pass as an argparse ``help=`` value
    """
    return text.replace("%", "%%")


def looks_like_structured_file(value: str) -> bool:
    """
    Check whether a string looks like a path to a structured config file.

    Args:
        value: String to check

    Returns:
        True if the string ends in .json, .yaml, .yml or .toml
    """
    return value.endswith(STRUCTURED_FILE_EXTENSIONS)


def dict_string_action(value: str, resolved: bool) -> DictStringAction:
    """
    Decide what to do with a string given to a dict field.

    One rule for every source (command line, nested command line, layers):

    - a path with a structured-file extension is loaded (a missing file then
      fails with the usual "not found" error);
    - for a ``cli_resolve`` field, any other string passes through to the
      resolver;
    - for a plain dict field, a path to an existing file (``~`` expanded, any
      extension) is loaded, and anything else is invalid.

    Args:
        value: The string given for the field
        resolved: True if the field is annotated with ``cli_resolve``

    Returns:
        The action to take: load a file, pass the string through, or reject it
    """
    if looks_like_structured_file(value):
        return DictStringAction.LOAD
    if resolved:
        return DictStringAction.PASS_THROUGH
    if Path(value).expanduser().is_file():
        return DictStringAction.LOAD
    return DictStringAction.INVALID


def invalid_dict_string_message(value: str, field_path: str, layer: str = "") -> str:
    """
    Build the error message for a string that can't be a dict field's value.

    Args:
        value: The rejected string
        field_path: Dotted path of the field (``name`` or ``mid.inner.opts``)
        layer: Label of the layer holding the value, if it came from a layer

    Returns:
        The error message
    """
    where = f" in layer '{layer}'" if layer else ""
    return (
        f"Invalid value {value!r} for dict field '{field_path}'{where}: "
        "expected a dict or a path to a configuration file "
        "(use cli_resolve() to accept other strings)"
    )


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


def missing_required_fields(config_class: type, values: Dict[str, Any]) -> List[str]:
    """
    Name the init fields of `config_class` that have no default and no value.

    Args:
        config_class: Dataclass about to be instantiated
        values: Keyword arguments that will be passed to it

    Returns:
        The missing field names, in declaration order (empty if none)
    """
    return [
        f.name
        for f in dataclasses.fields(config_class)
        if f.init
        and f.default is dataclasses.MISSING
        and f.default_factory is dataclasses.MISSING
        and f.name not in values
    ]


def describe_missing(names: List[str]) -> str:
    """Render missing field names for an error message."""
    label = "field" if len(names) == 1 else "fields"
    return f"missing required {label}: " + ", ".join(repr(n) for n in names)


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
            "YAML support not available. "
            "Install with: pip install 'dataclass-args[yaml]'"
        )
    try:
        result = yaml.safe_load(content)
    except yaml.YAMLError as e:
        raise ValueError(f"Invalid YAML in {file_path}: {e}") from e
    return {} if result is None else result  # an empty file is an empty mapping


def _parse_toml(content: str, file_path: Union[str, Path]) -> Any:
    """Parse TOML content, raising ValueError if unavailable or invalid."""
    if not HAS_TOML:
        raise ValueError("TOML support not available (requires Python 3.11+ tomllib)")
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
        result = yaml.safe_load(content)
    except yaml.YAMLError:
        return _UNPARSED
    return {} if result is None else result


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
        "Install YAML support with: pip install 'dataclass-args[yaml]'"
    )


def load_structured_file(file_path: Union[str, Path]) -> Dict[str, Any]:
    """
    Load a mapping from a JSON, YAML, or TOML file.

    The format is chosen by extension (.json, .yaml/.yml, .toml); any other
    extension is auto-detected (JSON, then YAML, then TOML). A leading ``~``
    is expanded to the user's home directory. An empty YAML file loads as
    ``{}``.

    Args:
        file_path: Path to the configuration file

    Returns:
        Dictionary containing the parsed configuration

    Raises:
        FileNotFoundError: If file doesn't exist
        ValueError: If the file can't be read or parsed, or its top level is
            not a mapping (e.g. a list or a plain string)
    """
    path = Path(file_path).expanduser()

    if not path.exists():
        raise FileNotFoundError(f"Configuration file not found: {file_path}")

    if not path.is_file():
        raise ValueError(f"Path is not a file: {file_path}")

    content = _read_text_file(path, file_path)

    # Known extension: strict parser; otherwise auto-detect the format
    parser = _PARSERS_BY_SUFFIX.get(path.suffix.lower())
    if parser is not None:
        data = parser(content, file_path)
    else:
        data = _auto_detect_format(content, file_path)
    if not isinstance(data, dict):
        raise ValueError(
            f"{file_path} must contain a mapping (key/value pairs) at the top "
            f"level, got {type(data).__name__}"
        )
    return data
