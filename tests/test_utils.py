"""
Comprehensive tests for utils module.
"""

import json
import os
import tempfile
from pathlib import Path
from unittest.mock import mock_open, patch

import pytest

from dataclass_args.utils import load_structured_file


class TestLoadStructuredFile:
    """Tests for load_structured_file function."""

    def test_load_json_file(self):
        """Should load valid JSON file."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump({"name": "test", "count": 42}, f)
            temp_path = f.name

        try:
            result = load_structured_file(temp_path)
            assert result == {"name": "test", "count": 42}
        finally:
            Path(temp_path).unlink()

    def test_load_json_with_nested_data(self):
        """Should load JSON with nested structures."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            data = {
                "server": {"host": "localhost", "port": 8080},
                "features": ["auth", "logging"],
            }
            json.dump(data, f)
            temp_path = f.name

        try:
            result = load_structured_file(temp_path)
            assert result["server"]["host"] == "localhost"
            assert result["features"] == ["auth", "logging"]
        finally:
            Path(temp_path).unlink()

    def test_file_not_found(self):
        """Should raise FileNotFoundError for non-existent file."""
        with pytest.raises(FileNotFoundError, match="Configuration file not found"):
            load_structured_file("/nonexistent/path/config.json")

    def test_path_is_directory(self):
        """Should raise ValueError if path is a directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with pytest.raises(ValueError, match="Path is not a file"):
                load_structured_file(tmpdir)

    def test_invalid_json(self):
        """Should raise ValueError for invalid JSON."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            f.write("{ invalid json }")
            temp_path = f.name

        try:
            with pytest.raises(ValueError, match="Invalid JSON"):
                load_structured_file(temp_path)
        finally:
            Path(temp_path).unlink()

    def test_non_utf8_file(self):
        """Should raise ValueError for non-UTF8 files."""
        with tempfile.NamedTemporaryFile(mode="wb", suffix=".json", delete=False) as f:
            f.write(b"\xff\xfe invalid utf-8")
            temp_path = f.name

        try:
            with pytest.raises(ValueError, match="not valid UTF-8"):
                load_structured_file(temp_path)
        finally:
            Path(temp_path).unlink()

    def test_ioerror_during_read(self):
        """Should raise ValueError for IOError during file read."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump({"test": "value"}, f)
            temp_path = f.name

        try:
            # Mock open to raise IOError
            with patch("builtins.open", side_effect=IOError("Permission denied")):
                with pytest.raises(ValueError, match="Cannot read file"):
                    load_structured_file(temp_path)
        finally:
            Path(temp_path).unlink()

    def test_accepts_path_object(self):
        """Should accept Path objects in addition to strings."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump({"test": "value"}, f)
            temp_path = Path(f.name)

        try:
            result = load_structured_file(temp_path)
            assert result == {"test": "value"}
        finally:
            temp_path.unlink()

    def test_autodetect_json_without_extension(self):
        """Should auto-detect JSON format without .json extension."""
        with tempfile.NamedTemporaryFile(mode="w", suffix="", delete=False) as f:
            json.dump({"format": "json"}, f)
            temp_path = f.name

        try:
            result = load_structured_file(temp_path)
            assert result == {"format": "json"}
        finally:
            Path(temp_path).unlink()

    def test_unsupported_format_no_extension(self, monkeypatch):
        """Should raise ValueError for unparseable file without extension."""
        import dataclass_args.utils

        # Disable optional parsers to test the error path
        monkeypatch.setattr(dataclass_args.utils, "HAS_YAML", False)
        monkeypatch.setattr(dataclass_args.utils, "HAS_TOML", False)

        with tempfile.NamedTemporaryFile(mode="w", suffix="", delete=False) as f:
            f.write("This is not valid JSON, YAML, or TOML content !!!")
            temp_path = f.name

        try:
            with pytest.raises(
                ValueError, match="Could not parse.*as any supported format"
            ):
                load_structured_file(temp_path)
        finally:
            Path(temp_path).unlink()

    def test_unsupported_extension(self):
        """Should try auto-detect for unknown extension."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            json.dump({"detected": "json"}, f)
            temp_path = f.name

        try:
            # Should auto-detect as JSON
            result = load_structured_file(temp_path)
            assert result == {"detected": "json"}
        finally:
            Path(temp_path).unlink()

    def test_unsupported_extension_invalid_content(self, monkeypatch):
        """Should fail auto-detect for unknown extension with invalid content."""
        import dataclass_args.utils

        # Disable optional parsers to test the error path with only JSON
        monkeypatch.setattr(dataclass_args.utils, "HAS_YAML", False)
        monkeypatch.setattr(dataclass_args.utils, "HAS_TOML", False)

        with tempfile.NamedTemporaryFile(mode="w", suffix=".xyz", delete=False) as f:
            f.write("random content that is not structured data")
            temp_path = f.name

        try:
            with pytest.raises(
                ValueError, match="Could not parse.*as any supported format"
            ):
                load_structured_file(temp_path)
        finally:
            Path(temp_path).unlink()


class TestLoadStructuredFileYAML:
    """Tests for YAML support in load_structured_file."""

    @pytest.fixture(autouse=True)
    def check_yaml_available(self):
        """Skip YAML tests if PyYAML not installed."""
        try:
            import yaml  # noqa: F401
        except ImportError:
            pytest.skip("PyYAML not installed")

    def test_load_yaml_file(self):
        """Should load valid YAML file."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write("name: test\ncount: 42\n")
            temp_path = f.name

        try:
            result = load_structured_file(temp_path)
            assert result == {"name": "test", "count": 42}
        finally:
            Path(temp_path).unlink()

    def test_load_yml_extension(self):
        """Should load .yml extension."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yml", delete=False) as f:
            f.write("key: value\n")
            temp_path = f.name

        try:
            result = load_structured_file(temp_path)
            assert result == {"key": "value"}
        finally:
            Path(temp_path).unlink()

    def test_invalid_yaml(self):
        """Should raise ValueError for invalid YAML."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write("invalid: yaml: content: ::::")
            temp_path = f.name

        try:
            with pytest.raises(ValueError, match="Invalid YAML"):
                load_structured_file(temp_path)
        finally:
            Path(temp_path).unlink()

    def test_empty_yaml_returns_empty_dict(self):
        """Should return empty dict for empty YAML file."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write("")
            temp_path = f.name

        try:
            result = load_structured_file(temp_path)
            assert result == {}
        finally:
            Path(temp_path).unlink()

    def test_yaml_with_complex_structures(self):
        """Should handle complex YAML structures."""
        yaml_content = """
