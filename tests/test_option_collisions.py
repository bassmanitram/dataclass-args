"""
Tests for option-string collision detection (OV1-OV4) and the negative-flag
help text (BF1).
"""

import argparse
from dataclasses import dataclass, field
from typing import Any, Dict, List

import pytest

from dataclass_args import (
    ConfigBuilderError,
    build_config,
    build_config_from_cli,
    cli_append,
    cli_help,
    cli_nested,
    cli_override_name,
    cli_positional,
    cli_short,
    combine_annotations,
)
from dataclass_args.builder import GenericConfigBuilder
from dataclass_args.formatter import RangeAppendHelpFormatter
from dataclass_args.option_collisions import plan_option_strings


def make_parser(config_class, base_config_name="config", **parser_kwargs):
    parser = argparse.ArgumentParser(**parser_kwargs)
    GenericConfigBuilder(config_class).add_arguments(parser, base_config_name)
    return parser


@dataclass
class OV1:
    d: Dict[str, Any] = field(default_factory=dict)


@dataclass
class OV2:
    mc: str = "x"
    model_config: Dict[str, Any] = field(default_factory=dict)


@dataclass
class OV3:
    config: Dict[str, Any] = field(default_factory=dict)


@dataclass
class OV4:
    host: str = cli_short("h", default="x")


def error_text(config_class, **kwargs):
    with pytest.raises(ConfigBuilderError) as exc:
        make_parser(config_class, **kwargs)
    return str(exc.value)


# ---------------------------------------------------------------------------
# OV1-OV4
# ---------------------------------------------------------------------------


def test_OV1_dict_override_collides_with_field_option():
    text = error_text(OV1)
    assert "'--d'" in text
    assert "field 'd' (--d)" in text
    assert "dict override of 'd' (--d)" in text
    assert 'cli_override_name("...")' in text


def test_OV2_dict_override_collides_with_another_field():
    text = error_text(OV2)
    assert "'--mc'" in text
    assert "field 'mc' (--mc)" in text
    assert "dict override of 'model_config' (--mc)" in text
    assert "cli_override_name" in text


def test_OV3_field_collides_with_the_config_file_option():
    text = error_text(OV3)
    assert "'--config'" in text
    assert "field 'config' (--config)" in text
    assert "config-file option (--config)" in text
    assert "rename the field, or pass a different base_config_name" in text


def test_OV4_short_option_collides_with_help():
    text = error_text(OV4)
    assert "'-h'" in text
    assert "field 'host' (-h)" in text
    assert "argparse help (-h/--help)" in text
    assert "-h is reserved for --help" in text


@pytest.mark.parametrize("config_class", [OV1, OV2, OV3, OV4])
def test_collisions_surface_through_every_public_entry_point(config_class):
    with pytest.raises(ConfigBuilderError):
        build_config(config_class, [])
    with pytest.raises(ConfigBuilderError):
        build_config_from_cli(config_class, [])


def test_nothing_is_registered_when_a_collision_is_found():
    parser = argparse.ArgumentParser()
    registered_before = set(parser._option_string_actions)
    with pytest.raises(ConfigBuilderError):
        GenericConfigBuilder(OV2).add_arguments(parser)
    assert set(parser._option_string_actions) == registered_before


def test_every_collision_is_reported_together():
    @dataclass
    class Many:
        d: Dict[str, Any] = field(default_factory=dict)
        host: str = cli_short("h", default="x")

    text = error_text(Many)
    assert "'--d'" in text
    assert "'-h'" in text


def test_help_long_option_collision():
    @dataclass
    class Helpful:
        help: str = "x"

    text = error_text(Helpful)
    assert "'--help'" in text
    assert "field 'help' (--help)" in text


# ---------------------------------------------------------------------------
# Depth, negative flags, bases
# ---------------------------------------------------------------------------


def test_nested_option_collides_with_a_top_level_dict_override():
    @dataclass
    class Inner:
        mc: str = "x"

    @dataclass
    class Outer:
        model_config: Dict[str, Any] = field(default_factory=dict)
        inner: Inner = cli_nested(prefix="", default_factory=Inner)

    text = error_text(Outer)
    assert "'--mc'" in text
    assert "field 'inner.mc' (--mc)" in text
    assert "dict override of 'model_config' (--mc)" in text


def test_negative_flag_collides_with_a_field_option():
    @dataclass
    class Neg:
        no_debug: str = "x"
        debug: bool = False

    text = error_text(Neg)
    assert "'--no-debug'" in text
    assert "field 'no_debug' (--no-debug)" in text
    assert "negative flag of 'debug' (--no-debug)" in text
    assert "rename one of the fields" in text


def test_nested_dict_override_collision_at_depth():
    @dataclass
    class Inner:
        model_config: Dict[str, Any] = field(default_factory=dict)

    @dataclass
    class Outer:
        inner: Inner = cli_nested(prefix="", default_factory=Inner)
        mc: str = "x"

    text = error_text(Outer)
    assert "'--mc'" in text
    assert "dict override of 'inner.model_config' (--mc)" in text


