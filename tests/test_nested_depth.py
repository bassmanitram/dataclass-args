"""
Tests for cli_nested at any depth (NN1-NN4): recursive flattening, composed
prefixes, recursive reconstruction, and effective values at depth.
"""

import argparse
import json
from dataclasses import MISSING, dataclass, field
from typing import Any, Dict

import pytest

from dataclass_args import (
    ConfigBuilderError,
    ConfigurationError,
    build_config,
    build_config_from_dict,
    cli_nested,
    cli_positional,
    cli_short,
    combine_annotations,
)
from dataclass_args.builder import GenericConfigBuilder
from dataclass_args.nested_processor import NestedFieldProcessor


@dataclass
class Inner:
    v: int = 1
    opts: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Mid:
    w: int = 2
    inner: Inner = cli_nested(default_factory=Inner)


@dataclass
class Top:
    name: str = "t"
    mid: Mid = cli_nested(default_factory=Mid)


@dataclass
class Leaf:
    z: int = 0


@dataclass
class L1:
    y: int = 0
    leaf: Leaf = cli_nested(default_factory=Leaf)


@dataclass
class L2:
    x: int = 0
    l1: L1 = cli_nested(default_factory=L1)


@dataclass
class L3:
    top: int = 0
    l2: L2 = cli_nested(default_factory=L2)


def _parser_flags(config_class):
    parser = argparse.ArgumentParser()
    GenericConfigBuilder(config_class).add_arguments(parser)
    return {opt for action in parser._actions for opt in action.option_strings}


# ---------------------------------------------------------------------------
# NN1-NN4: base behaviour at depth
# ---------------------------------------------------------------------------


def test_NN1_base_configs_two_levels():
    result = build_config(Top, [], base_configs={"mid": {"inner": {"v": 5}}})
    assert result.mid == Mid(w=2, inner=Inner(v=5))
    assert isinstance(result.mid.inner, Inner)


def test_NN2_from_dict_two_levels():
    result = build_config_from_dict(Top, {"mid": {"inner": {"v": 5}}})
    assert result.mid == Mid(w=2, inner=Inner(v=5))
    assert isinstance(result.mid.inner, Inner)


def test_NN3_parser_flags():
    flags = _parser_flags(Top)
    assert "--mid-inner-v" in flags
    assert "--mid-inner-opts" in flags
    assert "--mid-w" in flags
    assert "--mid-inner" not in flags


def test_NN4_cli_leaf_at_depth():
    result = build_config(Top, ["--mid-inner-v", "7"])
    assert result.mid.inner == Inner(v=7)
    assert result.mid.w == 2


def test_NN_cli_over_base_keeps_siblings():
    result = build_config(
        Top,
        ["--mid-inner-v", "7"],
        base_configs={"mid": {"w": 5, "inner": {"v": 5}}},
    )
    assert result.mid == Mid(w=5, inner=Inner(v=7))


def test_NN_three_levels():
    result = build_config(
        L3,
        ["--l2-l1-leaf-z", "9"],
        base_configs={"l2": {"x": 1, "l1": {"y": 2, "leaf": {"z": 3}}}},
    )
    assert result.l2 == L2(x=1, l1=L1(y=2, leaf=Leaf(z=9)))
    assert isinstance(result.l2.l1.leaf, Leaf)


def test_NN_three_levels_cli_only_and_defaults():
    assert build_config(L3, ["--l2-l1-y", "4"]).l2.l1 == L1(y=4, leaf=Leaf())
    assert build_config(L3, []) == L3()


def test_NN_config_file_two_levels(tmp_path):
    config_file = tmp_path / "c.yaml"
    config_file.write_text("mid:\n  inner:\n    v: 9\n")

    result = build_config(Top, ["--config", str(config_file)])
    assert result.mid.inner == Inner(v=9)


def test_NN_instance_base_at_depth_not_mutated():
    inst = Mid(w=5, inner=Inner(v=5))
    result = build_config(Top, ["--mid-inner-v", "7"], base_configs={"mid": inst})
    assert result.mid.inner == Inner(v=7)
    assert result.mid.w == 5
    assert inst.inner.v == 5


