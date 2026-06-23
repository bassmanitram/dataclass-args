"""
Tests for cli_resolve() functionality.

Tests cover:
- Basic dict → resolved object
- None bypass (resolver not called)
- Config file loading → resolution
- Property overrides applied before resolution
- base_configs with pre-built object → resolver handles pass-through
- Resolver error → ConfigurationError wrapping
- ConfigurationError from resolver → re-raised without double-wrapping
- combine_annotations compatibility
- Optional[T] with default=None
- Required field not provided → appropriate error
- cli_help interaction (help text correct)
- cli_short interaction (short option works)
- Property override on non-dict pre-built object → ConfigurationError
- Incompatibility with cli_positional/cli_append/cli_exclude/cli_file_loadable
- cli_resolve in nested dataclasses (accepted, resolver not called by library)
"""

import argparse
import json
import os
import tempfile
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import pytest

from dataclass_args import (
    ConfigBuilderError,
    ConfigurationError,
    build_config,
    cli_append,
    cli_exclude,
    cli_file_loadable,
    cli_help,
    cli_nested,
    cli_positional,
    cli_resolve,
    cli_short,
    combine_annotations,
    get_cli_resolver,
    is_cli_resolve,
)
from dataclass_args.builder import GenericConfigBuilder

# ============================================================================
# Test Fixtures - Resolver functions and dataclasses
# ============================================================================


class SandboxBase:
    """Base class for sandbox implementations."""

    pass


class DockerSandbox(SandboxBase):
    """Docker-based sandbox."""

    def __init__(self, image: str, memory: str = "512m"):
        self.image = image
        self.memory = memory

    def __eq__(self, other):
        return (
            isinstance(other, DockerSandbox)
            and self.image == other.image
            and self.memory == other.memory
        )


class LocalSandbox(SandboxBase):
    """Local sandbox for development."""

    def __init__(self, path: str = "/tmp"):
        self.path = path

    def __eq__(self, other):
        return isinstance(other, LocalSandbox) and self.path == other.path


def resolve_sandbox(value: Any) -> SandboxBase:
    """Resolver that converts a dict to a Sandbox instance."""
    if isinstance(value, dict):
        sandbox_type = value.get("type", "local")
        if sandbox_type == "docker":
            return DockerSandbox(
                image=value.get("image", "python:3.11"),
                memory=value.get("memory", "512m"),
            )
        elif sandbox_type == "local":
            return LocalSandbox(path=value.get("path", "/tmp"))
        else:
            raise ValueError(f"Unknown sandbox type: {sandbox_type}")
    # Pass-through for pre-built objects
    return value


def resolve_with_config_error(value: Any) -> Any:
    """Resolver that raises ConfigurationError."""
    raise ConfigurationError("Custom config error from resolver")


def resolve_with_generic_error(value: Any) -> Any:
    """Resolver that raises a generic error."""
    raise RuntimeError("Something went wrong in resolver")


def resolve_identity(value: Any) -> Any:
    """Identity resolver - returns value unchanged."""
    return value


# ============================================================================
# Test Classes
# ============================================================================


class TestBasicResolve:
    """Test basic cli_resolve functionality."""

    def test_dict_to_resolved_object(self):
        """Test basic dict → resolved object transformation."""

        @dataclass
        class Config:
            sandbox: Optional[SandboxBase] = combine_annotations(
                cli_resolve(resolver=resolve_sandbox),
                default=None,
            )

        config = build_config(
            Config,
            args=[],
            base_configs={"sandbox": {"type": "docker", "image": "node:18"}},
        )

        assert isinstance(config.sandbox, DockerSandbox)
        assert config.sandbox.image == "node:18"

    def test_none_bypass(self):
        """Test that resolver is NOT called when value is None."""
        call_count = {"calls": 0}

        def counting_resolver(value):
            call_count["calls"] += 1
            return value

        @dataclass
        class Config:
            sandbox: Optional[SandboxBase] = combine_annotations(
                cli_resolve(resolver=counting_resolver),
                default=None,
            )

        config = build_config(Config, args=[])

        assert config.sandbox is None
        assert call_count["calls"] == 0

    def test_resolver_always_called_for_non_none(self):
        """Test that resolver is always called for non-None values."""
        call_count = {"calls": 0}

        def counting_resolver(value):
            call_count["calls"] += 1
            return DockerSandbox(image="counted")

        @dataclass
        class Config:
            sandbox: Optional[SandboxBase] = combine_annotations(
                cli_resolve(resolver=counting_resolver),
                default=None,
            )

        config = build_config(
            Config,
            args=[],
            base_configs={"sandbox": {"type": "docker"}},
        )

        assert call_count["calls"] == 1
        assert isinstance(config.sandbox, DockerSandbox)

    def test_resolver_with_local_sandbox(self):
        """Test resolver producing different object types."""

        @dataclass
        class Config:
            sandbox: Optional[SandboxBase] = combine_annotations(
                cli_resolve(resolver=resolve_sandbox),
                default=None,
            )

        config = build_config(
            Config,
            args=[],
            base_configs={"sandbox": {"type": "local", "path": "/var/sandbox"}},
        )

        assert isinstance(config.sandbox, LocalSandbox)
        assert config.sandbox.path == "/var/sandbox"


