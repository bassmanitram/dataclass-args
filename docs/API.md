# API Reference

Complete API documentation for dataclass-args.

## Table of Contents

- [Main Functions](#main-functions)
- [Annotation Functions](#annotation-functions)
- [Advanced Classes](#advanced-classes)
- [Type Support](#type-support)
- [Exception Classes](#exception-classes)
- [Utility Functions](#utility-functions)
- [Best Practices](#best-practices)
- [Migration Guide](#migration-guide)

---

## Main Functions

### `build_config(config_class, args=None)`

The primary function for generating CLI from a dataclass. Simplified convenience function suitable for most use cases.

**Parameters:**
- `config_class` (Type[dataclass]): The dataclass to convert to CLI
- `args` (Optional[List[str]]): Command-line arguments to parse. Defaults to `sys.argv[1:]`

**Returns:**
- Instance of `config_class` with values parsed from CLI arguments

**Raises:**
- `SystemExit`: If argument parsing fails or `--help` is requested
- `ConfigBuilderError`: If the dataclass configuration is invalid

**Example:**
```python
from dataclasses import dataclass
from dataclass_args import build_config

@dataclass
class Config:
    name: str
    port: int = 8000

# Parse from sys.argv
config = build_config(Config)

# Parse from custom args
config = build_config(Config, args=['--name', 'myapp', '--port', '9000'])
```

---

### `build_config_from_cli(config_class, args=None, **options)`

Advanced function with additional configuration options. Provides full control over CLI generation.

**Parameters:**
- `config_class` (Type[dataclass]): The dataclass to convert to CLI
- `args` (Optional[List[str]]): Command-line arguments to parse
- `**options`: Additional configuration options:
  - `base_config_name` (str): Name for base config file argument (default: `'config'`)
  - `prog` (str): Program name for help text
  - `description` (str): Program description for help text
  - `epilog` (str): Text to display after help

**Returns:**
- Instance of `config_class` with values parsed from arguments

**Example:**
```python
from dataclass_args import build_config_from_cli

config = build_config_from_cli(
    Config,
    args=['--name', 'test'],
    prog='myapp',
    description='My Application CLI',
)
```

---

## Annotation Functions

### `cli_short(letter, **kwargs)`

Add a short option flag (e.g., `-n`) to a field.

**Parameters:**
- `letter` (str): Single character for short option (e.g., `'n'` creates `-n`)
- `**kwargs`: Field parameters (e.g., `default`, `default_factory`)

**Returns:**
- `Field` with short option metadata

**Example:**
```python
from dataclasses import dataclass
from dataclass_args import cli_short

@dataclass
class Config:
    name: str = cli_short('n')
    port: int = cli_short('p', default=8000)
```

**CLI Usage:**
```bash
python app.py -n myapp -p 9000
python app.py --name myapp --port 9000  # Long form also works
```

---

### `cli_choices(choices, **kwargs)`

Restrict field values to a specific set of valid choices.

**Parameters:**
- `choices` (List[Any]): List of valid values
- `**kwargs`: Field parameters (e.g., `default`, `default_factory`)

**Returns:**
- `Field` with choices validation metadata

**Example:**
```python
from dataclass_args import cli_choices

@dataclass
class Config:
    environment: str = cli_choices(['dev', 'staging', 'prod'])
    size: str = cli_choices(['small', 'medium', 'large'], default='medium')
```

**CLI Usage:**
```bash
python app.py --environment prod --size large     # Valid
python app.py --environment invalid                # Error!
```

---

### `cli_help(help_text, **kwargs)`

Add custom help text for a field in the `--help` output.

**Parameters:**
- `help_text` (str): Help text to display
- `**kwargs`: Field parameters (e.g., `default`, `default_factory`)

**Returns:**
- `Field` with help text metadata

**Example:**
```python
from dataclass_args import cli_help

@dataclass
class Config:
    host: str = cli_help("Server bind address", default="localhost")
    port: int = cli_help("Server port number", default=8000)
```

**Help Output:**
```
options:
  --host HOST    Server bind address (default: localhost)
  --port PORT    Server port number (default: 8000)
```

---

### `cli_positional(nargs=None, metavar=None, **kwargs)`

Mark a field as a positional argument (no `--` prefix required).

**Parameters:**
- `nargs` (Optional[Union[int, str]]): Number of arguments to accept:
  - `None` (default): Exactly one value (required)
  - `'?'`: Zero or one value (optional)
  - `'*'`: Zero or more values (optional list)
  - `'+'`: One or more values (required list)
  - `int` (e.g., `2`): Exact count (required list)
- `metavar` (Optional[str]): Name to display in help text
- `**kwargs`: Field parameters including `help`, `default`, `default_factory`

**Returns:**
- `Field` with positional argument metadata

**Examples:**

```python
from typing import List
from dataclass_args import cli_positional, cli_short

# Required positional
@dataclass
class Copy:
    source: str = cli_positional(help="Source file")
    dest: str = cli_positional(help="Destination file")
    recursive: bool = cli_short('r', default=False)

# CLI: python cp.py source.txt dest.txt -r

# Optional positional
@dataclass
class Convert:
    input_file: str = cli_positional(help="Input file")
    output_file: str = cli_positional(nargs='?', default='stdout', help="Output file")

# CLI: python convert.py input.json
# CLI: python convert.py input.json output.yaml

# Variable number of arguments
@dataclass
class Process:
    command: str = cli_positional(help="Command to run")
    files: List[str] = cli_positional(nargs='+', help="Files to process")

# CLI: python process.py compile file1.py file2.py file3.py

# Exact count
@dataclass
class Point:
    coordinates: List[float] = cli_positional(nargs=2, metavar='X Y', help="Coordinates")

# CLI: python plot.py 3.5 7.2
```

**Important Constraints:**
- At most ONE positional field can use `nargs='*'` or `'+'`
- If a positional list exists, it MUST be the LAST positional argument
- Use optional arguments with flags for multiple lists

---

### `cli_exclude(**kwargs)`

Exclude a field from CLI argument generation (internal/derived fields).

**Parameters:**
- `**kwargs`: Field parameters (e.g., `default`, `default_factory`)

**Returns:**
- `Field` marked for CLI exclusion

**Example:**
```python
from dataclass_args import cli_exclude
import uuid

@dataclass
class Config:
    name: str = cli_help("Application name")

    # Hidden from CLI
    instance_id: str = cli_exclude(default_factory=lambda: str(uuid.uuid4()))
    _internal: str = cli_exclude(default="internal_value")
```

---

### `cli_include(**kwargs)`

Explicitly mark a dataclass field to be included in CLI arguments. Useful when using custom field filters.

**Parameters:**
- `**kwargs`: Field parameters (e.g., `default`, `default_factory`)

**Returns:**
- `Field` with CLI inclusion metadata

**Example:**
```python
from dataclass_args import cli_include

@dataclass
class Config:
    # Explicitly included even if filter would exclude it
    special_field: str = cli_include(default="value")
```

---

### `cli_file_loadable(**kwargs)`

Mark a string field as file-loadable using the `@filename` syntax.

When a CLI argument value starts with '@', the remaining part is treated as a file path and the file content is loaded.

**Parameters:**
- `**kwargs`: Field parameters (e.g., `default`, `default_factory`)

**Returns:**
- `Field` with file-loadable metadata

**Example:**
```python
from dataclass_args import cli_file_loadable

@dataclass
class Config:
    name: str
    prompt: str = cli_file_loadable(default="Default prompt")
    content: str = cli_file_loadable()
```

**CLI Usage:**
```bash
# Use literal value
python app.py --name myapp --prompt "Hello world"

# Load from file
python app.py --name myapp --prompt "@prompts/system.txt"

# File content is read and assigned to the field
```

---

### `combine_annotations(*annotations, **kwargs)`

Combine multiple annotation functions on a single field.

**Parameters:**
- `*annotations`: Variable number of annotation functions (e.g., `cli_short`, `cli_choices`, `cli_help`)
- `**kwargs`: Field parameters (e.g., `default`, `default_factory`)

**Returns:**
- `Field` with all combined annotations

**Example:**
```python
from dataclass_args import combine_annotations, cli_short, cli_choices, cli_help

@dataclass
class Config:
    # Combine short option + choices + help
    environment: str = combine_annotations(
        cli_short('e'),
        cli_choices(['dev', 'staging', 'prod']),
        cli_help("Deployment environment"),
        default='dev'
    )

    # Combine short + help + positional
    input_file: str = combine_annotations(
        cli_positional(),
        cli_help("Input file path")
    )

    # Combine short + help
    port: int = combine_annotations(
        cli_short('p'),
        cli_help("Port number"),
        default=8000
    )
```

**CLI Usage:**
```bash
python app.py input.txt -e prod -p 9000
python app.py input.txt --environment staging --port 8080
```

---

## Advanced Classes

### `GenericConfigBuilder`

Advanced class for building dataclass instances from CLI arguments with full control.

Supports:
- Optional base config file loading (JSON, YAML, TOML)
- Type-aware CLI argument parsing
- List parameter handling with multiple values
- Object parameter file loading with property overrides
- File-loadable string parameters via '@' prefix
- Hierarchical merging of configuration sources
- Field filtering via annotations or custom filters

**Constructor Parameters:**
- `config_class` (Type[dataclass]): Dataclass type to build configurations for

**Methods:**

#### `add_arguments(parser, base_config_name='config', base_config_help='...')`

Add all dataclass arguments to an ArgumentParser.

**Parameters:**
- `parser` (argparse.ArgumentParser): Parser to add arguments to
- `base_config_name` (str): Name for base config file argument
- `base_config_help` (str): Help text for base config argument

#### `build_config(args, base_config_name='config')`

Build dataclass instance from parsed CLI arguments.

**Parameters:**
- `args` (argparse.Namespace): Parsed arguments from ArgumentParser
- `base_config_name` (str): Name of base config file argument

**Returns:**
- Instance of the configured dataclass

**Example:**
```python
from dataclass_args.builder import GenericConfigBuilder
import argparse

@dataclass
class Config:
    name: str
    port: int = 8000

# Create builder
builder = GenericConfigBuilder(Config)

# Create parser and add arguments
parser = argparse.ArgumentParser()
builder.add_arguments(parser)

# Parse and build
args = parser.parse_args()
config = builder.build_config(args)
```

---

## Type Support

### Supported Types

| Python Type | CLI Behavior | Example Input | Parsed Value |
|-------------|--------------|---------------|--------------|
| `str` | Single string value | `--name "hello"` | `"hello"` |
| `int` | Parsed as integer | `--count 42` | `42` |
| `float` | Parsed as float | `--rate 3.14` | `3.14` |
| `bool` | Boolean flag | `--debug` or `--no-debug` | `True` or `False` |
| `List[str]` | Multiple string values | `--tags a b c` | `["a", "b", "c"]` |
| `List[int]` | Multiple integer values | `--ids 1 2 3` | `[1, 2, 3]` |
| `List[float]` | Multiple float values | `--values 1.5 2.5` | `[1.5, 2.5]` |
| `Dict[str, Any]` | JSON/config file or key:value | `--config file.json` or `--c k:v` | `{...}` |
| `Optional[T]` | Optional parameter | `--timeout 30` or omit | `30` or `None` |
| `Path` | File path | `--output /tmp/file` | `Path('/tmp/file')` |
| `Enum` | Enum member (by value) | `--status active` | `Status.ACTIVE` |

### Type Examples

```python
from typing import List, Dict, Optional, Any
from pathlib import Path
from enum import Enum

class Status(Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"

@dataclass
class Config:
    # Basic types
    name: str
    count: int = 10
    rate: float = 1.5
    debug: bool = False

    # Collections
    tags: List[str] = None
    ports: List[int] = None
    settings: Dict[str, Any] = None

    # Optional
    timeout: Optional[int] = None

    # Path
    output: Path = Path("/tmp/output")

    # Enum
    status: Status = Status.ACTIVE
```

**CLI Usage:**
```bash
python app.py --name test --count 5 --rate 2.5 --debug \
    --tags a b c --ports 8000 8001 8002 \
    --settings config.json \
    --timeout 30 \
    --output /var/log/app.log \
    --status inactive
```

---

## Exception Classes

### `ConfigBuilderError`

Base exception for configuration building errors.

**Raised when:**
- Invalid dataclass configuration
- Conflicting annotations
- Multiple positional lists
- Positional list not at end

**Example:**
```python
from dataclass_args.exceptions import ConfigBuilderError

try:
    config = build_config(InvalidConfig)
except ConfigBuilderError as e:
    print(f"Configuration error: {e}")
```

---

### `ConfigurationError`

Exception raised for configuration validation errors.

**Raised when:**
- Invalid configuration values
- Type conversion failures
- Validation errors

---

### `FileLoadingError`

Exception raised when file loading fails.

**Raised when:**
- File not found
- File read errors
- Invalid file format

---

## Utility Functions

### `load_structured_file(file_path)`

Load structured data from JSON, YAML, or TOML file.

Automatically detects file format based on extension and attempts to parse.

**Parameters:**
- `file_path` (str): Path to the file

**Returns:**
- `dict`: Parsed file content

**Raises:**
- `FileLoadingError`: If file cannot be loaded or parsed

**Supported Formats:**
- `.json` - JSON files
- `.yaml`, `.yml` - YAML files (requires PyYAML)
- `.toml` - TOML files (requires tomli on Python < 3.11)

---

### `load_file_content(file_path)`

Load content from a file as UTF-8 encoded text.

**Parameters:**
- `file_path` (str): Path to the file

**Returns:**
- `str`: File content as string

**Raises:**
- `FileLoadingError`: If file cannot be read

---

### `is_file_loadable_value(value)`

Check if a value is a file-loadable string (starts with '@').

**Parameters:**
- `value` (Any): Value to check

**Returns:**
- `bool`: True if value is a string starting with '@'

---

## Configuration File Support

### Loading Configuration Files

Configuration files can be loaded using the `--config` option (automatically added).

**Supported Formats:**
- JSON (built-in)
- YAML (requires `pip install "dataclass-args[yaml]"`)
- TOML (requires `pip install "dataclass-args[toml]"`)

**Example:**

```yaml
# config.yaml
name: MyApp
port: 8000
debug: true
tags:
  - web
  - api
```

```python
@dataclass
class Config:
    name: str
    port: int = 8000
    debug: bool = False
    tags: List[str] = None

# Load from file and override
config = build_config(Config, args=['--config', 'config.yaml', '--port', '9000'])
# Result: name="MyApp", port=9000 (overridden), debug=True, tags=["web", "api"]
```

---

## Advanced Usage

### Custom Validation

Add custom validation in `__post_init__`:

```python
@dataclass
class Config:
    port: int = cli_short('p', default=8000)
    max_connections: int = 100

    def __post_init__(self):
        if self.port < 1024:
            raise ValueError("Port must be >= 1024")
        if self.max_connections <= 0:
            raise ValueError("max_connections must be positive")
```

### Nested Dataclasses

Use nested dataclasses for structured configuration:

```python
@dataclass
class DatabaseConfig:
    host: str = "localhost"
    port: int = 5432
    database: str = "mydb"

@dataclass
class AppConfig:
    name: str
    debug: bool = False
    database: Dict[str, Any] = None  # Load from config file

config = build_config(AppConfig, args=[
    '--name', 'myapp',
    '--database', 'db_config.json'
])

# Convert dict to dataclass
if config.database:
    db_config = DatabaseConfig(**config.database)
```

### Environment Variable Integration

Combine with environment variables:

```python
import os

@dataclass
class Config:
    api_key: str = os.getenv('API_KEY', '')
    port: int = cli_short('p', default=8000)

    def __post_init__(self):
        if not self.api_key:
            raise ValueError("API_KEY environment variable required")
```

---

## Best Practices

1. **Use Type Hints**: Always provide type hints for proper parsing
2. **Provide Defaults**: Use sensible defaults when possible
3. **Add Help Text**: Use `cli_help()` for clear documentation
4. **Validate in `__post_init__`**: Add custom validation after initialization
5. **Group Related Options**: Use short options for frequently used flags
6. **Use Positional for Required Args**: Consider positional args for required inputs
7. **Combine Annotations**: Use `combine_annotations()` for complex configurations
8. **Document Choices**: Use `cli_choices()` for restricted value sets

---

## Migration Guide

### From argparse

**Before:**
```python
import argparse

parser = argparse.ArgumentParser()
parser.add_argument('--name', required=True)
parser.add_argument('--port', type=int, default=8000)
parser.add_argument('--debug', action='store_true')
args = parser.parse_args()
```

**After:**
```python
from dataclasses import dataclass
from dataclass_args import build_config

@dataclass
class Config:
    name: str
    port: int = 8000
    debug: bool = False

config = build_config(Config)
```

### From click

**Before:**
```python
import click

@click.command()
@click.option('--name', required=True)
@click.option('--port', default=8000)
@click.option('--debug/--no-debug', default=False)
def main(name, port, debug):
    pass
```

**After:**
```python
from dataclasses import dataclass
from dataclass_args import build_config

@dataclass
class Config:
    name: str
    port: int = 8000
    debug: bool = False

config = build_config(Config)
```

---

## See Also

- [README.md](../README.md) - Overview and quick start
- [QUICKSTART.md](../QUICKSTART.md) - 5-minute tutorial
- [COVERAGE.md](COVERAGE.md) - Test coverage information
- [CONTRIBUTING.md](../CONTRIBUTING.md) - Development guide
- [examples/](../examples/) - Working code examples
