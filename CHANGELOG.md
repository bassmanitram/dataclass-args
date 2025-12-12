## [Unreleased]

### Added
- **Property override support for dict fields in nested dataclasses**
  - Dict fields inside nested dataclasses now get override arguments
  - Override argument format: `--prefix-abbreviation key.path:value`
  - Examples:
    - `model_config: Dict[str, Any]` in nested field with `prefix="agent-"` → `--agent-mc temperature:0.9`
    - Same with `prefix=""` → `--mc temperature:0.9`
  - Supports dotted path notation: `--agent-mc nested.key.path:value`
  - Fully compatible with auto-prefix mode
  - Enables CLI override of nested dict fields without full file replacement

### Examples
- New test script: `local/test_dict_override_in_nested.py` - Functional demonstration

### Tests
- Added 7 new tests in `tests/test_nested_dict_override.py`
  - Override argument generation with prefix
  - Override argument generation without prefix  
  - Override parsing with prefix
  - Override parsing without prefix
  - Help text verification
  - Multiple dict fields
  - Auto-prefix support
- All 348 tests passing (341 existing + 7 new)

### Quality
- 100% backward compatible - no breaking changes
- Minimal code change (25 lines in `builder.py`)
- All existing functionality preserved

# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.4.0] - 2025-12-12

### Added
- **Nested Dataclasses with `cli_nested()`** - Organize complex configurations hierarchically
  - Automatic flattening of nested dataclass fields into CLI arguments
  - Three prefix modes:
    - Custom prefix: `prefix="db"` → `--db-host`, `--db-port`
    - No prefix: `prefix=""` → `--host`, `--port` (complete flattening)
    - Auto prefix: `prefix=None` → `--database-host` (uses field name)
  - Short options support:
    - With prefix: Short options ignored (prevents conflicts)
    - Without prefix: Short options enabled (like regular fields)
  - Automatic collision detection:
    - Field name collisions detected at initialization
    - Short option collisions detected at initialization
    - Clear error messages with actionable solutions
  - Full integration:
    - Works with all field types (scalars, lists, dicts, booleans, optionals)
    - Compatible with all annotations (cli_help, cli_choices, cli_short, etc.)
    - Config file merging with partial overrides
    - Preserves non-specified nested field values
  - Real-world use cases: Database configs, logging configs, service endpoints, credentials

### Examples
- New example: `examples/nested_dataclass.py` - Basic nested configuration
- New example: `examples/nested_short_options.py` - Short options with nested fields

### Tests
- Added 24 comprehensive tests in `tests/test_cli_nested.py`
  - TestBasicNested - Three prefix modes, partial overrides, multiple nested
  - TestCollisionDetection - Field name and cross-nested collisions
  - TestShortOptions - Short options with/without prefix, collision detection
  - TestConfigFileMerging - Base config, CLI overrides, programmatic configs
  - TestFieldTypes - Lists, booleans, optionals in nested fields
  - TestIntegrationWithOtherAnnotations - cli_help, cli_choices, combine_annotations
  - TestEdgeCases - Empty dataclasses, defaults only, positional args errors
  - TestBuildConfigHelperFunction - Integration testing
- All 338 tests passing (314 existing + 24 new)
- Test coverage maintained

### Quality
- 100% backward compatible - no breaking changes
- All existing functionality preserved
- No regressions in existing tests
- Clear documentation with examples

### Documentation
- Updated README.md with "Nested Dataclasses" section
- Updated docs/API.md with `cli_nested()` API reference
- Complete examples with real-world scenarios
- Clear explanation of prefix modes and short option behavior

## [1.3.0] - 2025-12-04

### Added
- **Repeatable Options with `cli_append()`** - New annotation for options that can be specified multiple times
  - Each occurrence of the option accumulates into a list
  - Supports `nargs` parameter for multi-argument occurrences
  - `cli_append()` - Single value per occurrence → `List[T]`
  - `cli_append(nargs=2)` - Exact count per occurrence → `List[List[T]]`
  - `cli_append(nargs='+')` - Variable args (1+) per occurrence → `List[List[T]]`
  - Enables CLI patterns like: `-f file1 mime1 -f file2 -f file3 mime3`
  - Compatible with `combine_annotations()`, `cli_short()`, `cli_choices()`, `cli_help()`
  - Real-world use cases: Docker-style options, file uploads, environment variables, server pools

### Examples
- New example: `examples/cli_append_example.py` with 5 practical scenarios
  - Docker-style configuration (-p HOST CONTAINER, -v SOURCE TARGET, -e KEY VALUE)
  - File uploads with optional MIME types
  - Environment variable KEY VALUE pairs
  - Simple tag collection
  - Server pool HOST PORT pairs

### Tests
- Added 32 comprehensive tests in `tests/test_cli_append.py`
  - TestBasicAppend - Basic functionality
  - TestAppendWithNargs - Various nargs values
  - TestAppendWithTypes - int, float, str types
  - TestAppendWithChoices - Combined with cli_choices()
  - TestAppendRealWorldExamples - Practical scenarios
  - TestAppendEdgeCases - Error conditions
  - TestAppendCombinedAnnotations - With other annotations
  - TestAppendValidation - Custom validation
  - TestAppendIntegration - Complex configurations
  - TestAppendHelp - Help text generation
  - TestAppendTyping - Type correctness
- All 306 tests passing (274 existing + 32 new)
- Test coverage: 92.96%

### Quality
- 100% backward compatible - no breaking changes
- All existing functionality preserved
- No regressions in existing tests

