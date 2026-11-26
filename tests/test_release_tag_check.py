"""Tests for scripts/release_tag_check.sh, run against throwaway git repos."""

import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Optional

import pytest

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "release_tag_check.sh"
GIT_MISSING = shutil.which("git") is None

pytestmark = [
    pytest.mark.skipif(GIT_MISSING, reason="git is not available"),
    pytest.mark.skipif(
        sys.platform == "win32", reason="release script runs on Linux runners"
    ),
]

PYPROJECT = '[project]\nname = "demo"\nversion = "{version}"\n'
INIT_FILE = '"""Demo."""\n\n__version__ = "{version}"\n'
CHANGELOG = "# Changelog\n\n## [{version}] - 2026-01-01\n\n- Something\n"
GIT_ENV: Dict[str, str] = {
    "GIT_AUTHOR_NAME": "Test",
    "GIT_AUTHOR_EMAIL": "test@example.com",
    "GIT_COMMITTER_NAME": "Test",
    "GIT_COMMITTER_EMAIL": "test@example.com",
    "GIT_CONFIG_GLOBAL": os.devnull,
    "GIT_CONFIG_SYSTEM": os.devnull,
}


class Repo:
    """A throwaway git repository with release-relevant files."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.git("init", "-q", "-b", "main")

    def git(self, *args: str) -> str:
        """Run git in the repo and return stripped stdout."""
        result = subprocess.run(
            ["git", *args],
            cwd=self.path,
            env={**os.environ, **GIT_ENV},
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout.strip()

    def commit(
        self,
        version: str,
        init_version: Optional[str] = None,
        changelog_version: Optional[str] = None,
        extra_files: Optional[Dict[str, str]] = None,
    ) -> str:
        """Commit the three version files; each may deliberately disagree.

        Uses plumbing commands, so no user git configuration is needed.
        """
        files = {
            "pyproject.toml": PYPROJECT.format(version=version),
            "dataclass_args/__init__.py": INIT_FILE.format(
                version=init_version or version
            ),
            "CHANGELOG.md": CHANGELOG.format(version=changelog_version or version),
            **(extra_files or {}),
        }
        for name, content in files.items():
            target = self.path / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content)
            blob = self.git("hash-object", "-w", name)
            self.git("update-index", "--add", "--cacheinfo", f"100644,{blob},{name}")
        tree = self.git("write-tree")
        parents = ["-p", "HEAD"] if self.has_head() else []
        commit = self.git("commit-tree", tree, *parents, "-m", f"v{version}")
        self.git("update-ref", "HEAD", commit)
        return commit

    def has_head(self) -> bool:
        """Return True once the current branch has at least one commit."""
        probe = subprocess.run(
            ["git", "rev-parse", "-q", "--verify", "HEAD"],
            cwd=self.path,
            env={**os.environ, **GIT_ENV},
            capture_output=True,
        )
        return probe.returncode == 0

    def tag(self, name: str) -> None:
        """Create a tag on HEAD."""
        self.git("tag", name)

    def run(
        self, rev: str = "HEAD", env: Optional[Dict[str, str]] = None
    ) -> "subprocess.CompletedProcess[str]":
        """Run the release check script against a revision."""
        return subprocess.run(
            [str(SCRIPT), rev],
            cwd=self.path,
            env={**os.environ, **GIT_ENV, **(env or {})},
            capture_output=True,
            text=True,
        )


@pytest.fixture
def repo(tmp_path: Path) -> Repo:
    """An empty throwaway git repository."""
    return Repo(tmp_path)


def stdout_lines(result: "subprocess.CompletedProcess[str]") -> List[str]:
    """Return the non-empty stdout lines."""
    return [line for line in result.stdout.splitlines() if line]


def test_unchanged_and_already_tagged_needs_no_tag(repo: Repo) -> None:
    repo.commit("1.2.3")
    repo.tag("v1.2.3")
    repo.commit("1.2.3", extra_files={"other.txt": "unrelated\n"})
    result = repo.run()
    assert result.returncode == 0
    assert stdout_lines(result) == ["tag="]
    assert "already exists" in result.stderr


def test_bump_without_tag_requests_tag(repo: Repo) -> None:
    repo.commit("1.2.3")
    repo.tag("v1.2.3")
    repo.commit("1.2.4")
    result = repo.run()
    assert result.returncode == 0, result.stderr
    assert stdout_lines(result) == ["tag=v1.2.4"]


def test_existing_tag_needs_no_tag(repo: Repo) -> None:
    repo.commit("1.2.3")
    repo.commit("1.2.4")
    repo.tag("v1.2.4")
    result = repo.run()
    assert result.returncode == 0
    assert stdout_lines(result) == ["tag="]
    assert "already exists" in result.stderr


def test_bare_tag_is_ignored(repo: Repo) -> None:
    repo.commit("1.2.3")
    repo.tag("v1.2.3")
    repo.commit("1.2.4")
    repo.tag("1.2.4")
    result = repo.run()
    assert result.returncode == 0, result.stderr
    assert stdout_lines(result) == ["tag=v1.2.4"]


def test_rebase_merge_tags_when_bump_is_not_in_last_commit(repo: Repo) -> None:
    repo.commit("1.2.3")
    repo.tag("v1.2.3")
    repo.commit("1.2.4")
    repo.commit("1.2.4", extra_files={"a.txt": "a\n"})
    repo.commit("1.2.4", extra_files={"b.txt": "b\n"})
    result = repo.run()
    assert result.returncode == 0, result.stderr
    assert stdout_lines(result) == ["tag=v1.2.4"]
    assert "1.2.4 > highest tag v1.2.3" in result.stderr


def test_merge_commit_requests_tag(repo: Repo) -> None:
    repo.commit("1.2.3")
    repo.tag("v1.2.3")
    repo.git("checkout", "-q", "-b", "feature")
    repo.commit("1.2.4")
    repo.git("checkout", "-q", "main")
    repo.commit("1.2.3", extra_files={"other.txt": "unrelated\n"})
    repo.git("merge", "-q", "--no-ff", "-m", "Merge feature", "feature")
    assert len(repo.git("rev-list", "--parents", "-n1", "HEAD").split()) == 3
    result = repo.run()
    assert result.returncode == 0, result.stderr
    assert stdout_lines(result) == ["tag=v1.2.4"]


def test_untagged_unchanged_version_is_tagged_to_recover(repo: Repo) -> None:
    repo.commit("1.2.3")
    repo.tag("v1.2.3")
    repo.commit("1.2.4")
    repo.commit("1.2.4", extra_files={"other.txt": "unrelated\n"})
    result = repo.run()
    assert stdout_lines(result) == ["tag=v1.2.4"]


def test_first_release_requests_tag(repo: Repo) -> None:
    repo.commit("1.2.3")
    result = repo.run()
    assert result.returncode == 0, result.stderr
    assert stdout_lines(result) == ["tag=v1.2.3"]
    assert "first release" in result.stderr


def test_single_tagged_commit_needs_no_tag(repo: Repo) -> None:
    repo.commit("1.2.3")
    repo.tag("v1.2.3")
    result = repo.run()
    assert result.returncode == 0
    assert stdout_lines(result) == ["tag="]


def test_init_version_mismatch_fails(repo: Repo) -> None:
    repo.commit("1.2.3")
    repo.tag("v1.2.3")
    repo.commit("1.2.4", init_version="1.2.3")
    result = repo.run()
    assert result.returncode == 1
    assert "tag=" not in result.stdout
    assert "1.2.4" in result.stderr and "1.2.3" in result.stderr
    assert "__version__" in result.stderr


def test_missing_changelog_heading_fails(repo: Repo) -> None:
    repo.commit("1.2.3")
    repo.tag("v1.2.3")
    repo.commit("1.2.4", changelog_version="1.2.3")
    result = repo.run()
    assert result.returncode == 1
    assert "CHANGELOG.md" in result.stderr and "1.2.4" in result.stderr


def test_changelog_heading_dots_are_literal(repo: Repo) -> None:
    repo.commit("1.2.3")
    repo.tag("v1.2.3")
    repo.commit("1.2.4", changelog_version="1x2x4")
    assert repo.run().returncode == 1


def test_downgrade_below_highest_tag_fails(repo: Repo) -> None:
    repo.commit("2.0.0")
    repo.tag("v2.0.0")
    repo.commit("1.2.4")
    result = repo.run()
    assert result.returncode == 1
    assert "tag=" not in result.stdout
    assert "v2.0.0" in result.stderr and "1.2.4" in result.stderr
    assert "tags must increase" in result.stderr


def test_untagged_version_lower_than_highest_tag_fails(repo: Repo) -> None:
    repo.commit("1.9.0")
    repo.commit("1.10.0")
    repo.tag("v1.10.0")
    repo.commit("1.9.1")
    repo.commit("1.9.1", extra_files={"other.txt": "unrelated\n"})
    result = repo.run()
    assert result.returncode == 1
    assert "v1.10.0" in result.stderr


def test_version_comparison_is_numeric_not_lexicographic(repo: Repo) -> None:
    repo.commit("1.9.0")
    repo.tag("v1.9.0")
    repo.commit("1.10.0")
    result = repo.run()
    assert result.returncode == 0, result.stderr
    assert stdout_lines(result) == ["tag=v1.10.0"]


@pytest.mark.parametrize("version", ["1.2.4rc1", "1.2", "1.2.4.1", "v1.2.4"])
def test_non_numeric_version_fails(repo: Repo, version: str) -> None:
    repo.commit("1.2.3")
    repo.tag("v1.2.3")
    repo.commit(version)
    result = repo.run()
    assert result.returncode == 1
    assert "MAJOR.MINOR.PATCH" in result.stderr and version in result.stderr


def test_non_release_tags_do_not_affect_monotonic_check(repo: Repo) -> None:
    repo.commit("1.2.3")
    repo.tag("v1.2.3")
    repo.tag("vnext")
    repo.tag("v9.9.9rc1")
    repo.commit("1.2.4")
    result = repo.run()
    assert result.returncode == 0, result.stderr
    assert stdout_lines(result) == ["tag=v1.2.4"]


def test_writes_github_output(repo: Repo, tmp_path: Path) -> None:
    repo.commit("1.2.3")
    repo.tag("v1.2.3")
    repo.commit("1.2.4")
    output = tmp_path / "github_output"
    result = repo.run(env={"GITHUB_OUTPUT": str(output)})
    assert result.returncode == 0, result.stderr
    lines = output.read_text().splitlines()
    assert lines[0] == "tag=v1.2.4"
    assert lines[1].startswith("reason=")


def test_unknown_revision_fails(repo: Repo) -> None:
    repo.commit("1.2.3")
    result = repo.run("does-not-exist")
    assert result.returncode == 1
    assert "unknown commit" in result.stderr


def test_missing_argument_is_usage_error(repo: Repo) -> None:
    repo.commit("1.2.3")
    result = subprocess.run(
        [str(SCRIPT)], cwd=repo.path, capture_output=True, text=True
    )
    assert result.returncode == 2
    assert "usage" in result.stderr
