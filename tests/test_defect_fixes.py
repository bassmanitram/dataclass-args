"""
Tests for the 1.10.0 defect fixes: consistent one-level dict merge across
stages 2/3/4 (M1-M3) and isolation of caller-owned containers (A1-A4).
"""

import argparse
import json
from dataclasses import MISSING, dataclass, field
from typing import Any, Dict, List, Optional

import pytest

from dataclass_args import (
    ConfigurationError,
    build_config,
    build_config_from_dict,
    cli_append,
    cli_choices,
    cli_exclude,
    cli_help,
    cli_nested,
    cli_positional,
    cli_resolve,
    combine_annotations,
)
from dataclass_args.builder import GenericConfigBuilder
from dataclass_args.config_applicator import ConfigApplicator
from dataclass_args.convenience import _empty_namespace
from dataclass_args.formatter import RangeAppendHelpFormatter
from dataclass_args.layer_normalization import LayerNormalizer
from dataclass_args.nested_processor import NestedFieldProcessor
from dataclass_args.utils import (
    copy_containers,
    fresh_field_default,
    looks_like_structured_file,
)


@dataclass
class C:
    name: Optional[str] = "x"
    db: Dict[str, Any] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)


@dataclass
class DB:
    host: str = "localhost"
    opts: Dict[str, Any] = field(default_factory=dict)


@dataclass
class App:
    name: str = "x"
    db: DB = cli_nested(default_factory=DB)


@dataclass
class AnyDb:
    db: Any = None


# ---------------------------------------------------------------------------
# M1: stage 2 one-level merge
# ---------------------------------------------------------------------------


def test_M1_base_configs_key_merge():
    result = build_config(C, [], base_configs=[{"db": {"a": 1}}, {"db": {"b": 2}}])
    assert result.db == {"a": 1, "b": 2}


def test_M1_three_layers_order():
    result = build_config(
        C,
        [],
        base_configs=[
            {"db": {"a": 1, "b": 1}},
            {"db": {"b": 2}},
            {"db": {"c": 3}},
        ],
    )
    assert result.db == {"a": 1, "b": 2, "c": 3}


def test_M1_nested_dict_replaced_one_level():
    result = build_config(
        C,
        [],
        base_configs=[{"db": {"o": {"x": 1}}}, {"db": {"o": {"y": 2}}}],
    )
    assert result.db == {"o": {"y": 2}}


def test_M1_lists_still_replace():
    result = build_config(C, [], base_configs=[{"tags": ["a"]}, {"tags": ["b"]}])
    assert result.tags == ["b"]


def test_M1_none_still_clears():
    result = build_config(C, [], base_configs=[{"name": "b"}, {"name": None}])
    assert result.name is None


def test_M1_dict_over_scalar_and_scalar_over_dict():
    dict_wins = build_config(AnyDb, [], base_configs=[{"db": "s"}, {"db": {"a": 1}}])
    assert dict_wins.db == {"a": 1}

    scalar_wins = build_config(AnyDb, [], base_configs=[{"db": {"a": 1}}, {"db": "s"}])
    assert scalar_wins.db == "s"


# ---------------------------------------------------------------------------
# M2: stage 3 one-level merge
# ---------------------------------------------------------------------------


def test_M2_config_file_key_merge(tmp_path):
    config_file = tmp_path / "cfg.yaml"
    config_file.write_text("db:\n  b: 2\n")

    result = build_config(
        C,
        ["--config", str(config_file)],
        base_configs={"db": {"a": 1}},
    )
    assert result.db == {"a": 1, "b": 2}


# ---------------------------------------------------------------------------
# M3: build_config_from_dict with nested dataclass
# ---------------------------------------------------------------------------


def test_M3_from_dict_nested_keeps_base_siblings():
    result = build_config_from_dict(
        App,
        {"db": {"opts": {"y": 2}}},
        base_configs={"db": {"host": "a", "opts": {"x": 1}}},
    )
    assert result.db == DB(host="a", opts={"y": 2})


# ---------------------------------------------------------------------------
# A1-A4: caller data isolation
# ---------------------------------------------------------------------------


def test_A1_property_override_does_not_mutate_caller():
    caller = {"db": {"a": 1}}
    result = build_config(C, ["--d", "z:9"], base_configs=caller)
    assert caller == {"db": {"a": 1}}
    assert result.db == {"a": 1, "z": 9}


def test_A2_list_append_does_not_mutate_caller():
    caller = {"db": {"items": [0]}}
    result = build_config(C, ["--d", "items.+:1"], base_configs=caller)
    assert caller["db"]["items"] == [0]
    assert result.db["items"] == [0, 1]


def test_A3_dict_file_merge_does_not_mutate_caller(tmp_path):
    dict_file = tmp_path / "b.json"
    dict_file.write_text(json.dumps({"b": 2}))
    caller = {"db": {"a": 1}}

    build_config(C, ["--db", str(dict_file)], base_configs=caller)
    assert caller == {"db": {"a": 1}}


def test_A4_instance_does_not_alias_caller():
    caller = {"db": {"a": 1}}
    result = build_config(C, [], base_configs=caller)
    result.db["M"] = 1
    assert "M" not in caller["db"]


def test_A4_list_base_configs_not_aliased():
    caller = {"db": {"a": 1}}
    result = build_config(C, [], base_configs=[caller])
    result.db["M"] = 1
    assert "M" not in caller["db"]


