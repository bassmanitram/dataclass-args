"""
Tests for cli_extend(): repeatable list options that accumulate.

Covers:
- accumulation across repeated options and within one option
- the omitted option keeps earlier layers and the dataclass default
- the CLI value replaces earlier layers as a whole
- element types, choices, nesting at any depth
- validation errors at builder construction
- interaction with cli_resolve, cli_list_merge and provenance
- unchanged behaviour of unannotated list fields
"""

import argparse
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

import pytest

from dataclass_args import (
    ConfigLayer,
    build_config,
    build_config_from_dict,
    cli_append,
    cli_choices,
    cli_exclude,
    cli_extend,
    cli_list_merge,
    cli_nested,
    cli_positional,
    cli_resolve,
    cli_short,
    combine_annotations,
    is_cli_extend,
)
from dataclass_args.builder import GenericConfigBuilder
from dataclass_args.exceptions import ConfigBuilderError

DEEP = "deep"
RULES = "rules"


@dataclass
class T:
    t: List[str] = combine_annotations(
        cli_short("t"), cli_extend(), default_factory=list
    )


@dataclass
class TDefault:
    t: List[str] = combine_annotations(
        cli_short("t"), cli_extend(), default_factory=lambda: ["d"]
    )


def help_text(config_class: type) -> str:
    """Render --help for a config class with whitespace normalised."""
    parser = argparse.ArgumentParser()
    GenericConfigBuilder(config_class).add_arguments(parser)
    return " ".join(parser.format_help().split())


class TestAccumulation:
    def test_extend_repeated_flags(self):
        assert build_config(T, args=["-t", "a", "-t", "b"]).t == ["a", "b"]

    def test_extend_single_flag_many_values(self):
        assert build_config(T, args=["-t", "a", "b"]).t == ["a", "b"]

    def test_extend_mixed(self):
        assert build_config(T, args=["-t", "a", "b", "-t", "c"]).t == ["a", "b", "c"]

    def test_extend_omitted_keeps_layer(self):
        config = build_config(T, args=[], base_configs=[{"t": ["x"]}])
        assert config.t == ["x"]

    def test_extend_cli_replaces_layer_whole(self):
        config = build_config(
            T, args=["-t", "a", "-t", "b"], base_configs=[{"t": ["x"]}]
        )
        assert config.t == ["a", "b"]

    def test_extend_omitted_uses_default(self):
        assert build_config(TDefault, args=[]).t == ["d"]

    def test_extend_never_appends_to_default(self):
        assert build_config(TDefault, args=["-t", "a"]).t == ["a"]

    def test_extend_does_not_mutate_the_default(self):
        build_config(TDefault, args=["-t", "a", "-t", "b"])
        assert build_config(TDefault, args=[]).t == ["d"]


class TestOptionalAndTypes:
    def test_extend_optional_omitted(self):
        @dataclass
        class Config:
            o: Optional[List[str]] = combine_annotations(cli_extend(), default=None)

        assert build_config(Config, args=[]).o is None

    def test_extend_optional_empty(self):
        @dataclass
        class Config:
            o: Optional[List[str]] = combine_annotations(cli_extend(), default=None)

        assert build_config(Config, args=["--o"]).o == []
        assert build_config(Config, args=["--o", "--o"]).o == []

    def test_extend_element_type(self):
        @dataclass
        class Config:
            n: List[int] = combine_annotations(
                cli_short("n"), cli_extend(), default_factory=list
            )

        config = build_config(Config, args=["-n", "1", "-n", "2", "3"])

        assert config.n == [1, 2, 3]
        assert all(type(v) is int for v in config.n)

    def test_extend_choices(self, capsys):
        @dataclass
        class Config:
            t: List[str] = combine_annotations(
                cli_short("t"),
                cli_extend(),
                cli_choices(["a", "b"]),
                default_factory=list,
            )

        assert build_config(Config, args=["-t", "a", "-t", "b"]).t == ["a", "b"]
        with pytest.raises(SystemExit) as exc_info:
            build_config(Config, args=["-t", "a", "-t", "c"])
        assert exc_info.value.code == 2
        assert "invalid choice: 'c'" in capsys.readouterr().err


class TestNested:
    def test_extend_nested(self):
        @dataclass
        class Db:
            hosts: List[str] = combine_annotations(cli_extend(), default_factory=list)

        @dataclass
        class Config:
            db: Db = cli_nested(prefix="db", default_factory=Db)

        config = build_config(Config, args=["--db-hosts", "h1", "--db-hosts", "h2"])

        assert config.db.hosts == ["h1", "h2"]

    def test_extend_nested_depth_2(self):
        @dataclass
        class Inner:
            hosts: List[str] = combine_annotations(cli_extend(), default_factory=list)

        @dataclass
        class Mid:
            inner: Inner = cli_nested(prefix="inner", default_factory=Inner)

        @dataclass
        class Config:
            mid: Mid = cli_nested(prefix="mid", default_factory=Mid)

        config = build_config(
            Config, args=["--mid-inner-hosts", "h1", "--mid-inner-hosts", "h2"]
        )

        assert config.mid.inner.hosts == ["h1", "h2"]

    def test_extend_nested_invalid_at_depth_raises(self):
        @dataclass
        class Inner:
            name: str = combine_annotations(cli_extend(), default="x")

        @dataclass
        class Mid:
            inner: Inner = cli_nested(prefix="inner", default_factory=Inner)

        @dataclass
        class Config:
            mid: Mid = cli_nested(prefix="mid", default_factory=Mid)

        with pytest.raises(ConfigBuilderError, match="name"):
            GenericConfigBuilder(Config)


