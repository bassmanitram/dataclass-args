#!/usr/bin/env python
"""CI Environment Check Script - Diagnoses common CI failures for dataclass-args."""

import subprocess
import sys
from pathlib import Path


def _print_outcome(result):
    """Print the outcome of a finished check command."""
    if result.returncode == 0:
        print(f"✅ PASS")
        if result.stdout:
            print(result.stdout[:500])
        return

    print(f"❌ FAIL (exit code: {result.returncode})")
    if result.stderr:
        print("STDERR:", result.stderr[:500])
    if result.stdout:
        print("STDOUT:", result.stdout[:500])


def run_check(name, command, critical=True):
    """Run a check command and report status."""
    print(f"\n{'='*60}")
    print(f"CHECK: {name}")
    print(f"{'='*60}")
    try:
        result = subprocess.run(
            command, shell=True, capture_output=True, text=True, timeout=30
        )
        _print_outcome(result)
        return result.returncode == 0 or not critical
    except subprocess.TimeoutExpired:
        print(f"⏱️ TIMEOUT")
        return False
    except Exception as e:
        print(f"💥 ERROR: {e}")
        return False


def main():
    """Run all CI environment checks."""
    print("=" * 60)
    print("DATACLASS-CLI CI ENVIRONMENT CHECK")
    print("=" * 60)
    print(f"Python: {sys.version}")
    print(f"Path: {Path.cwd()}")

    checks = [
        (
            "Import dataclass_args",
            "python -c 'import dataclass_args; print(dataclass_args.__version__)'",
        ),
        (
            "Check get_origin/get_args",
            "python -c 'from typing import get_origin, get_args; print(\"typing OK\")'",
        ),
        ("Run pytest discovery", "python -m pytest tests/ --collect-only -q"),
        ("Run basic tests", "python -m pytest tests/test_basic.py -v"),
        ("Run file loading tests", "python -m pytest tests/test_file_loading.py -v"),
        ("Black check", "black --check dataclass_args/ tests/ examples/", False),
        ("isort check", "isort --check-only dataclass_args/ tests/ examples/", False),
        ("mypy check", "mypy dataclass_args/", False),
    ]

    passed = 0
    failed = 0

    for name, command, *args in checks:
        critical = args[0] if args else True
        if run_check(name, command, critical):
            passed += 1
        else:
            failed += 1
            if critical:
                print(f"\n❌ CRITICAL CHECK FAILED: {name}")
                print("Stopping further checks")
                break

    print(f"\n{'='*60}")
    print(f"SUMMARY: {passed} passed, {failed} failed")
    print(f"{'='*60}")

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
