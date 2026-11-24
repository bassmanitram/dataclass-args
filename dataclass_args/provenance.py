"""
Provenance: which layer supplied each value, and what changed along the way.

Provenance describes the **raw** layer values: after layer normalization
(file loading, instance conversion) and CLI application, before ``@file``
resolution (stage 5) and ``cli_resolve`` (stage 8). The returned dataclass
instance holds the resolved values.

A path is the tuple of keys from the top-level field down (``("skills",
"policy", "execution")``), written ``"skills.policy.execution"`` externally.
Dicts are recursed into; everything else (lists, scalars, None, objects) is a
leaf. The recorder keeps a live map of leaf path to value and is fed explicit
"incoming leaves" by the pipeline stages that combine values. Nothing is
created when provenance is not requested.
"""

import dataclasses
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Mapping, Optional, Tuple

from .merge_strategy import merge_lists
from .utils import copy_containers, fresh_field_default

Path = Tuple[str, ...]

ACTION_SET = "set"
ACTION_REPLACED = "replaced"
ACTION_CONFIRMED = "confirmed"
ACTION_CLEARED = "cleared"
ACTION_APPENDED = "appended"
ACTION_REMOVED = "removed"

CLI_LAYER = "cli"
DEFAULT_SOURCE = "default"
EXPLAIN_VALUE_WIDTH = 60
_ELLIPSIS = "..."


class _MissingValue:
    """Sentinel for "no value" (the value of a ``removed`` entry)."""

    _instance: Optional["_MissingValue"] = None

    def __new__(cls) -> "_MissingValue":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __repr__(self) -> str:
        return "MISSING_VALUE"

    def __copy__(self) -> "_MissingValue":
        return self

    def __deepcopy__(self, memo: Any) -> "_MissingValue":
        return self

    def __reduce__(self) -> str:
        return "MISSING_VALUE"


MISSING_VALUE = _MissingValue()


@dataclass(frozen=True)
class ProvenanceEntry:
    """One layer's contribution to a path."""

    layer: str
    value: Any
    action: str  # set | replaced | confirmed | cleared | appended | removed


@dataclass(frozen=True)
class ProvenanceChange:
    """A place where a later layer discarded a value an earlier layer had set."""

    path: str
    from_layer: str
    from_value: Any
    to_layer: str
    to_value: Any
    action: str  # replaced | cleared | removed


def collect_leaves(prefix: Path, value: Any) -> Dict[Path, Any]:
    """
    Flatten `value` into leaves under `prefix`.

    Dicts are recursed into; any other value is a leaf. An empty dict becomes
    a marker (the dict itself) so callers can tell "supplied an empty dict".
    """
    if not isinstance(value, dict):
        return {prefix: value}
    if not value:
        return {prefix: {}} if prefix else {}
    leaves: Dict[Path, Any] = {}
    for key, item in value.items():
        leaves.update(collect_leaves(prefix + (str(key),), item))
    return leaves


def _list_context(
    prefix: Path, keys: List[str], target: Any
) -> Optional[Tuple[Path, Any, str]]:
    """
    Find the first list a property-override path goes through.

    Returns:
        (path of the list, the list, the key applied to it) or None if the path
        never goes through a list
    """
    current = target
    for index, key in enumerate(keys):
        if isinstance(current, list):
            return prefix + tuple(keys[:index]), current, key
        if not isinstance(current, dict) or key not in current:
            return None
        current = current[key]
    return None


def _is_prefix(prefix: Path, path: Path) -> bool:
    """True if `path` is strictly below `prefix`."""
    return len(path) > len(prefix) and path[: len(prefix)] == prefix


def _rebuild_subtree(base: Path, leaves: Dict[Path, Any]) -> Dict[str, Any]:
    """Rebuild the dict below `base` from its live leaves."""
    tree: Dict[str, Any] = {}
    for path in sorted(leaves):
        node = tree
        for key in path[len(base) : -1]:
            node = node.setdefault(key, {})
        node[path[-1]] = copy_containers(leaves[path])
    return tree


