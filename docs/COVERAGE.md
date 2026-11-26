# Code Coverage Report

## Overview

This project maintains **97.68%** code coverage with comprehensive testing and branch coverage enabled.

## Current Coverage Statistics (v1.10.1)

| Module | Statements | Missing | Branches | Partial | Coverage |
|--------|------------|---------|----------|---------|----------|
| `__init__.py` | 10 | 0 | 0 | 0 | **100.00%** |
| `annotations.py` | 202 | 1 | 54 | 1 | **99.22%** |
| `append_action.py` | 6 | 0 | 0 | 0 | **100.00%** |
| `argument_registry.py` | 217 | 1 | 80 | 4 | **98.32%** |
| `builder.py` | 42 | 0 | 10 | 3 | **94.23%** |
| `cli_overrides.py` | 93 | 2 | 30 | 0 | **98.37%** |
| `config_applicator.py` | 118 | 0 | 48 | 0 | **100.00%** |
| `config_merging.py` | 64 | 1 | 20 | 1 | **97.62%** |
| `config_resolver.py` | 68 | 0 | 12 | 0 | **100.00%** |
| `convenience.py` | 97 | 0 | 46 | 9 | **93.71%** |
| `exceptions.py` | 8 | 0 | 0 | 0 | **100.00%** |
| `field_analyzer.py` | 314 | 13 | 144 | 6 | **95.41%** |
| `file_loading.py` | 40 | 0 | 16 | 0 | **100.00%** |
| `formatter.py` | 9 | 0 | 4 | 0 | **100.00%** |
| `instantiate.py` | 178 | 1 | 66 | 1 | **99.18%** |
| `layer_normalization.py` | 82 | 0 | 30 | 0 | **100.00%** |
| `merge_strategy.py` | 50 | 0 | 24 | 0 | **100.00%** |
| `nested_processor.py` | 199 | 5 | 82 | 3 | **97.15%** |
| `option_collisions.py` | 127 | 5 | 68 | 7 | **93.85%** |
| `provenance.py` | 202 | 2 | 64 | 2 | **98.50%** |
| `type_inspector.py` | 65 | 1 | 28 | 2 | **96.77%** |
| `utils.py` | 142 | 0 | 48 | 0 | **100.00%** |
| `value_resolution.py` | 72 | 3 | 34 | 1 | **96.23%** |
| **TOTAL** | **2405** | **35** | **908** | **40** | **97.68%** |

## Test Suite

- **Total Tests:** 1376
- **Test Execution Time:** ~10s
- **All Tests Passing:** ✅
- **Python Version:** 3.11+ (tested on 3.11–3.14)

## Coverage Requirements

- **Minimum Required:** 88%
- **Current Coverage:** 97.68% ✅
- **Modules at 100%:** 10 of 23

## Coverage History

| Version | Tests | Coverage | Change |
|---------|-------|----------|--------|
| v1.4.3 | 429 | 92.24% | baseline |
| v1.5.0 | 501 | 91.35% | +72 tests (new module) |
| v1.6.0 | 633 | 98.74% | +132 tests, gap coverage |
| v1.7.0 | 660 | 98.76% | +27 tests (build_config_from_dict) |
| v1.8.1 | 675 | 97.74% | +15 tests, major refactor |
| v1.9.0 | 723 | 97.58% | +48 tests (cli_override_name, list overrides) |
| v1.10.0 | 1234 | 98.02% | +511 tests (defect fixes, deep merge, layers, list rules, provenance, nesting at any depth) |
| v1.10.1 | 1376 | 97.68% | +142 tests (list element types, cli_extend, QA review fixes) |

## Architecture (v1.10.0)

```
dataclass_args/
├── convenience.py          # Public entry points (build_config, build_config_from_cli, build_config_from_dict)
├── builder.py              # Orchestrator: FieldAnalyzer + ArgumentRegistry + ConfigResolver
├── field_analyzer.py       # Field inspection, validation, collisions, cycle guard, list-rule map
├── argument_registry.py    # argparse argument registration
├── config_resolver.py      # Pipeline orchestrator (stages 1-9)
│   ├── config_merging.py       # ConfigLayer, base_configs normalisation, layer stacking
│   ├── layer_normalization.py  # Per-layer intake: keys, dict-field file refs, nested instances
│   ├── merge_strategy.py       # shallow/deep, MergeContext, list-merge rules
│   ├── cli_overrides.py        # Stage 4: CLI argument overrides
│   ├── nested_processor.py     # Stage 6: nested dataclasses at any depth
│   └── value_resolution.py     # Stages 5, 7, 8: @file, append ranges, cli_resolve
├── provenance.py           # Provenance recorder and query API
├── option_collisions.py    # Plans every option string and rejects clashes before registration
├── config_applicator.py    # One-level merge, --config file, property overrides
├── annotations.py          # Field metadata annotations (cli_short, cli_nested, cli_list_merge, ...)
├── type_inspector.py       # Type system utilities
├── file_loading.py         # @file syntax processing
├── utils.py                # Structured file loading, deep_merge, copy_containers
├── instantiate.py          # Object instantiation from config
├── formatter.py            # Help text formatting
├── append_action.py        # Custom argparse append action
└── exceptions.py           # Exception hierarchy
```

## Running Coverage Reports

### Quick Commands

```bash
# Run tests with coverage (automatic via pytest config)
pytest

# Run with HTML report
pytest --cov-report=html
open htmlcov/index.html

# Run specific module coverage
pytest --cov=dataclass_args.builder tests/

# Coverage summary only
pytest --cov=dataclass_args --cov-report=term-missing
```

## Test Organization

```
tests/
├── test_annotations.py             # Annotation functionality
├── test_basic.py                   # Basic configuration building
├── test_boolean_*.py               # Boolean flag handling
├── test_build_config_from_dict.py  # Programmatic dict-based config
├── test_builder_advanced.py        # Builder advanced paths
├── test_cli_append.py              # Append action
├── test_cli_choices.py             # Choice validation
├── test_cli_nested.py              # Nested dataclasses
├── test_cli_override_name.py       # Custom dict override names
├── test_cli_resolve.py             # Post-load field resolution
├── test_cli_short.py               # Short options
├── test_collisions.py              # Collision detection
├── test_config_applicator.py       # Config application
├── test_config_merging_*.py        # Config merging
├── test_description.py             # Help text customization
├── test_file_loading.py            # File loading (@file)
├── test_instantiate.py             # Object instantiation
├── test_nested_help_text.py        # Nested help text
├── test_pep604_union.py            # PEP 604 union type support
├── test_positional.py              # Positional arguments
├── test_type_inspector.py          # Type inspection
└── test_utils.py                   # File format loading
```

## Quality Metrics

- **Test Execution:** Fast (~10s for 1376 tests)
- **Test Reliability:** 100% (no flaky tests)
- **Cognitive Complexity:** All functions CC≤10
- **Test Clarity:** High (class-based organization, one class per concern)
- **Edge Case Coverage:** Comprehensive
- **Integration Tests:** Included
- **Mocking:** Minimal (only for truly untestable paths)

## Continuous Integration

All tests run automatically on:
- Every push
- Every pull request
- Multiple Python versions (3.11, 3.12, 3.13, 3.14)
- Multiple platforms (Linux, macOS, Windows)

---

**Last Updated:** 2026-11-24
**Version:** 1.10.1
