"""
Tests for cli_nested() functionality.

Tests cover:
- Basic nested dataclass support
- Three prefix modes (custom, none, auto)
- Field name collision detection
- Short option support and collision detection
- Config file merging with nested fields
- Partial overrides
- Multiple nested dataclasses
- Integration with other annotations
"""

import argparse
import json
import os
import tempfile
from dataclasses import dataclass
from typing import Dict, List, Optional

import pytest

from dataclass_args import (
    build_config,
    cli_choices,
    cli_help,
    cli_nested,
    cli_short,
    combine_annotations,
)
from dataclass_args.builder import GenericConfigBuilder
from dataclass_args.exceptions import ConfigBuilderError, ConfigurationError


class TestBasicNested:
    """Test basic nested dataclass functionality."""

    def test_custom_prefix(self):
        """Test nested dataclass with custom prefix."""

        @dataclass
        class DatabaseConfig:
            host: str = "localhost"
            port: int = 5432

        @dataclass
        class AppConfig:
            app_name: str = "myapp"
            db: DatabaseConfig = cli_nested(prefix="db", default_factory=DatabaseConfig)

        builder = GenericConfigBuilder(AppConfig)
        parser = argparse.ArgumentParser()
        builder.add_arguments(parser)

        args = parser.parse_args(
            ["--app-name", "TestApp", "--db-host", "prod.com", "--db-port", "3306"]
        )
        config = builder.build_config(args)

        assert config.app_name == "TestApp"
        assert config.db.host == "prod.com"
        assert config.db.port == 3306

    def test_no_prefix(self):
        """Test nested dataclass with no prefix (complete flattening)."""

        @dataclass
        class Credentials:
            username: str = "admin"
            password: str = "secret"

        @dataclass
        class AppConfig:
            app_name: str = "myapp"
            creds: Credentials = cli_nested(prefix="", default_factory=Credentials)

        builder = GenericConfigBuilder(AppConfig)
        parser = argparse.ArgumentParser()
        builder.add_arguments(parser)

        args = parser.parse_args(
            ["--app-name", "SecureApp", "--username", "john", "--password", "pass123"]
        )
        config = builder.build_config(args)

        assert config.app_name == "SecureApp"
        assert config.creds.username == "john"
        assert config.creds.password == "pass123"

    def test_auto_prefix(self):
        """Test nested dataclass with auto prefix (uses field name)."""

        @dataclass
        class LoggingConfig:
            level: str = "INFO"
            file: str = "app.log"

        @dataclass
        class AppConfig:
            app_name: str = "myapp"
            logging: LoggingConfig = cli_nested(default_factory=LoggingConfig)

        builder = GenericConfigBuilder(AppConfig)
        parser = argparse.ArgumentParser()
        builder.add_arguments(parser)

        args = parser.parse_args(
            [
                "--app-name",
                "LogApp",
                "--logging-level",
                "DEBUG",
                "--logging-file",
                "debug.log",
            ]
        )
        config = builder.build_config(args)

        assert config.app_name == "LogApp"
        assert config.logging.level == "DEBUG"
        assert config.logging.file == "debug.log"

    def test_partial_override(self):
        """Test that partial CLI overrides preserve other values."""

        @dataclass
        class ServerConfig:
            host: str = "default-host"
            port: int = 8080
            timeout: int = 30

        @dataclass
        class AppConfig:
            server: ServerConfig = cli_nested(prefix="s", default_factory=ServerConfig)

        builder = GenericConfigBuilder(AppConfig)
        parser = argparse.ArgumentParser()
        builder.add_arguments(parser)

        # Only override host
        args = parser.parse_args(["--s-host", "custom.com"])
        config = builder.build_config(args)

        assert config.server.host == "custom.com"
        assert config.server.port == 8080  # Default preserved
        assert config.server.timeout == 30  # Default preserved

    def test_multiple_nested(self):
        """Test multiple nested dataclasses in the same config."""

        @dataclass
        class DatabaseConfig:
            host: str = "db-host"

        @dataclass
        class CacheConfig:
            host: str = "cache-host"

        @dataclass
        class AppConfig:
            app_name: str = "app"
            db: DatabaseConfig = cli_nested(prefix="db", default_factory=DatabaseConfig)
            cache: CacheConfig = cli_nested(prefix="cache", default_factory=CacheConfig)

        builder = GenericConfigBuilder(AppConfig)
        parser = argparse.ArgumentParser()
        builder.add_arguments(parser)

        args = parser.parse_args(
            [
                "--app-name",
                "MultiApp",
                "--db-host",
                "postgres.com",
                "--cache-host",
                "redis.com",
            ]
        )
        config = builder.build_config(args)

        assert config.app_name == "MultiApp"
        assert config.db.host == "postgres.com"
        assert config.cache.host == "redis.com"


