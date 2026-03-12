#!/usr/bin/env python3
# Timestamp: 2026-03-13
# File: scitex_app/sdk/_protocol.py

"""FilesBackend protocol — structural typing for pluggable storage."""

from __future__ import annotations

from typing import List, Optional, Protocol, Union, runtime_checkable


@runtime_checkable
class FilesBackend(Protocol):
    """File storage backend protocol.

    Implementations must provide these 7 methods.
    Uses ``typing.Protocol`` for structural subtyping — backends
    just implement the methods, no inheritance required.

    Implementations
    ---------------
    - ``FileSystemBackend`` — local pathlib (ships with scitex-app)
    - ``CloudFilesBackend`` — HTTP via scitex_cloud (provided at runtime)
    """

    def read(self, path: str, *, binary: bool = False) -> Union[str, bytes]:
        """Read file content.

        Parameters
        ----------
        path : str
            Relative path within the backend's namespace.
        binary : bool
            If True, return bytes; otherwise return str.

        Raises
        ------
        FileNotFoundError
            If the file does not exist.
        """
        ...

    def write(self, path: str, content: Union[str, bytes]) -> None:
        """Write content to a file, creating parent dirs as needed.

        Parameters
        ----------
        path : str
            Relative path within the backend's namespace.
        content : str or bytes
            Text or binary content.
        """
        ...

    def list(
        self,
        directory: str = "",
        *,
        extensions: Optional[List[str]] = None,
    ) -> List[str]:
        """List file paths in a directory.

        Parameters
        ----------
        directory : str
            Relative directory path ("" = root).
        extensions : list of str, optional
            Filter by extension, e.g. [".yaml", ".png"].

        Returns
        -------
        list of str
            Relative file paths.
        """
        ...

    def exists(self, path: str) -> bool:
        """Check if a file exists."""
        ...

    def delete(self, path: str) -> None:
        """Delete a file.

        Raises
        ------
        FileNotFoundError
            If the file does not exist.
        """
        ...

    def rename(self, old_path: str, new_path: str) -> None:
        """Rename/move a file within the namespace.

        Raises
        ------
        FileNotFoundError
            If old_path does not exist.
        FileExistsError
            If new_path already exists.
        """
        ...

    def copy(self, src_path: str, dest_path: str) -> None:
        """Copy a file within the namespace.

        Raises
        ------
        FileNotFoundError
            If src_path does not exist.
        """
        ...


# EOF
