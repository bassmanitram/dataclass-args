"""Tests for cli_append() annotation and append action functionality."""

import argparse
from dataclasses import dataclass
from typing import List

import pytest

from dataclass_args import (
    build_config,
    cli_append,
    cli_choices,
    cli_help,
    cli_short,
    combine_annotations,
)
from dataclass_args.exceptions import ConfigurationError


class TestBasicAppend:
    """Test basic append functionality with single values."""

    def test_append_single_values(self):
        """Test append with single value per occurrence."""

        @dataclass
        class Config:
            tags: List[str] = cli_append(default_factory=list)

        config = build_config(
            Config, args=["--tags", "python", "--tags", "cli", "--tags", "tool"]
        )
        assert config.tags == ["python", "cli", "tool"]

    def test_append_with_short_option(self):
        """Test append with short option."""

        @dataclass
        class Config:
            tags: List[str] = combine_annotations(
                cli_short("t"), cli_append(), default_factory=list
            )

        config = build_config(Config, args=["-t", "python", "-t", "cli", "-t", "tool"])
        assert config.tags == ["python", "cli", "tool"]

    def test_append_no_occurrences(self):
        """Test append with no occurrences uses default."""

        @dataclass
        class Config:
            tags: List[str] = cli_append(default_factory=list)

        config = build_config(Config, args=[])
        assert config.tags == []

    def test_append_single_occurrence(self):
        """Test append with single occurrence."""

        @dataclass
        class Config:
            tags: List[str] = cli_append(default_factory=list)

        config = build_config(Config, args=["--tags", "single"])
        assert config.tags == ["single"]


class TestAppendWithNargs:
    """Test append with various nargs values."""

    def test_append_with_nargs_2(self):
        """Test append where each occurrence takes exactly 2 arguments."""

        @dataclass
        class Config:
            files: List[List[str]] = cli_append(nargs=2, default_factory=list)

        config = build_config(
            Config,
            args=[
                "--files",
                "doc.pdf",
                "application/pdf",
                "--files",
                "image.png",
                "image/png",
            ],
        )
        assert config.files == [
            ["doc.pdf", "application/pdf"],
            ["image.png", "image/png"],
        ]

    def test_append_with_nargs_2_short_option(self):
        """Test append with nargs=2 and short option."""

        @dataclass
        class Config:
            files: List[List[str]] = combine_annotations(
                cli_short("f"),
                cli_append(nargs=2),
                cli_help("File with MIME type"),
                default_factory=list,
            )

        config = build_config(
            Config,
            args=[
                "-f",
                "file1.txt",
                "text/plain",
                "-f",
                "file2.jpg",
                "image/jpeg",
                "-f",
                "file3.mp4",
                "video/mp4",
            ],
        )
        assert config.files == [
            ["file1.txt", "text/plain"],
            ["file2.jpg", "image/jpeg"],
            ["file3.mp4", "video/mp4"],
        ]

    def test_append_with_nargs_plus(self):
        """Test append where each occurrence takes 1 or more arguments."""

        @dataclass
        class Config:
            groups: List[List[str]] = cli_append(nargs="+", default_factory=list)

        config = build_config(
            Config,
            args=["--groups", "a", "b", "--groups", "c", "--groups", "d", "e", "f"],
        )
        assert config.groups == [["a", "b"], ["c"], ["d", "e", "f"]]

    def test_append_with_nargs_star(self):
        """Test append where each occurrence takes 0 or more arguments."""

        @dataclass
        class Config:
            items: List[List[str]] = cli_append(nargs="*", default_factory=list)

        config = build_config(
            Config, args=["--items", "a", "b", "--items", "--items", "c"]
        )
        assert config.items == [["a", "b"], [], ["c"]]

    def test_append_with_nargs_optional(self):
        """Test append with nargs='?' (0 or 1 per occurrence)."""

        @dataclass
        class Config:
            vals: List[str] = cli_append(nargs="?", default_factory=list)

        # Each occurrence takes 0 or 1 value
        config = build_config(Config, args=["--vals", "a", "--vals", "--vals", "c"])
        # Note: nargs='?' with append creates list of individual values (or None)
        assert config.vals == ["a", None, "c"]