class TestValidation:
    def test_extend_on_scalar_raises(self):
        @dataclass
        class Config:
            name: str = combine_annotations(cli_extend(), default="x")

        with pytest.raises(ConfigBuilderError, match="'name'"):
            GenericConfigBuilder(Config)

    def test_extend_with_append_raises(self):
        @dataclass
        class Config:
            items: List[str] = combine_annotations(
                cli_extend(), cli_append(), default_factory=list
            )

        with pytest.raises(ConfigBuilderError, match="'items'.*cli_append"):
            GenericConfigBuilder(Config)

    def test_extend_positional_raises(self):
        @dataclass
        class Config:
            items: List[str] = combine_annotations(
                cli_extend(), cli_positional(nargs="*"), default_factory=list
            )

        with pytest.raises(ConfigBuilderError, match="'items'.*cli_positional"):
            GenericConfigBuilder(Config)

    def test_extend_excluded_raises(self):
        @dataclass
        class Config:
            items: List[str] = combine_annotations(
                cli_extend(), cli_exclude(), default_factory=list
            )

        with pytest.raises(ConfigBuilderError, match="'items'.*cli_exclude"):
            GenericConfigBuilder(Config)

    def test_extend_list_of_lists_raises(self):
        @dataclass
        class Config:
            groups: List[List[str]] = combine_annotations(
                cli_extend(), default_factory=list
            )

        with pytest.raises(ConfigBuilderError, match="cli_append"):
            GenericConfigBuilder(Config)

    def test_extend_list_of_dicts_raises(self):
        @dataclass
        class Config:
            rows: List[dict] = combine_annotations(cli_extend(), default_factory=list)

        with pytest.raises(ConfigBuilderError, match="'rows'"):
            GenericConfigBuilder(Config)

    def test_extend_metadata_and_accessor(self):
        builder = GenericConfigBuilder(T)

        assert T.__dataclass_fields__["t"].metadata["cli_extend"] is True
        assert is_cli_extend(builder._config_fields["t"]) is True


class TestInteractions:
    def test_extend_with_resolve(self):
        received: List[Any] = []

        def resolver(value: Any) -> Any:
            received.append(value)
            return value

        @dataclass
        class Config:
            t: List[Any] = combine_annotations(
                cli_short("t"),
                cli_resolve(resolver=resolver),
                cli_extend(),
                default_factory=list,
            )

        build_config(Config, args=["-t", "a", "-t", "b"])

        assert received == [["a", "b"]]

    def test_extend_with_list_merge(self):
        @dataclass
        class Config:
            t: List[str] = combine_annotations(
                cli_short("t"),
                cli_extend(),
                cli_list_merge("append_unique"),
                default_factory=list,
            )

        layers = [
            ConfigLayer({"t": ["x", "y"]}, list_merge=RULES),
            ConfigLayer({"t": ["y", "z"]}, list_merge=RULES),
        ]

        without_cli = build_config(
            Config, args=[], base_configs=layers, merge_strategy=DEEP
        )
        with_cli = build_config(
            Config,
            args=["-t", "a", "-t", "b"],
            base_configs=layers,
            merge_strategy=DEEP,
        )

        assert without_cli.t == ["x", "y", "z"]
        assert with_cli.t == ["a", "b"]

    def test_extend_provenance(self):
        config, provenance = build_config(
            T,
            args=["-t", "a", "-t", "b"],
            base_configs=[ConfigLayer({"t": ["x"]}, name="file")],
            merge_strategy=DEEP,
            return_provenance=True,
        )

        assert config.t == ["a", "b"]
        assert provenance.source("t") == "cli"
        assert provenance.entries("t")[-1].value == ["a", "b"]

    def test_extend_from_dict_unaffected(self):
        assert build_config_from_dict(T, {"t": ["a"]}).t == ["a"]


class TestUnchangedDefaults:
    def test_plain_list_repeat_unchanged(self):
        @dataclass
        class Config:
            t: List[str] = combine_annotations(cli_short("t"), default_factory=list)

        assert build_config(Config, args=["-t", "a", "-t", "b"]).t == ["b"]

    def test_extend_help_text(self):
        @dataclass
        class Config:
            t: List[str] = combine_annotations(cli_extend(), default_factory=list)
            o: Optional[List[str]] = combine_annotations(cli_extend(), default=None)
            plain: List[str] = field(default_factory=list)
            plain_o: Optional[List[str]] = None

        text = help_text(Config)

        assert "(specify one or more values; repeatable)" in text
        assert "(specify zero or more values; repeatable)" in text
        assert text.count("repeatable") == 2
        assert "(specify one or more values)" in text
        assert "(specify zero or more values)" in text