def test_A4_from_dict_config_not_aliased():
    caller = {"db": {"a": 1}}
    result = build_config_from_dict(C, caller)
    result.db["M"] = 1
    assert caller == {"db": {"a": 1}}


# ---------------------------------------------------------------------------
# copy_containers
# ---------------------------------------------------------------------------


def test_copy_containers_new_containers_at_every_depth():
    original = {"a": {"b": [1, {"c": [2]}]}, "d": [[3]]}
    copied = copy_containers(original)

    assert copied == original
    assert copied is not original
    assert copied["a"] is not original["a"]
    assert copied["a"]["b"] is not original["a"]["b"]
    assert copied["a"]["b"][1] is not original["a"]["b"][1]
    assert copied["a"]["b"][1]["c"] is not original["a"]["b"][1]["c"]
    assert copied["d"] is not original["d"]
    assert copied["d"][0] is not original["d"][0]


def test_copy_containers_preserves_non_container_identity():
    instance = DB()
    pair = (1, [2])
    func = lambda x: x  # noqa: E731
    original = {"inst": instance, "tup": pair, "fn": func, "lst": [instance, func]}
    copied = copy_containers(original)

    assert copied == original
    assert copied["inst"] is instance
    assert copied["tup"] is pair
    assert copied["fn"] is func
    assert copied["lst"][0] is instance
    assert copied["lst"][1] is func


def test_copy_containers_scalars_returned_as_is():
    assert copy_containers(5) == 5
    assert copy_containers(None) is None
    text = "abc"
    assert copy_containers(text) is text


# ---------------------------------------------------------------------------
# merge_layer
# ---------------------------------------------------------------------------


def test_merge_layer_creates_new_dict_for_merged_keys():
    config = {"db": {"a": 1}}
    original_db = config["db"]
    layer = {"db": {"b": 2}}

    result = ConfigApplicator.merge_layer(config, layer)

    assert result is config
    assert result["db"] == {"a": 1, "b": 2}
    assert result["db"] is not layer["db"]
    assert result["db"] is not original_db
    assert original_db == {"a": 1}


def test_merge_layer_preserves_keys_only_in_config():
    result = ConfigApplicator.merge_layer({"a": 1, "db": {"x": 1}}, {"db": {"y": 2}})
    assert result == {"a": 1, "db": {"x": 1, "y": 2}}


def test_merge_layer_replaces_non_dict_pairs():
    result = ConfigApplicator.merge_layer(
        {"s": {"a": 1}, "t": "old", "l": [1], "n": "keep"},
        {"s": "scalar", "t": {"a": 1}, "l": [2], "n": None},
    )
    assert result == {"s": "scalar", "t": {"a": 1}, "l": [2], "n": None}


def test_merge_layer_replaces_nested_dicts_below_first_level():
    result = ConfigApplicator.merge_layer(
        {"db": {"o": {"x": 1}}}, {"db": {"o": {"y": 2}}}
    )
    assert result == {"db": {"o": {"y": 2}}}


# ---------------------------------------------------------------------------
# F1-F4: dict-field file refs are loaded when a layer enters the pipeline
# ---------------------------------------------------------------------------


@pytest.fixture
def db_file(tmp_path):
    path = tmp_path / "db.yaml"
    path.write_text("host: h\nport: 1\n")
    return path


@pytest.fixture
def opts_file(tmp_path):
    path = tmp_path / "opts.yaml"
    path.write_text("x: 1\n")
    return path


def test_F1_base_file_ref_then_property_override(db_file):
    result = build_config(C, ["--d", "port:5"], base_configs={"db": str(db_file)})
    assert result.db == {"host": "h", "port": 5}


def test_F1_file_ref_then_dict_layer_merges(db_file):
    result = build_config(C, [], base_configs=[{"db": str(db_file)}, {"db": {"x": 9}}])
    assert result.db == {"host": "h", "port": 1, "x": 9}


def test_F1_dict_layer_then_file_ref_merges(db_file):
    result = build_config(C, [], base_configs=[{"db": {"x": 9}}, {"db": str(db_file)}])
    assert result.db == {"x": 9, "host": "h", "port": 1}


def test_F2_config_file_ref_then_property_override(tmp_path, db_file):
    config_file = tmp_path / "c.yaml"
    config_file.write_text(f"db: {db_file}\n")

    result = build_config(C, ["--config", str(config_file), "--d", "port:5"])
    assert result.db == {"host": "h", "port": 5}


def test_F3_nested_dict_field_file_ref(opts_file):
    result = build_config(App, [], base_configs={"db": {"opts": str(opts_file)}})
    assert result.db.opts == {"x": 1}


def test_F3_nested_file_ref_merges_with_later_layer(opts_file):
    result = build_config(
        App,
        [],
        base_configs=[{"db": {"opts": str(opts_file)}}, {"db": {"host": "z"}}],
    )
    assert result.db == DB(host="z", opts={"x": 1})


def test_F4_from_dict_nested_file_ref(opts_file):
    result = build_config_from_dict(App, {"db": {"opts": str(opts_file)}})
    assert result.db.opts == {"x": 1}


def _recording_resolver(seen):
    def resolver(value):
        seen.append(value)
        return value

    return resolver


