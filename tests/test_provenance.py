"""
Tests for provenance (CR Part C): which layer supplied each value.

Every provenance build uses merge_strategy="deep" (layered mode).
"""

import copy
import json
import pickle
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import pytest

import dataclass_args
from dataclass_args import (
    MISSING_VALUE,
    ConfigBuilderError,
    ConfigLayer,
    Provenance,
    ProvenanceChange,
    ProvenanceEntry,
    build_config,
    build_config_from_cli,
    build_config_from_dict,
    cli_append,
    cli_list_merge,
    cli_nested,
    cli_positional,
    cli_resolve,
    combine_annotations,
)
from dataclass_args.builder import GenericConfigBuilder

DEEP = "deep"


@dataclass
class P:
    plugins: List[str] = combine_annotations(
        cli_list_merge("append_unique"), default_factory=list
    )
    tags: List[str] = field(default_factory=list)
    name: str = "n"
    maybe: Optional[str] = None
    db: Dict[str, Any] = field(default_factory=dict)
    skills: Dict[str, Any] = combine_annotations(
        cli_list_merge("append_unique", paths=["roots", "policy.denied"]),
        default_factory=dict,
    )


@dataclass
class Inner:
    v: int = 1
    opts: Dict[str, Any] = field(default_factory=dict)
    tags: List[str] = combine_annotations(
        cli_list_merge("append"), default_factory=list
    )


@dataclass
class Mid:
    w: int = 2
    inner: Inner = cli_nested(default_factory=Inner)


@dataclass
class Top:
    name: str = "t"
    mid: Mid = cli_nested(default_factory=Mid)


def layer(data, name, rules=False):
    return ConfigLayer(data, name=name, list_merge="rules" if rules else "replace")


def prov_from_dict(config_class, layers, config=None, **kwargs):
    return build_config_from_dict(
        config_class,
        config or {},
        base_configs=layers,
        merge_strategy=DEEP,
        return_provenance=True,
        **kwargs,
    )


def prov_from_cli(config_class, args, layers=None, **kwargs):
    return build_config_from_cli(
        config_class,
        args,
        base_configs=layers,
        merge_strategy=DEEP,
        return_provenance=True,
        **kwargs,
    )


# ---------------------------------------------------------------------------
# Public types
# ---------------------------------------------------------------------------


def test_exports():
    for name in ("Provenance", "ProvenanceEntry", "ProvenanceChange", "MISSING_VALUE"):
        assert name in dataclass_args.__all__
        assert hasattr(dataclass_args, name)


def test_missing_value_is_a_singleton_sentinel():
    from dataclass_args.provenance import _MissingValue

    assert repr(MISSING_VALUE) == "MISSING_VALUE"
    assert _MissingValue() is MISSING_VALUE
    assert copy.copy(MISSING_VALUE) is MISSING_VALUE
    assert copy.deepcopy(MISSING_VALUE) is MISSING_VALUE
    assert pickle.loads(pickle.dumps(MISSING_VALUE)) is MISSING_VALUE


def test_entry_and_change_are_frozen_value_objects():
    entry = ProvenanceEntry("a", 1, "set")
    assert entry == ProvenanceEntry("a", 1, "set")
    with pytest.raises(Exception):
        entry.layer = "b"
    change = ProvenanceChange("p", "a", 1, "b", 2, "replaced")
    assert change.path == "p"
    with pytest.raises(Exception):
        change.path = "q"


# ---------------------------------------------------------------------------
# C1-C10
# ---------------------------------------------------------------------------


def test_C1_replaced_value_and_change():
    _, prov = prov_from_dict(
        P,
        [
            layer({"skills": {"policy": {"execution": "deny"}}}, "platform"),
            layer({"skills": {"policy": {"execution": "allow"}}}, "agent"),
        ],
    )
    assert prov.source("skills.policy.execution") == "agent"
    assert prov.changes() == [
        ProvenanceChange(
            "skills.policy.execution", "platform", "deny", "agent", "allow", "replaced"
        )
    ]


def test_C2_append_entries():
    instance, prov = prov_from_dict(
        P,
        [
            layer({"plugins": ["dev"]}, "agent"),
            layer({"plugins": ["guard"]}, "override", rules=True),
        ],
    )
    assert instance.plugins == ["dev", "guard"]
    assert prov.entries("plugins") == [
        ProvenanceEntry("agent", ["dev"], "set"),
        ProvenanceEntry("override", ["guard"], "appended"),
    ]
    assert prov.source("plugins") == "override"


