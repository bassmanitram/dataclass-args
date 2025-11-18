"""Tests for custom description parameter."""

import sys
from dataclasses import dataclass
from io import StringIO
from typing import List, Optional

import pytest

from dataclass_args import GenericConfigBuilder, build_config, build_config_from_cli


@dataclass
class SimpleConfig:
    """Simple config for testing."""

    name: str = "default"
    count: int = 10


class TestCustomDescription:
    """Test custom description parameter functionality."""

    def test_builder_with_custom_description(self):
        """Test GenericConfigBuilder with custom description."""
        custom_desc = "My custom application configuration"
        builder = GenericConfigBuilder(SimpleConfig, description=custom_desc)

        assert builder.description == custom_desc
        assert builder.config_class == SimpleConfig

    def test_builder_with_no_description(self):
        """Test GenericConfigBuilder without description defaults to None."""
        builder = GenericConfigBuilder(SimpleConfig)

        assert builder.description is None
        assert builder.config_class == SimpleConfig

    def test_build_config_with_custom_description(self, capsys):
        """Test build_config with custom description in help."""
        custom_desc = "Configure the application server"

        with pytest.raises(SystemExit) as exc_info:
            build_config(SimpleConfig, args=["--help"], description=custom_desc)

        assert exc_info.value.code == 0
        captured = capsys.readouterr()
        assert custom_desc in captured.out

    def test_build_config_with_default_description(self, capsys):
        """Test build_config without description uses default format."""
        with pytest.raises(SystemExit) as exc_info:
            build_config(SimpleConfig, args=["--help"])

        assert exc_info.value.code == 0
        captured = capsys.readouterr()
        assert "Build SimpleConfig from CLI" in captured.out

    def test_build_config_from_cli_with_custom_description(self, capsys):
        """Test build_config_from_cli with custom description."""
        custom_desc = "Server configuration utility"

        with pytest.raises(SystemExit) as exc_info:
            build_config_from_cli(
                SimpleConfig, args=["--help"], description=custom_desc
            )

        assert exc_info.value.code == 0
        captured = capsys.readouterr()
        assert custom_desc in captured.out

    def test_build_config_from_cli_with_default_description(self, capsys):
        """Test build_config_from_cli without description uses default."""
        with pytest.raises(SystemExit) as exc_info:
            build_config_from_cli(SimpleConfig, args=["--help"])

        assert exc_info.value.code == 0
        captured = capsys.readouterr()
        assert "Build SimpleConfig from CLI" in captured.out

    def test_custom_description_does_not_affect_functionality(self):
        """Test that custom description doesn't change parsing behavior."""
        # Without description
        config1 = build_config(SimpleConfig, args=["--name", "test1", "--count", "100"])

        # With description
        config2 = build_config(
            SimpleConfig,
            args=["--name", "test1", "--count", "100"],
            description="Custom description",
        )

        assert config1.name == config2.name == "test1"
        assert config1.count == config2.count == 100

    def test_backward_compatibility_direct_builder(self):
        """Test that existing code using GenericConfigBuilder still works."""
        import argparse

        # Old pattern: GenericConfigBuilder without description
        builder = GenericConfigBuilder(SimpleConfig)
        parser = argparse.ArgumentParser(description="Custom parser")
        builder.add_arguments(parser)

        args = parser.parse_args(["--name", "legacy", "--count", "42"])
        config = builder.build_config(args)

        assert config.name == "legacy"
        assert config.count == 42

    def test_backward_compatibility_convenience_functions(self):
        """Test that existing convenience function calls still work."""
        # Old pattern: build_config without description
        config = build_config(SimpleConfig, args=["--name", "oldstyle"])

        assert config.name == "oldstyle"
        assert config.count == 10  # default

    def test_multiline_description(self, capsys):
        """Test that multiline descriptions work correctly."""
        multiline_desc = """Configure the application server.

This tool allows you to set various server parameters
including name, port, and other settings."""

        with pytest.raises(SystemExit) as exc_info:
            build_config(SimpleConfig, args=["--help"], description=multiline_desc)

        assert exc_info.value.code == 0
        captured = capsys.readouterr()
        # argparse may format this, but key parts should be present
        assert "Configure the application server" in captured.out

    def test_empty_string_description(self, capsys):
        """Test that empty string description is handled."""
        with pytest.raises(SystemExit) as exc_info:
            build_config(SimpleConfig, args=["--help"], description="")

        assert exc_info.value.code == 0
        captured = capsys.readouterr()
        # Empty description should be used (not default)
        assert "Build SimpleConfig from CLI" not in captured.out

    def test_description_with_special_characters(self, capsys):
        """Test description with special characters."""
        special_desc = "Config tool: <options> [required] {advanced}"

        with pytest.raises(SystemExit) as exc_info:
            build_config(SimpleConfig, args=["--help"], description=special_desc)

        assert exc_info.value.code == 0
        captured = capsys.readouterr()
        assert "Config tool:" in captured.out


