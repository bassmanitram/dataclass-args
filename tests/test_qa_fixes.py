"""
Regression tests for the defects found in the post-1.10.1 QA review.

Each test names the defect it pins. See the [Unreleased] section of
CHANGELOG.md for the user-facing description of each fix.
"""

import argparse
import contextlib
import io
import sys
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Union

import pytest

from dataclass_args import (
    ConfigBuilderError,
    ConfigLayer,
    ConfigurationError,
    GenericConfigBuilder,
    InstantiationError,
    build_config,
    build_config_from_dict,
    cli_append,
    cli_choices,
    cli_help,
    cli_nested,
    cli_override_name,
    cli_positional,
    cli_resolve,
    cli_short,
    combine_annotations,
    instantiate,
    load_structured_file,
)


def help_text(config_class, **kwargs) -> str:
    """Return the --help output of a dataclass CLI."""
    out = io.StringIO()
    with contextlib.redirect_stdout(out), pytest.raises(SystemExit):
        build_config(config_class, ["--help"], **kwargs)
    return out.getvalue()


# ---------------------------------------------------------------------------
# Field names with a leading underscore were silently ignored on the CLI
# (argparse derived dest "private" from "---private"; the field is "_private")
# ---------------------------------------------------------------------------


@dataclass
class Underscored:
    _count: int = 1
    _tags: List[str] = field(default_factory=list)
    _opts: Dict[str, Any] = field(default_factory=dict)
    _items: List[str] = combine_annotations(cli_append(), default_factory=list)
    _flag: bool = False


def test_leading_underscore_fields_take_cli_values():
    result = build_config(
        Underscored,
        ["---count", "7", "---tags", "a", "b", "--o", "k:1", "---items", "x"],
    )
    assert result._count == 7
    assert result._tags == ["a", "b"]
    assert result._opts == {"k": 1}
    assert result._items == ["x"]


def test_leading_underscore_bool_and_negative_flag():
    assert build_config(Underscored, ["---flag"])._flag is True
    assert (
        build_config(Underscored, ["--no--flag"], base_configs={"_flag": True})._flag
        is False
    )


def test_leading_underscore_field_in_unprefixed_nested_class():
    @dataclass
    class Inner:
        _level: int = 0

    @dataclass
    class Outer:
        inner: Inner = cli_nested(prefix="", default_factory=Inner)

    assert build_config(Outer, ["---level", "3"]).inner._level == 3


# ---------------------------------------------------------------------------
# Nested prefixes kept their underscores (--my_db-host next to
# --no-my-db-flag); nested bool help used the flat dest name
# ---------------------------------------------------------------------------


@dataclass
class Db:
    host: str = "localhost"
    ssl: bool = False


@dataclass
class Prefixed:
    primary_db: Db = cli_nested(default_factory=Db)  # auto prefix
    replica: Db = cli_nested(prefix="read_only", default_factory=Db)  # custom


def test_nested_prefix_spelling_unchanged_B2_deferred():
    """Option names are exactly as in 1.10.1 (hyphenating prefixes is deferred)."""
    text = help_text(Prefixed)
    assert "--primary_db-host" in text
    assert "--primary_db-ssl" in text
    assert "--no-primary-db-ssl" in text
    assert "--read_only-ssl" in text
    assert "--primary-db-host" not in text

    result = build_config(
        Prefixed,
        ["--primary_db-host", "p", "--read_only-host", "r", "--read_only-ssl"],
    )
    assert result.primary_db.host == "p"
    assert result.replica.host == "r"
    assert result.replica.ssl is True


def test_nested_negative_flag_spelling_unchanged():
    # The negative flag is the hyphenated field path, not the positive option
    # with "no-" put in front: see FUTURE_CHANGES.md ("Hyphenate underscores in
    # nested prefixes") for the planned change.
    result = build_config(
        Prefixed,
        ["--no-primary-db-ssl"],
        base_configs={"primary_db": {"ssl": True}},
    )
    assert result.primary_db.ssl is False

    @dataclass
    class Inner:
        in_enabled: bool = True

    @dataclass
    class Mid:
        inner: Inner = cli_nested(default_factory=Inner)

    @dataclass
    class Top:
        my_mid: Mid = cli_nested(default_factory=Mid)

    text = help_text(Top)
    assert "--my_mid-inner-in-enabled" in text
    assert "--no-my-mid-inner-in-enabled" in text
    assert (
        build_config(Top, ["--no-my-mid-inner-in-enabled"]).my_mid.inner.in_enabled
        is False
    )