class TestAppendWithTypes:
    """Test append with different types."""

    def test_append_integers(self):
        """Test append with integer type."""

        @dataclass
        class Config:
            ports: List[int] = cli_append(default_factory=list)

        config = build_config(
            Config, args=["--ports", "8000", "--ports", "8080", "--ports", "9000"]
        )
        assert config.ports == [8000, 8080, 9000]

    def test_append_floats(self):
        """Test append with float type."""

        @dataclass
        class Config:
            values: List[float] = cli_append(default_factory=list)

        config = build_config(
            Config, args=["--values", "1.5", "--values", "2.7", "--values", "3.14"]
        )
        assert config.values == [1.5, 2.7, 3.14]

    def test_append_pairs_mixed_types(self):
        """Test append with nargs=2 and mixed types in List[List[str]]."""

        @dataclass
        class Config:
            pairs: List[List[str]] = cli_append(nargs=2, default_factory=list)

        config = build_config(
            Config, args=["--pairs", "key1", "value1", "--pairs", "key2", "value2"]
        )
        assert config.pairs == [["key1", "value1"], ["key2", "value2"]]


class TestAppendWithChoices:
    """Test append combined with choices."""

    def test_append_with_choices(self):
        """Test append with restricted choices."""

        @dataclass
        class Config:
            tags: List[str] = combine_annotations(
                cli_append(),
                cli_choices(["dev", "prod", "staging"]),
                default_factory=list,
            )

        config = build_config(
            Config, args=["--tags", "dev", "--tags", "prod", "--tags", "staging"]
        )
        assert config.tags == ["dev", "prod", "staging"]

    def test_append_with_choices_invalid(self):
        """Test append with invalid choice raises error."""

        @dataclass
        class Config:
            tags: List[str] = combine_annotations(
                cli_append(), cli_choices(["dev", "prod"]), default_factory=list
            )

        with pytest.raises(SystemExit):
            build_config(Config, args=["--tags", "dev", "--tags", "invalid"])


class TestAppendRealWorldExamples:
    """Test real-world use cases."""

    def test_file_with_mime_type(self):
        """Test file upload scenario with optional MIME type (1 or 2 args)."""

        @dataclass
        class Config:
            files: List[List[str]] = combine_annotations(
                cli_short("f"),
                cli_append(nargs="+"),
                cli_help("File with optional MIME type"),
                default_factory=list,
            )

            def __post_init__(self):
                # Validate each file spec has 1 or 2 arguments
                for file_spec in self.files:
                    if len(file_spec) < 1 or len(file_spec) > 2:
                        raise ValueError(
                            f"Each file must have 1 or 2 arguments, got {len(file_spec)}"
                        )

        # Valid: some with mime, some without
        config = build_config(
            Config,
            args=[
                "-f",
                "doc.pdf",
                "application/pdf",
                "-f",
                "image.png",
                "-f",
                "video.mp4",
                "video/mp4",
            ],
        )
        assert config.files == [
            ["doc.pdf", "application/pdf"],
            ["image.png"],
            ["video.mp4", "video/mp4"],
        ]

    def test_mount_points(self):
        """Test docker-style mount points (source:dest)."""

        @dataclass
        class Config:
            mounts: List[List[str]] = combine_annotations(
                cli_short("v"),
                cli_append(nargs=2),
                cli_help("Volume mount (source destination)"),
                default_factory=list,
            )

        config = build_config(
            Config,
            args=[
                "-v",
                "/host/data",
                "/container/data",
                "-v",
                "/host/logs",
                "/container/logs",
                "-v",
                "/host/config",
                "/container/config",
            ],
        )
        assert config.mounts == [
            ["/host/data", "/container/data"],
            ["/host/logs", "/container/logs"],
            ["/host/config", "/container/config"],
        ]

    def test_environment_variables(self):
        """Test environment variable definitions (key=value pairs)."""

        @dataclass
        class Config:
            env_vars: List[List[str]] = combine_annotations(
                cli_short("e"),
                cli_append(nargs=2),
                cli_help("Environment variable (KEY VALUE)"),
                default_factory=list,
            )

        config = build_config(
            Config,
            args=[
                "-e",
                "DEBUG",
                "true",
                "-e",
                "LOG_LEVEL",
                "INFO",
                "-e",
                "PORT",
                "8080",
            ],
        )
        assert config.env_vars == [
            ["DEBUG", "true"],
            ["LOG_LEVEL", "INFO"],
            ["PORT", "8080"],
        ]

    def test_server_definitions(self):
        """Test server definitions with host and port."""

        @dataclass
        class Config:
            servers: List[List[str]] = combine_annotations(
                cli_short("s"),
                cli_append(nargs=2),
                cli_help("Server (HOST PORT)"),
                default_factory=list,
            )

        config = build_config(
            Config,
            args=[
                "-s",
                "server1.example.com",
                "8080",
                "-s",
                "server2.example.com",
                "8081",
                "-s",
                "server3.example.com",
                "8082",
            ],
        )
        assert config.servers == [
            ["server1.example.com", "8080"],
            ["server2.example.com", "8081"],
            ["server3.example.com", "8082"],
        ]