def test_C3_unset_field_source_is_default():
    _, prov = prov_from_dict(P, [layer({"tags": ["t"]}, "agent")])
    assert prov.source("name") == "default"
    assert prov.source("plugins") == "default"
    assert prov.entries("name") == []
    assert "name" not in prov.paths()


@pytest.mark.parametrize("entry", ["from_dict", "from_cli", "build_config", "builder"])
def test_C4_return_provenance_false_returns_the_instance_only(entry):
    layers = [layer({"name": "a"}, "file")]
    if entry == "from_dict":
        plain = build_config_from_dict(P, {}, base_configs=layers, merge_strategy=DEEP)
        flagged = build_config_from_dict(
            P, {}, base_configs=layers, merge_strategy=DEEP, return_provenance=False
        )
    elif entry == "from_cli":
        plain = build_config_from_cli(P, [], base_configs=layers, merge_strategy=DEEP)
        flagged = build_config_from_cli(
            P, [], base_configs=layers, merge_strategy=DEEP, return_provenance=False
        )
    elif entry == "build_config":
        plain = build_config(P, [], base_configs=layers, merge_strategy=DEEP)
        flagged = build_config(
            P, [], base_configs=layers, merge_strategy=DEEP, return_provenance=False
        )
    else:
        import argparse

        builder = GenericConfigBuilder(P)
        parser = argparse.ArgumentParser()
        builder.add_arguments(parser)
        args = parser.parse_args([])
        plain = builder.build_config(args, base_configs=layers, merge_strategy=DEEP)
        flagged = builder.build_config(
            args, base_configs=layers, merge_strategy=DEEP, return_provenance=False
        )
    assert isinstance(plain, P)
    assert plain == flagged


@pytest.mark.parametrize("entry", ["from_dict", "from_cli", "build_config", "builder"])
def test_return_provenance_true_returns_a_pair_on_every_entry_point(entry):
    layers = [layer({"name": "a"}, "file")]
    if entry == "from_dict":
        result = prov_from_dict(P, layers)
    elif entry == "from_cli":
        result = prov_from_cli(P, [], layers)
    elif entry == "build_config":
        result = build_config(
            P, [], base_configs=layers, merge_strategy=DEEP, return_provenance=True
        )
    else:
        import argparse

        builder = GenericConfigBuilder(P)
        parser = argparse.ArgumentParser()
        builder.add_arguments(parser)
        result = builder.build_config(
            parser.parse_args([]),
            base_configs=layers,
            merge_strategy=DEEP,
            return_provenance=True,
        )
    instance, prov = result
    assert isinstance(instance, P)
    assert isinstance(prov, Provenance)
    assert prov.source("name") == "file"


def test_C5_cli_overrides_a_file_value():
    _, prov = prov_from_cli(P, ["--name", "x"], [layer({"name": "f"}, "file")])
    assert prov.entries("name")[-1].layer == "cli"
    assert prov.source("name") == "cli"
    assert prov.changes() == [
        ProvenanceChange("name", "file", "f", "cli", "x", "replaced")
    ]


def test_C6_appended_lists_are_not_changes():
    _, prov = prov_from_dict(
        P,
        [
            layer({"plugins": ["dev"]}, "agent"),
            layer({"plugins": ["guard"]}, "override", rules=True),
        ],
    )
    assert prov.changes() == []


def test_C7_equal_value_is_confirmed_not_a_change():
    _, prov = prov_from_dict(
        P,
        [layer({"db": {"x": 1}}, "agent"), layer({"db": {"x": 1}}, "override")],
    )
    assert prov.changes() == []
    assert [e.action for e in prov.entries("db.x")] == ["set", "confirmed"]
    assert prov.source("db.x") == "override"


def test_C8_dict_cleared_by_none():
    _, prov = prov_from_dict(
        P,
        [
            layer({"db": {"host": "h", "port": 1}}, "agent"),
            layer({"db": None}, "override"),
        ],
    )
    changes = prov.changes()
    assert [(c.path, c.action) for c in changes] == [
        ("db", "cleared"),
        ("db.host", "removed"),
        ("db.port", "removed"),
    ]
    assert changes[0].from_layer == "agent"
    assert changes[0].from_value == {"host": "h", "port": 1}
    assert changes[0].to_layer == "override"
    assert changes[0].to_value is None
    assert all(c.to_value is MISSING_VALUE for c in changes[1:])
    assert all(c.from_layer == "agent" for c in changes[1:])
    assert prov.paths() == ["db"]
    assert prov.source("db.host") is None
    assert prov.source("db") == "override"
    assert prov.entries("db.host")[-1] == ProvenanceEntry(
        "override", MISSING_VALUE, "removed"
    )
    assert prov.entries("db.host")[0] == ProvenanceEntry("agent", "h", "set")


