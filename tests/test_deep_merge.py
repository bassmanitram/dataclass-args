"""
Tests for opt-in deep merge: the deep_merge primitive, merge_strategy on all
four entry points, validation, the E1-E12 oracles in both modes, cli_resolve
interaction, and deep merge of files and nested dataclasses.
"""

import argparse
import inspect
import json
from dataclasses import dataclass, field
from typing import Any, Dict, List

import pytest

import dataclass_args
from dataclass_args import (
    MERGE_DEEP,
    MERGE_SHALLOW,
    ConfigBuilderError,
    build_config,
    build_config_from_cli,
    build_config_from_dict,
    cli_nested,
    cli_resolve,
    combine_annotations,
    deep_merge,
)
from dataclass_args.builder import GenericConfigBuilder
from dataclass_args.config_applicator import ConfigApplicator
from dataclass_args.merge_strategy import (
    MergeContext,
    combine_dicts,
    make_merge_context,
)

SHALLOW_AND_DEEP = [MERGE_SHALLOW, MERGE_DEEP]


@dataclass
class C:
    name: str = "x"
    db: Dict[str, Any] = field(default_factory=dict)


@dataclass
class DB:
    host: str = "localhost"
    opts: Dict[str, Any] = field(default_factory=dict)


@dataclass
class App:
    db: DB = cli_nested(default_factory=DB)


@dataclass
class Inner:
    opts: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Mid:
    inner: Inner = cli_nested(default_factory=Inner)


@dataclass
class Top:
    mid: Mid = cli_nested(default_factory=Mid)


# ---------------------------------------------------------------------------
# deep_merge primitive
# ---------------------------------------------------------------------------


def test_deep_merge_reference_oracle():
    base = {
        "a": 1,
        "db": {"host": "h", "nested": {"x": 1, "y": 2}, "tags": [1, 2]},
        "keep": {"k": 1},
    }
    override = {
        "a": 2,
        "db": {"port": 5, "nested": {"y": 3, "z": 4}, "tags": [9]},
        "new": None,
    }
    result = deep_merge(base, override)

    assert result == {
        "a": 2,
        "db": {
            "host": "h",
            "nested": {"x": 1, "y": 3, "z": 4},
            "tags": [9],
            "port": 5,
        },
        "keep": {"k": 1},
        "new": None,
    }
    assert list(result) == ["a", "db", "keep", "new"]
    assert list(result["db"]) == ["host", "nested", "tags", "port"]


def test_deep_merge_keeps_keys_only_in_base():
    assert deep_merge({"a": 1, "b": {"c": 2}}, {"d": 3}) == {
        "a": 1,
        "b": {"c": 2},
        "d": 3,
    }


@pytest.mark.parametrize(
    "base_value, override_value",
    [
        ({"a": 1}, [1]),
        ([1], {"a": 1}),
        ({"a": 1}, None),
        ({"a": 1}, 5),
        (5, {"a": 1}),
        ([1, 2], [3]),
        ("s", "t"),
        (None, {"a": 1}),
        (None, None),
    ],
)
def test_deep_merge_override_wins_for_mixed_types(base_value, override_value):
    result = deep_merge({"k": base_value}, {"k": override_value})
    assert result == {"k": override_value}


def test_deep_merge_three_or_more_levels():
    base = {"l1": {"l2": {"l3": {"a": 1, "b": 1}}}}
    override = {"l1": {"l2": {"l3": {"b": 2, "c": 3}}}}
    assert deep_merge(base, override) == {
        "l1": {"l2": {"l3": {"a": 1, "b": 2, "c": 3}}}
    }


def test_deep_merge_empty_inputs():
    assert deep_merge({}, {}) == {}
    assert deep_merge({"a": {"b": 1}}, {}) == {"a": {"b": 1}}
    assert deep_merge({}, {"a": {"b": 1}}) == {"a": {"b": 1}}


def test_deep_merge_does_not_mutate_inputs_at_depth():
    base = {"db": {"nested": {"a": [1, {"k": 1}]}}, "only": {"x": [1]}}
    override = {"db": {"nested": {"b": {"c": 1}}}, "new": {"y": [2]}}
    base_snapshot = json.loads(json.dumps(base))
    override_snapshot = json.loads(json.dumps(override))

    result = deep_merge(base, override)
    result["db"]["nested"]["a"].append(99)
    result["db"]["nested"]["a"][1]["k"] = 99
    result["db"]["nested"]["b"]["c"] = 99
    result["only"]["x"].append(99)
    result["new"]["y"].append(99)

    assert base == base_snapshot
    assert override == override_snapshot