class TestConfigFileLoading:
    """Test cli_resolve with config file loading."""

    def test_load_from_cli_file_path(self):
        """Test loading dict from a file path via CLI and resolving."""

        @dataclass
        class Config:
            name: str = "app"
            sandbox: Optional[SandboxBase] = combine_annotations(
                cli_resolve(resolver=resolve_sandbox),
                default=None,
            )

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump({"type": "docker", "image": "alpine:3.18", "memory": "1g"}, f)
            config_file = f.name

        try:
            config = build_config(Config, args=["--sandbox", config_file])

            assert config.name == "app"
            assert isinstance(config.sandbox, DockerSandbox)
            assert config.sandbox.image == "alpine:3.18"
            assert config.sandbox.memory == "1g"
        finally:
            os.unlink(config_file)

    def test_load_from_config_flag(self):
        """Test loading via --config file with nested dict for resolve field."""

        @dataclass
        class Config:
            name: str = "app"
            sandbox: Optional[SandboxBase] = combine_annotations(
                cli_resolve(resolver=resolve_sandbox),
                default=None,
            )

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(
                {
                    "name": "FromConfig",
                    "sandbox": {"type": "docker", "image": "go:1.21"},
                },
                f,
            )
            config_file = f.name

        try:
            config = build_config(Config, args=["--config", config_file])

            assert config.name == "FromConfig"
            assert isinstance(config.sandbox, DockerSandbox)
            assert config.sandbox.image == "go:1.21"
        finally:
            os.unlink(config_file)


class TestPropertyOverrides:
    """Test property overrides applied before resolution."""

    def test_overrides_applied_before_resolution(self):
        """Test that property overrides modify dict before resolver is called."""

        @dataclass
        class Config:
            sandbox: Optional[SandboxBase] = combine_annotations(
                cli_resolve(resolver=resolve_sandbox),
                default=None,
            )

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump({"type": "docker", "image": "python:3.9"}, f)
            config_file = f.name

        try:
            # Apply override to change the image
            config = build_config(
                Config, args=["--sandbox", config_file, "--s", "image:python:3.12"]
            )

            assert isinstance(config.sandbox, DockerSandbox)
            assert config.sandbox.image == "python:3.12"
        finally:
            os.unlink(config_file)

    def test_override_on_non_dict_pre_built_raises_error(self):
        """Test that property overrides on pre-built objects raise ConfigurationError."""

        @dataclass
        class Config:
            sandbox: Optional[SandboxBase] = combine_annotations(
                cli_resolve(resolver=resolve_sandbox),
                default=None,
            )

        # Pre-built object from base_configs (not a dict)
        pre_built = DockerSandbox(image="pre-built:latest")

        with pytest.raises(ConfigurationError) as exc_info:
            build_config(
                Config,
                args=["--s", "image:changed"],
                base_configs={"sandbox": pre_built},
            )

        assert "Cannot apply property overrides" in str(exc_info.value)
        assert "not a dict" in str(exc_info.value)