def test_C9_source_of_unknown_and_default_paths():
    _, prov = prov_from_dict(P, [layer({"db": {"k": 1}}, "agent")])
    assert prov.source("does.not.exist") is None
    assert prov.source("tags") == "default"
    assert prov.source("db.unset") is None
    assert prov.source("db") is None  # dict field whose sub-keys layers set
    assert prov.entries("does.not.exist") == []


def test_C10_nested_cli_flag_over_a_file_value():
    instance, prov = prov_from_cli(
        Top,
        ["--mid-inner-v", "7"],
        [layer({"mid": {"inner": {"v": 5}}}, "file")],
    )
    assert instance.mid.inner.v == 7
    assert prov.source("mid.inner.v") == "cli"
    assert [e.layer for e in prov.entries("mid.inner.v")] == ["file", "cli"]
    assert prov.changes()[-1] == ProvenanceChange(
        "mid.inner.v", "file", 5, "cli", 7, "replaced"
    )


# ---------------------------------------------------------------------------
# Shallow mode
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("entry", ["from_dict", "from_cli", "build_config", "builder"])
def test_provenance_with_shallow_mode_raises_before_any_io(entry):
    missing = "/nonexistent/never/loaded.yaml"
    layers = [missing, layer({"name": "a"}, "file")]
    with pytest.raises(ConfigBuilderError) as exc:
        if entry == "from_dict":
            build_config_from_dict(P, {}, base_configs=layers, return_provenance=True)
        elif entry == "from_cli":
            build_config_from_cli(P, [], base_configs=layers, return_provenance=True)
        elif entry == "build_config":
            build_config(P, [], base_configs=layers, return_provenance=True)
        else:
            import argparse

            builder = GenericConfigBuilder(P)
            parser = argparse.ArgumentParser()
            builder.add_arguments(parser)
            builder.build_config(
                parser.parse_args([]), base_configs=layers, return_provenance=True
            )
    assert "return_provenance=True requires merge_strategy='deep'" in str(exc.value)


# ---------------------------------------------------------------------------
# Recording semantics
# ---------------------------------------------------------------------------


def test_non_dict_replaced_by_dict_removes_the_old_leaf():
    _, prov = prov_from_dict(P, [layer({"db": 7}, "a"), layer({"db": {"k": 1}}, "b")])
    assert [(c.path, c.action) for c in prov.changes()] == [("db", "removed")]
    assert prov.changes()[0].from_value == 7
    assert prov.changes()[0].to_value is MISSING_VALUE
    assert prov.paths() == ["db.k"]
    assert [e.action for e in prov.entries("db")] == ["set", "removed"]
    assert prov.entries("db.k") == [ProvenanceEntry("b", 1, "set")]


def test_dict_replaced_by_scalar_is_replaced_with_subtree_value():
    _, prov = prov_from_dict(
        P, [layer({"db": {"a": 1, "b": 2}}, "a"), layer({"db": 7}, "b")]
    )
    changes = prov.changes()
    assert (changes[0].path, changes[0].action) == ("db", "replaced")
    assert changes[0].from_value == {"a": 1, "b": 2}
    assert changes[0].to_value == 7
    assert [(c.path, c.action) for c in changes[1:]] == [
        ("db.a", "removed"),
        ("db.b", "removed"),
    ]
    assert prov.paths() == ["db"]


def test_from_layer_of_a_subtree_change_is_the_most_recent_descendant_layer():
    _, prov = prov_from_dict(
        P,
        [
            layer({"db": {"a": 1, "b": 2}}, "first"),
            layer({"db": {"a": 9}}, "second"),
            layer({"db": None}, "third"),
        ],
    )
    cleared = [c for c in prov.changes() if c.path == "db"][0]
    assert cleared.from_layer == "second"
    assert cleared.from_value == {"a": 9, "b": 2}


def test_none_over_none_is_confirmed():
    _, prov = prov_from_dict(
        P, [layer({"maybe": None}, "a"), layer({"maybe": None}, "b")]
    )
    assert [e.action for e in prov.entries("maybe")] == ["set", "confirmed"]
    assert prov.changes() == []


