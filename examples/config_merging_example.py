#!/usr/bin/env python3
"""
Configuration Merging Example

Demonstrates how to use base_configs to merge multiple configuration sources
with clear hierarchical precedence.

Usage:
    # Simple: just CLI args
    python config_merging_example.py simple --name "MyApp"

    # With base config file
    python config_merging_example.py with-file --name "MyApp"

    # With programmatic base configs
    python config_merging_example.py programmatic --name "MyApp"

    # Full multi-source merge
    python config_merging_example.py multi-source --name "MyApp" --debug
"""

import json
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from dataclass_args import build_config


@dataclass
class AppConfig:
    """Application configuration with multiple sources."""

    name: str
    environment: str = "development"
    region: str = "us-east-1"
    instance_count: int = 1
    debug: bool = False
    log_level: str = "INFO"


def example_simple():
    """Example 1: Simple configuration from CLI args only."""
    print("\n" + "=" * 70)
    print("Example 1: Simple CLI Configuration")
    print("=" * 70)

    config = build_config(
        AppConfig,
        args=["--name", "SimpleApp", "--environment", "staging"],
    )

    print("\nConfiguration:")
    print(f"  Name: {config.name}")
    print(f"  Environment: {config.environment}")
    print(f"  Region: {config.region}")
    print(f"  Instance Count: {config.instance_count}")
    print(f"  Debug: {config.debug}")
    print(f"  Log Level: {config.log_level}")


def example_with_file():
    """Example 2: Configuration from single file."""
    print("\n" + "=" * 70)
    print("Example 2: Single Config File")
    print("=" * 70)

    # Create a config file
    config_data = {
        "name": "FileBasedApp",
        "environment": "production",
        "instance_count": 5,
        "log_level": "WARNING",
    }

    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".json", delete=False
    ) as config_file:
        json.dump(config_data, config_file)
        config_path = config_file.name

    try:
        print(f"\nConfig file content: {json.dumps(config_data, indent=2)}")

        # Load from file, override with CLI
        config = build_config(
            AppConfig,
            args=["--region", "eu-west-1"],  # CLI override
            base_configs=config_path,  # Single file path
        )

        print("\nFinal Configuration:")
        print(f"  Name: {config.name} (from file)")
        print(f"  Environment: {config.environment} (from file)")
        print(f"  Region: {config.region} (CLI override)")
        print(f"  Instance Count: {config.instance_count} (from file)")
        print(f"  Debug: {config.debug} (default)")
        print(f"  Log Level: {config.log_level} (from file)")
    finally:
        Path(config_path).unlink()


def example_programmatic():
    """Example 3: Programmatic configuration with dict."""
    print("\n" + "=" * 70)
    print("Example 3: Programmatic Dict Configuration")
    print("=" * 70)

    # Define base config programmatically
    base_config = {
        "name": "ProgrammaticApp",
        "environment": "development",
        "debug": True,
        "log_level": "DEBUG",
    }

    print(f"\nBase config dict: {json.dumps(base_config, indent=2)}")

    config = build_config(
        AppConfig,
        args=["--instance-count", "3"],  # CLI override
        base_configs=base_config,  # Single dict
    )

    print("\nFinal Configuration:")
    print(f"  Name: {config.name} (from dict)")
    print(f"  Environment: {config.environment} (from dict)")
    print(f"  Region: {config.region} (default)")
    print(f"  Instance Count: {config.instance_count} (CLI override)")
    print(f"  Debug: {config.debug} (from dict)")
    print(f"  Log Level: {config.log_level} (from dict)")