def test_deep_merge_fresh_containers_at_every_level():
    base = {"db": {"nested": {"a": 1}, "tags": [1]}, "only": {"x": {"y": 1}}}
    override = {"db": {"nested": {"b": 2}}, "new": {"z": {"w": 1}}}
    result = deep_merge(base, override)

    assert result["db"] is not base["db"]
    assert result["db"]["nested"] is not base["db"]["nested"]
    assert result["db"]["tags"] is not base["db"]["tags"]
    assert result["only"] is not base["only"]
    assert result["only"]["x"] is not base["only"]["x"]
    assert result["new"] is not override["new"]
    assert result["new"]["z"] is not override["new"]["z"]


def test_deep_merge_copies_dicts_inside_lists():
    base = {"items": [{"a": 1}], "other": [[{"b": 1}]]}
    override = {"more": [{"c": 1}]}
    result = deep_merge(base, override)

    assert result["items"] == [{"a": 1}]
    assert result["items"][0] is not base["items"][0]
    assert result["other"][0][0] is not base["other"][0][0]
    assert result["more"][0] is not override["more"][0]


def test_deep_merge_shares_non_container_objects():
    marker = object()
    func = lambda: None  # noqa: E731
    pair = (1, [2])
    result = deep_merge({"a": marker, "t": pair}, {"f": func})

    assert result["a"] is marker
    assert result["t"] is pair
    assert result["f"] is func


def test_deep_merge_does_not_normalise_keys():
    result = deep_merge({"db-host": 1}, {"db_host": 2})
    assert result == {"db-host": 1, "db_host": 2}


# ---------------------------------------------------------------------------
# Constants, exports, signatures
# ---------------------------------------------------------------------------


def test_constants_and_exports():
    assert MERGE_SHALLOW == "shallow"
    assert MERGE_DEEP == "deep"
    for name in ("deep_merge", "MERGE_SHALLOW", "MERGE_DEEP"):
        assert name in dataclass_args.__all__
        assert hasattr(dataclass_args, name)

    from dataclass_args import config_merging, utils

    assert config_merging.MERGE_SHALLOW == "shallow"
    assert config_merging.MERGE_DEEP == "deep"
    assert utils.deep_merge is deep_merge


def test_merge_context_is_internal_and_defaults_to_shallow():
    assert "MergeContext" not in dataclass_args.__all__
    assert not hasattr(dataclass_args, "MergeContext")
    assert MergeContext().strategy == MERGE_SHALLOW
    with pytest.raises(Exception):
        MergeContext().strategy = MERGE_DEEP  # frozen


@pytest.mark.parametrize(
    "function, expected_tail",
    [
        (build_config, ["merge_strategy", "return_provenance"]),
        (build_config_from_cli, ["merge_strategy", "return_provenance"]),
        (
            build_config_from_dict,
            ["config_list_merge", "merge_strategy", "return_provenance"],
        ),
        (
            GenericConfigBuilder.build_config,
            ["merge_strategy", "return_provenance"],
        ),
    ],
)
def test_merge_strategy_precedes_return_provenance_defaulting_to_shallow(
    function, expected_tail
):
    parameters = list(inspect.signature(function).parameters.values())
    assert [p.name for p in parameters[-len(expected_tail) :]] == expected_tail
    by_name = {p.name: p for p in parameters}
    assert by_name["merge_strategy"].default == "shallow"
    assert by_name["return_provenance"].default is False


# ---------------------------------------------------------------------------
# E1-E12 oracles, in both modes
# ---------------------------------------------------------------------------


def _file(tmp_path, name, content):
    path = tmp_path / name
    path.write_text(content if isinstance(content, str) else json.dumps(content))
    return str(path)


def _e1(strategy, tmp_path):
    return build_config(
        C,
        [],
        base_configs=[
            {"name": "app", "db": {"host": "localhost", "port": 5432}},
            {"db": {"port": 3306, "timeout": 30}},
        ],
        merge_strategy=strategy,
    ).db