def test_none_over_value_is_cleared_and_value_over_none_is_replaced():
    _, prov = prov_from_dict(
        P,
        [
            layer({"maybe": "x"}, "a"),
            layer({"maybe": None}, "b"),
            layer({"maybe": "y"}, "c"),
        ],
    )
    assert [e.action for e in prov.entries("maybe")] == ["set", "cleared", "replaced"]
    assert [(c.action, c.from_value, c.to_value) for c in prov.changes()] == [
        ("cleared", "x", None),
        ("replaced", None, "y"),
    ]


def test_empty_dict_marker_removes_a_live_leaf_and_has_no_leaves():
    _, prov = prov_from_dict(P, [layer({"db": 7}, "a"), layer({"db": {}}, "b")])
    assert prov.paths() == []
    assert [(c.path, c.action) for c in prov.changes()] == [("db", "removed")]


def test_empty_dict_over_dict_changes_nothing():
    _, prov = prov_from_dict(P, [layer({"db": {"a": 1}}, "a"), layer({"db": {}}, "b")])
    assert prov.paths() == ["db.a"]
    assert prov.changes() == []


def test_hyphenated_keys_use_normalized_paths():
    @dataclass
    class H:
        api_key: str = "k"

    _, prov = prov_from_dict(H, [layer({"api-key": "x"}, "file")])
    assert prov.source("api_key") == "file"
    assert prov.source("api-key") is None


def test_instance_layers_are_recorded_as_leaves():
    _, prov = prov_from_dict(
        Top,
        [layer({"mid": Mid(w=5, inner=Inner(v=5))}, "inst")],
    )
    assert prov.source("mid.w") == "inst"
    assert prov.source("mid.inner.v") == "inst"
    assert prov.entries("mid.inner.v") == [ProvenanceEntry("inst", 5, "set")]


def test_dict_field_file_ref_leaves_are_attributed_to_the_layer(tmp_path):
    db_file = tmp_path / "db.yaml"
    db_file.write_text("host: h\nopts: {x: 1}\n")

    _, prov = prov_from_dict(P, [layer({"db": str(db_file)}, "defaults")])
    assert prov.source("db.host") == "defaults"
    assert prov.source("db.opts.x") == "defaults"
    assert prov.entries("db.opts.x") == [ProvenanceEntry("defaults", 1, "set")]


def test_default_layer_labels_when_no_name_is_given(tmp_path):
    path = tmp_path / "layer.yaml"
    path.write_text("name: from-file\n")
    _, prov = prov_from_dict(
        P, [{"tags": ["a"]}, str(path), ConfigLayer({"maybe": "m"})]
    )
    assert prov.source("tags") == "base_configs[0]"
    assert prov.source("name") == str(path)
    assert prov.source("maybe") == "base_configs[2]"


def test_single_dict_label_is_base_configs():
    _, prov = prov_from_cli(P, [], {"name": "a"})
    assert prov.source("name") == "base_configs"


def test_layered_config_dict_is_named_config():
    _, prov = prov_from_dict(
        P,
        [layer({"name": "base"}, "file")],
        config={"name": "cfg", "tags": ["t"]},
    )
    assert prov.source("name") == "config"
    assert prov.changes() == [
        ProvenanceChange("name", "file", "base", "config", "cfg", "replaced")
    ]
    assert prov.source("tags") == "config"


def test_config_list_merge_rules_record_an_append_by_the_config_layer():
    _, prov = prov_from_dict(
        P,
        [layer({"plugins": ["dev"]}, "agent")],
        config={"plugins": ["rt"]},
        config_list_merge="rules",
    )
    assert prov.entries("plugins") == [
        ProvenanceEntry("agent", ["dev"], "set"),
        ProvenanceEntry("config", ["rt"], "appended"),
    ]


def test_rules_at_depth_use_full_paths():
    instance, prov = prov_from_dict(
        Top,
        [
            layer({"mid": {"inner": {"tags": ["a"]}}}, "one"),
            layer({"mid": {"inner": {"tags": ["b"]}}}, "two", rules=True),
        ],
    )
    assert instance.mid.inner.tags == ["a", "b"]
    assert [e.action for e in prov.entries("mid.inner.tags")] == ["set", "appended"]


def test_append_unique_that_adds_nothing_is_still_appended_and_live_is_combined():
    instance, prov = prov_from_dict(
        P,
        [
            layer({"plugins": ["a", "b"]}, "one"),
            layer({"plugins": ["a"]}, "two", rules=True),
            layer({"plugins": ["c"]}, "three", rules=True),
        ],
    )
    assert instance.plugins == ["a", "b", "c"]
    assert [e.action for e in prov.entries("plugins")] == [
        "set",
        "appended",
        "appended",
    ]
    assert prov.changes() == []


