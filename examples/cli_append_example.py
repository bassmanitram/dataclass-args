#!/usr/bin/env python3
"""
Example demonstrating cli_append() for repeatable options with multiple arguments.

The cli_append() annotation allows an option to be specified multiple times,
with each occurrence collecting its own arguments.

Run with:
    python cli_append_example.py docker
    python cli_append_example.py files
    python cli_append_example.py environment
    python cli_append_example.py --help
"""

import sys
from dataclasses import dataclass
from typing import List

from dataclass_args import (
    build_config,
    cli_append,
    cli_choices,
    cli_help,
    cli_short,
    combine_annotations,
)


def example_docker():
    """Example 1: Docker-style command with multiple repeatable options."""
    print("\n" + "=" * 70)
    print("Example 1: Docker-Style Configuration")
    print("=" * 70)

    @dataclass
    class DockerConfig:
        """Docker-style configuration with repeatable mount, port, and env options."""

        image: str = cli_help("Container image")
        name: str = cli_short("n", default="container")

        # Ports: -p HOST CONTAINER (can repeat)
        ports: List[List[str]] = combine_annotations(
            cli_short("p"),
            cli_append(nargs=2),
            cli_help("Port mapping (HOST CONTAINER)"),
            default_factory=list,
        )

        # Volumes: -v SOURCE TARGET (can repeat)
        volumes: List[List[str]] = combine_annotations(
            cli_short("v"),
            cli_append(nargs=2),
            cli_help("Volume mount (SOURCE TARGET)"),
            default_factory=list,
        )

        # Environment: -e KEY VALUE (can repeat)
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

    print(f"\nConfiguration:")
    print(f"  Image: {config.image}")
    print(f"  Name: {config.name}")
    print(f"  Detached: {config.detach}")

    print(f"\nPort Mappings:")
    for host, container in config.ports:
        print(f"  {host} → {container}")

    print(f"\nVolume Mounts:")
    for source, target in config.volumes:
        print(f"  {source} → {target}")

    print(f"\nEnvironment Variables:")
    for key, value in config.env:
        print(f"  {key}={value}")

    print("\nCLI Used:")
    print(
        "  python cli_append_example.py --image nginx:latest -n webserver "
        "-p 8080 80 -p 8443 443 -v /host/html /usr/share/nginx/html "
        "-e DEBUG true -d"
    )


def example_files():
    """Example 2: File uploads with optional MIME types (1 or 2 arguments)."""
    print("\n" + "=" * 70)
    print("Example 2: Files with Optional MIME Types")
    print("=" * 70)

    @dataclass
    class UploadConfig:
        """File upload configuration with optional MIME type per file."""

        server: str = cli_help("Upload server URL")

        files: List[List[str]] = combine_annotations(
            cli_short("f"),
            cli_append(nargs="+"),
            cli_help("File with optional MIME type"),
            default_factory=list,
        )

        def __post_init__(self):
            # Validate each file has 1 or 2 arguments
            for file_spec in self.files:
                if len(file_spec) < 1 or len(file_spec) > 2:
                    raise ValueError(
                        f"Each file must have 1-2 arguments, got {len(file_spec)}"
                    )

    config = build_config(
        UploadConfig,
        args=[
            "--server",
            "https://upload.example.com",
            "-f",
            "document.pdf",
            "application/pdf",
            "-f",
            "image.png",
            "-f",
            "video.mp4",
            "video/mp4",
            "-f",
            "data.json",
        ],
    )

    print(f"\nUpload Server: {config.server}")
    print(f"\nFiles to Upload:")
    for file_spec in config.files:
        if len(file_spec) == 2:
            print(f"  {file_spec[0]:20s} (MIME: {file_spec[1]})")
        else:
            print(f"  {file_spec[0]:20s} (MIME: auto-detect)")

    print("\nCLI Used:")
    print(
        "  -f document.pdf application/pdf  # With MIME type\n"
        "  -f image.png                      # Auto-detect MIME\n"
        "  -f video.mp4 video/mp4            # With MIME type\n"
        "  -f data.json                      # Auto-detect MIME"
    )