def test_NN_instance_base_dict_field_not_aliased():
    inst = Mid(inner=Inner(opts={"x": [1]}))
    result = build_config(Top, [], base_configs={"mid": inst})
    result.mid.inner.opts["x"].append(2)
    assert inst.inner.opts == {"x": [1]}


def test_NN_instance_with_non_init_field_is_rebuilt():
    @dataclass
    class WithDerived:
        a: int = 1
        derived: int = field(init=False, default=0)

        def __post_init__(self) -> None:
            self.derived = self.a * 2

    @dataclass
    class Holder:
        wd: WithDerived = cli_nested(default_factory=WithDerived)

    result = build_config(Holder, ["--wd-a", "4"], base_configs={"wd": WithDerived()})
    assert result.wd.a == 4
    assert result.wd.derived == 8


# ---------------------------------------------------------------------------
# Prefix composition and short options
# ---------------------------------------------------------------------------


def _make_two_levels(top_prefix, inner_prefix):
    @dataclass
    class In:
        v: int = 1

    @dataclass
    class Md:
        inner: In = cli_nested(prefix=inner_prefix, default_factory=In)

    @dataclass
    class Tp:
        mid: Md = cli_nested(prefix=top_prefix, default_factory=Md)

    return Tp


@pytest.mark.parametrize(
    "top_prefix, inner_prefix, flag",
    [
        (None, None, "--mid-inner-v"),
        ("m", "", "--m-v"),
        ("", None, "--inner-v"),
        ("", "", "--v"),
        ("m", "n", "--m-n-v"),
        ("m-", None, "--m-inner-v"),
    ],
)
def test_NN_prefix_composition(top_prefix, inner_prefix, flag):
    config_class = _make_two_levels(top_prefix, inner_prefix)
    assert flag in _parser_flags(config_class)

    result = build_config(config_class, [flag, "7"])
    assert result.mid.inner.v == 7


def _make_short(inner_prefix, mid_prefix=""):
    @dataclass
    class Lf:
        z: int = combine_annotations(cli_short("z"), default=0)

    @dataclass
    class Md:
        leaf: Lf = cli_nested(prefix=inner_prefix, default_factory=Lf)

    @dataclass
    class Tp:
        mid: Md = cli_nested(prefix=mid_prefix, default_factory=Md)

    return Tp


def test_NN_short_option_at_depth_all_empty_prefix():
    config_class = _make_short("")
    assert "-z" in _parser_flags(config_class)
    assert build_config(config_class, ["-z", "3"]).mid.leaf.z == 3


def test_NN_short_option_ignored_with_prefix():
    assert "-z" not in _parser_flags(_make_short("lf"))
    assert "-z" not in _parser_flags(_make_short("", mid_prefix="md"))


def test_NN_short_option_collision_at_depth():
    @dataclass
    class Lf:
        z: int = combine_annotations(cli_short("z"), default=0)

    @dataclass
    class Md:
        leaf: Lf = cli_nested(prefix="", default_factory=Lf)

    @dataclass
    class Tp:
        other: int = combine_annotations(cli_short("z"), default=0)
        mid: Md = cli_nested(prefix="", default_factory=Md)

    with pytest.raises(ConfigBuilderError) as exc:
        GenericConfigBuilder(Tp)
    assert "-z" in str(exc.value)
    assert "mid.leaf.z" in str(exc.value)


# ---------------------------------------------------------------------------
# Collisions, cycles, positional
# ---------------------------------------------------------------------------


def test_NN_collision_across_levels():
    @dataclass
    class In:
        v: int = 1

    @dataclass
    class Md:
        inner: In = cli_nested(prefix="", default_factory=In)

    @dataclass
    class Tp:
        v: int = 0
        mid: Md = cli_nested(prefix="", default_factory=Md)

    with pytest.raises(ConfigBuilderError) as exc:
        GenericConfigBuilder(Tp)
    assert "mid.inner.v" in str(exc.value)


def test_NN_override_name_collision_at_depth():
    @dataclass
    class In:
        opts: Dict[str, Any] = field(default_factory=dict)

    @dataclass
    class Md:
        inner: In = cli_nested(prefix="", default_factory=In)

    @dataclass
    class Tp:
        other: Dict[str, Any] = field(default_factory=dict)
        mid: Md = cli_nested(prefix="", default_factory=Md)

    with pytest.raises(ConfigBuilderError) as exc:
        GenericConfigBuilder(Tp)
    assert "Override name collision" in str(exc.value)
    assert "mid.inner.opts" in str(exc.value)


