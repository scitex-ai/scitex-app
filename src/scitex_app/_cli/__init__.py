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

# audit-cli §1a — packages with _skills/ MUST expose
# `<cli> skills {list,get,install}`.
from ._skills import skills_group as _skills_group

main.add_command(_skills_group, name="skills")