def _e2(strategy, tmp_path):
    config_file = _file(tmp_path, "e2.yaml", "db: {port: 1, nested: {b: 2}}\n")
    return build_config(
        C,
        ["--config", config_file],
        base_configs={"db": {"host": "h", "nested": {"a": 1}}},
        merge_strategy=strategy,
    ).db


def _e3(strategy, tmp_path):
    db_file = _file(tmp_path, "e3.json", {"port": 1, "nested": {"b": 2}})
    return build_config_from_cli(
        C,
        ["--db", db_file],
        base_configs={"db": {"host": "h", "nested": {"a": 1}}},
        merge_strategy=strategy,
    ).db


def _e4(strategy, tmp_path):
    return build_config(
        C,
        ["--d", "nested.c:3"],
        base_configs={"db": {"nested": {"a": 1}}},
        merge_strategy=strategy,
    ).db


def _e5(strategy, tmp_path):
    db_file = _file(tmp_path, "e3.json", {"port": 1, "nested": {"b": 2}})
    return build_config(
        C,
        ["--db", db_file, "--d", "nested.c:3"],
        base_configs={"db": {"host": "h", "nested": {"a": 1}}},
        merge_strategy=strategy,
    ).db["nested"]


def _e6(strategy, tmp_path):
    return build_config_from_dict(
        C,
        {"db": {"port": 1, "nested": {"b": 2}}},
        base_configs={"db": {"host": "h", "nested": {"a": 1}}},
        merge_strategy=strategy,
    ).db


def _e7(strategy, tmp_path):
    return build_config(
        App,
        [],
        base_configs=[
            {"db": {"host": "a", "opts": {"x": 1}}},
            {"db": {"opts": {"y": 2}}},
        ],
        merge_strategy=strategy,
    ).db


def _e8(strategy, tmp_path):
    opts_file = _file(tmp_path, "e8.json", {"n": {"b": 2}})
    return build_config(
        App,
        ["--db-opts", opts_file],
        base_configs={"db": {"opts": {"x": 1, "n": {"a": 1}}}},
        merge_strategy=strategy,
    ).db.opts


def _e9(strategy, tmp_path):
    return build_config(
        C,
        [],
        base_configs=[{"db": {"tags": [1, 2]}}, {"db": {"tags": [3]}}],
        merge_strategy=strategy,
    ).db["tags"]


def _e10(strategy, tmp_path):
    return build_config(
        C,
        [],
        base_configs=[{"db": {"nested": {"a": 1}}}, {"db": {"nested": None}}],
        merge_strategy=strategy,
    ).db["nested"]


_SAME_E3 = {"host": "h", "nested": {"b": 2}, "port": 1}
_DEEP_E3 = {"host": "h", "nested": {"a": 1, "b": 2}, "port": 1}

ORACLES = [
    pytest.param(
        _e1,
        {"host": "localhost", "port": 3306, "timeout": 30},
        {"host": "localhost", "port": 3306, "timeout": 30},
        id="E1",
    ),
    pytest.param(
        _e2,
        {"host": "h", "nested": {"b": 2}, "port": 1},
        {"host": "h", "nested": {"a": 1, "b": 2}, "port": 1},
        id="E2",
    ),
    pytest.param(_e3, _SAME_E3, _DEEP_E3, id="E3"),
    pytest.param(
        _e4,
        {"nested": {"a": 1, "c": 3}},
        {"nested": {"a": 1, "c": 3}},
        id="E4",
    ),
    pytest.param(_e5, {"b": 2, "c": 3}, {"a": 1, "b": 2, "c": 3}, id="E5"),
    pytest.param(_e6, _SAME_E3, _DEEP_E3, id="E6"),
    pytest.param(
        _e7,
        DB(host="a", opts={"y": 2}),
        DB(host="a", opts={"x": 1, "y": 2}),
        id="E7",
    ),
    pytest.param(
        _e8,
        {"x": 1, "n": {"b": 2}},
        {"x": 1, "n": {"a": 1, "b": 2}},
        id="E8",
    ),
    pytest.param(_e9, [3], [3], id="E9"),
    pytest.param(_e10, None, None, id="E10"),
]


