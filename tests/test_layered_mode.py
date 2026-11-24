"""
Tests for layered mode in build_config_from_dict (merge_strategy="deep"): the
whole config dict is one real base layer named "config" instead of being
injected into the argparse Namespace.

The equivalence test (CR section 9.1.3) builds a single config dict in both
modes and requires identical results for every field kind.
"""

import argparse
import json
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import pytest

from dataclass_args import (
    ConfigBuilderError,
    ConfigLayer,
    ConfigurationError,
    build_config,
    build_config_from_dict,
    cli_append,
    cli_exclude,
    cli_file_loadable,
    cli_list_merge,
    cli_nested,
    cli_positional,
    cli_resolve,
    combine_annotations,
)
from dataclass_args.builder import GenericConfigBuilder

SHALLOW = "shallow"
DEEP = "deep"


@dataclass
class DB:
    host: str = "h"
    opts: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Prebuilt:
    n: int = 1


def passthrough(value):
    return value


@dataclass
class Kinds:
    name: str = "x"
    maybe: Optional[str] = "m"
    flag: bool = False
    msg: str = combine_annotations(cli_file_loadable(), default="")
    payload: Dict[str, Any] = field(default_factory=dict)
    extras: Dict[str, Any] = field(default_factory=dict)
    sb: Any = combine_annotations(cli_resolve(resolver=passthrough), default=None)
    files: List[List[str]] = combine_annotations(
        cli_append(min_args=1, max_args=2), default_factory=list
    )
    pairs: List[List[str]] = combine_annotations(
        cli_append(nargs=2), default_factory=list
    )
    tags: List[str] = field(default_factory=list)
    db: DB = cli_nested(default_factory=DB)
    secret: str = cli_exclude(default="s")
    pos: str = combine_annotations(cli_positional(nargs="?"), default="p")
    api_key: str = "k0"


@pytest.fixture
def files(tmp_path):
    message = tmp_path / "m.txt"
    message.write_text("hello")
    extras = tmp_path / "extras.yaml"
    extras.write_text("k: 1\n")
    opts = tmp_path / "opts.json"
    opts.write_text(json.dumps({"x": 1}))
    return {"message": str(message), "extras": str(extras), "opts": str(opts)}


def _build(config_class, config, mode, **kwargs):
    try:
        return build_config_from_dict(
            config_class, config, merge_strategy=mode, **kwargs
        )
    except Exception as error:  # noqa: BLE001 - the error itself is compared
        return (type(error).__name__, str(error))


KINDS = {
    "scalar": lambda f: {"name": "a"},
    "optional_none": lambda f: {"maybe": None},
    "bool_true": lambda f: {"flag": True},
    "bool_false": lambda f: {"flag": False},
    "file_loadable": lambda f: {"msg": "@" + f["message"]},
    "dict_as_dict": lambda f: {"payload": {"a": 1, "n": {"b": 2}}},
    "dict_as_file": lambda f: {"extras": f["extras"]},
    "cli_resolve_dict": lambda f: {"sb": {"a": 1}},
    "cli_resolve_prebuilt": lambda f: {"sb": Prebuilt(3)},
    "cli_append": lambda f: {"files": [["a", "b"], ["c"]]},
    "cli_append_nargs": lambda f: {"pairs": [["a", "b"]]},
    "cli_append_too_many": lambda f: {"files": [["a", "b", "c"]]},
    "cli_append_too_few": lambda f: {"pairs": [["only"]]},
    "list": lambda f: {"tags": ["a", "b"]},
    "nested_as_dict": lambda f: {"db": {"host": "z", "opts": {"x": 1}}},
    "nested_dict_field_file": lambda f: {"db": {"opts": f["opts"]}},
    "nested_as_instance": lambda f: {"db": DB("q", {"y": 2})},
    "nested_none": lambda f: {"db": None},
    "cli_exclude": lambda f: {"secret": "k"},
    "cli_positional": lambda f: {"pos": "zz"},
    "hyphenated_key": lambda f: {"api-key": "hh"},
    "empty": lambda f: {},
    "everything": lambda f: {
        "name": "a",
        "flag": True,
        "tags": ["t"],
        "payload": {"p": 1},
        "files": [["f"]],
        "db": {"host": "z"},
        "secret": "k",
        "pos": "zz",
        "api-key": "hh",
    },
}


@pytest.mark.parametrize("kind", sorted(KINDS))
def test_equivalence_single_config_dict_in_both_modes(kind, files):
    config = KINDS[kind](files)
    shallow_result = _build(Kinds, config, SHALLOW)
    deep_result = _build(Kinds, config, DEEP)
    assert shallow_result == deep_result


