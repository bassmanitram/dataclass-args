
All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).


## [1.10.1] - 2026-11-26

This release also includes the fixes from an independent QA review of the whole project.

### Changed (please read before upgrading)
- **A string given for a plain dict field is now either a file or an error, from every source.** This covers the command line (top level and nested), `base_configs`, `ConfigLayer`, `--config` values and `build_config_from_dict`.
  - The path of an **existing file** is loaded like a `--config` file, with the format detected from the content.
  - A missing `.json`/`.yaml`/`.yml`/`.toml` path is a "file not found" error.
  - Any other string raises `ConfigurationError`, naming the field (and the layer).

  Previously a non-file string was silently stored as a `str` in a `Dict` field, and existing files without a structured extension weren't loaded. Fields using `cli_resolve()` still receive other strings unchanged.
- `Optional[Union[A, B]]` now behaves exactly like `Union[A, B]`: the command-line value stays a string. Previously it was converted to `A` alone, so `Optional[Union[int, str]]` rejected `abc`. A union that includes a list follows the same rule.
- Fields declared with `field(init=False)` no longer get a command-line option. Setting one always crashed, because the constructor doesn't accept it.
- Booleans in **prefixed** nested dataclasses no longer get their `cli_short` option, as the README documents for every other field type. This also means one dataclass with a short-option boolean can be nested under two prefixes, which previously failed with a collision error.
- **Error message wording changed:**
  - a missing field is now "missing required field: 'name'" instead of Python's "missing 1 required positional argument";
  - `@file` errors no longer repeat their prefix;
  - invalid property overrides are reported as "Invalid override for 'field' (--option): …";
  - the `base_configs` type error lists `ConfigLayer`.

### Fixed
- **A field whose name starts with `_` silently ignored its command-line value** (`---count 7` left the default). Every argument is now registered with an explicit destination.
- **Two arguments sharing one Namespace attribute overwrote each other silently.** For example, a positional named `config` was read as the `--config` option, and an override name equal to a field name clashed with that field. This is now a `ConfigBuilderError`, naming both.
- **A malformed property-override key was stored silently instead of being rejected.** `--mc '{"temperature": 0.1}'` stored the key `'{"temperature"'`. Quoted keys, keys with spaces, `items[0]` and empty segments (`a..b`, `:1`) also created nonsense keys. Every key segment is now validated, and a malformed override raises `ConfigurationError` naming the field and option, and pointing at the field's file option for setting the whole dict. Valid forms are unchanged (`a.b`, `items.0`, `items.+`, colons in the value, hyphens and slashes in keys).
- A `%` in help text or in a choice crashed `--help`.
- A bare `list` annotation was treated as a single string.
- `~` wasn't expanded in config-file paths (`base_configs`, `--config` and dict-field files), although the README relied on it.
- A config file whose top level isn't a mapping gave a cryptic error, and a YAML `false` or `0` silently became `{}`. Both now give a clear error.
- A required boolean's help showed "(default: None)".
- Nested boolean help text now uses the dotted field path, like other nested fields.
- `cli_short('-')`, whitespace, and `cli_override_name()` with leading dashes are rejected at annotation time.
- Annotations no longer mutate a `metadata=` dict passed in by the caller. A read-only mapping such as `MappingProxyType` now works.
- `instantiate()`:
  - a non-string `_attr_`, and exceptions other than `ImportError` raised while importing a target module, are now wrapped in `InstantiationError`;
  - unreachable "annotation-guided" code was removed. Behaviour is unchanged, and the docs now describe the actual rule.
- **Repeated list flags silently dropped earlier values.** With a plain `List[T]` option, `-t a -t b` kept only `['b']`, while the help text ("specify one or more values") invited repeating the flag. The new opt-in **`cli_extend()`** annotation makes repeats accumulate into one flat list:
  - `-t a -t b` → `['a', 'b']`; `-t a b -t c` → `['a', 'b', 'c']`.
  - An omitted flag leaves earlier sources and the default untouched. A given flag replaces earlier sources as a whole, as list CLI values always have.
  - Works at any nesting depth. The help text gains "; repeatable".
  - Elements may be any scalar type, or a union or `Optional` of scalars (`List[Union[str, Path]]`, `list[str | Path]`). Element values are exactly what the plain option produces.
  - Raises `ConfigBuilderError` on a non-list field, on non-scalar elements (lists, tuples, sets, dicts, dataclasses; the message names the element type), or combined with `cli_append`, `cli_positional` or `cli_exclude`.
  - Fields without the annotation are unchanged. The README now documents that a repeated plain list flag keeps only its last occurrence.