@pytest.mark.parametrize("oracle, shallow_expected, deep_expected", ORACLES)
def test_E1_to_E10_in_both_modes(tmp_path, oracle, shallow_expected, deep_expected):
    assert oracle(MERGE_SHALLOW, tmp_path) == shallow_expected
    assert oracle(MERGE_DEEP, tmp_path) == deep_expected


def test_default_strategy_omitted_equals_shallow():
    layers = [{"db": {"a": {"x": 1}}}, {"db": {"a": {"y": 2}}}]
    assert build_config(C, [], base_configs=layers).db == {"a": {"y": 2}}


@pytest.mark.parametrize("bad", ["Deep", "replace", "", True, None, 1, ["deep"]])
def test_E11_invalid_strategy_raises_before_any_file_is_loaded(bad):
    with pytest.raises(ConfigBuilderError) as exc:
        build_config(
            C, [], base_configs="/nonexistent/never/loaded.yaml", merge_strategy=bad
        )
    message = str(exc.value)
    assert "merge_strategy must be 'shallow' or 'deep'" in message
    assert repr(bad) in message


def test_E11_invalid_strategy_raises_on_every_entry_point():
    missing = "/nonexistent/never/loaded.yaml"
    with pytest.raises(ConfigBuilderError):
        build_config_from_cli(C, [], base_configs=missing, merge_strategy="nope")
    with pytest.raises(ConfigBuilderError):
        build_config_from_dict(C, {}, base_configs=missing, merge_strategy="nope")

    builder = GenericConfigBuilder(C)
    parser = argparse.ArgumentParser()
    builder.add_arguments(parser)
    with pytest.raises(ConfigBuilderError):
        builder.build_config(
            parser.parse_args([]), base_configs=missing, merge_strategy="nope"
        )


@pytest.mark.parametrize("strategy", SHALLOW_AND_DEEP)
def test_E12_caller_base_configs_are_never_mutated(tmp_path, strategy):
    db_file = _file(tmp_path, "e3.json", {"port": 1, "nested": {"b": 2}})
    base = {"db": {"host": "h", "nested": {"a": 1}}}

    build_config(
        C,
        ["--db", db_file, "--d", "nested.c:3"],
        base_configs=base,
        merge_strategy=strategy,
    )
    assert base == {"db": {"host": "h", "nested": {"a": 1}}}


@pytest.mark.parametrize("strategy", SHALLOW_AND_DEEP)
def test_caller_config_for_from_dict_is_never_mutated(strategy):
    config = {"db": {"nested": {"b": 2}}}
    base = {"db": {"nested": {"a": 1}}}
    build_config_from_dict(C, config, base_configs=base, merge_strategy=strategy)
    assert config == {"db": {"nested": {"b": 2}}}
    assert base == {"db": {"nested": {"a": 1}}}


# ---------------------------------------------------------------------------
# All four entry points accept merge_strategy
# ---------------------------------------------------------------------------


def test_entry_points_accept_merge_strategy(tmp_path):
    assert _e1(MERGE_DEEP, tmp_path)["host"] == "localhost"  # build_config
    assert _e3(MERGE_DEEP, tmp_path) == _DEEP_E3  # build_config_from_cli
    assert _e6(MERGE_DEEP, tmp_path) == _DEEP_E3  # build_config_from_dict


def test_generic_config_builder_build_config_accepts_merge_strategy(tmp_path):
    db_file = _file(tmp_path, "e3.json", {"port": 1, "nested": {"b": 2}})
    builder = GenericConfigBuilder(C)
    parser = argparse.ArgumentParser()
    builder.add_arguments(parser)
    args = parser.parse_args(["--db", db_file])

    result = builder.build_config(
        args,
        base_configs={"db": {"host": "h", "nested": {"a": 1}}},
        merge_strategy=MERGE_DEEP,
    )
    assert result.db == _DEEP_E3


# ---------------------------------------------------------------------------
# Strategy plumbing units
# ---------------------------------------------------------------------------


def test_make_merge_context():
    assert make_merge_context("shallow") == MergeContext("shallow")
    assert make_merge_context("deep") == MergeContext("deep")
    with pytest.raises(ConfigBuilderError):
        make_merge_context("DEEP")


