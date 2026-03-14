#!/usr/bin/env python3
# Timestamp: 2026-03-15
# File: scitex_app/sdk/_tree.py

"""Tree builder utility for FilesBackend.

Converts flat file listings into nested directory tree structures.
Reusable by any app that needs a file browser UI.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional


def build_tree(
    backend: Any,
    directory: str = "",
    *,
    extensions: Optional[List[str]] = None,
    skip_hidden: bool = True,
    max_depth: int = 10,
) -> List[Dict[str, Any]]:
    """Build a nested tree structure from a FilesBackend.

    Parameters
    ----------
    backend : FilesBackend
        A file storage backend implementing the FilesBackend protocol.
    directory : str
        Starting directory (relative to backend root). Default: root.
    extensions : list of str, optional
        Filter files by extension (e.g., [".yaml", ".png"]).
        Directories are always included for traversal.
    skip_hidden : bool
        Skip files/directories starting with ".". Default: True.
    max_depth : int
        Maximum recursion depth to prevent runaway traversal. Default: 10.

    Returns
    -------
    list of dict
        Nested tree structure::

            [
                {"path": "subdir", "name": "subdir", "type": "directory",
                 "children": [...]},
                {"path": "file.yaml", "name": "file.yaml", "type": "file"},
            ]
    """
    if max_depth <= 0:
        return []

    # Get all entries in this directory
    entries = _list_entries(backend, directory)
    items = []

    for entry in entries:
        name = Path(entry["path"]).name

        if skip_hidden and name.startswith("."):
            continue

        if entry["type"] == "directory":
            children = build_tree(
                backend,
                entry["path"],
                extensions=extensions,
                skip_hidden=skip_hidden,
                max_depth=max_depth - 1,
            )
            if children:  # only include non-empty directories
                items.append(
                    {
                        "path": entry["path"],
                        "name": name,
                        "type": "directory",
                        "children": children,
                    }
                )
        else:
            # Apply extension filter to files
            if extensions:
                suffix = Path(name).suffix.lower()
                if suffix not in extensions:
                    continue
            items.append(
                {
                    "path": entry["path"],
                    "name": name,
                    "type": "file",
                }
            )

    # Sort: directories first, then alphabetically
    items.sort(key=lambda x: (x["type"] != "directory", x["name"].lower()))
    return items


def _list_entries(
    backend: Any,
    directory: str = "",
) -> List[Dict[str, str]]:
    """List directory entries with type information.

    Tries backend.list_entries() first (if available, returns files + dirs).
    Falls back to backend.list() for files and attempts directory discovery.
    """
    # Preferred: backend supports list_entries() returning typed entries
    if hasattr(backend, "list_entries"):
        return backend.list_entries(directory)

    # Fallback: use list() for files, try to discover directories
    # via the backend's internal structure
    if hasattr(backend, "_root"):
        # FileSystemBackend — access pathlib directly for directory info
        root = backend._root
        target = (root / directory) if directory else root
        if not target.is_dir():
            return []
        entries = []
        for item in sorted(target.iterdir(), key=lambda x: x.name.lower()):
            rel = str(item.relative_to(root))
            if item.is_dir():
                entries.append({"path": rel, "type": "directory"})
            elif item.is_file():
                entries.append({"path": rel, "type": "file"})
        return entries

    # Last resort: list() returns only files, no directory info
    files = backend.list(directory)
    return [{"path": f, "type": "file"} for f in files]


# EOF