server:
  host: localhost
  port: 8080
features:
  - authentication
  - logging
  - monitoring
settings:
  debug: true
  timeout: 30
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(yaml_content)
            temp_path = f.name

        try:
            result = load_structured_file(temp_path)
            assert result["server"]["host"] == "localhost"
            assert result["features"] == ["authentication", "logging", "monitoring"]
            assert result["settings"]["debug"] is True
        finally:
            Path(temp_path).unlink()

    def test_autodetect_yaml_without_extension(self):
        """Should auto-detect YAML format without extension when YAML available."""
        yaml_content = """
name: test
count: 42
enabled: true
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix="", delete=False) as f:
            f.write(yaml_content)
            temp_path = f.name

        try:
            result = load_structured_file(temp_path)
            assert result == {"name": "test", "count": 42, "enabled": True}
        finally:
            Path(temp_path).unlink()

    def test_autodetect_yaml_with_unknown_extension(self):
        """Should auto-detect YAML with unknown extension."""
        yaml_content = "key: value\nnested:\n  item: 123\n"
        with tempfile.NamedTemporaryFile(mode="w", suffix=".config", delete=False) as f:
            f.write(yaml_content)
            temp_path = f.name

        try:
            result = load_structured_file(temp_path)
            assert result == {"key": "value", "nested": {"item": 123}}
        finally:
            Path(temp_path).unlink()


class TestLoadStructuredFileTOML:
    """Tests for TOML support in load_structured_file."""

    @pytest.fixture(autouse=True)
    def check_toml_available(self):
        """Skip TOML tests if tomli/tomllib not installed."""
        try:
            try:
                import tomllib  # noqa: F401
            except ImportError:
                import tomli  # noqa: F401
        except ImportError:
            pytest.skip("TOML support not installed")

    def test_load_toml_file(self):
        """Should load valid TOML file."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".toml", delete=False) as f:
            f.write('name = "test"\ncount = 42\n')
            temp_path = f.name

        try:
            result = load_structured_file(temp_path)
            assert result == {"name": "test", "count": 42}
        finally:
            Path(temp_path).unlink()

    def test_invalid_toml(self):
        """Should raise ValueError for invalid TOML."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".toml", delete=False) as f:
            f.write("invalid toml ][[]")
            temp_path = f.name

        try:
            with pytest.raises(ValueError, match="Invalid TOML"):
                load_structured_file(temp_path)
        finally:
            Path(temp_path).unlink()

    def test_toml_with_sections(self):
        """Should handle TOML with sections."""
        toml_content = """