@dataclass
class CycleA:
    b: "CycleB" = cli_nested(default=None)


@dataclass
class CycleB:
    a: CycleA = cli_nested(default=None)


@dataclass
class SelfRef:
    me: "SelfRef" = cli_nested(default=None)


def test_NN_cycle_detected():
    with pytest.raises(ConfigBuilderError) as exc:
        GenericConfigBuilder(CycleA)
    assert "CycleA.b -> CycleB.a -> CycleA" in str(exc.value)


def test_NN_self_reference_detected():
    with pytest.raises(ConfigBuilderError) as exc:
        GenericConfigBuilder(SelfRef)
    assert "SelfRef.me -> SelfRef" in str(exc.value)


def test_NN_same_class_twice_on_different_branches_is_not_a_cycle():
    @dataclass
    class Both:
        first: Inner = cli_nested(default_factory=Inner)
        second: Inner = cli_nested(default_factory=Inner)

    result = build_config(Both, ["--first-v", "3", "--second-v", "4"])
    assert (result.first.v, result.second.v) == (3, 4)


def test_NN_positional_at_depth_raises():
    @dataclass
    class In:
        src: str = combine_annotations(cli_positional(), default="")

    @dataclass
    class Md:
        inner: In = cli_nested(default_factory=In)

    @dataclass
    class Tp:
        mid: Md = cli_nested(default_factory=Md)

    builder = GenericConfigBuilder(Tp)
    with pytest.raises(ConfigBuilderError) as exc:
        builder.add_arguments(argparse.ArgumentParser())
    assert "mid.inner.src" in str(exc.value)


# ---------------------------------------------------------------------------
# Effective values at depth (spec-013 semantics, generalised)
# ---------------------------------------------------------------------------


def test_NN_dict_override_at_depth():
    assert "--mid-inner-o" in _parser_flags(Top)

    result = build_config(
        Top,
        ["--mid-inner-o", "y:2"],
        base_configs={"mid": {"inner": {"opts": {"x": 1}}}},
    )
    assert result.mid.inner.opts == {"x": 1, "y": 2}


def test_NN_dict_override_at_depth_appends_to_base_list():
    result = build_config(
        Top,
        ["--mid-inner-o", "items.+:1"],
        base_configs={"mid": {"inner": {"opts": {"items": [0]}}}},
    )
    assert result.mid.inner.opts == {"items": [0, 1]}


def test_NN_dict_override_at_depth_keeps_default():
    @dataclass
    class InD:
        opts: Dict[str, Any] = field(default_factory=lambda: {"x": 1})

    @dataclass
    class MdD:
        inner: InD = cli_nested(default_factory=InD)

    @dataclass
    class TpD:
        mid: MdD = cli_nested(default_factory=MdD)

    first = build_config(TpD, ["--mid-inner-o", "y:2"])
    assert first.mid.inner.opts == {"x": 1, "y": 2}
    assert build_config(TpD, []).mid.inner.opts == {"x": 1}


def test_NN_dict_override_at_depth_on_instance_base_does_not_mutate():
    inst = Mid(inner=Inner(opts={"x": 1}))
    result = build_config(Top, ["--mid-inner-o", "y:2"], base_configs={"mid": inst})
    assert result.mid.inner.opts == {"x": 1, "y": 2}
    assert inst.inner.opts == {"x": 1}


def test_NN_dict_cli_file_at_depth_merges(tmp_path):
    path = tmp_path / "f.json"
    path.write_text(json.dumps({"n": 1, "y": 2}))

    result = build_config(
        Top,
        ["--mid-inner-opts", str(path)],
        base_configs={"mid": {"inner": {"opts": {"x": 1}}}},
    )
    assert result.mid.inner.opts == {"x": 1, "n": 1, "y": 2}


def test_NN_dict_cli_file_then_override_at_depth(tmp_path):
    path = tmp_path / "f.json"
    path.write_text(json.dumps({"n": 1}))

    result = build_config(Top, ["--mid-inner-opts", str(path), "--mid-inner-o", "z:3"])
    assert result.mid.inner.opts == {"n": 1, "z": 3}