class TestCollisionDetection:
    """Test collision detection for nested fields."""

    def test_field_name_collision_with_no_prefix(self):
        """Test that field name collisions are detected when nested has no prefix."""

        @dataclass
        class Nested:
            name: str = "nested"

        @dataclass
        class Config:
            name: str = "parent"
            nested: Nested = cli_nested(prefix="", default_factory=Nested)

        with pytest.raises(ConfigBuilderError) as exc_info:
            GenericConfigBuilder(Config)

        assert "collision" in str(exc_info.value).lower()
        assert "--name" in str(exc_info.value)

    def test_no_collision_with_prefix(self):
        """Test that same field names don't collide when nested has prefix."""

        @dataclass
        class Nested:
            name: str = "nested"

        @dataclass
        class Config:
            name: str = "parent"
            nested: Nested = cli_nested(prefix="n", default_factory=Nested)

        # Should not raise
        builder = GenericConfigBuilder(Config)
        parser = argparse.ArgumentParser()
        builder.add_arguments(parser)

        args = parser.parse_args(["--name", "parent-name", "--n-name", "nested-name"])
        config = builder.build_config(args)

        assert config.name == "parent-name"
        assert config.nested.name == "nested-name"

    def test_collision_across_multiple_nested(self):
        """Test collision detection across multiple nested dataclasses."""

        @dataclass
        class Nested1:
            value: str = "val1"

        @dataclass
        class Nested2:
            value: str = "val2"

        @dataclass
        class Config:
            nested1: Nested1 = cli_nested(prefix="", default_factory=Nested1)
            nested2: Nested2 = cli_nested(prefix="", default_factory=Nested2)

        with pytest.raises(ConfigBuilderError) as exc_info:
            GenericConfigBuilder(Config)

        assert "collision" in str(exc_info.value).lower()


class TestShortOptions:
    """Test short option support for nested fields."""

    def test_short_options_with_no_prefix(self):
        """Test that short options work when nested has no prefix."""

        @dataclass
        class Credentials:
            username: str = cli_short("u", default="admin")
            password: str = cli_short("p", default="secret")

        @dataclass
        class AppConfig:
            app_name: str = cli_short("a", default="app")
            creds: Credentials = cli_nested(prefix="", default_factory=Credentials)

        builder = GenericConfigBuilder(AppConfig)
        parser = argparse.ArgumentParser()
        builder.add_arguments(parser)

        # Use short options
        args = parser.parse_args(["-a", "TestApp", "-u", "john", "-p", "pass123"])
        config = builder.build_config(args)

        assert config.app_name == "TestApp"
        assert config.creds.username == "john"
        assert config.creds.password == "pass123"

    def test_short_options_ignored_with_prefix(self):
        """Test that short options are ignored when nested has prefix."""

        @dataclass
        class Database:
            host: str = cli_short("d", default="localhost")
            port: int = cli_short("p", default=5432)

        @dataclass
        class AppConfig:
            port: int = cli_short("p", default=8080)  # Same -p
            db: Database = cli_nested(prefix="db", default_factory=Database)

        # Should not raise (no collision because db has prefix)
        builder = GenericConfigBuilder(AppConfig)
        parser = argparse.ArgumentParser()
        builder.add_arguments(parser)

        # -p should set AppConfig.port, not Database.port
        args = parser.parse_args(["-p", "9000"])
        config = builder.build_config(args)

        assert config.port == 9000
        assert config.db.port == 5432  # Default, not affected by -p

    def test_short_option_collision_with_no_prefix(self):
        """Test that short option collisions are detected."""

        @dataclass
        class Nested:
            host: str = cli_short("a", default="nested")

        @dataclass
        class Config:
            app_name: str = cli_short("a", default="app")
            nested: Nested = cli_nested(prefix="", default_factory=Nested)

        with pytest.raises(ConfigBuilderError) as exc_info:
            GenericConfigBuilder(Config)

        assert "short option collision" in str(exc_info.value).lower()
        assert "-a" in str(exc_info.value)


