"""Tests for collision detection in nested dataclasses."""

from dataclasses import dataclass

import pytest

from dataclass_args import cli_nested, cli_short
from dataclass_args.builder import GenericConfigBuilder
from dataclass_args.exceptions import ConfigBuilderError


class TestNestedFieldCollisions:
    """Test detection of CLI name collisions when flattening nested dataclasses."""

    def test_no_collision_with_prefix(self):
        """Nested fields with prefix should not collide."""

        @dataclass
        class Inner:
            count: int = 0

        @dataclass
        class Outer:
            count: int = 0
            inner: Inner = cli_nested(default_factory=Inner, prefix="inner")

        # Should not raise
        builder = GenericConfigBuilder(Outer)
        assert builder is not None

    def test_collision_without_prefix(self):
        """Nested fields without prefix that collide should raise error."""

        @dataclass
        class Inner:
            count: int = 0

        @dataclass
        class Outer:
            count: int = 0
            inner: Inner = cli_nested(default_factory=Inner, prefix="")

        with pytest.raises(ConfigBuilderError, match="collision"):
            GenericConfigBuilder(Outer)

    def test_collision_between_nested_dataclasses(self):
        """Two nested dataclasses with same field names and no prefix should collide."""

        @dataclass
        class Inner1:
            value: str = "inner1"

        @dataclass
        class Inner2:
            value: str = "inner2"

        @dataclass
        class Outer:
            inner1: Inner1 = cli_nested(default_factory=Inner1, prefix="")
            inner2: Inner2 = cli_nested(default_factory=Inner2, prefix="")

        with pytest.raises(ConfigBuilderError, match="collision"):
            GenericConfigBuilder(Outer)

    def test_no_collision_with_different_names(self):
        """Nested dataclasses with different field names should not collide."""

        @dataclass
        class Inner:
            inner_field: int = 0

        @dataclass
        class Outer:
            outer_field: int = 0
            inner: Inner = cli_nested(default_factory=Inner, prefix="")

        # Should not raise
        builder = GenericConfigBuilder(Outer)
        assert builder is not None

    def test_auto_prefix_prevents_collision(self):
        """Auto-prefix (None) should prevent collision."""

        @dataclass
        class Inner:
            count: int = 0

        @dataclass
        class Outer:
            count: int = 0
            inner: Inner = cli_nested(
                default_factory=Inner,
            )  # Auto-prefix

        # Should not raise (auto-prefix adds "inner-")
        builder = GenericConfigBuilder(Outer)
        assert builder is not None


class TestShortOptionCollisions:
    """Test detection of short option collisions."""

    def test_no_collision_with_prefix(self):
        """Short options in nested fields with prefix should not conflict."""

        @dataclass
        class Inner:
            name: str = cli_short("n", default="inner")

        @dataclass
        class Outer:
            name: str = cli_short("n", default="outer")
            inner: Inner = cli_nested(default_factory=Inner, prefix="i")

        # Should not raise - nested field has prefix so no short option
        builder = GenericConfigBuilder(Outer)
        assert builder is not None

    def test_collision_without_prefix(self):
        """Short options in nested fields without prefix should collide."""

        @dataclass
        class Inner:
            name: str = cli_short("n", default="inner")

        @dataclass
        class Outer:
            name: str = cli_short("n", default="outer")
            inner: Inner = cli_nested(default_factory=Inner, prefix="")

        with pytest.raises(ConfigBuilderError, match="collision"):
            GenericConfigBuilder(Outer)

    def test_short_option_collision_between_nested(self):
        """Short options between two nested dataclasses should collide."""

        @dataclass
        class Inner1:
            value: str = cli_short("v", default="inner1")

        @dataclass
        class Inner2:
            value: str = cli_short("v", default="inner2")

        @dataclass
        class Outer:
            inner1: Inner1 = cli_nested(default_factory=Inner1, prefix="")
            inner2: Inner2 = cli_nested(default_factory=Inner2, prefix="")

        with pytest.raises(ConfigBuilderError, match="collision"):
            GenericConfigBuilder(Outer)

    def test_no_collision_different_short_options(self):
        """Different short options should not collide."""

        @dataclass
        class Inner:
            inner_name: str = cli_short("i", default="inner")

        @dataclass
        class Outer:
            outer_name: str = cli_short("o", default="outer")
            inner: Inner = cli_nested(default_factory=Inner, prefix="")

        # Should not raise - different field names AND short options
        builder = GenericConfigBuilder(Outer)
        assert builder is not None

    def test_no_short_options_defined(self):
        """No short options means no collision possible."""

        @dataclass
        class Inner:
            inner_field: str = "inner"

        @dataclass
        class Outer:
            outer_field: str = "outer"
            inner: Inner = cli_nested(default_factory=Inner, prefix="")

        # Should not raise - different field names, no short options
        builder = GenericConfigBuilder(Outer)
        assert builder is not None
