"""
Tests for ConfigLayer, the cli_list_merge annotation, the rule map and the list
rules applied at stage 2 (CR Part B, oracles B1-B12).
"""

import argparse
import json
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import pytest

import dataclass_args
from dataclass_args import (
    ConfigBuilderError,
    ConfigLayer,
    ConfigurationError,
    build_config,
    build_config_from_cli,
    build_config_from_dict,
    cli_append,
    cli_exclude,
    cli_help,
    cli_list_merge,
    cli_nested,
    cli_positional,
    cli_resolve,
    cli_short,
    combine_annotations,
    get_cli_list_merge,
)
from dataclass_args.builder import GenericConfigBuilder
from dataclass_args.merge_strategy import MergeContext, merge_with_rules

DEEP = "deep"
RULES = "rules"


@dataclass
class P:
    plugins: List[str] = combine_annotations(
        cli_list_merge("append_unique"), default_factory=list
    )
    tags: List[str] = field(default_factory=list)
    skills: Dict[str, Any] = combine_annotations(
        cli_list_merge("append_unique", paths=["roots", "policy.denied"]),
        default_factory=dict,
    )


def rules_layer(data, name=None):
    return ConfigLayer(data, name=name, list_merge=RULES)


def build(config_class, layers, args=None, **kwargs):
    return build_config(
        config_class, args or [], base_configs=layers, merge_strategy=DEEP, **kwargs
    )


# ---------------------------------------------------------------------------
# ConfigLayer
# ---------------------------------------------------------------------------


def test_config_layer_defaults():
    layer = ConfigLayer({"a": 1})
    assert layer.data == {"a": 1}
    assert layer.name is None
    assert layer.list_merge == "replace"


@pytest.mark.parametrize("bad", ["sometimes", "", None, True, "Rules"])
def test_B11_invalid_list_merge_raises_at_construction(bad):
    with pytest.raises(ConfigBuilderError) as exc:
        ConfigLayer({}, list_merge=bad)
    assert "list_merge must be 'replace' or 'rules'" in str(exc.value)


@pytest.mark.parametrize("bad", [5, None, ["a"], ("a",)])
def test_config_layer_data_must_be_str_or_dict(bad):
    with pytest.raises(ConfigBuilderError) as exc:
        ConfigLayer(bad)
    assert "data must be" in str(exc.value)


@pytest.mark.parametrize("bad", ["", 5, ["x"]])
def test_config_layer_name_must_be_non_empty_string(bad):
    with pytest.raises(ConfigBuilderError) as exc:
        ConfigLayer({}, name=bad)
    assert "name must be" in str(exc.value)


def test_config_layer_is_frozen():
    with pytest.raises(Exception):
        ConfigLayer({}).name = "x"


def test_exports():
    from dataclass_args import ConfigLayer as exported_layer
    from dataclass_args import cli_list_merge as exported_annotation

    assert exported_layer is ConfigLayer
    assert exported_annotation is cli_list_merge
    for name in ("ConfigLayer", "cli_list_merge", "get_cli_list_merge"):
        assert name in dataclass_args.__all__


def test_config_layer_accepted_as_single_value_and_in_lists():
    single = build_config(P, [], base_configs=ConfigLayer({"tags": ["a"]}))
    assert single.tags == ["a"]

    mixed = build_config(
        P,
        [],
        base_configs=[
            {"tags": ["a"]},
            ConfigLayer({"tags": ["b"]}),
            {"plugins": ["c"]},
        ],
    )
    assert mixed.tags == ["b"]
    assert mixed.plugins == ["c"]


def test_config_layer_with_file_path_data(tmp_path):
    path = tmp_path / "layer.yaml"
    path.write_text("tags: [x]\n")
    result = build_config(P, [], base_configs=ConfigLayer(str(path), name="defaults"))
    assert result.tags == ["x"]