- **List option elements are converted to their declared type** (changed default behaviour). `List[int]`, `List[float]` and `Optional[List[int]]` options, at any nesting depth, used to return strings (`--n 1 2` → `['1', '2']`) and accepted invalid values. They now return typed values (`[1, 2]`), and an invalid element is a normal argparse error. Positional and `cli_append` lists already converted; all three paths now share one converter.
- `List[int]` with `cli_choices([1, 2, 3])` rejected every value, because the string `'1'` never equals `1`. It now works.

### Documentation
- Corrected wrong or stale statements across README, API.md, QUICKSTART.md and AGENT_BOOTSTRAP.md:
  - examples that passed keys their dataclass doesn't have;
  - signatures (`cli_nested`);
  - help-output samples (non-bool fields never show defaults; QUICKSTART's help block was regenerated from real output);
  - `metavar='X Y'`, which renders as `X Y X Y`;
  - TOML now being built in;
  - the exceptions `load_structured_file`, `FileLoadingError` and `ConfigurationError` actually raise;
  - `cli_include` being a marker with no effect;
  - `cli_choices` applying to command-line values only;
  - `instantiate()` resolution rules.
- New `FUTURE_CHANGES.md` records accepted changes deferred to a later release: hyphenating nested prefixes, converting `Path`/`Enum` values, and others.
- Corrected the type tables. `Path` and `Enum` CLI values are passed through **as strings**; the tables claimed `Path(...)` and `Enum` members. Converting them (consistently for CLI and config-file values) is planned for a future minor release.
- Added `cli_extend` to README and API.md, and listed it in the compatibility notes for `cli_resolve` and `cli_list_merge`.

### Development
- Removed the unused `[tool.flake8]` table from `pyproject.toml`; it contradicted `.flake8`, which is the only flake8 configuration flake8 reads.

### Tests
- 1376 tests (up from 1234), with 97.68% coverage, on Python 3.11–3.14.
- Existing tests changed: two tests and one test class renamed to neutral names; tests that pinned a behaviour fixed above (dict-field strings, `Optional[Union]`, message wording) updated to the new behaviour; one test skipped when run as root (a mode-000 file is readable by root).

## [1.10.0] - 2026-11-24

### Breaking
- **Python 3.11+ is now required.** Support for 3.8, 3.9 and 3.10 (all end-of-life) is dropped. The supported and tested versions are 3.11, 3.12, 3.13 and 3.14.
- **The `typing-extensions` runtime dependency is removed.** The package has no runtime dependencies. If you relied on it being installed transitively, add it to your own requirements.
- The `toml` extra is now empty, because TOML support comes from the standard library (`tomllib`). `pip install "dataclass-args[toml]"` still works.

### Changed (default behaviour; please read before upgrading)
This release fixes many inconsistencies in how configuration sources are combined. Most of them lost data silently or crashed. Each change brings the code in line with the documented behaviour, or with what the CLI path already did.
- **Dicts merge one level deep at every source boundary.** Previously, a dict value in a later `base_configs` entry or `--config` file **replaced** the earlier dict wholesale, which contradicted the README. Top-level keys now merge, as `--field file.json` already did. Nested dicts inside a key are still replaced; use the new `merge_strategy="deep"` to merge them too. Lists still replace, and `None` still clears.
- **Caller data is never mutated or shared.** `base_configs` dicts and lists, the `build_config_from_dict` config dict and dataclass instances you pass in are copied when they enter the pipeline. Property overrides and appends used to write into your objects, and the built instance used to hold your dict.
- **Property overrides edit the effective value.** `--mc key:value` and `items.+:x` now apply to the merged value, or to the dataclass default when no source set the field. Previously they started from `{}` and discarded non-empty defaults, nested base values and lists (`items.+` produced `{'+': x}`).
- **Nested dict fields behave like top-level ones.** `--db-opts file.json` merges one level onto the configured value instead of replacing it. A non-file string passes through instead of raising.
- **Dict-field file references are loaded when each layer enters the pipeline.** That includes the `--config` file and fields inside nested dataclasses. `base_configs={"db": "db.yaml"}` plus `--d port:5` used to crash, and file paths inside nested dataclasses were never loaded.
- **Invalid values for `cli_nested` fields raise `ConfigurationError`.** A string or number given for a nested dataclass field used to be silently discarded, falling back to the defaults.
- **A dataclass instance in a layer combines like its field dict.** A later dict layer used to wipe the instance's values back to class defaults. Values that `__post_init__` computes, or that `init=False` fields hold, are recomputed when the instance is rebuilt.
- **An explicit `None` passed to `build_config_from_dict` clears the value.** It used to be silently ignored.
- **Hyphenated field names (`db-host`) are accepted in every layer**, not just in `build_config_from_dict`. Keys inside dict-field values are never renamed. If one layer sets both spellings, that's an error.
- **`cli_append` fields and optional positionals (`nargs="?"`/`"*"`) can be set from `base_configs` and `--config`.** The argparse default used to silently win.
- **`build_config_from_dict` never exits the process.** A required positional field used to make it print usage and raise `SystemExit(2)`. It now behaves like any other required field: a missing value raises `ConfigurationError`.

### Added
- **Opt-in deep merge.** `merge_strategy="shallow"|"deep"` on `build_config`, `build_config_from_cli`, `build_config_from_dict` and `GenericConfigBuilder.build_config`. The public `deep_merge(base, override)` utility and the `MERGE_SHALLOW` / `MERGE_DEEP` constants are exported.
- **Named layers:** `ConfigLayer(data, name=None, list_merge="replace"|"rules")`. It's accepted wherever `base_configs` accepts a path or a dict.
- **Per-field list-merge rules:** the `cli_list_merge("append"|"append_unique", paths=None)` annotation. In `list_merge="rules"` layers, annotated list fields and dict paths append instead of replacing. `append_unique` de-duplicates by `==`, so unhashable elements work. Rules work at any nesting depth and on `cli_exclude` fields.
- **`build_config_from_dict(..., config_list_merge="replace"|"rules")`.** In deep mode the config dict is a single layer named `config`.
- **Provenance:** pass `return_provenance=True` (deep mode) to get `(instance, Provenance)`. `Provenance` provides `entries(path)`, `source(path)`, `paths()`, `changes()` (values a later layer discarded) and `explain()`. Also exported: `ProvenanceEntry`, `ProvenanceChange` and `MISSING_VALUE`.
- **`cli_nested` works at any depth.** A nested dataclass inside a nested dataclass is flattened recursively (`--mid-inner-v`) and rebuilt as real instances. It used to be exposed as one string option, or left as a raw dict. Collision checks, short-option rules and property overrides apply at every level, and an annotation cycle is rejected when the builder is constructed.
- **New examples:** `examples/deep_merge_example.py` and `examples/layered_config_example.py`.

### Fixed
- **Every option-name clash is now a clear `ConfigBuilderError`.** These used to crash with a raw `argparse.ArgumentError`:
  - a one-letter dict field (`d: Dict`), whose override `--d` equals its own option;
  - an override that equals another field's option (`mc` vs `model_config` → `--mc`);
  - a field named like the config-file option (`config`);
  - `cli_short('h')`, which clashes with `--help`.

  The error names the option string and every claimant, and suggests the fix (`cli_override_name`, another short letter, or a different `base_config_name`).
- For a boolean field with custom help, the negative flag's help read `Disable <help text>`, e.g. "Disable Enable debug mode". It now reads `Disable --debug`.
- `examples/cli_append_example.py` crashed (it used `cli_short("h")`).
- A `nargs="*"` positional with `cli_choices` exited with an error when no values were given.
- `make examples`, and therefore `make check`, never ran: the target wasn't `.PHONY`, and its commands passed invalid boolean flags. `make lint`/`make format` pointed at a non-existent `dataclass_config/` directory. Examples now run through `scripts/run_examples.sh`, shared with CI.
- Error messages for property overrides now name the offending field and its type. Dict-field load errors name the layer.

### Development
- All 16 example scripts now run in CI and `make examples` (several were never run, and one was broken).
- Cognitive complexity ≤ 10 per function is now **enforced** (`flake8-cognitive-complexity` in pre-commit and `.flake8`). Eight functions that exceeded it were refactored without changing behaviour.
- CI tests Python 3.11–3.14. Single-version jobs run on 3.12, and mypy checks against 3.11.

### Documentation
- README: corrected the "Merge Behavior by Type" table, which claimed dict merging that the code didn't do. Added sections on deep merge and layered configuration (layers, list rules, provenance), and documented that required positionals must be given on the command line.
- API.md and AGENT_BOOTSTRAP.md updated for all new names and parameters. AGENT_BOOTSTRAP's module map and navigation guide had been stale since the 1.8.1 refactor and now match the code.
- Fixed documentation defects:
  - API.md documented `prog`/`epilog` options for `build_config_from_cli` that don't exist;
  - API.md claimed `@file` loading doesn't work in `build_config_from_dict` (it does);
  - `cli_override_name` was missing from API.md;
  - an unclosed code fence in the README (`build_config_from_cli`) and one in API.md (`cli_resolve`) broke the rendering of every section after them;
  - an orphaned, heading-less README snippet is restored as "Config Files, Dict Files and Property Overrides Together";
  - stale pipeline stage numbers ("Stage 3.8") are corrected;
  - the README's first Short Options example, and its web-server example, crashed (`cli_short('h')`, which `--help` owns);
  - several samples weren't valid Python: a required field after a defaulted one, or `cli_file_loadable(cli_help(...))`, which isn't a supported call;
  - two `--help` samples didn't match the real output;
  - the "Type Support" dict example and the coverage figures were wrong;
  - a duplicated "Development Setup" section and a broken COVERAGE.md link are fixed.

### Tests
- 1234 tests (up from 723), with 98.02% coverage, on every supported Python version.
- Existing tests that were changed, because they asserted a defect being fixed or for formatting only:
  - `test_cli_nested.py::…::test_nested_with_non_dict_non_dataclass_in_config` now expects `ConfigurationError` instead of the value being silently discarded;
  - `test_nested_help_text.py::…::test_nested_dataclass_field_shows_parent_context` now expects the recursive flag `--l2-l3-value`;
  - `test_file_loading.py` was reformatted by black for the py311 target;
  - the `< 3.10` skip markers were removed from `test_pep604_union.py` and `test_instantiate.py`.


## [1.9.1] - 2026-09-08

### Added
- **List index and append support in property overrides** — Navigate into list elements
  with numeric indices (`items.0:value`) and append with `+` (`items.+:value`).
  Supports deep navigation (`data.0.name:new`). List behavior is runtime-determined:
  numeric keys on dicts remain string keys for backward compatibility.

### Documentation
- New "Dict Field Property Overrides" section in README documenting the full override
  syntax: basic key:value, dot-path nesting, list indexing, list append, and collisions.
- Added property overrides to features list and type support table.

### Tests
- 723 tests passing (was 685 in v1.9.0)
- 38 new tests in `tests/test_config_applicator_list_operations.py`
- Coverage: 97.58%


## [1.9.0] - 2026-09-06

### Added
- **Custom override names with `cli_override_name()`** — Specify a custom abbreviation for
  dict field property override arguments. Resolves collisions when two dict fields share the
  same auto-generated initials (e.g., `sandbox_config` and `skills_config` both → `--sc`).
  ```python
  sandbox_config: Dict[str, Any] = field(default_factory=dict)              # → --sc (auto)
  skills_config: Dict[str, Any] = cli_override_name("sk", default_factory=dict)  # → --sk
  ```
- **Override name collision detection** — `ConfigBuilderError` raised at init time when two dict
  fields generate the same override abbreviation, with a clear message suggesting `cli_override_name()`.
- Compatible with `combine_annotations()` for use alongside `cli_help()` and other annotations.
- `get_cli_override_name()` accessor for metadata introspection.

### Tests
- 685 tests passing (was 675 in v1.8.1)
- 10 new tests in `tests/test_cli_override_name.py`
- Coverage: 97.63%

## [1.8.1] - 2026-08-20

### Architecture
- **Major refactoring: builder.py decomposed into focused modules**
  - `builder.py` (1394→183 lines) — Thin orchestrator
  - `field_analyzer.py` (626 lines) — Field inspection, validation, collision detection
  - `argument_registry.py` (751 lines) — argparse argument registration
  - `config_resolver.py` (138 lines) — Pipeline orchestrator
  - `config_merging.py` (159 lines) — Config normalization and merging (Stages 1-2)
  - `cli_overrides.py` (205 lines) — CLI argument override processing (Stage 3)
  - `value_resolution.py` (236 lines) — Raw value resolution, validation, cli_resolve (Stages 4-7)
  - `convenience.py` (265 lines) — Public entry points
- **All functions reduced to Cognitive Complexity ≤10** (was CC=22 max)
- Public API unchanged — fully backward compatible

### Fixed
- **`build_config_from_dict()` now resolves `@file` references** — Previously, `cli_file_loadable`
  fields passed through `@/path/to/file.txt` as literal strings. Now correctly loads file content.
- **`build_config_from_dict()` handles dict values directly** — Dict-typed field values are used
  as-is instead of attempting file-path loading.
- **`build_config()` remembers `base_config_name` from `add_arguments()`** — Callers no longer
  need to pass `base_config_name` explicitly if it was set during argument registration.
- **`base_configs` values now pass through full resolution pipeline** — Values from `base_configs`
  that survive merging (not overridden by main config) now get `@file` loading and dict-file
  loading applied, matching the behavior of CLI-provided values.

### Added
- **`build_config_from_dict()` accepts `base_configs` parameter** — Same semantics as
  `build_config_from_cli`: supports str (file path), dict, or List[Union[str, dict]].
  Precedence: `base_configs` (lowest) < `config` dict (highest).
- 15 new tests covering `build_config_from_dict` fixes and `base_configs` support

### Tests
- 675 tests passing (was 660 in v1.7.0)
- Coverage: 97.74%
- All CI checks passing (black, isort, mypy, flake8, pre-commit, twine)


## [1.7.0] - 2026-08-18

### Added
- **Programmatic Configuration with `build_config_from_dict()`** - Build dataclass instances
  from plain dictionaries without any CLI/argparse involvement
  - New public function: `build_config_from_dict(config_class, config)`
  - Accepts only `Dict[str, Any]` — raises `TypeError` for non-dict inputs with helpful message
  - Full resolution pipeline: nested dataclass reconstruction, `cli_resolve()` execution, defaults
  - Recommended entry point for Lambda handlers, SDKs, test harnesses, and any non-CLI context
  - Thin wrapper over existing `build_config_from_cli()` — zero new internal complexity
  - Eliminates the `args=[], base_configs=dict` ceremony for programmatic usage

### Examples
- New example: `examples/programmatic_example.py` - Demonstrates three patterns:
  - Lambda handler pattern (full config from merged dict)
  - Partial config pattern (defaults fill the gaps)
  - Test harness pattern (fixtures create config directly)

### Tests
- Added 17 comprehensive tests in `tests/test_build_config_from_dict.py`
  - Basic scalar fields, defaults, empty dict, required field errors
  - Nested dataclass reconstruction via `cli_nested()`
  - `cli_resolve()` resolver invocation on dict values
  - `cli_exclude()` fields settable via dict
  - TypeError for non-dict inputs (string, list, int)
  - Optional fields, list fields
- All 660 tests passing
- Coverage: 98.76%

### Quality
- 100% backward compatible — purely additive new function
- All CI checks passing (black, isort, mypy, bandit, examples)
- Exported in `__init__.py` and `__all__`


## [1.6.0] - 2026-07-23

### Added
- **Generic Object Instantiation with `instantiate()`** - Construct Python objects from
  configuration values using convention-based dispatch
  - String + registry → zero-arg class lookup
  - Dict with `_target_` → direct class import and construction
  - Dict with `type` + registry → registry-based lookup and construction
  - `_attr_` key for post-construction attribute traversal
  - Recursive resolution of nested dicts guided by `__init__` type annotations
  - List element resolution for dicts with dispatch keys
  - Configurable `target_key`, `type_key`, `attr_key` parameters
  - `max_depth` guard against infinite recursion
  - Path-context error messages for debugging nested configs
  - `InstantiationError` exception for all failure cases

## [1.5.1] - 2026-07-22

### Fixed
- **PEP 604 union types not recognized as Optional** - `int | None` (Python 3.10+ syntax)
  was not detected as Optional by TypeInspector, causing non-string Optional fields to be
  parsed as strings instead of their declared type. Now correctly handles both
  `typing.Optional[T]` and PEP 604 `T | None` syntax.

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