class ProvenanceRecorder:
    """Records layer events into a live leaf map (internal)."""

    def __init__(self, rules: Mapping[Path, str]):
        """
        Args:
            rules: Map of full key path to list-merge mode (cli_list_merge)
        """
        self._rules = rules
        self._entries: Dict[Path, List[ProvenanceEntry]] = {}
        self._live: Dict[Path, Any] = {}
        self._live_layer: Dict[Path, str] = {}
        self._live_seq: Dict[Path, int] = {}
        self._changes: List[ProvenanceChange] = []
        self._counter = 0

    # ------------------------------------------------------------------
    # Hooks
    # ------------------------------------------------------------------

    def record_layer(
        self, layer: str, data: Dict[str, Any], rules: bool = False
    ) -> None:
        """Record a whole layer (stages 2 and 3); `rules` marks a list-rules layer."""
        self._apply(layer, collect_leaves((), data), rules)

    def record_value(self, layer: str, path: Path, value: Any) -> None:
        """Record a value supplied at `path` (a dict contributes its leaves)."""
        self._apply(layer, collect_leaves(path, value), False)

    def record_override(
        self,
        layer: str,
        prefix: Path,
        keys: List[str],
        parsed: Any,
        target: Any,
    ) -> None:
        """
        Record one property override that has just been applied to `target`.

        Args:
            layer: Layer name
            prefix: Path of the dict field the override edits
            keys: The override's dotted path, split
            parsed: The parsed override value
            target: The edited dict (already updated)
        """
        found = _list_context(prefix, keys, target)
        if found is None:
            self._apply(layer, collect_leaves(prefix + tuple(keys), parsed), False)
            return
        list_path, actual, key = found
        if key == "+":
            self._record_appended(layer, list_path, [parsed], actual)
        else:
            self._apply(layer, {list_path: actual}, False)

    def finish(self, field_leaves: Mapping[Path, Any]) -> "Provenance":
        """Freeze the recording into a Provenance object."""
        return Provenance(
            self._entries,
            self._live,
            self._live_layer,
            self._changes,
            field_leaves,
        )

    # ------------------------------------------------------------------
    # Event processing
    # ------------------------------------------------------------------

    def _apply(self, layer: str, incoming: Dict[Path, Any], use_rules: bool) -> None:
        """Process incoming leaves in sorted path order."""
        for path in sorted(incoming):
            value = incoming[path]
            self._remove_leaf_ancestors(layer, path)
            if isinstance(value, dict):
                # An empty-dict marker supplies no leaf, but a live leaf at the
                # same path is replaced by a dict (non-dict -> dict)
                if path in self._live:
                    self._remove(layer, path)
                continue
            descendants = self._live_descendants(path)
            self._record_leaf(layer, path, value, descendants, use_rules)
            self._remove_descendants(layer, descendants)

    def _live_descendants(self, path: Path) -> Dict[Path, Any]:
        """The live leaves strictly below `path`."""
        return {p: v for p, v in self._live.items() if _is_prefix(path, p)}

    def _remove_leaf_ancestors(self, layer: str, path: Path) -> None:
        """A live leaf above `path` stops being a leaf (non-dict replaced by dict)."""
        for size in range(1, len(path)):
            ancestor = path[:size]
            if ancestor in self._live:
                self._remove(layer, ancestor)

    def _remove_descendants(self, layer: str, descendants: Dict[Path, Any]) -> None:
        """Remove each descendant of a path that became a leaf, in sorted order."""
        for descendant in sorted(descendants):
            self._remove(layer, descendant)

    def _remove(self, layer: str, path: Path) -> None:
        """Record that `layer` removed the live leaf at `path`."""
        self._changes.append(
            ProvenanceChange(
                ".".join(path),
                self._live_layer[path],
                copy_containers(self._live[path]),
                layer,
                MISSING_VALUE,
                ACTION_REMOVED,
            )
        )
        self._entries.setdefault(path, []).append(
            ProvenanceEntry(layer, MISSING_VALUE, ACTION_REMOVED)
        )
        for table in (self._live, self._live_layer, self._live_seq):
            del table[path]

    def _record_leaf(
        self,
        layer: str,
        path: Path,
        value: Any,
        descendants: Dict[Path, Any],
        use_rules: bool,
    ) -> None:
        """Classify and record one incoming leaf."""
        live_value = copy_containers(value)
        if path in self._live:
            action = self._live_action(path, value, use_rules)
            if action == ACTION_APPENDED:
                live_value = merge_lists(self._live[path], value, self._rules[path])
            elif action in (ACTION_REPLACED, ACTION_CLEARED):
                self._add_change(path, layer, value, action)
        elif descendants:
            action = ACTION_CLEARED if value is None else ACTION_REPLACED
            self._add_subtree_change(path, layer, value, action, descendants)
        else:
            action = ACTION_SET
        self._store(layer, path, copy_containers(value), action, live_value)

    def _live_action(self, path: Path, value: Any, use_rules: bool) -> str:
        """Action for a leaf that is already live."""
        old = self._live[path]
        if (
            use_rules
            and path in self._rules
            and isinstance(old, list)
            and isinstance(value, list)
        ):
            return ACTION_APPENDED
        if value == old:
            return ACTION_CONFIRMED
        return ACTION_CLEARED if value is None else ACTION_REPLACED

    def _record_appended(
        self, layer: str, path: Path, items: List[Any], actual: List[Any]
    ) -> None:
        """Record an append to the list at `path`; the live value is the actual list."""
        self._remove_leaf_ancestors(layer, path)
        self._store(
            layer,
            path,
            copy_containers(items),
            ACTION_APPENDED,
            copy_containers(actual),
        )

    def _store(
        self, layer: str, path: Path, entry_value: Any, action: str, live_value: Any
    ) -> None:
        """Append an entry and update the live map."""
        self._entries.setdefault(path, []).append(
            ProvenanceEntry(layer, entry_value, action)
        )
        self._counter += 1
        self._live[path] = live_value
        self._live_layer[path] = layer
        self._live_seq[path] = self._counter

    def _add_change(self, path: Path, layer: str, value: Any, action: str) -> None:
        """Record a replaced/cleared change over the live value at `path`."""
        self._changes.append(
            ProvenanceChange(
                ".".join(path),
                self._live_layer[path],
                copy_containers(self._live[path]),
                layer,
                copy_containers(value),
                action,
            )
        )

    def _add_subtree_change(
        self,
        path: Path,
        layer: str,
        value: Any,
        action: str,
        descendants: Dict[Path, Any],
    ) -> None:
        """Record a change over a sub-tree that stops being a dict."""
        newest = max(descendants, key=lambda p: self._live_seq[p])
        self._changes.append(
            ProvenanceChange(
                ".".join(path),
                self._live_layer[newest],
                _rebuild_subtree(path, descendants),
                layer,
                copy_containers(value),
                action,
            )
        )


