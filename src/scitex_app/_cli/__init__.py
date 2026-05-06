#!/usr/bin/env python3
# Timestamp: 2026-03-13
# File: scitex_app/_cli/__init__.py

"""scitex-app CLI — Command-line interface for scitex-app."""

from ._main import main

__all__ = ["main"]


# audit §4 — inject version into root --help
try:
    from importlib.metadata import version as _v
    main.help = (
        f"scitex-app (v{_v('scitex-app')}) — "
        + (main.help or "").lstrip()
    )
except Exception:
    pass
