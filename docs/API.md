# API Reference

Complete API documentation for dataclass-args.

## Table of Contents

- [Main Functions](#main-functions)
- [Layered Configuration](#layered-configuration)
- [Annotation Functions](#annotation-functions)
- [Advanced Classes](#advanced-classes)
- [Type Support](#type-support)
- [Exception Classes](#exception-classes)
- [Utility Functions](#utility-functions)
- [Object Instantiation](#object-instantiation)
- [Best Practices](#best-practices)
- [Migration Guide](#migration-guide)

---

## Main Functions

All three entry points share the following merge and layering parameters (and so does `GenericConfigBuilder.build_config`):

| Parameter | Default | Meaning |
|---|---|---|
| `base_configs` | `None` | Lowest-precedence sources: a file path (`str`), a `dict`, a [`ConfigLayer`](#configlayerdata-namenone-list_mergereplace), or a list mixing them. Applied in order, so later ones win. |
| `merge_strategy` | `"shallow"` | How dicts from different sources combine: `"shallow"` merges top-level keys (nested dicts are replaced); `"deep"` merges at every depth. Any other value raises `ConfigBuilderError` before any file is loaded. See [Deep Merge](#deep_mergebase-override). |
| `return_provenance` | `False` | `True` (deep mode only) returns `(instance, Provenance)`. See [Provenance](#provenance). |

Precedence (later wins): `base_configs[0] < base_configs[1] < … < --config file < CLI arguments`. Lists replace (except in [rules layers](#cli_list_mergemode-pathsnone-kwargs)), and an explicit `None` clears a value.

### `build_config(config_class, args=None, base_configs=None, description=None, merge_strategy="shallow", return_provenance=False)`

The primary function for generating a CLI from a dataclass.

**Parameters:**
- `config_class` (Type[dataclass]): the dataclass to convert to a CLI.
- `args` (Optional[List[str]]): command-line arguments to parse. Defaults to `sys.argv[1:]`.
- `description` (Optional[str]): ArgumentParser description. Defaults to `"Build <ClassName> from CLI"`.
- `base_configs`, `merge_strategy`, `return_provenance`: see the table above.

**Returns:** an instance of `config_class`, or `(instance, Provenance)` when `return_provenance=True`.

**Raises:**
- `SystemExit`: argument parsing failed, or `--help` was requested.
- `ConfigBuilderError`: the dataclass annotations, `merge_strategy` or the layer options are invalid.
- `ConfigurationError`: a configuration source couldn't be loaded or applied.

**Example:**
```python
from dataclasses import dataclass
from dataclass_args import build_config

@dataclass
class Config:
    name: str
    port: int = 8000

config = build_config(Config)                                   # parse sys.argv
config = build_config(Config, args=['--name', 'myapp', '--port', '9000'])
config = build_config(Config, args=['--name', 'x'], base_configs='defaults.yaml')
```

---

### `build_config_from_cli(config_class, args=None, base_config_name="config", base_configs=None, description=None, merge_strategy="shallow", return_provenance=False)`

Like `build_config`, plus control over the name of the config-file option.

**Parameters:**
- `base_config_name` (str): name of the config-file option (`--config` by default). The file it names is applied after `base_configs` and before CLI arguments.
- Everything else: as for `build_config`.

**Example:**
```python
from dataclass_args import build_config_from_cli

config = build_config_from_cli(
    Config,
    args=['--settings', 'prod.yaml', '--name', 'test'],
    base_config_name='settings',          # --settings instead of --config
    base_configs=['defaults.yaml', {'debug': True}],
    description='My Application CLI',
)
```

---

### `build_config_from_dict(config_class, config, base_configs=None, config_list_merge="replace", merge_strategy="shallow", return_provenance=False)`

Build a dataclass instance from a plain dictionary, with the full resolution pipeline. There's no command line. This is the recommended entry point for Lambda handlers, SDKs and test harnesses.

**Parameters:**
- `config_class` (Type[dataclass]): the dataclass to instantiate.
- `config` (Dict[str, Any]): field values. This has the highest precedence. Hyphenated field names (`db-host`) are accepted.
- `config_list_merge` (str): `"replace"` (default) or `"rules"`. With `"rules"` (deep mode only), `config` is treated as a [rules layer](#cli_list_mergemode-pathsnone-kwargs), so its annotated lists append onto `base_configs`.
- `base_configs`, `merge_strategy`, `return_provenance`: see the table above. In deep mode, `config` is applied as a single layer named `"config"`.

**Returns:** an instance of `config_class`, or `(instance, Provenance)`.

**Raises:**
- `TypeError`: `config` is not a dict.
- `ConfigBuilderError`: invalid options (for example `config_list_merge="rules"` with shallow merge).
- `ConfigurationError`: resolution failed, including a missing required field or positional. This function **never** calls `sys.exit`.

**What works:**
- `@file` references for `cli_file_loadable` fields;
- dict-field file paths (`.json`, `.yaml`, `.yml`, `.toml`);
- `cli_resolve()` resolvers;
- `cli_nested` dataclasses at any depth (given as dicts or instances);
- `cli_exclude()` fields;
- every positional field (there's no command line to require them);
- explicit `None` to clear a value.

**What doesn't apply:** `cli_choices()` validation. Choices are enforced by argparse, and a dict bypasses argparse.

**Example:**
```python
from dataclass_args import build_config_from_dict

config = build_config_from_dict(AppConfig, {
    "name": "production",
    "port": 8080,
    "database": {"host": "prod-db.example.com", "port": 5432},
})

# Layered, with list rules and provenance
config, prov = build_config_from_dict(
    AppConfig, {"plugins": ["runtime"]},
    base_configs=["defaults.yaml"],
    merge_strategy="deep", config_list_merge="rules", return_provenance=True,
)

build_config_from_dict(AppConfig, "not_a_dict")  # TypeError
```

---

## Layered Configuration

### `ConfigLayer(data, name=None, list_merge="replace")`

A frozen dataclass describing one configuration layer. It's accepted anywhere `base_configs` accepts a path or a dict.

- `data` (str | dict): a file path, loaded like a plain `base_configs` string, or a dict, which is copied and never mutated.
- `name` (Optional[str]): the layer name used in provenance and error messages. When it's omitted, the name is the file path, or `base_configs[i]` for a dict.
- `list_merge` (str): `"replace"` (default) or `"rules"`. In a rules layer, fields annotated with [`cli_list_merge`](#cli_list_mergemode-pathsnone-kwargs) append instead of replacing. Rules require `merge_strategy="deep"`.

Invalid arguments raise `ConfigBuilderError` when the layer is constructed.

### Provenance

`return_provenance=True` (deep mode only) returns `(instance, Provenance)`.

| Method | Returns |
|---|---|
| `entries(path) -> List[ProvenanceEntry]` | Every event at `path`, in order (`[]` if there are none). |
| `source(path) -> Optional[str]` | The layer that set the final value; `"default"` for an unset dataclass field; otherwise `None` (unknown or removed paths, unset keys inside dict fields, `cli_nested` container paths). |
| `paths() -> List[str]` | The existing leaf paths set by layers, sorted. |
| `changes() -> List[ProvenanceChange]` | Every place where a later layer discarded an earlier value (`replaced`, `cleared`, `removed`), in order. |
| `explain() -> str` | A plain-text `path \| source \| value` table, followed by the defaults. |

- **Entries.** `ProvenanceEntry(layer, value, action)`. The action is one of `set`, `replaced`, `confirmed` (same value again), `cleared` (explicit `None`), `appended` (list rule) or `removed` (a sub-tree replaced by a non-dict, or a leaf replaced by a dict).
- **Changes.** `ProvenanceChange(path, from_layer, from_value, to_layer, to_value, action)`. For `removed`, `to_value is MISSING_VALUE`.
- **Paths** are dotted keys. Dicts are recursed into, and lists, scalars and objects are leaves.
- **Raw values.** Values are recorded after files are loaded and before `@file` and `cli_resolve` resolution, so the instance holds the resolved values.
- **Layer names:**
  - the `ConfigLayer` name, otherwise the default above;
  - `config_file:<path>` for the config-file option;
  - `config` for the `build_config_from_dict` dict;
  - `cli` for command-line values.

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

### `cli_append(nargs=None, min_args=None, max_args=None, metavar=None, **kwargs)`

Mark a field for append action - allows repeating the option multiple times.

Each occurrence of the option collects its arguments, and all occurrences accumulate into a list.

**Parameters:**
- `nargs` (Optional[Union[int, str]]): Number of arguments per occurrence:
  - `None` (default): One value per occurrence → `List[T]`
  - `int` (e.g., `2`): Exact count per occurrence → `List[List[T]]`
  - `'+'`: One or more per occurrence → `List[List[T]]`
  - `'*'`: Zero or more per occurrence → `List[List[T]]`
  - `'?'`: Zero or one per occurrence → `List[T]`
  - **Mutually exclusive with** `min_args`/`max_args`
- `min_args` (Optional[int]): Minimum arguments per occurrence (must be >= 1)
  - Must be used together with `max_args`
  - Provides automatic validation with clear error messages
- `max_args` (Optional[int]): Maximum arguments per occurrence (must be >= min_args)
  - Must be used together with `min_args`
  - Enables clean help text display
- `metavar` (Optional[str]): Custom display name for arguments in help text
- `**kwargs`: Field parameters including `default_factory` (required)

**Returns:**
- `Field` with append action metadata

**Important:** Always use `default_factory=list`, not `default=[]`

**Examples:**

```python
from typing import List
from dataclass_args import cli_append, cli_short, cli_help, combine_annotations

# Simple tags (single value per -t)
@dataclass
class Config:
    tags: List[str] = combine_annotations(
        cli_short('t'),
        cli_append(),
        default_factory=list
    )

# CLI: -t python -t cli -t tool
# Result: ['python', 'cli', 'tool']

# Pairs (exactly 2 per occurrence)
@dataclass
class DockerConfig:
    ports: List[List[str]] = combine_annotations(
        cli_short('p'),
        cli_append(nargs=2),
        cli_help("Port mapping (HOST CONTAINER)"),
        default_factory=list
    )

# CLI: -p 8080 80 -p 8443 443
# Result: [['8080', '80'], ['8443', '443']]

# Variable args with validation (1 or 2 per occurrence)
@dataclass
class UploadConfig:
    files: List[List[str]] = combine_annotations(
        cli_short('f'),
        cli_append(nargs='+'),
        cli_help("File with optional MIME type"),
        default_factory=list
    )

    def __post_init__(self):
        for file_spec in self.files:
            if len(file_spec) < 1 or len(file_spec) > 2:
                raise ValueError("Each file needs 1-2 arguments")

# CLI: -f doc.pdf application/pdf -f image.png -f video.mp4 video/mp4
# Result: [['doc.pdf', 'application/pdf'], ['image.png'], ['video.mp4', 'video/mp4']]

# Environment variables
@dataclass
class AppConfig:
    env_vars: List[List[str]] = combine_annotations(
        cli_short('e'),
        cli_append(nargs=2),
        cli_help("Environment variable (KEY VALUE)"),
        default_factory=list
    )

# CLI: -e DEBUG true -e LOG_LEVEL info -e PORT 8080
# Result: [['DEBUG', 'true'], ['LOG_LEVEL', 'info'], ['PORT', '8080']]
```

**Use Cases:**
- Docker-style options: `-p HOST:CONTAINER`, `-v SOURCE:TARGET`, `-e KEY=VALUE`
- File operations: `-f file type`, multiple file uploads
- Server pools: `-s host port` repeated
- Build systems: `-I dir`, `-D key value`
- Tag/label collection: `-t tag` repeated

**Comparison with Regular Lists:**

Regular `List[T]` (single flag, all values after it):
```python
files: List[str] = cli_short('f', default_factory=list)
# CLI: -f file1 file2 file3
# Problem: -f file1 -f file2 → Only ['file2'] (last wins)
```

With `cli_append()` (repeated flags accumulate):
```python
files: List[str] = combine_annotations(
    cli_short('f'),
    cli_append(),
    default_factory=list
)
# CLI: -f file1 -f file2 -f file3
# Result: ['file1', 'file2', 'file3'] ← All accumulated!
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

### `cli_nested(prefix=None, default_factory=None, **kwargs)`

Mark a dataclass field as a nested configuration that should be flattened into CLI arguments.

**Parameters:**
- `prefix` (Optional[str]): Prefix for nested field CLI names
  - `None` (default): Auto-prefix using field name (e.g., `"database"` → `--database-host`)
  - `""` (empty string): No prefix, complete flattening (e.g., `--host`)
  - Custom string: Use specified prefix (e.g., `"db"` → `--db-host`)
- `default_factory` (Callable): Factory function to create default instance
- `**kwargs`: Field parameters (passed to dataclass field)

**Returns:**
- `Field` with nested dataclass metadata

**Behavior:**
- **With prefix**: Short options in nested fields are ignored (prevents conflicts)
- **Without prefix (`prefix=""`)**: Short options in nested fields are enabled
- **Automatic collision detection**: Field names and short options are validated

**Example:**
```python
from dataclasses import dataclass
from dataclass_args import build_config, cli_nested, cli_short

@dataclass
class DatabaseConfig:
    host: str = "localhost"
    port: int = 5432
    username: str = "admin"
    password: str = ""

@dataclass
class AppConfig:
    app_name: str = "myapp"

    # Custom prefix
    database: DatabaseConfig = cli_nested(prefix="db", default_factory=DatabaseConfig)

config = build_config(AppConfig)
# CLI: --app-name MyApp --db-host prod.com --db-port 5432
```

**Prefix Modes:**

1. **Custom Prefix:**
```python
database: DatabaseConfig = cli_nested(prefix="db", default_factory=DatabaseConfig)
# CLI: --db-host, --db-port, --db-username
```

2. **No Prefix (Complete Flattening):**
```python
credentials: Credentials = cli_nested(prefix="", default_factory=Credentials)
# CLI: --username, --password (no prefix)
# Short options enabled if defined in nested dataclass
```

3. **Auto Prefix (Field Name):**
```python
database: DatabaseConfig = cli_nested(default_factory=DatabaseConfig)
# CLI: --database-host, --database-port (uses field name)
```

**Short Options:**
```python
@dataclass
class ServerConfig:
    host: str = cli_short("H", default="localhost")   # (-h is reserved for --help)

@dataclass
class Config:
    # With prefix: -H is ignored (no conflict)
    server: ServerConfig = cli_nested(prefix="srv", default_factory=ServerConfig)
    # CLI: --srv-host (no -H)

    # No prefix: -H is enabled
    server2: ServerConfig = cli_nested(prefix="", default_factory=ServerConfig)
    # CLI: -H, --host (short option works)
```

**Collision Detection:**
```python
@dataclass
class Nested:
    name: str = "nested"

@dataclass
class Config:
    name: str = "parent"
    nested: Nested = cli_nested(prefix="", default_factory=Nested)

# ERROR: Field name collision detected on --name
```

**Config File Integration:**
```yaml
# config.yaml
database:
  host: "prod-db.example.com"
  port: 5432
  username: "prod_user"
```

```python
# CLI with partial override
config = build_config(AppConfig, args=[
    '--config', 'config.yaml',
    '--db-password', 'secret'  # Override specific field
])

# Result:
# - database.host: "prod-db.example.com" (from file)
# - database.port: 5432 (from file)
# - database.password: "secret" (CLI override)
```

**See Also:**
- [README: Nested Dataclasses](../README.md#nested-dataclasses)
- [Example: nested_dataclass.py](../examples/nested_dataclass.py)
- [Example: nested_short_options.py](../examples/nested_short_options.py)

---

### `cli_resolve(resolver, **kwargs)`

Mark a field for post-load resolution via a caller-provided resolver function.

After the raw value is assembled from all configuration sources (base_configs, config file, CLI arguments), the resolver function transforms it into the final field value. For non-list fields, the field is treated as dict-loadable during parsing (supports file paths and property overrides). For list fields, natural list parsing behavior is retained and the resolver receives the assembled list.

**Parameters:**
- `resolver` (Callable[[Any], Any]): Function that transforms the raw value into the final value.
  NOT called if raw value is None. Should handle pass-through for pre-built objects if needed.
- `**kwargs`: Field parameters (e.g., `default`, `default_factory`)

**Returns:**
- `Field` with resolver metadata

**Raises:**
- `ValueError`: If resolver is not callable

**Behavior:**
- Field type should be the FINAL type (e.g., `Optional[Sandbox]`) for correct type checking
- For **list fields**: retains natural list parsing (nargs), resolver receives assembled list
- For **non-list fields**: treated as dict field (file path + property overrides)
- After all config assembly, resolver is called on non-None values (stage 8 of the pipeline)
- None values bypass the resolver (natural Optional semantics)
- Resolver is always called for non-None values — resolver handles pass-through for pre-built objects
- Resolver exceptions wrapped in `ConfigurationError` with field context
- `ConfigurationError` raised by resolver is re-raised without double-wrapping

**Compatibility:**
- Works with: `cli_help`, `cli_short`, `cli_choices`, `cli_list_merge`, `cli_extend` (list fields), `combine_annotations`
- Incompatible with: `cli_positional`, `cli_nested`, `cli_append`, `cli_exclude`, `cli_file_loadable`
- In nested dataclasses: allowed but resolver NOT called (value stays raw; application resolves explicitly)

**Example:**
```python
from typing import Any, Optional
from dataclass_args import build_config, cli_resolve, cli_help, combine_annotations

class SandboxBase:
    """Base class for sandbox implementations."""
    pass

class DockerSandbox(SandboxBase):
    def __init__(self, image: str = "python:3.11", memory: str = "512m"):
        self.image = image
        self.memory = memory

def resolve_sandbox(value: Any) -> SandboxBase:
    """Resolver that converts a dict to a Sandbox instance."""
    if isinstance(value, dict):
        sandbox_type = value.get("type", "local")
        if sandbox_type == "docker":
            return DockerSandbox(
                image=value.get("image", "python:3.11"),
                memory=value.get("memory", "512m"),
            )
        raise ValueError(f"Unknown sandbox type: {sandbox_type}")
    # Pass-through for pre-built objects
    return value

@dataclass
class AppConfig:
    app_name: str = "myapp"
    sandbox: Optional[SandboxBase] = combine_annotations(
        cli_resolve(resolver=resolve_sandbox),
        cli_help("Sandbox configuration"),
        default=None,
    )

# Load from config file and resolve
config = build_config(AppConfig, args=['--sandbox', 'sandbox.yaml'])

# With property overrides (applied before resolution)
config = build_config(AppConfig, args=[
    '--sandbox', 'sandbox.yaml',
    '--s', 'image:python:3.12'
])

# Programmatic with pre-built object (resolver passes through)
config = build_config(
    AppConfig,
    args=[],
    base_configs={'sandbox': DockerSandbox(image='pre-built:latest')}
)
```

**List field example:**
```python
def resolve_paths(patterns):
    import glob
    files = [f for p in patterns for f in glob.glob(p)]
    return [load_structured_file(f) for f in files]

@dataclass
class Config:
    configs: List[Any] = combine_annotations(
        cli_resolve(resolver=resolve_paths),
        default_factory=list,
    )

# CLI: --configs "*.json" "extra/*.yaml"
# resolver receives: ["*.json", "extra/*.yaml"]
config = build_config(Config, args=["--configs", "*.json", "extra/*.yaml"])
```

**CLI Usage:**
```bash
# Load sandbox from a JSON/YAML file
python app.py --sandbox sandbox.yaml

# Override property before resolution
python app.py --sandbox sandbox.yaml --s image:node:18

# Full config with sandbox section
python app.py --config app.yaml
```

**Pipeline Position:**
```
Stage 1: Normalize layers (file refs loaded, keys normalized, nested instances → dicts)
Stage 2: Apply base_configs (one-level or deep merge; list rules in rules layers)
Stage 3: Apply config file
Stage 4: Apply CLI overrides
Stage 5: Resolve raw values (@file references)
Stage 6: Reconstruct nested dataclasses (any depth)
Stage 7: Validate append ranges
Stage 8: Resolve fields ← cli_resolve runs here
Stage 9: Create dataclass instance
```

**Error Handling:**
```python
# Generic errors wrapped with field context:
# ConfigurationError: Failed to resolve field 'sandbox': Unknown type 'invalid'

# ConfigurationError from resolver passes through unchanged:
# ConfigurationError: Custom error message from resolver
```

**See Also:**
- [README: Field Resolution](../README.md#field-resolution)
- [Example: cli_resolve_example.py](../examples/cli_resolve_example.py)

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
    content: str = cli_file_loadable(default="")
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

### `cli_override_name(name, **kwargs)`

Sets the abbreviation of a dict field's property-override option. By default it's built from the field name's initials (`model_config` → `--mc`). Use this to resolve collisions: two dict fields that would produce the same abbreviation raise `ConfigBuilderError` when the builder is constructed.

```python
sandbox_config: Dict[str, Any] = field(default_factory=dict)                   # --sc
skills_config: Dict[str, Any] = cli_override_name("sk", default_factory=dict)  # --sk
```

---

### `cli_list_merge(mode, paths=None, **kwargs)`

Makes a list merge by **appending** when it comes from a `list_merge="rules"` [`ConfigLayer`](#configlayerdata-namenone-list_mergereplace), or from the `build_config_from_dict` config with `config_list_merge="rules"`. Everywhere else it replaces as usual: in plain layers, the config-file option and CLI arguments.

- `mode`: `"append"` (concatenate) or `"append_unique"` (add only the elements not already present, compared with `==`; existing order is kept; unhashable elements work).
- `paths`:
  - `None` for a `List[...]` field, so the rule applies to the field itself;
  - required for a dict field: a list of dotted paths to lists inside the dict, such as `["roots", "policy.denied"]`.

The rule applies only where both the earlier and the later value are lists. Otherwise the later value wins, and `None` clears.

```python
plugins: List[str] = combine_annotations(cli_list_merge("append_unique"), default_factory=list)
skills: Dict[str, Any] = combine_annotations(
    cli_list_merge("append_unique", paths=["roots", "policy.denied"]), default_factory=dict)
```

**Validation.**
- An invalid `mode`, or an empty path, raises `ValueError` when the annotation is created.
- These raise `ConfigBuilderError` when the builder is constructed:
  - `paths` on a list field;
  - a dict field without `paths`;
  - a field that's neither a list nor a dict;
  - a `cli_nested` field. Annotate the nested class's own fields instead; rules apply at any depth.

**Compatible with:** `cli_resolve`, `cli_append`, `cli_extend`, `cli_help`, `cli_short`, `cli_positional`, `cli_exclude`. No CLI arguments are added.

---

### `cli_extend(**kwargs)`

Makes a `List[T]` / `Optional[List[T]]` option **repeatable**. Every occurrence's values are appended to one flat list (argparse `action="extend"`). Without it, a repeated list flag keeps only its last occurrence.

```python
paths: List[str] = combine_annotations(cli_short("p"), cli_extend(), default_factory=list)
# -p a -p b       → ['a', 'b']
# -p a b -p c     → ['a', 'b', 'c']
```

- **When the flag is omitted:** earlier sources and the dataclass default keep their value.
- **When it's given:** the accumulated CLI list replaces earlier sources as a whole. It's never appended to a default or to a config value.
- **Values:** element types are converted, and `cli_choices` is checked for every value. `Optional[List[T]]` with no values yields `[]`.
- **Nesting:** works in nested dataclasses at any depth.
- **Help suffix:** "(specify one or more values; repeatable)", or "zero or more" for Optional.
- **Raises `ConfigBuilderError`** (when the builder is constructed) on:
  - a non-list field;
  - a list with non-scalar elements (lists, tuples, sets, dicts, dataclasses). The message names the element type, and suggests `cli_append(nargs=…)` for a list of lists. Unions and `Optional`s of scalars (`List[Union[str, Path]]`, `list[str | Path]`) are accepted;
  - combination with `cli_append`, `cli_positional` or `cli_exclude`.
- **Compatible with:** `cli_short`, `cli_help`, `cli_choices`, `cli_resolve` (the resolver receives the final list), `cli_list_merge` (which applies between config sources, never to CLI values).

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
from dataclass_args import combine_annotations, cli_positional, cli_short, cli_choices, cli_help

@dataclass
class Config:
    # Combine help + positional (fields without defaults must come first)
    input_file: str = combine_annotations(
        cli_positional(),
        cli_help("Input file path")
    )

    # Combine short option + choices + help
    environment: str = combine_annotations(
        cli_short('e'),
        cli_choices(['dev', 'staging', 'prod']),
        cli_help("Deployment environment"),
        default='dev'
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

#### `build_config(args, base_config_name=None, base_configs=None, merge_strategy="shallow", return_provenance=False)`

Build a dataclass instance from parsed CLI arguments.

**Parameters:**
- `args` (argparse.Namespace): parsed arguments from the ArgumentParser.
- `base_config_name` (Optional[str]): name of the config-file argument (`config` by default).
- `base_configs`, `merge_strategy`, `return_provenance`: as for [the main functions](#main-functions).

**Returns:** an instance of the configured dataclass, or `(instance, Provenance)`.

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
| `List[str]` | Multiple string values (one flag; repeat with `cli_extend`) | `--tags a b c` | `["a", "b", "c"]` |
| `List[int]` | Multiple integer values | `--ids 1 2 3` | `[1, 2, 3]` |
| `List[float]` | Multiple float values | `--values 1.5 2.5` | `[1.5, 2.5]` |
| `Dict[str, Any]` | Dict or structured file, plus key:value overrides | `--model-config m.json` or `--mc k:v` | `{...}` |
| `Optional[T]` | Optional parameter | `--timeout 30` or omit | `30` or `None` |
| `Path` | File path (passed through as typed; not converted) | `--output /tmp/file` | `'/tmp/file'` (str) |
| `Enum` | Value as typed (not converted to the member) | `--status active` | `'active'` (str) |

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

Raised for programming errors: problems with the dataclass definition or the builder options. It's raised when the builder is constructed, or in `add_arguments`, before any configuration is loaded.

**Raised when:**
- Invalid dataclass configuration, or invalid or conflicting annotations (e.g. `cli_resolve` with `cli_append`, or `cli_list_merge` on a `cli_nested` field)
- **Option-name collisions.** Every option string the parser would contain is checked before anything is registered:
  - `-h`/`--help` and the `--config` option;
  - field long and short options at any nesting depth;
  - `--no-` flags and dict override options.

  The message lists every claimant and suggests a fix: `cli_override_name()`, a different `cli_short` letter, renaming a field, or a different `base_config_name`.
- Multiple positional lists, or a positional list that isn't last
- A `cli_nested` cycle (`A.b -> B.a -> A`)
- An invalid `merge_strategy`, `list_merge` or `config_list_merge`, or a layered-mode feature used with `merge_strategy="shallow"`

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

### `InstantiationError`

Exception raised when object instantiation from configuration fails.

**Raised when:**
- String config value has no registry or key not found in registry
- Import of target class path fails (module not found, attribute not found)
- Object construction fails (missing required args, validation errors)
- Maximum recursion depth exceeded
- Attribute traversal fails (`_attr_` path doesn't exist)

**Note:** `InstantiationError` is a direct subclass of `Exception`, not `ConfigBuilderError`. It represents a distinct concern (object construction from config).

**Example:**
```python
from dataclass_args import instantiate, InstantiationError

try:
    obj = instantiate({"_target_": "nonexistent.module.Class"})
except InstantiationError as e:
    print(f"Instantiation failed: {e}")
    # Error message includes path context for debugging
```

---

## Utility Functions

### `deep_merge(base, override)`

Returns a **new** dict with `override` recursively merged onto `base`. Neither input is mutated, and every dict and list in the result is a fresh container.

- Two dicts at the same key are merged recursively.
- Any other combination: the override wins. That includes lists (which replace) and `None` (which clears).
- Keys only in `base` are kept.
- Dataclass instances and other objects aren't recursed into.

```python
deep_merge({'db': {'host': 'h', 'pool': {'min': 1}}}, {'db': {'pool': {'max': 5}}})
# {'db': {'host': 'h', 'pool': {'min': 1, 'max': 5}}}
```

`MERGE_SHALLOW` (`"shallow"`) and `MERGE_DEEP` (`"deep"`) are exported as constants for `merge_strategy`.

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
- `.toml` - TOML files (built in via `tomllib`)

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

## Object Instantiation

### `instantiate(config, *, registry=None, target_key="_target_", type_key="type", attr_key="_attr_", recursive=True, max_depth=10)`

Construct a Python object from a configuration value using convention-based dispatch.

**Parameters:**
- `config` (Any): The configuration value to instantiate from. Can be:
  - `None` — returns None
  - Non-dict, non-string — returned as-is (pass-through)
  - `str` — looked up in registry
  - `dict` — dispatched based on special keys
- `registry` (Optional[Dict[str, str]]): Mapping of type names to importable class paths. Required for string configs and dicts with `type` key.
- `target_key` (str): Dict key indicating a direct import path. Default: `"_target_"`
- `type_key` (str): Dict key indicating a registry lookup name. Default: `"type"`
- `attr_key` (Optional[str]): Dict key indicating post-construction attribute traversal. Set to `None` to disable. Default: `"_attr_"`
- `recursive` (bool): Whether to recursively resolve nested dicts in kwargs based on `__init__` type annotations. Default: `True`
- `max_depth` (int): Maximum recursion depth to prevent infinite loops. Default: `10`

**Returns:**
- The instantiated object, or the original value for pass-through cases.

**Raises:**
- `InstantiationError`: When instantiation fails. Error messages include the resolution path for debugging (e.g., `"root.database.connection_pool"`).

**Dispatch Rules (priority order):**

| Rule | Condition | Behavior |
|------|-----------|----------|
| 1 | `config is None` | Return `None` |
| 2 | Not dict and not string | Return as-is (pass-through) |
| 3 | String + registry | Lookup class path in registry, call `cls()` |
| 4 | Dict with `_target_` key | Import class from path, call `cls(**remaining_kwargs)` |
| 5 | Dict with `type` key + registry | Lookup in registry, call `cls(**remaining_kwargs)` |
| 6 | Dict with neither key | Return as-is (plain dict) |

**Examples:**

```python
from dataclass_args import instantiate, InstantiationError

# Rule 1: None pass-through
assert instantiate(None) is None

# Rule 2: Non-dict/non-string pass-through
assert instantiate(42) == 42

# Rule 3: String + registry
registry = {"docker": "myapp.sandboxes.DockerSandbox"}
sandbox = instantiate("docker", registry=registry)

# Rule 4: Dict with _target_
config = {
    "_target_": "myapp.sandboxes.DockerSandbox",
    "image": "python:3.11",
    "memory": "512m",
}
sandbox = instantiate(config)

# Rule 5: Dict with type + registry
config = {"type": "docker", "image": "python:3.11"}
sandbox = instantiate(config, registry=registry)

# Rule 6: Plain dict (no special keys)
plain = {"key": "value"}
assert instantiate(plain) == {"key": "value"}
```

**Attribute Traversal (`_attr_`):**

After constructing an object, if the dict contained an `_attr_` key, the dotted path is traversed on the result:

```python
config = {
    "_target_": "myapp.Toolkit",
    "_attr_": "tools.search.engine",
}
# Constructs Toolkit(), then returns obj.tools.search.engine
engine = instantiate(config)
```

**Recursive Resolution:**

Nested dicts are recursively resolved based on the target class's `__init__` type annotations:

```python
config = {
    "_target_": "myapp.Server",
    "name": "prod",
    "database": {
        "_target_": "myapp.Database",
        "host": "db.example.com",
        "port": 5432,
    },
}
server = instantiate(config)
# server.database is a Database instance (recursively resolved)
```

List elements with dispatch keys are also resolved:

```python
config = {
    "_target_": "myapp.Pipeline",
    "steps": [
        {"_target_": "myapp.steps.Tokenize"},
        {"_target_": "myapp.steps.Embed", "model": "ada-002"},
    ],
}
pipeline = instantiate(config)
# pipeline.steps contains [Tokenize(), Embed(model="ada-002")]
```

**Use Cases:**
- Factory pattern: config files describe objects declaratively
- Plugin systems: registry maps short names to implementations
- Config-driven architecture: entire object graphs from YAML/JSON
- Hydra/OmegaConf-style configuration

**See Also:**
- [README: Object Instantiation](../README.md#object-instantiation)

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
