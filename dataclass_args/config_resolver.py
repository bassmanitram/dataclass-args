"""
Configuration resolution pipeline orchestrator.

Coordinates the multi-stage pipeline by delegating to stage-specific processors:
    - ConfigMerger: Normalize and merge base_configs + config files
    - CliOverrideProcessor: Apply CLI argument overrides
    - ValueResolver: Resolve raw values, validate, apply cli_resolve
    - NestedFieldProcessor: Reconstruct nested dataclass instances

Pipeline Stages:
    1. Normalize base_configs → List[Dict]  (files loaded, types validated,
                                             dict-field file refs loaded per layer)
    2. Apply base_configs → merged Dict      (one-level (default) or deep merge per merge_strategy)
    3. Apply config file → merged Dict       (--config file normalized, merged on top)
    4. Apply CLI overrides → merged Dict     (per-field: file loading, dict loading, scalars)
    5. Resolve raw values                    (@file refs in base_configs values that weren't overridden)
    6. Reconstruct nested fields             (flat dict → nested dataclass instances)
    7. Validate append ranges                (min_args/max_args enforcement)
    8. Resolve fields                        (cli_resolve transformations)
    9. Instantiate dataclass                 (Dict → dataclass instance)

Precedence (later wins):
    base_configs[0] < base_configs[1] < ... < --config file < CLI arguments
"""

import argparse
import dataclasses
from typing import Any, Dict, Mapping, Optional, Tuple

from .cli_overrides import CliOverrideProcessor
from .config_merging import LIST_MERGE_RULES, BaseConfigInput, ConfigLayer, ConfigMerger
from .exceptions import ConfigBuilderError, ConfigurationError
from .layer_normalization import LayerNormalizer
from .merge_strategy import MERGE_DEEP, MergeContext, make_merge_context
from .nested_processor import NestedFieldProcessor
from .provenance import ProvenanceRecorder
from .value_resolution import ValueResolver