class TestConfigFileMerging:
    """Test merging base configs with nested dataclasses."""

    def test_base_config_only(self):
        """Test loading nested dataclass from base config file."""

        @dataclass
        class DatabaseConfig:
            host: str = "default-host"
            port: int = 5432

        @dataclass
        class AppConfig:
            app_name: str = "default-app"
            db: DatabaseConfig = cli_nested(prefix="db", default_factory=DatabaseConfig)

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            config_data = {
                "app_name": "from-config",
                "db": {"host": "config-host", "port": 3306},
            }
            json.dump(config_data, f)
            config_file = f.name

        try:
            builder = GenericConfigBuilder(AppConfig)
            parser = argparse.ArgumentParser()
            builder.add_arguments(parser)

            args = parser.parse_args(["--config", config_file])
            config = builder.build_config(args)

            assert config.app_name == "from-config"
            assert config.db.host == "config-host"
            assert config.db.port == 3306
        finally:
            os.unlink(config_file)

    def test_base_config_with_cli_overrides(self):
        """Test that CLI overrides properly override base config nested values."""

        @dataclass
        class DatabaseConfig:
            host: str = "default-host"
            port: int = 5432
            database: str = "default-db"

        @dataclass
        class AppConfig:
            app_name: str = "default-app"
            db: DatabaseConfig = cli_nested(prefix="db", default_factory=DatabaseConfig)

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            config_data = {
                "app_name": "from-config",
                "db": {"host": "config-host", "port": 3306, "database": "config-db"},
            }
            json.dump(config_data, f)
            config_file = f.name

        try:
            builder = GenericConfigBuilder(AppConfig)
            parser = argparse.ArgumentParser()
            builder.add_arguments(parser)

            # Override only host and port via CLI
            args = parser.parse_args(
                ["--config", config_file, "--db-host", "cli-host", "--db-port", "9999"]
            )
            config = builder.build_config(args)

            assert config.app_name == "from-config"  # From config file
            assert config.db.host == "cli-host"  # CLI override
            assert config.db.port == 9999  # CLI override
            assert (
                config.db.database == "config-db"
            )  # From config file (not overridden)
        finally:
            os.unlink(config_file)

    def test_programmatic_base_config(self):
        """Test programmatic base_configs with nested dataclasses."""

        @dataclass
        class DatabaseConfig:
            host: str = "default-host"
            port: int = 5432

        @dataclass
        class AppConfig:
            app_name: str = "default-app"
            db: DatabaseConfig = cli_nested(prefix="db", default_factory=DatabaseConfig)

        builder = GenericConfigBuilder(AppConfig)
        parser = argparse.ArgumentParser()
        builder.add_arguments(parser)

        args = parser.parse_args(["--db-port", "7777"])

        # Programmatic base config
        base_config = {
            "app_name": "base-app",
            "db": {"host": "base-host", "port": 3306},
        }

        config = builder.build_config(args, base_configs=base_config)

        assert config.app_name == "base-app"  # From base_configs
        assert config.db.host == "base-host"  # From base_configs
        assert config.db.port == 7777  # CLI override


class TestFieldTypes:
    """Test that nested dataclasses work with various field types."""

    def test_nested_with_list_field(self):
        """Test nested dataclass with list field."""

        @dataclass
        class Config:
            tags: List[str] = None

        @dataclass
        class AppConfig:
            nested: Config = cli_nested(
                prefix="n", default_factory=lambda: Config(tags=[])
            )

        builder = GenericConfigBuilder(AppConfig)
        parser = argparse.ArgumentParser()
        builder.add_arguments(parser)

        args = parser.parse_args(["--n-tags", "tag1", "tag2", "tag3"])
        config = builder.build_config(args)

        assert config.nested.tags == ["tag1", "tag2", "tag3"]

    def test_nested_with_boolean_field(self):
        """Test nested dataclass with boolean field."""

        @dataclass
        class FeatureFlags:
            enable_cache: bool = False
            enable_logging: bool = True

        @dataclass
        class AppConfig:
            features: FeatureFlags = cli_nested(
                prefix="feat", default_factory=FeatureFlags
            )

        builder = GenericConfigBuilder(AppConfig)
        parser = argparse.ArgumentParser()
        builder.add_arguments(parser)

        args = parser.parse_args(["--feat-enable-cache", "--no-feat-enable-logging"])
        config = builder.build_config(args)

        assert config.features.enable_cache is True
        assert config.features.enable_logging is False

    def test_nested_with_optional_field(self):
        """Test nested dataclass with optional field."""

        @dataclass
        class Config:
            optional_value: Optional[str] = None
            required_value: str = "required"

        @dataclass
        class AppConfig:
            nested: Config = cli_nested(prefix="n", default_factory=Config)

        builder = GenericConfigBuilder(AppConfig)
        parser = argparse.ArgumentParser()
        builder.add_arguments(parser)

        # Don't provide optional_value
        args = parser.parse_args(["--n-required-value", "test"])
        config = builder.build_config(args)

        assert config.nested.optional_value is None
        assert config.nested.required_value == "test"