def test_rules_layer_does_not_append_when_a_side_is_not_a_list():
    _, prov = prov_from_dict(
        P,
        [
            layer({"plugins": ["dev"]}, "a"),
            layer({"plugins": "str"}, "b", rules=True),
        ],
    )
    assert [e.action for e in prov.entries("plugins")] == ["set", "replaced"]
    assert len(prov.changes()) == 1


# ---------------------------------------------------------------------------
# Stage 3, 4 and 6 hooks
# ---------------------------------------------------------------------------


def test_config_file_layer_is_named_with_its_path(tmp_path):
    config_file = tmp_path / "c.yaml"
    config_file.write_text("name: from-config-file\ndb: {a: 1}\n")

    _, prov = prov_from_cli(
        P, ["--config", str(config_file)], [layer({"name": "base"}, "file")]
    )
    expected = f"config_file:{config_file}"
    assert prov.source("name") == expected
    assert prov.source("db.a") == expected
    assert prov.changes() == [
        ProvenanceChange(
            "name", "file", "base", expected, "from-config-file", "replaced"
        )
    ]


def test_config_file_never_applies_list_rules(tmp_path):
    config_file = tmp_path / "c.yaml"
    config_file.write_text("plugins: [file]\n")

    instance, prov = prov_from_cli(
        P,
        ["--config", str(config_file)],
        [layer({"plugins": ["dev"]}, "a"), layer({"plugins": ["g"]}, "b", rules=True)],
    )
    assert instance.plugins == ["file"]
    assert prov.entries("plugins")[-1].action == "replaced"


def test_cli_list_value_never_applies_list_rules():
    instance, prov = prov_from_cli(
        P,
        ["--plugins", "x"],
        [layer({"plugins": ["dev"]}, "a"), layer({"plugins": ["g"]}, "b", rules=True)],
    )
    assert instance.plugins == ["x"]
    assert prov.entries("plugins")[-1] == ProvenanceEntry("cli", ["x"], "replaced")


def test_property_override_on_a_plain_path():
    instance, prov = prov_from_cli(P, ["--d", "a.b:1"], [layer({"name": "x"}, "f")])
    assert instance.db == {"a": {"b": 1}}
    assert prov.entries("db.a.b") == [ProvenanceEntry("cli", 1, "set")]
    assert prov.paths() == ["db.a.b", "name"]


def test_property_override_replacing_a_layer_value():
    _, prov = prov_from_cli(P, ["--d", "k:2"], [layer({"db": {"k": 1}}, "file")])
    assert prov.changes() == [ProvenanceChange("db.k", "file", 1, "cli", 2, "replaced")]


def test_property_override_plus_appends_to_a_list():
    instance, prov = prov_from_cli(
        P, ["--d", "tags.+:x"], [layer({"db": {"tags": ["t"]}}, "file")]
    )
    assert instance.db == {"tags": ["t", "x"]}
    assert prov.entries("db.tags") == [
        ProvenanceEntry("file", ["t"], "set"),
        ProvenanceEntry("cli", ["x"], "appended"),
    ]
    assert prov.changes() == []
    assert prov.source("db.tags") == "cli"


def test_property_override_index_set_records_the_whole_list():
    instance, prov = prov_from_cli(
        P, ["--d", "tags.0:z"], [layer({"db": {"tags": ["t", "u"]}}, "file")]
    )
    assert instance.db == {"tags": ["z", "u"]}
    assert prov.entries("db.tags")[-1] == ProvenanceEntry("cli", ["z", "u"], "replaced")
    assert prov.changes() == [
        ProvenanceChange("db.tags", "file", ["t", "u"], "cli", ["z", "u"], "replaced")
    ]


def test_property_override_through_list_element_records_the_list_path():
    instance, prov = prov_from_cli(
        P,
        ["--d", "items.0.name:z"],
        [layer({"db": {"items": [{"name": "a"}]}}, "file")],
    )
    assert instance.db == {"items": [{"name": "z"}]}
    assert prov.entries("db.items")[-1] == ProvenanceEntry(
        "cli", [{"name": "z"}], "replaced"
    )


def test_property_override_seeded_defaults_are_not_attributed_to_cli():
    @dataclass
    class Seeded:
        db: Dict[str, Any] = field(default_factory=lambda: {"x": 1})

    instance, prov = prov_from_cli(Seeded, ["--d", "y:2"])
    assert instance.db == {"x": 1, "y": 2}
    assert prov.paths() == ["db.y"]
    assert prov.entries("db.x") == []
    assert prov.source("db.x") is None
    assert prov.source("db.y") == "cli"