class TestAppendEdgeCases:
    """Test edge cases and error conditions."""

    def test_append_mixed_with_other_args(self):
        """Test append field mixed with regular arguments."""

        @dataclass
        class Config:
            name: str
            tags: List[str] = cli_append(default_factory=list)
            debug: bool = False

        config = build_config(
            Config,
            args=["--name", "MyApp", "--tags", "python", "--debug", "--tags", "cli"],
        )
        assert config.name == "MyApp"
        assert config.tags == ["python", "cli"]
        assert config.debug is True

    def test_append_with_default_factory(self):
        """Test append requires default_factory=list."""

        @dataclass
        class Config:
            tags: List[str] = cli_append(default_factory=list)

        config = build_config(Config, args=[])
        assert config.tags == []
        assert isinstance(config.tags, list)

    def test_append_multiple_fields(self):
        """Test multiple append fields in same config."""

        @dataclass
        class Config:
            tags: List[str] = cli_append(default_factory=list)
            labels: List[str] = cli_append(default_factory=list)

        config = build_config(
            Config,
            args=["--tags", "a", "--labels", "x", "--tags", "b", "--labels", "y"],
        )
        assert config.tags == ["a", "b"]
        assert config.labels == ["x", "y"]

    def test_append_with_nargs_exact_count_mismatch(self):
        """Test append with nargs=2 requires exactly 2 args per occurrence."""

        @dataclass
        class Config:
            pairs: List[List[str]] = cli_append(nargs=2, default_factory=list)

        # Should fail with only 1 argument
        with pytest.raises(SystemExit):
            build_config(Config, args=["--pairs", "only_one"])


class TestAppendCombinedAnnotations:
    """Test cli_append combined with other annotations."""

    def test_append_with_help(self):
        """Test append with custom help text."""

        @dataclass
        class Config:
            items: List[str] = combine_annotations(
                cli_append(), cli_help("Add an item"), default_factory=list
            )

        config = build_config(Config, args=["--items", "a", "--items", "b"])
        assert config.items == ["a", "b"]

    def test_append_with_short_and_help(self):
        """Test append with short option and help."""

        @dataclass
        class Config:
            files: List[List[str]] = combine_annotations(
                cli_short("f"),
                cli_append(nargs=2),
                cli_help("File with MIME type"),
                default_factory=list,
            )

        config = build_config(
            Config, args=["-f", "a.txt", "text/plain", "-f", "b.jpg", "image/jpeg"]
        )
        assert config.files == [["a.txt", "text/plain"], ["b.jpg", "image/jpeg"]]

    def test_append_with_all_annotations(self):
        """Test append with short, choices, and help."""

        @dataclass
        class Config:
            envs: List[str] = combine_annotations(
                cli_short("e"),
                cli_append(),
                cli_choices(["dev", "staging", "prod"]),
                cli_help("Add environment"),
                default_factory=list,
            )

        config = build_config(Config, args=["-e", "dev", "-e", "staging", "-e", "prod"])
        assert config.envs == ["dev", "staging", "prod"]


class TestAppendValidation:
    """Test validation with __post_init__."""

    def test_append_with_post_init_validation(self):
        """Test append with custom validation in __post_init__."""

        @dataclass
        class Config:
            files: List[List[str]] = combine_annotations(
                cli_short("f"), cli_append(nargs="+"), default_factory=list
            )

            def __post_init__(self):
                # Validate each file spec has 1 or 2 arguments
                for file_spec in self.files:
                    if len(file_spec) < 1 or len(file_spec) > 2:
                        raise ValueError(
                            f"Each file must have 1-2 arguments, got {len(file_spec)}"
                        )

        # Valid: 1 or 2 args per occurrence
        config = build_config(
            Config, args=["-f", "file1", "mime1", "-f", "file2", "-f", "file3", "mime3"]
        )
        assert config.files == [["file1", "mime1"], ["file2"], ["file3", "mime3"]]

    def test_append_validation_failure(self):
        """Test that validation in __post_init__ catches invalid data."""

        @dataclass
        class Config:
            files: List[List[str]] = cli_append(nargs="+", default_factory=list)

            def __post_init__(self):
                for file_spec in self.files:
                    if len(file_spec) > 2:
                        raise ValueError(f"Too many arguments: {len(file_spec)}")

        # Should fail: one occurrence has 3 arguments
        with pytest.raises(ConfigurationError) as exc_info:
            build_config(Config, args=["--files", "a", "b", "c", "--files", "d"])
        assert "Too many arguments: 3" in str(exc_info.value)


