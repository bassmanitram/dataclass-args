"""
Utility functions for dataclass CLI configuration.
"""

import json
from pathlib import Path
from typing import Any, Dict, Union

try:
    import yaml

    HAS_YAML = True
except ImportError:
    HAS_YAML = False

try:
    # Python 3.11+
    import tomllib

    HAS_TOML = True
except ImportError:
    try:
        # Python < 3.11
        import tomli as tomllib

        HAS_TOML = True
    except ImportError:
        HAS_TOML = False


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

    # Read file content
    try:
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
    except UnicodeDecodeError:
        raise ValueError(f"File is not valid UTF-8: {file_path}")
    except IOError as e:
        raise ValueError(f"Cannot read file: {file_path}") from e

    # Determine format from extension
    suffix = path.suffix.lower()

    # Try JSON first (most common)
    if suffix == ".json":
        try:
            return json.loads(content)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in {file_path}: {e}") from e

    # Try YAML
    elif suffix in {".yaml", ".yml"}:
        if not HAS_YAML:
            raise ValueError(
                f"YAML support not available. Install with: pip install 'dataclass-args[yaml]'"
            )
        try:
            return yaml.safe_load(content) or {}
        except yaml.YAMLError as e:
            raise ValueError(f"Invalid YAML in {file_path}: {e}") from e

    # Try TOML
    elif suffix == ".toml":
        if not HAS_TOML:
            raise ValueError(
                f"TOML support not available. Install with: pip install 'dataclass-args[toml]'"
            )
        try:
            return tomllib.loads(content)
        except Exception as e:  # tomllib exceptions vary
            raise ValueError(f"Invalid TOML in {file_path}: {e}") from e

    # Auto-detect format if no extension or unknown extension
    else:
        # Try JSON first
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            pass

        # Try YAML if available
        if HAS_YAML:
            try:
                return yaml.safe_load(content) or {}
            except yaml.YAMLError:
                pass

        # Try TOML if available
        if HAS_TOML:
            try:
                return tomllib.loads(content)
            except Exception:  # nosec B110
                pass

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
