# dataclass-args - Agent Bootstrap

**Purpose**: Zero-boilerplate CLI generation from Python dataclasses with advanced type support
**Type**: Library
**Language**: Python 3.11+ (non-EOL versions only; tested on 3.11–3.14; no runtime dependencies)
**Repository**: https://github.com/bassmanitram/dataclass-args

---

## What You Need to Know

**This is**: A library that auto-generates argparse-based CLIs from dataclass definitions. You define a dataclass with typed fields and optional metadata annotations (`cli_short`, `cli_append`, `cli_nested`, etc.), call `build_config()`, and get a fully functional CLI with help text, type validation, and configuration file merging. Eliminates argparse boilerplate.

**Architecture in one sentence**: Dataclass introspection → Field analysis → ArgumentParser generation → Parsing → Configuration merging → Dataclass instantiation.

**The ONE constraint that must not be violated**: At most ONE positional argument can use `nargs='*'` or `'+'`, and it MUST be the last positional - this is an argparse limitation, not negotiable.

---

## Mental Model

- Think of this as **dataclass-to-CLI compiler** - your dataclass definition IS the CLI specification
- Field metadata (`cli_short`, `cli_choices`, `cli_nested`, etc.) controls CLI behavior - these are **declarative annotations**
- Configuration merging follows **precedence layers**: base_configs → --config file → CLI args (later wins)
- **How layers combine** is per call: `merge_strategy="shallow"` (default) merges dicts **one level** at every boundary; `"deep"` merges recursively. Lists replace, `None` clears, in both
- **Layered mode** (`merge_strategy="deep"`) unlocks named `ConfigLayer`s, per-field list rules (`cli_list_merge` + `list_merge="rules"` layers append instead of replace) and provenance (`return_provenance=True` → which layer set each leaf)
- **Every layer is normalised on entry** (`LayerNormalizer`): private copy, hyphen→underscore field names, dict-field file refs loaded, `cli_nested` instances → field dicts. After that, merging only ever sees plain dicts
- Type system drives parsing - `List[str]` becomes multi-value arg, `bool` becomes flag, `Optional[T]` becomes optional
- Positional args are **greedy** - they consume remaining arguments, which is why only ONE list positional allowed
- **Nested dataclasses flatten to CLI** - `cli_nested()` expands nested fields with configurable prefixes

---

## Codebase Organization

```
dataclass_args/
├── convenience.py          # Public entry points: build_config, build_config_from_cli, build_config_from_dict
├── builder.py              # GenericConfigBuilder - thin orchestrator (analyser + registry + resolver)
├── field_analyzer.py       # Field inspection, validation, collisions, cycle guard, list-rule map
├── argument_registry.py    # argparse registration (field → add_argument), help text, override names
├── option_collisions.py    # Plans every option string; any clash → ConfigBuilderError before registration
├── config_resolver.py      # The 9-stage pipeline (see State & Data Flow)
├── config_merging.py       # ConfigLayer, base_configs normalisation (labels), layer stacking
├── merge_strategy.py       # MERGE_SHALLOW/DEEP, MergeContext (per-call), combine_dicts, merge_with_rules
├── layer_normalization.py  # LayerNormalizer - per-layer intake (keys, file refs, nested instances)
├── config_applicator.py    # merge_layer, --config file, property overrides (set_nested_property)
├── cli_overrides.py        # Stage 4: real CLI values + top-level property overrides
├── nested_processor.py     # Recursive flattening + reconstruction of cli_nested at any depth
├── value_resolution.py     # Stage 5 @file resolution, stage 7 append ranges, stage 8 cli_resolve
├── provenance.py           # Provenance recorder + query API (entries/source/paths/changes/explain)
├── annotations.py          # cli_*() annotations and their accessors
├── type_inspector.py       # Type analysis utilities
├── file_loading.py         # @file.txt syntax support for string fields
├── utils.py                # load_structured_file, deep_merge, copy_containers, fresh_field_default
├── instantiate.py          # instantiate() - object construction from config
└── exceptions.py           # ConfigBuilderError (programming errors) / ConfigurationError (config errors)
tests/                      # 1399 tests, ~98% coverage, Python 3.11–3.14
```

