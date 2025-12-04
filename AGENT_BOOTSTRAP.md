# Dataclass Args - Agent Bootstrap Guide

## Project Overview

**dataclass-args** is a Python library that provides zero-boilerplate CLI generation from Python dataclasses with advanced type support and file loading capabilities. It transforms dataclass definitions into fully-featured command-line interfaces with minimal code.

- **Repository**: https://github.com/bassmanitram/dataclass-args
- **PyPI Package**: https://pypi.org/project/dataclass-args/
- **Current Version**: 1.3.0
- **License**: MIT
- **Python Support**: 3.8, 3.9, 3.10, 3.11, 3.12

## Core Purpose

The library eliminates boilerplate code for creating CLIs by automatically generating argument parsers from dataclass definitions. It bridges the gap between configuration management and command-line interfaces with a type-safe, annotation-based approach.

## Key Features

### 1. **Automatic CLI Generation**
- Single function call (`build_config()`) generates complete CLI from dataclass
- Automatic help text generation and argument parsing
- Type-aware parsing for all standard Python types

### 2. **Short Options** (`cli_short`)
- Concise `-n` flags in addition to `--name` long forms
- Example: `cli_short('n', default="value")`

### 3. **Boolean Flags**
- Proper `--flag` and `--no-flag` boolean handling
- No need for `store_true`/`store_false` boilerplate

### 4. **Positional Arguments** (`cli_positional`)
- Support for positional args without `--` prefix
- Variable length support: `nargs='?'`, `'*'`, `'+'`, or exact count
- Validation: At most one greedy positional, must be last

### 5. **Value Validation** (`cli_choices`)
- Restrict field values to valid choices
- Example: `cli_choices(['dev', 'staging', 'prod'])`

### 6. **Repeatable Options** (`cli_append`) - NEW in v1.3.0
- Allow options to be specified multiple times
- Each occurrence collects its own arguments
- Supports `nargs` for multi-argument occurrences
- Example: `-f file1 mime1 -f file2 -f file3 mime3`
- Use cases: Docker-style options, file uploads, environment variables

### 7. **File Loading** (`cli_file_loadable`)
- Load string parameters from files using `@filename` syntax
- Home directory expansion: `@~/file.txt`
- Example: `--prompt "@~/prompts/system.txt"`

### 8. **Configuration Merging** (`base_configs`)
- Hierarchical config merging from multiple sources
- Order: `base_configs` → `--config` file → CLI args
- Accepts: single file, dict, or list of files/dicts

### 9. **Flexible Types**
- Support for `List`, `Dict`, `Optional`, `Path`, and custom types
- Nested dictionary property overrides

### 10. **Annotation Combining** (`combine_annotations`)
- Merge multiple features: short options + choices + help + append
- Clean, readable field definitions

### 11. **Custom Help Text** (`cli_help`, `description` parameter)
- Field-level custom help with `cli_help()`
- Program-level custom description parameter

## Architecture

### Project Structure

```
dataclass-args/
├── dataclass_args/          # Main package
│   ├── __init__.py         # Public API exports
│   ├── annotations.py      # Field annotation utilities (cli_short, cli_append, etc.)
│   ├── builder.py          # GenericConfigBuilder - core logic
│   ├── exceptions.py       # Custom exceptions
│   ├── file_loading.py     # File loading with @ syntax
│   └── utils.py            # Helper functions (load_structured_file, etc.)
├── tests/                   # Test suite (306 tests, 92.96% coverage)
│   ├── test_basic.py
│   ├── test_annotations.py
│   ├── test_boolean_flags.py
│   ├── test_boolean_base_configs.py
│   ├── test_cli_short.py
│   ├── test_cli_choices.py
│   ├── test_cli_append.py          # NEW in v1.3.0
│   ├── test_positional.py
│   ├── test_config_merging_simple.py
│   ├── test_description.py
│   ├── test_combine_annotations.py
│   ├── test_file_loading.py
│   ├── test_builder_advanced.py
│   └── test_utils.py
├── examples/                # Working examples
│   ├── basic_example.py
│   ├── advanced_example.py
│   ├── all_features_example.py
│   ├── boolean_flags_example.py
│   ├── cli_short_example.py
│   ├── cli_choices_example.py
│   ├── cli_append_example.py       # NEW in v1.3.0
│   ├── positional_example.py
│   ├── config_merging_example.py
│   └── custom_description_example.py
├── docs/                    # Documentation
│   ├── API.md
│   ├── COVERAGE.md
│   └── research/           # Implementation notes
├── .github/workflows/       # CI/CD pipelines
│   ├── test.yml            # Cross-platform testing
│   ├── lint.yml            # Code quality
│   ├── quality.yml         # Type checking, security
│   ├── examples.yml        # Example validation
│   ├── release.yml         # PyPI publishing
│   └── docs.yml            # Documentation
├── pyproject.toml          # Package configuration
├── README.md               # User documentation
├── CHANGELOG.md            # Version history
├── CONTRIBUTING.md         # Development guide
├── Makefile                # Development tasks
└── LICENSE                 # MIT license
```