def test_property_override_plus_on_a_default_list_records_the_actual_list():
    @dataclass
    class SeededList:
        db: Dict[str, Any] = field(default_factory=lambda: {"items": [0]})

    instance, prov = prov_from_cli(SeededList, ["--d", "items.+:1"])
    assert instance.db == {"items": [0, 1]}
    assert prov.entries("db.items") == [ProvenanceEntry("cli", [1], "appended")]
    assert prov.paths() == ["db.items"]


def test_cli_dict_file_contributes_only_the_loaded_leaves(tmp_path):
    db_file = tmp_path / "f.json"
    db_file.write_text(json.dumps({"p": 1}))

    instance, prov = prov_from_cli(
        P, ["--db", str(db_file)], [layer({"db": {"h": "a"}}, "file")]
    )
    assert instance.db == {"h": "a", "p": 1}
    assert prov.source("db.p") == "cli"
    assert prov.source("db.h") == "file"
    assert prov.changes() == []


def test_cli_dict_file_replacing_a_prebuilt_object_removes_it():
    prebuilt = object()

    @dataclass
    class R:
        sb: Any = combine_annotations(
            cli_resolve(resolver=lambda value: value), default=None
        )

    _, prov = prov_from_cli(R, [], [layer({"sb": prebuilt}, "file")])
    assert prov.entries("sb")[0].value is prebuilt


def test_cli_scalar_and_cli_append_values_are_recorded():
    @dataclass
    class K:
        files: List[List[str]] = combine_annotations(
            cli_append(nargs=2), default_factory=list
        )
        out: str = combine_annotations(cli_positional(nargs="?"), default="o")

    instance, prov = prov_from_cli(
        K, ["typed", "--files", "a", "b"], [layer({"out": "base"}, "file")]
    )
    assert instance.files == [["a", "b"]]
    assert prov.entries("files") == [ProvenanceEntry("cli", [["a", "b"]], "set")]
    assert prov.source("out") == "cli"


def test_cli_cleared_value_over_non_none_value():
    _, prov = prov_from_cli(
        P, [], [layer({"maybe": "x"}, "f"), layer({"maybe": None}, "g")]
    )
    assert prov.changes()[-1].action == "cleared"


def test_nested_cli_dict_file_contributes_the_loaded_dict_only(tmp_path):
    opts_file = tmp_path / "o.json"
    opts_file.write_text(json.dumps({"n": 1}))

    instance, prov = prov_from_cli(
        Top,
        ["--mid-inner-opts", str(opts_file)],
        [layer({"mid": {"inner": {"opts": {"x": 1}}}}, "file")],
    )
    assert instance.mid.inner.opts == {"x": 1, "n": 1}
    assert prov.source("mid.inner.opts.n") == "cli"
    assert prov.source("mid.inner.opts.x") == "file"


def test_nested_property_override_seeded_defaults_are_not_attributed_to_cli():
    @dataclass
    class InD:
        opts: Dict[str, Any] = field(default_factory=lambda: {"x": 1})

    @dataclass
    class TpD:
        inner: InD = cli_nested(default_factory=InD)

    instance, prov = prov_from_cli(TpD, ["--inner-o", "y:2"])
    assert instance.inner.opts == {"x": 1, "y": 2}
    assert prov.paths() == ["inner.opts.y"]
    assert prov.source("inner.opts.x") is None


def test_nested_property_override_plus_records_an_append():
    _, prov = prov_from_cli(
        Top,
        ["--mid-inner-o", "items.+:2"],
        [layer({"mid": {"inner": {"opts": {"items": [1]}}}}, "file")],
    )
    assert prov.entries("mid.inner.opts.items") == [
        ProvenanceEntry("file", [1], "set"),
        ProvenanceEntry("cli", [2], "appended"),
    ]


def test_nested_cli_scalar_and_dict_file_are_recorded(tmp_path):
    opts = tmp_path / "opts.json"
    opts.write_text('{"k": 1}')
    _, prov = prov_from_cli(Top, ["--mid-w", "9", "--mid-inner-opts", str(opts)])
    assert prov.entries("mid.w") == [ProvenanceEntry("cli", 9, "set")]
    assert prov.entries("mid.inner.opts.k") == [ProvenanceEntry("cli", 1, "set")]


def test_nested_cli_list_value_is_recorded():
    @dataclass
    class InL:
        files: List[List[str]] = combine_annotations(
            cli_append(nargs=2), default_factory=list
        )

    @dataclass
    class TpL:
        inner: InL = cli_nested(default_factory=InL)

    _, prov = prov_from_cli(TpL, ["--inner-files", "a", "b"])
    assert prov.entries("inner.files") == [ProvenanceEntry("cli", [["a", "b"]], "set")]


