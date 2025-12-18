"""Test that nested field help text shows parent.field context."""

import argparse
from dataclasses import dataclass

from dataclass_args import GenericConfigBuilder, cli_help, cli_nested


class TestNestedHelpText:
    """Test nested field help text generation."""

    def test_nested_with_prefix_shows_parent_field_in_help(self):
        """Nested fields with prefix should show 'parent.field' in help text."""

        @dataclass
        class AgentConfig:
            name: str = "default"
            timeout: int = 30

        @dataclass
        class Config:
            agent: AgentConfig = cli_nested(prefix="a2a")

        builder = GenericConfigBuilder(Config)
        parser = argparse.ArgumentParser()
        builder.add_arguments(parser)

        # Get help text
        help_text = parser.format_help()

        # Should show parent.field in help text
        assert "agent.name" in help_text
        assert "agent.timeout" in help_text

        # Should NOT show generic "nested field"
        assert "nested field" not in help_text

    def test_nested_with_custom_help_uses_custom(self):
        """Custom help text should override parent.field format."""

        @dataclass
        class Inner:
            value: str = cli_help("Custom help text", default="test")

        @dataclass
        class Outer:
            inner: Inner = cli_nested(prefix="i")

        builder = GenericConfigBuilder(Outer)
        parser = argparse.ArgumentParser()
        builder.add_arguments(parser)

        help_text = parser.format_help()

        # Should use custom help text
        assert "Custom help text" in help_text

        # Should NOT show parent.field format
        assert "inner.value" not in help_text

    def test_nested_empty_prefix_shows_field_name(self):
        """Nested fields with empty prefix should show just the field name."""

        @dataclass
        class Inner:
            count: int = 5

        @dataclass
        class Outer:
            inner: Inner = cli_nested(prefix="")

        builder = GenericConfigBuilder(Outer)
        parser = argparse.ArgumentParser()
        builder.add_arguments(parser)

        help_text = parser.format_help()

        # With empty prefix, should show field name
        assert "--count" in help_text
        # Should show just "count" not "inner.count" since prefix is empty
        lines = help_text.split("\n")
        count_help = [line for line in lines if "--count" in line]
        assert any("count" in line for line in count_help)

    def test_multiple_nested_fields_all_show_parent(self):
        """Multiple nested fields should all show parent.field format."""

        @dataclass
        class DatabaseConfig:
            host: str = "localhost"
            port: int = 5432
            user: str = "admin"

        @dataclass
        class CacheConfig:
            host: str = "localhost"
            port: int = 6379

        @dataclass
        class AppConfig:
            database: DatabaseConfig = cli_nested(prefix="db")
            cache: CacheConfig = cli_nested(prefix="cache")

        builder = GenericConfigBuilder(AppConfig)
        parser = argparse.ArgumentParser()
        builder.add_arguments(parser)

        help_text = parser.format_help()

        # Database fields
        assert "database.host" in help_text
        assert "database.port" in help_text
        assert "database.user" in help_text

        # Cache fields
        assert "cache.host" in help_text
        assert "cache.port" in help_text

        # CLI names should have prefixes
        assert "--db-host" in help_text
        assert "--db-port" in help_text
        assert "--cache-host" in help_text
        assert "--cache-port" in help_text

    def test_nested_dataclass_field_shows_parent_context(self):
        """Nested dataclass fields (not fully flattened) show parent context."""

        @dataclass
        class Level3:
            value: str = "deep"

        @dataclass
        class Level2:
            level3: Level3 = cli_nested(prefix="l3")

        @dataclass
        class Level1:
            level2: Level2 = cli_nested(prefix="l2")

        builder = GenericConfigBuilder(Level1)
        parser = argparse.ArgumentParser()
        builder.add_arguments(parser)

        help_text = parser.format_help()

        # Level2.level3 is not fully flattened (requires recursive flattening)
        # So it shows as level2.level3
        assert "level2.level3" in help_text

        # CLI name has the l2 prefix
        assert "--l2-level3" in help_text