def extended(annotation: Any, **kwargs: Any) -> type:
    """Build a config class with one `p` field using cli_extend."""
    attrs = {
        "__annotations__": {"p": annotation},
        "p": combine_annotations(cli_extend(), **kwargs),
    }
    return dataclass(type("ExtendConfig", (), attrs))


def plain(annotation: Any, **kwargs: Any) -> type:
    """Build a config class with one `p` field and no cli_extend."""
    attrs = {"__annotations__": {"p": annotation}, "p": field(**kwargs)}
    return dataclass(type("PlainConfig", (), attrs))


UNION_CASES = [
    pytest.param(List[Union[str, Path]], ["a", "b"], id="union_str_path"),
    pytest.param(List[Optional[str]], ["a", "b"], id="list_of_optional"),
    pytest.param(List[Union[int, float]], ["1", "2.5"], id="union_int_float"),
    pytest.param(
        List[Optional[Union[str, Path]]], ["a", "b"], id="optional_union_str_path"
    ),
]


class TestScalarUnionElements:
    @pytest.mark.parametrize("annotation, tokens", UNION_CASES)
    def test_U1_extend_equals_plain(self, annotation, tokens):
        factory = {"default_factory": list}
        expected = build_config(plain(annotation, **factory), args=["--p", *tokens]).p

        config = build_config(
            extended(annotation, **factory),
            args=[arg for token in tokens for arg in ("--p", token)],
        )

        assert config.p == expected
        assert [type(v) for v in config.p] == [type(v) for v in expected]

    def test_U1_pep604_union(self):
        annotation = list[str | Path]
        factory = {"default_factory": list}
        expected = build_config(plain(annotation, **factory), args=["--p", "a", "b"]).p

        config = build_config(
            extended(annotation, **factory), args=["--p", "a", "--p", "b"]
        )

        assert config.p == expected == ["a", "b"]

    def test_U2_list_of_optional(self):
        config = build_config(
            extended(List[Optional[str]], default_factory=list),
            args=["--p", "a", "--p", "b"],
        )

        assert config.p == ["a", "b"]

    def test_U3_optional_list_of_union_omitted(self):
        config_class = extended(Optional[List[Union[str, Path]]], default=None)

        assert build_config(config_class, args=[]).p is None
        assert build_config(config_class, args=["--p", "a", "--p", "b"]).p == [
            "a",
            "b",
        ]

    def test_U4_union_int_float(self):
        factory = {"default_factory": list}
        expected = build_config(
            plain(List[Union[int, float]], **factory), args=["--p", "1", "2.5"]
        ).p

        config = build_config(
            extended(List[Union[int, float]], **factory),
            args=["--p", "1", "--p", "2.5"],
        )

        assert config.p == expected

    @pytest.mark.parametrize("annotation, tokens", UNION_CASES)
    def test_U7_plain_fields_unchanged(self, annotation, tokens):
        config = build_config(
            plain(annotation, default_factory=list), args=["--p", *tokens]
        )

        assert config.p == tokens
        assert all(type(v) is str for v in config.p)

    def test_union_extend_nested(self):
        @dataclass
        class Inner:
            p: List[Union[str, Path]] = combine_annotations(
                cli_extend(), default_factory=list
            )

        @dataclass
        class Config:
            inner: Inner = cli_nested(prefix="inner", default_factory=Inner)

        config = build_config(Config, args=["--inner-p", "a", "--inner-p", "b"])

        assert config.inner.p == ["a", "b"]


class TestNonScalarElements:
    def test_U5_dict_elements_named(self):
        with pytest.raises(ConfigBuilderError) as exc_info:
            GenericConfigBuilder(extended(List[Dict[str, Any]], default_factory=list))

        message = str(exc_info.value)
        assert "'p'" in message
        assert "Dict[str, Any]" in message
        assert "cli_append" not in message

    def test_U6_list_elements_suggest_append(self):
        with pytest.raises(ConfigBuilderError) as exc_info:
            GenericConfigBuilder(extended(List[List[str]], default_factory=list))

        message = str(exc_info.value)
        assert "List[str]" in message
        assert "cli_append(nargs=...)" in message

    def test_union_with_container_member_rejected(self):
        with pytest.raises(
            ConfigBuilderError, match=r"scalar list elements.*List\[str\]"
        ):
            GenericConfigBuilder(
                extended(List[Union[str, List[str]]], default_factory=list)
            )

    def test_tuple_and_dataclass_elements_rejected(self):
        @dataclass
        class Row:
            name: str = ""

        for annotation in (List[Tuple[str, str]], List[Row], List[Optional[Row]]):
            with pytest.raises(ConfigBuilderError) as exc_info:
                GenericConfigBuilder(extended(annotation, default_factory=list))
            assert "cli_append" not in str(exc_info.value)

    def test_container_abc_and_bare_container_elements_rejected(self):
        from typing import Sequence

        for annotation in (List[Sequence[str]], List[set], List[frozenset]):
            with pytest.raises(ConfigBuilderError, match="scalar list elements"):
                GenericConfigBuilder(extended(annotation, default_factory=list))