class TestIntegrationWithOtherAnnotations:
    """Test that cli_nested works with other annotations."""

    def test_with_cli_help(self):
        """Test nested fields with custom help text."""

        @dataclass
        class DatabaseConfig:
            host: str = cli_help("Database hostname", default="localhost")
            port: int = cli_help("Database port number", default=5432)

        @dataclass
        class AppConfig:
            db: DatabaseConfig = cli_nested(prefix="db", default_factory=DatabaseConfig)

        builder = GenericConfigBuilder(AppConfig)
        parser = argparse.ArgumentParser()
        builder.add_arguments(parser)

        # Check that help text is preserved
        args = parser.parse_args(["--db-host", "test.com"])
        config = builder.build_config(args)

        assert config.db.host == "test.com"

    def test_with_cli_choices(self):
        """Test nested fields with choices."""

        @dataclass
        class LogConfig:
            level: str = cli_choices(
                ["DEBUG", "INFO", "WARNING", "ERROR"], default="INFO"
            )

        @dataclass
        class AppConfig:
            logging: LogConfig = cli_nested(prefix="log", default_factory=LogConfig)

        builder = GenericConfigBuilder(AppConfig)
        parser = argparse.ArgumentParser()
        builder.add_arguments(parser)

        # Valid choice
        args = parser.parse_args(["--log-level", "DEBUG"])
        config = builder.build_config(args)
        assert config.logging.level == "DEBUG"

        # Invalid choice should raise
        with pytest.raises(SystemExit):
            parser.parse_args(["--log-level", "INVALID"])

    def test_with_combined_annotations(self):
        """Test nested fields with combined annotations."""

        @dataclass
        class ServerConfig:
            host: str = combine_annotations(
                cli_short("h"), cli_help("Server hostname"), default="localhost"
            )

        @dataclass
        class AppConfig:
            # With prefix - short option ignored
            server1: ServerConfig = cli_nested(
                prefix="s1", default_factory=ServerConfig
            )
            # No prefix - short option enabled
            server2: ServerConfig = cli_nested(
                prefix="s2", default_factory=ServerConfig
            )

        builder = GenericConfigBuilder(AppConfig)
        parser = argparse.ArgumentParser()
        builder.add_arguments(parser)

        args = parser.parse_args(["--s1-host", "srv1.com", "--s2-host", "srv2.com"])
        config = builder.build_config(args)

        assert config.server1.host == "srv1.com"
        assert config.server2.host == "srv2.com"


class TestEdgeCases:
    """Test edge cases and error conditions."""

    def test_empty_nested_dataclass(self):
        """Test nested dataclass with no fields."""

        @dataclass
        class EmptyConfig:
            pass

        @dataclass
        class AppConfig:
            app_name: str = "app"
            empty: EmptyConfig = cli_nested(prefix="e", default_factory=EmptyConfig)

        builder = GenericConfigBuilder(AppConfig)
        parser = argparse.ArgumentParser()
        builder.add_arguments(parser)

        args = parser.parse_args(["--app-name", "TestApp"])
        config = builder.build_config(args)

        assert config.app_name == "TestApp"
        assert isinstance(config.empty, EmptyConfig)

    def test_nested_with_defaults_only(self):
        """Test nested dataclass where all fields have defaults."""

        @dataclass
        class AllDefaults:
            field1: str = "default1"
            field2: int = 42
            field3: bool = True

        @dataclass
        class AppConfig:
            nested: AllDefaults = cli_nested(prefix="n", default_factory=AllDefaults)

        builder = GenericConfigBuilder(AppConfig)
        parser = argparse.ArgumentParser()
        builder.add_arguments(parser)

        # Parse with no arguments
        args = parser.parse_args([])
        config = builder.build_config(args)

        assert config.nested.field1 == "default1"
        assert config.nested.field2 == 42
        assert config.nested.field3 is True

    def test_positional_args_in_nested_raises_error(self):
        """Test that positional arguments in nested dataclasses raise error."""
        from dataclass_args import cli_positional

        @dataclass
        class Nested:
            pos_arg: str = cli_positional(default="default_value")

        @dataclass
        class Config:
            nested: Nested = cli_nested(prefix="n", default_factory=Nested)

        builder = GenericConfigBuilder(Config)
        parser = argparse.ArgumentParser()

        with pytest.raises(ConfigBuilderError) as exc_info:
            builder.add_arguments(parser)

        assert "positional" in str(exc_info.value).lower()
        assert "not supported" in str(exc_info.value).lower()


