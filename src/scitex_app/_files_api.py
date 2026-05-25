#!/usr/bin/env python3
# Timestamp: 2026-05-12
# File: scitex_app/_files_api.py

"""Flat module-level wrappers around `FilesBackend` operations.

These mirror the package's MCP tool surface (`app_read_file`,
`app_write_file`, …) so users have a single-call Python API that
matches what MCP exposes — closing the API↔MCP parity check
(§6) and giving users a more discoverable surface for one-off
file operations than `get_files(root).read(path)`.

Each wrapper resolves the backend via :func:`scitex_app.sdk.get_files`
on every call, so it honours the same auto-detection rules
(``SCITEX_API_TOKEN`` for cloud, filesystem otherwise) and stays
in lock-step with whatever backend the caller has registered.

Heavy file shims (binary handling, traversal safety) live on the
backend; this module is intentionally thin.
"""

from __future__ import annotations

from pathlib import Path
from typing import List, Optional, Union

from .sdk import get_files


def read_file(
    path: str,
    *,
    root: Union[str, Path] = ".",
    binary: bool = False,
) -> Union[str, bytes]:
    """Read a single file via the resolved :class:`FilesBackend`.

    Equivalent to ``get_files(root).read(path, binary=binary)``;
    mirrors the ``app_read_file`` MCP tool.
    """
    return get_files(root).read(path, binary=binary)


def write_file(
    path: str,
    content: Union[str, bytes],
    *,
    root: Union[str, Path] = ".",
) -> None:
    """Write a file via the resolved :class:`FilesBackend`.

    Mirrors the ``app_write_file`` MCP tool.
    """
    get_files(root).write(path, content)


def list_files(
    directory: str = "",
    *,
    root: Union[str, Path] = ".",
    extensions: Optional[List[str]] = None,
) -> List[str]:
    """List file paths under *directory*.

    Mirrors the ``app_list_files`` MCP tool.
    """
    return get_files(root).list(directory, extensions=extensions)


def file_exists(path: str, *, root: Union[str, Path] = ".") -> bool:
    """Return whether *path* exists in the resolved backend.

    Mirrors the ``app_file_exists`` MCP tool.
    """
    return get_files(root).exists(path)


def delete_file(path: str, *, root: Union[str, Path] = ".") -> None:
    """Delete *path* in the resolved backend.

    Mirrors the ``app_delete_file`` MCP tool.
    """
    get_files(root).delete(path)


def copy_file(
    src_path: str,
    dest_path: str,
    *,
    root: Union[str, Path] = ".",
) -> None:
    """Copy *src_path* to *dest_path* within the resolved backend.

    Mirrors the ``app_copy_file`` MCP tool.
    """
    get_files(root).copy(src_path, dest_path)


def rename_file(
    old_path: str,
    new_path: str,
    *,
    root: Union[str, Path] = ".",
) -> None:
    """Rename *old_path* to *new_path* within the resolved backend.

    Mirrors the ``app_rename_file`` MCP tool.
    """
    get_files(root).rename(old_path, new_path)


def scaffold(
    target_dir: Union[str, Path] = ".",
    *,
    name: Optional[str] = None,
    label: Optional[str] = None,
    icon: str = "fas fa-puzzle-piece",
    description: str = "",
    frontend: str = "html",
    overwrite: bool = False,
) -> List[Path]:
    """Generate a new SciTeX workspace app skeleton.

    Mirrors the ``app_scaffold`` MCP tool. Auto-appends ``_app`` /
    ``-app`` to *name* (matching the MCP tool's behaviour) so
    Python and MCP callers see the same result for the same inputs.
    """
    from .appmaker import init_app

    target = Path(target_dir).resolve()
    app_name = name or target.name

    if not (app_name.endswith("_app") or app_name.endswith("-app")):
        sep = "-" if "-" in app_name else "_"
        app_name = f"{app_name}{sep}app"

    return init_app(
        target_dir=target,
        name=app_name,
        label=label or "",
        icon=icon,
        description=description,
        overwrite=overwrite,
        frontend_type=frontend,
    )


def validate(app_dir: Union[str, Path] = ".") -> List[str]:
    """Audit a SciTeX app for cloud-submission readiness.

    Mirrors the ``app_validate`` MCP tool. Returns the list of
    errors (empty when the app is ready).
    """
    from .appmaker import validate as _validate

    return _validate(app_dir)


__all__ = [
    "read_file",
    "write_file",
    "list_files",
    "file_exists",
    "delete_file",
    "copy_file",
    "rename_file",
    "scaffold",
    "validate",
]


# EOF
