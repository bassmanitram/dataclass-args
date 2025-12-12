# Builder.py Refactoring Plan

## Executive Summary

The `dataclass_args/builder.py` file has grown to 1512 lines with significant code duplication, particularly in argument generation methods. This plan outlines a systematic refactoring to reduce duplication by ~210 lines (14%) while improving maintainability.

## Current Issues

### 1. Duplicated Argument Name Building (3 occurrences)
**Locations:**
- `_add_field_argument()` lines 729-734
- `_add_nested_field_argument()` lines 624-630  
- `_add_boolean_argument()` lines 896-902

**Pattern:**
```python
arg_names = []
if short_option:
    arg_names.append(f"-{short_option}")
arg_names.append(cli_name)
```

### 2. Duplicated Help Text Building (2 occurrences)
**Locations:**
- `_add_field_argument()` lines 737-747
- `_add_nested_field_argument()` lines 644-654

**Pattern:**
```python
custom_help = get_cli_help(info)
help_text = custom_help if custom_help else f"{default_text}"

choices = get_cli_choices(info)
if choices:
    choices_str = ", ".join(str(c) for c in choices)
    if help_text:
        help_text += f" (choices: {choices_str})"
    else:
        help_text = f"choices: {choices_str}"
```

### 3. Duplicated List Field Handling (2 occurrences - identical)
**Locations:**
- `_add_field_argument()` lines 754-769
- `_add_nested_field_argument()` lines 661-675

### 4. Duplicated Dict Field Handling (2 occurrences - similar)
**Locations:**
- `_add_field_argument()` lines 770-783
- `_add_nested_field_argument()` lines 676-710

### 5. Duplicated Scalar Field Handling (2 occurrences - identical)
**Locations:**
- `_add_field_argument()` lines 785-788
- `_add_nested_field_argument()` lines 712-715

### 6. Nearly Identical Methods
- `_add_field_argument()` (70 lines)
- `_add_nested_field_argument()` (116 lines)
These differ only in: short option handling, help text defaults, and override name computation.

## Refactoring Strategy

### Phase 1: Extract Helper Methods (~50 lines saved)

#### 1.1 Extract `_build_arg_names()`
```python
def _build_arg_names(self, cli_name: str, short_option: Optional[str] = None) -> List[str]:
    """
    Build argument names list with optional short option.
    
    Args:
        cli_name: Long-form CLI name (e.g., "--host")
        short_option: Optional short option character (e.g., "h")
        
    Returns:
        List of argument names, short option first if present
        
    Example:
        _build_arg_names("--host", "h") → ["-h", "--host"]
        _build_arg_names("--host", None) → ["--host"]
    """
    arg_names = []
    if short_option:
        arg_names.append(f"-{short_option}")
    arg_names.append(cli_name)
    return arg_names
```

**Impact:** Eliminates 15 lines across 3 methods

#### 1.2 Extract `_build_help_text()`
```python
def _build_help_text(
    self, 
    base_help: str, 
    choices: Optional[List[Any]] = None,
    extra_suffix: Optional[str] = None
) -> str:
    """
    Build help text with optional choices and suffix.
    
    Args:
        base_help: Base help text
        choices: Optional list of valid choices
        extra_suffix: Optional suffix to append (e.g., "(specify zero or more values)")
        
    Returns:
        Complete help text
        
    Example:
        _build_help_text("Server port", [80, 443, 8080]) 
        → "Server port (choices: 80, 443, 8080)"
    """
    help_text = base_help
    if choices:
        choices_str = ", ".join(str(c) for c in choices)
        help_text += f" (choices: {choices_str})"
    if extra_suffix:
        help_text += f" {extra_suffix}"
    return help_text
```

**Impact:** Eliminates 20 lines across 2 methods

#### 1.3 Extract `_add_list_field()`
```python
def _add_list_field(
    self,
    parser: argparse.ArgumentParser,
    arg_names: List[str],
    info: Dict[str, Any],
    help_text: str,
    choices: Optional[List[Any]] = None
) -> None:
    """
    Add list field argument with appropriate nargs.
    
    Args:
        parser: ArgumentParser to add argument to
        arg_names: List of argument names (with optional short form)
        info: Field info dict containing is_optional flag
        help_text: Base help text
        choices: Optional list of valid choices
    """
    if info["is_optional"]:
        nargs_val = "*"
        help_suffix = "(specify zero or more values)"
    else:
        nargs_val = "+"
        help_suffix = "(specify one or more values)"
    
    final_help = self._build_help_text(help_text, choices, help_suffix)
    parser.add_argument(*arg_names, nargs=nargs_val, choices=choices, help=final_help)
```

**Impact:** Eliminates 30 lines across 2 methods