class TestBuildConfigHelperFunction:
    """Test the build_config() helper function with nested dataclasses."""

    def test_build_config_with_nested(self, monkeypatch):
        """Test build_config() helper with nested dataclass."""

        @dataclass
        class DatabaseConfig:
            host: str = "localhost"
            port: int = 5432

        @dataclass
        class AppConfig:
            app_name: str = "myapp"
            db: DatabaseConfig = cli_nested(prefix="db", default_factory=DatabaseConfig)

        # Simulate command line
        test_args = ["test_prog", "--app-name", "TestApp", "--db-host", "prod.com"]
        monkeypatch.setattr("sys.argv", test_args)

        config = build_config(AppConfig)

        assert config.app_name == "TestApp"
        assert config.db.host == "prod.com"
        assert config.db.port == 5432


class TestNestedProcessorErrorPaths:
    """Tests for error handling in nested_processor.py."""

    def test_nested_dict_field_from_file(self):
        """Nested dict field loads from file via load_structured_file."""
        from typing import Any

        @dataclass
        class SettingsConfig:
            settings: Dict[str, Any] = None

        @dataclass
        class AppConfig:
            app_name: str = "test"
            config: SettingsConfig = cli_nested(
                prefix="n", default_factory=SettingsConfig
            )

        # Create a JSON file with dict content
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump({"key1": "value1", "port": 8080}, f)
            temp_path = f.name

        try:
            result = build_config(AppConfig, ["--n-settings", temp_path])
            assert result.config.settings == {"key1": "value1", "port": 8080}
        finally:
            os.unlink(temp_path)

    def test_nested_dict_field_nonexistent_file_error(self):
        """Nested dict field with nonexistent file raises error."""
        from typing import Any

        from dataclass_args.exceptions import ConfigurationError

        @dataclass
        class SettingsConfig:
            settings: Dict[str, Any] = None

        @dataclass
        class AppConfig:
            app_name: str = "test"
            config: SettingsConfig = cli_nested(
                prefix="n", default_factory=SettingsConfig
            )

        with pytest.raises((ConfigurationError, SystemExit)):
            build_config(AppConfig, ["--n-settings", "/nonexistent/file.json"])

    def test_nested_dict_field_with_property_overrides(self):
        """Nested dict field supports property overrides."""
        from typing import Any

        @dataclass
        class SettingsConfig:
            settings: Dict[str, Any] = None

        @dataclass
        class AppConfig:
            app_name: str = "test"
            config: SettingsConfig = cli_nested(
                prefix="n", default_factory=SettingsConfig
            )

        # Create a JSON file with base config
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump({"host": "localhost", "port": 5432}, f)
            temp_path = f.name

        try:
            result = build_config(
                AppConfig,
                ["--n-settings", temp_path, "--n-s", "port:9999"],
            )
            assert result.config.settings["host"] == "localhost"
            assert result.config.settings["port"] == 9999
        finally:
            os.unlink(temp_path)

    def test_nested_reconstruction_failure(self):
        """Nested dataclass construction failure raises ConfigurationError."""
        from dataclass_args.exceptions import ConfigurationError

        @dataclass
        class ValidatedConfig:
            host: str = "localhost"
            port: int = 5432

            def __post_init__(self):
                if self.port < 0:
                    raise ValueError(f"port must be non-negative, got {self.port}")

        @dataclass
        class AppConfig:
            app_name: str = "test"
            server: ValidatedConfig = cli_nested(
                prefix="srv", default_factory=ValidatedConfig
            )

        with pytest.raises(
            ConfigurationError, match="Failed to create nested dataclass"
        ):
            build_config(AppConfig, ["--srv-port", "-1"])

    def test_nested_file_loadable_error(self):
        """Nested file-loadable field with bad path raises ConfigurationError."""
        from dataclass_args import cli_file_loadable
        from dataclass_args.exceptions import ConfigurationError

        @dataclass
        class ContentConfig:
            content: str = cli_file_loadable(default="")

        @dataclass
        class AppConfig:
            app_name: str = "test"
            docs: ContentConfig = cli_nested(
                prefix="doc", default_factory=ContentConfig
            )

        with pytest.raises((ConfigurationError, SystemExit)):
            build_config(AppConfig, ["--doc-content", "@/nonexistent/path.txt"])

    def test_nested_with_prebuilt_dataclass_in_base_configs(self):
        """Pre-built dataclass in base_configs gets merged with CLI overrides."""

        @dataclass
        class DatabaseConfig:
            host: str = "localhost"
            port: int = 5432

        @dataclass
        class AppConfig:
            name: str = "app"
            db: DatabaseConfig = cli_nested(prefix="db", default_factory=DatabaseConfig)

        # Pre-built instance in base_configs
        prebuilt = DatabaseConfig(host="prebuilt-host", port=9999)
        result = build_config(
            AppConfig,
            args=["--db-port", "3306"],
            base_configs={"db": prebuilt},
        )
        # host from prebuilt, port overridden by CLI
        assert result.db.host == "prebuilt-host"
        assert result.db.port == 3306

    def test_nested_with_non_dict_non_dataclass_in_config(self):
        """Non-dict non-dataclass value for a nested field raises ConfigurationError (F5)."""

        @dataclass
        class DatabaseConfig:
            host: str = "localhost"
            port: int = 5432

        @dataclass
        class AppConfig:
            name: str = "app"
            db: DatabaseConfig = cli_nested(prefix="db", default_factory=DatabaseConfig)

        # String value (invalid type for nested field) in base_configs
        with pytest.raises(ConfigurationError) as exc:
            build_config(
                AppConfig,
                args=["--db-host", "cli-host"],
                base_configs={"db": "invalid_string_value"},
            )
        assert "'db'" in str(exc.value)
        assert "DatabaseConfig" in str(exc.value)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])