def test_combine_dicts_dispatch():
    base = {"a": {"x": 1}}
    override = {"a": {"y": 2}}

    assert combine_dicts(base, override, MergeContext("shallow")) == {"a": {"y": 2}}
    assert combine_dicts(base, override, MergeContext("deep")) == {
        "a": {"x": 1, "y": 2}
    }
    assert base == {"a": {"x": 1}}
    assert override == {"a": {"y": 2}}


def test_combine_dicts_uses_the_sites_shallow_function():
    config = {"a": {"x": 1}}
    result = combine_dicts(
        config, {"a": {"y": 2}}, MergeContext(), ConfigApplicator.merge_layer
    )
    assert result is config
    assert result == {"a": {"x": 1, "y": 2}}


def test_merge_layer_with_shallow_mutates_and_deep_returns_new():
    config = {"db": {"a": {"x": 1}}}
    layer = {"db": {"a": {"y": 2}}}

    shallow = ConfigApplicator.merge_layer_with(config, layer, MergeContext("shallow"))
    assert shallow is config
    assert config == {"db": {"a": {"y": 2}}}

    config = {"db": {"a": {"x": 1}}}
    deep = ConfigApplicator.merge_layer_with(config, layer, MergeContext("deep"))
    assert deep is not config
    assert deep == {"db": {"a": {"x": 1, "y": 2}}}
    assert config == {"db": {"a": {"x": 1}}}


def test_apply_base_configs_deep_does_not_alias_layers():
    layers = [{"db": {"a": {"x": 1}}}, {"db": {"b": [1]}}]
    result = ConfigApplicator.apply_base_configs(layers, MergeContext("deep"))
    result["db"]["a"]["x"] = 99
    result["db"]["b"].append(2)
    assert layers == [{"db": {"a": {"x": 1}}}, {"db": {"b": [1]}}]


def test_apply_config_file_deep_merges_the_loaded_file(tmp_path):
    config_file = _file(tmp_path, "c.yaml", "db: {b: {y: 2}}\n")
    args = argparse.Namespace(config=config_file)

    result = ConfigApplicator.apply_config_file(
        {"db": {"b": {"x": 1}}}, args, "config", None, MergeContext("deep")
    )
    assert result == {"db": {"b": {"x": 1, "y": 2}}}


# ---------------------------------------------------------------------------
# Deep merge with files, nested dataclasses and depth (A1-A3)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("strategy", SHALLOW_AND_DEEP)
def test_A1_file_ref_layer_then_dict_layer(tmp_path, strategy):
    db_file = _file(tmp_path, "db.yaml", "{host: h, opts: {x: 1}}\n")
    result = build_config(
        C,
        [],
        base_configs=[{"db": db_file}, {"db": {"opts": {"y": 2}}}],
        merge_strategy=strategy,
    )
    expected = {
        MERGE_DEEP: {"host": "h", "opts": {"x": 1, "y": 2}},
        MERGE_SHALLOW: {"host": "h", "opts": {"y": 2}},
    }[strategy]
    assert result.db == expected


@pytest.mark.parametrize("strategy", SHALLOW_AND_DEEP)
def test_A2_nested_dataclass_dict_field_file_ref_layers(tmp_path, strategy):
    opts_file = _file(tmp_path, "o.yaml", "x: 1\n")
    result = build_config(
        App,
        [],
        base_configs=[{"db": {"opts": opts_file}}, {"db": {"opts": {"y": 2}}}],
        merge_strategy=strategy,
    )
    expected = {MERGE_DEEP: {"x": 1, "y": 2}, MERGE_SHALLOW: {"y": 2}}[strategy]
    assert result.db.opts == expected


@pytest.mark.parametrize("strategy", SHALLOW_AND_DEEP)
def test_A3_two_layers_merge_opts_at_depth_two(strategy):
    result = build_config(
        Top,
        [],
        base_configs=[
            {"mid": {"inner": {"opts": {"a": {"x": 1}, "keep": 1}}}},
            {"mid": {"inner": {"opts": {"a": {"y": 2}}}}},
        ],
        merge_strategy=strategy,
    )
    expected = {
        MERGE_DEEP: {"a": {"x": 1, "y": 2}, "keep": 1},
        MERGE_SHALLOW: {"a": {"y": 2}},
    }[strategy]
    assert result.mid.inner.opts == expected


