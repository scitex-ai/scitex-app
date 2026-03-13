#!/usr/bin/env python3
# Timestamp: 2026-03-13
# File: scitex_app/sdk/_filesystem.py

"""FileSystem backend — local-disk implementation of FilesBackend."""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import List, Optional, Union


class FileSystemBackend:
    """Local filesystem implementation of FilesBackend.

    All paths are relative to a root directory. Path traversal
    outside root is prevented.

    Parameters
    ----------
    root : str or Path
        Root directory for all file operations.
    """

    def __init__(self, root: Union[str, Path]) -> None:
        self._root = Path(root).resolve()

    @property
    def root(self) -> Path:
        """Root directory."""
        return self._root

    def _resolve(self, path: str) -> Path:
        """Resolve relative path, preventing traversal attacks."""
        resolved = (self._root / path.lstrip("/")).resolve()
        if not str(resolved).startswith(str(self._root)):
            raise ValueError(f"Path traversal detected: {path!r}")
        return resolved

    def read(self, path: str, *, binary: bool = False) -> Union[str, bytes]:
        """Read file content."""
        target = self._resolve(path)
        if not target.exists():
            raise FileNotFoundError(f"File not found: {path!r}")
        if binary:
            return target.read_bytes()
        return target.read_text(encoding="utf-8")

    def write(self, path: str, content: Union[str, bytes]) -> None:
        """Write content to a file, creating parent dirs as needed."""
        target = self._resolve(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(content, bytes):
            target.write_bytes(content)
        else:
            target.write_text(content, encoding="utf-8")

    def list(
        self,
        directory: str = "",
        *,
        extensions: Optional[List[str]] = None,
    ) -> List[str]:
        """List file paths in a directory."""
        target = self._resolve(directory) if directory else self._root
        if not target.exists():
            return []
        results = []
        for item in sorted(target.iterdir()):
            if item.is_file():
                if extensions and item.suffix.lower() not in extensions:
                    continue
                results.append(str(item.relative_to(self._root)))
        return results

    def exists(self, path: str) -> bool:
        """Check if a file exists."""
        return self._resolve(path).exists()

    def delete(self, path: str) -> None:
        """Delete a file."""
        target = self._resolve(path)
        if not target.exists():
            raise FileNotFoundError(f"File not found: {path!r}")
        target.unlink()

    def rename(self, old_path: str, new_path: str) -> None:
        """Rename/move a file."""
        old = self._resolve(old_path)
        new = self._resolve(new_path)
        if not old.exists():
            raise FileNotFoundError(f"File not found: {old_path!r}")
        if new.exists():
            raise FileExistsError(f"File already exists: {new_path!r}")
        new.parent.mkdir(parents=True, exist_ok=True)
        old.rename(new)

    def copy(self, src_path: str, dest_path: str) -> None:
        """Copy a file."""
        src = self._resolve(src_path)
        dest = self._resolve(dest_path)
        if not src.exists():
            raise FileNotFoundError(f"File not found: {src_path!r}")
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dest)

    def __repr__(self) -> str:
        return f"FileSystemBackend({self._root})"


# EOF
