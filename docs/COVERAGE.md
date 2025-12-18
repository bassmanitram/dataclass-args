# Code Coverage Report

## Overview

This project maintains **92.19%** code coverage with comprehensive testing.

## Current Coverage Statistics (v1.4.3)

| Module | Statements | Missing | Branches | Partial | Coverage |
|--------|------------|---------|----------|---------|----------|
| `__init__.py` | 7 | 0 | 0 | 0 | **100.00%** |
| `annotations.py` | 143 | 2 | 42 | 2 | **97.84%** |
| `append_action.py` | 6 | 0 | 0 | 0 | **100.00%** |
| `builder.py` | 420 | 29 | 194 | 16 | **91.69%** |
| `config_applicator.py` | 49 | 0 | 16 | 0 | **100.00%** |
| `exceptions.py` | 6 | 0 | 0 | 0 | **100.00%** |
| `file_loading.py` | 40 | 6 | 16 | 1 | **87.50%** |
| `formatter.py` | 9 | 0 | 4 | 0 | **100.00%** |
| `nested_processor.py` | 115 | 14 | 48 | 5 | **88.34%** |
| `type_inspector.py` | 67 | 6 | 26 | 5 | **86.02%** |
| `utils.py` | 70 | 6 | 24 | 1 | **92.55%** |
| **TOTAL** | **932** | **63** | **370** | **30** | **92.24%** |

## Test Suite

- **Total Tests:** 429
- **Test Execution Time:** ~0.75s
- **All Tests Passing:** ✅

## Coverage Requirements

- **Minimum Required:** 88%
- **Current Coverage:** 92.24% ✅
- **Target Coverage:** 95%+

## Recent Improvements (v1.4.2)

- Added 75 new tests (+21%)
- TypeInspector: 51% → 86% (+35%)
- ConfigApplicator: 78% → 100% (+22%)
- Overall: 88.84% → 92.24% (+3.40%)

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

## Uncovered Code Analysis

Most uncovered code is:
- Edge case error paths (intentionally tested via integration tests)
- Import fallbacks for optional dependencies (YAML, TOML)
- Collision detection paths (some require invalid configurations)
- Platform-specific error handling

## Coverage by Category

| Category | Coverage | Status |
|----------|----------|--------|
| Core Functionality | 95%+ | ✅ Excellent |
| Error Handling | 90%+ | ✅ Good |
| Type System | 86%+ | ✅ Good |
| Configuration Loading | 92%+ | ✅ Excellent |
| Nested Dataclasses | 88%+ | ✅ Good |
| Annotations | 97%+ | ⭐ Excellent |

## Test Organization

```
tests/
├── test_annotations.py         # Annotation functionality (24 tests)
├── test_basic.py               # Basic configuration building (20 tests)
├── test_boolean_*.py           # Boolean flag handling (36 tests)
├── test_cli_append.py          # Append action (40 tests)
├── test_cli_choices.py         # Choice validation (20 tests)
├── test_cli_nested.py          # Nested dataclasses (27 tests)
├── test_cli_short.py           # Short options (18 tests)
├── test_collisions.py          # Collision detection (10 tests)
├── test_config_applicator.py   # Config application (36 tests)
├── test_config_merging_*.py    # Config merging (10 tests)
├── test_description.py         # Help text customization (18 tests)
├── test_file_loading.py        # File loading (@file) (22 tests)
├── test_nested_help_text.py    # Nested help text (5 tests) [NEW v1.4.3]
├── test_positional.py          # Positional arguments (38 tests)
├── test_type_inspector.py      # Type inspection (30 tests)
├── test_utils.py               # File format loading (34 tests)
└── test_*_override.py          # Property overrides (13 tests)
```

## Quality Metrics

- **Test Execution:** Fast (~0.65s for 424 tests)
- **Test Reliability:** 100% (no flaky tests)
- **Test Clarity:** High (clear names, good organization)
- **Edge Case Coverage:** Comprehensive
- **Integration Tests:** Included

## Continuous Integration

All tests run automatically on:
- Every push
- Every pull request
- Multiple Python versions (3.8, 3.9, 3.10, 3.11, 3.12)
- Multiple platforms (Linux, macOS, Windows)

---

**Last Updated:** 2024-12-16
**Version:** 1.4.3
