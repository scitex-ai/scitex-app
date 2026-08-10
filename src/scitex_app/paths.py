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
# Containment
#
# These helpers are the whole reason this module can be handed
# attacker-influenced text. Every function below that joins a caller-supplied
# string onto a root goes through them; nothing here trusts its caller to have
# sanitised anything first.
#
# BOTH checks are required, and neither replaces the other:
#
#   * Segment validation alone would miss a symlink planted inside the root.
#   * Containment alone would miss CROSS-TENANT reach, because
#     ``owner="alice/../bob"`` resolves to another tenant's directory that is
#     still *inside* the base dir -- a root-containment check happily returns
#     it. Measured 2026-08-03: owner="alice", repo="../../bob/proj/bobrepo"
#     returned bob's real project directory.
#
# Refusing the input SHAPE is also cheaper and stricter than catching the
# escape after the join: a rejected segment never reaches ``stat``.
# ---------------------------------------------------------------------------


#: Rejected inside a single component. ``os.altsep`` is included so a
#: Windows-style ``a\b`` is refused on POSIX too -- the value may have been
#: produced on another platform, and a component is never a path.
_SEPARATOR_CHARS = frozenset({os.sep, os.altsep, "/", "\\", "\0"} - {None})


def _is_safe_segment(segment: object) -> bool:
    """Return ``True`` if ``segment`` is usable as ONE path component.

    Refuses a non-string, the empty string, ``.``/``..``, an absolute form,
    anything containing a separator or NUL, and non-printable characters --
    the last because a name that reaches a log would otherwise be able to
    inject control sequences into it.
    """
    if not isinstance(segment, str) or not segment:
        return False
    if segment in (os.curdir, os.pardir):
        return False
    if not segment.isprintable():
        return False
    if _SEPARATOR_CHARS.intersection(segment):
        return False
    # Belt and braces: the separator check already covers POSIX. An absolute
    # segment is the specific hazard behind pathlib's join semantics --
    # Path('/a/b') / '/etc' == Path('/etc'), silently DISCARDING the root it
    # was supposed to be joined onto.
    return not Path(segment).is_absolute()


def _contained(candidate: Path, root: Path) -> Optional[Path]:
    """Return ``candidate`` if it stays inside ``root``, else ``None``.

    Containment is decided on fully RESOLVED paths -- never by a string prefix
    match, because ``/x/proj`` is a string prefix of the unrelated sibling
    ``/x/proj-secret``. Resolving first also collapses symlinks, so a link
    planted inside ``root`` cannot be used to step outside it.

    The ORIGINAL ``candidate`` is returned, not its resolved form, so callers
    keep the path they asked for.
    """
    resolved = candidate.resolve()
    root_resolved = root.resolve()
    if resolved != root_resolved and root_resolved not in resolved.parents:
        return None
    return candidate


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

    Layout: ``base_dir/data/users/<owner>/proj/<repo>/``

    ``owner`` and ``repo`` are validated as single components and the result is
    asserted to stay under the users tree, so this is safe for ANY caller. It
    previously depended on Django's ``<str:>`` URL converter excluding ``/`` --
    a property of the ROUTING layer, not of this function, which a CLI caller,
    an embedding service, or a future ``<path:>`` route does not have.

    Returns ``None`` if the directory does not exist OR if the request was
    refused. Refusal is logged; it is not silent.
    """
    root = get_base_dir(base_dir)
    if not (_is_safe_segment(owner) and _is_safe_segment(repo)):
        logger.warning(
            "Refused unsafe project request: owner=%r repo=%r", owner, repo
        )
        return None
    users_root = root / "data" / "users"
    project_dir = _contained(users_root / owner / "proj" / repo, users_root)
    if project_dir is None:
        logger.warning(
            "Refused project escaping the users tree: owner=%r repo=%r", owner, repo
        )
        return None
    return project_dir if project_dir.is_dir() else None


def resolve_published_project_dir(
    slug: str,
    *,
    base_dir: Union[str, Path, None] = None,
) -> Optional[Path]:
    """Resolve a published project directory.

    Layout: ``base_dir/data/projects/<slug>/``

    ``slug`` is validated and contained exactly as ``owner``/``repo`` are in
    :func:`resolve_user_project_dir`. It carried the IDENTICAL defect and was
    reachable the same way; fixing only the user path would have left this as
    the remaining way in.

    Returns ``None`` if the directory does not exist OR if the request was
    refused. Refusal is logged; it is not silent.
    """
    root = get_base_dir(base_dir)
    if not _is_safe_segment(slug):
        logger.warning("Refused unsafe published project request: slug=%r", slug)
        return None
    projects_root = root / "data" / "projects"
    project_dir = _contained(projects_root / slug, projects_root)
    if project_dir is None:
        logger.warning("Refused published project escaping its tree: slug=%r", slug)
        return None
    return project_dir if project_dir.is_dir() else None


# ---------------------------------------------------------------------------
# Manifest
# ---------------------------------------------------------------------------


def resolve_manifest(project_dir: Union[str, Path]) -> dict:
    """Read ``manifest.json`` from a project directory.

    Returns an empty dict if the file does not exist or is invalid.
    """
    project_dir = Path(project_dir)
    manifest_path = _contained(project_dir / "manifest.json", project_dir)
    if manifest_path is None:
        logger.warning("Refused manifest escaping its project dir: %s", project_dir)
        return {}
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

    ``filename`` is caller-supplied, so it is validated as a single component:
    a traversal filename would otherwise read any file on the host. Both the
    flat and nested results are contained, so a symlinked SUBDIRECTORY cannot
    serve a template from outside the templates tree either.
    """
    templates_dir = Path(templates_dir)
    if not _is_safe_segment(filename):
        logger.warning("Refused unsafe template filename: %r", filename)
        return None
    if not templates_dir.is_dir():
        return None
    # Flat layout
    flat = _contained(templates_dir / filename, templates_dir)
    if flat is not None and flat.is_file():
        return flat
    # Nested layout — first subdirectory containing the file
    for subdir in safe_iterdir(templates_dir):
        if not subdir.is_dir():
            continue
        nested = _contained(subdir / filename, templates_dir)
        if nested is None:
            logger.warning("Skipped template subdir escaping its tree: %s", subdir)
            continue
        if nested.is_file():
            return nested
    return None


