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
- Nested dataclass flattening for complex configurations
- Post-load field resolution via resolver functions
- Generic object instantiation from configuration values
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
    from dataclass_args import (
        cli_choices, cli_file_loadable, cli_help, cli_short, combine_annotations
    )

    @dataclass
    class Config:
        name: str = combine_annotations(cli_short('n'), cli_help("Application name"))
        environment: str = cli_choices(['dev', 'staging', 'prod'])
        region: str = combine_annotations(
            cli_short('r'),
            cli_choices(['us-east', 'us-west', 'eu-west']),
            default='us-east'
        )
        message: str = cli_file_loadable(default="")  # Supports @filename loading

    # Usage: -n MyApp --environment prod -r us-west --message @file.txt
    config = build_config(Config)

Nested Dataclass Usage:
    from dataclass_args import cli_nested

    @dataclass
    class WrapperConfig:
        retry_count: int = 3
        timeout: int = 30

    @dataclass
    class AppConfig:
        app_name: str
        wrapper: WrapperConfig = cli_nested(prefix="w")

    # Usage: --app-name MyApp --w-retry-count 5 --w-timeout 60
    config = build_config(AppConfig)

Resolver Usage:
    from dataclass_args import cli_resolve, combine_annotations

    def resolve_backend(value):
        if isinstance(value, dict):
            return create_backend(**value)
        return value

    @dataclass
    class AppConfig:
        backend: Optional[Backend] = combine_annotations(
            cli_resolve(resolver=resolve_backend),
            default=None,
        )

    # Usage: --backend backend.yaml --b type:redis
    config = build_config(AppConfig)

Instantiation Usage:
    from dataclass_args import instantiate

    # Direct target import (remaining keys are keyword arguments)
    obj = instantiate({"_target_": "datetime.timedelta", "hours": 2})

    # Registry-based lookup
    registry = {"docker": "myapp.sandboxes.DockerSandbox"}
    obj = instantiate("docker", registry=registry)
    obj = instantiate({"type": "docker", "image": "python:3.11"},
                      registry=registry)
"""

from .annotations import (
    cli_append,
    cli_choices,
    cli_exclude,
    cli_extend,
    cli_file_loadable,
    cli_help,
    cli_include,
    cli_list_merge,
    cli_nested,
    cli_override_name,
    cli_positional,
    cli_resolve,
    cli_short,
    combine_annotations,
    get_cli_append_max_args,
    get_cli_append_metavar,
    get_cli_append_min_args,
    get_cli_append_nargs,
    get_cli_choices,
    get_cli_list_merge,
    get_cli_nested_prefix,
    get_cli_override_name,
    get_cli_positional_metavar,
    get_cli_positional_nargs,
    get_cli_resolver,
    get_cli_short,
    is_cli_append,
    is_cli_excluded,
    is_cli_extend,
    is_cli_file_loadable,
    is_cli_included,
    is_cli_nested,
    is_cli_positional,
    is_cli_resolve,
)
from .builder import (
    GenericConfigBuilder,
    build_config,
    build_config_from_cli,
    build_config_from_dict,
)
from .config_merging import MERGE_DEEP, MERGE_SHALLOW, ConfigLayer
from .exceptions import (
    ConfigBuilderError,
    ConfigurationError,
    FileLoadingError,
    InstantiationError,
)
from .file_loading import is_file_loadable_value, load_file_content
from .instantiate import instantiate
from .provenance import MISSING_VALUE, Provenance, ProvenanceChange, ProvenanceEntry
from .utils import deep_merge, load_structured_file

__version__ = "1.10.1"

__all__ = [
    # Main API
    "build_config",
    "build_config_from_cli",
    "build_config_from_dict",
    "GenericConfigBuilder",
    # Instantiation
    "instantiate",
    # Annotations
    "cli_help",
    "cli_list_merge",
    "cli_short",
    "cli_override_name",
    "cli_choices",
    "cli_exclude",
    "cli_include",
    "cli_file_loadable",
    "cli_nested",
    "cli_positional",
    "cli_append",
    "cli_extend",
    "cli_resolve",
    "combine_annotations",
    "get_cli_short",
    "get_cli_override_name",
    "get_cli_choices",
    "get_cli_list_merge",
    "get_cli_nested_prefix",
    "get_cli_positional_nargs",
    "get_cli_positional_metavar",
    "get_cli_append_nargs",
    "get_cli_append_metavar",
    "get_cli_append_min_args",
    "get_cli_append_max_args",
    "get_cli_resolver",
    "is_cli_file_loadable",
    "is_cli_excluded",
    "is_cli_included",
    "is_cli_nested",
    "is_cli_positional",
    "is_cli_append",
    "is_cli_extend",
    "is_cli_resolve",
    # File loading
    "load_file_content",
    "is_file_loadable_value",
    # Utilities
    "load_structured_file",
    "deep_merge",
    "MERGE_SHALLOW",
    "MERGE_DEEP",
    "ConfigLayer",
    "Provenance",
    "ProvenanceEntry",
    "ProvenanceChange",
    "MISSING_VALUE",
    # Exceptions
    "ConfigBuilderError",
    "ConfigurationError",
    "FileLoadingError",
    "InstantiationError",
]