[server]
host = "localhost"
port = 8080

[database]
url = "postgresql://localhost/db"
pool_size = 10

[[features]]
name = "auth"
enabled = true

[[features]]
name = "logging"
enabled = false
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".toml", delete=False) as f:
            f.write(toml_content)
            temp_path = f.name

        try:
            result = load_structured_file(temp_path)
            assert result["server"]["host"] == "localhost"
            assert result["database"]["pool_size"] == 10
            assert len(result["features"]) == 2
            assert result["features"][0]["name"] == "auth"
        finally:
            Path(temp_path).unlink()

    def test_autodetect_toml_without_extension(self, monkeypatch):
        """Should auto-detect TOML format without extension when TOML available."""
        import dataclass_args.utils

        # Disable YAML so TOML gets tried
        monkeypatch.setattr(dataclass_args.utils, "HAS_YAML", False)

        toml_content = 'name = "test"\ncount = 42\nenabled = true\n'
        with tempfile.NamedTemporaryFile(mode="w", suffix="", delete=False) as f:
            f.write(toml_content)
            temp_path = f.name

        try:
            result = load_structured_file(temp_path)
            assert result == {"name": "test", "count": 42, "enabled": True}
        finally:
            Path(temp_path).unlink()

    def test_autodetect_toml_with_unknown_extension(self, monkeypatch):
        """Should auto-detect TOML with unknown extension."""
        import dataclass_args.utils

        # Disable YAML so TOML gets tried
        monkeypatch.setattr(dataclass_args.utils, "HAS_YAML", False)

        toml_content = '[section]\nkey = "value"\nnumber = 123\n'
        with tempfile.NamedTemporaryFile(mode="w", suffix=".cfg", delete=False) as f:
            f.write(toml_content)
            temp_path = f.name

        try:
            result = load_structured_file(temp_path)
            assert result == {"section": {"key": "value", "number": 123}}
        finally:
            Path(temp_path).unlink()


class TestLoadStructuredFileMissingDependencies:
    """Tests for behavior when optional dependencies are missing."""

    def test_yaml_without_pyyaml(self, monkeypatch):
        """Should raise helpful error for YAML without PyYAML installed."""
        # Mock HAS_YAML to False
        import dataclass_args.utils

        monkeypatch.setattr(dataclass_args.utils, "HAS_YAML", False)

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write("test: value")
            temp_path = f.name

        try:
            with pytest.raises(
                ValueError, match="YAML support not available.*pip install"
            ):
                load_structured_file(temp_path)
        finally:
            Path(temp_path).unlink()

    def test_toml_without_tomli(self, monkeypatch):
        """Should raise helpful error for TOML without tomli/tomllib."""
        # Mock HAS_TOML to False
        import dataclass_args.utils

        monkeypatch.setattr(dataclass_args.utils, "HAS_TOML", False)

        with tempfile.NamedTemporaryFile(mode="w", suffix=".toml", delete=False) as f:
            f.write('test = "value"')
            temp_path = f.name

        try:
            with pytest.raises(
                ValueError, match="TOML support not available.*pip install"
            ):
                load_structured_file(temp_path)
        finally:
            Path(temp_path).unlink()