#### 1.4 Extract `_add_dict_field()`
```python
def _add_dict_field(
    self,
    parser: argparse.ArgumentParser,
    arg_names: List[str],
    help_text: str,
    override_name: str
) -> None:
    """
    Add dict field argument with file path and override support.
    
    Args:
        parser: ArgumentParser to add arguments to
        arg_names: List of argument names for main field
        help_text: Base help text
        override_name: Name for override argument (e.g., "--mc")
    """
    # Main argument for file path
    dict_help = f"{help_text} configuration file path" if help_text else "configuration file path"
    parser.add_argument(*arg_names, type=str, help=dict_help)
    
    # Override argument
    if override_name:
        override_help = (
            f"{help_text} property override (format: key.path:value)" 
            if help_text 
            else "property override (format: key.path:value)"
        )
        parser.add_argument(override_name, action="append", help=override_help)
```

**Impact:** Eliminates 28 lines across 2 methods

#### 1.5 Extract `_add_scalar_field()`
```python
def _add_scalar_field(
    self,
    parser: argparse.ArgumentParser,
    arg_names: List[str],
    info: Dict[str, Any],
    help_text: str,
    choices: Optional[List[Any]] = None
) -> None:
    """
    Add scalar field argument.
    
    Args:
        parser: ArgumentParser to add argument to
        arg_names: List of argument names
        info: Field info dict containing type
        help_text: Base help text
        choices: Optional list of valid choices
    """
    arg_type = self._get_argument_type(info["type"])
    final_help = self._build_help_text(help_text, choices)
    parser.add_argument(*arg_names, type=arg_type, choices=choices, help=final_help)
```

**Impact:** Eliminates 8 lines across 2 methods

#### 1.6 Extract `_compute_override_name()`
```python
def _compute_override_name(self, info: Dict[str, Any], prefix: str) -> str:
    """
    Compute override argument name for dict fields.
    
    Args:
        info: Field info dict containing override_name
        prefix: Prefix for nested fields (empty string = no prefix)
        
    Returns:
        Override argument name (e.g., "--mc" or "--agent-mc")
        
    Example:
        _compute_override_name(info, "") → "--mc"
        _compute_override_name(info, "agent-") → "--agent-mc"
    """
    if prefix == "":
        return info.get("override_name", "")
    else:
        base_override = info.get("override_name", "").lstrip("--")
        return f"--{prefix}{base_override}" if base_override else f"--{prefix}override"
```

**Impact:** Eliminates 12 lines of duplicated logic

### Phase 2: Merge Duplicate Methods (~100 lines saved)

#### 2.1 Replace `_add_field_argument()` and `_add_nested_field_argument()`

**New unified method:**
```python
def _add_argument(
    self,
    parser: argparse.ArgumentParser,
    field_name: str,
    info: Dict[str, Any],
    cli_name: Optional[str] = None,
    prefix: str = ""
) -> None:
    """
    Add CLI argument for a field (nested or flat).
    
    This method handles all field types: scalars, lists, dicts, booleans, and append fields.
    It supports both flat fields and nested dataclass fields with optional prefix.
    
    Args:
        parser: ArgumentParser to add arguments to
        field_name: Field name (for boolean dest and default help text)
        info: Field info dict from _analyze_config_fields()
        cli_name: Pre-computed CLI name (for nested fields). If None, uses info["cli_name"]
        prefix: Prefix for nested fields (empty string = no prefix)
        
    Note:
        Short options are only added when prefix is empty (nested with no prefix).
        Boolean fields are handled by _add_boolean_argument().
    """
    # Boolean fields handled separately (different argparse pattern)
    if info["type"] == bool:
        # For nested fields, update cli_name in info
        if cli_name:
            nested_info = dict(info)
            nested_info["cli_name"] = cli_name
            self._add_boolean_argument(parser, field_name, nested_info)
        else:
            self._add_boolean_argument(parser, field_name, info)
        return
    
    # Determine CLI name
    if cli_name is None:
        cli_name = info["cli_name"]
    
    # Get short option (only if no prefix for nested fields)
    short_option = None if prefix else get_cli_short(info)
    
    # Build argument names list
    arg_names = self._build_arg_names(cli_name, short_option)
    
    # Get base help text
    custom_help = get_cli_help(info)
    help_text = custom_help if custom_help else (
        "nested field" if prefix else field_name
    )
    
    # Get choices
    choices = get_cli_choices(info)
    
    # Handle append fields (special action)
    if is_cli_append(info):
        self._add_append_argument(parser, arg_names, info, help_text, choices)
        return
    
    # Handle by field type
    if info["is_list"]:
        self._add_list_field(parser, arg_names, info, help_text, choices)
    elif info["is_dict"]:
        override_name = self._compute_override_name(info, prefix)
        self._add_dict_field(parser, arg_names, help_text, override_name)
    else:
        self._add_scalar_field(parser, arg_names, info, help_text, choices)
```

**Update call sites:**

In `add_arguments()` method, replace:
```python
# OLD:
if not is_cli_positional(info):
    self._add_nested_field_argument(parser, cli_name, info, prefix)
```