def test_nested_bool_help_uses_dotted_path():
    text = help_text(Prefixed)
    assert "--primary_db-ssl" in text
    assert "--no-primary-db-ssl" in text
    assert "primary_db.ssl (default: False)" in text
    assert "Disable primary_db.ssl" in text
    assert "primary_db_ssl" not in text


# ---------------------------------------------------------------------------
# Guard: every option string is exactly as 1.10.1 (commit 78536b1) built it,
# for the README "Nested Dataclasses" example plus underscored prefixes, bools
# at depth 2 and leading-underscore fields
# ---------------------------------------------------------------------------


@dataclass
class GuardDatabaseConfig:
    host: str = "localhost"
    port: int = 5432
    username: str = "admin"
    password: str = "secret"
    use_ssl: bool = False


@dataclass
class GuardCacheConfig:
    host: str = "localhost"
    port: int = 6379
    ttl: int = 3600
    read_only: bool = False


@dataclass
class GuardInner:
    in_enabled: bool = False
    in_name: str = "x"
    _hidden: bool = False


@dataclass
class GuardMid:
    mid_flag: bool = False
    inner: GuardInner = cli_nested(default_factory=GuardInner)
    own_inner: GuardInner = cli_nested(prefix="own_in", default_factory=GuardInner)


@dataclass
class GuardFlat:
    flat_on: bool = cli_short("f", default=False)
    _flat_private: bool = False


@dataclass
class GuardAppConfig:
    app_name: str = "myapp"
    debug: bool = False
    dry_run: bool = False
    database: GuardDatabaseConfig = cli_nested(
        prefix="db", default_factory=GuardDatabaseConfig
    )
    cache: GuardCacheConfig = cli_nested(
        prefix="cache", default_factory=GuardCacheConfig
    )
    primary_db: GuardDatabaseConfig = cli_nested(default_factory=GuardDatabaseConfig)
    replica: GuardDatabaseConfig = cli_nested(
        prefix="read_only", default_factory=GuardDatabaseConfig
    )
    my_mid: GuardMid = cli_nested(default_factory=GuardMid)
    bare: GuardMid = cli_nested(prefix="bm", default_factory=GuardMid)
    flat: GuardFlat = cli_nested(prefix="", default_factory=GuardFlat)


EXPECTED_1101_OPTION_STRINGS = [
    "---flat-private",
    "--app-name",
    "--bm-inner--hidden",
    "--bm-inner-in-enabled",
    "--bm-inner-in-name",
    "--bm-mid-flag",
    "--bm-own_in--hidden",
    "--bm-own_in-in-enabled",
    "--bm-own_in-in-name",
    "--cache-host",
    "--cache-port",
    "--cache-read-only",
    "--cache-ttl",
    "--config",
    "--db-host",
    "--db-password",
    "--db-port",
    "--db-use-ssl",
    "--db-username",
    "--debug",
    "--dry-run",
    "--flat-on",
    "--my_mid-inner--hidden",
    "--my_mid-inner-in-enabled",
    "--my_mid-inner-in-name",
    "--my_mid-mid-flag",
    "--my_mid-own_in--hidden",
    "--my_mid-own_in-in-enabled",
    "--my_mid-own_in-in-name",
    "--no-bm-inner--hidden",
    "--no-bm-inner-in-enabled",
    "--no-bm-mid-flag",
    "--no-bm-own-in--hidden",
    "--no-bm-own-in-in-enabled",
    "--no-cache-read-only",
    "--no-db-use-ssl",
    "--no-debug",
    "--no-dry-run",
    "--no-flat-on",
    "--no-flat-private",
    "--no-my-mid-inner--hidden",
    "--no-my-mid-inner-in-enabled",
    "--no-my-mid-mid-flag",
    "--no-my-mid-own-in--hidden",
    "--no-my-mid-own-in-in-enabled",
    "--no-primary-db-use-ssl",
    "--no-read-only-use-ssl",
    "--primary_db-host",
    "--primary_db-password",
    "--primary_db-port",
    "--primary_db-use-ssl",
    "--primary_db-username",
    "--read_only-host",
    "--read_only-password",
    "--read_only-port",
    "--read_only-use-ssl",
    "--read_only-username",
    "-f",
]