### Core Components

#### 1. `GenericConfigBuilder` (builder.py)
The central class that orchestrates CLI generation:
- **Initialization**: Analyzes dataclass fields, extracts type hints and metadata
- **Argument Addition**: Generates argparse arguments from field definitions
- **Configuration Building**: Merges configs from multiple sources
- **Validation**: Enforces constraints (e.g., positional list rules)

Key methods:
- `__init__(config_class, description=None)` - Initialize builder
- `add_arguments(parser)` - Add all fields as arguments
- `build_config(args, base_configs=None)` - Build final config instance
- `_validate_positional_arguments()` - Enforce positional constraints
- `_add_append_argument()` - Handle repeatable options (NEW in v1.3.0)

#### 2. Annotation System (annotations.py)
Field metadata system using Python's `field(metadata={...})`:
- `cli_short(letter)` - Short option flag
- `cli_choices(choices_list)` - Value validation
- `cli_positional(nargs=None, metavar=None)` - Positional argument
- `cli_append(nargs=None)` - Repeatable option (NEW in v1.3.0)
- `cli_help(text)` - Custom help text
- `cli_exclude()` - Hide from CLI
- `cli_file_loadable()` - Enable @file loading
- `combine_annotations(*annotations)` - Merge multiple features

#### 3. Configuration Merging (builder.py)
Four-stage hierarchical merge:
1. **Programmatic base_configs** (lowest priority)
   - Files: Loaded via `load_structured_file()`
   - Dicts: Used directly
   - List: Applied sequentially
2. **Config file from `--config`**
   - Overrides base_configs
3. **CLI arguments** (highest priority)
   - Override all previous sources
4. **Dataclass instantiation**
   - Create final instance

Merge behavior:
- **Scalars**: Replace
- **Lists**: Replace (not append)
  - Exception: cli_append() fields accumulate repeated occurrences
- **Dicts**: Shallow merge (keys merged, later overrides earlier)

#### 4. File Loading (file_loading.py)
Handle `@filename` syntax for string fields:
- Detect `@` prefix: `is_file_loadable_value()`
- Load content: `load_file_content()` with path expansion
- Process fields: `process_file_loadable_value()`
- Home expansion: `~/` → user home, `~user/` → other user

#### 5. Type System Integration
Leverages Python's typing system:
- Type hints extraction via `get_type_hints()`
- Generic type inspection: `get_origin()`, `get_args()`
- Support for: `List[T]`, `List[List[T]]`, `Dict[K, V]`, `Optional[T]`, `Union`, `Path`
- Custom type handling via string conversion

### Configuration Flow

```
User defines dataclass
        ↓
build_config() called
        ↓
GenericConfigBuilder created
        ↓
Field analysis (types, annotations, defaults)
        ↓
ArgumentParser generation
  - Detect cli_append() → use action='append'
  - Detect cli_positional() → positional args
  - Regular fields → optional args
        ↓
Parse CLI arguments
        ↓
Configuration merge:
  1. base_configs (if provided)
  2. --config file (if provided)
  3. CLI overrides
        ↓
Dataclass instantiation
        ↓
Return configured instance
```

## Development Workflow

### Setup
```bash
# Clone repository
git clone https://github.com/bassmanitram/dataclass-args.git
cd dataclass-args

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dev dependencies
pip install -e ".[dev,all]"

# Setup pre-commit hooks
make setup
```

### Testing
```bash
# Run all tests (automatic coverage via pytest.ini)
pytest

# Detailed coverage report
make coverage

# Coverage HTML report (opens browser)
make coverage-html

# Run specific test file
pytest tests/test_cli_append.py

# Run with verbose output
pytest -v
```

**Test Coverage**: 92.96% (306 tests passing)
- Minimum required: 90%
- Coverage config: `pyproject.toml` [tool.coverage]

### Code Quality
```bash
# Format code (Black + isort)
make format

# Run linting
make lint
# - black --check
# - isort --check-only
# - mypy (type checking)
# - flake8 (style checking)

# Full check (lint + test + examples)
make check
```

