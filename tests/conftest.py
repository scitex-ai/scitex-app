#!/usr/bin/env python3
# Timestamp: 2026-05-12
# File: tests/conftest.py

"""Pytest configuration for scitex-app.

Module-import-time coverage wiring (parallel + subprocess support).
`os.environ.setdefault` would be a no-op here because pytest-cov has
already set COVERAGE_FILE to a tmp dir by the time conftest is loaded.
"""
from __future__ import annotations

import os
import sys
import sysconfig
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
_SRC_PATH = _REPO_ROOT / "src"

# Ensure tests import from local source (src/)
if str(_SRC_PATH) in sys.path:
    sys.path.remove(str(_SRC_PATH))
sys.path.insert(0, str(_SRC_PATH))

# Clear cached imports to force reload
_modules_to_clear = [k for k in sys.modules.keys() if k.startswith("scitex_app")]
for _mod in _modules_to_clear:
    del sys.modules[_mod]

# Pin coverage's data file at the repo root and point process_startup
# at our pyproject so child interpreters configure themselves correctly.
os.environ["COVERAGE_PROCESS_START"] = str(_REPO_ROOT / "pyproject.toml")
os.environ["COVERAGE_FILE"] = str(_REPO_ROOT / ".coverage")


def _ensure_subprocess_coverage_shim() -> None:
    """Drop an idempotent `.pth` file in site-packages that auto-starts
    coverage in every child Python interpreter via
    `coverage.process_startup()`.
    """
    purelib = Path(sysconfig.get_paths()["purelib"])
    pth = purelib / "_scitex_app_subprocess_coverage.pth"
    shim = (
        "import os, coverage\n"
        "if os.environ.get('COVERAGE_PROCESS_START'):\n"
        "    coverage.process_startup()\n"
    )
    try:
        if not pth.exists() or pth.read_text() != shim:
            pth.write_text(shim)
    except OSError:
        # site-packages may be read-only (e.g. system Python); silently
        # skip — local dev venvs are writable and that's where this matters.
        pass


_ensure_subprocess_coverage_shim()
