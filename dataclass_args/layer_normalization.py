"""
Layer normalization: resolve dict-field file references when a layer enters the pipeline.

A layer is one dict entering the pipeline (a base_configs item, the --config
file dict, or the internal layer built by build_config_from_dict). Normalizing
a layer before it is merged guarantees that merging and property overrides only
ever see dicts, never file-path strings, and that invalid nested values are
rejected instead of silently discarded.
"""

from dataclasses import dataclass, fields
from typing import Any, Dict, FrozenSet

from .exceptions import ConfigurationError
from .utils import copy_containers, load_structured_file, looks_like_structured_file


@dataclass(frozen=True)
class _Schema:
    """Schema for one dataclass level: all its field names, and the fields to normalize."""

    names: FrozenSet[str]
    entries: Dict[str, Any]


@dataclass(frozen=True)
class _NestedSchema:
    """Schema for a nested dataclass field: its class and its own level schema."""

    nested_class: type
    schema: _Schema


# Marker stored in a schema for a dict field
_DICT_FIELD = object()


def _field_name_aliases(
    layer: Dict[str, Any], field_names: FrozenSet[str]
) -> Dict[str, str]:
    """Map each hyphenated key whose underscore spelling is a field name to that spelling."""
    return {
        key: key.replace("-", "_")
        for key in layer
        if isinstance(key, str) and "-" in key and key.replace("-", "_") in field_names
    }


def check_both_spellings(
    layer: Dict[str, Any],
    field_names: FrozenSet[str],
    label: str,
    parent: str = "",
) -> Dict[str, str]:
    """
    Reject a layer that sets both spellings of a field name.

    Args:
        layer: Dict to check (not modified)
        field_names: Field names of the dataclass this layer level maps to
        label: Layer name used in error messages
        parent: Dotted path of this level ("" at top level)

    Returns:
        Map of hyphenated key to its underscore spelling (empty if none)

    Raises:
        ConfigurationError: If the layer sets both spellings of a field name
    """
    aliases = _field_name_aliases(layer, field_names)
    at = f" in '{parent}'" if parent else ""
    for key, alias in aliases.items():
        if alias in layer:
            raise ConfigurationError(
                f"Layer '{label}' sets both '{key}' and '{alias}'{at}"
            )
    return aliases


def normalize_field_name_keys(
    layer: Dict[str, Any],
    field_names: FrozenSet[str],
    label: str,
    parent: str = "",
) -> None:
    """
    Rename hyphenated field-name keys in `layer` to their underscore spelling.

    Keys whose underscore spelling is not a field name are left alone.

    Args:
        layer: Dict to normalize (modified in place; key order is preserved)
        field_names: Field names of the dataclass this layer level maps to
        label: Layer name used in error messages
        parent: Dotted path of this level ("" at top level)

    Raises:
        ConfigurationError: If the layer sets both spellings of a field name
    """
    aliases = check_both_spellings(layer, field_names, label, parent)
    if not aliases:
        return
    renamed = {aliases.get(key, key): value for key, value in layer.items()}
    layer.clear()
    layer.update(renamed)


class LayerNormalizer:
    """
    Normalizes configuration layers against a dataclass field schema.

    The schema is built once, recursively, from the analysed config fields.
    """

    def __init__(self, config_fields: Dict[str, Dict[str, Any]], config_class: type):
        """
        Build the normalization schema.

        Args:
            config_fields: Analyzed field information for the top-level dataclass
            config_class: The top-level dataclass (its field names include
                cli_exclude fields, which are not in `config_fields`)
        """
        self._schema = self._build_schema(config_fields, config_class)

    @staticmethod
    def _build_schema(
        config_fields: Dict[str, Dict[str, Any]], config_class: type
    ) -> _Schema:
        """Map dict fields to a marker and nested dataclass fields to nested schemas."""
        # Import here to avoid circular dependency
        from .builder import GenericConfigBuilder

        entries: Dict[str, Any] = {}
        for field_name, info in config_fields.items():
            if info.get("is_nested_dataclass", False):
                nested_class = info["type"]
                nested_fields = GenericConfigBuilder(nested_class)._config_fields
                entries[field_name] = _NestedSchema(
                    nested_class,
                    LayerNormalizer._build_schema(nested_fields, nested_class),
                )
            elif info.get("is_dict", False):
                entries[field_name] = _DICT_FIELD
        return _Schema(frozenset(f.name for f in fields(config_class)), entries)

    def normalize(self, layer: Dict[str, Any], label: str) -> Dict[str, Any]:
        """
        Normalize a layer: field-name keys, dict-field file refs, nested values.

        Hyphenated field-name keys are renamed to their underscore spelling at
        every level (never inside dict-field values) before anything else.

        Args:
            layer: Configuration layer (modified in place)
            label: Human-readable layer name used in error messages

        Returns:
            The same `layer` dict

        Raises:
            ConfigurationError: If a layer sets both spellings of a field name, a
                file reference cannot be loaded, or a nested field holds
                something other than a dict, instance or None
        """
        return self._normalize(layer, self._schema, label, "")

    def _normalize(
        self,
        layer: Dict[str, Any],
        schema: _Schema,
        label: str,
        prefix: str,
    ) -> Dict[str, Any]:
        """Normalize `layer` against `schema`; `prefix` is the dotted path so far."""
        normalize_field_name_keys(layer, schema.names, label, prefix.rstrip("."))
        for key, entry in schema.entries.items():
            if key not in layer:
                continue
            dotted = f"{prefix}{key}"
            if entry is _DICT_FIELD:
                layer[key] = self._load_dict_field(layer[key], dotted, label)
            else:
                layer[key] = self._normalize_nested(layer[key], entry, label, dotted)
        return layer

    def _normalize_nested(
        self, value: Any, entry: _NestedSchema, label: str, dotted: str
    ) -> Any:
        """
        Normalize a nested field value and return its replacement.

        An instance of the declared class becomes a dict of its init=True
        fields (values copied), so later layers combine with it exactly as
        with the equivalent dict. Dicts are normalized recursively; None is
        kept; anything else is rejected.
        """
        if isinstance(value, entry.nested_class):
            value = self._instance_to_dict(value, entry.nested_class)
        if isinstance(value, dict):
            return self._normalize(value, entry.schema, label, f"{dotted}.")
        if value is None:
            return None
        raise ConfigurationError(
            f"Nested field '{dotted}' in layer '{label}' expects a dict or "
            f"{entry.nested_class.__name__} instance, got {type(value).__name__}"
        )

    @staticmethod
    def _instance_to_dict(instance: Any, nested_class: type) -> Dict[str, Any]:
        """Return the init=True fields of `instance` (per the declared class), copied."""
        return {
            f.name: copy_containers(getattr(instance, f.name))
            for f in fields(nested_class)
            if f.init
        }

    @staticmethod
    def _load_dict_field(value: Any, dotted: str, label: str) -> Any:
        """Load a structured-file reference; return any other value unchanged."""
        if not isinstance(value, str) or not looks_like_structured_file(value):
            return value
        try:
            return load_structured_file(value)
        except Exception as e:
            raise ConfigurationError(
                f"Failed to load dict field '{dotted}' from '{value}' "
                f"in layer '{label}': {e}"
            ) from e