class ConfigResolver:
    """
    Orchestrates the config resolution pipeline.

    Delegates to stage-specific processors:
    - ConfigMerger: file loading and merging
    - CliOverrideProcessor: CLI argument processing
    - ValueResolver: value resolution and validation
    - NestedFieldProcessor: nested dataclass reconstruction
    """

    def __init__(
        self,
        config_class: type,
        config_fields: Dict[str, Dict[str, Any]],
        field_analyzer: Any,
        list_merge_rules: Optional[Mapping[Tuple[str, ...], str]] = None,
    ):
        """
        Initialize config resolver.

        Args:
            config_class: Dataclass type to build
            config_fields: Dictionary of analyzed field information
            field_analyzer: FieldAnalyzer instance for nested field operations
            list_merge_rules: Map of full key path to list-merge mode, built from
                the cli_list_merge annotations (default: no rules)
        """
        self.config_class = config_class
        self.config_fields = config_fields
        self.field_analyzer = field_analyzer
        self.list_merge_rules = dict(list_merge_rules or {})

        # Initialize stage-specific processors
        self.merger = ConfigMerger()
        self.cli_processor = CliOverrideProcessor(config_fields)
        self.value_resolver = ValueResolver(config_fields)
        self.layer_normalizer = LayerNormalizer(config_fields, config_class)

    def build_config(
        self,
        args: argparse.Namespace,
        base_config_name: str = "config",
        base_configs: Optional[BaseConfigInput] = None,
        merge_strategy: str = "shallow",
        return_provenance: bool = False,
    ) -> Any:
        """
        Build dataclass instance from parsed CLI arguments with hierarchical config merging.

        Configuration sources are merged in the following order (later sources override earlier):
        1. Programmatic base_configs (if provided) - files loaded and applied in order
        2. Config file from --config argument (if provided)
        3. CLI argument overrides

        Args:
            args: Parsed CLI arguments from argparse
            base_config_name: Name of the base config file argument (default: "config")
            base_configs: Optional base configuration(s) to apply before --config file.
                         Can be:
                         - str: Path to a single config file
                         - dict: A single configuration dictionary
                         - List[Union[str, dict]]: Multiple configs (files and/or dicts) applied in order
            merge_strategy: How dicts that meet while combining sources are merged:
                           "shallow" (default, one level) or "deep" (recursive)
            return_provenance: If True (requires merge_strategy="deep"), return
                              ``(instance, Provenance)`` instead of the instance

        Returns:
            Instance of the configured dataclass type, or ``(instance,
            Provenance)`` when return_provenance=True

        Raises:
            ConfigBuilderError: If merge_strategy is not 'shallow' or 'deep'
            ConfigurationError: If configuration is invalid or files cannot be loaded
        """
        # Validate before loading or merging anything
        ctx = self._make_context(base_configs, merge_strategy, return_provenance)

        # Stages 1-3: Normalize and merge base configs, then the --config file
        config_dict = self._merge_sources(args, base_config_name, base_configs, ctx)

        # Stage 4: Apply CLI argument overrides
        config_dict = self.cli_processor.apply_cli_overrides(config_dict, args, ctx)

        # Stage 5: Resolve raw values from base_configs/config file
        config_dict = self.value_resolver.resolve_raw_values(config_dict, args)

        # Stage 6: Reconstruct nested dataclass instances
        config_dict = self._reconstruct_nested_fields(config_dict, args, ctx)

        # Stage 7: Validate append field ranges
        self.value_resolver.validate_append_ranges(config_dict)

        # Stage 8: Resolve fields (cli_resolve)
        config_dict = self.value_resolver.resolve_fields(config_dict)

        # Stage 9: Instantiate dataclass
        instance = self._instantiate(config_dict)
        if ctx.recorder is None:
            return instance
        return instance, ctx.recorder.finish(self.field_analyzer.build_field_leaf_map())

    def _make_context(
        self,
        base_configs: Optional[BaseConfigInput],
        merge_strategy: str,
        return_provenance: bool,
    ) -> MergeContext:
        """Validate the merge knobs and build the per-call context."""
        ctx = make_merge_context(merge_strategy, self.list_merge_rules)
        self._check_rules_layers_allowed(base_configs, ctx)
        if not return_provenance:
            return ctx
        if ctx.strategy != MERGE_DEEP:
            raise ConfigBuilderError(
                "return_provenance=True requires merge_strategy='deep'"
            )
        return dataclasses.replace(
            ctx, recorder=ProvenanceRecorder(self.list_merge_rules)
        )

    def _merge_sources(
        self,
        args: argparse.Namespace,
        base_config_name: str,
        base_configs: Optional[BaseConfigInput],
        ctx: MergeContext,
    ) -> Dict[str, Any]:
        """Stages 1-3: normalize and merge base_configs, then apply --config."""
        labeled_configs = self.merger.normalize_base_configs_labeled(base_configs)
        normalized_configs = [
            self.layer_normalizer.normalize(layer, label)
            for label, layer, _ in labeled_configs
        ]
        rules_layers = [mode == LIST_MERGE_RULES for _, _, mode in labeled_configs]
        labels = [label for label, _, _ in labeled_configs]
        config_dict = self.merger.apply_base_configs(
            normalized_configs, ctx, rules_layers, labels
        )
        return self.merger.apply_config_file(
            config_dict, args, base_config_name, self.layer_normalizer.normalize, ctx
        )

    def _instantiate(self, config_dict: Dict[str, Any]) -> Any:
        """Stage 9: instantiate the dataclass from the resolved dict."""
        try:
            return self.config_class(**config_dict)
        except Exception as e:
            raise ConfigurationError(
                f"Failed to create {self.config_class.__name__}: {e}"
            ) from e

    @staticmethod
    def _check_rules_layers_allowed(
        base_configs: Optional[BaseConfigInput], ctx: MergeContext
    ) -> None:
        """Reject list_merge='rules' layers unless merge_strategy is 'deep'."""
        if ctx.strategy == MERGE_DEEP:
            return
        items = base_configs if isinstance(base_configs, list) else [base_configs]
        if any(
            isinstance(item, ConfigLayer) and item.list_merge == LIST_MERGE_RULES
            for item in items
        ):
            raise ConfigBuilderError(
                "list_merge='rules' requires merge_strategy='deep'"
            )

    def _reconstruct_nested_fields(
        self,
        config: Dict[str, Any],
        args: argparse.Namespace,
        ctx: MergeContext = MergeContext(),
    ) -> Dict[str, Any]:
        """Reconstruct nested fields (delegates to NestedFieldProcessor)."""
        flat_fields = self.field_analyzer.flatten_nested_fields(self.config_fields)
        processor = NestedFieldProcessor(self.config_class, self.config_fields)
        return processor.reconstruct(config, args, flat_fields, ctx)