### Style Standards
- **Line length**: 88 (Black default)
- **Import sorting**: isort with Black profile
- **Type hints**: Required for public APIs
- **Docstrings**: Google-style format
- **Python version**: 3.8+ (use `typing.List` not `list` for 3.8 compat)

### Running Examples
```bash
# Individual examples
python examples/basic_example.py --name "Test" --count 5
python examples/cli_short_example.py -n MyApp -p 9000
python examples/cli_append_example.py docker  # NEW in v1.3.0
python examples/positional_example.py source.txt dest.txt

# All examples via Makefile
make examples
```

### CI/CD Pipeline
GitHub Actions workflows (`.github/workflows/`):
- **test.yml**: Cross-platform testing (Ubuntu, Windows, macOS) × Python 3.8-3.12
- **lint.yml**: Black, isort, flake8 checks
- **quality.yml**: mypy type checking, bandit security scan
- **examples.yml**: Validate all examples run successfully
- **release.yml**: Automated PyPI publishing on tag push
- **docs.yml**: Documentation generation/validation

## Common Development Tasks

### Adding a New Feature

1. **Design Phase**
   - Document in `local/` or `docs/research/`
   - Consider backward compatibility
   - Design API (annotations, functions, types)

2. **Implementation**
   - Add code to appropriate module (annotations.py, builder.py, etc.)
   - Update `__all__` exports in `__init__.py`
   - Add type hints and docstrings

3. **Testing**
   - Add test file: `tests/test_<feature>.py`
   - Aim for >90% coverage for new code
   - Include edge cases, error handling

4. **Documentation**
   - Update README.md with usage examples
   - Update CHANGELOG.md
   - Add example script in `examples/` if significant
   - Update API.md if needed

5. **Validation**
   ```bash
   make format  # Format code
   make lint    # Check style
   pytest       # Run tests
   make check   # Full validation
   ```

### Adding a New Annotation

Example from v1.3.0: Adding `cli_append()` annotation

1. **Define in annotations.py**:
   ```python
   def cli_append(nargs: Optional[Any] = None, **kwargs) -> Any:
       """Mark field for append action - allows repeating the option."""
       field_kwargs = kwargs.copy()
       metadata = field_kwargs.pop("metadata", {})
       metadata["cli_append"] = True
       if nargs is not None:
           metadata["cli_append_nargs"] = nargs
       field_kwargs["metadata"] = metadata
       return field(**field_kwargs)
   
   def is_cli_append(field_info: Dict[str, Any]) -> bool:
       """Check if field uses append action."""
       field_obj = field_info.get("field_obj")
       if field_obj and hasattr(field_obj, "metadata"):
           return field_obj.metadata.get("cli_append", False)
       return False
   
   def get_cli_append_nargs(field_info: Dict[str, Any]) -> Optional[Any]:
       """Get nargs value for append argument."""
       field_obj = field_info.get("field_obj")
       if field_obj and hasattr(field_obj, "metadata"):
           return field_obj.metadata.get("cli_append_nargs")
       return None
   ```

2. **Export in __init__.py**:
   ```python
   from .annotations import cli_append, is_cli_append, get_cli_append_nargs
   __all__ = [..., "cli_append", "is_cli_append", "get_cli_append_nargs"]
   ```

3. **Use in builder.py**:
   ```python
   from .annotations import is_cli_append, get_cli_append_nargs
   
   def _add_field_argument(self, parser, field_name, info):
       if is_cli_append(info):
           self._add_append_argument(parser, arg_names, info, help_text, choices)
           return
       # ... rest of logic
   
   def _add_append_argument(self, parser, arg_names, info, help_text, choices):
       append_nargs = get_cli_append_nargs(info)
       # Get element type for List[T] or List[List[T]]
       # ... type detection logic
       kwargs = {
           "action": "append",
           "type": arg_type,
           "help": help_text + " (can be repeated)",
       }
       if append_nargs is not None:
           kwargs["nargs"] = append_nargs
       parser.add_argument(*arg_names, **kwargs)
   ```

4. **Add tests** in `tests/test_cli_append.py` (32 tests added)

5. **Document** in README.md, API.md, and add example

### Debugging Tips

1. **Test Isolation**: Run single test with `-v` for details
   ```bash
   pytest tests/test_cli_append.py::TestBasicAppend::test_append_single_values -v
   ```

2. **Coverage Gaps**: Check HTML report
   ```bash
   make coverage-html
   # Opens htmlcov/index.html
   ```

