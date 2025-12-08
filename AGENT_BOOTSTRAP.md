# dataclass-args - Agent Bootstrap

**Purpose**: Zero-boilerplate CLI generation from Python dataclasses with advanced type support  
**Type**: Library  
**Language**: Python 3.8+  
**Repository**: https://github.com/bassmanitram/dataclass-args

---

## What You Need to Know

**This is**: A library that auto-generates argparse-based CLIs from dataclass definitions. You define a dataclass with typed fields and optional metadata annotations (`cli_short`, `cli_append`, etc.), call `build_config()`, and get a fully functional CLI with help text, type validation, and configuration file merging. Eliminates argparse boilerplate.

**Architecture in one sentence**: Dataclass introspection → Field analysis → ArgumentParser generation → Parsing → Configuration merging → Dataclass instantiation.

**The ONE constraint that must not be violated**: At most ONE positional argument can use `nargs='*'` or `'+'`, and it MUST be the last positional - this is an argparse limitation, not negotiable.

---

## Mental Model

- Think of this as **dataclass-to-CLI compiler** - your dataclass definition IS the CLI specification
- Field metadata (`cli_short`, `cli_choices`, etc.) controls CLI behavior - these are **declarative annotations**
- Configuration merging follows **precedence layers**: base_configs → --config file → CLI args (later wins)
- Type system drives parsing - `List[str]` becomes multi-value arg, `bool` becomes flag, `Optional[T]` becomes optional
- Positional args are **greedy** - they consume remaining arguments, which is why only ONE list positional allowed

---

## Codebase Organization

```
dataclass_args/
├── builder.py         # GenericConfigBuilder - core CLI generation logic
├── annotations.py     # Field metadata: cli_short(), cli_append(), cli_choices(), etc.
├── file_loading.py    # @file.txt syntax support for string fields
├── utils.py           # load_structured_file() - YAML/JSON/TOML loading
├── exceptions.py      # ConfigBuilderError and subclasses
└── tests/             # Comprehensive test suite (one file per feature)
```

**Navigation Guide**:

| When you need to... | Start here | Why |
|---------------------|------------|-----|
| Add new annotation | `annotations.py` → create `cli_*()` function | All annotations defined here |
| Modify argument generation | `builder.py` → `_add_field_argument()` | Where field → argparse arg translation happens |
| Change merge behavior | `builder.py` → `build_config()` → merge logic | Configuration hierarchy handled here |
| Fix type handling | `builder.py` → `_get_field_type_info()` | Type introspection and parsing |
| Add file format support | `utils.py` → `load_structured_file()` | Format dispatch logic |

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
   - **Enforced by**: `_validate_positional_arguments()` called during builder init

2. **Append fields must have default_factory=list**: `cli_append()` requires list type with factory
   - **Why**: argparse `action='append'` appends to existing list, needs empty list to start
   - **Breaks if violated**: First append creates new list, subsequent appends fail
   - **Enforced by**: Documentation, examples, tests demonstrate pattern (not runtime enforced)

3. **nargs and min_args/max_args are mutually exclusive**: Can't specify both for `cli_append()`
   - **Why**: They solve same problem differently - nargs is exact count, min/max is range
   - **Breaks if violated**: `ValueError` raised in `cli_append()` validation
   - **Enforced by**: Validation in `annotations.py` at annotation creation time

---

## Non-Obvious Behaviors & Gotchas

Things that surprise people:

