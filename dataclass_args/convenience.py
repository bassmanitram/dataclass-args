"""
Public entry points for building dataclass configurations.

This module provides the user-facing API functions that hide the internal
machinery (GenericConfigBuilder, FieldAnalyzer, ArgumentRegistry, ConfigResolver).

Functions:
    build_config(cls)              → Parse sys.argv, return dataclass instance
    build_config_from_cli(cls, …) → Parse args list with options, return instance
    build_config_from_dict(cls, d) → Build from dict (no CLI, for programmatic use)

All functions return an instance of the provided dataclass type.
"""

import argparse
import dataclasses
import sys
from typing import Any, Dict, List, Literal, Optional, Tuple, Type, Union, overload

from .builder import GenericConfigBuilder
from .config_merging import (
    LIST_MERGE_REPLACE,
    LIST_MERGE_RULES,
    BaseConfigInput,
    ConfigLayer,
)
from .exceptions import ConfigBuilderError
from .formatter import RangeAppendHelpFormatter
from .layer_normalization import check_both_spellings
from .merge_strategy import MERGE_DEEP, MergeContext, make_merge_context
from .provenance import Provenance
from .utils import copy_containers


@overload
def build_config_from_cli(
    config_class: Type,
    args: Optional[List[str]] = ...,
    base_config_name: str = ...,
    base_configs: Optional[BaseConfigInput] = ...,
    description: Optional[str] = ...,
    merge_strategy: str = ...,
    *,
    return_provenance: Literal[True],
) -> Tuple[Any, Provenance]: ...


@overload
def build_config_from_cli(
    config_class: Type,
    args: Optional[List[str]] = ...,
    base_config_name: str = ...,
    base_configs: Optional[BaseConfigInput] = ...,
    description: Optional[str] = ...,
    merge_strategy: str = ...,
    return_provenance: Literal[False] = ...,
) -> Any: ...


@overload
def build_config_from_cli(
    config_class: Type,
    args: Optional[List[str]] = ...,
    base_config_name: str = ...,
    base_configs: Optional[BaseConfigInput] = ...,
    description: Optional[str] = ...,
    merge_strategy: str = ...,
    return_provenance: bool = ...,
) -> Any: ...


def build_config_from_cli(
    config_class: Type,
    args: Optional[List[str]] = None,
    base_config_name: str = "config",
    base_configs: Optional[BaseConfigInput] = None,
    description: Optional[str] = None,
    merge_strategy: str = "shallow",
    return_provenance: bool = False,
) -> Any:
    """
    Build dataclass instance from CLI arguments with optional base configs.

    Configuration sources are merged in the following order (later sources override earlier):
    1. base_configs (if provided) - files loaded and applied in order
    2. Config file from --config argument (if provided)
    3. CLI argument overrides

    Args:
        config_class: Dataclass type to build
        args: Command-line arguments (defaults to sys.argv[1:])
        base_config_name: Name for base config file argument (default: "config")
        base_configs: Optional base configuration(s). Can be:
                     - str: Path to a single config file
                     - dict: A single configuration dictionary
                     - List[Union[str, dict]]: Multiple configs applied in order
        description: Optional description for ArgumentParser help text.
                    If not provided, uses "Build {ClassName} from CLI"
        merge_strategy: How dicts from different sources are merged:
                       "shallow" (default, one level) or "deep" (recursive)
        return_provenance: If True (requires merge_strategy="deep"), return
                          ``(instance, Provenance)`` instead of the instance

    Returns:
        Instance of config_class built from merged configurations, or
        ``(instance, Provenance)`` when return_provenance=True

    Raises:
        ConfigBuilderError: If merge_strategy is not 'shallow' or 'deep'

    Example:
        # Single file
        config = build_config_from_cli(MyConfig, base_configs='defaults.yaml')

        # Single dict
        config = build_config_from_cli(MyConfig, base_configs={'debug': True})

        # With custom description
        config = build_config_from_cli(
            MyConfig,
            description="Configure the application server"
        )

        # Mixed list
        config = build_config_from_cli(
            MyConfig,
            args=['--config', 'prod.yaml', '--name', 'override'],
            base_configs=[
                'company-defaults.yaml',
                {'team': 'platform'},
                'env-staging.json',
            ]
        )
    """
    if args is None:
        args = sys.argv[1:]

    builder = GenericConfigBuilder(config_class, description=description)

    desc = (
        builder.description
        if builder.description is not None
        else f"Build {config_class.__name__} from CLI"
    )
    parser = argparse.ArgumentParser(
        description=desc, formatter_class=RangeAppendHelpFormatter
    )
    builder.add_arguments(parser, base_config_name)

    parsed_args = parser.parse_args(args)
    return builder.build_config(
        parsed_args, base_config_name, base_configs, merge_strategy, return_provenance
    )


