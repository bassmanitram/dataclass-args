#!/usr/bin/env python3
"""
Layered configuration example: named layers, list-merge rules and provenance.

A platform team ships defaults and mandatory overrides; a developer ships an
agent config in between. The overrides layer is a "rules" layer: annotated
list fields and dict paths *append* there instead of replacing, so the
platform can add a guardrail plugin without wiping the developer's plugins.
Provenance then tells you which layer set each value, and which developer
values a platform override changed.

Run with no arguments:
    python layered_config_example.py
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List

from dataclass_args import (
    ConfigLayer,
    build_config_from_dict,
    cli_list_merge,
    combine_annotations,
)


@dataclass
class AgentConfig:
    name: str = "agent"
    plugins: List[str] = combine_annotations(
        cli_list_merge("append_unique"), default_factory=list
    )
    skills: Dict[str, Any] = combine_annotations(
        cli_list_merge("append_unique", paths=["roots", "policy.denied"]),
        default_factory=dict,
    )


LAYERS = [
    ConfigLayer(
        {
            "plugins": ["telemetry"],
            "skills": {"policy": {"execution": "deny", "denied": ["exfil"]}},
        },
        name="defaults.d/10-platform",
    ),
    ConfigLayer(
        {
            "name": "support-bot",
            "plugins": ["crm"],
            "skills": {"roots": ["./skills"], "policy": {"execution": "allow"}},
        },
        name="agent.yaml",
    ),
    ConfigLayer(
        {
            "plugins": ["guardrail"],
            "skills": {"policy": {"execution": "deny", "denied": ["shell"]}},
        },
        name="overrides.d/50-security",
        list_merge="rules",
    ),
]


def main() -> None:
    config, prov = build_config_from_dict(
        AgentConfig,
        {},
        base_configs=LAYERS,
        merge_strategy="deep",
        return_provenance=True,
    )

    print(f"plugins = {config.plugins}")
    print(f"skills  = {config.skills}")
    print()

    print("Platform overrides that changed developer values:")
    for change in prov.changes():
        if (
            change.to_layer.startswith("overrides.d/")
            and change.from_layer == "agent.yaml"
        ):
            print(
                f"  {change.path}: {change.from_layer} set {change.from_value!r}, "
                f"{change.to_layer} changed it to {change.to_value!r}"
            )
    print()
    print(prov.explain())

    # 'agent.yaml' replaced the platform plugins (a replace layer); the rules
    # layer then appended the guardrail instead of wiping 'crm'.
    assert config.plugins == ["crm", "guardrail"]
    assert config.skills["policy"]["denied"] == ["exfil", "shell"]
    assert prov.source("skills.policy.execution") == "overrides.d/50-security"
    assert prov.source("name") == "agent.yaml"
    print("\n✓ All assertions passed")


if __name__ == "__main__":
    main()