@pytest.mark.parametrize("strategy", SHALLOW_AND_DEEP)
def test_A3_cli_file_at_depth_merges_onto_layer_value(tmp_path, strategy):
    opts_file = _file(tmp_path, "f.json", {"a": {"y": 2}})
    result = build_config(
        Top,
        ["--mid-inner-opts", opts_file],
        base_configs={"mid": {"inner": {"opts": {"a": {"x": 1}, "keep": 1}}}},
        merge_strategy=strategy,
    )
    expected = {
        MERGE_DEEP: {"a": {"x": 1, "y": 2}, "keep": 1},
        MERGE_SHALLOW: {"a": {"y": 2}, "keep": 1},
    }[strategy]
    assert result.mid.inner.opts == expected


def test_A3_cli_file_at_depth_does_not_merge_onto_default(tmp_path):
    @dataclass
    class InD:
        opts: Dict[str, Any] = field(default_factory=lambda: {"a": {"x": 1}})

    @dataclass
    class TpD:
        inner: InD = cli_nested(default_factory=InD)

    opts_file = _file(tmp_path, "f.json", {"a": {"y": 2}})
    result = build_config(TpD, ["--inner-opts", opts_file], merge_strategy=MERGE_DEEP)
    assert result.inner.opts == {"a": {"y": 2}}


def test_deep_merge_property_overrides_unchanged_at_depth():
    result = build_config(
        Top,
        ["--mid-inner-o", "a.y:2"],
        base_configs={"mid": {"inner": {"opts": {"a": {"x": 1}}}}},
        merge_strategy=MERGE_DEEP,
    )
    assert result.mid.inner.opts == {"a": {"x": 1, "y": 2}}


def test_deep_mode_lists_replace_and_none_clears():
    @dataclass
    class L:
        tags: List[str] = field(default_factory=list)
        name: Any = "x"

    result = build_config(
        L,
        [],
        base_configs=[{"tags": ["a"], "name": "b"}, {"tags": ["c"], "name": None}],
        merge_strategy=MERGE_DEEP,
    )
    assert result.tags == ["c"]
    assert result.name is None


# ---------------------------------------------------------------------------
# cli_resolve (A4)
# ---------------------------------------------------------------------------


def _resolver_class(seen):
    def resolver(value):
        seen.append(value)
        return value

    @dataclass
    class R:
        sb: Any = combine_annotations(cli_resolve(resolver=resolver), default=None)

    return R


@pytest.mark.parametrize("strategy", SHALLOW_AND_DEEP)
def test_A4_cli_resolve_dict_in_base_and_cli_file(tmp_path, strategy):
    seen: List[Any] = []
    sb_file = _file(tmp_path, "sb.json", {"a": {"y": 2}})

    build_config(
        _resolver_class(seen),
        ["--sb", sb_file],
        base_configs={"sb": {"a": {"x": 1}, "k": 1}},
        merge_strategy=strategy,
    )
    expected = {
        MERGE_DEEP: {"a": {"x": 1, "y": 2}, "k": 1},
        MERGE_SHALLOW: {"a": {"y": 2}, "k": 1},
    }[strategy]
    assert seen == [expected]


@pytest.mark.parametrize("strategy", SHALLOW_AND_DEEP)
def test_A4_cli_resolve_prebuilt_object_in_base_is_replaced(tmp_path, strategy):
    seen: List[Any] = []
    prebuilt = object()
    sb_file = _file(tmp_path, "sb.json", {"a": 1})

    build_config(
        _resolver_class(seen),
        ["--sb", sb_file],
        base_configs={"sb": prebuilt},
        merge_strategy=strategy,
    )
    assert seen == [{"a": 1}]


@pytest.mark.parametrize("strategy", SHALLOW_AND_DEEP)
def test_A4_cli_resolve_prebuilt_object_keeps_identity(strategy):
    seen: List[Any] = []
    prebuilt = object()

    build_config(
        _resolver_class(seen),
        [],
        base_configs={"sb": prebuilt},
        merge_strategy=strategy,
    )
    assert seen[0] is prebuilt


# ---------------------------------------------------------------------------
# IN1: instances of cli_nested fields become field dicts at layer intake
# ---------------------------------------------------------------------------


