#!/usr/bin/env python3
# Timestamp: 2026-03-13
# File: scitex_app/__init__.py

"""scitex-app — Write-once interface for local + cloud SciTeX apps.

Standalone package. Zero dependencies (pure stdlib).
When used with scitex, integration is automatic via scitex.app.

Public API (3 functions)::

    from scitex_app.sdk import get_files, register_backend, FilesBackend

    # Get a file backend (auto-detects local vs cloud)
    files = get_files("./project")

    # Read/write files
    content = files.read("data/config.yaml")
    files.write("output/result.csv", csv_text)

    # Register a custom backend
    register_backend("s3", my_s3_factory)
"""

from __future__ import annotations

from .sdk import FilesBackend, build_tree, get_files, register_backend


def _resolve_version() -> str:
    """Read version from importlib.metadata, fallback to pyproject.toml."""
    try:
        from importlib.metadata import version

        return version("scitex-app")
    except Exception:
        pass
    try:
        from pathlib import Path
        import re

        toml = Path(__file__).resolve().parent.parent.parent / "pyproject.toml"
        match = re.search(r'version\s*=\s*"([^"]+)"', toml.read_text())
        if match:
            return match.group(1)
    except Exception:
        pass
    return "0.0.0"


__version__ = _resolve_version()

__all__ = [
    "__version__",
    "FilesBackend",
    "get_files",
    "register_backend",
    "build_tree",
    "chat",
    "paths",
    "validator",
]


_LOADING = set()


def __getattr__(name: str):
    """Lazy imports for optional modules (chat, paths, etc.)."""
    if name in _LOADING:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    _LOADING.add(name)
    try:
        if name == "chat":
            from . import _chat

            return _chat
        if name == "paths":
            from . import paths as _paths

            return _paths
        if name == "validator":
            from . import validator as _validator

            return _validator
    finally:
        _LOADING.discard(name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


# EOF
