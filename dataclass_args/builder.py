"""
Orchestrator for dataclass-to-CLI generation.

GenericConfigBuilder ties together the three processing phases:
    1. FieldAnalyzer  — Inspect dataclass, produce field_info dicts
    2. ArgumentRegistry — Register field_info as argparse arguments
    3. ConfigResolver — Merge config sources (one-level by default, or deep
       per merge_strategy), resolve, instantiate

This module is deliberately thin. All logic lives in the phase-specific
modules. GenericConfigBuilder exists for backward compatibility and as
the single object that holds the analysis state.

Usage:
    builder = GenericConfigBuilder(MyConfig)
    parser = argparse.ArgumentParser()
    builder.add_arguments(parser)
    args = parser.parse_args()
    config = builder.build_config(args)

For most use cases, prefer the convenience functions:
    from dataclass_args import build_config, build_config_from_dict
"""

import argparse
from dataclasses import is_dataclass
from typing import Any, Dict, Literal, Optional, Tuple, Type, overload

from .argument_registry import ArgumentRegistry
from .config_merging import BaseConfigInput
from .config_resolver import ConfigResolver
from .exceptions import ConfigBuilderError
from .field_analyzer import FieldAnalyzer
from .provenance import Provenance


class GenericConfigBuilder:
    """
    Builds dataclass instances from CLI arguments and optional base config file.

    Supports any dataclass type with:
    - Optional base config file loading
    - Type-aware CLI argument parsing
    - List parameter accumulation
    - Object parameter file loading with property overrides
    - File-loadable string parameters via '@' prefix
    - Hierarchical merging of configuration sources
    - Field filtering via cli_exclude() annotations
    - Append action for repeatable options
    - Post-load resolution via cli_resolve() annotations
    """

    def __init__(
        self,
        config_class: Type,
        description: Optional[str] = None,
    ):
        """
        Initialize builder for a specific dataclass type.

        Args:
            config_class: Dataclass type to build configurations for
            description: Optional description for ArgumentParser help text.
                        If not provided, uses "Build {ClassName} from CLI"

        Raises:
            ConfigBuilderError: If config_class is not a dataclass
        """
        if not is_dataclass(config_class):
            raise ConfigBuilderError(
                f"config_class must be a dataclass, got {config_class}"
            )

        self.config_class = config_class
        self.description = description
        self._base_config_name = "config"  # Default, updated by add_arguments()

        # Initialize field analyzer
        self.field_analyzer = FieldAnalyzer(config_class)
        self._config_fields = self.field_analyzer.analyze_config_fields()

        # Reject cli_nested cycles before anything recurses into nested classes
        self.field_analyzer.validate_nested_cycles(self._config_fields)

        # Full-path list-merge rule map (cli_list_merge), validated once here
        self.list_merge_rules = self.field_analyzer.build_list_merge_rules()

        # Create argument registry
        self.argument_registry = ArgumentRegistry(
            self.field_analyzer, self._config_fields
        )

        # Create config resolver
        self.config_resolver = ConfigResolver(
            config_class,
            self._config_fields,
            self.field_analyzer,
            self.list_merge_rules,
        )

        # Validate nested dataclass field name collisions
        self.field_analyzer.validate_nested_collisions(self._config_fields)

        # Validate short option collisions (for nested fields with no prefix)
        self.field_analyzer.validate_short_option_collisions(self._config_fields)

        # Validate override name collisions (for dict fields)
        self.field_analyzer.validate_override_name_collisions(self._config_fields)

    def _flatten_nested_fields(self) -> Dict[str, Any]:
        """Flatten nested fields (delegates to FieldAnalyzer)."""
        return self.field_analyzer.flatten_nested_fields(self._config_fields)

    def add_arguments(
        self,
        parser: argparse.ArgumentParser,
        base_config_name: str = "config",
        base_config_help: str = "Base configuration file (JSON, YAML, or TOML)",
    ) -> None:
        """
        Add all dataclass arguments to parser (delegates to ArgumentRegistry).

        Args:
            parser: ArgumentParser to add arguments to
            base_config_name: Name for base config file argument
            base_config_help: Help text for base config file argument
        """
        self._base_config_name = base_config_name.replace("-", "_")
        self.argument_registry.add_arguments(parser, base_config_name, base_config_help)

    @overload
    def build_config(
        self,
        args: argparse.Namespace,
        base_config_name: Optional[str] = ...,
        base_configs: Optional[BaseConfigInput] = ...,
        merge_strategy: str = ...,
        *,
        return_provenance: Literal[True],
    ) -> Tuple[Any, Provenance]: ...

    @overload
    def build_config(
        self,
        args: argparse.Namespace,
        base_config_name: Optional[str] = ...,
        base_configs: Optional[BaseConfigInput] = ...,
        merge_strategy: str = ...,
        return_provenance: Literal[False] = ...,
    ) -> Any: ...

    @overload
    def build_config(
        self,
        args: argparse.Namespace,
        base_config_name: Optional[str] = ...,
        base_configs: Optional[BaseConfigInput] = ...,
        merge_strategy: str = ...,
        return_provenance: bool = ...,
    ) -> Any: ...

    def build_config(
        self,
        args: argparse.Namespace,
        base_config_name: Optional[str] = None,
        base_configs: Optional[BaseConfigInput] = None,
        merge_strategy: str = "shallow",
        return_provenance: bool = False,
    ) -> Any:
        """
        Build dataclass instance from parsed CLI arguments (delegates to
        ConfigResolver).

        Configuration sources are merged in the following order (later sources override
        earlier):
        1. Programmatic base_configs (if provided) - files loaded and applied in order
        2. Config file from --config argument (if provided)
        3. CLI argument overrides

        Args:
            args: Parsed CLI arguments from argparse
            base_config_name: Name of the base config file argument.
                             If None (default), uses the name registered in
                             add_arguments().
            base_configs: Optional base configuration(s) to apply before --config file.
                         Can be:
                         - str: Path to a single config file
                         - dict: A single configuration dictionary
                         - List[Union[str, dict]]: Multiple configs (files and/or dicts)
                           applied in order
            merge_strategy: How dicts from different sources are merged:
                           "shallow" (default, one level) or "deep" (recursive)
            return_provenance: If True (requires merge_strategy="deep"), return
                              ``(instance, Provenance)`` instead of the instance

        Returns:
            Instance of the configured dataclass type, or ``(instance,
            Provenance)`` when return_provenance=True

        Raises:
            ConfigBuilderError: If merge_strategy is not 'shallow' or 'deep'
            ConfigurationError: If configuration is invalid or files cannot be loaded

        Example:
            # Single file path
            config = builder.build_config(args, base_configs='defaults.yaml')

            # Single dict
            config = builder.build_config(args, base_configs={'debug': True})

            # Mixed list
            config = builder.build_config(
                args,
                base_configs=[
                    'base.yaml',              # Load file
                    {'env': 'staging'},       # Use dict
                    'overrides.json',         # Load file
                ]
            )
        """
        if base_config_name is None:
            base_config_name = self._base_config_name
        return self.config_resolver.build_config(
            args, base_config_name, base_configs, merge_strategy, return_provenance
        )


# Re-export convenience functions for backward compatibility
from .convenience import (  # noqa: E402
    build_config,
    build_config_from_cli,
    build_config_from_dict,
)

__all__ = [
    "GenericConfigBuilder",
    "build_config",
    "build_config_from_cli",
    "build_config_from_dict",
]