def test_F_cli_resolve_dict_field_file_ref_loaded_before_resolver(db_file):
    seen: List[Any] = []

    @dataclass
    class R:
        sb: Any = combine_annotations(
            cli_resolve(resolver=_recording_resolver(seen)), default=None
        )

    build_config(R, [], base_configs={"sb": str(db_file)})
    assert seen == [{"host": "h", "port": 1}]


def test_F_non_file_string_passes_through():
    seen: List[Any] = []

    @dataclass
    class R:
        sb: Any = combine_annotations(
            cli_resolve(resolver=_recording_resolver(seen)), default=None
        )

    build_config(R, [], base_configs={"sb": "docker"})
    assert seen == ["docker"]


def test_F_load_error_names_field_and_layer():
    with pytest.raises(ConfigurationError) as exc:
        build_config(C, [], base_configs=[{"db": "missing.yaml"}])
    message = str(exc.value)
    assert "'db'" in message
    assert "missing.yaml" in message
    assert "base_configs[0]" in message


def test_F_load_error_names_nested_dotted_path():
    with pytest.raises(ConfigurationError) as exc:
        build_config(App, [], base_configs={"db": {"opts": "missing.yaml"}})
    assert "'db.opts'" in str(exc.value)
    assert "layer 'base_configs'" in str(exc.value)


def test_F_string_base_config_label_is_its_path(tmp_path):
    layer_file = tmp_path / "layer.yaml"
    layer_file.write_text("db: missing.yaml\n")

    with pytest.raises(ConfigurationError) as exc:
        build_config(C, [], base_configs=str(layer_file))
    assert f"layer '{layer_file}'" in str(exc.value)


def test_F_config_file_layer_label_in_error(tmp_path):
    config_file = tmp_path / "c.yaml"
    config_file.write_text("db: missing.yaml\n")

    with pytest.raises(ConfigurationError) as exc:
        build_config(C, ["--config", str(config_file)])
    message = str(exc.value)
    assert "config_file:" in message
    assert not message.startswith("Failed to load config file")


# ---------------------------------------------------------------------------
# F5 / F5b: nested field values
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("value", ["db.yaml", 42, [1]])
def test_F5_nested_string_raises(value):
    with pytest.raises(ConfigurationError) as exc:
        build_config(App, [], base_configs={"db": value})
    assert "'db'" in str(exc.value)
    assert "DB" in str(exc.value)


def test_F5_from_dict_nested_string_raises():
    with pytest.raises(ConfigurationError):
        build_config_from_dict(App, {"db": "x"})


def test_F5_nested_none_gives_defaults():
    result = build_config(App, [], base_configs={"db": None})
    assert result.db == DB()


def test_F5b_from_dict_nested_instance_kept():
    result = build_config_from_dict(App, {"db": DB(host="z")})
    assert result.db == DB(host="z")


def test_F5_stage6_safety_net_rejects_non_dict_value():
    builder = GenericConfigBuilder(App)
    with pytest.raises(ConfigurationError) as exc:
        builder.config_resolver._reconstruct_nested_fields(
            {"db": 5}, argparse.Namespace()
        )
    assert "Nested field 'db'" in str(exc.value)


# ---------------------------------------------------------------------------
# E1: error messages
# ---------------------------------------------------------------------------


def test_E1_property_override_on_plain_string_dict_field():
    with pytest.raises(ConfigurationError) as exc:
        build_config(C, ["--d", "port:5"], base_configs={"db": "plainstring"})
    message = str(exc.value)
    assert "Cannot apply property overrides to field 'db'" in message
    assert "str" in message


def test_E1_set_nested_property_names_offending_prefix():
    with pytest.raises(ValueError) as exc:
        ConfigApplicator.set_nested_property({"a": {"b": "s"}}, "a.b.c", "1")
    message = str(exc.value)
    assert "'a.b'" in message
    assert "str" in message
    assert "not a dictionary" in message


def test_E1_set_nested_property_names_prefix_while_navigating():
    with pytest.raises(ValueError) as exc:
        ConfigApplicator.set_nested_property({"a": {"b": "s"}}, "a.b.c.d", "1")
    message = str(exc.value)
    assert "'a.b'" in message
    assert "not a dictionary" in message


# ---------------------------------------------------------------------------
# Units: LayerNormalizer, looks_like_structured_file, apply_config_file
# ---------------------------------------------------------------------------


@dataclass
class Outer:
    inner: App = cli_nested(default_factory=App)
    meta: Dict[str, Any] = field(default_factory=dict)
    label: str = "l"


def _normalizer(config_class):
    return LayerNormalizer(
        GenericConfigBuilder(config_class)._config_fields, config_class
    )


def test_layer_normalizer_loads_top_level_dict_field(db_file):
    layer = {"db": str(db_file)}
    result = _normalizer(C).normalize(layer, "L")
    assert result is layer
    assert layer == {"db": {"host": "h", "port": 1}}


def test_layer_normalizer_leaves_other_values_unchanged():
    layer = {"db": "plain", "name": "n.yaml", "unknown": "u.yaml", "tags": ["t.yaml"]}
    _normalizer(C).normalize(layer, "L")
    assert layer == {
        "db": "plain",
        "name": "n.yaml",
        "unknown": "u.yaml",
        "tags": ["t.yaml"],
    }


