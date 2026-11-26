"""
Configuration merging: normalize and merge base_configs + config files.

This module handles the first three stages of the config resolution pipeline:
    1. Normalize base_configs → List[Dict]  (files loaded, types validated)
    2. Apply base_configs → merged Dict     (one-level or deep merge, in order)
    3. Apply config file → merged Dict      (merged on top, same strategy)

Precedence (later wins):
    base_configs[0] < base_configs[1] < ... < --config file
"""

import argparse
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

from .config_applicator import ConfigApplicator
from .exceptions import ConfigBuilderError, ConfigurationError
from .merge_strategy import MERGE_DEEP, MERGE_SHALLOW, MergeContext
from .utils import copy_containers, load_structured_file

LIST_MERGE_REPLACE = "replace"
LIST_MERGE_RULES = "rules"
_LAYER_LIST_MERGES = (LIST_MERGE_REPLACE, LIST_MERGE_RULES)


@dataclass(frozen=True)
class ConfigLayer:
    """
    One named configuration layer for ``base_configs``.

    Attributes:
        data: A file path (loaded like a plain base_configs string) or a dict
        name: Optional label used in error messages (default: the file path,
            or "base_configs[i]" / "base_configs" for dicts)
        list_merge: "replace" (default; lists replace, like a plain item) or
            "rules" (lists at cli_list_merge-annotated locations are combined;
            requires merge_strategy="deep")

    Raises:
        ConfigBuilderError: At construction, before any I/O, if a value is invalid
    """

    data: Union[str, Dict[str, Any]]
    name: Optional[str] = None
    list_merge: str = LIST_MERGE_REPLACE

    def __post_init__(self) -> None:
        """Validate the layer."""
        if self.list_merge not in _LAYER_LIST_MERGES:
            raise ConfigBuilderError(
                f"list_merge must be 'replace' or 'rules', got {self.list_merge!r}"
            )
        if not isinstance(self.data, (str, dict)):
            raise ConfigBuilderError(
                f"ConfigLayer data must be a file path (str) or a dict, "
                f"got {type(self.data).__name__}"
            )
        if self.name is not None and (not isinstance(self.name, str) or not self.name):
            raise ConfigBuilderError(
                "ConfigLayer name must be a non-empty string or None, "
                f"got {self.name!r}"
            )


# Type alias for base_configs parameter
BaseConfigInput = Union[
    str,
    Dict[str, Any],
    ConfigLayer,
    List[Union[str, Dict[str, Any], ConfigLayer]],
]

# A normalized layer: (label, dict, list_merge)
LabeledLayer = Tuple[str, Dict[str, Any], str]