With:
```python
# NEW:
if not is_cli_positional(info):
    nested_field = mapping["nested_field"]
    self._add_argument(parser, nested_field, info, cli_name, prefix)
```

And replace:
```python
# OLD:
if not is_cli_positional(info) and not info.get("is_nested_dataclass", False):
    self._add_field_argument(parser, field_name, info)
```

With:
```python
# NEW:
if not is_cli_positional(info) and not info.get("is_nested_dataclass", False):
    self._add_argument(parser, field_name, info)
```

**Impact:** Eliminates ~100 lines by removing one of two nearly-identical methods

### Phase 3: Update Tests and Documentation (~10 lines)

1. Update internal documentation references
2. Verify all 348 tests still pass
3. Update AGENT_BOOTSTRAP.md if needed

## Implementation Checklist

### Prerequisites
- [ ] Create feature branch: `refactor/reduce-duplication`
- [ ] Ensure all tests pass on main: `pytest tests/ -q`
- [ ] Create backup: `git stash` or `git branch backup-before-refactor`

### Phase 1: Extract Helpers (Commit after each)
- [ ] Extract `_build_arg_names()` method
- [ ] Update 3 call sites to use new method
- [ ] Run tests: `pytest tests/ -q`
- [ ] Commit: "refactor: Extract _build_arg_names() helper"

- [ ] Extract `_build_help_text()` method
- [ ] Update 2 call sites
- [ ] Run tests
- [ ] Commit: "refactor: Extract _build_help_text() helper"

- [ ] Extract `_add_list_field()` method
- [ ] Update 2 call sites
- [ ] Run tests
- [ ] Commit: "refactor: Extract _add_list_field() helper"

- [ ] Extract `_add_dict_field()` method
- [ ] Update 2 call sites
- [ ] Run tests
- [ ] Commit: "refactor: Extract _add_dict_field() helper"

- [ ] Extract `_add_scalar_field()` method
- [ ] Update 2 call sites
- [ ] Run tests
- [ ] Commit: "refactor: Extract _add_scalar_field() helper"

- [ ] Extract `_compute_override_name()` method
- [ ] Update call sites
- [ ] Run tests
- [ ] Commit: "refactor: Extract _compute_override_name() helper"

### Phase 2: Merge Methods
- [ ] Create new `_add_argument()` method
- [ ] Update call sites in `add_arguments()`
- [ ] Run tests (should still pass)
- [ ] Delete `_add_field_argument()` method
- [ ] Delete `_add_nested_field_argument()` method
- [ ] Run tests (should still pass)
- [ ] Commit: "refactor: Merge _add_field_argument and _add_nested_field_argument into _add_argument"

### Phase 3: Verification
- [ ] Run full test suite: `pytest tests/ -xvs`
- [ ] Check code formatting: `black --check dataclass_args/`
- [ ] Check imports: `isort --check-only dataclass_args/`
- [ ] Verify line count reduction: `wc -l dataclass_args/builder.py`
- [ ] Update documentation if needed
- [ ] Final commit: "refactor: Update documentation after refactoring"

### Phase 4: Merge
- [ ] Push feature branch
- [ ] Create PR with detailed description
- [ ] Review changes
- [ ] Merge to main

## Expected Results

### Quantitative
- **Lines before:** ~1512
- **Lines after:** ~1300  
- **Lines saved:** ~210 (14% reduction)
- **Tests:** All 348 tests passing
- **Coverage:** Maintained or improved

### Qualitative
- **Single source of truth** for argument generation patterns
- **Easier maintenance** - changes to argument generation in one place
- **Better testability** - smaller, focused methods
- **Clearer code** - each method has single responsibility
- **No functional changes** - pure refactoring

## Risks and Mitigation

### Risk 1: Breaking existing functionality
**Mitigation:** 
- Run tests after each step
- Keep original methods until new method verified
- Use feature branch for safety

### Risk 2: Subtle behavioral differences
**Mitigation:**
- Carefully preserve all conditionals
- Test edge cases explicitly
- Review diff carefully before committing

### Risk 3: Test failures
**Mitigation:**
- Fix tests as they break
- Verify tests are testing behavior, not implementation
- Don't merge until all tests pass

## Timeline

- **Phase 1:** 2-3 hours (6 helper extractions × 20-30 min each)
- **Phase 2:** 1-2 hours (method merge + call site updates)
- **Phase 3:** 30 minutes (verification + documentation)
- **Total:** 4-6 hours

## Future Opportunities

After this refactoring, consider:

1. **Extract argument type handling** - `_get_argument_type()` could be enhanced
2. **Consolidate validation** - Boolean, list, dict validation patterns
3. **Improve help text formatting** - Consistent formatting across all field types
4. **Extract override logic** - Property override handling could be its own module

---

**Author:** AI Assistant  
**Date:** 2025-12-12  
**Status:** DRAFT - Ready for implementation