def example_environment():
    """Example 3: Environment variable definitions with validation."""
    print("\n" + "=" * 70)
    print("Example 3: Environment Variables with Validation")
    print("=" * 70)

    @dataclass
    class AppConfig:
        """Application with environment variable configuration."""

        name: str = cli_short("n")
        environment: str = combine_annotations(
            cli_choices(["dev", "staging", "prod"]), default="dev"
        )

        # Environment variables as KEY VALUE pairs
        env_vars: List[List[str]] = combine_annotations(
            cli_short("e"),
            cli_append(nargs=2),
            cli_help("Environment variable (KEY VALUE)"),
            default_factory=list,
        )

    config = build_config(
        AppConfig,
        args=[
            "-n",
            "myapp",
            "--environment",
            "prod",
            "-e",
            "DEBUG",
            "false",
            "-e",
            "LOG_LEVEL",
            "WARNING",
            "-e",
            "PORT",
            "8080",
            "-e",
            "WORKERS",
            "4",
        ],
    )

    print(f"\nApplication: {config.name}")
    print(f"Environment: {config.environment}")

    print(f"\nEnvironment Variables:")
    for key, value in config.env_vars:
        print(f"  {key:15s} = {value}")

    print("\nCLI Used:")
    print("  -n myapp --environment prod")
    print("  -e DEBUG false -e LOG_LEVEL WARNING -e PORT 8080 -e WORKERS 4")


def example_tags():
    """Example 4: Simple tags (single value per occurrence)."""
    print("\n" + "=" * 70)
    print("Example 4: Simple Tag Collection")
    print("=" * 70)

    @dataclass
    class ProjectConfig:
        """Project configuration with tags."""

        name: str

        # Tags: each -t adds one tag
        tags: List[str] = combine_annotations(
            cli_short("t"),
            cli_append(),
            cli_help("Add a tag"),
            default_factory=list,
        )

    config = build_config(
        ProjectConfig,
        args=[
            "--name",
            "dataclass-args",
            "-t",
            "python",
            "-t",
            "cli",
            "-t",
            "dataclass",
            "-t",
            "argparse",
            "-t",
            "tool",
        ],
    )

    print(f"\nProject: {config.name}")
    print(f"Tags: {', '.join(config.tags)}")

    print("\nCLI Used:")
    print("  --name dataclass-args -t python -t cli -t dataclass -t argparse -t tool")


def example_servers():
    """Example 5: Server pool with host and port pairs."""
    print("\n" + "=" * 70)
    print("Example 5: Server Pool Configuration")
    print("=" * 70)

    @dataclass
    class LoadBalancerConfig:
        """Load balancer with multiple backend servers."""

        name: str

        # Servers: -s HOST PORT (can repeat)
        servers: List[List[str]] = combine_annotations(
            cli_short("s"),
            cli_append(nargs=2),
            cli_help("Backend server (HOST PORT)"),
            default_factory=list,
        )

        health_check: bool = cli_short("h", default=True)

    config = build_config(
        LoadBalancerConfig,
        args=[
            "--name",
            "web-lb",
            "-s",
            "server1.example.com",
            "8080",
            "-s",
            "server2.example.com",
            "8080",
            "-s",
            "server3.example.com",
            "8080",
            "-h",
        ],
    )

    print(f"\nLoad Balancer: {config.name}")
    print(f"Health Check: {config.health_check}")

    print(f"\nBackend Servers:")
    for i, (host, port) in enumerate(config.servers, 1):
        print(f"  {i}. {host}:{port}")

    print("\nCLI Used:")
    print(
        "  -s server1.example.com 8080 -s server2.example.com 8080 -s server3.example.com 8080"
    )


def main():
    """Run examples based on command-line argument."""
    if len(sys.argv) > 1:
        example = sys.argv[1]
        if example == "docker":
            example_docker()
        elif example == "files":
            example_files()
        elif example == "environment":
            example_environment()
        elif example == "tags":
            example_tags()
        elif example == "servers":
            example_servers()
        else:
            print(f"Unknown example: {example}")
            print("\nAvailable examples:")
            print("  docker      - Docker-style -p, -v, -e options")
            print("  files       - File uploads with optional MIME types")
            print("  environment - Environment variable KEY VALUE pairs")
            print("  tags        - Simple tag collection")
            print("  servers     - Server pool with HOST PORT pairs")
            sys.exit(1)
    else:
        # Run all examples
        example_docker()
        example_files()
        example_environment()
        example_tags()
        example_servers()

        print("\n" + "=" * 70)
        print("All Examples Complete!")
        print("=" * 70)
        print("\n💡 Key Points:")
        print("  • cli_append() allows repeating an option multiple times")
        print("  • Each occurrence can take 1+ arguments via nargs")
        print("  • Use List[str] for single values per occurrence")
        print("  • Use List[List[str]] for multiple values per occurrence")
        print("  • Combine with cli_short() for concise CLIs")
        print("  • Validate with __post_init__() for custom constraints")


if __name__ == "__main__":
    main()