def test_config_layer_dict_data_is_copied():
    data = {"tags": ["a"]}
    result = build_config(P, ["--tags", "z"], base_configs=ConfigLayer(data))
    assert result.tags == ["z"]
    result = build(P, [ConfigLayer(data)])
    result.tags.append("mutated")
    assert data == {"tags": ["a"]}


# ---------------------------------------------------------------------------
# Labels
# ---------------------------------------------------------------------------


def test_load_error_names_the_layer():
    with pytest.raises(ConfigurationError) as exc:
        build_config(
            P, [], base_configs=ConfigLayer("missing.yaml", name="defaults.d/10")
        )
    assert "defaults.d/10" in str(exc.value)


def test_load_error_without_name_keeps_default_location():
    with pytest.raises(ConfigurationError) as exc:
        build_config(P, [], base_configs=[{"tags": []}, ConfigLayer("missing.yaml")])
    assert "base_configs[1]" in str(exc.value)


def test_dict_field_file_ref_error_names_the_layer():
    with pytest.raises(ConfigurationError) as exc:
        build_config(
            P,
            [],
            base_configs=ConfigLayer({"skills": "missing.yaml"}, name="agent.yaml"),
        )
    assert "agent.yaml" in str(exc.value)


def test_normalize_base_configs_still_returns_plain_dicts():
    from dataclass_args.config_merging import ConfigMerger

    merger = ConfigMerger()
    result = merger.normalize_base_configs([{"a": 1}, ConfigLayer({"b": 2}, name="n")])
    assert result == [{"a": 1}, {"b": 2}]


def test_labeled_normalization_triples():
    from dataclass_args.config_merging import ConfigMerger

    labeled = ConfigMerger().normalize_base_configs_labeled(
        [{"a": 1}, ConfigLayer({"b": 2}, name="n", list_merge="rules"), {"c": 3}]
    )
    assert labeled == [
        ("base_configs[0]", {"a": 1}, "replace"),
        ("n", {"b": 2}, "rules"),
        ("base_configs[2]", {"c": 3}, "replace"),
    ]


# ---------------------------------------------------------------------------
# cli_list_merge annotation
# ---------------------------------------------------------------------------


def test_annotation_metadata_and_accessor():
    list_field = cli_list_merge("append", default_factory=list)
    assert list_field.metadata["cli_list_merge"] == {"mode": "append", "paths": None}

    dict_field = cli_list_merge(
        "append_unique", paths=["a", "b.c"], default_factory=dict
    )
    assert dict_field.metadata["cli_list_merge"] == {
        "mode": "append_unique",
        "paths": ["a", "b.c"],
    }

    builder = GenericConfigBuilder(P)
    assert get_cli_list_merge(builder._config_fields["plugins"]) == {
        "mode": "append_unique",
        "paths": None,
    }
    assert get_cli_list_merge(builder._config_fields["tags"]) is None


@pytest.mark.parametrize(
    "mode, paths",
    [
        ("bogus", None),
        ("prepend", None),
        ("append", []),
        ("append", [""]),
        ("append", ["a..b"]),
        ("append", [".a"]),
        ("append", ["a."]),
    ],
)
def test_B10_invalid_annotation_raises_value_error(mode, paths):
    with pytest.raises(ValueError):
        cli_list_merge(mode, paths=paths)


def test_B10_hand_built_bad_metadata_raises_at_builder_construction():
    @dataclass
    class Bad:
        items: List[str] = field(
            default_factory=list,
            metadata={"cli_list_merge": {"mode": "bogus", "paths": None}},
        )

    with pytest.raises(ConfigBuilderError) as exc:
        GenericConfigBuilder(Bad)
    assert "'items'" in str(exc.value)
    assert "mode" in str(exc.value)


def test_paths_on_list_field_rejected():
    @dataclass
    class Bad:
        items: List[str] = combine_annotations(
            cli_list_merge("append", paths=["a"]), default_factory=list
        )

    with pytest.raises(ConfigBuilderError) as exc:
        GenericConfigBuilder(Bad)
    assert "'items'" in str(exc.value)
    assert "paths" in str(exc.value)