1. **List fields without cli_append accumulate from single flag**:
   - **Why it's this way**: `--files a b c` puts all three in list (argparse default)
   - **Common mistake**: Expecting `--files a --files b` to work (it doesn't without cli_append)
   - **Correct approach**: Use `cli_append()` if you want `--files a --files b` pattern

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

---

## Key Patterns & Abstractions

**Pattern 1: Metadata-Driven Generation**
- **Used for**: All field customization (short options, choices, positional, append, etc.)
- **Structure**: Annotation functions return `field(metadata={...})`, builder inspects metadata
- **Examples in code**: `cli_short()`, `cli_append()`, `cli_choices()` - all return field with metadata

**Pattern 2: Type-Directed Parsing**
- **Used for**: Converting strings to target types (List[int], Optional[str], Path, etc.)
- **Structure**: Introspect type hints, generate appropriate argparse `type=` and `nargs=`
- **Why**: Dataclass type is source of truth, argparse must match

**Anti-pattern to avoid: Using list literal as default**
- **Don't do this**: `files: List[str] = []` (mutable default)
- **Why it fails**: All instances share same list object, modifications leak across instances
- **Instead**: `files: List[str] = field(default_factory=list)`

---

## State & Data Flow

**State management**:
- **Persistent state**: Configuration files (YAML/JSON/TOML) on filesystem
- **Runtime state**: GenericConfigBuilder holds field analysis, ArgumentParser instance
- **No state here**: Annotation functions are pure (just return field metadata)

**Data flow**:
```
Dataclass Definition → GenericConfigBuilder.__init__() → Field Analysis
                                                              ↓
                                                    ArgumentParser.add_argument()
                                                              ↓
        Command-line args → ArgumentParser.parse_args() → Namespace
                                                              ↓
                    base_configs → Merge → --config file → Merge → CLI args → Merge
                                                              ↓
                                                    Dataclass(**merged_dict)
```

**Critical paths**: Type hint extraction must happen before argument addition - argparse needs type info to generate correct parser.

---

## Integration Points

**This project depends on** (upstream):
- **typing-extensions**: Backport of typing features, tightly coupled (enables Python 3.8 support)
- **PyYAML** (optional): YAML loading, loosely coupled (via utils.py)
- **tomli** (optional, Python <3.11): TOML loading, loosely coupled

**Projects that depend on this** (downstream):
- **strands-agent-factory**: Uses dataclass-args for CLI scripts (chatbot, a2a-server)
- **yacba**: Uses dataclass-args for configuration CLI generation
- **Your CLI applications**: Configuration and argument parsing

**Related projects** (siblings):
- **profile-config**: File-based config vs dataclass-args' CLI args - often used together
- **envlog**: Environment-based config, complementary domain

---

## Configuration Philosophy

**What's configurable**: Field behavior via annotations, merge strategy via base_configs, precedence via order

**What's hardcoded**:
- ArgumentParser as underlying engine
- Dataclass field introspection approach
- Type-to-argparse mapping rules

**The trap**: Trying to use `nargs='*'` on multiple positional arguments. Argparse can't parse ambiguous CLIs like `cmd pos1_val pos2_val_or_pos1_val`. Only ONE greedy positional allowed, must be last.

---

## Testing Strategy

**What we test**:
- **Annotation behavior**: Each annotation (cli_short, cli_append, etc.) has dedicated test file
- **Type handling**: Lists, Dicts, Optional, Path, nested types
- **Merge behavior**: base_configs precedence, file loading, override order
- **Edge cases**: Empty configs, missing fields, type mismatches

**What we don't test**:
- **argparse internals**: Trust stdlib works
- **Dataclass mechanics**: Trust Python's dataclasses module

**Test organization**: One test file per feature (test_cli_short.py, test_cli_append.py, etc.). Each test creates dataclass, generates CLI, tests parsing.

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

---

## Modification Patterns

**To add new annotation** (e.g., `cli_required()`):
1. Create function in `annotations.py` → `cli_required(**kwargs)` returning `field(metadata={...})`
2. Add helper `is_cli_required(field_info)` and `get_cli_required_value(field_info)`
3. Update `builder.py` → `_add_field_argument()` to check metadata and apply to argparse
4. Add test file `tests/test_cli_required.py` with comprehensive cases
5. Add example in `examples/cli_required_example.py`

**To add new type support** (e.g., Decimal):
1. Update `builder.py` → `_get_field_type_info()` to detect Decimal type
2. Add conversion logic (argparse `type=Decimal` or custom converter)
3. Add tests in `tests/test_builder_advanced.py` or new file
4. Document in README.md type support section

**To fix precedence issue** (e.g., CLI args not overriding base_configs):
1. Check `builder.py` → `build_config()` merge logic - order matters
2. Verify argparse isn't using `set_defaults()` (should use `SUPPRESS` for booleans)
3. Add test demonstrating correct precedence
4. Fix merge order or default handling

---

## When to Update This Document

Update this bootstrap when:
- [x] New annotation type added (extends metadata system, documents pattern)
- [x] Merge strategy fundamentally changes (precedence rules)
- [x] Type system handling changes (new type inspection approach)
- [x] Configuration philosophy changes (e.g., support config hierarchy like profile-config)

Don't update for:
- ❌ Individual annotation additions (follow existing pattern)
- ❌ Type support additions (extend type handling)
- ❌ Bug fixes in parsing or merging
- ❌ Test additions
- ❌ Example additions

---

**Last Updated**: 2025-12-03  
**Last Architectural Change**: v1.3.0 - Added min_args/max_args to cli_append() for flexible validation