class TestAppendIntegration:
    """Integration tests with realistic scenarios."""

    def test_complete_docker_command(self):
        """Test a docker-like command with multiple append options."""

        @dataclass
        class DockerConfig:
            image: str
            name: str = cli_short("n", default="container")
            ports: List[List[str]] = combine_annotations(
                cli_short("p"),
                cli_append(nargs=2),
                cli_help("Port mapping (HOST CONTAINER)"),
                default_factory=list,
            )
            volumes: List[List[str]] = combine_annotations(
                cli_short("v"),
                cli_append(nargs=2),
                cli_help("Volume mount (SOURCE TARGET)"),
                default_factory=list,
            )
            env: List[List[str]] = combine_annotations(
                cli_short("e"),
                cli_append(nargs=2),
                cli_help("Environment variable (KEY VALUE)"),
                default_factory=list,
            )
            detach: bool = cli_short("d", default=False)

        config = build_config(
            DockerConfig,
            args=[
                "--image",
                "nginx:latest",
                "-n",
                "webserver",
                "-p",
                "8080",
                "80",
                "-p",
                "8443",
                "443",
                "-v",
                "/host/html",
                "/usr/share/nginx/html",
                "-v",
                "/host/config",
                "/etc/nginx",
                "-e",
                "DEBUG",
                "true",
                "-e",
                "LOG_LEVEL",
                "info",
                "-d",
            ],
        )

        assert config.image == "nginx:latest"
        assert config.name == "webserver"
        assert config.ports == [["8080", "80"], ["8443", "443"]]
        assert config.volumes == [
            ["/host/html", "/usr/share/nginx/html"],
            ["/host/config", "/etc/nginx"],
        ]
        assert config.env == [["DEBUG", "true"], ["LOG_LEVEL", "info"]]
        assert config.detach is True

    def test_git_style_command(self):
        """Test git-style command with grouped files."""

        @dataclass
        class GitConfig:
            command: str
            file_groups: List[List[str]] = combine_annotations(
                cli_short("g"),
                cli_append(nargs="+"),
                cli_help("Group of files to process together"),
                default_factory=list,
            )
            message: str = cli_short("m", default="")

        config = build_config(
            GitConfig,
            args=[
                "--command",
                "commit",
                "-g",
                "src/main.py",
                "src/utils.py",
                "-g",
                "tests/test_main.py",
                "-g",
                "README.md",
                "CHANGELOG.md",
                "docs/API.md",
                "-m",
                "Update multiple components",
            ],
        )

        assert config.command == "commit"
        assert config.file_groups == [
            ["src/main.py", "src/utils.py"],
            ["tests/test_main.py"],
            ["README.md", "CHANGELOG.md", "docs/API.md"],
        ]
        assert config.message == "Update multiple components"


class TestAppendHelp:
    """Test help text generation for append fields."""

    def test_append_help_text(self):
        """Test that help text indicates repeatability."""

        @dataclass
        class Config:
            tags: List[str] = combine_annotations(
                cli_short("t"),
                cli_append(),
                cli_help("Add a tag"),
                default_factory=list,
            )

        # Build parser to inspect help
        from dataclass_args import GenericConfigBuilder

        builder = GenericConfigBuilder(Config)
        parser = argparse.ArgumentParser()
        builder.add_arguments(parser)

        # Get help text
        help_text = parser.format_help()
        assert "(can be repeated)" in help_text
        assert "Add a tag" in help_text


class TestAppendTyping:
    """Test type correctness for append fields."""

    def test_append_list_of_strings(self):
        """Test List[str] with append gives flat list."""

        @dataclass
        class Config:
            tags: List[str] = cli_append(default_factory=list)

        config = build_config(Config, args=["--tags", "a", "--tags", "b"])
        assert isinstance(config.tags, list)
        assert all(isinstance(item, str) for item in config.tags)

    def test_append_list_of_lists_with_nargs(self):
        """Test List[List[str]] with nargs gives nested lists."""

        @dataclass
        class Config:
            pairs: List[List[str]] = cli_append(nargs=2, default_factory=list)

        config = build_config(Config, args=["--pairs", "a", "b", "--pairs", "c", "d"])
        assert isinstance(config.pairs, list)
        assert all(isinstance(item, list) for item in config.pairs)
        assert all(all(isinstance(x, str) for x in item) for item in config.pairs)


