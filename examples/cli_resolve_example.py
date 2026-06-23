#!/usr/bin/env python3
"""
Example: Post-Load Field Resolution with cli_resolve()

Demonstrates using cli_resolve() to transform dict configuration values
into typed objects after all config sources are merged.

This pattern is useful when:
- A config field needs to become a typed object (not just a dict)
- The object type depends on config values (factory pattern)
- You want to keep config files simple (plain dicts) but work with rich objects

Usage Examples:

1. Use base config (defaults):
   $ python cli_resolve_example.py --app-name "MyApp"

2. Load sandbox from a JSON file:
   $ python cli_resolve_example.py --sandbox sandbox.json

3. Load sandbox from file and override a property:
   $ python cli_resolve_example.py --sandbox sandbox.json --s image:python:3.12

4. Use with --config for full application config:
   $ python cli_resolve_example.py --config app_config.json

5. Provide base configs programmatically (for demonstration, uses defaults below):
   $ python cli_resolve_example.py --app-name "ProdApp"

How it works:
- The field type is `Optional[SandboxBase]` (the FINAL type)
- During parsing, it's treated as a dict field (file path + property overrides)
- After all config assembly, the resolver transforms dict → typed object
- If value is None, resolver is never called
"""

import json
import os
import sys
import tempfile
from dataclasses import dataclass
from typing import Any, Optional

from dataclass_args import (
    build_config,
    cli_help,
    cli_resolve,
    cli_short,
    combine_annotations,
)

# ============================================================================
# Domain types (what you'd have in your application)
# ============================================================================


class SandboxBase:
    """Base class for sandbox environments."""

    def describe(self) -> str:
        raise NotImplementedError


class DockerSandbox(SandboxBase):
    """Docker container-based sandbox."""

    def __init__(self, image: str = "python:3.11", memory: str = "512m"):
        self.image = image
        self.memory = memory

    def describe(self) -> str:
        return f"Docker(image={self.image}, memory={self.memory})"


class LocalSandbox(SandboxBase):
    """Local filesystem sandbox for development."""

    def __init__(self, path: str = "/tmp/sandbox"):
        self.path = path

    def describe(self) -> str:
        return f"Local(path={self.path})"


# ============================================================================
# Resolver function (the factory logic)
# ============================================================================


def resolve_sandbox(value: Any) -> SandboxBase:
    """
    Transform raw config value into a Sandbox instance.

    This is the resolver function passed to cli_resolve(). It receives
    the assembled raw value (typically a dict from config files) and
    returns the final typed object.

    For pre-built objects (e.g., from programmatic base_configs), it
    passes them through unchanged.
    """
    if isinstance(value, SandboxBase):
        # Pre-built object - pass through
        return value

    if isinstance(value, dict):
        sandbox_type = value.get("type", "local")
        if sandbox_type == "docker":
            return DockerSandbox(
                image=value.get("image", "python:3.11"),
                memory=value.get("memory", "512m"),
            )
        elif sandbox_type == "local":
            return LocalSandbox(path=value.get("path", "/tmp/sandbox"))
        else:
            raise ValueError(f"Unknown sandbox type: {sandbox_type}")

    raise ValueError(f"Cannot resolve sandbox from: {type(value).__name__}")


# ============================================================================
# Configuration dataclass
# ============================================================================


@dataclass
class AppConfig:
    """Application configuration with a resolved sandbox field."""

    app_name: str = combine_annotations(
        cli_short("n"),
        cli_help("Application name"),
        default="myapp",
    )

    debug: bool = combine_annotations(
        cli_short("d"),
        cli_help("Enable debug mode"),
        default=False,
    )

    # The cli_resolve field:
    # - Type is Optional[SandboxBase] (final type for type checking)
    # - During parsing: treated as dict (supports file path + overrides)
    # - After assembly: resolve_sandbox() transforms dict → SandboxBase instance
    sandbox: Optional[SandboxBase] = combine_annotations(
        cli_resolve(resolver=resolve_sandbox),
        cli_help("Sandbox configuration"),
        default=None,
    )


# ============================================================================
# Main
# ============================================================================


def main():
    """Demonstrate cli_resolve functionality."""
    # Create a sample config file for demonstration
    sample_config = {"type": "docker", "image": "python:3.11", "memory": "1g"}

    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".json", delete=False, prefix="sandbox_"
    ) as f:
        json.dump(sample_config, f)
        sample_file = f.name

    try:
        print("=" * 60)
        print("cli_resolve() Example")
        print("=" * 60)

        # If no CLI args beyond script name, demonstrate with base_configs
        if len(sys.argv) <= 1:
            print("\n[Demo mode: Using base_configs with sandbox dict]")
            print(f"[Sample sandbox config file created at: {sample_file}]")
            print(f"\nTry: python {sys.argv[0]} --sandbox {sample_file}")
            print(
                f"Or:  python {sys.argv[0]} --sandbox {sample_file} --s image:node:18"
            )
            print()

            config = build_config(
                AppConfig,
                args=["--app-name", "DemoApp"],
                base_configs={
                    "sandbox": {
                        "type": "docker",
                        "image": "python:3.11",
                        "memory": "2g",
                    }
                },
            )
        else:
            config = build_config(AppConfig)

        print(f"\nConfiguration:")
        print(f"  App Name: {config.app_name}")
        print(f"  Debug:    {config.debug}")

        if config.sandbox:
            print(f"  Sandbox:  {config.sandbox.describe()}")
            print(f"  Type:     {type(config.sandbox).__name__}")
        else:
            print(f"  Sandbox:  None (not configured)")

        print("\n" + "=" * 60)
    finally:
        os.unlink(sample_file)


if __name__ == "__main__":
    main()
