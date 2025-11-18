## [1.2.1] - 2025-11-18

### Added
- **Optional `description` parameter** for custom ArgumentParser help text
  - `GenericConfigBuilder.__init__()` now accepts optional `description` parameter
  - `build_config()` and `build_config_from_cli()` accept optional `description` parameter
  - Allows customization of help text instead of generic "Build {ClassName} from CLI" format
  - Example: `build_config(ServerConfig, description="Server configuration management tool")`
- New test suite: `tests/test_description.py` with 18 tests covering the description parameter
- New example: `examples/custom_description_example.py` demonstrating custom descriptions

### Changed
- ArgumentParser description now uses custom text if provided, falls back to default format
- Updated docstrings for `GenericConfigBuilder`, `build_config()`, and `build_config_from_cli()`

### Fixed
- None (backward compatible enhancement)

### Quality
- All 252 tests passing (234 existing + 18 new)
- Test coverage: 93.90%
- 100% backward compatible - no breaking changes
- Python 3.8+ compatible (uses `typing.List` for compatibility)


## [1.2.0] - 2025-11-12

### Added
- **Enhanced `base_configs` parameter** for flexible programmatic configuration merging
  - Accepts single config file path (`str`): `base_configs='defaults.yaml'`
  - Accepts single configuration dictionary (`dict`): `base_configs={'debug': True}`
  - Accepts list mixing files and dicts (`List[Union[str, dict]]`): `base_configs=['base.yaml', {'env': 'prod'}, 'overrides.json']`
  - Files in `base_configs` are automatically loaded
  - Applied before `--config` file and CLI arguments in clear hierarchical order
- Crystal clear four-stage configuration merge process:
  1. Programmatic `base_configs` (if provided) - applied sequentially
  2. Config file from `--config` CLI argument (if provided)
  3. CLI argument overrides (highest priority)
  4. Dataclass instantiation
- Comprehensive error messages with context (e.g., list indices for failed file loads)
- New test suite: `tests/test_config_merging_simple.py` with 10 tests covering core functionality
- Example script: `examples/config_merging_example.py` demonstrating multi-source configuration

### Changed
- Refactored `GenericConfigBuilder.build_config()` into distinct stages for clarity
- Enhanced `build_config()` and `build_config_from_cli()` to accept `base_configs` parameter
- Improved internal code organization with dedicated methods:
  - `_normalize_base_configs()` - Converts any input format to List[Dict]
  - `_apply_base_configs()` - Merges base configs sequentially
  - `_apply_config_file()` - Loads and merges --config file
  - `_apply_cli_overrides()` - Applies CLI argument overrides
- Updated error message for config file loading to be more specific

### Fixed
- None (backward compatible enhancement)

### Notes
- **Known Limitation**: Boolean fields with defaults may not merge correctly from `base_configs` when no CLI flag is provided for that field. This is due to argparse's `set_defaults()` behavior. Workaround: explicitly provide boolean flags on CLI when using `base_configs` with booleans. See `local/KNOWN_LIMITATION.md` for details.

### Quality
- All 234 tests passing (224 existing + 10 new)
- Test coverage: 94.15%
- Backward compatible - no breaking changes


## [1.1.0] - 2024-11-02

### Removed
- Removed unused `exclude_fields`, `include_fields`, `field_filter`, and `use_annotations` parameters from `GenericConfigBuilder.__init__()` and `build_config_from_cli()`
  - These were rarely-used internal parameters intended for edge cases
  - The annotation-based approach using `cli_exclude()` has always been the recommended and documented method
  - No known usage in production code based on usage analysis
  - `use_annotations` parameter allowed runtime override of annotations, creating confusing dual-control mechanism
- Removed `exclude_internal_fields()` utility function
  - Was an example function for the deprecated `field_filter` parameter
  - No usage in production code
  - Its use case is now handled by `cli_exclude()` annotation

### Changed
- Simplified `GenericConfigBuilder` API from 5 parameters to 1 (`config_class` only)
- Simplified `build_config_from_cli` by removing `use_annotations` parameter
- Field filtering now exclusively uses `cli_exclude()` annotations - no runtime overrides
- Reduced API surface area by 80% for improved clarity

### Migration (if needed)
If you were using these parameters, switch to `cli_exclude()` annotations:

**Before:**
```python
builder = GenericConfigBuilder(MyConfig, exclude_fields={'secret'})
# or
builder = GenericConfigBuilder(MyConfig, use_annotations=False)
# or
builder = GenericConfigBuilder(MyConfig, field_filter=exclude_internal_fields)
```

**After:**
```python
@dataclass
class MyConfig:
    public: str
    secret: str = cli_exclude(default="")

builder = GenericConfigBuilder(MyConfig)
```

