#!/usr/bin/env python3
"""
Example: Nested Dataclass Configuration

Demonstrates using cli_nested() to organize configuration into nested dataclasses.
This helps structure complex configurations while keeping the CLI clean.
"""

from dataclasses import dataclass

from dataclass_args import build_config, cli_help, cli_nested


@dataclass
class DatabaseConfig:
    """Database connection configuration."""

    host: str = cli_help("Database host", default="localhost")
    port: int = cli_help("Database port", default=5432)
    database: str = cli_help("Database name", default="mydb")
    username: str = cli_help("Database username", default="admin")


@dataclass
class LoggingConfig:
    """Logging configuration."""

    level: str = cli_help("Log level (DEBUG, INFO, WARNING, ERROR)", default="INFO")
    file: str = cli_help("Log file path", default="app.log")
    format: str = cli_help("Log format string", default="%(levelname)s: %(message)s")


@dataclass
class AppConfig:
    """Main application configuration with nested sections."""

    # Top-level fields
    app_name: str = cli_help("Application name", default="myapp")
    debug: bool = cli_help("Enable debug mode", default=False)
    workers: int = cli_help("Number of worker threads", default=4)

    # Nested configurations with custom prefixes
    database: DatabaseConfig = cli_nested(prefix="db", default_factory=DatabaseConfig)

    logging: LoggingConfig = cli_nested(prefix="log", default_factory=LoggingConfig)


def main():
    """Build and display configuration."""
    config = build_config(AppConfig)

    print("=" * 60)
    print("Application Configuration")
    print("=" * 60)
    print(f"\nApplication:")
    print(f"  Name:    {config.app_name}")
    print(f"  Debug:   {config.debug}")
    print(f"  Workers: {config.workers}")

    print(f"\nDatabase:")
    print(f"  Host:     {config.database.host}")
    print(f"  Port:     {config.database.port}")
    print(f"  Database: {config.database.database}")
    print(f"  Username: {config.database.username}")

    print(f"\nLogging:")
    print(f"  Level:  {config.logging.level}")
    print(f"  File:   {config.logging.file}")
    print(f"  Format: {config.logging.format}")
    print("\n" + "=" * 60)


if __name__ == "__main__":
    main()


"""
Usage Examples:

1. Use defaults:
   $ python nested_dataclass.py

2. Override application settings:
   $ python nested_dataclass.py --app-name "ProductionApp" --workers 8 --debug

3. Override database settings (note the 'db-' prefix):
   $ python nested_dataclass.py --db-host prod.example.com --db-port 3306 --db-database prod_db

4. Override logging settings (note the 'log-' prefix):
   $ python nested_dataclass.py --log-level DEBUG --log-file /var/log/app.log

5. Mix and match:
   $ python nested_dataclass.py \\
       --app-name "MyService" \\
       --db-host db.example.com \\
       --db-database myservice_db \\
       --log-level WARNING \\
       --workers 16

6. Get help (shows all options including nested):
   $ python nested_dataclass.py --help

Benefits of nested dataclasses:
- Organized, hierarchical configuration structure
- Clear separation of concerns (database, logging, etc.)
- Prefixes prevent naming conflicts
- Type safety within each nested dataclass
- Reusable configuration components
"""