@dataclass
class DBP:
    host: str = "localhost"
    port: int = 5432
    opts: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AppP:
    db: DBP = cli_nested(default_factory=DBP)


@dataclass
class InnerV:
    v: int = 1
    opts: Dict[str, Any] = field(default_factory=dict)


@dataclass
class MidW:
    w: int = 2
    inner: InnerV = cli_nested(default_factory=InnerV)


@dataclass
class TopW:
    mid: MidW = cli_nested(default_factory=MidW)


@dataclass
class DBX:
    host: str = "h"
    url: str = field(init=False, default="")

    def __post_init__(self) -> None:
        self.url = f"db://{self.host}"


@dataclass
class AppX:
    dbx: DBX = cli_nested(default_factory=DBX)


def _prod_instance():
    return DBP(host="prod", port=6000, opts={"x": 1})


@pytest.mark.parametrize(
    "strategy, expected_opts",
    [(MERGE_SHALLOW, {"y": 2}), (MERGE_DEEP, {"x": 1, "y": 2})],
)
def test_IN1_instance_then_dict_layer(strategy, expected_opts):
    result = build_config(
        AppP,
        [],
        base_configs=[{"db": _prod_instance()}, {"db": {"opts": {"y": 2}}}],
        merge_strategy=strategy,
    )
    assert result.db == DBP("prod", 6000, expected_opts)


@pytest.mark.parametrize("strategy", SHALLOW_AND_DEEP)
def test_IN1_from_dict_over_instance_base(strategy):
    result = build_config_from_dict(
        AppP,
        {"db": {"port": 7000}},
        base_configs={"db": _prod_instance()},
        merge_strategy=strategy,
    )
    assert result.db == DBP("prod", 7000, {"x": 1})


@pytest.mark.parametrize(
    "strategy, expected_opts",
    [(MERGE_SHALLOW, {}), (MERGE_DEEP, {"k": 1})],
)
def test_IN1_dict_then_instance_layer(strategy, expected_opts):
    result = build_config(
        AppP,
        [],
        base_configs=[{"db": {"host": "a", "opts": {"k": 1}}}, {"db": DBP(port=1)}],
        merge_strategy=strategy,
    )
    assert result.db == DBP("localhost", 1, expected_opts)


@pytest.mark.parametrize(
    "strategy, expected_opts",
    [(MERGE_SHALLOW, {"y": 2}), (MERGE_DEEP, {"x": 1, "y": 2})],
)
def test_IN1_instance_then_instance(strategy, expected_opts):
    result = build_config(
        AppP,
        [],
        base_configs=[{"db": DBP(opts={"x": 1})}, {"db": DBP(opts={"y": 2})}],
        merge_strategy=strategy,
    )
    assert result.db.opts == expected_opts


@pytest.mark.parametrize(
    "strategy, expected_inner",
    [
        (MERGE_SHALLOW, InnerV(v=1, opts={"y": 2})),
        (MERGE_DEEP, InnerV(v=5, opts={"y": 2})),
    ],
)
def test_IN1_depth_two(strategy, expected_inner):
    result = build_config(
        TopW,
        [],
        base_configs=[
            {"mid": MidW(w=5, inner=InnerV(v=5))},
            {"mid": {"inner": {"opts": {"y": 2}}}},
        ],
        merge_strategy=strategy,
    )
    assert result.mid == MidW(w=5, inner=expected_inner)


def test_IN1_caller_instance_not_mutated():
    inst = _prod_instance()
    inner_opts = inst.opts

    result = build_config(
        AppP,
        ["--db-o", "z:1"],
        base_configs=[{"db": inst}, {"db": {"opts": {"y": 2}}}],
        merge_strategy=MERGE_DEEP,
    )
    assert result.db.opts == {"x": 1, "y": 2, "z": 1}
    assert inst == DBP("prod", 6000, {"x": 1})
    assert inst.opts is inner_opts
    assert result.db.opts is not inst.opts


def test_IN1_caller_nested_instance_not_mutated_at_depth():
    inst = MidW(w=5, inner=InnerV(v=5, opts={"x": [1]}))

    result = build_config(
        TopW,
        ["--mid-inner-o", "x.+:2"],
        base_configs={"mid": inst},
        merge_strategy=MERGE_DEEP,
    )
    assert result.mid.inner.opts == {"x": [1, 2]}
    assert inst == MidW(w=5, inner=InnerV(v=5, opts={"x": [1]}))