class Provenance:
    """
    Read-only history of a build: which layer supplied each value.

    Describes the raw layer values; the instance holds resolved values.
    Every value returned is a copy, so neither callers nor later stages can
    alter the recorded history.
    """

    def __init__(
        self,
        entries: Dict[Path, List[ProvenanceEntry]],
        live: Dict[Path, Any],
        live_layer: Dict[Path, str],
        changes: List[ProvenanceChange],
        field_leaves: Mapping[Path, Any],
    ):
        """Built by the pipeline; not meant to be constructed by callers."""
        self._entries = entries
        self._live = live
        self._live_layer = live_layer
        self._changes = changes
        self._field_leaves = field_leaves

    @staticmethod
    def _key(path: str) -> Path:
        """Split a dotted path into its keys."""
        return tuple(path.split("."))

    def entries(self, path: str) -> List[ProvenanceEntry]:
        """Every layer that touched `path`, in application order ([] if none)."""
        return [
            ProvenanceEntry(e.layer, copy_containers(e.value), e.action)
            for e in self._entries.get(self._key(path), [])
        ]

    def source(self, path: str) -> Optional[str]:
        """
        The layer that supplied the final value at `path`.

        Returns "default" for a dataclass field that no layer set, and None for
        unknown paths, removed paths, nested-dataclass containers and keys
        inside dict fields that no layer set.
        """
        key = self._key(path)
        if key in self._live:
            return self._live_layer[key]
        if key in self._field_leaves and self._is_unset(key):
            return DEFAULT_SOURCE
        return None

    def _is_unset(self, key: Path) -> bool:
        """True if the path has no entries and no existing descendants."""
        if self._entries.get(key):
            return False
        return not any(_is_prefix(key, live_path) for live_path in self._live)

    def paths(self) -> List[str]:
        """Existing, layer-set leaf paths, sorted (defaults are not listed)."""
        return sorted(".".join(path) for path in self._live)

    def changes(self) -> List[ProvenanceChange]:
        """Where a later layer discarded an earlier value, chronologically."""
        return [
            ProvenanceChange(
                c.path,
                c.from_layer,
                copy_containers(c.from_value),
                c.to_layer,
                copy_containers(c.to_value),
                c.action,
            )
            for c in self._changes
        ]

    def explain(self) -> str:
        """A plain-text table: ``path | source | value``, then defaults."""
        rows = [("path", "source", "value")]
        for path in sorted(self._live):
            rows.append(
                (".".join(path), self._live_layer[path], _shorten(self._live[path]))
            )
        for path in sorted(self._field_leaves):
            if self._is_unset(path):
                default = fresh_field_default(self._field_leaves[path])
                rows.append(
                    (".".join(path), "(" + DEFAULT_SOURCE + ")", _shorten(default))
                )
        return "\n".join(" | ".join(row) for row in rows)


def _shorten(value: Any) -> str:
    """repr(value) truncated to EXPLAIN_VALUE_WIDTH characters."""
    text = "<no default>" if value is dataclasses.MISSING else repr(value)
    if len(text) <= EXPLAIN_VALUE_WIDTH:
        return text
    return text[: EXPLAIN_VALUE_WIDTH - len(_ELLIPSIS)] + _ELLIPSIS


def override_observer(
    ctx: Any, prefix: Path, target: Any
) -> Optional[Callable[[List[str], Any], None]]:
    """
    Build the property-override hook for a build, or None when provenance is off.

    Args:
        ctx: The build's MergeContext (its ``recorder`` may be None)
        prefix: Path of the dict field the overrides edit
        target: The dict being edited
    """
    recorder = ctx.recorder
    if recorder is None:
        return None

    def observe(keys: List[str], parsed: Any) -> None:
        recorder.record_override(CLI_LAYER, prefix, keys, parsed, target)

    return observe
