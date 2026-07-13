"""Optional-dependency extras must be all-or-nothing and never empty.

Operator directive (2026-07-13, prompted by scitex-writer PR #322):
a fine-grained extra that goes empty silently turns "pip install
pkg[X]" into a no-op that looks like a fix but installs nothing --
worse than no hint, since the user believes they already tried it.
One `[all]` extra covers everything user-facing; `dev`/`docs` stay
separate since those are for BUILDING the package, not using it.
"""

from __future__ import annotations

import re
import subprocess
import tomllib
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent.parent


@pytest.fixture
def pyproject_data():
    text = (REPO_ROOT / "pyproject.toml").read_text()
    return tomllib.loads(text)


def test_no_optional_dependency_group_is_empty(pyproject_data):
    # Arrange
    extras = pyproject_data["project"]["optional-dependencies"]
    # Act
    empty = [name for name, deps in extras.items() if not deps]
    # Assert
    assert empty == []


def test_all_extra_exists(pyproject_data):
    # Arrange
    extras = pyproject_data["project"]["optional-dependencies"]
    # Act
    # Assert
    assert "all" in extras


def test_only_all_dev_docs_extras_declared(pyproject_data):
    # Arrange
    extras = pyproject_data["project"]["optional-dependencies"]
    # Act
    # Assert
    assert set(extras) == {"all", "dev", "docs"}


_THIS_FILE = Path(__file__).resolve()
_SCANNED_SUFFIXES = {".py", ".md", ".rst", ".toml", ".yml", ".yaml"}
# CHANGELOG.md narrates past incidents/fixes in prose and will keep
# needing to describe this exact bracket-extra pattern as an example --
# excluded so a historical mention is never mistaken for a live hint.
_EXCLUDED_PATHS = {"CHANGELOG.md"}


def _tracked_files() -> list[Path]:
    """Git-tracked files only -- ignores build artifacts / local exports
    (e.g. sphinx `_build`, skill-doc mirrors) that never ship in the repo.
    """
    out = subprocess.run(
        ["git", "-C", str(REPO_ROOT), "ls-files"],
        capture_output=True,
        text=True,
        check=True,
    )
    return [REPO_ROOT / line for line in out.stdout.splitlines() if line]


def _referenced_extras_in_repo() -> set[str]:
    """Every real `scitex-app[<extra>]` reference in tracked source/docs.

    Excludes this file itself: its own docstring/comments use `[X]` as
    a placeholder when explaining the pattern, not a real instruction.
    """
    pattern = re.compile(r"scitex-app\[([\w-]+)\]")
    found: set[str] = set()
    for path in _tracked_files():
        if path.resolve() == _THIS_FILE or path.suffix not in _SCANNED_SUFFIXES:
            continue
        if path.name in _EXCLUDED_PATHS:
            continue
        try:
            text = path.read_text(errors="ignore")
        except OSError:
            continue
        found.update(pattern.findall(text))
    return found


def test_every_referenced_extra_is_a_real_non_empty_extra(pyproject_data):
    # Arrange
    extras = pyproject_data["project"]["optional-dependencies"]
    referenced = _referenced_extras_in_repo()
    # Act
    broken = [name for name in referenced if name not in extras or not extras[name]]
    # Assert
    assert broken == []