### Documentation
- Updated README.md with repeatable options section
- Added API reference for `cli_append()`
- Added usage examples and patterns
- Updated feature list


## [1.2.2] - 2024-11-20

### Fixed
- **Boolean fields from base_configs now work correctly**
  - Fixed critical bug where boolean values from `base_configs` dict/files were always ignored
  - Boolean fields now properly respect configuration hierarchy: `base_configs` < `--config` < CLI
  - CLI flags correctly override `base_configs`; unspecified flags preserve `base_configs` values
  - Technical: Changed `_add_boolean_argument()` to use `argparse.SUPPRESS` instead of `parser.set_defaults()`
  - This resolves the known limitation documented in v1.2.0
- Added 22 comprehensive tests in `tests/test_boolean_base_configs.py` covering all boolean scenarios

### Quality
- All 274 tests passing (252 existing + 22 new)
- Test coverage: 93.89%
- 100% backward compatible - no breaking changes

### Migration
No migration required. This fix only affects boolean fields used with `base_configs` parameter.
If you were working around this bug, you can now remove workarounds.


## [1.2.1] - 2024-11-18

### Added
- **Optional `description` parameter** for custom ArgumentParser help text
  - `GenericConfigBuilder.__init__()` now accepts optional `description` parameter
  - `build_config()` and `build_config_from_cli()` accept optional `description` parameter
  - Allows customization of help text instead of generic "Build {ClassName} from CLI" format
  - Example: `build_config(ServerConfig, description="Server configuration management tool")`
- New test suite: `tests/test_description.py` with 18 tests covering the description parameter

### Quality
- All 252 tests passing (234 existing + 18 new)
- Test coverage: 93.90%
- 100% backward compatible

### Migration
No migration required. This is an additive feature with no breaking changes.


## [1.2.0] - 2024-11-12

### Added
- **Enhanced `base_configs` parameter** with comprehensive support for multiple configuration sources
  - Single file path: `base_configs='defaults.yaml'`
  - Single dict: `base_configs={'debug': True}`
  - List of mixed sources: `base_configs=['base.yaml', {'env': 'prod'}, 'overrides.json']`
  - Files in list are loaded and applied sequentially
  - Dicts in list are applied directly
  - Enables flexible configuration composition and layering

### Changed
- **Improved configuration merge hierarchy** with clear precedence:
  1. Programmatic `base_configs` (lowest priority)
  2. Config file from `--config` argument
  3. CLI argument overrides (highest priority)
- Builder methods simplified:
  - `_normalize_base_configs()` - Normalize input to list of dicts
  - `_apply_base_configs()` - Sequential merge of base configs
  - `_apply_config_file()` - Merge --config file
  - `_apply_cli_overrides()` - Apply CLI args

### Tests
- Added 20 new tests in `tests/test_config_merging_simple.py`
- All 234 tests passing (214 existing + 20 new)
- Test coverage: 94.15%

### Migration
Fully backward compatible. Existing code using string or dict for `base_configs` continues to work.
The new list format is optional and additive.

### Known Limitations
- Boolean values from `base_configs` dict may not apply correctly in all cases (to be fixed in 1.2.2)


## [1.1.0] - 2024-11-02

### Removed
- **Simplified API** - Removed unused optional parameters from core functions:
  - Removed `exclude_fields` parameter from `build_config()` and `build_config_from_cli()`
  - Removed `field_filter` parameter from `GenericConfigBuilder.__init__()`
  - These parameters were never documented and added unnecessary complexity
  - Field exclusion is now exclusively done via `cli_exclude()` annotation
  - This change reduces API surface area by ~80% while maintaining all functionality

### Changed
- Streamlined builder initialization and configuration logic
- Improved code clarity and maintainability

### Quality
- All 224 tests passing
- Test coverage: 94.29%
- 100% backward compatible for documented features

### Migration
If you were using undocumented `exclude_fields` or `field_filter` parameters:
- Replace `exclude_fields=['field1', 'field2']` with `field1: str = cli_exclude()` annotation
- Replace `field_filter` callback with `cli_exclude()` on specific fields
- This provides more explicit and maintainable field exclusion


## [1.0.1] - 2024-11-02

### Added
- **Home directory expansion for file loading**
  - `@~/file.txt` expands to user's home directory
  - `@~alice/file.txt` expands to alice's home directory
  - Applies to all file-loadable fields marked with `cli_file_loadable()`

### Tests
- Added 10 new tests in `tests/test_file_loading.py`
- All 234 tests passing (224 existing + 10 new)
- Test coverage: 94.35%

### Migration
No migration required. This is an additive feature.


## [1.0.0] - 2024-01-31

### First Stable Release

This release marks the 1.0 stable version with a complete, tested, and documented feature set.

### Features
- Automatic CLI generation from dataclass definitions
- Type-safe argument parsing for standard Python types
- Short-form options with `cli_short()`
- Boolean flags with `--flag` and `--no-flag` forms
- Value validation with `cli_choices()`
- File-loadable parameters with `@filename` syntax
- Positional arguments with `cli_positional()`
- Configuration file merging with hierarchical overrides
- Support for `List`, `Dict`, `Optional`, and custom types
- Custom help text and field exclusion
- Comprehensive test coverage (>92%)

### Quality
- 216 tests passing
- Test coverage: ~92%
- Cross-platform support (Linux, macOS, Windows)
- Python 3.8+ support

### Documentation
- Complete README with examples
- API reference
- Multiple working examples
- Contributing guidelines

### Stability
- API is now frozen following semantic versioning
- No breaking changes in 1.x series
- Deprecated features will be maintained until 2.0