def test_add_help_false_allows_short_h():
    parser = make_parser(OV4, add_help=False)
    assert parser.parse_args(["-h", "value"]).host == "value"


def test_config_field_is_fine_with_a_different_base_config_name():
    result = build_config_from_cli(OV3, [], base_config_name="settings")
    assert result.config == {}
    parser = make_parser(OV3, base_config_name="settings")
    assert "--settings" in parser._option_string_actions
    assert "--config" in parser._option_string_actions


def test_field_named_like_the_base_config_name_collides():
    @dataclass
    class Settings:
        settings: str = "x"

    text = error_text(Settings, base_config_name="settings")
    assert "'--settings'" in text
    assert "config-file option (--settings)" in text
    # the same dataclass is fine with the default config-file option name
    assert build_config(Settings, []).settings == "x"


# ---------------------------------------------------------------------------
# Fixes and non-colliding classes
# ---------------------------------------------------------------------------


def test_override_name_fix_for_ov1_works():
    @dataclass
    class Fixed:
        d: Dict[str, Any] = combine_annotations(
            cli_override_name("dd"), default_factory=dict
        )

    result = build_config(Fixed, ["--dd", "k:v"])
    assert result.d == {"k": "v"}


def test_different_short_letter_fix_for_ov4_works():
    @dataclass
    class Fixed:
        host: str = cli_short("H", default="x")

    assert build_config(Fixed, ["-H", "y"]).host == "y"


def test_non_colliding_classes_still_build():
    @dataclass
    class Inner:
        level: int = 1
        verbose: bool = False

    @dataclass
    class Fine:
        name: str = cli_short("n", default="n")
        debug: bool = cli_short("d", default=False)
        quiet: bool = False
        tags: List[str] = field(default_factory=list)
        files: List[List[str]] = combine_annotations(
            cli_append(nargs=2), default_factory=list
        )
        settings: Dict[str, Any] = field(default_factory=dict)
        out: str = combine_annotations(cli_positional(nargs="?"), default="o")
        inner: Inner = cli_nested(default_factory=Inner)

    result = build_config(Fine, ["-n", "x", "-d", "--inner-verbose", "--no-quiet"])
    assert result.name == "x" and result.debug is True
    assert result.inner.verbose is True


# ---------------------------------------------------------------------------
# The plan matches the real registration
# ---------------------------------------------------------------------------


def test_planned_option_strings_match_the_registered_ones():
    @dataclass
    class Inner:
        level: int = cli_short("l", default=1)
        verbose: bool = cli_short("v", default=False)
        opts: Dict[str, Any] = field(default_factory=dict)

    @dataclass
    class Everything:
        name: str = cli_short("n", default="n")
        debug: bool = cli_short("d", default=False)
        tags: List[str] = field(default_factory=list)
        files: List[List[str]] = combine_annotations(
            cli_short("f"), cli_append(nargs=2), default_factory=list
        )
        model_config: Dict[str, Any] = field(default_factory=dict)
        out: str = combine_annotations(cli_positional(nargs="?"), default="o")
        inner: Inner = cli_nested(default_factory=Inner)

    builder = GenericConfigBuilder(Everything)
    parser = argparse.ArgumentParser()
    builder.add_arguments(parser)

    flat = builder.field_analyzer.flatten_nested_fields(builder._config_fields)
    planned = plan_option_strings(builder.argument_registry, flat, "config", True)
    assert {option for option, _, _ in planned} == set(parser._option_string_actions)
    assert len({option for option, _, _ in planned}) == len(planned)


# ---------------------------------------------------------------------------
# BF1
# ---------------------------------------------------------------------------


def help_lines(config_class):
    parser = argparse.ArgumentParser(formatter_class=RangeAppendHelpFormatter)
    GenericConfigBuilder(config_class).add_arguments(parser)
    return parser.format_help().splitlines()


def test_BF1_negative_flag_with_custom_help_names_the_positive_option():
    @dataclass
    class Custom:
        debug: bool = combine_annotations(cli_help("Enable debug mode"), default=False)

    lines = help_lines(Custom)
    assert any(
        "--no-debug" in line and line.rstrip().endswith("Disable --debug")
        for line in lines
    )
    assert any("Enable debug mode (default: False)" in line for line in lines)


def test_BF1_negative_flag_without_custom_help_is_unchanged():
    @dataclass
    class Plain:
        debug: bool = False

    lines = help_lines(Plain)
    assert any(
        "--no-debug" in line and line.rstrip().endswith("Disable debug")
        for line in lines
    )


def test_BF1_nested_negative_flag_names_the_prefixed_option():
    @dataclass
    class Inner:
        verbose: bool = combine_annotations(cli_help("Be loud"), default=False)

    @dataclass
    class Outer:
        inner: Inner = cli_nested(default_factory=Inner)

    lines = help_lines(Outer)
    assert any(line.rstrip().endswith("Disable --inner-verbose") for line in lines)