class TestAdditionalCoverage:
    """Additional tests to improve code coverage."""

    def test_nested_field_with_choices(self):
        """Test that choices work in nested fields."""

        @dataclass
        class LogConfig:
            level: str = cli_choices(["DEBUG", "INFO", "WARNING"], default="INFO")

        @dataclass
        class Config:
            log: LogConfig = cli_nested(prefix="log", default_factory=LogConfig)

        builder = GenericConfigBuilder(Config)
        parser = argparse.ArgumentParser()
        builder.add_arguments(parser)

        args = parser.parse_args(["--log-level", "DEBUG"])
        config = builder.build_config(args)

        assert config.log.level == "DEBUG"

    def test_is_cli_nested_helper(self):
        """Test is_cli_nested() helper function."""
        from dataclass_args.annotations import is_cli_nested

        @dataclass
        class Nested:
            value: str = "test"

        @dataclass
        class Config:
            nested: Nested = cli_nested(prefix="n", default_factory=Nested)
            regular: str = "regular"

        # Analyze fields
        from dataclasses import fields

        for field in fields(Config):
            info = {"field_obj": field}
            if field.name == "nested":
                assert is_cli_nested(info) is True
            else:
                assert is_cli_nested(info) is False

    def test_get_cli_nested_prefix_helper(self):
        """Test get_cli_nested_prefix() helper function."""
        from dataclass_args.annotations import get_cli_nested_prefix

        @dataclass
        class Nested:
            value: str = "test"

        @dataclass
        class Config:
            nested1: Nested = cli_nested(prefix="custom", default_factory=Nested)
            nested2: Nested = cli_nested(prefix="", default_factory=Nested)
            nested3: Nested = cli_nested(default_factory=Nested)

        from dataclasses import fields

        for field in fields(Config):
            info = {"field_obj": field}
            prefix = get_cli_nested_prefix(info)
            if field.name == "nested1":
                assert prefix == "custom"
            elif field.name == "nested2":
                assert prefix == ""
            elif field.name == "nested3":
                assert prefix is None