@overload
def build_config(
    config_class: Type,
    args: Optional[List[str]] = ...,
    base_configs: Optional[BaseConfigInput] = ...,
    description: Optional[str] = ...,
    merge_strategy: str = ...,
    *,
    return_provenance: Literal[True],
) -> Tuple[Any, Provenance]: ...


@overload
def build_config(
    config_class: Type,
    args: Optional[List[str]] = ...,
    base_configs: Optional[BaseConfigInput] = ...,
    description: Optional[str] = ...,
    merge_strategy: str = ...,
    return_provenance: Literal[False] = ...,
) -> Any: ...


@overload
def build_config(
    config_class: Type,
    args: Optional[List[str]] = ...,
    base_configs: Optional[BaseConfigInput] = ...,
    description: Optional[str] = ...,
    merge_strategy: str = ...,
    return_provenance: bool = ...,
) -> Any: ...


def build_config(
    config_class: Type,
    args: Optional[List[str]] = None,
    base_configs: Optional[BaseConfigInput] = None,
    description: Optional[str] = None,
    merge_strategy: str = "shallow",
    return_provenance: bool = False,
) -> Any:
    """
    Simplified convenience function to build dataclass from CLI arguments.

    Configuration sources are merged in the following order (later sources override earlier):
    1. base_configs (if provided) - files loaded and applied in order
    2. Config file from --config argument (if provided)
    3. CLI argument overrides

    Args:
        config_class: Dataclass type to build
        args: Command-line arguments (defaults to sys.argv[1:])
        base_configs: Optional base configuration(s). Can be:
                     - str: Path to a single config file
                     - dict: A single configuration dictionary
                     - List[Union[str, dict]]: Multiple configs applied in order
        description: Optional description for ArgumentParser help text.
                    If not provided, uses "Build {ClassName} from CLI"
        merge_strategy: How dicts from different sources are merged:
                       "shallow" (default, one level) or "deep" (recursive)
        return_provenance: If True (requires merge_strategy="deep"), return
                          ``(instance, Provenance)`` instead of the instance

    Returns:
        Instance of config_class built from merged configurations, or
        ``(instance, Provenance)`` when return_provenance=True

    Raises:
        ConfigBuilderError: If merge_strategy is not 'shallow' or 'deep'

    Example:
        # Simple usage
        config = build_config(Config)

        # With base config file
        config = build_config(Config, base_configs='defaults.yaml')

        # With custom description
        config = build_config(
            Config,
            description="My application configuration tool"
        )

        # With mixed sources
        config = build_config(
            Config,
            args=['--count', '100'],
            base_configs=[
                'base.yaml',
                {'environment': 'prod'},
            ]
        )
    """
    return build_config_from_cli(
        config_class,
        args,
        base_configs=base_configs,
        description=description,
        merge_strategy=merge_strategy,
        return_provenance=return_provenance,
    )