class TestLoadStructuredFileEdgeCases:
    """Edge case tests for load_structured_file."""

    def test_empty_json_file(self):
        """Should handle empty JSON file (invalid JSON)."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            f.write("")
            temp_path = f.name

        try:
            with pytest.raises(ValueError, match="Invalid JSON"):
                load_structured_file(temp_path)
        finally:
            Path(temp_path).unlink()

    def test_json_with_comments_invalid(self):
        """JSON with comments should fail (JSON doesn't support comments)."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            f.write('// comment\n{"key": "value"}')
            temp_path = f.name

        try:
            with pytest.raises(ValueError, match="Invalid JSON"):
                load_structured_file(temp_path)
        finally:
            Path(temp_path).unlink()

    def test_case_insensitive_extension(self):
        """Should handle extensions in any case."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".JSON", delete=False) as f:
            json.dump({"test": "value"}, f)
            temp_path = f.name

        try:
            result = load_structured_file(temp_path)
            assert result == {"test": "value"}
        finally:
            Path(temp_path).unlink()

    def test_special_characters_in_path(self):
        """Should handle paths with special characters."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create file with spaces in name
            file_path = Path(tmpdir) / "config file with spaces.json"
            with open(file_path, "w") as f:
                json.dump({"test": "value"}, f)

            result = load_structured_file(file_path)
            assert result == {"test": "value"}

    def test_symlink_to_file(self):
        """Should follow symlinks to files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create actual file
            actual_file = Path(tmpdir) / "actual.json"
            with open(actual_file, "w") as f:
                json.dump({"test": "symlink"}, f)

            # Create symlink
            symlink = Path(tmpdir) / "link.json"
            try:
                symlink.symlink_to(actual_file)

                result = load_structured_file(symlink)
                assert result == {"test": "symlink"}
            except OSError:
                # Skip on systems that don't support symlinks (Windows without privileges)
                pytest.skip("Symlinks not supported on this system")


class TestLoadStructuredFileAutoDetectionErrorPaths:
    """Tests to cover error handling in auto-detection logic."""

    @pytest.fixture(autouse=True)
    def check_dependencies(self):
        """Skip if YAML or TOML not available."""
        try:
            import yaml  # noqa: F401

            try:
                import tomllib  # noqa: F401
            except ImportError:
                import tomli  # noqa: F401
        except ImportError:
            pytest.skip("Both YAML and TOML needed for auto-detection error tests")

    def test_autodetect_yaml_error_fallback_to_toml(self, monkeypatch):
        """Should try TOML if YAML fails during auto-detection."""
        import dataclass_args.utils

        # Create content that is valid TOML but causes YAML error
        toml_content = '[section]\nkey = "value"\n'

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".unknown", delete=False
        ) as f:
            f.write(toml_content)
            temp_path = f.name

        try:
            # Mock yaml.safe_load to raise YAMLError
            import yaml

            original_safe_load = yaml.safe_load

            def mock_yaml_load(content):
                if content == toml_content:
                    raise yaml.YAMLError("Mocked YAML error")
                return original_safe_load(content)

            monkeypatch.setattr(yaml, "safe_load", mock_yaml_load)

            # Should fall back to TOML
            result = load_structured_file(temp_path)
            assert result == {"section": {"key": "value"}}
        finally:
            Path(temp_path).unlink()

    def test_autodetect_all_formats_fail(self, monkeypatch):
        """Should provide helpful error when all formats fail during auto-detection."""
        import json

        import yaml

        import dataclass_args.utils

        # Mock all parsers to fail
        monkeypatch.setattr(
            json,
            "loads",
            lambda x: (_ for _ in ()).throw(json.JSONDecodeError("mock", x, 0)),
        )
        monkeypatch.setattr(
            yaml, "safe_load", lambda x: (_ for _ in ()).throw(yaml.YAMLError("mock"))
        )

        try:
            import tomllib

            monkeypatch.setattr(
                tomllib, "loads", lambda x: (_ for _ in ()).throw(ValueError("mock"))
            )
        except ImportError:
            try:
                import tomli

                monkeypatch.setattr(
                    tomli, "loads", lambda x: (_ for _ in ()).throw(ValueError("mock"))
                )
            except ImportError:
                pass

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".unknown", delete=False
        ) as f:
            f.write("some content")
            temp_path = f.name

        try:
            with pytest.raises(
                ValueError, match="Could not parse.*as any supported format"
            ):
                load_structured_file(temp_path)
        finally:
            Path(temp_path).unlink()

    def test_error_message_lists_available_formats(self, monkeypatch):
        """Error message should list available formats."""
        import dataclass_args.utils

        # Test with only JSON available
        monkeypatch.setattr(dataclass_args.utils, "HAS_YAML", False)
        monkeypatch.setattr(dataclass_args.utils, "HAS_TOML", False)

        with tempfile.NamedTemporaryFile(mode="w", suffix=".xyz", delete=False) as f:
            f.write("invalid")
            temp_path = f.name

        try:
            with pytest.raises(ValueError, match="Supported formats: JSON"):
                load_structured_file(temp_path)
        finally:
            Path(temp_path).unlink()