For third-party dataclasses, use inheritance:
```python
@dataclass
class MyConfig(ThirdPartyConfig):
    unwanted_field: str = cli_exclude()  # Override to exclude
```

If you need different field visibility for different contexts, use separate dataclasses:
```python
@dataclass
class PublicConfig:
    name: str
    value: str

@dataclass
class DebugConfig(PublicConfig):
    secret: str  # Include in debug version only
```

### Quality
- All 224 tests passing (removed 4 tests for deprecated function)
- Test coverage: 94.29%
- Removed 6 obsolete tests for deprecated parameters


## [1.0.1] - 2025-11-02

### Added
- **Home directory expansion** for file-loadable parameters
  - `@~/file.txt` now expands to user's home directory
  - `@~username/file.txt` expands to specified user's home directory
  - Supports all path types: `@~/path`, `@~user/path`, `@/absolute`, `@relative`

### Changed
- Updated `load_file_content()` to use `Path.expanduser()` for tilde expansion
- Enhanced documentation with path expansion examples

### Tests
- Added 4 new tests for tilde expansion functionality
- All 234 tests passing with 94.35% coverage


## [1.0.0] - 2025-01-31

### 🎉 First Stable Release

This is the first production-ready release of dataclass-args. The API is now stable and follows semantic versioning.

#### Core Features
- **Zero-boilerplate CLI generation** from Python dataclasses
- **Type-safe argument parsing** for all standard Python types (`str`, `int`, `float`, `bool`, `List`, `Dict`, `Optional`, etc.)
- **Positional arguments** - Support for positional args with `cli_positional()` annotation and all nargs variants
- **Short options** - Concise `-n` flags with `cli_short()` annotation
- **Boolean flags** - Proper `--flag` and `--no-flag` boolean handling
- **Value validation** - Restrict values with `cli_choices()` annotation
- **File loading** - Load string parameters from files using `@filename` syntax
- **Config file merging** - Combine configuration files (JSON, YAML, TOML) with CLI overrides
- **Hierarchical overrides** - Override nested dictionary properties with `--dict property:value` syntax
- **Flexible annotations** - Combine multiple features with `combine_annotations()`
- **Custom help text** - Add descriptions with `cli_help()` annotation
- **Field control** - Exclude/include fields with `cli_exclude()` and `cli_include()`
- **Positional list validation** - Enforces constraints to prevent ambiguous CLIs

#### Quality Metrics
- **Test Coverage**: ~92% code coverage across comprehensive test suite
- **Test Files**: 10 test modules with extensive unit and integration tests (216 total tests)
- **Code Quality**: All linting, type checking, and security scans passing
- **Python Support**: Python 3.8, 3.9, 3.10, 3.11, 3.12
- **Dependencies**: Minimal - only `typing-extensions` required
- **Optional Dependencies**: PyYAML for YAML, tomli for TOML (Python <3.11)

#### API Stability
- **Public API**: Stable and follows semantic versioning from this release
- **Breaking Changes**: None planned for 1.x series
- **Deprecations**: None at this time

#### Documentation
- Comprehensive README with examples
- API reference documentation
- Contributing guide
- Multiple working examples in `examples/` directory
- Full docstring coverage

#### What's Next
- Future 1.x releases will be backward compatible
- New features will be added in minor version bumps (1.1.0, 1.2.0, etc.)
- Bug fixes will be in patch releases (1.0.1, 1.0.2, etc.)

### Migration from 0.x
No migration needed - this is the initial stable release.


## [0.1.0] - 2025-01-30

### Added
- Initial development release
- Core CLI generation functionality
- Type-safe argument parsing
- File loading support with `@filename` syntax
- Configuration file merging (JSON, YAML, TOML)
- Field annotations: `cli_help()`, `cli_exclude()`, `cli_file_loadable()`, `cli_include()`
- Short options with `cli_short()` annotation
- Boolean flags with `--flag` and `--no-flag` support
- Value choices with `cli_choices()` annotation
- Annotation combination with `combine_annotations()`
- Advanced type support: `List`, `Dict`, `Optional`, custom types
- Comprehensive test suite
- Documentation and examples

[Unreleased]: https://github.com/bassmanitram/dataclass-args/compare/v1.2.1...HEAD
[1.2.1]: https://github.com/bassmanitram/dataclass-args/compare/v1.2.0...v1.2.1
[1.2.0]: https://github.com/bassmanitram/dataclass-args/compare/v1.1.0...v1.2.0
[1.1.0]: https://github.com/bassmanitram/dataclass-args/releases/tag/v1.1.0
[1.0.1]: https://github.com/bassmanitram/dataclass-args/releases/tag/v1.0.1
[1.0.0]: https://github.com/bassmanitram/dataclass-args/releases/tag/v1.0.0
[0.1.0]: https://github.com/bassmanitram/dataclass-args/releases/tag/v0.1.0
