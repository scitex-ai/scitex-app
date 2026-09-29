"""Smoke-test isolation: every CLI subprocess gets a fake home.

``$SCITEX_DIR`` is redirected to a tmp dir so skills paths and runtime
state never touch the developer's real ``~/.scitex``. ``SCITEX_API_TOKEN``
is DELETED (not blanked): ``get_files()`` treats any truthy value —
including a blank string — as "route to cloud", so only an absent var
selects the local backend under test.

No monkeypatch (PA-306): explicit save/restore with try/finally.
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from pathlib import Path

import pytest


@pytest.fixture(autouse=True)
def _isolated_scitex_home(tmp_path: Path) -> Iterator[None]:
    previous = {
        name: os.environ.get(name) for name in ("SCITEX_DIR", "SCITEX_API_TOKEN")
    }
    os.environ["SCITEX_DIR"] = str(tmp_path / "scitex-home")
    os.environ.pop("SCITEX_API_TOKEN", None)
    try:
        yield
    finally:
        for name, value in previous.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value