def test_NN_dict_cli_non_file_string_rejected_at_depth():
    with pytest.raises(ConfigurationError) as exc:
        build_config(Top, ["--mid-inner-opts", "plain"])
    assert "Invalid value 'plain' for dict field 'mid.inner.opts'" in str(exc.value)


def test_NN_dict_override_at_depth_on_non_dict_raises():
    with pytest.raises(ConfigurationError) as exc:
        build_config(
            Top,
            ["--mid-inner-o", "y:2"],
            base_configs={"mid": {"inner": {"opts": 5}}},
        )
    assert "mid.inner.opts" in str(exc.value)
    assert "not a dict" in str(exc.value)


def test_NN_layer_file_ref_at_depth(tmp_path):
    path = tmp_path / "o.yaml"
    path.write_text("x: 1\n")

    result = build_config(Top, [], base_configs={"mid": {"inner": {"opts": str(path)}}})
    assert result.mid.inner.opts == {"x": 1}


def test_NN_layer_value_walks_dicts_and_instances():
    path = ("mid", "inner", "opts")
    layer_value = NestedFieldProcessor._layer_value

    assert layer_value({"mid": {"inner": {"opts": {"a": 1}}}}, path) == {"a": 1}
    assert layer_value({"mid": Mid(inner=Inner(opts={"b": 2}))}, path) == {"b": 2}
    assert layer_value({"mid": {"inner": Inner(opts={"c": 3})}}, path) == {"c": 3}
    assert layer_value({}, path) is MISSING
    assert layer_value({"mid": None}, path) is MISSING
    assert layer_value({"mid": {"inner": 5}}, path) is MISSING
    assert layer_value({"mid": {"inner": {}}}, path) is MISSING
    assert layer_value({"mid": {"inner": {"opts": None}}}, path) is None


# ---------------------------------------------------------------------------
# Help text, errors, None
# ---------------------------------------------------------------------------


def test_NN_help_text_dotted_path():
    parser = argparse.ArgumentParser()
    GenericConfigBuilder(Top).add_arguments(parser)
    assert "mid.inner.v" in parser.format_help()


def test_NN_non_dict_at_depth_raises():
    with pytest.raises(ConfigurationError) as exc:
        build_config(Top, [], base_configs={"mid": {"inner": "x"}})
    assert "mid.inner" in str(exc.value)


def test_NN_non_dict_at_depth_from_dict_raises():
    with pytest.raises(ConfigurationError) as exc:
        build_config_from_dict(Top, {"mid": {"inner": 3}})
    assert "mid.inner" in str(exc.value)


def test_NN_stage6_safety_net_names_dotted_path():
    builder = GenericConfigBuilder(Top)
    with pytest.raises(ConfigurationError) as exc:
        builder.config_resolver._reconstruct_nested_fields(
            {"mid": {"inner": 3}}, argparse.Namespace()
        )
    assert "'mid.inner'" in str(exc.value)
    assert "Inner" in str(exc.value)


def test_NN_none_at_depth_gives_defaults():
    result = build_config(Top, [], base_configs={"mid": {"inner": None}})
    assert result.mid.inner == Inner()


def test_NN_none_at_depth_with_cli_value():
    result = build_config(
        Top, ["--mid-inner-v", "6"], base_configs={"mid": {"inner": None}}
    )
    assert result.mid.inner == Inner(v=6)


def test_NN_instance_creation_error_names_dotted_path():
    with pytest.raises(ConfigurationError) as exc:
        build_config(Top, [], base_configs={"mid": {"inner": {"nope": 1}}})
    assert "Failed to create nested dataclass Inner" in str(exc.value)
    assert "'mid.inner'" in str(exc.value)


def test_NN_cli_exclude_fields_survive_rebuild():
    from dataclass_args import cli_exclude

    @dataclass
    class In:
        v: int = 1
        secret: str = cli_exclude(default="s")

    @dataclass
    class Md:
        inner: In = cli_nested(default_factory=In)

    @dataclass
    class Tp:
        mid: Md = cli_nested(default_factory=Md)

    result = build_config(
        Tp, ["--mid-inner-v", "2"], base_configs={"mid": {"inner": {"secret": "k"}}}
    )
    assert result.mid.inner == In(v=2, secret="k")