def test_option_strings_identical_to_1_10_1():
    parser = argparse.ArgumentParser(add_help=False)
    GenericConfigBuilder(GuardAppConfig).add_arguments(parser)
    registered = sorted(
        option for action in parser._actions for option in action.option_strings
    )
    assert registered == EXPECTED_1101_OPTION_STRINGS


# ---------------------------------------------------------------------------
# Nested bool fields kept their cli_short letter under a prefix, so reusing
# a dataclass for two nested fields raised an option collision
# ---------------------------------------------------------------------------


@dataclass
class Server:
    verbose: bool = cli_short("v", default=False)
    port: int = cli_short("p", default=80)


def test_prefixed_nested_bool_has_no_short_option():
    @dataclass
    class App:
        srv: Server = cli_nested(prefix="srv", default_factory=Server)

    with pytest.raises(SystemExit), contextlib.redirect_stderr(io.StringIO()):
        build_config(App, ["-v"])
    assert build_config(App, ["--srv-verbose"]).srv.verbose is True


def test_same_nested_class_reused_under_two_prefixes():
    @dataclass
    class App:
        a: Server = cli_nested(prefix="a", default_factory=Server)
        b: Server = cli_nested(prefix="b", default_factory=Server)

    result = build_config(App, ["--b-verbose", "--a-port", "1"])
    assert (result.a.verbose, result.b.verbose, result.a.port) == (False, True, 1)


def test_unprefixed_nested_bool_keeps_short_option():
    @dataclass
    class App:
        srv: Server = cli_nested(prefix="", default_factory=Server)

    assert build_config(App, ["-v"]).srv.verbose is True


# ---------------------------------------------------------------------------
# Two arguments storing into the same Namespace attribute overwrote each
# other silently (different option strings, same dest)
# ---------------------------------------------------------------------------


def test_positional_named_like_config_option_is_rejected():
    @dataclass
    class Cmd:
        config: str = cli_positional()

    with pytest.raises(ConfigBuilderError) as exc:
        build_config(Cmd, ["x"])
    message = str(exc.value)
    assert "Argument destination 'config'" in message
    assert "positional 'config'" in message
    assert "config-file option (--config)" in message


def test_positional_is_fine_with_another_config_option_name():
    @dataclass
    class Cmd:
        config: str = cli_positional()

    from dataclass_args import build_config_from_cli

    result = build_config_from_cli(Cmd, ["x"], base_config_name="settings")
    assert result.config == "x"


def test_override_name_sharing_a_field_dest_is_rejected():
    @dataclass
    class Clash:
        a_b: int = 0
        settings: Dict[str, Any] = cli_override_name("a_b", default_factory=dict)

    with pytest.raises(ConfigBuilderError, match="Argument destination 'a_b'"):
        GenericConfigBuilder(Clash).add_arguments(argparse.ArgumentParser())


# ---------------------------------------------------------------------------
# Annotation validation and metadata hygiene
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("letter", ["-", " ", "\t"])
def test_cli_short_rejects_dash_and_whitespace(letter):
    with pytest.raises(ValueError, match="can't be '-' or whitespace"):
        cli_short(letter)


@pytest.mark.parametrize("name", ["--sk", "-s", "s k"])
def test_cli_override_name_rejects_dashes_and_whitespace(name):
    with pytest.raises(ValueError, match="without the leading '--'"):
        cli_override_name(name)


def test_caller_metadata_dict_is_not_mutated():
    shared = {"owner": "team"}
    first = cli_short("a", metadata=shared)
    second = cli_help("text", metadata=shared)
    combined = combine_annotations(cli_short("c"), metadata=shared)
    assert shared == {"owner": "team"}
    assert dict(first.metadata) == {"owner": "team", "cli_short": "a"}
    assert dict(second.metadata) == {"owner": "team", "cli_help": "text"}
    assert dict(combined.metadata) == {"owner": "team", "cli_short": "c"}