@pytest.mark.parametrize("strategy", SHALLOW_AND_DEEP)
def test_IN1_init_false_field_recomputed(strategy):
    result = build_config(
        AppX,
        [],
        base_configs=[{"dbx": DBX(host="a")}, {"dbx": {"host": "b"}}],
        merge_strategy=strategy,
    )
    assert result.dbx.host == "b"
    assert result.dbx.url == "db://b"


@pytest.mark.parametrize("strategy", SHALLOW_AND_DEEP)
def test_IN1_cli_resolve_prebuilt_untouched(tmp_path, strategy):
    seen: List[Any] = []
    sb_file = _file(tmp_path, "sb.json", {"a": 1})

    build_config(
        _resolver_class(seen),
        ["--sb", sb_file],
        base_configs={"sb": DBP(port=1)},
        merge_strategy=strategy,
    )
    assert seen == [{"a": 1}]


@pytest.mark.parametrize("strategy", SHALLOW_AND_DEEP)
def test_IN1_cli_resolve_prebuilt_instance_keeps_identity(strategy):
    seen: List[Any] = []
    prebuilt = DBP(port=1)

    build_config(
        _resolver_class(seen),
        [],
        base_configs={"sb": prebuilt},
        merge_strategy=strategy,
    )
    assert seen[0] is prebuilt


@pytest.mark.parametrize("strategy", SHALLOW_AND_DEEP)
def test_IN1_any_field_instance_not_converted(strategy):
    @dataclass
    class Holder:
        obj: Any = None

    result = build_config(
        Holder,
        [],
        base_configs=[{"obj": DBP()}, {"obj": {"port": 1}}],
        merge_strategy=strategy,
    )
    assert result.obj == {"port": 1}

    kept = build_config(
        Holder, [], base_configs={"obj": DBP(port=3)}, merge_strategy=strategy
    )
    assert kept.obj == DBP(port=3)


@pytest.mark.parametrize("strategy", SHALLOW_AND_DEEP)
def test_IN1_instance_inside_dict_field_value_not_converted(strategy):
    marker = DBP(port=9)
    result = build_config(
        C,
        [],
        base_configs=[{"db": {"obj": marker}}, {"db": {"other": 1}}],
        merge_strategy=strategy,
    )
    assert result.db["obj"] is marker


@pytest.mark.parametrize("strategy", SHALLOW_AND_DEEP)
def test_IN1_nested_sub_instance_converted_recursively(strategy):
    result = build_config(
        TopW,
        [],
        base_configs=[
            {"mid": MidW(w=5, inner=InnerV(v=5, opts={"x": 1}))},
            {"mid": {"w": 6}},
        ],
        merge_strategy=strategy,
    )
    assert result.mid == MidW(w=6, inner=InnerV(v=5, opts={"x": 1}))


@pytest.mark.parametrize("strategy", SHALLOW_AND_DEEP)
def test_IN1_dict_field_file_ref_inside_instance_is_loaded(tmp_path, strategy):
    opts_file = _file(tmp_path, "o.yaml", "x: 1\n")
    result = build_config(
        AppP,
        [],
        base_configs=[{"db": DBP(opts=opts_file)}, {"db": {"port": 1}}],
        merge_strategy=strategy,
    )
    assert result.db == DBP(port=1, opts={"x": 1})


def test_IN1_instance_of_wrong_class_still_rejected():
    with pytest.raises(dataclass_args.ConfigurationError) as exc:
        build_config(AppP, [], base_configs={"db": DB()})
    assert "'db'" in str(exc.value)
    assert "DBP" in str(exc.value)


def test_IN1_stage6_still_rebuilds_instances_that_skip_the_normaliser():
    inst = DBP(host="k", opts={"x": [1]})
    builder = GenericConfigBuilder(AppP)

    result = builder.config_resolver._reconstruct_nested_fields(
        {"db": inst}, argparse.Namespace()
    )
    assert result["db"] == DBP(host="k", opts={"x": [1]})
    assert result["db"] is not inst
    assert result["db"].opts is not inst.opts
