"""
Dataclass CLI - Zero-boilerplate CLI generation for Python dataclasses.

This package provides automatic CLI interface generation from Python dataclasses
with advanced features including:

- Type-safe argument parsing for all standard Python types
- Short-form options for concise command lines
- Restricted value choices with validation
- File-loadable string parameters using @filename syntax
- Configuration file merging with CLI overrides
- Hierarchical property overrides for dictionary fields
- Comprehensive validation and error handling
- Automatic help text generation

Basic Usage:
    from dataclasses import dataclass
    from dataclass_args import build_config

    @dataclass
    class Config:
        name: str
        count: int = 10

    config = build_config(Config)  # Automatically parses sys.argv

Advanced Usage:
    from dataclass_args import cli_help, cli_short, cli_choices, cli_file_loadable

    @dataclass
    class Config:
        name: str = cli_short('n', cli_help("Application name"))
        environment: str = cli_choices(['dev', 'staging', 'prod'])
        region: str = combine_annotations(
            cli_short('r'),
            cli_choices(['us-east', 'us-west', 'eu-west']),
            default='us-east'
        )
        message: str = cli_file_loadable()  # Supports @filename loading

    # Usage: -n MyApp --environment prod -r us-west --message @file.txt
    config = build_config(Config)
"""

from .annotations import (
    cli_choices,
    cli_exclude,
    cli_file_loadable,
    cli_help,
    cli_include,
    cli_positional,
    cli_short,
    combine_annotations,
    get_cli_choices,
    get_cli_positional_metavar,
    get_cli_positional_nargs,
    get_cli_short,
    is_cli_excluded,
    is_cli_file_loadable,
    is_cli_included,
    is_cli_positional,
)
from .builder import GenericConfigBuilder, build_config, build_config_from_cli
from .exceptions import ConfigBuilderError, ConfigurationError, FileLoadingError
from .file_loading import is_file_loadable_value, load_file_content
from .utils import load_structured_file

__version__ = "1.2.0"

__all__ = [
    # Main API
    "build_config",
    "build_config_from_cli",
    "GenericConfigBuilder",
    # Annotations
    "cli_help",
    "cli_short",
    "cli_choices",
    "cli_exclude",
    "cli_include",
    "cli_file_loadable",
    "cli_positional",
    "combine_annotations",
    "get_cli_short",
    "get_cli_choices",
    "get_cli_positional_nargs",
    "get_cli_positional_metavar",
    "is_cli_file_loadable",
    "is_cli_excluded",
    "is_cli_included",
    "is_cli_positional",
    # File loading
    "load_file_content",
    "is_file_loadable_value",
    # Utilities
    "load_structured_file",
    # Exceptions
    "ConfigBuilderError",
    "ConfigurationError",
    "FileLoadingError",
]
