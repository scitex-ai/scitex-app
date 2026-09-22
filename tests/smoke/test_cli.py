"""Smoke: the installed CLI launches and serves its happy paths (PS-211).

Subprocess-driven (``sys.executable -m scitex_app``) so this proves the
installed entry point resolves — an in-process import would not.
Hermetic: no network, no credentials, no writes outside tmp dirs.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.smoke


def _run(*argv: str) -> subprocess.CompletedProcess[str]:
    env = dict(os.environ)
    completed = subprocess.run(
        [sys.executable, "-m", "scitex_app", *argv],
        capture_output=True,
        text=True,
        timeout=60,
        env=env,
    )
    return completed


def test_top_level_help_lists_file_commands() -> None:
    # Arrange
    argv = ("--help",)
    # Act
    completed = _run(*argv)
    # Assert
    assert (completed.returncode, "file" in completed.stdout) == (0, True)


def test_file_write_read_exists_roundtrip(tmp_path: Path) -> None:
    # Arrange
    root = str(tmp_path)
    # Act
    wrote = _run("file", "write", "note.txt", "hello-smoke", "--root", root)
    read = _run("file", "read", "note.txt", "--root", root)
    exists = _run("file", "exists", "note.txt", "--root", root)
    # Assert
    assert (
        wrote.returncode,
        read.returncode,
        exists.returncode,
        read.stdout.strip(),
    ) == (0, 0, 0, "hello-smoke")


def test_app_init_dry_run_prints_plan(tmp_path: Path) -> None:
    # Arrange
    target = str(tmp_path / "probe_app")
    # Act
    completed = _run("app", "init", target, "--dry-run")
    # Assert
    assert (completed.returncode, "DRY RUN" in completed.stdout) == (0, True)