def test_missing_paths_on_dict_field_rejected():
    @dataclass
    class Bad:
        settings: Dict[str, Any] = combine_annotations(
            cli_list_merge("append"), default_factory=dict
        )

    with pytest.raises(ConfigBuilderError) as exc:
        GenericConfigBuilder(Bad)
    assert "'settings'" in str(exc.value)
    assert "requires 'paths'" in str(exc.value)


def test_scalar_field_rejected():
    @dataclass
    class Bad:
        name: str = combine_annotations(cli_list_merge("append"), default="x")

    with pytest.raises(ConfigBuilderError) as exc:
        GenericConfigBuilder(Bad)
    assert "'name'" in str(exc.value)
    assert "list or dict" in str(exc.value)


def test_cli_nested_field_rejected_with_pointer_to_inner_fields():
    @dataclass
    class Inner:
        tags: List[str] = field(default_factory=list)

    @dataclass
    class Bad:
        inner: Inner = combine_annotations(
            cli_nested(), cli_list_merge("append"), default_factory=Inner
        )

    with pytest.raises(ConfigBuilderError) as exc:
        GenericConfigBuilder(Bad)
    assert "'inner'" in str(exc.value)
    assert "inside the nested dataclass" in str(exc.value)


def test_invalid_annotation_inside_nested_class_is_reported():
    @dataclass
    class Inner:
        name: str = combine_annotations(cli_list_merge("append"), default="x")

    @dataclass
    class Outer:
        inner: Inner = cli_nested(default_factory=Inner)

    with pytest.raises(ConfigBuilderError) as exc:
        GenericConfigBuilder(Outer)
    assert "'name'" in str(exc.value)


def test_compatible_with_cli_resolve_list_and_dict_fields():
    seen: List[Any] = []

    def resolver(value):
        seen.append(value)
        return value

    @dataclass
    class Resolved:
        plugins: List[str] = combine_annotations(
            cli_resolve(resolver=resolver),
            cli_list_merge("append"),
            default_factory=list,
        )
        skills: Any = combine_annotations(
            cli_resolve(resolver=resolver),
            cli_list_merge("append", paths=["roots"]),
            default=None,
        )

    GenericConfigBuilder(Resolved)
    result = build(
        Resolved,
        [
            {"plugins": ["a"], "skills": {"roots": ["x"]}},
            rules_layer({"plugins": ["b"], "skills": {"roots": ["y"]}}),
        ],
    )
    assert result.plugins == ["a", "b"]
    assert result.skills == {"roots": ["x", "y"]}
    assert ["a", "b"] in seen
    assert {"roots": ["x", "y"]} in seen


def test_cli_resolve_dict_field_without_paths_rejected():
    @dataclass
    class Bad:
        sb: Any = combine_annotations(
            cli_resolve(resolver=lambda v: v), cli_list_merge("append"), default=None
        )

    with pytest.raises(ConfigBuilderError) as exc:
        GenericConfigBuilder(Bad)
    assert "'sb'" in str(exc.value)


def test_compatible_with_cli_append_help_short_positional_and_exclude():
    @dataclass
    class Mixed:
        files: List[List[str]] = combine_annotations(
            cli_append(), cli_list_merge("append"), default_factory=list
        )
        names: List[str] = combine_annotations(
            cli_help("names"),
            cli_short("n"),
            cli_list_merge("append"),
            default_factory=list,
        )
        rest: List[str] = combine_annotations(
            cli_positional(nargs="*"), cli_list_merge("append"), default_factory=list
        )
        hidden: List[str] = combine_annotations(
            cli_exclude(), cli_list_merge("append"), default_factory=list
        )

    builder = GenericConfigBuilder(Mixed)
    assert set(builder.list_merge_rules) == {
        ("files",),
        ("names",),
        ("rest",),
        ("hidden",),
    }


