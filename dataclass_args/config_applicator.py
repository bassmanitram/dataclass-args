"""
Configuration application utilities.

Consolidates logic for applying configurations from various sources. Dicts
that meet while layers are combined are merged one level deep (default) or
recursively, per the build's ``merge_strategy`` (see ``merge_strategy.py``).
"""

import argparse
from typing import Any, Callable, Dict, List, Optional

from .exceptions import ConfigurationError
from .merge_strategy import MergeContext, combine_dicts
from .utils import load_structured_file


class ConfigApplicator:
    """
    Apply configurations from various sources (base configs, files, CLI overrides).

    Consolidates repeated patterns in _apply_* methods.
    """

    @staticmethod
    def merge_layer(config: Dict[str, Any], layer: Dict[str, Any]) -> Dict[str, Any]:
        """
        Merge `layer` onto `config` one level deep. Mutates and returns `config`.

        Dict values present in both are combined by key into a new dict (nested
        dicts below that level are replaced, not merged). Any other value,
        including None and lists, replaces the existing one.

        Args:
            config: Configuration dictionary to merge into (modified in place)
            layer: Configuration dictionary applied on top

        Returns:
            The updated `config` dictionary
        """
        for key, value in layer.items():
            if isinstance(config.get(key), dict) and isinstance(value, dict):
                config[key] = {**config[key], **value}
            else:
                config[key] = value
        return config

    @staticmethod
    def merge_layer_with(
        config: Dict[str, Any],
        layer: Dict[str, Any],
        ctx: MergeContext,
        rules: bool = False,
    ) -> Dict[str, Any]:
        """
        Merge `layer` onto `config` using the build's merge strategy.

        Shallow: `merge_layer` (mutates and returns `config`). Deep: a full
        recursive `deep_merge` (returns a new dict), so callers must use the
        return value.

        Args:
            config: Accumulated configuration dictionary
            layer: Layer applied on top
            ctx: Merge context of the current build
            rules: Apply list-merge rules for this layer (deep mode only)

        Returns:
            The merged configuration dictionary
        """
        return combine_dicts(config, layer, ctx, ConfigApplicator.merge_layer, rules)

    @staticmethod
    def apply_base_configs(
        base_configs: List[Dict[str, Any]],
        ctx: MergeContext = MergeContext(),
        rules_layers: Optional[List[bool]] = None,
        labels: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Apply base configuration dictionaries in order.

        Args:
            base_configs: List of configuration dictionaries to merge in order
            ctx: Merge context (default: shallow)
            rules_layers: Optional per-layer flags (parallel to `base_configs`);
                a True layer is merged with the context's list-merge rules
            labels: Optional per-layer names (parallel to `base_configs`), used
                to record provenance when the context carries a recorder

        Returns:
            Merged configuration dictionary

        Note:
            Each config is applied sequentially, with a one-level dict merge
            (default) or a deep merge per `merge_strategy`. Later configs
            override earlier ones.
        """
        config: Dict[str, Any] = {}

        for index, base_config in enumerate(base_configs):
            if not isinstance(base_config, dict):
                raise ConfigurationError(
                    f"base_configs must contain dictionaries, got {type(base_config)}"
                )
            use_rules = bool(rules_layers and rules_layers[index])
            if ctx.recorder is not None and labels is not None:
                ctx.recorder.record_layer(labels[index], base_config, use_rules)
            config = ConfigApplicator.merge_layer_with(
                config, base_config, ctx, use_rules
            )

        return config

    @staticmethod
    def apply_config_file(
        config: Dict[str, Any],
        args: argparse.Namespace,
        base_config_name: str,
        normalize: Optional[Callable[[Dict[str, Any], str], Dict[str, Any]]] = None,
        ctx: MergeContext = MergeContext(),
    ) -> Dict[str, Any]:
        """
        Load and merge configuration from --config file argument.

        Args:
            config: Current configuration dictionary
            args: Parsed CLI arguments
            base_config_name: Name of the config file argument
            normalize: Optional layer normaliser applied to the loaded file dict
                (with label "config_file:<path>") before it is merged
            ctx: Merge context (default: shallow)

        Returns:
            Updated configuration dictionary with file config merged

        Raises:
            ConfigurationError: If file cannot be loaded or normalization fails
        """
        base_config_value = getattr(args, base_config_name.replace("-", "_"), None)

        if base_config_value:
            try:
                file_config = load_structured_file(base_config_value)
                if normalize is not None:
                    file_config = normalize(
                        file_config, f"config_file:{base_config_value}"
                    )
                if ctx.recorder is not None:
                    ctx.recorder.record_layer(
                        f"config_file:{base_config_value}", file_config
                    )
                config = ConfigApplicator.merge_layer_with(config, file_config, ctx)
            except ConfigurationError:
                raise
            except Exception as e:
                raise ConfigurationError(
                    f"Failed to load config file '{base_config_value}': {e}"
                ) from e

        return config

    @staticmethod
    def apply_property_overrides(
        target_dict: Dict[str, Any],
        overrides: List[str],
        observer: Optional[Callable[[List[str], Any], None]] = None,
    ) -> None:
        """
        Apply property path overrides to target dictionary.

        Args:
            target_dict: Dictionary to apply overrides to (modified in place)
            overrides: List of "key.path:value" override strings
            observer: Optional callback called after each override is applied,
                with the split key path and the parsed value (used to record
                provenance)

        Raises:
            ValueError: If override format is invalid
        """
        for override in overrides:
            if ":" not in override:
                raise ValueError(
                    f"Invalid override format: {override} (expected key.path:value)"
                )

            path, value_str = override.split(":", 1)
            ConfigApplicator.set_nested_property(target_dict, path, value_str)
            if observer is not None:
                observer(path.split("."), ConfigApplicator.parse_value(value_str))

    @staticmethod
    def set_nested_property(target: Dict[str, Any], path: str, value_str: str) -> None:
        """
        Set nested property using dot notation with list index support.

        Supports:
        - Dict navigation: "outer.inner.key" → target["outer"]["inner"]["key"]
        - List indexing: "items.0" → target["items"][0] (when items is a list)
        - List append: "items.+" → target["items"].append(value)
        - Mixed: "data.0.name" → target["data"][0]["name"]

        List indexing is determined by the runtime type of the container:
        - If the container is a list and the key is a non-negative integer, index into
          it
        - If the container is a dict, the key is always a string key (even "0" or "+")
        - Missing intermediate keys always create dicts (never auto-create lists)

        Args:
            target: Target dictionary
            path: Property path (e.g., "outer.inner.key" or "items.0.name")
            value_str: String value to parse and set

        Raises:
            ValueError: If list index is out of range, or navigation fails
        """
        keys = path.split(".")
        current = target

        # Navigate to parent of final key
        for position, key in enumerate(keys[:-1]):
            current = ConfigApplicator._navigate_step(
                current, key, path, keys[:position]
            )

        # Set final value
        final_key = keys[-1]
        parsed_value = ConfigApplicator.parse_value(value_str)

        if isinstance(current, list):
            ConfigApplicator._set_list_element(current, final_key, parsed_value)
        elif isinstance(current, dict):
            current[final_key] = parsed_value
        else:
            raise ConfigApplicator._not_a_container_error(
                path, ".".join(keys[:-1]), current
            )

    @staticmethod
    def _navigate_step(
        current: Any, key: str, path: str, parent_keys: List[str]
    ) -> Any:
        """
        Move one path segment into a dict (creating it if missing) or a list.

        Args:
            current: Container being navigated
            key: Path segment to enter
            path: Full property path (for error messages)
            parent_keys: Path segments leading to `current` (for error messages)

        Raises:
            ValueError: If `current` is neither a dict nor a list
        """
        if isinstance(current, list):
            return ConfigApplicator._navigate_list(current, key)
        if isinstance(current, dict):
            if key not in current:
                current[key] = {}
            return current[key]
        raise ConfigApplicator._not_a_container_error(
            path, ".".join(parent_keys), current
        )

    @staticmethod
    def _not_a_container_error(path: str, prefix: str, current: Any) -> ValueError:
        """Build the error for a path segment that is neither a dict nor a list."""
        return ValueError(
            f"Cannot set nested property '{path}': '{prefix}' is a "
            f"{type(current).__name__}, not a dictionary or list"
        )

    @staticmethod
    def _navigate_list(container: list, key: str) -> Any:
        """
        Navigate into a list element during path traversal.

        Args:
            container: The list to index into
            key: Path segment (must be a non-negative integer)

        Returns:
            The list element at the given index

        Raises:
            ValueError: If key is not a valid index or is out of range
        """
        if not key.isdigit():
            raise ValueError(f"Cannot navigate list with non-numeric key: {key}")
        index = int(key)
        if index >= len(container):
            raise ValueError(
                f"List index out of range: {index} "
                f"for list of length {len(container)}"
            )
        return container[index]

    @staticmethod
    def _set_list_element(container: list, key: str, value: Any) -> None:
        """
        Set an element in a list by index or append with '+'.

        Args:
            container: The list to modify
            key: Index string or '+' for append
            value: Parsed value to set

        Raises:
            ValueError: If key is not a valid index or is out of range
        """
        if key == "+":
            container.append(value)
        elif key.isdigit():
            index = int(key)
            if index >= len(container):
                raise ValueError(
                    f"List index out of range: {index} "
                    f"for list of length {len(container)}"
                )
            container[index] = value
        else:
            raise ValueError(f"Cannot set list element with non-numeric key: {key}")

    @staticmethod
    def parse_value(value_str: str) -> Any:
        """
        Parse string value to appropriate type.

        Tries JSON parsing first (for numbers, bools, etc.), falls back to string.
        """
        import json

        try:
            return json.loads(value_str)
        except json.JSONDecodeError:
            return value_str