def test_equivalence_errors_are_real_errors_in_both_modes():
    shallow_result = _build(Kinds, {"files": [["a", "b", "c"]]}, SHALLOW)
    assert shallow_result[0] == "ConfigurationError"
    assert "Expected at most 2" in shallow_result[1]
    assert _build(Kinds, {"files": [["a", "b", "c"]]}, DEEP) == shallow_result


def test_equivalence_results_are_the_expected_values(files):
    result = _build(Kinds, {"files": [["a"]], "pos": "zz", "api-key": "hh"}, DEEP)
    assert result.files == [["a"]]
    assert result.pos == "zz"
    assert result.api_key == "hh"
    assert _build(Kinds, {"msg": "@" + files["message"]}, DEEP).msg == "hello"
    assert _build(Kinds, {"extras": files["extras"]}, DEEP).extras == {"k": 1}


# ---------------------------------------------------------------------------
# Layered-mode behaviour
# ---------------------------------------------------------------------------


def test_deep_mode_config_dict_is_the_last_base_layer():
    result = build_config_from_dict(
        Kinds,
        {"payload": {"b": 2}},
        base_configs=[{"payload": {"a": 1}}],
        merge_strategy=DEEP,
    )
    assert result.payload == {"a": 1, "b": 2}


def test_deep_mode_config_wins_over_base_configs():
    result = build_config_from_dict(
        Kinds,
        {"name": "config"},
        base_configs=[{"name": "base"}],
        merge_strategy=DEEP,
    )
    assert result.name == "config"


def test_deep_mode_explicit_none_clears_base_value():
    result = build_config_from_dict(
        Kinds, {"maybe": None}, base_configs={"maybe": "b"}, merge_strategy=DEEP
    )
    assert result.maybe is None


def test_deep_mode_does_not_let_argparse_defaults_override_layers():
    result = build_config_from_dict(
        Kinds,
        {"name": "n"},
        base_configs={"files": [["x"]], "pos": "base-pos", "pairs": [["a", "b"]]},
        merge_strategy=DEEP,
    )
    assert result.files == [["x"]]
    assert result.pos == "base-pos"
    assert result.pairs == [["a", "b"]]


def test_deep_mode_namespace_is_not_used_for_config_values(monkeypatch):
    seen = {}
    original = GenericConfigBuilder.build_config

    def spy(
        self,
        args,
        base_config_name=None,
        base_configs=None,
        merge_strategy="shallow",
        return_provenance=False,
    ):
        seen["args"] = dict(vars(args))
        return original(
            self,
            args,
            base_config_name,
            base_configs,
            merge_strategy,
            return_provenance,
        )

    monkeypatch.setattr(GenericConfigBuilder, "build_config", spy)
    build_config_from_dict(Kinds, {"name": "n", "tags": ["a"]}, merge_strategy=DEEP)

    assert all(value is None for value in seen["args"].values())


def test_shallow_mode_keeps_the_legacy_namespace_route(monkeypatch):
    seen = {}
    original = GenericConfigBuilder.build_config

    def spy(
        self,
        args,
        base_config_name=None,
        base_configs=None,
        merge_strategy="shallow",
        return_provenance=False,
    ):
        seen["name"] = getattr(args, "name", None)
        return original(
            self,
            args,
            base_config_name,
            base_configs,
            merge_strategy,
            return_provenance,
        )

    monkeypatch.setattr(GenericConfigBuilder, "build_config", spy)
    build_config_from_dict(Kinds, {"name": "n"}, merge_strategy=SHALLOW)

    assert seen["name"] == "n"


def test_deep_mode_caller_config_is_not_mutated():
    config = {"payload": {"a": [1]}, "db": {"opts": {"x": [1]}}}
    result = build_config_from_dict(Kinds, config, merge_strategy=DEEP)
    result.payload["a"].append(2)
    result.db.opts["x"].append(2)
    assert config == {"payload": {"a": [1]}, "db": {"opts": {"x": [1]}}}


def test_deep_mode_config_layer_errors_are_labelled_config():
    with pytest.raises(ConfigurationError) as exc:
        build_config_from_dict(Kinds, {"extras": "missing.yaml"}, merge_strategy=DEEP)
    assert "layer 'config'" in str(exc.value)