# ---------------------------------------------------------------------------
# Rule map
# ---------------------------------------------------------------------------


def test_rule_map_for_list_and_dict_fields():
    rules = GenericConfigBuilder(P).list_merge_rules
    assert rules == {
        ("plugins",): "append_unique",
        ("skills", "roots"): "append_unique",
        ("skills", "policy", "denied"): "append_unique",
    }


def test_rule_map_reads_cli_exclude_fields():
    @dataclass
    class Hidden:
        secrets: List[str] = combine_annotations(
            cli_exclude(), cli_list_merge("append"), default_factory=list
        )

    assert GenericConfigBuilder(Hidden).list_merge_rules == {("secrets",): "append"}


@dataclass
class Leaf:
    tags: List[str] = combine_annotations(
        cli_list_merge("append_unique"), default_factory=list
    )
    skills: Dict[str, Any] = combine_annotations(
        cli_list_merge("append", paths=["roots"]), default_factory=dict
    )
    hidden: List[str] = combine_annotations(
        cli_exclude(), cli_list_merge("append"), default_factory=list
    )
    plain: List[str] = field(default_factory=list)


@dataclass
class Mid:
    leaf: Leaf = cli_nested(default_factory=Leaf)
    tags: List[str] = combine_annotations(
        cli_list_merge("append"), default_factory=list
    )


@dataclass
class Top:
    mid: Mid = cli_nested(default_factory=Mid)
    plugins: List[str] = combine_annotations(
        cli_list_merge("append_unique"), default_factory=list
    )


def test_rule_map_uses_full_paths_at_any_depth():
    assert GenericConfigBuilder(Top).list_merge_rules == {
        ("plugins",): "append_unique",
        ("mid", "tags"): "append",
        ("mid", "leaf", "tags"): "append_unique",
        ("mid", "leaf", "skills", "roots"): "append",
        ("mid", "leaf", "hidden"): "append",
    }


def test_rule_map_empty_without_annotations():
    @dataclass
    class Plain:
        tags: List[str] = field(default_factory=list)

    assert GenericConfigBuilder(Plain).list_merge_rules == {}


# ---------------------------------------------------------------------------
# merge_with_rules unit
# ---------------------------------------------------------------------------


def test_merge_with_rules_append_keeps_duplicates():
    rules = {("a",): "append"}
    assert merge_with_rules({"a": ["a"]}, {"a": ["a", "b"]}, rules) == {
        "a": ["a", "a", "b"]
    }


def test_merge_with_rules_append_unique_dedups_within_later_list():
    rules = {("a",): "append_unique"}
    assert merge_with_rules({"a": []}, {"a": ["a", "a"]}, rules) == {"a": ["a"]}


def test_merge_with_rules_append_unique_keeps_base_duplicates():
    rules = {("a",): "append_unique"}
    result = merge_with_rules({"a": ["x", "x"]}, {"a": ["x", "y"]}, rules)
    assert result == {"a": ["x", "x", "y"]}


def test_B8_append_unique_works_for_unhashable_elements():
    rules = {("a",): "append_unique"}
    result = merge_with_rules(
        {"a": [{"id": 1}]}, {"a": [{"id": 1}, {"id": 2}, [3], [3]]}, rules
    )
    assert result == {"a": [{"id": 1}, {"id": 2}, [3]]}


def test_merge_with_rules_non_list_sides_override():
    rules = {("a",): "append"}
    assert merge_with_rules({"a": ["dev"]}, {"a": "str"}, rules) == {"a": "str"}
    assert merge_with_rules({"a": "str"}, {"a": ["g"]}, rules) == {"a": ["g"]}
    assert merge_with_rules({"a": ["dev"]}, {"a": None}, rules) == {"a": None}
    assert merge_with_rules({"a": None}, {"a": ["g"]}, rules) == {"a": ["g"]}
    assert merge_with_rules({"a": {"x": 1}}, {"a": ["g"]}, rules) == {"a": ["g"]}


