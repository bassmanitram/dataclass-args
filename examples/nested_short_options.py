#!/usr/bin/env python3
"""
Example: Short Options with Nested Dataclasses

Demonstrates how short options work with nested dataclasses:
- With prefix: Short options are NOT supported (prevents conflicts)
- No prefix (prefix=""): Short options ARE supported
- Collision detection for no-prefix nested fields

Usage Examples:

1. Using short options for top-level and nested (no prefix) fields:
   $ python nested_short_options.py -a "MyApp" -w 8 -u john -p pass123

   Output:
     Application:
       Name:    MyApp
       Workers: 8
     Credentials (no prefix, short options enabled):
       Username: john
       Password: pass123

2. Database fields must use long form (have prefix):
   $ python nested_short_options.py --db-host prod.db.com --db-port 3306

   Note: Cannot use -h or -p for database because it has prefix="db"

3. Mix short and long options:
   $ python nested_short_options.py -a "Service" -u admin --db-host prod.db.com

4. Show help (see which fields have short options):
   $ python nested_short_options.py --help

   You'll see:
     -a APP_NAME, --app-name APP_NAME       (has short option)
     -w WORKERS, --workers WORKERS           (has short option)
     -u USERNAME, --username USERNAME        (nested, no prefix - has short option!)
     -p PASSWORD, --password PASSWORD        (nested, no prefix - has short option!)
     --db-host DB_HOST                       (nested with prefix - NO short option)
     --db-port DB_PORT                       (nested with prefix - NO short option)

Key Points:

1. No Prefix = Short Options Enabled
   When a nested dataclass has prefix="", its fields are completely flattened
   and their short options work just like regular fields.

2. With Prefix = No Short Options
   When a nested dataclass has a prefix (prefix="db"), short options are NOT
   supported for those fields to avoid confusion and conflicts.

3. Collision Detection
   If you try to use the same short option for multiple fields (including
   nested fields with no prefix), you'll get a clear error message:

   Example of collision:
     @dataclass
     class Config:
         app_name: str = cli_short("a")
         nested: Nested = cli_nested(prefix="")  # Nested has field with -a too

   Error:
     Short option collision detected:
       -a
         - app_name (--app-name)
         - nested.name (--name)

4. Best Practices
   - Use prefix="" when you want complete flattening with short options
   - Use prefix="xyz" when you want clear namespacing (no short options)
   - Be mindful of short option collisions when using prefix=""
"""

from dataclasses import dataclass

from dataclass_args import (
    build_config,
    cli_help,
    cli_nested,
    cli_short,
    combine_annotations,
)


@dataclass
class Credentials:
    """Credentials with short options (will be flattened)."""

    username: str = combine_annotations(
        cli_short("u"), cli_help("Username for authentication"), default="admin"
    )
    password: str = combine_annotations(
        cli_short("p"), cli_help("Password for authentication"), default="secret"
    )


@dataclass
class DatabaseConfig:
    """Database config with prefix (short options ignored)."""

    host: str = combine_annotations(
        cli_short("h"),  # This will be IGNORED because prefix="db"
        cli_help("Database host"),
        default="localhost",
    )
    port: int = combine_annotations(
        cli_short("p"),  # This will be IGNORED (no conflict with creds.password)
        cli_help("Database port"),
        default=5432,
    )


@dataclass
class AppConfig:
    """
    Main configuration demonstrating short options with nested dataclasses.

    - creds: No prefix, short options enabled (-u, -p)
    - db: Has prefix, short options disabled (must use --db-host, --db-port)
    """

    app_name: str = combine_annotations(
        cli_short("a"), cli_help("Application name"), default="myapp"
    )

    workers: int = combine_annotations(
        cli_short("w"), cli_help("Number of worker threads"), default=4
    )

    # Nested with NO prefix - short options ARE supported
    creds: Credentials = cli_nested(
        prefix="", default_factory=Credentials  # Empty prefix = flatten completely
    )

    # Nested with prefix - short options NOT supported
    db: DatabaseConfig = cli_nested(
        prefix="db",  # With prefix = short options ignored
        default_factory=DatabaseConfig,
    )


def main():
    """Build and display configuration."""
    config = build_config(AppConfig)

    print("=" * 60)
    print("Configuration with Short Options")
    print("=" * 60)
    print(f"\nApplication:")
    print(f"  Name:    {config.app_name}")
    print(f"  Workers: {config.workers}")

    print(f"\nCredentials (no prefix, short options enabled):")
    print(f"  Username: {config.creds.username}")
    print(f"  Password: {config.creds.password}")

    print(f"\nDatabase (with prefix, short options disabled):")
    print(f"  Host: {config.db.host}")
    print(f"  Port: {config.db.port}")
    print("\n" + "=" * 60)