class TestDescriptionWithComplexConfig:
    """Test description parameter with more complex configurations."""

    @dataclass
    class ComplexConfig:
        """Complex config with various field types."""

        host: str = "localhost"
        port: int = 8080
        debug: bool = False
        tags: Optional[List[str]] = None

        def __post_init__(self):
            if self.tags is None:
                self.tags = []

    def test_complex_config_with_description(self, capsys):
        """Test complex config with custom description."""
        desc = "Advanced server configuration with multiple options"

        with pytest.raises(SystemExit) as exc_info:
            build_config(self.ComplexConfig, args=["--help"], description=desc)

        assert exc_info.value.code == 0
        captured = capsys.readouterr()
        assert desc in captured.out
        # Should still show all the arguments
        assert "--host" in captured.out
        assert "--port" in captured.out
        assert "--debug" in captured.out

    def test_complex_config_parsing_with_description(self):
        """Test that complex config parsing works with description."""
        config = build_config(
            self.ComplexConfig,
            args=["--host", "0.0.0.0", "--port", "9000", "--debug"],
            description="Test configuration",
        )

        assert config.host == "0.0.0.0"
        assert config.port == 9000
        assert config.debug is True


class TestDescriptionEdgeCases:
    """Test edge cases and error conditions."""

    def test_none_description_explicitly(self):
        """Test explicitly passing None as description."""
        builder = GenericConfigBuilder(SimpleConfig, description=None)
        assert builder.description is None

    def test_description_type_validation(self):
        """Test that non-string descriptions work (argparse coerces to str)."""
        # argparse will convert to string, so this should work
        builder = GenericConfigBuilder(SimpleConfig, description=123)
        assert builder.description == 123

        # When used in ArgumentParser, argparse will handle conversion
        import argparse

        desc = builder.description or f"Build {builder.config_class.__name__} from CLI"
        parser = argparse.ArgumentParser(description=str(desc))
        assert "123" in parser.format_help()

    def test_very_long_description(self, capsys):
        """Test with a very long description."""
        long_desc = "A " + "very " * 100 + "long description."

        with pytest.raises(SystemExit) as exc_info:
            build_config(SimpleConfig, args=["--help"], description=long_desc)

        assert exc_info.value.code == 0
        captured = capsys.readouterr()
        # argparse will format it, but it should appear
        assert "very" in captured.out

    def test_description_with_unicode(self, capsys):
        """Test description with unicode characters."""
        unicode_desc = "配置工具 - Configuration Tool 🚀"

        with pytest.raises(SystemExit) as exc_info:
            build_config(SimpleConfig, args=["--help"], description=unicode_desc)

        assert exc_info.value.code == 0
        captured = capsys.readouterr()
        # Check for parts of the unicode string
        assert "Configuration Tool" in captured.out