def test_merge_with_rules_without_rule_lists_replace():
    assert merge_with_rules({"a": [1]}, {"a": [2]}, {}) == {"a": [2]}


def test_merge_with_rules_matches_deep_merge_when_no_rules_apply():
    base = {"a": 1, "d": {"x": [1], "y": {"z": 1}}, "keep": [1]}
    override = {"a": 2, "d": {"x": [2], "y": {"w": 2}}, "new": {"n": 1}}
    assert merge_with_rules(base, override, {}) == dataclass_args.deep_merge(
        base, override
    )


def test_merge_with_rules_fresh_containers_and_no_mutation():
    rules = {("d", "items"): "append"}
    base = {"d": {"items": [{"k": 1}]}, "only": [[1]]}
    override = {"d": {"items": [{"k": 2}]}, "new": [{"n": 1}]}
    snapshot = json.loads(json.dumps([base, override]))

    result = merge_with_rules(base, override, rules)
    result["d"]["items"][0]["k"] = 99
    result["d"]["items"][1]["k"] = 99
    result["only"][0].append(99)
    result["new"][0]["n"] = 99

    assert [base, override] == snapshot


def test_merge_context_list_rules_default_is_empty_and_read_only():
    ctx = MergeContext()
    assert dict(ctx.list_rules) == {}
    with pytest.raises(TypeError):
        ctx.list_rules[("a",)] = "append"  # type: ignore[index]


# ---------------------------------------------------------------------------
# B1-B12 oracles
# ---------------------------------------------------------------------------


def test_B1_replace_layers_replace_lists():
    result = build(P, [{"plugins": ["a"]}, {"plugins": ["b"]}])
    assert result.plugins == ["b"]


def test_B2_rules_layer_appends():
    result = build(P, [{"plugins": ["dev"]}, rules_layer({"plugins": ["guard"]})])
    assert result.plugins == ["dev", "guard"]


def test_B3_append_unique_keeps_order_and_dedups():
    result = build(
        P, [{"plugins": ["guard", "dev"]}, rules_layer({"plugins": ["guard"]})]
    )
    assert result.plugins == ["guard", "dev"]


def test_B4_unannotated_list_replaces_in_rules_layer():
    result = build(P, [{"tags": ["x"]}, rules_layer({"tags": ["y"]})])
    assert result.tags == ["y"]


def test_B5_dict_field_paths():
    result = build(
        P,
        [
            {
                "skills": {
                    "roots": ["./sk"],
                    "policy": {"denied": ["old"], "execution": "allow"},
                }
            },
            rules_layer(
                {"skills": {"policy": {"denied": ["exfil"], "execution": "deny"}}}
            ),
        ],
    )
    assert result.skills == {
        "roots": ["./sk"],
        "policy": {"denied": ["old", "exfil"], "execution": "deny"},
    }


def test_B6_rules_layer_without_earlier_value():
    result = build(P, [rules_layer({"plugins": ["guard"]})])
    assert result.plugins == ["guard"]


def test_B7_explicit_none_clears():
    result = build(P, [{"plugins": ["dev"]}, rules_layer({"plugins": None})])
    assert result.plugins is None


def test_B8_unhashable_elements_through_a_build():
    @dataclass
    class Items:
        items: List[Dict[str, Any]] = combine_annotations(
            cli_list_merge("append_unique"), default_factory=list
        )

    result = build(
        Items,
        [{"items": [{"id": 1}]}, rules_layer({"items": [{"id": 1}, {"id": 2}]})],
    )
    assert result.items == [{"id": 1}, {"id": 2}]