**Navigation Guide**:

| When you need to... | Start here | Why |
|---------------------|------------|-----|
| Add new annotation | `annotations.py` → `cli_*()` + accessor; validate in `field_analyzer.py` | All annotations defined here |
| Modify argument generation | `argument_registry.py` | Field → argparse translation, help text |
| Change merge behavior | `merge_strategy.py` (`combine_dicts`, `merge_with_rules`) and its 4 call sites | Every place two sources meet uses this |
| Change what a layer looks like on entry | `layer_normalization.py` | Keys, file refs, nested instances |
| Fix type handling | `field_analyzer.py` / `type_inspector.py` | Type introspection |
| Add file format support | `utils.py` → `load_structured_file()` | Format dispatch logic |
| Handle nested dataclasses | `nested_processor.py` | Recursive flatten/reconstruct, keyed by `path` tuples |
| Provenance / layer names | `provenance.py`, hooks at stages 2/3/4/6 | Recorder rides on `MergeContext.recorder` |

**Entry points**:
- Main execution: `build_config(MyDataclass, ['arg1', 'arg2'])` - Returns dataclass instance
- Tests: `tests/test_*.py` - One file per feature area
- Examples: `examples/` - Working demonstrations of each feature

---

## Critical Invariants

These rules MUST be maintained:

1. **One greedy positional maximum**: At most one positional with `nargs` in `['*', '+']`, must be last
   - **Why**: argparse limitation - multiple greedy positionals create ambiguous CLI
   - **Breaks if violated**: ArgumentParser raises error at construction time
   - **Enforced by**: `FieldAnalyzer.validate_positional_arguments()` during builder init

2. **"Nothing typed" must be distinguishable from a CLI value**: argparse defaults never carry dataclass defaults
   - **Why**: stages treat a non-`None` Namespace value as "given on the CLI" and let it override layers
   - **How**: booleans, `append` actions and `*` positionals use `default=SUPPRESS`; `?` positionals use `None` (SUPPRESS is a string and older argparse type-converts string defaults). Dataclass defaults apply at instantiation
   - **Breaks if violated**: layer values for that field are silently ignored (defect AP1 in 1.9.x)

3. **nargs and min_args/max_args are mutually exclusive**: Can't specify both for `cli_append()`
   - **Why**: They solve same problem differently - nargs is exact count, min/max is range
   - **Breaks if violated**: `ValueError` raised in `cli_append()` validation
   - **Enforced by**: Validation in `annotations.py` at annotation creation time

4. **Nested field collision detection**: No duplicate CLI names from flattened nested fields
   - **Why**: Ambiguous which field gets the value (e.g., `app.name` vs `db.name` both become `--name`)
   - **Breaks if violated**: `ConfigBuilderError` with collision details
   - **Enforced by**: `NestedFieldProcessor._check_collision()` during flattening (all depths), short-option and override-name checks in `FieldAnalyzer`, and a final whole-parser plan in `option_collisions.py` (run by `add_arguments` before anything is registered) that also covers `-h/--help`, the `--config` option, `--no-` flags and dict override options. A second check (`check_dest_collisions`) rejects two arguments sharing one Namespace attribute; every argument is registered with an explicit `dest` (`utils.cli_name_to_dest`), so names like `_count` (`---count`) read back correctly

5. **Caller data is never mutated or aliased**: every layer is copied at intake (`copy_containers`: dicts/lists at every depth; other objects by reference)
   - **Breaks if violated**: property overrides/appends write into the caller's dicts; the instance holds caller objects

6. **`deep_merge` stays pure**: no field knowledge, no I/O, never mutates inputs, never recurses into non-dicts. Field-aware behaviour (list rules, instance conversion) lives in `merge_with_rules` / `LayerNormalizer`

7. **Cognitive complexity ≤ 10 per function**: enforced in CI by `flake8-cognitive-complexity`

---

