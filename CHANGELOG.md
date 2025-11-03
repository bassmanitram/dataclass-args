# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).


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

---

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

---

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

[Unreleased]: https://github.com/bassmanitram/dataclass-args/compare/v1.1.0...HEAD
[1.1.0]: https://github.com/bassmanitram/dataclass-args/releases/tag/v1.1.0
[1.0.1]: https://github.com/bassmanitram/dataclass-args/releases/tag/v1.0.1
[1.0.0]: https://github.com/bassmanitram/dataclass-args/releases/tag/v1.0.0
[0.1.0]: https://github.com/bassmanitram/dataclass-args/releases/tag/v0.1.0