def test_layer_normalizer_leaves_dict_and_none_dict_values():
    layer = {"db": None}
    _normalizer(C).normalize(layer, "L")
    assert layer == {"db": None}

    layer = {"db": {"k": "v.yaml"}}
    _normalizer(C).normalize(layer, "L")
    assert layer == {"db": {"k": "v.yaml"}}


def test_layer_normalizer_recurses_into_nested_in_nested(opts_file):
    layer = {"inner": {"db": {"opts": str(opts_file)}}, "meta": str(opts_file)}
    _normalizer(Outer).normalize(layer, "L")
    assert layer == {"inner": {"db": {"opts": {"x": 1}}}, "meta": {"x": 1}}


def test_layer_normalizer_nested_in_nested_error_path():
    with pytest.raises(ConfigurationError) as exc:
        _normalizer(Outer).normalize({"inner": {"db": 3}}, "L")
    assert "'inner.db'" in str(exc.value)
    assert "layer 'L'" in str(exc.value)


def test_layer_normalizer_converts_nested_instance_keeps_none():
    layer = {"db": DB(host="k")}
    instance = layer["db"]
    _normalizer(App).normalize(layer, "L")
    assert layer["db"] == {"host": "k", "opts": {}}
    assert type(layer["db"]) is dict
    assert instance == DB(host="k")
    assert layer["db"]["opts"] is not instance.opts

    layer = {"db": None}
    _normalizer(App).normalize(layer, "L")
    assert layer == {"db": None}


def test_layer_normalizer_leaves_unknown_nested_keys_unchanged():
    layer = {"db": {"opts": {"a": 1}, "extra": "e.yaml"}}
    _normalizer(App).normalize(layer, "L")
    assert layer == {"db": {"opts": {"a": 1}, "extra": "e.yaml"}}


def test_looks_like_structured_file():
    for name in ("a.json", "a.yaml", "a.yml", "a.toml"):
        assert looks_like_structured_file(name)
    for name in ("a.txt", "yaml", "docker", ""):
        assert not looks_like_structured_file(name)


def test_apply_config_file_default_does_not_normalize(tmp_path):
    config_file = tmp_path / "c.yaml"
    config_file.write_text("db: some.yaml\n")
    args = argparse.Namespace(config=str(config_file))

    result = ConfigApplicator.apply_config_file({}, args, "config")
    assert result == {"db": "some.yaml"}


def test_apply_config_file_normalizer_error_not_rewrapped(tmp_path):
    config_file = tmp_path / "c.yaml"
    config_file.write_text("db: 1\n")
    args = argparse.Namespace(config=str(config_file))

    def failing(layer, label):
        raise ConfigurationError(f"custom {label}")

    with pytest.raises(ConfigurationError) as exc:
        ConfigApplicator.apply_config_file({}, args, "config", failing)
    assert str(exc.value) == f"custom config_file:{config_file}"


# ---------------------------------------------------------------------------
# P1-P7: property overrides edit the effective value; nested CLI dicts merge
# ---------------------------------------------------------------------------


@dataclass
class CD:
    db: Dict[str, Any] = field(default_factory=lambda: {"x": 1, "items": [0]})


@dataclass
class DBD:
    host: str = "localhost"
    opts: Dict[str, Any] = field(default_factory=lambda: {"x": 1, "items": [0]})


@dataclass
class AppD:
    db: DBD = cli_nested(default_factory=DBD)


@pytest.fixture
def merge_file(tmp_path):
    path = tmp_path / "f.json"
    path.write_text(json.dumps({"n": {"b": 2}, "y": 2}))
    return path


def test_P1_nested_override_keeps_base_dict():
    result = build_config(
        App,
        ["--db-o", "y:2"],
        base_configs={"db": {"host": "a", "opts": {"x": 1}}},
    )
    assert result.db == DB(host="a", opts={"x": 1, "y": 2})


def test_P2_nested_append_to_base_list():
    result = build_config(
        App,
        ["--db-o", "items.+:1"],
        base_configs={"db": {"opts": {"items": [0]}}},
    )
    assert result.db.opts == {"items": [0, 1]}


def test_P3_top_level_override_keeps_default():
    result = build_config(CD, ["--d", "y:2"])
    assert result.db == {"x": 1, "items": [0], "y": 2}


def test_P4_top_level_append_to_default_list():
    result = build_config(CD, ["--d", "items.+:1"])
    assert result.db["items"] == [0, 1]


def test_P5_nested_override_keeps_default():
    result = build_config(AppD, ["--db-o", "y:2"])
    assert result.db.opts == {"x": 1, "items": [0], "y": 2}


def test_P5_default_not_shared_between_builds():
    build_config(AppD, ["--db-o", "y:2", "--db-o", "items.+:1"])
    second = build_config(AppD, [])
    assert second.db.opts == {"x": 1, "items": [0]}


def test_P3_default_not_shared_between_builds():
    build_config(CD, ["--d", "y:2", "--d", "items.+:1"])
    second = build_config(CD, [])
    assert second.db == {"x": 1, "items": [0]}


def test_P_override_after_explicit_none_starts_empty():
    result = build_config(CD, ["--d", "y:2"], base_configs={"db": None})
    assert result.db == {"y": 2}


