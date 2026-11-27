# Dataclass Args

Generate command-line interfaces from Python dataclasses.

[![Tests](https://github.com/bassmanitram/dataclass-args/actions/workflows/test.yml/badge.svg)](https://github.com/bassmanitram/dataclass-args/actions/workflows/test.yml)
[![Lint](https://github.com/bassmanitram/dataclass-args/actions/workflows/lint.yml/badge.svg)](https://github.com/bassmanitram/dataclass-args/actions/workflows/lint.yml)
[![Code Quality](https://github.com/bassmanitram/dataclass-args/actions/workflows/quality.yml/badge.svg)](https://github.com/bassmanitram/dataclass-args/actions/workflows/quality.yml)
[![Examples](https://github.com/bassmanitram/dataclass-args/actions/workflows/examples.yml/badge.svg)](https://github.com/bassmanitram/dataclass-args/actions/workflows/examples.yml)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![PyPI version](https://img.shields.io/pypi/v/dataclass-args.svg)](https://pypi.org/project/dataclass-args/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

## Features

- **[Automatic CLI Generation](#quick-start)** - Generate CLI from dataclass definitions
- **[Type-Safe Parsing](#type-support)** - Type-aware argument parsing for standard Python types
- **[Nested Dataclasses](#nested-dataclasses)** - Organize configs hierarchically with automatic flattening
- **[Positional Arguments](#positional-arguments)** - Support for positional args with `cli_positional()`
- **[Short Options](#short-options)** - Concise `-n` flags in addition to `--name`
- **[Boolean Flags](#boolean-flags)** - Proper `--flag` and `--no-flag` boolean handling
- **[Value Validation](#value-choices)** - Restrict values with `cli_choices()`
- **[Repeatable Options](#repeatable-options)** - Allow options to be specified multiple times with `cli_append()`
- **[File Loading](#file-loadable-parameters)** - Load parameters from files using `@filename` syntax
- **[Config Merging](#configuration-merging)** - Combine configuration sources with hierarchical overrides
- **[Deep Merge](#deep-merge)** - Opt-in recursive dict merging with `merge_strategy="deep"`
- **[Layered Configuration](#layered-configuration)** - Named layers, per-field list-merge rules (`cli_list_merge()`) and provenance (which layer set what)
- **[Property Overrides](#dict-field-property-overrides)** - Set individual dict properties with `--mc key:value` and list indexing
- **[Flexible Types](#type-support)** - Support for `List`, `Dict`, `Optional`, and custom types
- **[Field Resolution](#field-resolution)** - Transform config dicts into typed objects with `cli_resolve()`
- **[Object Instantiation](#object-instantiation)** - Construct objects from config using `instantiate()`
- **[Rich Annotations](#combining-annotations)** - Custom help text, exclusions, and combinations
- **[Programmatic Usage](#programmatic-usage)** - Build configs from dicts without CLI via `build_config_from_dict()`
- **[Zero Dependencies](#installation)** - No runtime dependencies; optional YAML support
## Quick Start

### Installation

```bash
pip install dataclass-args              # requires Python 3.11+

# With optional format support
pip install "dataclass-args[yaml]"      # YAML config files (JSON and TOML are built in)
pip install "dataclass-args[all]"       # All optional dependencies
```

### Basic Usage

```python
from dataclasses import dataclass
from dataclass_args import build_config

@dataclass
class Config:
    name: str
    count: int = 10
    debug: bool = False

# Generate CLI from dataclass
config = build_config(Config)

# Use your config
print(f"Running {config.name} with count={config.count}, debug={config.debug}")
```

```bash
$ python app.py --name "MyApp" --count 5 --debug
Running MyApp with count=5, debug=True

$ python app.py --help
usage: app.py [-h] [--config CONFIG] [--name NAME] [--count COUNT] [--debug] [--no-debug]

Build Config from CLI

options:
  -h, --help       show this help message and exit
  --config CONFIG  Base configuration file (JSON, YAML, or TOML)
  --name NAME      name
  --count COUNT    count
  --debug          debug (default: False)
  --no-debug       Disable debug
```

## Core Features

### Short Options

Add concise short flags to your CLI:

```python
from dataclass_args import cli_short

@dataclass
class ServerConfig:
    host: str = cli_short('H', default="localhost")
    port: int = cli_short('p', default=8000)
    debug: bool = cli_short('d', default=False)
```

```bash
# Use short forms
$ python server.py -H 0.0.0.0 -p 9000 -d

# Or long forms
$ python server.py --host 0.0.0.0 --port 9000 --debug

# Mix and match
$ python server.py -H 0.0.0.0 --port 9000 -d
```

`-h` is reserved for `--help`. Every option name is checked when the builder is constructed: short options, long options, `--no-` flags, dict override options and the `--config` option. Any clash raises `ConfigBuilderError`, naming the clashing fields and suggesting a fix.

### Boolean Flags

Booleans work as proper CLI flags with negative forms:

```python
@dataclass
class BuildConfig:
    test: bool = True      # Default enabled
    deploy: bool = False   # Default disabled
```

```bash
# Enable a flag
$ python build.py --deploy

# Disable a flag
$ python build.py --no-test

# Use defaults (omit flags)
$ python build.py  # test=True, deploy=False
```

With short options:

```python
@dataclass
class Config:
    verbose: bool = cli_short('v', default=False)
    debug: bool = cli_short('d', default=False)
```

```bash
$ python app.py -v -d              # Short flags
$ python app.py --verbose --debug  # Long flags
$ python app.py --no-verbose       # Negative form
```

### Value Choices

Restrict field values to a valid set:

```python
from dataclass_args import cli_choices

@dataclass
class DeployConfig:
    environment: str = cli_choices(['dev', 'staging', 'prod'])
    region: str = cli_choices(['us-east-1', 'us-west-2', 'eu-west-1'], default='us-east-1')
    size: str = cli_choices(['small', 'medium', 'large'], default='medium')
```

```bash
# Valid choices
$ python deploy.py --environment prod --region us-west-2

# Invalid choice shows error
$ python deploy.py --environment invalid
error: argument --environment: invalid choice: 'invalid' (choose from 'dev', 'staging', 'prod')
```



### Repeatable Options

Use `cli_append()` to allow an option to be specified multiple times, with each occurrence collecting its own arguments:

```python
from dataclass_args import cli_append

@dataclass
class Config:
    # Simple tags: each -t adds one value
    tags: List[str] = combine_annotations(
        cli_short('t'),
        cli_append(),
        cli_help("Add a tag"),
        default_factory=list
    )
```

```bash
# Each -t occurrence accumulates
$ python app.py -t python -t cli -t tool
# Result: ['python', 'cli', 'tool']
```

#### Repeatable List Flags (`cli_extend`)

A plain `List[T]` option takes several values after **one** flag (`--tags a b c`). If the flag is **repeated**, only the **last** occurrence is kept (argparse's default): `--tags a --tags b` gives `['b']`. To make repeats accumulate into one flat list, add `cli_extend()`:

```python
from dataclass_args import cli_extend

@dataclass
class Config:
    paths: List[str] = combine_annotations(
        cli_short('p'),
        cli_extend(),
        cli_help("Config files"),
        default_factory=list
    )
```

```bash
$ python app.py -p a.json -p b.json       # ['a.json', 'b.json']
$ python app.py -p a.json b.json -p c.json  # ['a.json', 'b.json', 'c.json']
```

How it combines with other sources:
- If the flag is omitted, earlier sources (`base_configs`, `--config`) and the dataclass default keep their value.
- If the flag is given, the accumulated CLI list **replaces** earlier sources as a whole. It's never appended to a default or to a config-file value. Use [list-merge rules](#layered-configuration) to combine lists *between* config sources.

Details:
- Element types are converted (`List[int]`: `-n 1 -n 2 3` → `[1, 2, 3]`), and `cli_choices` applies to every value.
- For `Optional[List[T]]`, giving the flag with no values yields `[]`.
- Works in nested dataclasses at any depth.
- The help text reads "(specify one or more values; repeatable)".

`cli_extend` versus `cli_append`: `cli_extend` flattens every occurrence into one list, while `cli_append` keeps one entry (or sub-list) per occurrence. They're mutually exclusive. `cli_extend` raises `ConfigBuilderError` if it's:
- combined with `cli_append`, `cli_positional` or `cli_exclude`;
- used on a non-list field;
- used on a list with non-scalar elements (lists, tuples, sets, dicts, dataclasses).

Elements may be any scalar type, or a union or `Optional` of scalars, e.g. `List[Union[str, Path]]` or `list[str | Path]`. Element values are exactly what the plain list option produces.

#### Repeatable with Multiple Arguments

Each occurrence can take multiple arguments using `nargs`:

```python
@dataclass
class DockerConfig:
    # Each -p takes exactly 2 arguments (HOST CONTAINER)
    ports: List[List[str]] = combine_annotations(
        cli_short('p'),
        cli_append(nargs=2),
        cli_help("Port mapping (HOST CONTAINER)"),
        default_factory=list
    )

    # Each -v takes exactly 2 arguments (SOURCE TARGET)
    volumes: List[List[str]] = combine_annotations(
        cli_short('v'),
        cli_append(nargs=2),
        cli_help("Volume mount (SOURCE TARGET)"),
        default_factory=list
    )
```

```bash
$ python docker.py -p 8080 80 -p 8443 443 -v /host/data /container/data
```

#### Variable Arguments with Validation

Use `min_args` and `max_args` for flexible argument counts with automatic validation:

```python
@dataclass
class UploadConfig:
    files: List[List[str]] = combine_annotations(
        cli_short('f'),
        cli_append(min_args=1, max_args=2, metavar="FILE [MIMETYPE]"),
        cli_help("File with optional MIME type"),
        default_factory=list
    )
    # No __post_init__ needed - validation is automatic!
```

```bash
# Mix files with and without MIME types
$ python upload.py -f doc.pdf application/pdf -f image.png -f video.mp4 video/mp4
# Result: [['doc.pdf', 'application/pdf'], ['image.png'], ['video.mp4', 'video/mp4']]

# Validation catches errors automatically
$ python upload.py -f file1 arg2 arg3 arg4
# Error: Expected at most 2 argument(s), got 4
```

**Clean help display:**
```
-f FILE [MIMETYPE], --files FILE [MIMETYPE]
    File with optional MIME type (can be repeated, 1-2 args each)
```

**Parameters:**
- `min_args`: Minimum arguments per occurrence
- `max_args`: Maximum arguments per occurrence
- Must be used together (both or neither)
- Mutually exclusive with `nargs`

**nargs Options:**
- `None` - One value per occurrence → `List[T]`
- `int` (e.g., `2`) - Exact count per occurrence → `List[List[T]]`
- `'+'` - One or more per occurrence → `List[List[T]]`
- `'*'` - Zero or more per occurrence → `List[List[T]]`

**Use Cases:**
- Docker-style options: `-p 8080:80 -p 8443:443 -v /host:/container -e KEY=value`
- File operations: `-f file1 type1 -f file2 -f file3 type3`
- Server pools: `-s host1 port1 -s host2 port2`
- Build systems: `-I dir1 -I dir2 --define KEY VAL`

### Positional Arguments

Add positional arguments that don't require `--` prefixes:

```python
from dataclass_args import cli_positional

@dataclass
class CopyCommand:
    source: str = cli_positional(help="Source file")
    dest: str = cli_positional(help="Destination file")
    recursive: bool = cli_short('r', default=False)
```

```bash
# Positional arguments are matched by position
$ python cp.py source.txt destination.txt -r

# Optional flags can appear anywhere
$ python cp.py -r source.txt destination.txt
```

#### Variable Number of Arguments

Use `nargs` to accept multiple values:

```python
from typing import List

@dataclass
class GitCommit:
    command: str = cli_positional(help="Git command")
    files: List[str] = cli_positional(nargs='+', help="Files to commit")
    message: str = cli_short('m', default="")

# CLI: python git.py commit file1.py file2.py file3.py -m "Add feature"
```

**nargs Options:**
- `None` (default) - Exactly one value (required)
- `'?'` - Zero or one value (optional)
- `'*'` - Zero or more values (optional list)
- `'+'` - One or more values (required list)
- `int` (e.g., `2`) - Exact count (required list)

#### Optional Positional Arguments

```python
@dataclass
class Convert:
    input_file: str = cli_positional(help="Input file")
    output_file: str = cli_positional(
        nargs='?',
        default='stdout',
        help="Output file (default: stdout)"
    )
    format: str = cli_short('f', default='json')
```

```bash
# With output file
$ python convert.py input.json output.yaml -f yaml

# Without output file (uses default)
$ python convert.py input.json -f xml
```

#### ⚠️ Positional List Constraints

Positional arguments with variable length have important constraints:

**Rules:**
1. At most ONE positional field can use `nargs='*'` or `'+'`
2. If present, the positional list must be the LAST positional argument
3. For multiple lists, use optional arguments with flags

**Valid:**
```python
@dataclass
class Valid:
    command: str = cli_positional()          # First
    files: List[str] = cli_positional(nargs='+')  # Last (OK!)
    exclude: List[str] = cli_short('e', default_factory=list)  # Optional list with flag (OK!)
```

**Invalid:**
```python
@dataclass
class Invalid:
    files: List[str] = cli_positional(nargs='+')  # Positional list
    output: str = cli_positional()                 # ERROR: positional after list!

# ConfigBuilderError: Positional list argument must be last.
# Fix: Make output an optional argument with a flag
```

**Why?** Positional lists are greedy and consume all remaining values. The parser can't determine where one positional list ends and another begins without `--` flags.

#### Positional Values from Config Sources

- **Required positionals** (`nargs` of `None`, `'+'` or an integer) are part of the command-line contract. They must be given on the command line, and a value in `base_configs` or `--config` can't satisfy them.
- **Optional positionals** (`nargs='?'` or `'*'`) behave like any other field. A config source can set them, and the command line overrides it.
- In `build_config_from_dict` there is no command line, so every positional, required or not, comes from the config dict.

### Combining Annotations

Use `combine_annotations()` to merge multiple features:

```python
from dataclass_args import combine_annotations, cli_short, cli_choices, cli_help

@dataclass
class AppConfig:
    # Combine short option + help text
    name: str = combine_annotations(
        cli_short('n'),
        cli_help("Application name")
    )

    # Combine short + choices + help
    environment: str = combine_annotations(
        cli_short('e'),
        cli_choices(['dev', 'staging', 'prod']),
        cli_help("Deployment environment"),
        default='dev'
    )

    # Boolean with short + help
    debug: bool = combine_annotations(
        cli_short('d'),
        cli_help("Enable debug mode"),
        default=False
    )
```

```bash
# Concise CLI usage
$ python app.py -n myapp -e prod -d

# Clear help output
$ python app.py --help
options:
  -h, --help            show this help message and exit
  --config CONFIG       Base configuration file (JSON, YAML, or TOML)
  -n NAME, --name NAME  Application name
  -e {dev,staging,prod}, --environment {dev,staging,prod}
                        Deployment environment (choices: dev, staging, prod)
  -d, --debug           Enable debug mode (default: False)
  --no-debug            Disable --debug
```

(Python 3.13+ prints short options without the metavar repeated: `-n, --name NAME`.)

### Real-World Example

```python
from dataclasses import dataclass
from dataclass_args import build_config, cli_short, cli_choices, cli_help, combine_annotations

@dataclass
class DeploymentConfig:
    """Configuration for application deployment."""

    # Basic settings with short options
    name: str = combine_annotations(
        cli_short('n'),
        cli_help("Application name")
    )

    version: str = combine_annotations(
        cli_short('v'),
        cli_help("Version to deploy"),
        default='latest'
    )

    # Validated choices
    environment: str = combine_annotations(
        cli_short('e'),
        cli_choices(['dev', 'staging', 'prod']),
        cli_help("Target environment"),
        default='dev'
    )

    region: str = combine_annotations(
        cli_short('r'),
        cli_choices(['us-east-1', 'us-west-2', 'eu-west-1']),
        cli_help("AWS region"),
        default='us-east-1'
    )

    size: str = combine_annotations(
        cli_short('s'),
        cli_choices(['small', 'medium', 'large', 'xlarge']),
        cli_help("Instance size"),
        default='medium'
    )

    # Boolean flags
    dry_run: bool = combine_annotations(
        cli_short('d'),
        cli_help("Perform dry run without deploying"),
        default=False
    )

    notify: bool = combine_annotations(
        cli_short('N'),
        cli_help("Send deployment notifications"),
        default=True
    )

if __name__ == "__main__":
    config = build_config(DeploymentConfig)

    print(f"Deploying {config.name} v{config.version}")
    print(f"Environment: {config.environment}")
    print(f"Region: {config.region}")
    print(f"Size: {config.size}")
    print(f"Dry run: {config.dry_run}")
    print(f"Notify: {config.notify}")
```

```bash
# Production deployment
$ python deploy.py -n myapp -v 2.1.0 -e prod -r us-west-2 -s large

# Dry run in staging
$ python deploy.py -n myapp -e staging -d --no-notify

# Help shows everything clearly
$ python deploy.py --help
```

## Advanced Features

### File-Loadable Parameters

Load string parameters from files using the `@filename` syntax. Supports home directory expansion with `~`:

```python
from dataclass_args import cli_file_loadable

@dataclass
class AppConfig:
    name: str = cli_help("Application name", default="app")
    system_prompt: str = cli_file_loadable(default="You are a helpful assistant")
    welcome_message: str = cli_file_loadable(default="Welcome!")

config = build_config(AppConfig)
```

```bash
# Use literal values
$ python app.py --system-prompt "You are a coding assistant"

# Load from files (absolute paths)
$ python app.py --system-prompt "@/etc/prompts/assistant.txt"

# Load from home directory
$ python app.py --system-prompt "@~/prompts/assistant.txt"

# Load from another user's home
$ python app.py --system-prompt "@~alice/shared/prompt.txt"

# Load from relative paths
$ python app.py --welcome-message "@messages/welcome.txt"

# Mix literal and file-loaded values
$ python app.py --name "MyApp" --system-prompt "@~/prompts/assistant.txt"
```

**Path Expansion:**
- `@~/file.txt` → Expands to user's home directory (e.g., `/home/user/file.txt`)
- `@~username/file.txt` → Expands to specified user's home directory
- `@/absolute/path` → Used as-is
- `@relative/path` → Relative to current working directory

### Nested Dataclasses

Organize complex configurations into nested dataclasses with automatic CLI flattening. Use `cli_nested()` to create hierarchical configs that are exposed as flat CLI arguments with customizable prefixes.

Nesting works at any depth. A `cli_nested` dataclass inside another one is flattened recursively, combining the prefixes from each level (`--mid-inner-v`), and is rebuilt as real dataclass instances.

```python
from dataclass_args import cli_nested

@dataclass
class DatabaseConfig:
    host: str = "localhost"
    port: int = 5432
    username: str = "admin"
    password: str = "secret"

@dataclass
class CacheConfig:
    host: str = "localhost"
    port: int = 6379
    ttl: int = 3600

@dataclass
class AppConfig:
    app_name: str = "myapp"
    debug: bool = False

    # Nested with custom prefix
    database: DatabaseConfig = cli_nested(prefix="db", default_factory=DatabaseConfig)

    # Nested with custom prefix
    cache: CacheConfig = cli_nested(prefix="cache", default_factory=CacheConfig)

config = build_config(AppConfig)
```

```bash
# All nested fields are flattened with prefixes
$ python app.py \
    --app-name "MyApp" \
    --db-host prod-db.example.com \
    --db-port 5432 \
    --db-username dbuser \
    --cache-host redis.example.com \
    --cache-ttl 7200

# Help shows all flattened fields
$ python app.py --help
options:
  -h, --help            show this help message and exit
  --config CONFIG       Base configuration file (JSON, YAML, or TOML)
  --app-name APP_NAME   app_name
  --debug               debug (default: False)
  --no-debug            Disable debug
  --db-host DB_HOST     database.host
  --db-port DB_PORT     database.port
  --db-username DB_USERNAME
                        database.username
  --db-password DB_PASSWORD
                        database.password
  --cache-host CACHE_HOST
                        cache.host
  --cache-port CACHE_PORT
                        cache.port
  --cache-ttl CACHE_TTL
                        cache.ttl
```

#### Prefix Modes

**Custom Prefix:**
```python
database: DatabaseConfig = cli_nested(prefix="db", default_factory=DatabaseConfig)
# CLI: --db-host, --db-port, --db-username
```

**No Prefix (Complete Flattening):**
```python
credentials: Credentials = cli_nested(prefix="", default_factory=Credentials)
# CLI: --username, --password (no prefix)
```

**Auto Prefix (Uses Field Name):**
```python
database: DatabaseConfig = cli_nested(default_factory=DatabaseConfig)
# CLI: --database-host, --database-port (field name as prefix)
```

Underscores in a prefix are currently kept in the positive option (`primary_db: DatabaseConfig = cli_nested(...)` gives `--primary_db-host`), while negative boolean flags hyphenate them (`--no-primary-db-ssl`). Normalising prefixes to hyphens is planned; see [FUTURE_CHANGES.md](FUTURE_CHANGES.md).

#### Short Options with Nested Fields

Short options behave differently based on the prefix:

**With Prefix** → Short options are **ignored**, for every field type including booleans (so the same dataclass can be nested twice without clashes):
```python
@dataclass
class ServerConfig:
    host: str = cli_short("H", default="localhost")
    port: int = cli_short("p", default=8080)

@dataclass
class Config:
    server: ServerConfig = cli_nested(prefix="srv", default_factory=ServerConfig)

# CLI: --srv-host, --srv-port (no -H or -p for nested fields)
```

**No Prefix** → Short options are **enabled**:
```python
@dataclass
class Credentials:
    username: str = cli_short("u", default="admin")
    password: str = cli_short("p", default="secret")

@dataclass
class Config:
    app_name: str = cli_short("a", default="app")
    creds: Credentials = cli_nested(prefix="", default_factory=Credentials)

# CLI: -a, -u, -p all work! (completely flattened)
```

```bash
# Use short options for all fields
$ python app.py -a MyApp -u john -p secretpass
```

#### Collision Detection

Automatic collision detection prevents field name and short option conflicts:

**Field Name Collision:**
```python
@dataclass
class Nested:
    name: str = "nested"

@dataclass
class Config:
    name: str = "parent"
    nested: Nested = cli_nested(prefix="", default_factory=Nested)

# ERROR: Field name collision detected:
#   --name
#     - name
#     - nested.name
# Solution: Add prefix to nested field or rename
```

**Short Option Collision:**
```python
@dataclass
class Nested:
    host: str = cli_short("x", default="nested-host")

@dataclass
class Config:
    proxy: str = cli_short("x", default="none")
    nested: Nested = cli_nested(prefix="", default_factory=Nested)

# ERROR: Short option collision detected:
#   -x
#     - proxy (--proxy)
#     - nested.host (--host)
# Solution: Use different short options or add prefix
```

#### Config File Merging with Nested Fields

Nested dataclasses work seamlessly with config files:

**config.yaml:**
```yaml
app_name: "ProductionApp"
database:
  host: "prod-db.example.com"
  port: 5432
  username: "prod_user"
cache:
  host: "redis.example.com"
  ttl: 7200
```

```python
config = build_config(AppConfig, args=[
    '--config', 'config.yaml',
    '--db-password', 'secret',      # Override specific nested field
    '--cache-ttl', '3600'            # Override another nested field
])

# Result:
# - app_name: "ProductionApp" (from file)
# - database.host: "prod-db.example.com" (from file)
# - database.password: "secret" (CLI override)
# - cache.host: "redis.example.com" (from file)
# - cache.ttl: 3600 (CLI override)
```

#### Real-World Example

```python
from dataclasses import dataclass
from dataclass_args import build_config, cli_nested, cli_short, cli_help, combine_annotations

@dataclass
class DatabaseConfig:
    """Database connection settings."""
    host: str = cli_help("Database hostname", default="localhost")
    port: int = cli_help("Database port", default=5432)
    database: str = cli_help("Database name", default="mydb")
    username: str = cli_help("Database username", default="admin")
    password: str = cli_help("Database password", default="")

@dataclass
class LoggingConfig:
    """Logging configuration."""
    level: str = combine_annotations(
        cli_help("Log level"),
        cli_choices(["DEBUG", "INFO", "WARNING", "ERROR"]),
        default="INFO"
    )
    file: str = cli_help("Log file path", default="app.log")
    format: str = cli_help("Log format string", default="%(levelname)s: %(message)s")

@dataclass
class AppConfig:
    """Application configuration with nested sections."""

    # Top-level settings
    app_name: str = combine_annotations(
        cli_short("n"),
        cli_help("Application name"),
        default="myapp"
    )

    debug: bool = combine_annotations(
        cli_short("d"),
        cli_help("Enable debug mode"),
        default=False
    )

    workers: int = combine_annotations(
        cli_short("w"),
        cli_help("Number of worker threads"),
        default=4
    )

    # Nested configurations
    database: DatabaseConfig = cli_nested(
        prefix="db",
        default_factory=DatabaseConfig
    )

    logging: LoggingConfig = cli_nested(
        prefix="log",
        default_factory=LoggingConfig
    )

if __name__ == "__main__":
    config = build_config(AppConfig)

    print(f"App: {config.app_name}")
    print(f"Database: {config.database.host}:{config.database.port}/{config.database.database}")
    print(f"Logging: {config.logging.level} -> {config.logging.file}")
```

```bash
# Production deployment with nested config
$ python app.py \
    -n "ProductionApp" \
    -w 16 \
    --db-host prod-db.example.com \
    --db-database prod_db \
    --db-username prod_user \
    --log-level WARNING \
    --log-file /var/log/app.log

# Or load base config and override specific fields
$ python app.py \
    --config production.yaml \
    --db-password "${DB_PASSWORD}" \
    --log-level DEBUG
```

**See also:**
- [`examples/nested_dataclass.py`](examples/nested_dataclass.py) - Complete nested dataclass example
- [`examples/nested_short_options.py`](examples/nested_short_options.py) - Short options with nested fields


### Field Resolution

Transform configuration dictionaries into typed objects using `cli_resolve()`. This enables a clean factory pattern where config files contain simple dicts, but your application works with rich typed objects.

```python
from dataclass_args import build_config, cli_resolve, cli_help, combine_annotations

# Your domain types
class SandboxBase:
    pass

class DockerSandbox(SandboxBase):
    def __init__(self, image: str = "python:3.11", memory: str = "512m"):
        self.image = image
        self.memory = memory

# Your resolver function (owns all instantiation logic)
def resolve_sandbox(value):
    if isinstance(value, dict):
        sandbox_type = value.get("type", "local")
        if sandbox_type == "docker":
            return DockerSandbox(image=value.get("image", "python:3.11"))
        # ... other types
    return value  # Pass-through for pre-built objects

# Your config dataclass
@dataclass
class AppConfig:
    app_name: str = "myapp"

    # Field type is the FINAL type (for type checking)
    # During parsing, treated as dict (supports file paths + property overrides)
    # After assembly, resolver transforms dict → typed object
    sandbox: Optional[SandboxBase] = combine_annotations(
        cli_resolve(resolver=resolve_sandbox),
        cli_help("Sandbox configuration"),
        default=None,
    )

config = build_config(AppConfig)
```

```bash
# Load sandbox from a config file
$ python app.py --sandbox sandbox.yaml

# Load and override a property before resolution
$ python app.py --sandbox sandbox.yaml --s image:python:3.12

# Or specify in a full config file
$ python app.py --config app.yaml
```

**sandbox.yaml:**
```yaml
type: docker
image: python:3.11
memory: 1g
```

#### How It Works

1. **Parsing**: Field is treated as a dict field (supports file path loading + property overrides)
2. **Assembly**: All config sources merge normally (base_configs → config file → CLI)
3. **Resolution** (pipeline stage 8): Resolver function called on non-None values
4. **Result**: Dict is transformed into the typed object for the dataclass

#### List Fields

`cli_resolve` also works on list fields. The field retains its natural list parsing behavior,
and the resolver receives the entire assembled list:

```python
def resolve_plugin_paths(patterns):
    """Expand glob patterns and load plugin configs."""
    import glob
    files = [f for p in patterns for f in glob.glob(p)]
    return [load_and_create_plugin(f) for f in files]

@dataclass
class AppConfig:
    plugins: List[Any] = combine_annotations(
        cli_resolve(resolver=resolve_plugin_paths),
        cli_help("Plugin config file patterns"),
        default_factory=list,
    )
```

```bash
$ python app.py --plugins "plugins/*.json" "extra/*.yaml"
# resolver receives: ["plugins/*.json", "extra/*.yaml"]
```

#### Behavior Rules

| Value State | What Happens |
|-------------|--------------|
| `None` | Resolver NOT called, field stays `None` |
| Dict (from config/file) | Resolver called, result assigned to field |
| A string that isn't a path to an existing file (from the CLI or a config source) | Resolver called with the string |
| Pre-built object (programmatic) | Resolver called, can pass through unchanged |
| Property overrides on non-dict | `ConfigurationError` raised |

#### Compatibility

- **Works with**: `cli_help`, `cli_short`, `cli_choices`, `cli_list_merge` (list rules run on the raw values, before the resolver), `cli_extend` (list fields), `combine_annotations`
- **Incompatible with** (on same field): `cli_positional`, `cli_nested`, `cli_append`, `cli_exclude`, `cli_file_loadable`
- **Nested fields**: Allowed in nested dataclasses, but resolver is NOT called (value stays raw)

#### Error Handling

Resolver exceptions are wrapped in `ConfigurationError` with field context:
```
ConfigurationError: Failed to resolve field 'sandbox': Unknown sandbox type: invalid
```

If the resolver itself raises `ConfigurationError`, it's re-raised without wrapping.

**See also:**
- [`examples/cli_resolve_example.py`](examples/cli_resolve_example.py) - Complete working example

### Config Files, Dict Files and Property Overrides Together

A `--config` file, a dict-field file and individual property overrides compose in precedence order:

```yaml
# config.yaml
name: "DefaultApp"
count: 100
database:
  host: "localhost"
  port: 5432
  timeout: 30
```

```python
@dataclass
class AppConfig:
    name: str
    count: int = 10
    database: Dict[str, Any] = None

config = build_config_from_cli(AppConfig, [
    '--config', 'config.yaml',  # Load base configuration
    '--name', 'OverriddenApp',  # Override name
    '--database', 'db.json',    # Load additional database config
    '--d', 'timeout:60'         # Override database.timeout property
])
# db.json = {"pool": 5}  →
# AppConfig(name='OverriddenApp', count=100,
#           database={'host': 'localhost', 'port': 5432, 'timeout': 60, 'pool': 5})
```

### Object Instantiation

Construct Python objects from configuration values using convention-based dispatch with `instantiate()`. Supports direct class import via `_target_`, registry-based lookup, recursive resolution, and post-construction attribute traversal.

```python
from dataclass_args import instantiate

# Direct class import
config = {
    "_target_": "myapp.sandboxes.DockerSandbox",
    "image": "python:3.11",
    "memory": "512m",
}
sandbox = instantiate(config)

# Registry-based lookup
registry = {
    "docker": "myapp.sandboxes.DockerSandbox",
    "local": "myapp.sandboxes.LocalSandbox",
}
sandbox = instantiate("docker", registry=registry)

# Dict with type key + registry
config = {"type": "docker", "image": "python:3.11"}
sandbox = instantiate(config, registry=registry)

# Recursive resolution (nested objects)
config = {
    "_target_": "myapp.Server",
    "name": "prod",
    "database": {
        "_target_": "myapp.Database",
        "host": "db.example.com",
    },
}
server = instantiate(config)
# server.database is automatically instantiated as a Database object
```

Nested dicts (and list elements) are instantiated only when they carry a dispatch key (`_target_`, or `type` with a registry). A plain nested dict is passed to the constructor as a dict, whatever the parameter's type annotation. Annotations are used for one thing: a string argument whose parameter is annotated with a class is looked up in the registry.

**Dispatch Rules:**
1. `None` → returns `None`
2. Non-dict/non-string → pass-through (pre-built objects)
3. String + registry → lookup and construct with no args
4. Dict with `_target_` → import class, construct with remaining kwargs
5. Dict with `type` + registry → lookup, construct with remaining kwargs
6. Plain dict (no special keys) → return as-is

**See also:** [Full API documentation](docs/API.md#object-instantiation)

### Custom Help and Annotations

```python
from dataclass_args import cli_help, cli_exclude, cli_file_loadable, combine_annotations

@dataclass
class ServerConfig:
    # Custom help text
    host: str = cli_help("Server bind address", default="127.0.0.1")
    port: int = cli_help("Server port number", default=8000)

    # File-loadable with help
    ssl_cert: str = combine_annotations(
        cli_file_loadable(), cli_help("SSL certificate content"), default=""
    )

    # Hidden from CLI
    secret_key: str = cli_exclude(default="auto-generated")

    # Multiple values
    allowed_hosts: List[str] = cli_help("Allowed host headers", default_factory=list)
```

### Complex Types and Validation

```python
from typing import List, Dict, Optional
from pathlib import Path

@dataclass
class MLConfig:
    # Basic types
    model_name: str = cli_help("Model identifier", default="baseline")
    learning_rate: float = cli_help("Learning rate", default=0.001)
    epochs: int = cli_help("Training epochs", default=100)

    # Complex types
    layer_sizes: List[int] = cli_help("Neural network layer sizes", default_factory=lambda: [128, 64])
    hyperparameters: Dict[str, Any] = cli_help("Model hyperparameters", default_factory=dict)

    # Optional types
    checkpoint_path: Optional[Path] = cli_help("Path to model checkpoint", default=None)

    # File-loadable configurations
    training_config: str = combine_annotations(
        cli_file_loadable(), cli_help("Training configuration"), default=""
    )

    def __post_init__(self):
        # Custom validation
        if self.learning_rate <= 0:
            raise ValueError("Learning rate must be positive")
        if self.epochs <= 0:
            raise ValueError("Epochs must be positive")
```


### Configuration Merging

Dataclass-args supports hierarchical configuration merging from multiple sources with clear precedence rules.

#### Merge Order (Highest Priority Last)

Configuration sources are merged in this order, with later sources overriding earlier ones:

1. **Programmatic `base_configs`** (if provided) - Lowest priority
2. **Config file** from `--config` CLI argument (if provided)
3. **CLI arguments** - Highest priority

#### Basic Usage

Load a base configuration file and override with CLI arguments:

```python
from dataclasses import dataclass
from dataclass_args import build_config

@dataclass
class AppConfig:
    name: str
    count: int = 10
    region: str = "us-east-1"

# Load from file, override with CLI
config = build_config(
    AppConfig,
    args=['--config', 'prod.yaml', '--count', '100']
)
```

**prod.yaml:**
```yaml
name: "ProductionApp"
count: 50
region: "eu-west-1"
```

**Result:**
- `name`: "ProductionApp" (from file)
- `count`: 100 (CLI override)
- `region`: "eu-west-1" (from file)

#### Programmatic Base Configs

For advanced use cases, provide base configuration programmatically using the `base_configs` parameter:

```python
# Single file path
config = build_config(AppConfig, base_configs='defaults.yaml')

# Single configuration dict
config = build_config(AppConfig, base_configs={'name': 'app', 'count': 50})

# List mixing files and dicts (applied in order)
config = build_config(
    AppConfig,
    args=['--config', 'user.yaml', '--name', 'override'],
    base_configs=[
        'company-defaults.yaml',      # Company-wide defaults
        {'region': 'eu-west-1'},      # Programmatic override
        'team-overrides.json',        # Team-specific settings
    ]
)
```

**Merge order for the list example:**
1. `company-defaults.yaml` (loaded and applied first)
2. `{'region': 'eu-west-1'}` (overrides company defaults)
3. `team-overrides.json` (loaded and overrides previous)
4. `user.yaml` (from `--config`, overrides all base_configs)
5. `--name 'override'` (CLI arg, highest priority)

#### Merge Behavior by Type

| Type | Behavior | Example |
|------|----------|---------|
| **Scalar** (str, int, float) | Replace | Later value replaces earlier value |
| **List** | Replace | Later list replaces earlier list (not appended) |
| **Dict** | One-level merge | Top-level keys are merged; later sources override earlier keys. Nested dicts inside a key are replaced, not merged |

**Dict merge example:**
```python
# base_configs[0]
{'name': 'app', 'db': {'host': 'localhost', 'port': 5432}}

# base_configs[1]
{'db': {'port': 3306, 'timeout': 30}}

# Result after merging:
{'name': 'app', 'db': {'host': 'localhost', 'port': 3306, 'timeout': 30}}
#  ^unchanged    ^merged: host kept, port updated, timeout added
```

**Nested dict replaced example:**
```python
# base_configs[0]: {'db': {'host': 'h', 'opts': {'x': 1}}}
# base_configs[1]: {'db': {'opts': {'y': 2}}}
# Result:          {'db': {'host': 'h', 'opts': {'y': 2}}}   # host kept, opts replaced
```

#### Deep Merge

By default, dicts from different sources are merged **one level** deep: a nested dict inside a key is replaced, not merged. Pass `merge_strategy="deep"` to merge dicts recursively at every depth, at every point where two sources meet (`base_configs`, `--config`, `--field file.json`, and nested dataclass values):

```python
from dataclass_args import build_config, MERGE_DEEP

@dataclass
class AppConfig:
    db: Dict[str, Any] = field(default_factory=dict)

layers = [
    {'db': {'host': 'localhost', 'pool': {'min': 1, 'max': 10}}},
    {'db': {'pool': {'max': 50}}},
]

build_config(AppConfig, [], base_configs=layers).db
# {'host': 'localhost', 'pool': {'max': 50}}             # default: pool replaced

build_config(AppConfig, [], base_configs=layers, merge_strategy=MERGE_DEEP).db
# {'host': 'localhost', 'pool': {'min': 1, 'max': 50}}   # deep: pool merged
```

Both modes follow the same rules:
- Lists **replace** (but see [list-merge rules](#layered-configuration)).
- An explicit `None` **clears** a value.
- Precedence is unchanged.
- The objects you pass in are never mutated.

The same semantics are available as a utility function: `deep_merge(base, override)` returns a new dict and leaves both inputs untouched.

`merge_strategy` is accepted by `build_config`, `build_config_from_cli`, `build_config_from_dict` and `GenericConfigBuilder.build_config`. See [`examples/deep_merge_example.py`](examples/deep_merge_example.py).

#### Layered Configuration

Tools that combine platform defaults, a user's own config and mandatory platform overrides need three things beyond deep merge. This is similar to systemd drop-in directories, or to Docker Compose's per-field merge rules:
- **Named layers**, so you can tell where a value came from.
- A way for an override layer to **add to a list** instead of replacing it.
- A record of **which layer set what**.

All three need `merge_strategy="deep"`.

**Named layers.** `ConfigLayer` is accepted anywhere `base_configs` accepts a path or a dict:

```python
from dataclass_args import ConfigLayer

base_configs = [
    ConfigLayer("defaults.d/10-platform.yaml", name="platform"),
    ConfigLayer(agent_dict, name="agent.yaml"),
    ConfigLayer(overrides_dict, name="overrides", list_merge="rules"),
]
```

**List-merge rules.** In a layer with `list_merge="rules"`, the list fields and dict paths annotated with `cli_list_merge()` **append** instead of replacing. Lists you haven't annotated still replace, and CLI arguments always replace.

```python
from dataclass_args import cli_list_merge, combine_annotations

@dataclass
class AgentConfig:
    plugins: List[str] = combine_annotations(
        cli_list_merge("append_unique"), default_factory=list)
    skills: Dict[str, Any] = combine_annotations(
        cli_list_merge("append_unique", paths=["roots", "policy.denied"]),
        default_factory=dict)

layers = [
    {"plugins": ["dev"],
     "skills": {"roots": ["./sk"], "policy": {"denied": ["old"], "execution": "allow"}}},
    ConfigLayer({"plugins": ["guard"],
                 "skills": {"policy": {"denied": ["exfil"], "execution": "deny"}}},
                list_merge="rules"),
]
cfg = build_config(AgentConfig, [], base_configs=layers, merge_strategy="deep")
cfg.plugins  # ['dev', 'guard']
cfg.skills   # {'roots': ['./sk'], 'policy': {'denied': ['old', 'exfil'], 'execution': 'deny'}}
```

The two modes:
- `"append"`: concatenates the lists.
- `"append_unique"`: adds only the elements not already present, compared with `==` (so dicts work too). Existing order is kept.

Rules apply only where **both** sides are lists. Otherwise the later value wins as usual, so `None` still clears. Annotate list or dict fields inside nested dataclasses to apply rules at any depth. With `build_config_from_dict(..., merge_strategy="deep", config_list_merge="rules")`, the `config` dict itself is a rules layer.

**Provenance.** Pass `return_provenance=True` to get `(instance, Provenance)`:

```python
cfg, prov = build_config_from_dict(
    AgentConfig, {}, base_configs=[
        ConfigLayer({"skills": {"policy": {"execution": "deny"}}}, name="platform"),
        ConfigLayer({"skills": {"policy": {"execution": "allow"}}}, name="agent"),
    ],
    merge_strategy="deep", return_provenance=True)

prov.source("skills.policy.execution")   # 'agent'
prov.changes()   # [ProvenanceChange(path='skills.policy.execution', from_layer='platform',
                 #   from_value='deny', to_layer='agent', to_value='allow', action='replaced')]
print(prov.explain())                    # path | source | value  table
```

| Method | Returns |
|---|---|
| `entries(path)` | Every layer that touched `path`, in order (`set`, `replaced`, `confirmed`, `cleared`, `appended`, `removed`) |
| `source(path)` | The layer that set the final value; `"default"` for an unset dataclass field; `None` for unknown paths |
| `paths()` | All layer-set leaf paths (dotted, sorted) |
| `changes()` | Every place where a later layer **discarded** an earlier value. Appends and identical re-sets aren't changes. |
| `explain()` | A plain-text table of every path, its source and its value |

Some details:
- Paths are dotted, and lists are leaves.
- Provenance records **raw** layer values: after files are loaded, but before `@file` and `cli_resolve` resolution. The instance holds the resolved values.
- The layer names are:
  - the `ConfigLayer` name;
  - otherwise the file path, or `base_configs[i]` for a dict;
  - `config_file:<path>` for `--config`;
  - `config` for the `build_config_from_dict` dict;
  - `cli` for the command line.

See [`examples/layered_config_example.py`](examples/layered_config_example.py).

#### Real-World Example

```python
import os
from dataclasses import dataclass
from dataclass_args import build_config

@dataclass
class DeployConfig:
    app_name: str
    environment: str
    region: str = "us-east-1"
    instance_count: int = 1

# Determine environment
env = os.getenv('ENV', 'dev')

# Multi-layer configuration
config = build_config(
    DeployConfig,
    args=['--config', '~/.myapp/personal.yaml', '--region', 'us-west-2'],
    base_configs=[
        'config/base.yaml',           # Company-wide defaults
        f'config/{env}.yaml',         # Environment-specific (dev/staging/prod)
        {'instance_count': 2},        # Quick programmatic toggle
    ]
)

# Configuration is built from all sources with clear precedence
print(f"Deploying {config.app_name} to {config.environment}")
```

**Use Cases:**

1. **Multi-environment deployments:**
   ```python
   config = build_config(
       Config,
       args=['--config', f'{env}.yaml'],
       base_configs='base.yaml'
   )
   ```

2. **Testing with fixtures:**
   ```python
   test_config = {'region': 'test-region', 'count': 1}
   config = build_config(
       AppConfig,
       args=['--name', 'test-run'],
       base_configs=test_config
   )
   ```

3. **Team and personal settings:**
   ```python
   config = build_config(
       Config,
       base_configs=[
           'company.yaml',      # Company defaults
           'team.yaml',         # Team overrides
           '~/.myapp/personal.yaml',  # Personal settings (~ is expanded)
       ]
   )
   ```

Every config file (in `base_configs`, `--config`, or given for a dict field) must hold a mapping at its top level; a list or a bare value raises `ConfigurationError`. A leading `~` in the path is expanded to the home directory. Relative paths, including `@file` references inside a config file, are resolved against the current working directory, not the config file's directory.

#### Complete Example

See [`examples/config_merging_example.py`](examples/config_merging_example.py) for a comprehensive demonstration of configuration merging with multiple sources.

```bash
# Run the example
python examples/config_merging_example.py multi-source
```

#### See Also

- [Configuration File Formats](#configuration-file-formats) - Supported formats
- [Type Support](#type-support) - Type-specific behavior
- [API Reference](#api-reference) - Full API documentation


### Dict Field Property Overrides

Dict fields (`Dict[str, Any]`) automatically get a short override argument for setting individual properties via the CLI. The override name is auto-generated from field name initials (e.g., `model_config` → `--mc`), or set explicitly with `cli_override_name()`.

```python
from dataclasses import dataclass, field
from typing import Dict, Any
from dataclass_args import build_config, cli_override_name

@dataclass
class AppConfig:
    model_config: Dict[str, Any] = field(default_factory=dict)
    # Auto-generated override: --mc
```

#### Basic Property Overrides

Use `--abbreviation key:value` to set individual properties:

```bash
# Load dict from file, then override specific properties
$ python app.py --model-config model.yaml --mc temperature:0.9 --mc max_tokens:4096

# Set nested properties with dot notation
$ python app.py --model-config model.yaml --mc provider.settings.timeout:30

# Values are auto-parsed (JSON types)
$ python app.py --mc count:42 --mc enabled:true --mc name:my-model
# Result: {"count": 42, "enabled": true, "name": "my-model"}
```

#### List Element Overrides

When a property value is a list, use numeric indices to modify individual elements, or `+` to append:

```bash
# Given model.yaml contains: {"tags": ["python", "ml", "v1"], "endpoints": [{"url": "http://old"}]}

# Replace a list element by index
$ python app.py --model-config model.yaml --mc tags.0:updated-python
# Result: tags = ["updated-python", "ml", "v1"]

# Append to a list
$ python app.py --model-config model.yaml --mc tags.+:new-tag
# Result: tags = ["python", "ml", "v1", "new-tag"]

# Modify a property inside a list element
$ python app.py --model-config model.yaml --mc endpoints.0.url:http://new
# Result: endpoints = [{"url": "http://new"}]

# Multiple list operations
$ python app.py --model-config model.yaml --mc tags.0:first --mc tags.+:last
```

**Index rules:**
- `items.0` — set element at index 0 (the list must already exist and the index must be in range, otherwise `ConfigurationError`)
- `items.+` — append new element to list (the list must already exist)
- `items.0.name` — navigate into list element 0, then set `name` property
- Negative indices are not supported
- If the container is a dict (not a list), `0` and `+` are ordinary string keys: `{"0": "value"}`. So if `items` doesn't exist yet, `items.0:x` creates `{"items": {"0": "x"}}`; set the list first if you want list behaviour

**Key syntax:**
- The argument is split at the **first** `:`, so values may contain colons (`--mc url:http://host:8080/p`).
- Key segments are separated by dots. Each segment must be non-empty and contain no whitespace, quotes, braces or brackets. Hyphens, slashes and other characters are fine (`max-tokens`, `provider/model`).
- Anything else raises `ConfigurationError` naming the field and option, for example:
  - a JSON object (`--mc '{"temperature": 0.1}'`);
  - a quoted key;
  - `items[0]` (use `items.0`);
  - an `@file` value.
- An override sets **one property**. To set the whole dict, pass a file to the field's own option (`--model-config model.yaml`).

#### Override Name Collisions

When two dict fields share the same auto-generated abbreviation, use `cli_override_name()`:

```python
@dataclass
class Config:
    sandbox_config: Dict[str, Any] = field(default_factory=dict)              # → --sc (auto)
    skills_config: Dict[str, Any] = cli_override_name("sk", default_factory=dict)  # → --sk
```

Without the annotation, both fields would generate `--sc`, causing a `ConfigBuilderError` at init time with a message suggesting the fix.

A string given for a dict field (on the command line, or as a value in `base_configs`, `--config` or `build_config_from_dict`) is handled the same way everywhere:
- the path of an **existing file**, of any extension, is loaded like a `--config` file (format detected from the content);
- a missing `.json`/`.yaml`/`.yml`/`.toml` path is a "file not found" error;
- any other string raises `ConfigurationError`.

Fields annotated with `cli_resolve()` receive any other string unchanged.

### Programmatic Usage

For non-CLI contexts use `build_config_from_dict()` to build a dataclass instance directly from a dictionary:

```python
from dataclass_args import build_config_from_dict

# Configuration from any source (API payload, DynamoDB, merged dicts, etc.)
config_dict = {
    "app_name": "production-api",
    "port": 8080,
    "system_prompt": "@/path/to/prompt.txt",  # @file references resolved!
    "database": {
        "host": "rds-prod.amazonaws.com",
        "port": 5432,
    },
}

# One-liner: dict in, typed dataclass out
config = build_config_from_dict(AppConfig, config_dict)

# With layered base configs (same as build_config_from_cli)
config = build_config_from_dict(
    AppConfig,
    {"port": 9000},                          # Highest priority
    base_configs=[
        "company-defaults.yaml",             # Lowest priority
        {"app_name": "staging-api"},         # Middle priority
    ],
)
```

**Key behaviors:**
- `@file` references resolved for `cli_file_loadable` fields (loads file content)
- Dict-file paths (`.json`/`.yaml`/`.yml`/`.toml`) loaded for dict-typed fields, including inside nested dataclasses
- `cli_resolve()` resolvers fire on assembled values
- Nested dataclasses (`cli_nested`, any depth) reconstruct from nested dicts or instances
- `base_configs` support with same precedence rules as CLI mode (including `ConfigLayer`, `merge_strategy` and provenance)
- Fields with defaults work when omitted from the dict; an explicit `None` clears a value
- Every positional field can be set (there is no command line to require it)
- Hyphenated field names (`"db-host"`) are accepted
- `cli_exclude()` fields are settable (no CLI to exclude from)
- Never exits the process: errors are raised as `ConfigurationError` / `ConfigBuilderError`
- Only accepts `Dict[str, Any]` — raises `TypeError` for non-dict inputs

**What does NOT apply via dict:**
- `cli_choices()` validation. Choices are enforced by argparse, so they apply only to command-line values; values from a dict, `base_configs` or `--config` aren't checked against them

**See also:** [`examples/programmatic_example.py`](examples/programmatic_example.py) for complete working examples.



## API Reference

> **📖 Full API Documentation:** See [docs/API.md](docs/API.md) for complete API reference with detailed examples.

### Quick API Reference

### Main Functions

#### `build_config(config_class, args=None, base_configs=None, description=None, merge_strategy="shallow", return_provenance=False)`

Generate CLI from dataclass and parse arguments.

```python
config = build_config(MyDataclass)  # Uses sys.argv automatically
```

#### `build_config_from_cli(config_class, args=None, **options)`

Generate CLI with additional options.

```python
config = build_config_from_cli(
    MyDataclass,
    args=['--name', 'test'],
    base_configs=['defaults.yaml', {'debug': True}],
    base_config_name='config',      # name of the --config option
    merge_strategy='deep',          # optional: recursive dict merge
)
```

#### `build_config_from_dict(config_class, config, base_configs=None, config_list_merge="replace", merge_strategy="shallow", return_provenance=False)`

Build a dataclass instance from a dictionary with full resolution pipeline. Recommended for Lambda handlers, SDKs, and test harnesses.

```python
from dataclass_args import build_config_from_dict

# Simple usage
config = build_config_from_dict(MyDataclass, {"name": "test", "port": 8080})

# With base configs
config = build_config_from_dict(MyDataclass, {"port": 9000}, base_configs="defaults.yaml")
```

### Annotations

#### `cli_short(letter, **kwargs)`

Add a short option flag to a field.

```python
field: str = cli_short('f', default="value")

# Or combine with other annotations
field: str = combine_annotations(
    cli_short('f'),
    cli_help("Help text"),
    default="value"
)
```

#### `cli_choices(choices_list, **kwargs)`

Restrict field to a set of valid choices.

```python
env: str = cli_choices(['dev', 'prod'], default='dev')

# Or combine
env: str = combine_annotations(
    cli_short('e'),
    cli_choices(['dev', 'prod']),
    cli_help("Environment"),
    default='dev'
)
```

#### `cli_help(help_text, **kwargs)`

Add custom help text to CLI arguments.

```python
field: str = cli_help("Custom help text", default="default_value")
```



#### `cli_positional(nargs=None, metavar=None, **kwargs)`

Mark a field as a positional CLI argument (no `--` prefix required).

```python
# Required positional
source: str = cli_positional(help="Source file")

# Optional positional
output: str = cli_positional(nargs='?', default='stdout')

# Variable number (list)
files: List[str] = cli_positional(nargs='+', help="Files")

# Exact count
coords: List[float] = cli_positional(nargs=2, metavar='COORD')  # usage: COORD COORD

# Combined with other annotations
input: str = combine_annotations(
    cli_positional(),
    cli_help("Input file path")
)
```

**Important:** At most one positional can use `nargs='*'` or `'+'`, and it must be the last positional.

#### `cli_nested(prefix=None, **kwargs)`

Mark a dataclass field as a nested configuration that should be flattened into CLI arguments.

```python
# Custom prefix
database: DatabaseConfig = cli_nested(prefix="db", default_factory=DatabaseConfig)
# CLI: --db-host, --db-port

# No prefix (complete flattening)
credentials: Credentials = cli_nested(prefix="", default_factory=Credentials)
# CLI: --username, --password

# Auto prefix (uses field name)
logging: LogConfig = cli_nested(default_factory=LogConfig)
# CLI: --logging-level, --logging-file
```

**Important:**
- Fields with prefixes don't support short options (booleans included)
- Fields without prefix (prefix="") support short options
- Underscores in a prefix are kept in positive options (`my_db` → `--my_db-host`); hyphenation is planned ([FUTURE_CHANGES.md](FUTURE_CHANGES.md))
- Automatic collision detection for field names and short options
- Works seamlessly with config file merging

#### `cli_resolve(resolver, **kwargs)`

Mark a field for post-load resolution via a callable. After the raw value is assembled
from all configuration sources, the resolver transforms it into the final field value.
For non-list fields, treated as dict-loadable during parsing (file paths + property overrides).
For list fields, retains natural list parsing behavior (resolver receives assembled list).

```python
def resolve_sandbox(value):
    if isinstance(value, dict):
        return create_sandbox(**value)
    return value  # Pass-through for pre-built objects

sandbox: Optional[SandboxBase] = combine_annotations(
    cli_resolve(resolver=resolve_sandbox),
    cli_help("Sandbox configuration"),
    default=None,
)
```

**Important:**
- Resolver is NOT called when value is None
- Compatible with: `cli_help`, `cli_short`, `cli_choices`, `cli_list_merge`, `cli_extend` (list fields), `combine_annotations`
- Incompatible with: `cli_positional`, `cli_nested`, `cli_append`, `cli_exclude`, `cli_file_loadable`
- In nested dataclasses: allowed but resolver NOT called (value stays raw)

#### `cli_override_name(name, **kwargs)`

Specify a custom override abbreviation for dict field property overrides.
Dict fields auto-generate a short override argument from field name initials
(e.g., `model_config` → `--mc`). Use this to resolve collisions.

```python
# Without annotation: sandbox_config → --sc, skills_config → --sc (collision!)
# With annotation:
sandbox_config: Dict[str, Any] = field(default_factory=dict)              # → --sc (auto)
skills_config: Dict[str, Any] = cli_override_name("sk", default_factory=dict)  # → --sk
```

#### `cli_exclude(**kwargs)`

Exclude fields from CLI argument generation.

```python
internal_field: str = cli_exclude(default="hidden")
```

#### `cli_file_loadable(**kwargs)`

Mark string fields as file-loadable via '@filename' syntax.

```python
content: str = cli_file_loadable(default="default content")
```

#### `combine_annotations(*annotations, **kwargs)`

Combine multiple annotations on a single field.

```python
field: str = combine_annotations(
    cli_short('f'),
    cli_choices(['a', 'b', 'c']),
    cli_help("Description"),
    default='a'
)
```

## Type Support

Dataclass CLI supports standard Python types:

| Type | CLI Behavior | Example |
|------|--------------|---------|
| `str` | Direct string value | `--name "hello"` |
| `int` | Parsed as integer | `--count 42` |
| `float` | Parsed as float | `--rate 0.1` |
| `bool` | Flag with negative | `--debug` or `--no-debug` |
| `List[T]` / `list[T]` / `list` | Multiple values after one flag; elements converted to `T` for `int`/`float`/`str` (strings for a bare `list`; a repeated flag keeps the last occurrence unless `cli_extend()`) | `--items a b c` |
| `Dict[str, Any]` / `dict` | A dict, or the path of an existing structured file (format detected from the content), plus property overrides; any other string is an error | `--model-config m.json --mc temperature:0.9 --mc tags.0:new` |
| `Optional[T]` | Same as `T`; the option may be omitted | `--timeout 30` (or omit) |
| `Union[A, B]` | The value as typed, as a **string** (also for `Optional[Union[A, B]]` and `A \| B \| None`) | `--port-or-name 8080` |
| `Path` | The path as typed, as a **string** (not converted to `Path`) | `--output /path/to/file` |
| Custom types | String representation | `--custom "value"` |

Values from config files and `base_configs` are used as loaded (YAML/JSON/TOML types); they are not converted to the field type. Fields declared with `field(init=False)` can't be passed to the constructor, so they get no CLI option and can't be set from config sources.

Help text (from `cli_help()` or generated) is shown literally: a `%` needs no escaping.

## Configuration File Formats

Supports multiple configuration file formats:

### JSON
```json
{
  "name": "MyApp",
  "count": 42,
  "database": {
    "host": "localhost",
    "port": 5432
  }
}
```

### YAML (requires `pip install "dataclass-args[yaml]"`)
```yaml
name: MyApp
count: 42
database:
  host: localhost
  port: 5432
```

### TOML (built in, via the standard library's `tomllib`)
```toml
name = "MyApp"
count = 42

[database]
host = "localhost"
port = 5432
```

## Examples

Check the [`examples/`](examples/) directory for complete working examples:

- **`basic_example.py`** / **`advanced_example.py`** - Getting started; file loading and config files
- **`positional_example.py`** - Positional arguments and variable length args
- **`boolean_flags_example.py`** - Boolean flags with `--flag` and `--no-flag`
- **`cli_choices_example.py`** - Value validation with choices
- **`cli_short_example.py`** - Short option flags
- **`cli_append_example.py`** - Repeatable options (`cli_append`)
- **`nested_dataclass.py`** / **`nested_short_options.py`** - Nested dataclasses and their short options
- **`config_merging_example.py`** - `base_configs` and `--config` precedence
- **`deep_merge_example.py`** - Shallow vs deep merge
- **`layered_config_example.py`** - Named layers, list-merge rules and provenance
- **`cli_resolve_example.py`** - Post-load field resolution with factory pattern
- **`programmatic_example.py`** - `build_config_from_dict()` without a CLI
- **`custom_description_example.py`** - Custom parser descriptions
- **`all_features_example.py`** - All features together
- And more...

### Web Server Configuration

```python
import os
from dataclasses import dataclass
from typing import List
from dataclass_args import build_config, cli_short, cli_help, cli_exclude, cli_file_loadable, combine_annotations

@dataclass
class ServerConfig:
    # Basic server settings
    host: str = combine_annotations(
        cli_short('H'),
        cli_help("Server bind address"),
        default="127.0.0.1"
    )

    port: int = combine_annotations(
        cli_short('p'),
        cli_help("Server port number"),
        default=8000
    )

    workers: int = combine_annotations(
        cli_short('w'),
        cli_help("Number of worker processes"),
        default=1
    )

    # Security settings
    ssl_cert: str = combine_annotations(
        cli_file_loadable(), cli_help("SSL certificate content"), default=""
    )
    ssl_key: str = combine_annotations(
        cli_file_loadable(), cli_help("SSL private key content"), default=""
    )

    # Application settings
    debug: bool = combine_annotations(
        cli_short('d'),
        cli_help("Enable debug mode"),
        default=False
    )

    allowed_hosts: List[str] = cli_help("Allowed host headers", default_factory=list)

    # Internal fields (hidden from CLI)
    _server_id: str = cli_exclude(default_factory=lambda: f"server-{os.getpid()}")

if __name__ == "__main__":
    config = build_config(ServerConfig)
    print(f"Starting server on {config.host}:{config.port}")
```

```bash
# Start server with short options
$ python server.py -H 0.0.0.0 -p 9000 -w 4 -d

# Load SSL certificates from files
$ python server.py --ssl-cert "@certs/server.crt" --ssl-key "@certs/server.key"
```

## Contributing

Contributions are welcome! Please see our [Contributing Guide](CONTRIBUTING.md) for details.

### Development Setup

The project is managed with [uv](https://docs.astral.sh/uv/). Development dependencies live in the `dev` dependency group, and exact versions are pinned in the committed `uv.lock`.

```bash
git clone https://github.com/bassmanitram/dataclass-args.git
cd dataclass-args
make setup   # uv sync --all-extras + install pre-commit hooks
```

### Running Tests

```bash
# Run all tests (coverage is automatic)
uv run pytest
make test

# Run tests with detailed coverage report
make coverage

# Run tests with coverage and open HTML report
make coverage-html

# Run a specific test file
uv run pytest tests/test_cli_short.py

# Run against another Python version, in a throwaway environment
# (without --isolated, uv would rebuild .venv for that version)
uv run --isolated --all-extras --python 3.13 pytest
```

### Code Coverage

This project maintains **97%+ code coverage** (branch coverage). Coverage reports are generated automatically when running tests.

- **Quick check**: `make coverage`
- **Detailed report**: See `htmlcov/index.html`
- **Coverage docs**: [COVERAGE.md](docs/COVERAGE.md)

All code changes should maintain or improve coverage. CI fails below 88%.

### Code Formatting

```bash
# Format code
make format          # uv run black + uv run isort

# Check formatting, lint and types
make lint            # black --check, isort --check-only, mypy, flake8 (all via uv run)
```

The pre-commit hooks run the same locked tool versions, through `uv run`, so local checks, pre-commit and CI always agree.

### Full Check (like CI)

```bash
# Run all checks: linting, tests, and examples
make check
```

## Changelog

See [CHANGELOG.md](CHANGELOG.md) for version history and changes.

## Support

- **Issues**: [GitHub Issues](https://github.com/bassmanitram/dataclass-args/issues)
- **Documentation**: This README and comprehensive docstrings
- **Examples**: See the [examples/](examples/) directory

## Quick Reference

```python
from dataclasses import dataclass
from dataclass_args import (
    build_config,                # Main function
    build_config_from_dict,      # Programmatic (no CLI) config building
    instantiate,                 # Object instantiation from config
    cli_short,                   # Short options: -n
    cli_positional,              # Positional args
    cli_choices,                 # Value validation
    cli_help,                    # Custom help text
    cli_nested,                  # Nested dataclasses
    cli_exclude,                 # Hide from CLI
    cli_file_loadable,           # @file loading
    cli_override_name,           # Custom dict override abbreviation
    cli_resolve,                 # Post-load resolution
    cli_list_merge,              # Append-in-rules-layers list fields
    cli_extend,                  # Repeatable list flags that accumulate
    combine_annotations,         # Combine features
    ConfigLayer,                 # Named config layer (replace | rules)
    deep_merge,                  # Recursive dict merge utility
    InstantiationError,          # Instantiation failures
)

@dataclass
class Config:
    # Simple field
    name: str

    # Positional argument
    input_file: str = cli_positional()

    # With short option
    port: int = cli_short('p', default=8000)

    # With choices
    env: str = cli_choices(['dev', 'prod'], default='dev')

    # Boolean flag
    debug: bool = False  # Creates --debug and --no-debug

    # Combine everything
    region: str = combine_annotations(
        cli_short('r'),
        cli_choices(['us-east-1', 'us-west-2']),
        cli_help("AWS region"),
        default='us-east-1'
    )

    # Hidden from CLI
    secret: str = cli_exclude(default="hidden")

    # File-loadable
    config_text: str = cli_file_loadable(default="")

    # Nested dataclass
    database: DatabaseConfig = cli_nested(prefix="db", default_factory=DatabaseConfig)


    # Resolved field (dict → typed object via resolver)
    sandbox: Optional[SandboxBase] = combine_annotations(
        cli_resolve(resolver=resolve_sandbox),
        default=None,
    )
# Build and use
config = build_config(Config)

# Instantiate objects from config
obj = instantiate({"_target_": "myapp.MyClass", "param": "value"})
obj = instantiate("my_type", registry={"my_type": "myapp.MyClass"})
```

Define your dataclass, add annotations as needed, and call `build_config()` for CLI or `build_config_from_dict()` for programmatic usage.