class TestPreBuiltObjects:
    """Test base_configs with pre-built objects (resolver handles pass-through)."""

    def test_pre_built_object_pass_through(self):
        """Test that resolver handles pre-built objects via pass-through."""

        @dataclass
        class Config:
            sandbox: Optional[SandboxBase] = combine_annotations(
                cli_resolve(resolver=resolve_sandbox),
                default=None,
            )

        pre_built = DockerSandbox(image="pre-built:latest", memory="2g")

        config = build_config(
            Config,
            args=[],
            base_configs={"sandbox": pre_built},
        )

        # resolve_sandbox returns non-dict values as-is
        assert isinstance(config.sandbox, DockerSandbox)
        assert config.sandbox.image == "pre-built:latest"
        assert config.sandbox.memory == "2g"

    def test_cli_file_overrides_pre_built_object(self):
        """Test that CLI file path overrides a pre-built object from base_configs."""

        @dataclass
        class Config:
            sandbox: Optional[SandboxBase] = combine_annotations(
                cli_resolve(resolver=resolve_sandbox),
                default=None,
            )

        pre_built = DockerSandbox(image="pre-built:latest")

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump({"type": "local", "path": "/opt/sandbox"}, f)
            config_file = f.name

        try:
            config = build_config(
                Config,
                args=["--sandbox", config_file],
                base_configs={"sandbox": pre_built},
            )

            # CLI file overrides pre-built - now a dict from file, resolved to LocalSandbox
            assert isinstance(config.sandbox, LocalSandbox)
            assert config.sandbox.path == "/opt/sandbox"
        finally:
            os.unlink(config_file)