def test_deep_mode_nested_error_at_depth_is_labelled_config():
    with pytest.raises(ConfigurationError) as exc:
        build_config_from_dict(
            Kinds, {"db": {"opts": "missing.yaml"}}, merge_strategy=DEEP
        )
    assert "'db.opts'" in str(exc.value)
    assert "layer 'config'" in str(exc.value)


def test_deep_mode_both_spellings_still_rejected():
    with pytest.raises(ConfigurationError) as exc:
        build_config_from_dict(
            Kinds, {"api-key": "a", "api_key": "b"}, merge_strategy=DEEP
        )
    assert "Layer 'config'" in str(exc.value)


def test_deep_mode_non_dict_config_still_raises_type_error():
    with pytest.raises(TypeError):
        build_config_from_dict(Kinds, ["not", "a", "dict"], merge_strategy=DEEP)


def test_deep_mode_nested_instance_in_config_combines_with_dict_base():
    result = build_config_from_dict(
        Kinds,
        {"db": DB(host="inst")},
        base_configs={"db": {"opts": {"x": 1}}},
        merge_strategy=DEEP,
    )
    # the instance is its field dict, so its empty opts deep-merge onto the base opts
    assert result.db == DB(host="inst", opts={"x": 1})


def test_deep_mode_works_with_list_rules_on_nested_fields():
    @dataclass
    class Inner:
        plugins: List[str] = combine_annotations(
            cli_list_merge("append"), default_factory=list
        )

    @dataclass
    class Outer:
        inner: Inner = cli_nested(default_factory=Inner)

    result = build_config_from_dict(
        Outer,
        {"inner": {"plugins": ["b"]}},
        base_configs=[{"inner": {"plugins": ["a"]}}],
        merge_strategy=DEEP,
        config_list_merge="rules",
    )
    assert result.inner.plugins == ["a", "b"]


# ---------------------------------------------------------------------------
# config_list_merge validation
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("bad", ["Rules", "append", "", None, True])
def test_invalid_config_list_merge_raises(bad):
    with pytest.raises(ConfigBuilderError) as exc:
        build_config_from_dict(Kinds, {}, merge_strategy=DEEP, config_list_merge=bad)
    assert "config_list_merge must be 'replace' or 'rules'" in str(exc.value)


def test_config_list_merge_rules_requires_deep_before_any_work():
    with pytest.raises(ConfigBuilderError) as exc:
        build_config_from_dict(
            Kinds,
            {},
            base_configs="/nonexistent/never/loaded.yaml",
            config_list_merge="rules",
        )
    assert "requires merge_strategy='deep'" in str(exc.value)


def test_invalid_merge_strategy_wins_over_config_list_merge():
    with pytest.raises(ConfigBuilderError) as exc:
        build_config_from_dict(
            Kinds, {}, merge_strategy="nope", config_list_merge="bogus"
        )
    assert "merge_strategy must be" in str(exc.value)


def test_config_list_merge_replace_is_accepted_in_shallow_mode():
    result = build_config_from_dict(
        Kinds, {"tags": ["a"]}, merge_strategy=SHALLOW, config_list_merge="replace"
    )
    assert result.tags == ["a"]


def test_config_list_merge_precedes_merge_strategy_in_the_signature():
    import inspect

    names = list(inspect.signature(build_config_from_dict).parameters)
    assert names[-3:] == ["config_list_merge", "merge_strategy", "return_provenance"]


def test_base_configs_may_hold_config_layers_in_layered_mode():
    result = build_config_from_dict(
        Kinds,
        {"payload": {"c": 3}},
        base_configs=[ConfigLayer({"payload": {"a": 1}}, name="defaults")],
        merge_strategy=DEEP,
    )
    assert result.payload == {"a": 1, "c": 3}


def test_build_config_with_cli_values_is_unaffected_by_layered_mode():
    result = build_config(
        Kinds,
        ["--tags", "cli"],
        base_configs=[{"tags": ["base"]}],
        merge_strategy=DEEP,
    )
    assert result.tags == ["cli"]


def test_generic_builder_optional_positional_has_no_argparse_default():
    builder = GenericConfigBuilder(Kinds)
    parser = argparse.ArgumentParser()
    builder.add_arguments(parser)
    assert getattr(parser.parse_args([]), "pos", None) is None

    # the dataclass default still applies when nothing is given anywhere
    assert build_config_from_dict(Kinds, {}, merge_strategy=DEEP).pos == "p"
    assert build_config_from_dict(Kinds, {}, merge_strategy=SHALLOW).pos == "p"
    assert build_config(Kinds, []).pos == "p"