def test_B9_from_dict_config_layer_with_rules():
    result = build_config_from_dict(
        P,
        {"plugins": ["rt"]},
        base_configs=[{"plugins": ["dev"]}],
        merge_strategy=DEEP,
        config_list_merge=RULES,
    )
    assert result.plugins == ["dev", "rt"]


def test_B9_from_dict_config_layer_replace_by_default():
    result = build_config_from_dict(
        P,
        {"plugins": ["rt"]},
        base_configs=[{"plugins": ["dev"]}],
        merge_strategy=DEEP,
    )
    assert result.plugins == ["rt"]


def test_B12_real_cli_values_always_replace():
    result = build_config_from_cli(
        P,
        ["--plugins", "x"],
        base_configs=[{"plugins": ["dev"]}, rules_layer({"plugins": ["g"]})],
        merge_strategy=DEEP,
    )
    assert result.plugins == ["x"]


def test_config_file_always_replaces_lists(tmp_path):
    config_file = tmp_path / "c.yaml"
    config_file.write_text("plugins: [file]\n")

    result = build(
        P,
        [{"plugins": ["dev"]}, rules_layer({"plugins": ["g"]})],
        args=["--config", str(config_file)],
    )
    assert result.plugins == ["file"]


# ---------------------------------------------------------------------------
# Additional oracles
# ---------------------------------------------------------------------------


def test_layer_order_interleaves_rules_and_replace_layers():
    result = build(
        P,
        [
            {"plugins": ["a"]},
            rules_layer({"plugins": ["b"]}),
            rules_layer({"plugins": ["c"]}),
            {"plugins": ["z"]},
            rules_layer({"plugins": ["d"]}),
        ],
    )
    assert result.plugins == ["z", "d"]


def test_rules_at_depth_two_levels():
    result = build(
        Top,
        [
            {
                "mid": {
                    "tags": ["a"],
                    "leaf": {"tags": ["x"], "skills": {"roots": ["r1"]}},
                }
            },
            rules_layer(
                {
                    "mid": {
                        "tags": ["a", "b"],
                        "leaf": {"tags": ["x", "y"], "skills": {"roots": ["r2"]}},
                    }
                }
            ),
        ],
    )
    assert result.mid.tags == ["a", "a", "b"]
    assert result.mid.leaf.tags == ["x", "y"]
    assert result.mid.leaf.skills == {"roots": ["r1", "r2"]}


def test_rules_apply_to_cli_exclude_list_fields():
    result = build(
        Top,
        [
            {"mid": {"leaf": {"hidden": ["a"]}}},
            rules_layer({"mid": {"leaf": {"hidden": ["b"]}}}),
        ],
    )
    assert result.mid.leaf.hidden == ["a", "b"]


def test_unannotated_nested_list_replaces():
    result = build(
        Top,
        [
            {"mid": {"leaf": {"plain": ["a"]}}},
            rules_layer({"mid": {"leaf": {"plain": ["b"]}}}),
        ],
    )
    assert result.mid.leaf.plain == ["b"]


def test_rules_with_nested_instances_in_layers():
    result = build(
        Top,
        [
            {"mid": Mid(tags=["a"])},
            rules_layer({"mid": Mid(tags=["b"])}),
        ],
    )
    assert result.mid.tags == ["a", "b"]


def test_file_ref_loaded_then_rules_apply(tmp_path):
    skills_file = tmp_path / "skills.yaml"
    skills_file.write_text("roots: [a]\n")

    result = build(
        P,
        [{"skills": str(skills_file)}, rules_layer({"skills": {"roots": ["b"]}})],
    )
    assert result.skills == {"roots": ["a", "b"]}


