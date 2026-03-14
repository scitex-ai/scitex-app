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

__all__ = [
    "FilesBackend",
    "get_files",
    "register_backend",
    "build_tree",
]

# EOF
