"""
Merge strategy: constants, per-call context and the dict combination helper.

A merge strategy decides how two dicts that meet at a combination site are
combined: one level deep ("shallow", the default) or recursively ("deep").
The strategy is validated once per build and travels through the pipeline as a
MergeContext method parameter, never as state on the long-lived processors.

This is a leaf module so that every pipeline stage can import it without
creating an import cycle. The public constants are re-exported from
``config_merging`` and the package root.
"""

from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any, Callable, Dict, List, Mapping, Optional, Tuple

from .annotations import LIST_MERGE_APPEND
from .exceptions import ConfigBuilderError
from .utils import copy_containers, deep_merge

MERGE_SHALLOW = "shallow"
MERGE_DEEP = "deep"


@dataclass(frozen=True)
class MergeContext:
    """
    Per-build merge settings, passed as a method parameter to each stage.

    Attributes:
        strategy: "shallow" or "deep"
        list_rules: Map of full key path to list-merge mode, built from the
            cli_list_merge annotations (read-only; empty by default)
        recorder: Provenance recorder, or None (the default) when provenance
            was not requested; every hook is a single ``is not None`` check
    """

    strategy: str = MERGE_SHALLOW
    list_rules: Mapping[Tuple[str, ...], str] = field(
        default_factory=lambda: MappingProxyType({})
    )
    recorder: Optional[Any] = field(default=None, compare=False, repr=False)


def make_merge_context(
    merge_strategy: Any,
    list_rules: Optional[Mapping[Tuple[str, ...], str]] = None,
    recorder: Optional[Any] = None,
) -> MergeContext:
    """
    Validate a merge_strategy value and build the context for one call.

    Args:
        merge_strategy: Value given by the caller
        list_rules: Optional map of key path to list-merge mode
        recorder: Optional provenance recorder

    Returns:
        A MergeContext carrying the validated strategy

    Raises:
        ConfigBuilderError: If the value is not exactly 'shallow' or 'deep'
    """
    if not isinstance(merge_strategy, str) or merge_strategy not in (
        MERGE_SHALLOW,
        MERGE_DEEP,
    ):
        raise ConfigBuilderError(
            f"merge_strategy must be 'shallow' or 'deep', got {merge_strategy!r}"
        )
    return MergeContext(
        strategy=merge_strategy,
        list_rules=MappingProxyType(dict(list_rules or {})),
        recorder=recorder,
    )


def one_level_update(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    """Return a new dict with `override`'s keys replacing `base`'s (one level)."""
    return {**base, **override}


def merge_lists(base: List[Any], override: List[Any], mode: str) -> List[Any]:
    """Combine two lists according to a list-merge mode (new list, copied elements)."""
    result = copy_containers(base)
    if mode == LIST_MERGE_APPEND:
        return result + copy_containers(override)
    # append_unique: the earlier list keeps its own duplicates; later elements are
    # added when not == to anything already present (works for unhashable values)
    for item in override:
        if not any(item == existing for existing in result):
            result.append(copy_containers(item))
    return result


def _merge_rule_value(
    base_value: Any,
    override_value: Any,
    rules: Mapping[Tuple[str, ...], str],
    path: Tuple[str, ...],
) -> Any:
    """Merge two values at `path`: dicts recurse, ruled lists combine, else override."""
    if isinstance(base_value, dict) and isinstance(override_value, dict):
        return merge_with_rules(base_value, override_value, rules, path)
    mode = rules.get(path)
    if mode and isinstance(base_value, list) and isinstance(override_value, list):
        return merge_lists(base_value, override_value, mode)
    return copy_containers(override_value)


def merge_with_rules(
    base: Dict[str, Any],
    override: Dict[str, Any],
    rules: Mapping[Tuple[str, ...], str],
    path: Tuple[str, ...] = (),
) -> Dict[str, Any]:
    """
    Deep-merge `override` onto `base`, combining lists at ruled paths.

    Identical to ``deep_merge`` except at a path listed in `rules` where both
    values are lists: there the lists are combined per the rule's mode. If
    either side is not a list the override wins as usual (so None clears).

    Args:
        base: Dict to merge onto
        override: Dict whose values win
        rules: Map of full key path to list-merge mode
        path: Key path of `base` within the whole config (used by recursion)

    Returns:
        A new merged dict sharing no containers with either input
    """
    result: Dict[str, Any] = {}
    for key, base_value in base.items():
        if key in override:
            result[key] = _merge_rule_value(
                base_value, override[key], rules, path + (key,)
            )
        else:
            result[key] = copy_containers(base_value)
    for key, value in override.items():
        if key not in base:
            result[key] = copy_containers(value)
    return result


def combine_dicts(
    base: Dict[str, Any],
    override: Dict[str, Any],
    ctx: MergeContext,
    shallow: Callable[
        [Dict[str, Any], Dict[str, Any]], Dict[str, Any]
    ] = one_level_update,
    rules: bool = False,
) -> Dict[str, Any]:
    """
    Combine two dicts according to the merge strategy.

    Args:
        base: Existing dict
        override: Dict applied on top
        ctx: Merge context of the current build
        shallow: The one-level combination used by the calling site in shallow
            mode (defaults to a plain key update)
        rules: Apply the context's list-merge rules (deep mode only; used for
            stage-2 layers declared with list_merge="rules")

    Returns:
        The combined dict (deep mode: a new dict that shares no containers
        with either input)
    """
    if ctx.strategy == MERGE_DEEP:
        if rules:
            return merge_with_rules(base, override, ctx.list_rules)
        return deep_merge(base, override)
    return shallow(base, override)
