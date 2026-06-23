
All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.5.0] - 2026-06-23

### Added
- **Post-Load Field Resolution with `cli_resolve()`** - Transform config values into typed objects
  - New annotation `cli_resolve(resolver=callable)` marks fields for post-load transformation
  - After all config assembly (base_configs → config file → CLI), resolver transforms raw value
  - None bypass: resolver never called when value is None (natural Optional semantics)
  - Error handling: resolver exceptions wrapped in `ConfigurationError` with field context
  - Pipeline position: Stage 3.8 (after nested reconstruction, before dataclass creation)
  - **Dict fields** (default mode for non-list types):
    - Field treated as dict-loadable during parsing (file paths + property overrides)
    - Resolver receives assembled dict, returns typed object
    - Property override protection: raises error for overrides on pre-built (non-dict) objects
  - **List fields** (automatic for List-typed fields):
    - Field retains natural list parsing behavior (`nargs` semantics)
    - Resolver receives the assembled list (not individual elements)
    - Enables patterns like: accept glob patterns from CLI, expand and resolve in resolver
    - Example: `files: List[Any] = cli_resolve(resolver=expand_and_load, default_factory=list)`
  - **Nested dataclass support**:
    - `cli_resolve` fields inside nested dataclasses are accepted (no error)
    - Resolver is NOT called by the library for nested fields (value stays raw)
    - Application can call resolvers explicitly post-construction
    - Enables dataclasses with `cli_resolve` fields to be reused via `cli_nested()`
  - Compatible with: `cli_help`, `cli_short`, `cli_choices`, `combine_annotations`
  - Incompatible with: `cli_positional`, `cli_nested` (same field), `cli_append`, `cli_exclude`, `cli_file_loadable`
  - Incompatibility validation at init time (fail-fast)

### Examples
- New example: `examples/cli_resolve_example.py` - Post-load field resolution demonstration
  - DockerSandbox and LocalSandbox factory pattern
  - Config file loading with resolution
  - Property overrides before resolution
  - Pre-built object pass-through
  - List field resolution

### Tests
- Added 51 comprehensive tests in `tests/test_cli_resolve.py`
  - TestBasicResolve - Dict → object, None bypass, resolver always called
  - TestConfigFileLoading - File path loading, --config integration
  - TestPropertyOverrides - Overrides before resolution, non-dict protection
  - TestPreBuiltObjects - Pass-through, CLI override of pre-built
  - TestErrorHandling - Error wrapping, ConfigurationError pass-through, invalid resolver
  - TestCombineAnnotations - cli_help, cli_short, combined
  - TestOptionalAndRequired - Optional with None, base_configs provided
  - TestIncompatibleAnnotations - All incompatible combinations + multiple
  - TestNestedDataclassSupport - Accepted in nested, resolver not called, raw value preserved
  - TestMetadataAccessors - is_cli_resolve, get_cli_resolver
  - TestBuildConfigHelperFunction - End-to-end integration
  - TestMultipleResolveFields - Two resolve fields, independent None bypass
  - TestConfigMergingWithResolve - Precedence testing
  - TestEdgeCases - Empty dict, resolver returns None, different types
  - TestListFieldResolve - List from CLI, base_configs, pre-built objects, empty list, errors
- All 480 tests passing (429 existing + 51 new)
- Coverage: 92.92% (up from 92.24%)

### Quality
- 100% backward compatible - no breaking changes
- All existing functionality preserved
- No regressions in existing tests
- Clean separation of concerns: library provides hook, caller provides logic

### Documentation
- Updated README.md with "Field Resolution" section (dict and list modes)
- Updated docs/API.md with `cli_resolve()` API reference
- Updated AGENT_BOOTSTRAP.md with new feature details
- Complete example with real-world factory pattern

### Migration
No migration required. This is a purely additive feature.

## [1.4.3] - 2025-12-18

### Fixed
- **Nested field help text** - Nested fields with prefix now show descriptive help text
  - Before: `--a2a-name A2A_NAME    nested field` (generic, unhelpful)
  - After: `--a2a-name A2A_NAME    agent.name` (clear context)
  - Help text now shows `parent.field` format for better UX
  - Improves discoverability and reduces confusion
  - Custom help text still takes precedence via `cli_help()`