def _route_config_values(
    builder: GenericConfigBuilder, config: dict
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """
    Split a build_config_from_dict config into base-layer values and CLI values.

    Returns:
        Tuple of (values routed through the internal base_configs layer,
        values injected into the argparse Namespace)
    """
    base_config_values: Dict[str, Any] = {}
    cli_values: Dict[str, Any] = {}
    for key, raw_value in config.items():
        value = copy_containers(raw_value)
        arg_key = key.replace("-", "_")
        field_info = builder._config_fields.get(key) or builder._config_fields.get(
            arg_key
        )

        if field_info is None:
            # Field not in config_fields (e.g., cli_exclude) - route through base_configs
            base_config_values[key] = value
        elif field_info.get("is_nested_dataclass"):
            # Nested field - route through base_configs, where the layer
            # normalizer validates it and stage 6 reconstructs it
            base_config_values[key] = value
        elif value is None:
            # Explicit None clears the value: argparse treats None as "not
            # provided", so route it through the layer that wins over base_configs
            base_config_values[arg_key] = None
        else:
            # Regular field - process through CLI pipeline
            cli_values[arg_key] = value
    return base_config_values, cli_values


def _combine_base_configs(
    base_configs: Optional[BaseConfigInput],
    base_config_values: Union[Dict[str, Any], ConfigLayer, None],
) -> Optional[List[Union[str, Dict[str, Any], ConfigLayer]]]:
    """Put user-supplied base_configs first, then the internally-routed layer."""
    combined: List[Union[str, Dict[str, Any], ConfigLayer]] = []

    # Add user-supplied base_configs first (lowest precedence)
    if base_configs is not None:
        if isinstance(base_configs, list):
            combined.extend(base_configs)
        else:
            combined.append(base_configs)

    # Add internally-routed nested/excluded values on top
    if base_config_values:
        combined.append(base_config_values)

    return combined if combined else None


def _empty_namespace(parser: argparse.ArgumentParser) -> argparse.Namespace:
    """
    Build a Namespace holding "no CLI value" (None) for every argument.

    The programmatic API must never run argparse's required-argument check or
    exit, so the parser is only used to learn the argument names.
    """
    return argparse.Namespace(
        **{action.dest: None for action in parser._actions if action.dest != "help"}
    )


def _validate_config_list_merge(config_list_merge: Any, ctx: MergeContext) -> None:
    """Validate config_list_merge and its compatibility with the merge strategy."""
    if config_list_merge not in (LIST_MERGE_REPLACE, LIST_MERGE_RULES):
        raise ConfigBuilderError(
            f"config_list_merge must be 'replace' or 'rules', got {config_list_merge!r}"
        )
    if config_list_merge == LIST_MERGE_RULES and ctx.strategy != MERGE_DEEP:
        raise ConfigBuilderError(
            "config_list_merge='rules' requires merge_strategy='deep'"
        )


def _validate_provenance(return_provenance: bool, ctx: MergeContext) -> None:
    """Provenance needs layered mode (merge_strategy='deep')."""
    if return_provenance and ctx.strategy != MERGE_DEEP:
        raise ConfigBuilderError(
            "return_provenance=True requires merge_strategy='deep'"
        )


def _inject_config_values(
    builder: GenericConfigBuilder, args: argparse.Namespace, config: dict
) -> Optional[Dict[str, Any]]:
    """
    Legacy (shallow) route: inject regular fields into the Namespace.

    Returns:
        The values routed through an internal base layer (nested/excluded
        fields and explicit None), or None if there are none
    """
    base_config_values, cli_values = _route_config_values(builder, config)
    for key, value in cli_values.items():
        setattr(args, key, value)
    return base_config_values or None


@overload
def build_config_from_dict(
    config_class: type,
    config: dict,
    base_configs: Optional[BaseConfigInput] = ...,
    config_list_merge: str = ...,
    merge_strategy: str = ...,
    *,
    return_provenance: Literal[True],
) -> Tuple[Any, Provenance]: ...


@overload
def build_config_from_dict(
    config_class: type,
    config: dict,
    base_configs: Optional[BaseConfigInput] = ...,
    config_list_merge: str = ...,
    merge_strategy: str = ...,
    return_provenance: Literal[False] = ...,
) -> Any: ...


@overload
def build_config_from_dict(
    config_class: type,
    config: dict,
    base_configs: Optional[BaseConfigInput] = ...,
    config_list_merge: str = ...,
    merge_strategy: str = ...,
    return_provenance: bool = ...,
) -> Any: ...


def build_config_from_dict(
    config_class: type,
    config: dict,
    base_configs: Optional[BaseConfigInput] = None,
    config_list_merge: str = LIST_MERGE_REPLACE,
    merge_strategy: str = "shallow",
    return_provenance: bool = False,
) -> Any:
    """
    Build a dataclass instance from a dictionary, processing values as CLI values.

    Dict values are processed exactly as if they came from the CLI:
    - @file reference loading (for cli_file_loadable fields)
    - Dict field structured file loading
    - cli_resolve() post-load resolution
    - Nested dataclass reconstruction

    Configuration sources are merged in the following order (later sources override earlier):
    1. base_configs (if provided) - files and/or dicts applied in order
    2. config dict values (highest priority)

    This is the recommended entry point for non-CLI contexts such as
    Lambda handlers, programmatic SDKs, and test harnesses.

    Args:
        config_class: Dataclass type to instantiate
        config: Dictionary of field values (processed as if from CLI)
        base_configs: Optional base configuration(s) applied before config dict.
                     Can be:
                     - str: Path to a single config file
                     - dict: A single configuration dictionary
                     - List[Union[str, dict]]: Multiple configs applied in order
        config_list_merge: List policy of the `config` dict when
                          merge_strategy="deep": "replace" (default) or "rules"
                          (lists at cli_list_merge locations are combined with
                          earlier layers). "rules" requires merge_strategy="deep".
        merge_strategy: How dicts from different sources are merged:
                       "shallow" (default, one level) or "deep" (recursive).
                       In deep mode the whole `config` dict is applied as the
                       last base layer (named "config") instead of being
                       processed as CLI values.
        return_provenance: If True (requires merge_strategy="deep"), return
                          ``(instance, Provenance)`` instead of the instance

    Returns:
        Instance of config_class with all values resolved, or
        ``(instance, Provenance)`` when return_provenance=True

    Raises:
        ConfigBuilderError: If merge_strategy or config_list_merge is invalid, or
            config_list_merge="rules" is combined with merge_strategy="shallow"
        ConfigurationError: If resolution fails
        TypeError: If config is not a dict

    Example:
        # Simple usage
        config = build_config_from_dict(AppConfig, {
            "model": "bedrock:claude-3",
            "temperature": 0.7,
        })

        # With base configs (overridden by config dict)
        config = build_config_from_dict(
            AppConfig,
            {"temperature": 0.9},
            base_configs='defaults.yaml',
        )

        # With multiple base configs
        config = build_config_from_dict(
            AppConfig,
            {"temperature": 0.9},
            base_configs=['base.yaml', {'model': 'fallback'}],
        )
    """
    # Validate the knobs before doing any work
    ctx = make_merge_context(merge_strategy)
    _validate_config_list_merge(config_list_merge, ctx)
    _validate_provenance(return_provenance, ctx)

    if not isinstance(config, dict):
        raise TypeError(
            f"build_config_from_dict requires a dict, got {type(config).__name__}. "
            f"Use build_config_from_cli() with base_configs for file paths or lists."
        )

    # Build CLI infrastructure (parser, field analysis) without parsing real args
    builder = GenericConfigBuilder(config_class)
    parser = argparse.ArgumentParser()
    builder.add_arguments(parser)

    # A Namespace with no CLI values (never parsed, so argparse can't exit)
    args = _empty_namespace(parser)

    field_names = frozenset(f.name for f in dataclasses.fields(config_class))
    check_both_spellings(config, field_names, "config")

    if ctx.strategy == MERGE_DEEP:
        # Layered mode: no CLI injection; `config` is one real layer, applied last
        config_layer: Union[Dict[str, Any], ConfigLayer, None] = ConfigLayer(
            copy_containers(config), name="config", list_merge=config_list_merge
        )
    else:
        config_layer = _inject_config_values(builder, args, config)

    # Combine user-supplied base_configs with the config layer.
    # Precedence: base_configs (lowest) < config dict (highest)
    combined_base_configs = _combine_base_configs(base_configs, config_layer)

    return builder.build_config(
        args,
        base_configs=combined_base_configs,
        merge_strategy=merge_strategy,
        return_provenance=return_provenance,
    )
