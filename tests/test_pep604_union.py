"""
Tests for PEP 604 union type support (X | None syntax, Python 3.10+).

Verifies that `int | None`, `float | None`, etc. are correctly recognized
as Optional types by TypeInspector and work end-to-end with build_config().

All tests in this file require Python 3.10+ and are skipped on older versions.
"""

import pytest


class TestTypeInspectorPEP604:
    """Test TypeInspector with PEP 604 union types."""

    def test_is_optional_int_or_none(self):
        """Test is_optional recognizes int | None."""
        from dataclass_args.type_inspector import TypeInspector

        assert TypeInspector.is_optional(int | None)

    def test_is_optional_float_or_none(self):
        """Test is_optional recognizes float | None."""
        from dataclass_args.type_inspector import TypeInspector

        assert TypeInspector.is_optional(float | None)

    def test_is_optional_str_or_none(self):
        """Test is_optional recognizes str | None."""
        from dataclass_args.type_inspector import TypeInspector

        assert TypeInspector.is_optional(str | None)

    def test_is_optional_int_or_str_not_optional(self):
        """Test is_optional returns False for int | str (no None)."""
        from dataclass_args.type_inspector import TypeInspector

        assert not TypeInspector.is_optional(int | str)

    def test_is_optional_multi_union_with_none(self):
        """Test is_optional with int | str | None."""
        from dataclass_args.type_inspector import TypeInspector

        assert TypeInspector.is_optional(int | str | None)

    def test_unwrap_optional_int_or_none(self):
        """Test unwrap_optional extracts int from int | None."""
        from dataclass_args.type_inspector import TypeInspector

        assert TypeInspector.unwrap_optional(int | None) is int

    def test_unwrap_optional_float_or_none(self):
        """Test unwrap_optional extracts float from float | None."""
        from dataclass_args.type_inspector import TypeInspector

        assert TypeInspector.unwrap_optional(float | None) is float

    def test_unwrap_optional_str_or_none(self):
        """Test unwrap_optional extracts str from str | None."""
        from dataclass_args.type_inspector import TypeInspector

        assert TypeInspector.unwrap_optional(str | None) is str

    def test_get_origin_and_args_pep604(self):
        """Test get_origin_and_args returns correct values for PEP 604 types."""
        import types

        from dataclass_args.type_inspector import TypeInspector

        origin, args = TypeInspector.get_origin_and_args(int | None)
        assert origin is types.UnionType
        assert int in args
        assert type(None) in args


class TestBuildConfigPEP604:
    """Test build_config with PEP 604 union type fields."""

    def test_int_or_none_field_parsed_as_int(self):
        """Test int | None field is correctly parsed as int from CLI."""
        from dataclasses import dataclass

        from dataclass_args import build_config

        @dataclass
        class Config:
            count: int | None = None

        config = build_config(Config, args=["--count", "42"])
        assert config.count == 42
        assert isinstance(config.count, int)

    def test_float_or_none_field_parsed_as_float(self):
        """Test float | None field is correctly parsed as float from CLI."""
        from dataclasses import dataclass

        from dataclass_args import build_config

        @dataclass
        class Config:
            rate: float | None = None

        config = build_config(Config, args=["--rate", "3.14"])
        assert config.rate == 3.14
        assert isinstance(config.rate, float)

    def test_str_or_none_field_parsed_as_str(self):
        """Test str | None field still works correctly."""
        from dataclasses import dataclass

        from dataclass_args import build_config

        @dataclass
        class Config:
            name: str | None = None

        config = build_config(Config, args=["--name", "hello"])
        assert config.name == "hello"
        assert isinstance(config.name, str)

    def test_pep604_field_not_provided_stays_none(self):
        """Test int | None field stays None when not provided."""
        from dataclasses import dataclass

        from dataclass_args import build_config

        @dataclass
        class Config:
            count: int | None = None
            name: str = "default"

        config = build_config(Config, args=["--name", "test"])
        assert config.count is None

    def test_pep604_from_base_configs(self):
        """Test int | None field works correctly with base_configs."""
        from dataclasses import dataclass

        from dataclass_args import build_config

        @dataclass
        class Config:
            count: int | None = None
            rate: float | None = None

        config = build_config(
            Config,
            args=[],
            base_configs={"count": 10, "rate": 2.5},
        )
        assert config.count == 10
        assert config.rate == 2.5

    def test_pep604_cli_overrides_base_configs(self):
        """Test CLI overrides base_configs for int | None fields."""
        from dataclasses import dataclass

        from dataclass_args import build_config

        @dataclass
        class Config:
            count: int | None = None

        config = build_config(
            Config,
            args=["--count", "99"],
            base_configs={"count": 10},
        )
        assert config.count == 99

    def test_pep604_in_nested_dataclass(self):
        """Test int | None field works in nested dataclass."""
        from dataclasses import dataclass

        from dataclass_args import build_config, cli_nested

        @dataclass
        class InnerConfig:
            timeout: int | None = None
            weight: float | None = None

        @dataclass
        class AppConfig:
            name: str = "app"
            inner: InnerConfig = cli_nested(prefix="i", default_factory=InnerConfig)

        config = build_config(
            AppConfig, args=["--i-timeout", "30", "--i-weight", "0.75"]
        )
        assert config.inner.timeout == 30
        assert isinstance(config.inner.timeout, int)
        assert config.inner.weight == 0.75
        assert isinstance(config.inner.weight, float)

    def test_pep604_with_post_init_validation(self):
        """Test int | None field works with __post_init__ validation."""
        from dataclasses import dataclass

        from dataclass_args import build_config

        @dataclass
        class Config:
            count: int | None = None

            def __post_init__(self):
                if self.count is not None and self.count < 0:
                    raise ValueError("count must be non-negative")

        # Valid
        config = build_config(Config, args=["--count", "5"])
        assert config.count == 5

    def test_pep604_mixed_with_typing_optional(self):
        """Test mixing PEP 604 and typing.Optional in same dataclass."""
        from dataclasses import dataclass
        from typing import Optional

        from dataclass_args import build_config

        @dataclass
        class Config:
            count: int | None = None  # PEP 604
            name: Optional[str] = None  # typing.Optional

        config = build_config(Config, args=["--count", "7", "--name", "mixed"])
        assert config.count == 7
        assert isinstance(config.count, int)
        assert config.name == "mixed"
        assert isinstance(config.name, str)


class TestRegressionTypingOptional:
    """Regression tests ensuring typing.Optional still works."""

    def test_optional_int_still_works(self):
        """Regression: Optional[int] still parsed correctly."""
        from dataclasses import dataclass
        from typing import Optional

        from dataclass_args import build_config

        @dataclass
        class Config:
            count: Optional[int] = None

        config = build_config(Config, args=["--count", "10"])
        assert config.count == 10
        assert isinstance(config.count, int)

    def test_optional_float_still_works(self):
        """Regression: Optional[float] still parsed correctly."""
        from dataclasses import dataclass
        from typing import Optional

        from dataclass_args import build_config

        @dataclass
        class Config:
            rate: Optional[float] = None

        config = build_config(Config, args=["--rate", "1.5"])
        assert config.rate == 1.5
        assert isinstance(config.rate, float)

    def test_optional_str_still_works(self):
        """Regression: Optional[str] still parsed correctly."""
        from dataclasses import dataclass
        from typing import Optional

        from dataclass_args import build_config

        @dataclass
        class Config:
            name: Optional[str] = None

        config = build_config(Config, args=["--name", "test"])
        assert config.name == "test"
        assert isinstance(config.name, str)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
