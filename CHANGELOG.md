# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).


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

[Unreleased]: https://github.com/bassmanitram/dataclass-args/compare/v1.0.1...HEAD
[1.0.1]: https://github.com/bassmanitram/dataclass-args/releases/tag/v1.0.1
[1.0.0]: https://github.com/bassmanitram/dataclass-args/releases/tag/v1.0.0
[0.1.0]: https://github.com/bassmanitram/dataclass-args/releases/tag/v0.1.0
