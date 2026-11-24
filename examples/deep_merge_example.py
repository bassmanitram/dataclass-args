#!/usr/bin/env python3
"""
Deep merge example: the same layers built with merge_strategy="shallow" and "deep".

Dict values from different sources are merged one level deep by default
("shallow"). With merge_strategy="deep" they are merged recursively at every
depth. Lists always replace and an explicit None always clears, in both modes.

Run with no arguments:
    python deep_merge_example.py
"""

from dataclasses import dataclass, field
from typing import Any, Dict

from dataclass_args import MERGE_DEEP, MERGE_SHALLOW, build_config, deep_merge


@dataclass
class AppConfig:
    name: str = "app"
    db: Dict[str, Any] = field(default_factory=dict)


# Two in-memory layers, lowest precedence first (they could equally be files)
COMPANY_DEFAULTS = {
    "name": "app",
    "db": {"host": "localhost", "port": 5432, "pool": {"min": 1, "max": 10}},
}
TEAM_OVERRIDES = {
    "db": {"port": 3306, "pool": {"max": 50}, "timeout": 30},
}


def main() -> None:
    layers = [COMPANY_DEFAULTS, TEAM_OVERRIDES]

    shallow = build_config(AppConfig, [], base_configs=layers)
    deep = build_config(AppConfig, [], base_configs=layers, merge_strategy=MERGE_DEEP)

    print(f"merge_strategy={MERGE_SHALLOW!r} (default):")
    print(f"  db = {shallow.db}")
    print("  -> top-level db keys merged; the nested 'pool' dict was replaced")
    print()
    print(f"merge_strategy={MERGE_DEEP!r}:")
    print(f"  db = {deep.db}")
    print("  -> merged at every depth: pool.min kept, pool.max overridden")
    print()

    # The same semantics are available as a pure utility function
    merged = deep_merge(COMPANY_DEFAULTS, TEAM_OVERRIDES)
    print(f"deep_merge(...)['db']['pool'] = {merged['db']['pool']}")

    # Inputs are never mutated
    assert COMPANY_DEFAULTS["db"]["pool"] == {"min": 1, "max": 10}
    assert shallow.db["pool"] == {"max": 50}
    assert deep.db["pool"] == {"min": 1, "max": 50}
    print("\n✓ All assertions passed")


if __name__ == "__main__":
    main()
