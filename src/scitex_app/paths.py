#!/usr/bin/env python3
# Timestamp: 2026-03-16
# File: scitex_app/paths.py

"""Reusable path resolution for SciTeX apps.

All functions accept an explicit ``base_dir`` to stay Django-agnostic.
When omitted, ``SCITEX_BASE_DIR`` env var is used as fallback.

Directory conventions::

    base_dir/
      data/
        users/<owner>/proj/<repo>/      # user (dev) apps
          manifest.json
          templates/<app_name>/index_partial.html
          static/<app_name>/...
        projects/<slug>/                # published projects
          manifest.json
          ...
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Iterator, Optional, Union

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Base directory resolution
# ---------------------------------------------------------------------------


def get_base_dir(base_dir: Union[str, Path, None] = None) -> Path:
    """Return the SciTeX base directory.

    Priority: explicit argument > ``SCITEX_BASE_DIR`` env var.
    Raises ``ValueError`` if neither is available.
    """
    if base_dir is not None:
        return Path(base_dir).resolve()
    env = os.environ.get("SCITEX_BASE_DIR")
    if env:
        return Path(env).resolve()
    raise ValueError("No base directory: pass base_dir or set SCITEX_BASE_DIR env var")


# ---------------------------------------------------------------------------
# Project directory resolution
# ---------------------------------------------------------------------------


def resolve_user_project_dir(
    owner: str,
    repo: str,
    *,
    base_dir: Union[str, Path, None] = None,
) -> Optional[Path]:
    """Resolve a user's dev-app project directory.

    Returns ``None`` if the directory does not exist.

    Layout: ``base_dir/data/users/<owner>/proj/<repo>/``
    """
    root = get_base_dir(base_dir)
    project_dir = root / "data" / "users" / owner / "proj" / repo
    return project_dir if project_dir.is_dir() else None


def resolve_published_project_dir(
    slug: str,
    *,
    base_dir: Union[str, Path, None] = None,
) -> Optional[Path]:
    """Resolve a published project directory.

    Returns ``None`` if the directory does not exist.

    Layout: ``base_dir/data/projects/<slug>/``
    """
    root = get_base_dir(base_dir)
    project_dir = root / "data" / "projects" / slug
    return project_dir if project_dir.is_dir() else None


# ---------------------------------------------------------------------------
# Manifest
# ---------------------------------------------------------------------------


def resolve_manifest(project_dir: Union[str, Path]) -> dict:
    """Read ``manifest.json`` from a project directory.

    Returns an empty dict if the file does not exist or is invalid.
    """
    manifest_path = Path(project_dir) / "manifest.json"
    if not manifest_path.is_file():
        return {}
    try:
        return json.loads(manifest_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        logger.warning("Failed to read manifest %s: %s", manifest_path, exc)
        return {}


# ---------------------------------------------------------------------------
# Template resolution
# ---------------------------------------------------------------------------


def find_partial_template(
    templates_dir: Union[str, Path],
    filename: str = "index_partial.html",
) -> Optional[Path]:
    """Find a partial template in a templates directory.

    Supports flat layout (``templates/index_partial.html``)
    and nested layout (``templates/<app>/index_partial.html``).
    """
    templates_dir = Path(templates_dir)
    if not templates_dir.is_dir():
        return None
    # Flat layout
    flat = templates_dir / filename
    if flat.is_file():
        return flat
    # Nested layout — first subdirectory containing the file
    for subdir in safe_iterdir(templates_dir):
        if subdir.is_dir():
            nested = subdir / filename
            if nested.is_file():
                return nested
    return None


def resolve_template_dir(
    project_dir: Union[str, Path],
) -> Optional[Path]:
    """Return the templates directory for a project, if it exists."""
    tpl = Path(project_dir) / "templates"
    return tpl if tpl.is_dir() else None


# ---------------------------------------------------------------------------
# Static file resolution
# ---------------------------------------------------------------------------


def resolve_static_dir(
    project_dir: Union[str, Path],
) -> Optional[Path]:
    """Return the static directory for a project, if it exists."""
    static = Path(project_dir) / "static"
    return static if static.is_dir() else None


# ---------------------------------------------------------------------------
# Module name parsing
# ---------------------------------------------------------------------------


def parse_dev_module_name(module_name: str) -> Optional[tuple[str, str]]:
    """Parse ``dev__<owner>__<repo>`` format into ``(owner, repo)``.

    Returns ``None`` if the name does not match the convention.
    """
    if not module_name.startswith("dev__"):
        return None
    parts = module_name.split("__")
    if len(parts) != 3:
        return None
    return parts[1], parts[2]


# ---------------------------------------------------------------------------
# Directory utilities
# ---------------------------------------------------------------------------


def safe_iterdir(directory: Union[str, Path]) -> Iterator[Path]:
    """Iterate directory entries, skipping hidden files and handling errors."""
    try:
        for entry in sorted(Path(directory).iterdir()):
            if entry.name.startswith("."):
                continue
            yield entry
    except (PermissionError, OSError) as exc:
        logger.debug("Cannot iterate %s: %s", directory, exc)


def validate_project_structure(
    project_dir: Union[str, Path],
) -> tuple[bool, str]:
    """Validate that a project directory has the expected structure.

    Returns ``(is_valid, message)``.
    """
    project_dir = Path(project_dir)
    if not project_dir.is_dir():
        return False, f"Directory not found: {project_dir}"
    tpl_dir = project_dir / "templates"
    if not tpl_dir.is_dir():
        return False, f"Missing templates/ directory in {project_dir}"
    if find_partial_template(tpl_dir) is None:
        return False, f"No index_partial.html found in {tpl_dir}"
    return True, "ok"


# EOF