class TestErrorHandling:
    """Test error handling in resolution."""

    def test_generic_error_wrapped_in_configuration_error(self):
        """Test that generic resolver errors are wrapped in ConfigurationError."""

        @dataclass
        class Config:
            sandbox: Optional[Any] = combine_annotations(
                cli_resolve(resolver=resolve_with_generic_error),
                default=None,
            )

        with pytest.raises(ConfigurationError) as exc_info:
            build_config(
                Config,
                args=[],
                base_configs={"sandbox": {"type": "docker"}},
            )

        assert "Failed to resolve field 'sandbox'" in str(exc_info.value)
        assert "Something went wrong" in str(exc_info.value)

    def test_configuration_error_re_raised_without_wrapping(self):
        """Test that ConfigurationError from resolver is re-raised without double-wrapping."""

        @dataclass
        class Config:
            sandbox: Optional[Any] = combine_annotations(
                cli_resolve(resolver=resolve_with_config_error),
                default=None,
            )

        with pytest.raises(ConfigurationError) as exc_info:
            build_config(
                Config,
                args=[],
                base_configs={"sandbox": {"type": "docker"}},
            )

        # Should be the exact message from resolver, not wrapped
        assert str(exc_info.value) == "Custom config error from resolver"

    def test_invalid_resolver_not_callable(self):
        """Test that non-callable resolver raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            cli_resolve(resolver="not_callable")

        assert "must be callable" in str(exc_info.value)

    def test_resolver_value_error(self):
        """Test that ValueError from resolver is wrapped."""

        def bad_resolver(value):
            raise ValueError("Invalid config format")

        @dataclass
        class Config:
            backend: Optional[Any] = combine_annotations(
                cli_resolve(resolver=bad_resolver),
                default=None,
            )

        with pytest.raises(ConfigurationError) as exc_info:
            build_config(
                Config,
                args=[],
                base_configs={"backend": {"invalid": True}},
            )

        assert "Failed to resolve field 'backend'" in str(exc_info.value)


class TestCombineAnnotations:
    """Test cli_resolve with combine_annotations."""

    def test_with_cli_help(self):
        """Test cli_resolve combined with cli_help."""

        @dataclass
        class Config:
            sandbox: Optional[SandboxBase] = combine_annotations(
                cli_resolve(resolver=resolve_sandbox),
                cli_help("Sandbox configuration file"),
                default=None,
            )

        # Should parse without error
        builder = GenericConfigBuilder(Config)
        parser = argparse.ArgumentParser()
        builder.add_arguments(parser)

        # Verify help text is present
        help_text = parser.format_help()
        assert "Sandbox configuration file" in help_text

    def test_with_cli_short(self):
        """Test cli_resolve combined with cli_short."""

        @dataclass
        class Config:
            sandbox: Optional[SandboxBase] = combine_annotations(
                cli_resolve(resolver=resolve_sandbox),
                cli_short("s"),
                default=None,
            )

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump({"type": "docker", "image": "rust:1.70"}, f)
            config_file = f.name

        try:
            # Use short option
            config = build_config(Config, args=["-s", config_file])

            assert isinstance(config.sandbox, DockerSandbox)
            assert config.sandbox.image == "rust:1.70"
        finally:
            os.unlink(config_file)

    def test_with_cli_help_and_cli_short(self):
        """Test cli_resolve combined with both cli_help and cli_short."""

        @dataclass
        class Config:
            sandbox: Optional[SandboxBase] = combine_annotations(
                cli_resolve(resolver=resolve_sandbox),
                cli_short("x"),
                cli_help("Sandbox config"),
                default=None,
            )

        builder = GenericConfigBuilder(Config)
        parser = argparse.ArgumentParser()
        builder.add_arguments(parser)

        help_text = parser.format_help()
        assert "Sandbox config" in help_text
        assert "-x" in help_text


class TestOptionalAndRequired:
    """Test Optional[T] and required field behaviors."""

    def test_optional_with_default_none(self):
        """Test Optional field with default=None (not required)."""

        @dataclass
        class Config:
            name: str = "app"
            sandbox: Optional[SandboxBase] = combine_annotations(
                cli_resolve(resolver=resolve_sandbox),
                default=None,
            )

        config = build_config(Config, args=["--name", "test"])

        assert config.name == "test"
        assert config.sandbox is None

    def test_optional_field_provided_via_base_configs(self):
        """Test optional field provided via base_configs."""

        @dataclass
        class Config:
            sandbox: Optional[SandboxBase] = combine_annotations(
                cli_resolve(resolver=resolve_sandbox),
                default=None,
            )

        config = build_config(
            Config,
            args=[],
            base_configs={"sandbox": {"type": "docker", "image": "ubuntu:22.04"}},
        )

        assert isinstance(config.sandbox, DockerSandbox)
        assert config.sandbox.image == "ubuntu:22.04"


class TestIncompatibleAnnotations:
    """Test that cli_resolve raises errors with incompatible annotations."""

    def test_incompatible_with_cli_positional(self):
        """Test that cli_resolve cannot be combined with cli_positional."""

        @dataclass
        class Config:
            sandbox: Optional[Any] = combine_annotations(
                cli_resolve(resolver=resolve_identity),
                cli_positional(),
                default=None,
            )

        with pytest.raises(ConfigBuilderError) as exc_info:
            GenericConfigBuilder(Config)

        assert "cli_resolve cannot be combined with" in str(exc_info.value)
        assert "cli_positional" in str(exc_info.value)

    def test_incompatible_with_cli_append(self):
        """Test that cli_resolve cannot be combined with cli_append."""

        @dataclass
        class Config:
            sandbox: Optional[Any] = combine_annotations(
                cli_resolve(resolver=resolve_identity),
                cli_append(),
                default_factory=list,
            )

        with pytest.raises(ConfigBuilderError) as exc_info:
            GenericConfigBuilder(Config)

        assert "cli_resolve cannot be combined with" in str(exc_info.value)
        assert "cli_append" in str(exc_info.value)

    def test_incompatible_with_cli_exclude(self):
        """Test that cli_resolve cannot be combined with cli_exclude."""

        @dataclass
        class Config:
            name: str = "app"
            sandbox: Optional[Any] = combine_annotations(
                cli_resolve(resolver=resolve_identity),
                cli_exclude(),
                default=None,
            )

        with pytest.raises(ConfigBuilderError) as exc_info:
            GenericConfigBuilder(Config)

        assert "cli_resolve cannot be combined with" in str(exc_info.value)
        assert "cli_exclude" in str(exc_info.value)

    def test_incompatible_with_cli_file_loadable(self):
        """Test that cli_resolve cannot be combined with cli_file_loadable."""

        @dataclass
        class Config:
            sandbox: Optional[Any] = combine_annotations(
                cli_resolve(resolver=resolve_identity),
                cli_file_loadable(),
                default=None,
            )

        with pytest.raises(ConfigBuilderError) as exc_info:
            GenericConfigBuilder(Config)

        assert "cli_resolve cannot be combined with" in str(exc_info.value)
        assert "cli_file_loadable" in str(exc_info.value)

    def test_incompatible_with_cli_nested(self):
        """Test that cli_resolve cannot be combined with cli_nested."""

        @dataclass
        class Inner:
            value: str = "test"

        @dataclass
        class Config:
            sandbox: Inner = combine_annotations(
                cli_resolve(resolver=resolve_identity),
                cli_nested(prefix="sb"),
                default_factory=Inner,
            )

        with pytest.raises(ConfigBuilderError) as exc_info:
            GenericConfigBuilder(Config)

        assert "cli_resolve cannot be combined with" in str(exc_info.value)
        assert "cli_nested" in str(exc_info.value)

    def test_multiple_incompatible_annotations_all_listed(self):
        """Test that all incompatible annotations are listed in error."""

        @dataclass
        class Config:
            sandbox: Optional[Any] = combine_annotations(
                cli_resolve(resolver=resolve_identity),
                cli_positional(),
                cli_file_loadable(),
                default=None,
            )

        with pytest.raises(ConfigBuilderError) as exc_info:
            GenericConfigBuilder(Config)

        error_msg = str(exc_info.value)
        assert "cli_positional" in error_msg
        assert "cli_file_loadable" in error_msg


class TestNestedDataclassSupport:
    """Test that cli_resolve works inside nested dataclasses (resolver not called by library)."""

    def test_cli_resolve_in_nested_accepted(self):
        """Test that cli_resolve inside a nested dataclass does NOT raise."""

        @dataclass
        class InnerConfig:
            backend: Optional[Any] = combine_annotations(
                cli_resolve(resolver=resolve_identity),
                default=None,
            )

        @dataclass
        class Config:
            name: str = "app"
            inner: InnerConfig = cli_nested(prefix="i", default_factory=InnerConfig)

        # Should NOT raise - cli_resolve is allowed in nested dataclasses
        builder = GenericConfigBuilder(Config)
        assert builder is not None

    def test_nested_resolve_field_value_stays_raw(self):
        """Test that resolver is NOT called for nested cli_resolve fields."""
        call_count = {"calls": 0}

        def counting_resolver(value):
            call_count["calls"] += 1
            return {"resolved": True}

        @dataclass
        class InnerConfig:
            name: str = "inner"
            backend: Optional[Any] = combine_annotations(
                cli_resolve(resolver=counting_resolver),
                default=None,
            )

        @dataclass
        class Config:
            app_name: str = "app"
            inner: InnerConfig = cli_nested(prefix="i", default_factory=InnerConfig)

        # Provide a value for the nested resolve field via base_configs
        config = build_config(
            Config,
            args=[],
            base_configs={"inner": {"name": "test", "backend": {"type": "redis"}}},
        )

        # Resolver should NOT have been called (library doesn't resolve nested fields)
        assert call_count["calls"] == 0
        # Value should remain as raw dict (not resolved)
        assert config.inner.backend == {"type": "redis"}
        assert config.inner.name == "test"

    def test_nested_resolve_field_none_default(self):
        """Test nested cli_resolve field with None default works correctly."""

        @dataclass
        class InnerConfig:
            backend: Optional[Any] = combine_annotations(
                cli_resolve(resolver=resolve_identity),
                default=None,
            )

        @dataclass
        class Config:
            app_name: str = "app"
            inner: InnerConfig = cli_nested(prefix="i", default_factory=InnerConfig)

        config = build_config(Config, args=["--app-name", "test"])

        assert config.inner.backend is None

    def test_nested_resolve_with_cli_override(self):
        """Test nested cli_resolve field can receive value from CLI (as dict file path)."""

        @dataclass
        class InnerConfig:
            name: str = "inner"
            settings: Optional[Any] = combine_annotations(
                cli_resolve(resolver=resolve_identity),
                default=None,
            )

        @dataclass
        class Config:
            app_name: str = "app"
            inner: InnerConfig = cli_nested(prefix="i", default_factory=InnerConfig)

        # Provide settings via a JSON file on CLI
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump({"host": "localhost", "port": 5432}, f)
            config_file = f.name

        try:
            config = build_config(Config, args=["--i-settings", config_file])

            # Value loaded from file but NOT resolved (stays as dict)
            assert config.inner.settings == {"host": "localhost", "port": 5432}
        finally:
            os.unlink(config_file)


class TestMetadataAccessors:
    """Test is_cli_resolve() and get_cli_resolver() accessors."""

    def test_is_cli_resolve_true(self):
        """Test is_cli_resolve returns True for annotated fields."""

        @dataclass
        class Config:
            sandbox: Optional[Any] = combine_annotations(
                cli_resolve(resolver=resolve_sandbox),
                default=None,
            )

        from dataclasses import fields as dc_fields

        field_obj = dc_fields(Config)[0]
        info = {"field_obj": field_obj}

        assert is_cli_resolve(info) is True

    def test_is_cli_resolve_false(self):
        """Test is_cli_resolve returns False for non-annotated fields."""

        @dataclass
        class Config:
            name: str = "app"

        from dataclasses import fields as dc_fields

        field_obj = dc_fields(Config)[0]
        info = {"field_obj": field_obj}

        assert is_cli_resolve(info) is False

    def test_get_cli_resolver(self):
        """Test get_cli_resolver returns the resolver function."""

        @dataclass
        class Config:
            sandbox: Optional[Any] = combine_annotations(
                cli_resolve(resolver=resolve_sandbox),
                default=None,
            )

        from dataclasses import fields as dc_fields

        field_obj = dc_fields(Config)[0]
        info = {"field_obj": field_obj}

        resolver = get_cli_resolver(info)
        assert resolver is resolve_sandbox

    def test_get_cli_resolver_none_for_regular_field(self):
        """Test get_cli_resolver returns None for non-resolve fields."""

        @dataclass
        class Config:
            name: str = "app"

        from dataclasses import fields as dc_fields

        field_obj = dc_fields(Config)[0]
        info = {"field_obj": field_obj}

        assert get_cli_resolver(info) is None


class TestBuildConfigHelperFunction:
    """Test the build_config() helper function with cli_resolve."""

    def test_build_config_end_to_end(self):
        """Test complete end-to-end with build_config()."""

        @dataclass
        class AppConfig:
            name: str = "myapp"
            sandbox: Optional[SandboxBase] = combine_annotations(
                cli_resolve(resolver=resolve_sandbox),
                cli_help("Sandbox configuration"),
                default=None,
            )

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump({"type": "docker", "image": "python:3.11", "memory": "1g"}, f)
            config_file = f.name

        try:
            config = build_config(
                AppConfig, args=["--name", "TestApp", "--sandbox", config_file]
            )

            assert config.name == "TestApp"
            assert isinstance(config.sandbox, DockerSandbox)
            assert config.sandbox.image == "python:3.11"
            assert config.sandbox.memory == "1g"
        finally:
            os.unlink(config_file)


class TestMultipleResolveFields:
    """Test multiple cli_resolve fields in the same dataclass."""

    def test_two_resolve_fields(self):
        """Test dataclass with two cli_resolve fields."""

        def resolve_backend(value):
            if isinstance(value, dict):
                return f"backend:{value.get('type', 'unknown')}"
            return value

        def resolve_cache(value):
            if isinstance(value, dict):
                return f"cache:{value.get('engine', 'unknown')}"
            return value

        @dataclass
        class Config:
            backend: Optional[str] = combine_annotations(
                cli_resolve(resolver=resolve_backend),
                default=None,
            )
            cache: Optional[str] = combine_annotations(
                cli_resolve(resolver=resolve_cache),
                default=None,
            )

        config = build_config(
            Config,
            args=[],
            base_configs={
                "backend": {"type": "redis"},
                "cache": {"engine": "memcached"},
            },
        )

        assert config.backend == "backend:redis"
        assert config.cache == "cache:memcached"

    def test_one_none_one_resolved(self):
        """Test that None bypass works independently for each field."""

        @dataclass
        class Config:
            backend: Optional[str] = combine_annotations(
                cli_resolve(resolver=resolve_identity),
                default=None,
            )
            cache: Optional[str] = combine_annotations(
                cli_resolve(resolver=resolve_identity),
                default=None,
            )

        config = build_config(
            Config,
            args=[],
            base_configs={"backend": {"type": "redis"}},
        )

        # backend gets resolved (value is dict), cache stays None
        assert config.backend == {"type": "redis"}
        assert config.cache is None


class TestConfigMergingWithResolve:
    """Test config merging precedence with cli_resolve fields."""

    def test_base_configs_then_config_file(self):
        """Test that --config file overrides base_configs before resolution."""

        @dataclass
        class Config:
            sandbox: Optional[SandboxBase] = combine_annotations(
                cli_resolve(resolver=resolve_sandbox),
                default=None,
            )

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(
                {"sandbox": {"type": "docker", "image": "from-config-file:latest"}}, f
            )
            config_file = f.name

        try:
            config = build_config(
                Config,
                args=["--config", config_file],
                base_configs={"sandbox": {"type": "local", "path": "/base"}},
            )

            # Config file overrides base_configs
            assert isinstance(config.sandbox, DockerSandbox)
            assert config.sandbox.image == "from-config-file:latest"
        finally:
            os.unlink(config_file)

    def test_cli_overrides_config_file(self):
        """Test that CLI args override config file before resolution."""

        @dataclass
        class Config:
            sandbox: Optional[SandboxBase] = combine_annotations(
                cli_resolve(resolver=resolve_sandbox),
                default=None,
            )

        # Config file with one value
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False
        ) as config_f:
            json.dump(
                {"sandbox": {"type": "docker", "image": "from-global:1.0"}}, config_f
            )
            global_config = config_f.name

        # CLI file with different value
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False
        ) as cli_f:
            json.dump({"type": "docker", "image": "from-cli:2.0"}, cli_f)
            cli_file = cli_f.name

        try:
            config = build_config(
                Config,
                args=["--config", global_config, "--sandbox", cli_file],
            )

            # CLI file overrides config file
            assert isinstance(config.sandbox, DockerSandbox)
            assert config.sandbox.image == "from-cli:2.0"
        finally:
            os.unlink(global_config)
            os.unlink(cli_file)


class TestEdgeCases:
    """Test edge cases."""

    def test_resolver_returns_none(self):
        """Test resolver returning None explicitly."""

        def none_resolver(value):
            return None

        @dataclass
        class Config:
            sandbox: Optional[Any] = combine_annotations(
                cli_resolve(resolver=none_resolver),
                default=None,
            )

        config = build_config(
            Config,
            args=[],
            base_configs={"sandbox": {"type": "docker"}},
        )

        assert config.sandbox is None

    def test_resolver_returns_different_type(self):
        """Test resolver returning a completely different type."""

        def string_resolver(value):
            return json.dumps(value) if isinstance(value, dict) else str(value)

        @dataclass
        class Config:
            data: Optional[str] = combine_annotations(
                cli_resolve(resolver=string_resolver),
                default=None,
            )

        config = build_config(
            Config,
            args=[],
            base_configs={"data": {"key": "value"}},
        )

        assert config.data == '{"key": "value"}'

    def test_empty_dict_still_resolved(self):
        """Test that empty dict is still passed to resolver."""
        call_count = {"calls": 0}

        def tracking_resolver(value):
            call_count["calls"] += 1
            return {"resolved": True}

        @dataclass
        class Config:
            sandbox: Optional[Dict[str, Any]] = combine_annotations(
                cli_resolve(resolver=tracking_resolver),
                default=None,
            )

        config = build_config(
            Config,
            args=[],
            base_configs={"sandbox": {}},
        )

        assert call_count["calls"] == 1
        assert config.sandbox == {"resolved": True}


if __name__ == "__main__":
    pytest.main([__file__, "-v"])


class TestListFieldResolve:
    """Test cli_resolve on List fields.."""

    def test_list_str_from_cli(self):
        """Test cli_resolve on List[str] — resolver receives list from CLI."""

        def resolve_paths(value):
            """Expand glob patterns or transform paths."""
            if isinstance(value, list):
                return [f"expanded:{v}" for v in value]
            return value

        @dataclass
        class Config:
            files: List[str] = combine_annotations(
                cli_resolve(resolver=resolve_paths),
                default_factory=list,
            )

        config = build_config(Config, args=["--files", "a.py", "b.py", "c.py"])

        assert config.files == ["expanded:a.py", "expanded:b.py", "expanded:c.py"]

    def test_list_from_base_configs(self):
        """Test cli_resolve on List[Any] with base_configs providing a list."""

        def resolve_items(value):
            if isinstance(value, list):
                return [{"name": item, "processed": True} for item in value]
            return value

        @dataclass
        class Config:
            items: List[Any] = combine_annotations(
                cli_resolve(resolver=resolve_items),
                default_factory=list,
            )

        config = build_config(
            Config,
            args=[],
            base_configs={"items": ["alpha", "beta", "gamma"]},
        )

        assert config.items == [
            {"name": "alpha", "processed": True},
            {"name": "beta", "processed": True},
            {"name": "gamma", "processed": True},
        ]

    def test_list_with_pre_built_objects(self):
        """Test cli_resolve on List[Any] with pre-built objects in list."""

        class Widget:
            def __init__(self, name):
                self.name = name

        def resolve_widgets(value):
            if isinstance(value, list):
                return [
                    item if isinstance(item, Widget) else Widget(str(item))
                    for item in value
                ]
            return value

        @dataclass
        class Config:
            widgets: List[Any] = combine_annotations(
                cli_resolve(resolver=resolve_widgets),
                default_factory=list,
            )

        pre_built = Widget("pre-built")
        config = build_config(
            Config,
            args=[],
            base_configs={"widgets": [pre_built, "from-config"]},
        )

        assert len(config.widgets) == 2
        assert config.widgets[0] is pre_built  # Same object (pass-through)
        assert config.widgets[1].name == "from-config"

    def test_optional_list_none_bypass(self):
        """Test cli_resolve on Optional[List[Any]] with None — resolver not called."""
        call_count = {"calls": 0}

        def counting_resolver(value):
            call_count["calls"] += 1
            return value

        @dataclass
        class Config:
            items: Optional[List[str]] = combine_annotations(
                cli_resolve(resolver=counting_resolver),
                default=None,
            )

        config = build_config(Config, args=[])

        assert config.items is None
        assert call_count["calls"] == 0

    def test_list_cli_values_nargs(self):
        """Test cli_resolve list field receives values from nargs."""

        def sort_resolver(value):
            if isinstance(value, list):
                return sorted(value)
            return value

        @dataclass
        class Config:
            tags: List[str] = combine_annotations(
                cli_resolve(resolver=sort_resolver),
                default_factory=list,
            )

        config = build_config(Config, args=["--tags", "zebra", "apple", "mango"])

        assert config.tags == ["apple", "mango", "zebra"]

    def test_empty_list_calls_resolver(self):
        """Test that empty list [] is passed to resolver (not None bypass)."""
        call_count = {"calls": 0}

        def tracking_resolver(value):
            call_count["calls"] += 1
            return ["default_item"]

        @dataclass
        class Config:
            items: Optional[List[str]] = combine_annotations(
                cli_resolve(resolver=tracking_resolver),
                default_factory=list,
            )

        # Provide empty list via base_configs
        config = build_config(
            Config,
            args=[],
            base_configs={"items": []},
        )

        assert call_count["calls"] == 1
        assert config.items == ["default_item"]

    def test_list_resolve_error_wrapped(self):
        """Test that errors in list resolver are properly wrapped."""

        def bad_resolver(value):
            raise RuntimeError("Cannot process list")

        @dataclass
        class Config:
            items: List[str] = combine_annotations(
                cli_resolve(resolver=bad_resolver),
                default_factory=list,
            )

        with pytest.raises(ConfigurationError) as exc_info:
            build_config(
                Config,
                args=[],
                base_configs={"items": ["a", "b"]},
            )

        assert "Failed to resolve field 'items'" in str(exc_info.value)
        assert "Cannot process list" in str(exc_info.value)

    def test_existing_dict_resolve_still_works(self):
        """Regression: dict-mode cli_resolve still works after list support added."""

        @dataclass
        class Config:
            sandbox: Optional[SandboxBase] = combine_annotations(
                cli_resolve(resolver=resolve_sandbox),
                default=None,
            )

        config = build_config(
            Config,
            args=[],
            base_configs={"sandbox": {"type": "docker", "image": "python:3.11"}},
        )

        assert isinstance(config.sandbox, DockerSandbox)
        assert config.sandbox.image == "python:3.11"

    def test_list_resolve_with_cli_short(self):
        """Test list cli_resolve combined with cli_short."""

        def upper_resolver(value):
            if isinstance(value, list):
                return [v.upper() for v in value]
            return value

        @dataclass
        class Config:
            names: List[str] = combine_annotations(
                cli_resolve(resolver=upper_resolver),
                cli_short("n"),
                default_factory=list,
            )

        config = build_config(Config, args=["-n", "hello", "world"])

        assert config.names == ["HELLO", "WORLD"]

    def test_list_resolve_with_cli_help(self):
        """Test list cli_resolve combined with cli_help."""

        def identity_resolver(value):
            return value

        @dataclass
        class Config:
            items: List[str] = combine_annotations(
                cli_resolve(resolver=identity_resolver),
                cli_help("Input items to process"),
                default_factory=list,
            )

        builder = GenericConfigBuilder(Config)
        parser = argparse.ArgumentParser()
        builder.add_arguments(parser)

        help_text = parser.format_help()
        assert "Input items to process" in help_text