def test_P_nested_override_after_explicit_none_starts_empty():
    result = build_config(AppD, ["--db-o", "y:2"], base_configs={"db": {"opts": None}})
    assert result.db.opts == {"y": 2}


def test_P_nested_override_on_instance_base_does_not_mutate_it():
    inst = DB(opts={"x": 1})
    result = build_config(App, ["--db-o", "y:2"], base_configs={"db": inst})
    assert result.db.opts == {"x": 1, "y": 2}
    assert inst.opts == {"x": 1}


def test_P_nested_override_on_non_dict_raises():
    with pytest.raises(ConfigurationError) as exc:
        build_config(App, ["--db-o", "y:2"], base_configs={"db": {"opts": "plainstr"}})
    message = str(exc.value)
    assert "db.opts" in message
    assert "not a dict" in message


def test_P6_nested_cli_file_merges_onto_layer_value(merge_file):
    result = build_config(
        App,
        ["--db-opts", str(merge_file)],
        base_configs={"db": {"opts": {"x": 1}}},
    )
    assert result.db.opts == {"x": 1, "n": {"b": 2}, "y": 2}


def test_P6_nested_cli_file_does_not_merge_onto_default(merge_file):
    result = build_config(AppD, ["--db-opts", str(merge_file)])
    assert result.db.opts == {"n": {"b": 2}, "y": 2}


def test_P6_nested_cli_file_then_override(merge_file):
    result = build_config(
        App,
        ["--db-opts", str(merge_file), "--db-o", "z:3"],
        base_configs={"db": {"opts": {"x": 1}}},
    )
    assert result.db.opts == {"x": 1, "n": {"b": 2}, "y": 2, "z": 3}


def test_P6_nested_cli_file_merges_onto_instance_layer(merge_file):
    inst = DB(opts={"x": 1})
    result = build_config(
        App, ["--db-opts", str(merge_file)], base_configs={"db": inst}
    )
    assert result.db.opts == {"x": 1, "n": {"b": 2}, "y": 2}
    assert inst.opts == {"x": 1}


def test_P6_nested_cli_file_load_error_names_nested_field():
    with pytest.raises(ConfigurationError) as exc:
        build_config(App, ["--db-opts", "missing.json"])
    assert "'db.opts'" in str(exc.value)


def test_P7_nested_non_file_string_passes_through():
    result = build_config(App, ["--db-opts", "plainstr"])
    assert result.db.opts == "plainstr"


def test_P_nested_cli_dict_value_merges_onto_layer_value():
    builder = GenericConfigBuilder(App)
    flat = builder._flatten_nested_fields()
    processor = NestedFieldProcessor(App, builder.config_resolver.config_fields)

    result = processor.reconstruct(
        {"db": {"opts": {"x": 1}}}, argparse.Namespace(db_opts={"y": 2}), flat
    )
    assert result["db"].opts == {"x": 1, "y": 2}


@dataclass
class DefaultVariants:
    required: int
    factory: Dict[str, Any] = field(default_factory=lambda: {"a": [1]})
    scalar: int = 3


def test_fresh_field_default_variants():
    variants = DefaultVariants.__dataclass_fields__

    first = fresh_field_default(variants["factory"])
    second = fresh_field_default(variants["factory"])
    assert first == {"a": [1]}
    assert first is not second
    assert fresh_field_default(variants["scalar"]) == 3
    assert fresh_field_default(variants["required"]) is MISSING


def test_fresh_field_default_copies_plain_container_default():
    shared = {"k": [1]}
    field_obj = field(default=None)
    field_obj.default = shared

    fresh = fresh_field_default(field_obj)
    assert fresh == shared
    assert fresh is not shared
    assert fresh["k"] is not shared["k"]


# ---------------------------------------------------------------------------
# N1/N2: explicit None from build_config_from_dict
# ---------------------------------------------------------------------------


def test_N1_from_dict_none_clears_base_scalar():
    result = build_config_from_dict(C, {"name": None}, base_configs={"name": "b"})
    assert result.name is None


def test_N1_from_dict_none_without_base():
    result = build_config_from_dict(C, {"name": None})
    assert result.name is None


def test_N2_from_dict_none_clears_base_dict():
    result = build_config_from_dict(C, {"db": None}, base_configs={"db": {"a": 1}})
    assert result.db is None


def test_N2_from_dict_none_list_field():
    result = build_config_from_dict(C, {"tags": None}, base_configs={"tags": ["a"]})
    assert result.tags is None


def test_N_from_dict_none_cli_resolve_not_called():
    seen: List[Any] = []

    @dataclass
    class R:
        sb: Any = combine_annotations(
            cli_resolve(resolver=_recording_resolver(seen)), default=None
        )

    result = build_config_from_dict(R, {"sb": None}, base_configs={"sb": {"a": 1}})
    assert result.sb is None
    assert seen == []


def test_N_from_dict_non_none_route_unchanged():
    result = build_config_from_dict(C, {"name": "z"}, base_configs={"name": "b"})
    assert result.name == "z"


# ---------------------------------------------------------------------------
# K1: hyphenated field-name keys in every layer
# ---------------------------------------------------------------------------


@dataclass
class K:
    db_host: str = "d"


@dataclass
class DBK:
    max_conn: int = 1


@dataclass
class AppK:
    db: DBK = cli_nested(default_factory=DBK)