### Added
- **New test suite** - `tests/test_nested_help_text.py` (5 tests)
  - Verifies parent.field format in help text
  - Tests custom help text override behavior
  - Tests empty prefix behavior
  - Tests multiple nested dataclasses
  - All backward compatibility scenarios covered

### Quality
- Total tests: 424 → 429 (+5)
- Coverage: 92.19% maintained
- All CI checks passing
- 100% backward compatible


## [1.4.2] - 2025-12-16

### Changed
- **Code quality improvements and refactoring**
  - Removed unnecessary delegation stubs in builder.py (-34 lines)
  - Made ConfigApplicator method visibility consistent (public API cleanup)
  - Extracted ConfigApplicator class for config application logic
  - Extracted NestedFieldProcessor class for nested dataclass handling
  - Builder.py reduced from 1272 to 1238 lines while maintaining all functionality

### Added
- **Comprehensive test coverage improvements**
  - Added 70 new tests (354 → 424 total tests)
  - Added TypeInspector test suite (30 tests, coverage 51% → 86%)
  - Added ConfigApplicator test suite (36 tests, coverage 78% → 100%)
  - Added collision detection tests (11 tests for nested fields)
  - Overall test coverage: 88.84% → 92.19%

### Quality
- All 424 tests passing
- Test execution time: ~0.65s
- Better code organization and maintainability
- 100% backward compatible - no breaking changes
- Production-ready quality (Grade: A)

### Architecture
- ConfigApplicator: Handles configuration merging and property overrides
- NestedFieldProcessor: Handles nested dataclass flattening and reconstruction
- TypeInspector: Type analysis utilities (already existed, now fully tested)
- Cleaner separation of concerns, easier to maintain and extend

### Migration
No migration required. All changes are internal refactoring with full backward compatibility.


## [1.4.1] - 2025-12-12

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

### Tests
- Added 7 new tests in `tests/test_nested_dict_override.py`
- All 348 tests passing (341 existing + 7 new)

### Quality
- 100% backward compatible - no breaking changes
- Minimal code change (25 lines in `builder.py`)
- All existing functionality preserved


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

### Tests
- Added 32 comprehensive tests in `tests/test_cli_append.py`
- All 306 tests passing (274 existing + 32 new)
- Test coverage: 92.96%

### Quality
- 100% backward compatible - no breaking changes
- All existing functionality preserved
- No regressions in existing tests


## [1.2.2] - 2025-11-20

### Fixed
- **Boolean fields from base_configs now work correctly**
  - Fixed critical bug where boolean values from `base_configs` dict/files were always ignored
  - Boolean fields now properly respect configuration hierarchy: `base_configs` < `--config` < CLI
  - Technical: Changed `_add_boolean_argument()` to use `argparse.SUPPRESS` instead of `parser.set_defaults()`

### Quality
- All 274 tests passing (252 existing + 22 new)
- Test coverage: 93.89%
- 100% backward compatible


## [1.2.1] - 2025-11-18

### Added
- **Optional `description` parameter** for custom ArgumentParser help text
  - `build_config()` and `build_config_from_cli()` accept optional `description` parameter

### Quality
- All 252 tests passing (234 existing + 18 new)
- 100% backward compatible


## [1.2.0] - 2025-11-12

### Added
- **Enhanced `base_configs` parameter** with comprehensive support for multiple configuration sources
  - Single file path: `base_configs='defaults.yaml'`
  - Single dict: `base_configs={'debug': True}`
  - List of mixed sources: `base_configs=['base.yaml', {'env': 'prod'}, 'overrides.json']`

### Changed
- **Improved configuration merge hierarchy** with clear precedence:
  1. Programmatic `base_configs` (lowest priority)
  2. Config file from `--config` argument
  3. CLI argument overrides (highest priority)

### Known Limitations
- Boolean values from `base_configs` dict may not apply correctly in all cases (fixed in 1.2.2)


## [1.1.0] - 2025-11-03

### Removed
- **Simplified API** - Removed unused optional parameters from core functions
  - Field exclusion is now exclusively done via `cli_exclude()` annotation


## [1.0.1] - 2025-11-02

### Added
- **Home directory expansion for file loading** (`@~/file.txt`, `@~alice/file.txt`)


## [1.0.0] - 2025-11-01

### First Stable Release
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
- Cross-platform support (Linux, macOS, Windows)
- Python 3.8+ support