def test_layered_from_dict_has_no_cli_entries():
    _, prov = prov_from_dict(Top, [], config={"mid": {"w": 5}, "name": "x"})
    assert {e.layer for path in prov.paths() for e in prov.entries(path)} == {"config"}


# ---------------------------------------------------------------------------
# cli_resolve, defaults at depth, explain
# ---------------------------------------------------------------------------


def test_cli_resolve_provenance_holds_the_raw_value_instance_holds_the_resolved():
    @dataclass
    class Resolved:
        sb: Any = combine_annotations(
            cli_resolve(resolver=lambda value: ("resolved", value)), default=None
        )

    instance, prov = prov_from_dict(Resolved, [layer({"sb": {"a": 1}}, "file")])
    assert instance.sb == ("resolved", {"a": 1})
    assert prov.entries("sb.a") == [ProvenanceEntry("file", 1, "set")]
    assert prov.source("sb.a") == "file"


def test_defaults_at_depth():
    _, prov = prov_from_dict(Top, [layer({"name": "x"}, "f")])
    assert prov.source("mid.inner.v") == "default"
    assert prov.source("mid.w") == "default"
    assert prov.source("mid.inner.opts") == "default"
    assert prov.source("mid") is None
    assert prov.source("mid.inner") is None
    rows = prov.explain().splitlines()
    assert "mid.inner.v | (default) | 1" in rows
    assert "mid.w | (default) | 2" in rows


def test_explain_exact_text_and_truncation():
    long_value = "x" * 100
    _, prov = prov_from_dict(
        P,
        [
            layer({"name": "first", "tags": ["a"]}, "base"),
            layer({"name": long_value}, "agent"),
        ],
    )
    truncated = repr(long_value)[:57] + "..."
    assert len(truncated) == 60
    expected = "\n".join(
        [
            "path | source | value",
            "name | agent | " + truncated,
            "tags | base | ['a']",
            "db | (default) | {}",
            "maybe | (default) | None",
            "plugins | (default) | []",
            "skills | (default) | {}",
        ]
    )
    assert prov.explain() == expected


def test_explain_short_values_are_not_truncated():
    _, prov = prov_from_dict(P, [layer({"name": "x" * 57}, "a")])
    row = [r for r in prov.explain().splitlines() if r.startswith("name |")][0]
    assert row == "name | a | " + repr("x" * 57)


def test_explain_lists_defaults_for_fields_without_a_default_value():
    @dataclass
    class NeedsValue:
        required: int
        optional: int = 3

    _, prov = prov_from_dict(NeedsValue, [layer({"required": 1}, "f")])
    assert prov.explain().splitlines() == [
        "path | source | value",
        "required | f | 1",
        "optional | (default) | 3",
    ]


def test_paths_are_sorted_and_exclude_defaults_and_removed_paths():
    _, prov = prov_from_dict(
        P,
        [
            layer({"name": "a", "db": {"b": 1, "a": 2}}, "one"),
            layer({"tags": ["x"]}, "two"),
        ],
    )
    assert prov.paths() == ["db.a", "db.b", "name", "tags"]


# ---------------------------------------------------------------------------
# Mutation safety and zero cost
# ---------------------------------------------------------------------------


def test_mutating_the_instance_does_not_change_provenance():
    instance, prov = prov_from_dict(
        P, [layer({"tags": ["a"], "db": {"k": [1]}}, "file")]
    )
    instance.tags.append("mutated")
    instance.db["k"].append(2)
    instance.db["new"] = 1

    assert prov.entries("tags") == [ProvenanceEntry("file", ["a"], "set")]
    assert prov.entries("db.k") == [ProvenanceEntry("file", [1], "set")]
    assert prov.entries("db.new") == []


def test_mutating_returned_values_does_not_change_later_results():
    _, prov = prov_from_dict(
        P,
        [
            layer({"tags": ["a"], "db": {"k": {"x": 1}}}, "one"),
            layer({"tags": ["b"]}, "two"),
        ],
    )
    prov.entries("tags")[0].value.append("mutated")
    prov.changes()[0].from_value.append("mutated")
    prov.changes()[0].to_value.append("mutated")

    assert prov.entries("tags")[0].value == ["a"]
    assert prov.changes()[0].from_value == ["a"]
    assert prov.changes()[0].to_value == ["b"]