def example_multi_source():
    """Example 4: Multi-source configuration merge."""
    print("\n" + "=" * 70)
    print("Example 4: Multi-Source Configuration Merge")
    print("=" * 70)

    # Create company-wide defaults file
    company_defaults = {
        "name": "CompanyApp",
        "region": "us-east-1",
        "instance_count": 1,
        "log_level": "INFO",
    }
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump(company_defaults, f)
        company_path = f.name

    # Create environment-specific file
    env_config = {
        "environment": "production",
        "instance_count": 5,
        "log_level": "WARNING",
    }
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump(env_config, f)
        env_path = f.name

    # Create user overrides file
    user_overrides = {"region": "eu-west-1", "debug": False}
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump(user_overrides, f)
        user_path = f.name

    try:
        print("\nConfiguration sources:")
        print(f"1. Company defaults: {json.dumps(company_defaults, indent=2)}")
        print(f"2. Environment config: {json.dumps(env_config, indent=2)}")
        print(f"3. Team-specific dict: {{'name': 'TeamApp', 'log_level': 'ERROR'}}")
        print(f"4. User overrides (--config): {json.dumps(user_overrides, indent=2)}")
        print("5. CLI args: --name 'FinalApp' --debug")

        print("\nMerge order (later overrides earlier):")
        print("  1. company-defaults.json (lowest priority)")
        print("  2. env-production.json")
        print("  3. team dict")
        print("  4. user-overrides.json (from --config)")
        print("  5. CLI args (highest priority)")

        config = build_config(
            AppConfig,
            args=[
                "--config",
                user_path,  # User overrides file
                "--name",
                "FinalApp",  # CLI override
                "--debug",  # CLI override
            ],
            base_configs=[
                company_path,  # Company defaults (priority 1)
                env_path,  # Environment config (priority 2)
                {
                    "name": "TeamApp",
                    "log_level": "ERROR",
                },  # Team dict (priority 3)
            ],
        )

        print("\nFinal Configuration:")
        print(f"  Name: {config.name} (from CLI - highest priority)")
        print(f"  Environment: {config.environment} (from env config)")
        print(f"  Region: {config.region} (from user overrides)")
        print(f"  Instance Count: {config.instance_count} (from env config)")
        print(f"  Debug: {config.debug} (from CLI)")
        print(f"  Log Level: {config.log_level} (from team dict)")

        print("\nTrace:")
        print(
            "  name: company → env (no change) → team 'TeamApp' → user (no change) → CLI 'FinalApp' ✓"
        )
        print("  environment: company (default) → env 'production' ✓")
        print("  region: company 'us-east-1' → user 'eu-west-1' ✓")
        print("  instance_count: company 1 → env 5 ✓")
        print("  debug: company (default) → user False → CLI True ✓")
        print("  log_level: company 'INFO' → env 'WARNING' → team 'ERROR' ✓")

    finally:
        Path(company_path).unlink()
        Path(env_path).unlink()
        Path(user_path).unlink()


def example_testing_pattern():
    """Example 5: Testing pattern with fixtures."""
    print("\n" + "=" * 70)
    print("Example 5: Testing Pattern with Fixtures")
    print("=" * 70)

    # Test fixture as a dict
    test_fixture = {
        "name": "test-app",
        "environment": "test",
        "region": "us-east-1",
        "instance_count": 1,
        "debug": True,
        "log_level": "DEBUG",
    }

    print(f"\nTest fixture: {json.dumps(test_fixture, indent=2)}")

    # Override specific values for this test
    config = build_config(
        AppConfig,
        args=["--name", "specific-test", "--instance-count", "2"],
        base_configs=test_fixture,
    )

    print("\nTest Configuration:")
    print(f"  Name: {config.name} (test override)")
    print(f"  Environment: {config.environment} (from fixture)")
    print(f"  Region: {config.region} (from fixture)")
    print(f"  Instance Count: {config.instance_count} (test override)")
    print(f"  Debug: {config.debug} (from fixture)")
    print(f"  Log Level: {config.log_level} (from fixture)")

    print("\nThis pattern is useful for:")
    print("  - Unit testing with consistent fixtures")
    print("  - Integration testing with environment-specific configs")
    print("  - Parameterized tests with programmatic config variations")


def main():
    """Run all examples."""
    if len(sys.argv) > 1:
        example = sys.argv[1]
        if example == "simple":
            example_simple()
        elif example == "with-file":
            example_with_file()
        elif example == "programmatic":
            example_programmatic()
        elif example == "multi-source":
            example_multi_source()
        elif example == "testing":
            example_testing_pattern()
        else:
            print(f"Unknown example: {example}")
            print(
                "Available examples: simple, with-file, programmatic, multi-source, testing"
            )
    else:
        # Run all examples
        example_simple()
        example_with_file()
        example_programmatic()
        example_multi_source()
        example_testing_pattern()

    print("\n" + "=" * 70)
    print("Examples Complete!")
    print("=" * 70)


if __name__ == "__main__":
    main()
