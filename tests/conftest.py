"""Shared pytest fixtures."""

import os
from pathlib import Path

import pytest


@pytest.fixture
def fake_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Redirect ``~`` to ``tmp_path`` on every platform.

    POSIX ``expanduser`` reads ``HOME``; Windows reads ``USERPROFILE`` and then
    ``HOMEDRIVE`` + ``HOMEPATH``, ignoring ``HOME``. All four are set.
    """
    drive, tail = os.path.splitdrive(str(tmp_path))
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    monkeypatch.setenv("HOMEDRIVE", drive)
    monkeypatch.setenv("HOMEPATH", tail)
    return tmp_path