@dataclass
class Model:
    model_config: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Secret:
    name: str = "n"
    secret_key: str = cli_exclude(default="")


def test_K1_base_configs_hyphen_key():
    result = build_config(K, [], base_configs={"db-host": "h"})
    assert result.db_host == "h"


def test_K1_config_file_hyphen_key(tmp_path):
    config_file = tmp_path / "c.yaml"
    config_file.write_text("db-host: h\n")

    result = build_config(K, ["--config", str(config_file)])
    assert result.db_host == "h"


def test_K1_nested_hyphen_key():
    result = build_config(AppK, [], base_configs={"db": {"max-conn": 5}})
    assert result.db.max_conn == 5


def test_K1_hyphen_dict_field_file_ref_loaded(opts_file):
    result = build_config(Model, [], base_configs={"model-config": str(opts_file)})
    assert result.model_config == {"x": 1}


def test_K1_dict_field_inner_keys_untouched():
    result = build_config(C, [], base_configs={"db": {"max-size": 1}})
    assert result.db == {"max-size": 1}


def test_K1_cli_exclude_field_hyphen_key():
    result = build_config(Secret, [], base_configs={"secret-key": "s"})
    assert result.secret_key == "s"


def test_K1_both_spellings_in_layer_raises():
    with pytest.raises(ConfigurationError) as exc:
        build_config(K, [], base_configs={"db-host": "a", "db_host": "b"})
    message = str(exc.value)
    assert "'db-host'" in message
    assert "'db_host'" in message
    assert "base_configs" in message


def test_K1_both_spellings_nested_raises():
    with pytest.raises(ConfigurationError) as exc:
        build_config(AppK, [], base_configs={"db": {"max-conn": 1, "max_conn": 2}})
    assert "in 'db'" in str(exc.value)


def test_K1_both_spellings_from_dict_raises():
    with pytest.raises(ConfigurationError) as exc:
        build_config_from_dict(K, {"db-host": "a", "db_host": "b"})
    assert "Layer 'config'" in str(exc.value)


def test_K1_from_dict_hyphen_key_does_not_mutate_caller():
    caller = {"db-host": "a"}
    result = build_config_from_dict(K, caller)
    assert result.db_host == "a"
    assert caller == {"db-host": "a"}


def test_K1_same_key_in_different_layers_ok():
    result = build_config(K, [], base_configs=[{"db-host": "a"}, {"db_host": "b"}])
    assert result.db_host == "b"


def test_K1_unknown_hyphen_key_still_fails():
    with pytest.raises(ConfigurationError):
        build_config(K, [], base_configs={"no-such": 1})


def test_K1_rename_preserves_key_order_and_values():
    layer = {"a": 1, "db-host": "h", "z": 2}
    _normalizer(K).normalize(layer, "L")
    assert list(layer.items()) == [("a", 1), ("db_host", "h"), ("z", 2)]


# ---------------------------------------------------------------------------
# AP1: argparse defaults must not mask layer values
# RP1: build_config_from_dict never runs argparse's required-argument check
# ---------------------------------------------------------------------------

BOTH_STRATEGIES = ["shallow", "deep"]


@dataclass
class AppendFields:
    tags: List[str] = combine_annotations(cli_append(), default_factory=list)
    app: List[List[str]] = combine_annotations(
        cli_append(nargs=2), default_factory=list
    )
    seeded: List[str] = combine_annotations(cli_append(), default_factory=lambda: ["d"])
    files: List[List[str]] = combine_annotations(
        cli_append(min_args=1, max_args=2), default_factory=list
    )


@dataclass
class OptionalPositional:
    out: str = combine_annotations(
        cli_positional(nargs="?", default="stdout"), default="stdout"
    )


@dataclass
class StarPositional:
    files: List[str] = combine_annotations(
        cli_positional(nargs="*"), default_factory=list
    )


@dataclass
class StarPositionalSeeded:
    files: List[str] = combine_annotations(
        cli_positional(nargs="*"), default_factory=lambda: ["seed"]
    )


@dataclass
class StarChoices:
    files: List[str] = combine_annotations(
        cli_positional(nargs="*"), cli_choices(["a", "b"]), default_factory=list
    )


@dataclass
class OptionalTyped:
    count: int = combine_annotations(cli_positional(nargs="?", default=5), default=5)
    mode: str = combine_annotations(
        cli_positional(nargs="?"), cli_choices(["fast", "slow"]), default="fast"
    )


def _parser_for(config_class):
    parser = argparse.ArgumentParser()
    GenericConfigBuilder(config_class).add_arguments(parser)
    return parser


@pytest.mark.parametrize("strategy", BOTH_STRATEGIES)
def test_AP1_cli_append_from_base_configs(strategy):
    result = build_config(
        AppendFields, [], base_configs={"tags": ["t"]}, merge_strategy=strategy
    )
    assert result.tags == ["t"]


@pytest.mark.parametrize("strategy", BOTH_STRATEGIES)
def test_AP1_cli_append_nargs_from_base_configs(strategy):
    result = build_config(
        AppendFields, [], base_configs={"app": [["a", "b"]]}, merge_strategy=strategy
    )
    assert result.app == [["a", "b"]]