class ConfigMerger:
    """
    Handles normalization and merging of base configs and config files.

    Responsibilities:
    - Normalize base_configs input (strings, dicts, ConfigLayers, lists) to dicts
    - Load config files
    - Merge configs in order (one-level (default) or deep merge per merge_strategy)
    - Apply --config file on top of base_configs
    """

    def normalize_base_configs(
        self, base_configs: Optional[BaseConfigInput]
    ) -> List[Dict[str, Any]]:
        """
        Normalize base_configs input to list of dicts.

        Accepts:
        - None: Returns empty list
        - str: Load file, return list with one dict
        - dict: Return list with one dict
        - ConfigLayer: Load/copy its data, return list with one dict
        - list: Process each element (load files, keep dicts)

        Args:
            base_configs: Configuration input in various formats

        Returns:
            List of configuration dictionaries

        Raises:
            ConfigurationError: If file cannot be loaded or invalid type
        """
        return [
            layer for _, layer, _ in self.normalize_base_configs_labeled(base_configs)
        ]

    def normalize_base_configs_labeled(
        self, base_configs: Optional[BaseConfigInput]
    ) -> List[LabeledLayer]:
        """
        Normalize base_configs input to a list of (label, dict, list_merge) triples.

        Labels identify each layer in error messages: a ConfigLayer's name if
        given, otherwise the path for a string item, "base_configs[i]" for a
        dict in a list, and "base_configs" for a single dict.

        Args:
            base_configs: Configuration input in various formats

        Returns:
            List of (label, configuration dictionary, list_merge) triples

        Raises:
            ConfigurationError: If file cannot be loaded or invalid type
        """
        if base_configs is None:
            return []

        # List of strings, dicts and/or ConfigLayers
        if isinstance(base_configs, list):
            return [
                self._normalize_labeled_item(item, i, f"base_configs[{i}]")
                for i, item in enumerate(base_configs)
            ]

        # Single string path, dict or ConfigLayer
        if isinstance(base_configs, (str, dict, ConfigLayer)):
            return [self._normalize_labeled_item(base_configs, None, "base_configs")]

        raise ConfigurationError(
            "base_configs must be str, dict, ConfigLayer, or list, "
            f"got {type(base_configs).__name__}"
        )

    def _normalize_labeled_item(
        self, item: Any, index: Optional[int], dict_label: str
    ) -> LabeledLayer:
        """Normalize one base_configs item to a (label, dict, list_merge) triple."""
        name = None
        list_merge = LIST_MERGE_REPLACE
        if isinstance(item, ConfigLayer):
            name, list_merge, item = item.name, item.list_merge, item.data
        label = name or (item if isinstance(item, str) else dict_label)
        return (label, self._normalize_single_config(item, index, name), list_merge)

    def _normalize_single_config(
        self,
        item: Union[str, Dict[str, Any]],
        index: Optional[int],
        name: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Normalize a single config item (string path or dict).

        Args:
            item: Config item to normalize (str or dict)
            index: Index in list (None if single item)
            name: ConfigLayer name to use as the error location, if any

        Returns:
            Configuration dictionary

        Raises:
            ConfigurationError: If file cannot be loaded or invalid type
        """
        # Dict: return a copy so the caller's containers are never shared
        if isinstance(item, dict):
            return copy_containers(item)

        # String: load from file
        if isinstance(item, str):
            return self._load_config_file(item, index, name)

        # Invalid type: raise error
        self._raise_invalid_type_error(item, index)

    def _load_config_file(
        self, path: str, index: Optional[int], name: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Load configuration from file.

        Args:
            path: File path to load
            index: Index in list (None if single item)
            name: ConfigLayer name to use as the error location, if any

        Returns:
            Configuration dictionary

        Raises:
            ConfigurationError: If file cannot be loaded
        """
        try:
            return load_structured_file(path)
        except Exception as e:
            default = f"base_configs[{index}]" if index is not None else "base_configs"
            location = name or default
            raise ConfigurationError(
                f"Failed to load {location} from '{path}': {e}"
            ) from e

    def _raise_invalid_type_error(self, item: Any, index: Optional[int]) -> None:
        """
        Raise error for invalid config item type.

        Args:
            item: Invalid config item
            index: Index in list (None if single item)

        Raises:
            ConfigurationError: Always raises
        """
        type_name = type(item).__name__
        if index is not None:
            raise ConfigurationError(
                f"base_configs[{index}] must be str or dict, got {type_name}"
            )
        else:
            raise ConfigurationError(
                f"base_config item must be str or dict, got {type_name}"
            )

    def apply_base_configs(
        self,
        base_configs: List[Dict[str, Any]],
        ctx: MergeContext = MergeContext(),
        rules_layers: Optional[List[bool]] = None,
        labels: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Apply base configuration dictionaries (delegates to ConfigApplicator)."""
        return ConfigApplicator.apply_base_configs(
            base_configs, ctx, rules_layers, labels
        )

    def apply_config_file(
        self,
        config: Dict[str, Any],
        args: argparse.Namespace,
        base_config_name: str,
        normalize: Optional[Callable[[Dict[str, Any], str], Dict[str, Any]]] = None,
        ctx: MergeContext = MergeContext(),
    ) -> Dict[str, Any]:
        """Load and merge config from --config file (delegates to ConfigApplicator)."""
        return ConfigApplicator.apply_config_file(
            config, args, base_config_name, normalize, ctx
        )
