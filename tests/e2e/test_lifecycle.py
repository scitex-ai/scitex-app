"""E2E: full app lifecycle against real subsystems (PS-212).

Two workflows, no network beyond loopback, no credentials beyond tmp
files: (1) the SDK file lifecycle on a real directory — write, read,
list, exists, rename, copy, delete; (2) scaffold-then-validate through
the real CLI — ``app init`` writes a real app tree, ``app validate``
grades it to completion.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.e2e


def test_sdk_file_lifecycle_on_real_directory(tmp_path: Path) -> None:
    # Arrange
    from scitex_app.sdk import get_files

    files = get_files(str(tmp_path))
    # Act
    files.write("data/a.txt", "lifecycle")
    content = files.read("data/a.txt")
    listed_before = files.list("data")
    found_before = files.exists("data/a.txt")
    files.rename("data/a.txt", "data/b.txt")
    files.copy("data/b.txt", "data/c.txt")
    listed_after = sorted(files.list("data"))
    files.delete("data/b.txt")
    gone = files.exists("data/b.txt")
    kept = files.exists("data/c.txt")
    # Assert
    assert (content, listed_before, found_before, listed_after, gone, kept) == (
        "lifecycle",
        ["data/a.txt"],
        True,
        ["data/b.txt", "data/c.txt"],
        False,
        True,
    )


def test_scaffold_then_validate_completes(tmp_path: Path) -> None:
    # Arrange
    target = str(tmp_path / "e2e_app")
    argv = [sys.executable, "-m", "scitex_app"]
    # Act
    init = subprocess.run(
        [*argv, "app", "init", target, "--name", "e2e_app", "-y"],
        capture_output=True,
        text=True,
        timeout=120,
    )
    validate = subprocess.run(
        [*argv, "app", "validate", target],
        capture_output=True,
        text=True,
        timeout=120,
    )
    created = sorted(p.name for p in Path(target).rglob("*") if p.is_file())
    # Assert
    assert (init.returncode, validate.returncode in (0, 1), bool(created)) == (
        0,
        True,
        True,
    )