## Non-Obvious Behaviors & Gotchas

Things that surprise people:

1. **List fields take all values from a single flag; repeats keep the last occurrence** unless `cli_extend()` (flat accumulate) or `cli_append()` (one entry per occurrence):
   - **Why it's this way**: `--files a b c` puts all three in list (argparse default)
   - **Common mistake**: Expecting `--files a --files b` to give both (it silently keeps only `['b']`)
   - **Correct approach**: `cli_extend()` for one flat list (`['a', 'b']`), `cli_append()` for one entry per occurrence
   - **Element types** are converted for `int`/`float`/`str` lists (v1.10.1); `Path`/`Enum` CLI values stay strings by design (for now)

2. **Boolean fields from base_configs work differently than CLI**:
   - **Why**: argparse uses `SUPPRESS` to distinguish "not specified" from "specified as False"
   - **Watch out for**: `--flag` sets True, omitting flag preserves base_configs value (doesn't default to False)
   - **Pattern**: This enables base_configs to provide booleans that CLI can override

3. **File loading with @syntax only works for string fields**:
   - **Why**: Only string fields support `@file.txt` - type system doesn't allow `@file.txt` for int/bool
   - **Pattern**: Use `cli_file_loadable()` annotation, then `--prompt @~/prompt.txt`
   - **Gotcha**: Tilde expansion happens automatically, path is relative to CWD

4. **combine_annotations merges metadata, not creates union**:
   - **Why**: Single field needs multiple features (short + choices + help)
   - **Watch out for**: Order doesn't matter (all metadata merged into field)
   - **Correct approach**: `combine_annotations(cli_short('r'), cli_choices(['a','b']), cli_help('text'))`

5. **Short options disabled for nested fields with prefix** (v1.4.0):
   - **Why**: Prevents ambiguity - `--db-host` is clear, `-d` could be many things
   - **Pattern**: Short options only work when `prefix=""`  (flat namespace)
   - **Gotcha**: Top-level fields still get short options, just not nested ones with prefix. This applies to booleans too, so one dataclass can be nested under two prefixes
   - **Override**: Use `prefix="custom"` or `prefix=""` (flat) to control

6. **Auto prefix uses field name** (v1.4.0):
   - **Why**: `cli_nested()` without prefix uses field name as prefix
   - **Example**: `db: DbConfig = cli_nested()` → fields become `--db-name`, `--db-host`

7. **cli_resolve fields are dual-natured** (v1.5.0):
   - **Why it's this way**: Field type is `Optional[Sandbox]` but during parsing it's treated as dict
   - **Common mistake**: Expecting the field to accept complex types directly on CLI
   - **Pattern**: For non-list fields, library forces `is_dict=True`; for list fields, keeps list behavior. Resolver runs after assembly
   - **Gotcha**: Property overrides work (modify dict before resolution) but fail on pre-built objects

8. **Shallow merge is one level, everywhere** (v1.10.0):
   - **Watch out for**: `{'db': {'opts': {'x':1}}}` then `{'db': {'opts': {'y':2}}}` → `opts == {'y':2}` (nested dict replaced). Use `merge_strategy="deep"` for recursive merging
   - **History**: before 1.10, `base_configs`/`--config` replaced dicts wholesale while `--field file.json` merged one level; it is now consistent

9. **Property overrides edit the effective value** (v1.10.0): `--mc k:v` applies to the merged value, else to a fresh copy of the dataclass default; after an explicit `None` it starts from `{}`. A *full* value (`--mc file.json`, a dict layer) still replaces the default rather than merging into it

10. **Required positionals are CLI-only**: `nargs` `None`/`'+'`/int must be typed; layers cannot satisfy them. Optional positionals (`?`/`*`) and everything else can come from any layer. `build_config_from_dict` has no CLI, so all positionals come from the dict

11. **Provenance records raw values** (v1.10.0): after file loading, before `@file`/`cli_resolve`. Only paths a source actually supplied are recorded; `source()` returns `"default"` only for unset dataclass field leaves

12. **List rules never fire for CLI values or the `--config` file**: only stage-2 layers with `list_merge="rules"` (and the `build_config_from_dict` config with `config_list_merge="rules"`)

13. **A string for a plain dict field is a file path or an error** (v1.10.1): from any source (CLI, nested CLI, every layer), an existing file of any extension is loaded like `--config`; a missing `.json/.yaml/.yml/.toml` path is "not found"; anything else raises. Only `cli_resolve` fields receive other strings. One helper implements this for all entry points.

14. **CLI option names are frozen until a minor release**: nested prefixes keep underscores in positive options (`--primary_db-host`) while negative flags hyphenate (`--no-primary-db-ssl`). Hyphenation is recorded in `FUTURE_CHANGES.md`; don't "fix" it in a patch release. The help-snapshot gate catches accidental renames.

---

## Architecture Decisions

**Why use dataclass metadata instead of custom decorators?**
- **Trade-off**: Metadata is less visible but preserves dataclass semantics (dataclasses.field)
- **Alternative considered**: Decorator like `@cli_short('n')` on field
- **Why metadata wins**: Dataclass remains valid dataclass, tools (IDEs, type checkers) understand it, no magic decorators

**Why support both base_configs dict and file?**
- **Trade-off**: More complex merging logic but maximizes flexibility
- **Alternative considered**: File only, or dict only
- **Why both**: Dict for programmatic config (tests, generated), file for static config (deployment)

**Why allow list of overrides instead of single override?**
- **Trade-off**: More complex precedence but enables layered config (base → environment → local)
- **Alternative considered**: Single override source
- **Implications**: Must document precedence clearly, list order matters (later wins)

**Why flatten nested dataclasses instead of subparsers?** (v1.4.0)
- **Trade-off**: Flatter CLI namespace vs nested structure
- **Alternative considered**: argparse subparsers (`cmd db --host localhost`)
- **Why flatten**: Simpler mental model, all flags at same level, config files map directly to CLI

---

## Key Patterns & Abstractions

**Pattern 1: Metadata-Driven Generation**
- **Used for**: All field customization (short options, choices, positional, append, nested, etc.)
- **Structure**: Annotation functions return `field(metadata={...})`, builder inspects metadata
- **Examples in code**: `cli_short()`, `cli_append()`, `cli_nested()` - all return field with metadata

**Pattern 2: Type-Directed Parsing**
- **Used for**: Converting strings to target types (List[int], Optional[str], Path, etc.)
- **Structure**: Introspect type hints, generate appropriate argparse `type=` and `nargs=`
- **Why**: Dataclass type is source of truth, argparse must match

**Pattern 3: Recursive Field Flattening** (v1.4.0)
- **Used for**: Expanding nested dataclass fields into flat CLI arguments
- **Structure**: Detect nested dataclass via `cli_nested()`, recursively extract fields, add prefix
- **Why**: Enables hierarchical config without complex CLI syntax

**Anti-pattern to avoid: Using list literal as default**
- **Don't do this**: `files: List[str] = []` (mutable default)
- **Why it fails**: All instances share same list object, modifications leak across instances
- **Instead**: `files: List[str] = field(default_factory=list)`

---

## State & Data Flow

**State management**:
- **Persistent state**: Configuration files (YAML/JSON/TOML) on filesystem
- **Runtime state**: GenericConfigBuilder holds field analysis, ArgumentParser instance, flattened field map
- **No state here**: Annotation functions are pure (just return field metadata)

**Data flow** (`ConfigResolver.build_config`; a `MergeContext` carrying strategy, list rules and the optional provenance recorder is created per call and passed to each stage):
```
validate merge_strategy / rules / provenance options           (before any I/O)
1. normalise layers: base_configs → (label, dict, list_merge); LayerNormalizer on each
2. apply base_configs      one-level or deep merge; merge_with_rules for rules layers   [provenance]
3. apply --config file     normalised, then merged (never rules)                         [provenance]
4. apply CLI overrides     real CLI values + top-level property overrides (always replace) [provenance]
5. resolve raw values      @file references in layer values
6. reconstruct nested      cli_nested at any depth, CLI flags + nested overrides           [provenance]
7. validate append ranges  min_args/max_args
8. resolve fields          cli_resolve (top level only)
9. instantiate             config_class(**config)
```
`build_config_from_dict` in deep mode appends the whole `config` dict as the last layer (`name="config"`); in shallow mode it injects regular values into an unparsed Namespace (never `parse_args`, so it never exits).

**Critical paths**:
- Type hint extraction must happen before argument addition - argparse needs type info
- Nested field flattening must check for collisions before adding arguments

---

## Integration Points

**This project depends on** (upstream):
- **No runtime dependencies** (Python 3.11+ stdlib: `tomllib`, `typing`, `types.UnionType`)
- **PyYAML** (optional): YAML loading, loosely coupled (via utils.py)

**Projects that depend on this** (downstream):
- **CLI applications and agent frameworks**: configuration and argument parsing, including layered configuration (defaults, user config, mandatory overrides) with provenance

**Related projects** (siblings):
- **profile-config**: File-based config vs dataclass-args' CLI args - often used together
- **envlog**: Environment-based config, complementary domain

---

## Configuration Philosophy

**What's configurable**: Field behavior via annotations; dict merge depth via `merge_strategy`; list behaviour per field via `cli_list_merge` in rules layers; precedence via layer order; layer names via `ConfigLayer`; nested structure via cli_nested prefix modes

**What's hardcoded**:
- ArgumentParser as underlying engine
- Dataclass field introspection approach
- Type-to-argparse mapping rules
- Nested field flattening strategy

**The trap**: Trying to use `nargs='*'` on multiple positional arguments. Argparse can't parse ambiguous CLIs like `cmd pos1_val pos2_val_or_pos1_val`. Only ONE greedy positional allowed, must be last.

---

## Testing Strategy

**What we test**:
- **Annotation behavior**: Each annotation (cli_short, cli_append, cli_nested, etc.) has dedicated test file
- **Type handling**: Lists, Dicts, Optional, Path, nested types
- **Merge behavior**: base_configs precedence, file loading, override order
- **Nested dataclasses**: Prefix modes, collision detection, config file merging, any depth (`test_nested_depth.py`)
- **Defect regressions**: one test per defect ID (`test_defect_fixes.py`, IDs from the 1.10 defect register)
- **Merge/layers/provenance**: `test_deep_merge.py`, `test_list_merge_rules.py`, `test_layered_mode.py` (incl. shallow-vs-layered equivalence per field kind), `test_provenance.py`
- **Python matrix**: the whole suite runs on 3.11–3.14 in CI
- **Edge cases**: Empty configs, missing fields, type mismatches

**What we don't test**:
- **argparse internals**: Trust stdlib works
- **Dataclass mechanics**: Trust Python's dataclasses module

**Test organization**: One test file per feature (test_cli_short.py, test_cli_append.py, test_cli_nested.py, etc.). Each test creates dataclass, generates CLI, tests parsing.

**Mocking strategy**: No mocking - use real dataclasses, real argparse, real file I/O with tempfiles. More realistic, easier to debug.

---

## Common Problems & Diagnostic Paths

**Symptom**: "Positional list argument must be last" error
- **Most likely cause**: Multiple positional arguments with `nargs='*'` or `'+'`
- **Check**: Count positional fields in dataclass - only one can be greedy
- **Fix**: Make additional lists optional with flags: `files: List[str] = cli_short('f', default_factory=list)`

**Symptom**: Append not accumulating values across multiple flag uses
- **Likely cause**: Field is `List[str]` without `cli_append()` annotation
- **Diagnostic**: Check if field has `cli_append()` - regular List fields take all values from single flag
- **Solution**: Add `cli_append()` annotation: `tags: List[str] = cli_append(default_factory=list)`

**Symptom**: Boolean from base_configs not applying
- **Why it happens**: Fixed in v1.2.2 - earlier versions had bug
- **Diagnostic**: Check version with `pip show dataclass-args`
- **Solution**: Upgrade to v1.2.2+

**Symptom**: min_args/max_args validation not working
- **Why it happens**: Feature added in v1.3.0
- **Diagnostic**: Check if using both nargs and min/max (mutually exclusive)
- **Solution**: Use `cli_append(min_args=X, max_args=Y)` without nargs parameter

**Symptom**: "CLI name collision detected" error (v1.4.0)
- **Likely cause**: Multiple nested fields flatten to same CLI name (e.g., `--name` from both app and db)
- **Diagnostic**: Error message shows which fields collide
- **Solution**: Use custom prefix: `db: DbConfig = cli_nested(prefix="database")` → `--database-name`

**Symptom**: Short options not working for nested fields (v1.4.0)
- **Why it happens**: Short options disabled when prefix is set (by design)
- **Diagnostic**: Check if nested field uses `prefix=""` (flat namespace)
- **Solution**: Use `prefix=""` to enable short options, or accept long options only

**Symptom**: "cli_resolve cannot be combined with..." error (v1.5.0)
- **Likely cause**: Using `cli_resolve` together with `cli_positional`, `cli_nested`, `cli_append`, `cli_exclude`, or `cli_file_loadable`
- **Diagnostic**: Check field annotations for incompatible combinations
- **Solution**: Remove incompatible annotation. `cli_resolve` only works with `cli_help`, `cli_short`, `cli_choices`

**Symptom**: "Cannot apply property overrides... not a dict" (v1.5.0)
- **Likely cause**: Pre-built object in base_configs + CLI property overrides on same field
- **Diagnostic**: Check if base_configs provides an already-instantiated object AND CLI uses `--abbreviation key:value`
- **Solution**: Remove pre-built object from base_configs, or don't use property overrides for that field

---

## Modification Patterns

**To add new annotation** (e.g., `cli_required()`):
1. `annotations.py`: `cli_required(**kwargs)` returning `field(metadata={...})` + accessor
2. `field_analyzer.py`: validate combinations at builder construction (fail fast with `ConfigBuilderError`)
3. `argument_registry.py`: apply to argparse if it affects the CLI (keep argparse defaults "nothing typed"-safe; see invariant 2)
4. Tests in a dedicated `tests/test_cli_required.py`; check `--help` is unchanged for existing examples
5. Example in `examples/` and a line in `scripts/run_examples.sh`

**To add new type support** (e.g., Decimal): `type_inspector.py` / `field_analyzer.py` detection → `argument_registry.py` conversion → tests → README type table.

**To change how sources combine**: change `merge_strategy.py` only; all four combination sites (stages 2, 3, 4 dict override, 6 nested dict) call `combine_dicts`. Keep shallow behaviour pinned (tests + `local`-style oracle outputs) and keep `deep_merge` pure.

**To add a provenance hook**: feed the recorder the *incoming* leaves of what the source supplied (never a before/after diff of the merged config, which would credit seeded defaults to the wrong layer).

## When to Update This Document

Update this bootstrap when:
- [x] New annotation type added (extends metadata system, documents pattern)
- [x] Merge strategy fundamentally changes (precedence rules)
- [x] Type system handling changes (new type inspection approach)
- [x] Configuration philosophy changes (e.g., support config hierarchy like profile-config)
- [x] **Nested dataclass support added** (v1.4.0 - architectural change)
- [x] **Post-load resolution added** (v1.5.0 - new pipeline stage, new annotation pattern)
- [x] **Merge strategies, layers, list rules, provenance, nesting at any depth, Python ≥ 3.11** (v1.10.0)

Don't update for:
- ❌ Individual annotation additions (follow existing pattern)
- ❌ Type support additions (extend type handling)
- ❌ Bug fixes in parsing or merging
- ❌ Test additions
- ❌ Example additions

---

**Last Updated**: 2026-11-24
**Last Architectural Change**: v1.10.0 - layer normalisation stage, per-call MergeContext (merge strategy, list rules, provenance recorder), recursive nesting, Python ≥ 3.11