@pytest.mark.parametrize("strategy", BOTH_STRATEGIES)
def test_AP1_cli_append_from_config_file(tmp_path, strategy):
    config_file = tmp_path / "c.yaml"
    config_file.write_text("tags: [t]\n")

    result = build_config(
        AppendFields, ["--config", str(config_file)], merge_strategy=strategy
    )
    assert result.tags == ["t"]


@pytest.mark.parametrize("strategy", BOTH_STRATEGIES)
def test_AP1_cli_append_cli_still_replaces(strategy):
    result = build_config(
        AppendFields,
        ["--tags", "x", "--tags", "y"],
        base_configs={"tags": ["t"]},
        merge_strategy=strategy,
    )
    assert result.tags == ["x", "y"]


@pytest.mark.parametrize("strategy", BOTH_STRATEGIES)
def test_AP1_cli_append_default_when_unset(strategy):
    result = build_config(AppendFields, [], merge_strategy=strategy)
    assert result.tags == []
    assert result.seeded == ["d"]
    assert result.app == []


@pytest.mark.parametrize("strategy", BOTH_STRATEGIES)
def test_AP1_cli_append_seeded_default_is_overridden_by_layer(strategy):
    result = build_config(
        AppendFields, [], base_configs={"seeded": ["layer"]}, merge_strategy=strategy
    )
    assert result.seeded == ["layer"]


@pytest.mark.parametrize("strategy", BOTH_STRATEGIES)
def test_AP1_cli_append_min_max_validation_on_layer_value(strategy):
    with pytest.raises(ConfigurationError) as exc:
        build_config(
            AppendFields,
            [],
            base_configs={"files": [["a", "b", "c"]]},
            merge_strategy=strategy,
        )
    assert "Expected at most 2" in str(exc.value)


@pytest.mark.parametrize("strategy", BOTH_STRATEGIES)
def test_AP1_optional_positional_from_base_configs(strategy):
    result = build_config(
        OptionalPositional,
        [],
        base_configs={"out": "f.txt"},
        merge_strategy=strategy,
    )
    assert result.out == "f.txt"


@pytest.mark.parametrize("strategy", BOTH_STRATEGIES)
def test_AP1_optional_positional_default(strategy):
    result = build_config(OptionalPositional, [], merge_strategy=strategy)
    assert result.out == "stdout"


@pytest.mark.parametrize("strategy", BOTH_STRATEGIES)
def test_AP1_optional_positional_cli_wins(strategy):
    result = build_config(
        OptionalPositional,
        ["typed.txt"],
        base_configs={"out": "f.txt"},
        merge_strategy=strategy,
    )
    assert result.out == "typed.txt"


@pytest.mark.parametrize("strategy", BOTH_STRATEGIES)
def test_AP1_star_positional_from_base_configs(strategy):
    result = build_config(
        StarPositional, [], base_configs={"files": ["a"]}, merge_strategy=strategy
    )
    assert result.files == ["a"]


@pytest.mark.parametrize("strategy", BOTH_STRATEGIES)
def test_AP1_star_positional_typed_values_win(strategy):
    result = build_config(
        StarPositional,
        ["x", "y"],
        base_configs={"files": ["a"]},
        merge_strategy=strategy,
    )
    assert result.files == ["x", "y"]


@pytest.mark.parametrize("strategy", BOTH_STRATEGIES)
def test_AP1_star_positional_dataclass_default_when_nothing_anywhere(strategy):
    assert build_config(StarPositional, [], merge_strategy=strategy).files == []
    assert build_config(StarPositionalSeeded, [], merge_strategy=strategy).files == [
        "seed"
    ]


@pytest.mark.parametrize("strategy", BOTH_STRATEGIES)
def test_AP1_star_positional_with_choices(strategy):
    # nothing typed, nothing in any layer: dataclass default (no argparse error)
    assert build_config(StarChoices, [], merge_strategy=strategy).files == []
    # typed values are still checked against the choices
    assert build_config(StarChoices, ["a", "b"], merge_strategy=strategy).files == [
        "a",
        "b",
    ]
    # a layer value is not masked when nothing is typed
    assert build_config(
        StarChoices, [], base_configs={"files": ["b"]}, merge_strategy=strategy
    ).files == ["b"]


def test_AP1_star_positional_with_choices_still_rejects_bad_typed_value(capsys):
    with pytest.raises(SystemExit):
        build_config(StarChoices, ["a", "zzz"])
    assert "invalid choice: 'zzz'" in capsys.readouterr().err


def test_AP1_star_positional_with_choices_help_shows_choices_metavar():
    help_text = _parser_for(StarChoices).format_help()
    assert "FILES" in help_text
    assert "SUPPRESS" not in help_text


@pytest.mark.parametrize("strategy", BOTH_STRATEGIES)
def test_AP1_optional_positional_with_type_and_choices_nothing_typed(strategy):
    result = build_config(OptionalTyped, [], merge_strategy=strategy)
    assert (result.count, result.mode) == (5, "fast")

    typed = build_config(OptionalTyped, ["7", "slow"], merge_strategy=strategy)
    assert (typed.count, typed.mode) == (7, "slow")

    layered = build_config(
        OptionalTyped,
        [],
        base_configs={"count": 9, "mode": "slow"},
        merge_strategy=strategy,
    )
    assert (layered.count, layered.mode) == (9, "slow")


