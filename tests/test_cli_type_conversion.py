"""
Tests for CLI value conversion to declared types.

Covers:
- LT1: option list fields convert elements with their element type
  (top level and nested, at any depth)
- LT2: choices on typed list fields compare converted values
- LT3: Path fields are intentionally left as str (pinned)
- Values from layers are not coerced; bool elements stay str
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, List, Optional

import pytest

from dataclass_args import (
    build_config,
    cli_append,
    cli_choices,
    cli_nested,
    cli_positional,
    cli_resolve,
    combine_annotations,
)


class TestOptionListConversion:
    """LT1: option lists convert their elements."""

    def test_LT1_list_int(self):
        @dataclass
        class Config:
            n: List[int] = field(default_factory=list)

        config = build_config(Config, args=["--n", "1", "2"])

        assert config.n == [1, 2]
        assert all(type(v) is int for v in config.n)

    def test_LT1_list_float(self):
        @dataclass
        class Config:
            f: List[float] = field(default_factory=list)

        config = build_config(Config, args=["--f", "1.5", "2"])

        assert config.f == [1.5, 2.0]
        assert all(type(v) is float for v in config.f)

    def test_LT1_optional_list_int(self):
        @dataclass
        class Config:
            o: Optional[List[int]] = None

        assert build_config(Config, args=["--o", "3"]).o == [3]
        assert build_config(Config, args=[]).o is None

    def test_LT1_optional_list_empty(self):
        @dataclass
        class Config:
            o: Optional[List[int]] = None

        assert build_config(Config, args=["--o"]).o == []

    def test_LT1_nested_list_int(self):
        @dataclass
        class Db:
            ports: List[int] = field(default_factory=list)

        @dataclass
        class Config:
            db: Db = cli_nested(prefix="db", default_factory=Db)

        config = build_config(Config, args=["--db-ports", "1", "2"])

        assert config.db.ports == [1, 2]
        assert all(type(v) is int for v in config.db.ports)

    def test_LT1_nested_list_int_depth_2(self):
        @dataclass
        class Inner:
            ports: List[int] = field(default_factory=list)

        @dataclass
        class Mid:
            inner: Inner = cli_nested(prefix="inner", default_factory=Inner)

        @dataclass
        class Config:
            mid: Mid = cli_nested(prefix="mid", default_factory=Mid)

        config = build_config(Config, args=["--mid-inner-ports", "1", "2"])

        assert config.mid.inner.ports == [1, 2]
        assert all(type(v) is int for v in config.mid.inner.ports)

    def test_LT1_invalid_element_is_parse_error(self, capsys):
        @dataclass
        class Config:
            n: List[int] = field(default_factory=list)

        with pytest.raises(SystemExit) as exc_info:
            build_config(Config, args=["--n", "1", "x"])

        assert exc_info.value.code == 2
        assert "invalid int value" in capsys.readouterr().err

    def test_LT1_list_str_unchanged(self):
        @dataclass
        class Config:
            t: List[str] = field(default_factory=list)

        config = build_config(Config, args=["--t", "1", "2"])

        assert config.t == ["1", "2"]
        assert all(type(v) is str for v in config.t)

    def test_LT1_layer_values_not_coerced(self):
        @dataclass
        class Config:
            n: List[int] = field(default_factory=list)

        config = build_config(Config, args=[], base_configs={"n": ["7"]})

        assert config.n == ["7"]

    def test_LT1_list_any_unchanged(self):
        received: List[Any] = []

        def resolver(value: Any) -> Any:
            received.append(value)
            return value

        @dataclass
        class Config:
            items: List[Any] = combine_annotations(
                cli_resolve(resolver=resolver), default_factory=list
            )

        build_config(Config, args=["--items", "1", "2"])

        assert received == [["1", "2"]]


class TestChoicesOnTypedList:
    """LT2: choices on typed lists compare converted values."""

    def test_LT2_int_choices_on_list(self):
        @dataclass
        class Config:
            lv: List[int] = combine_annotations(
                cli_choices([1, 2, 3]), default_factory=list
            )

        assert build_config(Config, args=["--lv", "1", "2"]).lv == [1, 2]
        with pytest.raises(SystemExit) as exc_info:
            build_config(Config, args=["--lv", "4"])
        assert exc_info.value.code == 2


class TestPathStaysStr:
    """LT3 is intentionally not fixed: Path options keep str values."""

    def test_LT3_path_still_str_by_design(self):
        @dataclass
        class Config:
            p: Path = Path(".")
            ps: List[Path] = field(default_factory=list)

        config = build_config(Config, args=["--p", "a/b", "--ps", "a", "b/c"])

        assert config.p == "a/b"
        assert type(config.p) is str
        assert config.ps == ["a", "b/c"]
        assert all(type(v) is str for v in config.ps)


class TestUnchangedBehaviour:
    """Guards for paths that must not drift."""

    def test_LT_append_and_positional_still_convert(self):
        @dataclass
        class AppendConfig:
            ids: List[int] = cli_append(default_factory=list)
            groups: List[List[float]] = cli_append(nargs="+", default_factory=list)

        @dataclass
        class PositionalConfig:
            nums: List[int] = combine_annotations(
                cli_positional(nargs="*"), default_factory=list
            )

        append = build_config(
            AppendConfig,
            args=["--ids", "1", "--ids", "2", "--groups", "1.5", "2", "--groups", "3"],
        )
        positional = build_config(PositionalConfig, args=["4", "5"])

        assert append.ids == [1, 2]
        assert append.groups == [[1.5, 2.0], [3.0]]
        assert positional.nums == [4, 5]

    def test_LT_bool_list_unchanged(self):
        @dataclass
        class Config:
            b: List[bool] = field(default_factory=list)

        config = build_config(Config, args=["--b", "true", "false"])

        assert config.b == ["true", "false"]