3. **Type Issues**: Run mypy on specific file
   ```bash
   mypy dataclass_args/builder.py
   ```

4. **argparse Behavior**: Use `--debug` in examples, inspect `parser.parse_args()`

5. **Config Merging**: Add print statements in `_apply_*()` methods

6. **Append Behavior**: Check if `action='append'` is set in argparse args

## Important Constraints and Patterns

### Positional Arguments
**Critical Rule**: At most ONE positional can use `nargs='*'` or `'+'`, and it MUST be last.

**Why**: Positional lists are greedy - they consume all remaining arguments. Multiple greedy positionals or positionals after a list create ambiguous CLIs that argparse cannot parse.

**Validation**: `_validate_positional_arguments()` enforces this at build time.

**Workaround**: Use optional arguments with flags for additional lists:
```python
files: List[str] = cli_positional(nargs='+')      # OK: positional list
exclude: List[str] = cli_short('e', default_factory=list)  # OK: optional list
```

### Repeatable Options (cli_append)
**New in v1.3.0**: Use `cli_append()` for options that should accumulate when repeated.

**Pattern**: Each occurrence of the flag collects its own arguments:
```python
files: List[List[str]] = combine_annotations(
    cli_short('f'),
    cli_append(nargs=2),  # Each -f takes 2 args
    default_factory=list
)
# CLI: -f file1 mime1 -f file2 mime2
# Result: [['file1', 'mime1'], ['file2', 'mime2']]
```

**Important**: Always use `default_factory=list`, not `default=[]`

**Comparison with regular List**:
- Regular `List[str]`: `-f a b c` → all values after single flag
- `cli_append()`: `-f a -f b -f c` → repeated flag accumulates

### Boolean Fields and base_configs
**Fixed in v1.2.2**: Boolean values from `base_configs` now work correctly.

**Implementation**: Uses `argparse.SUPPRESS` instead of `set_defaults()` to preserve config hierarchy:
- Unspecified CLI flags → preserve `base_configs` value
- Specified CLI flags → override `base_configs` value

### Type Compatibility
**Python 3.8 Support**: Use `typing.List` not `list` for type hints.
```python
# Correct (3.8+)
from typing import List
files: List[str]

# Wrong (3.9+ only)
files: list[str]
```

### Metadata Access
Always check field metadata exists:
```python
field_obj = info.get("field_obj")
if field_obj and hasattr(field_obj, "metadata"):
    value = field_obj.metadata.get("key", default)
```

## Version History and Compatibility

### v1.3.0 (2024-12-XX) - Current
- **Added**: Repeatable options with `cli_append(nargs=None)`
- Enables Docker-style CLIs: `-p 8080 80 -p 8443 443`
- Supports variable args per occurrence: `-f file mime -f file`
- 306 tests, 92.96% coverage
- 32 new tests, all backward compatible

### v1.2.2 (2024-11-20)
- **Fixed**: Boolean fields from base_configs now work correctly
- 274 tests, 93.89% coverage
- All backward compatible

### v1.2.1 (2024-11-18)
- **Added**: Optional `description` parameter for custom help text
- 252 tests, 93.90% coverage

### v1.2.0 (2024-11-12)
- **Added**: Enhanced `base_configs` with file/dict/list support
- Configuration merging with clear precedence
- 234 tests, 94.15% coverage

### v1.1.0 (2024-11-02)
- **Removed**: Unused `exclude_fields`, `field_filter` parameters
- API simplification (80% surface area reduction)
- 224 tests, 94.29% coverage

### v1.0.1 (2024-11-02)
- **Added**: Home directory expansion for file loading (`~/`)
- 234 tests, 94.35% coverage

### v1.0.0 (2024-01-31) - First Stable Release
- Complete feature set stabilized
- 216 tests, ~92% coverage
- API frozen (semantic versioning from this point)

**Migration**: No breaking changes since 1.0.0. All 1.x versions are backward compatible.

## Dependencies

### Core (Required)
- `typing-extensions>=4.0.0` - Backport of typing features for Python 3.8

### Optional
- **YAML support**: `PyYAML>=6.0` - Install with `pip install "dataclass-args[yaml]"`
- **TOML support**: `tomli>=2.0.0` (Python <3.11) - Install with `pip install "dataclass-args[toml]"`
- **All formats**: `pip install "dataclass-args[all]"`