def resolve_template_dir(
    project_dir: Union[str, Path],
) -> Optional[Path]:
    """Return the templates directory for a project, if it exists.

    ``None`` when it does not exist, and also when it resolves OUTSIDE the
    project directory -- a symlinked ``templates/`` is how one tenant's
    project would otherwise serve another's files.
    """
    project_dir = Path(project_dir)
    tpl = _contained(project_dir / "templates", project_dir)
    if tpl is None:
        logger.warning("Refused templates dir escaping its project: %s", project_dir)
        return None
    return tpl if tpl.is_dir() else None


# ---------------------------------------------------------------------------
# Static file resolution
# ---------------------------------------------------------------------------


def resolve_static_dir(
    project_dir: Union[str, Path],
) -> Optional[Path]:
    """Return the static directory for a project, if it exists.

    Contained exactly like :func:`resolve_template_dir`; a symlinked
    ``static/`` is the same cross-tenant read by another name.
    """
    project_dir = Path(project_dir)
    static = _contained(project_dir / "static", project_dir)
    if static is None:
        logger.warning("Refused static dir escaping its project: %s", project_dir)
        return None
    return static if static.is_dir() else None


# ---------------------------------------------------------------------------
# Module name parsing
# ---------------------------------------------------------------------------


def parse_dev_module_name(module_name: str) -> Optional[tuple[str, str]]:
    """Parse ``dev__<owner>__<repo>`` format into ``(owner, repo)``.

    Returns ``None`` if the name does not match the convention -- which now
    INCLUDES a structurally valid name whose components are not usable as
    directory names (``dev__../../etc__x``, ``dev__a/b__c``, ``dev__/abs__c``,
    ``dev____x``). Those were previously returned to the caller, who then
    joined them onto a filesystem root.

    Rejection returns ``None`` rather than raising, because ``None`` is this
    function's existing "not a dev module" answer and every caller already
    handles it -- a parser that raises would turn a probe into a 500. The
    rejection is LOGGED rather than silent, with ``%r`` so a hostile name
    cannot inject control characters into the log line.
    """
    if not isinstance(module_name, str) or not module_name.startswith("dev__"):
        return None
    parts = module_name.split("__")
    if len(parts) != 3:
        return None
    owner, repo = parts[1], parts[2]
    if not (_is_safe_segment(owner) and _is_safe_segment(repo)):
        logger.warning("Rejected dev module name %r", module_name)
        return None
    return owner, repo


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