def test_caller_layer_data_is_not_aliased_by_provenance():
    data = {"tags": ["a"]}
    _, prov = prov_from_dict(P, [layer(data, "file")])
    data["tags"].append("later")
    assert prov.entries("tags")[0].value == ["a"]


def test_return_provenance_false_never_creates_a_recorder(monkeypatch):
    def explode(*args, **kwargs):
        raise AssertionError("a recorder was constructed")

    monkeypatch.setattr("dataclass_args.config_resolver.ProvenanceRecorder", explode)
    layers = [layer({"name": "a"}, "file")]

    assert build_config(P, [], base_configs=layers, merge_strategy=DEEP).name == "a"
    assert (
        build_config_from_dict(
            P, {"name": "b"}, base_configs=layers, merge_strategy=DEEP
        ).name
        == "b"
    )
    assert build_config(P, [], base_configs=layers).name == "a"

    with pytest.raises(AssertionError):
        build_config(
            P, [], base_configs=layers, merge_strategy=DEEP, return_provenance=True
        )


def test_merge_context_recorder_is_none_by_default_and_ignored_by_equality():
    from dataclass_args.merge_strategy import MergeContext

    assert MergeContext().recorder is None
    assert MergeContext(recorder=object()) == MergeContext()
    assert "recorder" not in repr(MergeContext(recorder=object()))


def test_recorder_never_raises_for_a_build_without_layers():
    _, prov = prov_from_dict(P, [])
    assert prov.paths() == []
    assert prov.changes() == []
    assert prov.source("name") == "default"


# ---------------------------------------------------------------------------
# Consistency and the layered-policy end-to-end scenario
# ---------------------------------------------------------------------------


def test_every_live_leaf_equals_the_raw_config_after_stage_4(monkeypatch):
    from dataclass_args.value_resolution import ValueResolver

    captured: Dict[str, Any] = {}
    original = ValueResolver.resolve_raw_values

    def spy(self, config, args):
        captured["raw"] = copy.deepcopy(config)
        return original(self, config, args)

    monkeypatch.setattr(ValueResolver, "resolve_raw_values", spy)

    _, prov = prov_from_cli(
        P,
        ["--name", "cli", "--d", "k.+:2", "--d", "n.m:1", "--plugins", "p"],
        [
            layer({"name": "a", "db": {"k": [1], "z": 0}, "tags": ["t"]}, "one"),
            layer({"plugins": ["x"], "skills": {"roots": ["r"]}}, "two", rules=True),
            layer(
                {"skills": {"roots": ["s"], "policy": {"denied": ["d"]}}},
                "three",
                rules=True,
            ),
        ],
    )
    raw = captured["raw"]
    for path in prov.paths():
        node = raw
        for key in path.split("."):
            node = node[key]
        assert node == prov._live[tuple(path.split("."))]


def test_layered_policy_end_to_end_scenario():
    @dataclass
    class Cfg:
        plugins: List[str] = combine_annotations(
            cli_list_merge("append_unique"), default_factory=list
        )
        skills: Dict[str, Any] = combine_annotations(
            cli_list_merge("append_unique", paths=["roots", "policy.denied"]),
            default_factory=dict,
        )

    layers = [
        layer(
            {"skills": {"policy": {"execution": "deny"}}, "plugins": ["p"]},
            "defaults.d/10",
        ),
        layer(
            {"skills": {"policy": {"execution": "allow"}}, "plugins": ["dev"]},
            "agent.yaml",
        ),
        layer(
            {"skills": {"policy": {"execution": "deny"}}, "plugins": ["guard"]},
            "overrides.d/50",
            rules=True,
        ),
    ]
    instance, prov = build_config_from_dict(
        Cfg, {}, base_configs=layers, merge_strategy=DEEP, return_provenance=True
    )

    # defaults.d/10's plugins were replaced by agent.yaml (not appended), then guard appended
    assert instance.plugins == ["dev", "guard"]
    assert instance.skills == {"policy": {"execution": "deny"}}

    warnings = [
        f"{c.path} {c.from_layer} {c.from_value} -> {c.to_layer} {c.to_value}"
        for c in prov.changes()
        if c.to_layer.startswith(("overrides.d/", "overrides="))
        and c.from_layer in ("agent.yaml",)
    ]
    assert warnings == [
        "skills.policy.execution agent.yaml allow -> overrides.d/50 deny"
    ]
    assert prov.source("skills.policy.execution") == "overrides.d/50"
    assert [e.layer for e in prov.entries("skills.policy.execution")] == [
        "defaults.d/10",
        "agent.yaml",
        "overrides.d/50",
    ]