### Development Only
- `pytest>=7.0.0`, `pytest-cov>=4.0.0` - Testing
- `black>=23.0.0`, `isort>=5.12.0` - Formatting
- `mypy>=1.0.0` - Type checking
- `flake8>=6.0.0` - Linting
- `pre-commit>=3.0.0` - Git hooks
- `bandit>=1.7.0` - Security scanning

## Common Pitfalls and Solutions

### 1. Import Errors
**Problem**: `ModuleNotFoundError: No module named 'dataclass_args'`
**Solution**: Install in development mode: `pip install -e .`

### 2. Coverage Not Running
**Problem**: Tests pass but no coverage report
**Solution**: Coverage is automatic via `pyproject.toml`. Use `make coverage` for details.

### 3. Positional List Error
**Problem**: `ConfigBuilderError: Positional list argument must be last`
**Solution**: Make later arguments optional with flags, or use only one positional list.

### 4. Boolean Not Overriding
**Problem**: Boolean from base_configs doesn't apply
**Solution**: Fixed in v1.2.2. Upgrade: `pip install --upgrade dataclass-args`

### 5. Type Checking Failures
**Problem**: mypy errors with `List[str]`
**Solution**: Import from `typing`: `from typing import List`

### 6. Tests Fail on Windows
**Problem**: Path separator issues
**Solution**: Use `Path` from `pathlib` for cross-platform paths

### 7. Append Not Accumulating (NEW)
**Problem**: Multiple `-f` flags, only last one kept
**Solution**: Use `cli_append()` instead of regular `List[T]` field

### 8. Append with Wrong Type (NEW)
**Problem**: `List[str]` with `cli_append(nargs=2)` causes type mismatch
**Solution**: Use `List[List[str]]` when `nargs` takes multiple arguments

## Quick Reference

### Most Used Commands
```bash
pytest                          # Run tests
make coverage                   # Coverage report
make format                     # Format code
make lint                       # Check style
make check                      # Full validation
python examples/<name>.py       # Run example
```

### Key Files to Modify
- **New feature**: Start with `dataclass_args/annotations.py` or `builder.py`
- **New test**: Add `tests/test_<feature>.py`
- **Documentation**: Update `README.md`, `CHANGELOG.md`, `API.md`
- **Example**: Add `examples/<feature>_example.py`

### Common Annotations
```python
# Short option
name: str = cli_short('n')

# Choices
env: str = cli_choices(['dev', 'staging', 'prod'])

# Positional
source: str = cli_positional()

# Repeatable (NEW)
tags: List[str] = cli_append(default_factory=list)

# Repeatable with pairs (NEW)
ports: List[List[str]] = combine_annotations(
    cli_short('p'),
    cli_append(nargs=2),
    default_factory=list
)

# Combined
region: str = combine_annotations(
    cli_short('r'),
    cli_choices(['us-east', 'us-west']),
    cli_help("AWS region"),
    default='us-east'
)
```

### Code Review Checklist
- [ ] Type hints on all public functions
- [ ] Docstrings in Google style
- [ ] Tests added (>90% coverage)
- [ ] `make format` run
- [ ] `make lint` passes
- [ ] `make check` passes
- [ ] CHANGELOG.md updated
- [ ] README.md updated (if user-facing)
- [ ] API.md updated (for new API)
- [ ] Example added (if significant feature)
- [ ] Backward compatible (or documented breaking change)

## Getting Help

- **Documentation**: Start with README.md and API.md
- **Examples**: Check `examples/` directory for working code
- **Tests**: Look at `tests/` for usage patterns
- **Issues**: Search GitHub issues for similar problems
- **Research**: Check `docs/research/` for implementation notes
- **Local docs**: Check `local/` for session-specific documentation

## Future Development Areas

### Potential Enhancements
1. **Validation**: Integration with pydantic for advanced validation
2. **Subcommands**: Support for Click-style command groups
3. **Shell Completion**: Bash/zsh autocomplete generation
4. **Config Formats**: Support for additional formats (INI, XML)
5. **IDE Integration**: Language server protocol support
6. **Performance**: Lazy field analysis, caching
7. **Auto-detection**: Automatic `default_factory=list` for append fields

### Maintenance Priorities
1. **Compatibility**: Maintain Python 3.8+ support until EOL
2. **Stability**: No breaking changes in 1.x series
3. **Quality**: Keep test coverage >90%
4. **Documentation**: Keep examples and docs current
5. **Security**: Regular dependency updates, security scans

---

**Last Updated**: 2024-12-XX
**Bootstrap Version**: 1.1
**For**: dataclass-args v1.3.0
**Status**: Release ready, pending git commit