class TestAppendWithMinMaxArgs:
    """Test cli_append with min_args/max_args range validation."""

    def test_min_max_valid_range(self):
        """Test that valid argument counts within range work."""

        @dataclass
        class Config:
            files: List[List[str]] = combine_annotations(
                cli_short("f"),
                cli_append(min_args=1, max_args=2),
                default_factory=list,
            )

        config = build_config(
            Config,
            args=[
                "-f",
                "file1",
                "mime1",  # 2 args
                "-f",
                "file2",  # 1 arg
                "-f",
                "file3",
                "mime3",  # 2 args
            ],
        )

        assert config.files == [["file1", "mime1"], ["file2"], ["file3", "mime3"]]

    def test_min_max_too_many_args(self):
        """Test that exceeding max_args raises error."""

        @dataclass
        class Config:
            files: List[List[str]] = combine_annotations(
                cli_short("f"),
                cli_append(min_args=1, max_args=2),
                default_factory=list,
            )

        with pytest.raises(ConfigurationError, match="Expected at most 2 argument"):
            build_config(Config, args=["-f", "file1", "arg2", "arg3", "arg4"])

    def test_min_max_exact_range(self):
        """Test min=max works correctly."""

        @dataclass
        class Config:
            pairs: List[List[str]] = combine_annotations(
                cli_short("p"),
                cli_append(min_args=2, max_args=2),
                default_factory=list,
            )

        config = build_config(Config, args=["-p", "k1", "v1", "-p", "k2", "v2"])

        assert config.pairs == [["k1", "v1"], ["k2", "v2"]]

        # Should fail with wrong count
        with pytest.raises(ConfigurationError, match="Expected at most 2 argument"):
            build_config(Config, args=["-p", "k1", "v1", "extra"])

    def test_min_max_mutually_exclusive_with_nargs(self):
        """Test that nargs and min/max_args cannot be used together."""

        with pytest.raises(
            ValueError, match="nargs.*min_args.*max_args.*mutually exclusive"
        ):

            @dataclass
            class Config:
                files: List[str] = combine_annotations(
                    cli_append(nargs=2, min_args=1, max_args=2), default_factory=list
                )

    def test_min_max_must_be_used_together(self):
        """Test that min_args requires max_args and vice versa."""

        with pytest.raises(ValueError, match="must be used together"):

            @dataclass
            class Config:
                files: List[str] = combine_annotations(
                    cli_append(min_args=1), default_factory=list
                )

        with pytest.raises(ValueError, match="must be used together"):

            @dataclass
            class Config2:
                files: List[str] = combine_annotations(
                    cli_append(max_args=2), default_factory=list
                )

    def test_min_args_validation(self):
        """Test that min_args must be >= 1."""

        with pytest.raises(ValueError, match="min_args.*must be >= 1"):

            @dataclass
            class Config:
                files: List[str] = combine_annotations(
                    cli_append(min_args=0, max_args=2), default_factory=list
                )

    def test_max_args_validation(self):
        """Test that max_args must be >= min_args."""

        with pytest.raises(ValueError, match="max_args.*must be >= min_args"):

            @dataclass
            class Config:
                files: List[str] = combine_annotations(
                    cli_append(min_args=3, max_args=2), default_factory=list
                )

    def test_min_max_with_other_annotations(self):
        """Test that min/max works with other annotations."""

        @dataclass
        class Config:
            files: List[List[str]] = combine_annotations(
                cli_short("f"),
                cli_append(min_args=1, max_args=3, metavar="FILE [MIME] [ENCODING]"),
                cli_help("Input files with optional metadata"),
                default_factory=list,
            )

        config = build_config(
            Config,
            args=[
                "-f",
                "file1",
                "text/plain",
                "utf-8",  # 3 args
                "-f",
                "file2",  # 1 arg
                "-f",
                "file3",
                "image/png",  # 2 args
            ],
        )

        assert config.files == [
            ["file1", "text/plain", "utf-8"],
            ["file2"],
            ["file3", "image/png"],
        ]