# ---------------------------------------------------------------------------
# Type handling
# ---------------------------------------------------------------------------


def test_bare_list_annotation_is_a_list_option():
    @dataclass
    class Bare:
        items: list = field(default_factory=list)

    assert build_config(Bare, ["--items", "a", "b"]).items == ["a", "b"]


def test_optional_union_behaves_like_the_union():
    @dataclass
    class U:
        plain: Union[int, str] = 0
        optional: Optional[Union[int, str]] = None
        pep604: int | str | None = None

    result = build_config(U, ["--plain", "abc", "--optional", "abc", "--pep604", "xyz"])
    assert (result.plain, result.optional, result.pep604) == ("abc", "abc", "xyz")


@dataclass
class WithInitFalse:
    a: int = 1
    computed: int = field(default=0, init=False)

    def __post_init__(self):
        self.computed = self.a * 10


def test_init_false_field_is_not_a_cli_option():
    assert "--computed" not in help_text(WithInitFalse)
    with pytest.raises(SystemExit), contextlib.redirect_stderr(io.StringIO()):
        build_config(WithInitFalse, ["--computed", "5"])
    assert build_config(WithInitFalse, ["--a", "2"]).computed == 20


def test_init_false_field_in_nested_class_and_provenance():
    @dataclass
    class Outer:
        inner: WithInitFalse = cli_nested(default_factory=WithInitFalse)

    result, prov = build_config(
        Outer, ["--inner-a", "3"], merge_strategy="deep", return_provenance=True
    )
    assert result.inner.computed == 30
    assert "inner.computed" not in prov.explain()


# ---------------------------------------------------------------------------
# @file errors repeated the field context ("Failed to process field 'x':
# Failed to process field 'x': ...")
# ---------------------------------------------------------------------------


def test_file_loading_error_names_the_field_once():
    from dataclass_args import cli_file_loadable

    @dataclass
    class F:
        msg: str = cli_file_loadable(default="")
        empty: str = cli_file_loadable(default="")

    with pytest.raises(ConfigurationError) as exc:
        build_config(F, ["--msg", "@/nonexistent/file.txt"])
    assert str(exc.value) == (
        "Failed to process field 'msg': File not found: /nonexistent/file.txt"
    )

    with pytest.raises(ConfigurationError) as exc:
        build_config_from_dict(F, {"empty": "@"})
    assert str(exc.value).count("Failed to process field") == 1
    assert "Empty file path after '@'" in str(exc.value)


# ---------------------------------------------------------------------------
# Config files: non-mapping top level gave "'list' object has no attribute
# 'items'"; "~" was not expanded although the README relies on it
# ---------------------------------------------------------------------------


@dataclass
class Settings:
    name: str = "app"
    settings: Dict[str, Any] = field(default_factory=dict)


@pytest.mark.parametrize(
    "filename, content, kind",
    [
        ("list.json", "[1, 2]", "list"),
        ("scalar.yaml", "just a string", "str"),
        ("false.yaml", "false", "bool"),
        ("text.conf", "hello world", "str"),
    ],
)
def test_non_mapping_config_file_is_a_clear_error(tmp_path, filename, content, kind):
    path = tmp_path / filename
    path.write_text(content)
    with pytest.raises(ConfigurationError) as exc:
        build_config(Settings, ["--config", str(path)])
    assert f"must contain a mapping (key/value pairs) at the top level, got {kind}" in (
        str(exc.value)
    )
    with pytest.raises(ValueError, match="must contain a mapping"):
        load_structured_file(path)


def test_non_mapping_dict_field_file_is_a_clear_error(tmp_path):
    path = tmp_path / "list.json"
    path.write_text("[1]")
    with pytest.raises(ConfigurationError, match="must contain a mapping"):
        build_config(Settings, ["--settings", str(path)])


def test_empty_yaml_file_is_an_empty_mapping(tmp_path):
    path = tmp_path / "empty.yaml"
    path.write_text("")
    assert load_structured_file(path) == {}
    assert build_config(Settings, ["--config", str(path)]) == Settings()