def test_rules_apply_to_raw_values_before_cli_resolve():
    seen: List[Any] = []

    def resolver(value):
        seen.append(list(value))
        return [item.upper() for item in value]

    @dataclass
    class Resolved:
        plugin_config_paths: List[str] = combine_annotations(
            cli_resolve(resolver=resolver),
            cli_list_merge("append_unique"),
            default_factory=list,
        )

    result = build(
        Resolved,
        [
            {"plugin_config_paths": ["a.yaml"]},
            rules_layer({"plugin_config_paths": ["b.yaml", "a.yaml"]}),
        ],
    )
    assert seen == [["a.yaml", "b.yaml"]]
    assert result.plugin_config_paths == ["A.YAML", "B.YAML"]


def test_hyphenated_keys_are_normalized_before_rules_apply():
    @dataclass
    class Hyphen:
        my_plugins: List[str] = combine_annotations(
            cli_list_merge("append"), default_factory=list
        )

    hyphenated = build(
        Hyphen, [{"my_plugins": ["a"]}, rules_layer({"my-plugins": ["b"]})]
    )
    assert hyphenated.my_plugins == ["a", "b"]


def test_caller_layer_data_is_not_mutated_by_rules():
    first = {"plugins": ["a"]}
    second = {"plugins": ["b"]}
    result = build(P, [first, rules_layer(second)])
    result.plugins.append("c")
    assert first == {"plugins": ["a"]}
    assert second == {"plugins": ["b"]}


# ---------------------------------------------------------------------------
# Shallow mode and validation before I/O
# ---------------------------------------------------------------------------


def test_shallow_with_rules_layer_raises_before_any_file_is_loaded():
    with pytest.raises(ConfigBuilderError) as exc:
        build_config(
            P,
            [],
            base_configs=["/nonexistent/never/loaded.yaml", rules_layer({"tags": []})],
        )
    assert "list_merge='rules' requires merge_strategy='deep'" in str(exc.value)


def test_shallow_single_rules_layer_raises():
    with pytest.raises(ConfigBuilderError):
        build_config(P, [], base_configs=rules_layer({"tags": []}))


def test_shallow_with_config_list_merge_rules_raises():
    with pytest.raises(ConfigBuilderError) as exc:
        build_config_from_dict(
            P,
            {"plugins": []},
            base_configs="/nonexistent/never/loaded.yaml",
            config_list_merge=RULES,
        )
    assert "requires merge_strategy='deep'" in str(exc.value)


def test_invalid_merge_strategy_is_reported_before_rules_check():
    with pytest.raises(ConfigBuilderError) as exc:
        build_config(
            P,
            [],
            base_configs=rules_layer({}),
            merge_strategy="nope",
        )
    assert "merge_strategy must be" in str(exc.value)


def test_replace_config_layer_in_shallow_mode_equals_plain_dict():
    layers_plain = [{"db": {"a": {"x": 1}}}, {"db": {"a": {"y": 2}}}]
    layers_wrapped = [
        ConfigLayer({"db": {"a": {"x": 1}}}),
        ConfigLayer({"db": {"a": {"y": 2}}}, name="second", list_merge="replace"),
    ]

    @dataclass
    class C:
        db: Dict[str, Any] = field(default_factory=dict)

    assert build_config(C, [], base_configs=layers_plain) == build_config(
        C, [], base_configs=layers_wrapped
    )


def test_list_merge_rules_builder_attribute_feeds_the_resolver():
    builder = GenericConfigBuilder(P)
    assert builder.config_resolver.list_merge_rules == builder.list_merge_rules

    parser = argparse.ArgumentParser()
    builder.add_arguments(parser)
    result = builder.build_config(
        parser.parse_args([]),
        base_configs=[{"plugins": ["a"]}, rules_layer({"plugins": ["b"]})],
        merge_strategy=DEEP,
    )
    assert result.plugins == ["a", "b"]


def test_optional_annotation_types_are_supported():
    @dataclass
    class Opt:
        plugins: Optional[List[str]] = combine_annotations(
            cli_list_merge("append"), default=None
        )

    result = build(Opt, [{"plugins": ["a"]}, rules_layer({"plugins": ["b"]})])
    assert result.plugins == ["a", "b"]