def test_AP1_parse_args_suppress_append():
    parser = _parser_for(AppendFields)
    assert not hasattr(parser.parse_args([]), "tags")
    assert not hasattr(parser.parse_args([]), "seeded")
    assert not hasattr(parser.parse_args([]), "files")
    typed = parser.parse_args(["--tags", "x", "--tags", "y", "--files", "a", "b"])
    assert typed.tags == ["x", "y"]
    assert typed.files == [["a", "b"]]


def test_AP1_parse_args_suppress_star_positional():
    parser = _parser_for(StarPositionalSeeded)
    assert not hasattr(parser.parse_args([]), "files")
    assert parser.parse_args(["x", "y"]).files == ["x", "y"]


def test_AP1_parse_args_optional_positional_has_no_default():
    parser = _parser_for(OptionalPositional)
    assert getattr(parser.parse_args([]), "out", None) is None
    assert parser.parse_args(["typed"]).out == "typed"


@dataclass
class HelpKinds:
    out: str = combine_annotations(
        cli_positional(nargs="?", default="stdout"),
        cli_help("Output file"),
        default="stdout",
    )
    inputs: List[str] = combine_annotations(
        cli_positional(nargs="*"), cli_help("Input files"), default_factory=list
    )
    tags: List[str] = combine_annotations(
        cli_append(), cli_help("Tags"), default_factory=lambda: ["dflt"]
    )
    pairs: List[List[str]] = combine_annotations(
        cli_append(nargs=2), cli_help("Pairs"), default_factory=list
    )
    files: List[List[str]] = combine_annotations(
        cli_append(min_args=1, max_args=2), cli_help("Files"), default_factory=list
    )
    name: str = "n"


# Captured from the tree before AP1 (the usage line and the section heading
# differ between Python versions, so only the argument listing is compared)
EXPECTED_HELP_LISTING = """\
  OUT                  Output file
  INPUTS               Input files

options:
  -h, --help           show this help message and exit
  --config CONFIG      Base configuration file (JSON, YAML, or TOML)
  --tags TAGS          Tags (can be repeated)
  --pairs PAIRS PAIRS  Pairs (can be repeated)
  --files FILES        Files (can be repeated, 1-2 args each)
  --name NAME          name
"""


def test_AP1_help_unchanged(monkeypatch):
    monkeypatch.setenv("COLUMNS", "100")
    parser = argparse.ArgumentParser(
        prog="prog", description="d", formatter_class=RangeAppendHelpFormatter
    )
    GenericConfigBuilder(HelpKinds).add_arguments(parser)

    help_text = parser.format_help().replace("optional arguments:", "options:")
    listing = help_text.split("positional arguments:\n", 1)[1]
    assert listing == EXPECTED_HELP_LISTING
    assert "dflt" not in help_text
    assert "SUPPRESS" not in help_text


@dataclass
class Req:
    source: str = cli_positional()


@pytest.mark.parametrize("strategy", BOTH_STRATEGIES)
def test_RP1_from_dict_required_positional(strategy):
    result = build_config_from_dict(Req, {"source": "s"}, merge_strategy=strategy)
    assert result == Req(source="s")


@pytest.mark.parametrize("strategy", BOTH_STRATEGIES)
def test_RP1_from_dict_missing_required_positional(capsys, strategy):
    with pytest.raises(ConfigurationError) as exc:
        build_config_from_dict(Req, {}, merge_strategy=strategy)
    assert "Failed to create Req" in str(exc.value)
    captured = capsys.readouterr()
    assert captured.err == ""
    assert captured.out == ""


@pytest.mark.parametrize("strategy", BOTH_STRATEGIES)
def test_RP1_from_dict_required_positional_from_base_configs(strategy):
    result = build_config_from_dict(
        Req, {}, base_configs={"source": "b"}, merge_strategy=strategy
    )
    assert result.source == "b"


@dataclass
class EveryKind:
    name: str = "n"
    flag: bool = False
    note: Optional[str] = None
    tags: List[str] = combine_annotations(cli_append(), default_factory=list)
    files: List[List[str]] = combine_annotations(
        cli_append(min_args=1, max_args=2), default_factory=list
    )
    out: str = combine_annotations(cli_positional(nargs="?"), default="o")
    rest: List[str] = combine_annotations(
        cli_positional(nargs="*"), default_factory=list
    )
    payload: Dict[str, Any] = field(default_factory=dict)
    sb: Any = combine_annotations(cli_resolve(resolver=lambda v: v), default=None)
    db: DB = cli_nested(default_factory=DB)


def test_RP1_namespace_equivalence():
    parser = _parser_for(EveryKind)
    parsed = parser.parse_args([])
    empty = _empty_namespace(parser)

    parsed_values = {k: v for k, v in vars(parsed).items() if v is not None}
    empty_values = {k: v for k, v in vars(empty).items() if v is not None}
    assert parsed_values == empty_values == {}
    assert set(vars(parsed)) <= set(vars(empty))
    assert "help" not in vars(empty)
    assert {"name", "flag", "tags", "out", "rest", "db_host", "config"} <= set(
        vars(empty)
    )


def test_RP1_empty_namespace_covers_every_parser_destination():
    parser = _parser_for(EveryKind)
    destinations = {a.dest for a in parser._actions if a.dest != "help"}
    assert set(vars(_empty_namespace(parser))) == destinations
    assert all(value is None for value in vars(_empty_namespace(parser)).values())