def test_tilde_is_expanded_in_config_paths(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    (tmp_path / "app.json").write_text('{"name": "from-home"}')
    (tmp_path / "s.json").write_text('{"k": 1}')

    assert build_config(Settings, ["--config", "~/app.json"]).name == "from-home"
    assert build_config(Settings, [], base_configs="~/app.json").name == "from-home"
    assert build_config(Settings, ["--settings", "~/s.json"]).settings == {"k": 1}
    assert load_structured_file("~/app.json") == {"name": "from-home"}


# ---------------------------------------------------------------------------
# A non-file string given for a plain dict field was stored as a str
# ---------------------------------------------------------------------------


def test_plain_dict_field_rejects_non_file_string():
    with pytest.raises(ConfigurationError) as exc:
        build_config(Settings, ["--settings", "settings.conf"])
    assert "Invalid value 'settings.conf' for dict field 'settings'" in str(exc.value)
    assert "cli_resolve()" in str(exc.value)

    with pytest.raises(ConfigurationError, match="for dict field 'settings'"):
        build_config_from_dict(Settings, {"settings": "settings.conf"})


@dataclass
class Holder:
    opts: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Outer:
    holder: Holder = cli_nested(default_factory=Holder)


@dataclass
class Resolved:
    opts: Dict[str, Any] = combine_annotations(
        cli_resolve(resolver=lambda v: {"got": v}), default_factory=dict
    )


@dataclass
class ResolvedOuter:
    inner: Resolved = cli_nested(default_factory=Resolved)


@pytest.fixture
def conf_file(tmp_path):
    """A YAML file with a .conf extension."""
    path = tmp_path / "settings.conf"
    path.write_text("k: 1\n")
    return path


@pytest.fixture
def bare_file(tmp_path):
    """A YAML file without an extension."""
    path = tmp_path / "settings"
    path.write_text("k: 2\n")
    return path


def test_B1p_existing_unknown_extension_file_loads_from_cli(conf_file):
    assert build_config(Settings, ["--settings", str(conf_file)]).settings == {"k": 1}


def test_B1p_existing_extensionless_file_loads_from_cli(bare_file):
    assert build_config(Settings, ["--settings", str(bare_file)]).settings == {"k": 2}


def test_B1p_existing_file_loads_from_nested_cli(conf_file, bare_file):
    result = build_config(Outer, ["--holder-opts", str(conf_file)])
    assert result.holder.opts == {"k": 1}
    result = build_config(Outer, ["--holder-opts", str(bare_file)])
    assert result.holder.opts == {"k": 2}


def test_B1p_existing_file_loads_from_layers(conf_file, bare_file):
    assert build_config(
        Settings, [], base_configs={"settings": str(conf_file)}
    ).settings == {"k": 1}
    assert build_config_from_dict(Settings, {"settings": str(bare_file)}).settings == {
        "k": 2
    }
    nested = build_config(
        Outer, [], base_configs=[ConfigLayer({"holder": {"opts": str(conf_file)}})]
    )
    assert nested.holder.opts == {"k": 1}


def test_B1p_cli_file_merges_with_layer_value(conf_file):
    result = build_config(
        Settings,
        ["--settings", str(conf_file)],
        base_configs={"settings": {"a": 0}},
    )
    assert result.settings == {"a": 0, "k": 1}


def test_B1p_missing_structured_path_is_not_found_error(tmp_path):
    missing = str(tmp_path / "nope.json")
    for args, config_class in [
        (["--settings", missing], Settings),
        (["--holder-opts", missing], Outer),
    ]:
        with pytest.raises(ConfigurationError) as exc:
            build_config(config_class, args)
        assert "Failed to load dictionary config for" in str(exc.value)
        assert "not found" in str(exc.value)

    with pytest.raises(ConfigurationError, match="not found") as exc:
        build_config(Settings, [], base_configs={"settings": missing})
    assert "Failed to load dict field 'settings'" in str(exc.value)


def test_B1p_missing_unstructured_path_is_invalid(tmp_path):
    with pytest.raises(ConfigurationError, match="Invalid value .*nope.conf"):
        build_config(Settings, ["--settings", str(tmp_path / "nope.conf")])


def test_B1p_plain_string_is_invalid_from_the_cli():
    with pytest.raises(ConfigurationError) as exc:
        build_config(Settings, ["--settings", "hello"])
    assert str(exc.value) == (
        "Invalid value 'hello' for dict field 'settings': expected a dict or a "
        "path to a configuration file (use cli_resolve() to accept other strings)"
    )
    with pytest.raises(ConfigurationError, match="dict field 'holder.opts'"):
        build_config(Outer, ["--holder-opts", "hello"])


def test_B1p_plain_string_is_invalid_from_a_layer_and_names_the_layer():
    with pytest.raises(ConfigurationError) as exc:
        build_config(
            Settings, [], base_configs=ConfigLayer({"settings": "hello"}, name="team")
        )
    assert "Invalid value 'hello' for dict field 'settings' in layer 'team'" in str(
        exc.value
    )
    with pytest.raises(ConfigurationError, match="dict field 'holder.opts' in layer"):
        build_config(Outer, [], base_configs={"holder": {"opts": "hello"}})


def test_B1p_plain_string_is_invalid_in_build_config_from_dict():
    with pytest.raises(ConfigurationError, match="Invalid value 'hello'"):
        build_config_from_dict(Settings, {"settings": "hello"})


def test_B1p_non_mapping_file_content_names_the_field(tmp_path):
    path = tmp_path / "list.conf"
    path.write_text("- 1\n- 2\n")
    for args in (["--settings", str(path)],):
        with pytest.raises(ConfigurationError) as exc:
            build_config(Settings, args)
        assert "field 'settings'" in str(exc.value)
        assert "must contain a mapping" in str(exc.value)
    with pytest.raises(ConfigurationError, match="holder.opts.*must contain a mapping"):
        build_config(Outer, ["--holder-opts", str(path)])
    with pytest.raises(ConfigurationError, match="'settings'.*must contain a mapping"):
        build_config(Settings, [], base_configs={"settings": str(path)})


def test_B1p_resolve_field_receives_the_string_from_the_cli():
    assert build_config(Resolved, ["--opts", "hello"]).opts == {"got": "hello"}
    # Resolvers aren't run for nested fields: the string passes through as given
    result = build_config(ResolvedOuter, ["--inner-opts", "hello"])
    assert result.inner.opts == "hello"


def test_B1p_resolve_field_receives_the_string_from_a_layer():
    assert build_config(Resolved, [], base_configs={"opts": "hello"}).opts == {
        "got": "hello"
    }
    result = build_config_from_dict(ResolvedOuter, {"inner": {"opts": "hello"}})
    assert result.inner.opts == "hello"


def test_B1p_tilde_path_loads_as_a_dict_field_value(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    (tmp_path / "x.json").write_text('{"k": 3}')
    assert build_config(Settings, ["--settings", "~/x.json"]).settings == {"k": 3}
    assert build_config(Outer, ["--holder-opts", "~/x.json"]).holder.opts == {"k": 3}
    assert build_config(
        Settings, [], base_configs={"settings": "~/x.json"}
    ).settings == {"k": 3}


def test_B1p_tilde_path_to_existing_unknown_extension_file(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    (tmp_path / "x.conf").write_text("k: 4\n")
    assert build_config(Settings, ["--settings", "~/x.conf"]).settings == {"k": 4}


def test_resolve_field_still_accepts_plain_strings():
    @dataclass
    class R:
        backend: Any = combine_annotations(
            cli_resolve(resolver=lambda v: f"resolved:{v}"), default=None
        )

    assert build_config(R, ["--backend", "redis"]).backend == "resolved:redis"


def test_nested_resolve_field_still_accepts_plain_strings():
    @dataclass
    class Inner:
        backend: Any = combine_annotations(cli_resolve(resolver=str), default=None)

    @dataclass
    class Outer:
        inner: Inner = cli_nested(default_factory=Inner)

    assert build_config(Outer, ["--inner-backend", "redis"]).inner.backend == "redis"


# ---------------------------------------------------------------------------
# Help text: a "%" crashed --help; a bool without a default said
# "(default: None)"
# ---------------------------------------------------------------------------


def test_percent_signs_in_help_are_shown_literally():
    @dataclass
    class P:
        cpu: int = cli_help("CPU limit in %", default=50)
        ratio: str = cli_choices(["10%", "20%"], default="10%")
        fast: bool = cli_help("100% speed", default=False)
        tags: List[str] = combine_annotations(
            cli_help("Tags, 5% max"), default_factory=list
        )
        extra: Dict[str, Any] = combine_annotations(
            cli_help("Extra %"), default_factory=dict
        )
        files: List[str] = combine_annotations(
            cli_append(), cli_help("Files %"), default_factory=list
        )
        target: str = cli_positional(help="Target %", default="t")

    text = help_text(P)
    for expected in [
        "CPU limit in %",
        "(choices: 10%, 20%)",
        "100% speed (default: False)",
        "Tags, 5% max",
        "Extra % configuration file path",
        "Files % (can be repeated)",
        "Target %",
    ]:
        assert expected in text


def test_required_bool_help_has_no_default_suffix():
    @dataclass
    class B:
        strict: bool
        loose: bool = True

    text = help_text(B)
    assert "strict\n" in text
    assert "(default: None)" not in text
    assert "loose (default: True)" in text


# ---------------------------------------------------------------------------
# A missing required value said "missing 1 required positional argument",
# confusing for options and config keys
# ---------------------------------------------------------------------------


def test_missing_required_fields_are_named():
    @dataclass
    class Req:
        name: str
        region: str
        port: int = 80

    with pytest.raises(ConfigurationError) as exc:
        build_config(Req, ["--port", "1"])
    assert str(exc.value) == (
        "Failed to create Req: missing required fields: 'name', 'region'"
    )

    with pytest.raises(ConfigurationError) as exc:
        build_config_from_dict(Req, {"name": "x"})
    assert str(exc.value) == "Failed to create Req: missing required field: 'region'"


def test_missing_required_nested_field_is_named():
    @dataclass
    class Inner:
        host: str

    @dataclass
    class Outer:
        inner: Inner = cli_nested(prefix="db", default_factory=dict)

    with pytest.raises(ConfigurationError) as exc:
        build_config(Outer, [])
    assert str(exc.value) == (
        "Failed to create nested dataclass Inner for field 'inner': "
        "missing required field: 'host'"
    )
    assert build_config(Outer, ["--db-host", "h"]).inner.host == "h"


# ---------------------------------------------------------------------------
# instantiate()
# ---------------------------------------------------------------------------


def test_instantiate_rejects_non_string_attr_path():
    with pytest.raises(InstantiationError, match="'_attr_' must be a string"):
        instantiate({"_target_": "collections.OrderedDict", "_attr_": 5})


def test_instantiate_attr_key_can_be_disabled_and_absent():
    result = instantiate({"_target_": "collections.OrderedDict"}, attr_key=None)
    assert dict(result) == {}


def test_instantiate_wraps_errors_raised_while_importing(tmp_path, monkeypatch):
    (tmp_path / "qa_broken_module.py").write_text("raise RuntimeError('boom')\n")
    monkeypatch.syspath_prepend(str(tmp_path))
    monkeypatch.delitem(sys.modules, "qa_broken_module", raising=False)

    with pytest.raises(InstantiationError) as exc:
        instantiate({"_target_": "qa_broken_module.Thing"})
    assert "Error while importing module 'qa_broken_module'" in str(exc.value)
    assert "RuntimeError: boom" in str(exc.value)


def test_instantiate_keyword_example_from_docs():
    from datetime import timedelta

    assert instantiate({"_target_": "datetime.timedelta", "hours": 2}) == timedelta(
        hours=2
    )


def test_nested_positional_still_gets_its_dedicated_error():
    @dataclass
    class Inner:
        path: str = cli_positional(default="x")

    @dataclass
    class Outer:
        inner: Inner = cli_nested(default_factory=Inner)

    with pytest.raises(ConfigBuilderError, match="Positional arguments in nested"):
        build_config(Outer, [])
