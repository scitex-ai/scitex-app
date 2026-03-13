#!/usr/bin/env python3
# Timestamp: 2026-03-13
# File: scitex_app/sdk/_cloud_files.py

"""FileVault client — per-app namespaced file storage via REST API.

REST endpoints:
  GET    /platform/api/files/<app>/                 (list root)
  GET    /platform/api/files/<app>/<file_path>      (read file)
  POST   /platform/api/files/<app>/<file_path>      (upload/write)
  DELETE /platform/api/files/<app>/<file_path>       (delete file)
"""

from __future__ import annotations

from typing import Any, List, Optional, Union

from ._client import get_client


def list_files(
    app: str,
    *,
    path: str = "",
    project: Optional[str] = None,
    extensions: Optional[str] = None,
) -> dict:
    """List files in an app's vault."""
    client = get_client()
    params: dict[str, Any] = {}
    if project:
        params["project"] = project
    if extensions:
        params["extensions"] = extensions

    endpoint = f"/platform/api/files/{app}/"
    if path:
        endpoint = f"/platform/api/files/{app}/{path}"
    return client.request("GET", endpoint, params=params)


def download(app: str, file_path: str, *, project: Optional[str] = None) -> dict:
    """Download a file from the vault."""
    client = get_client()
    params: dict[str, Any] = {}
    if project:
        params["project"] = project
    return client.request(
        "GET", f"/platform/api/files/{app}/{file_path}", params=params
    )


def upload(
    app: str,
    file_path: str,
    content: Union[str, bytes],
    *,
    project: Optional[str] = None,
) -> dict:
    """Upload a file to the vault."""
    client = get_client()
    data: dict[str, Any] = {}
    if project:
        data["project"] = project

    if isinstance(content, bytes):
        files = {"file": (file_path.split("/")[-1], content)}
        return client.request(
            "POST", f"/platform/api/files/{app}/{file_path}", data=data, files=files
        )
    else:
        data["content"] = content
        return client.request(
            "POST", f"/platform/api/files/{app}/{file_path}", data=data
        )


def delete(app: str, file_path: str, *, project: Optional[str] = None) -> dict:
    """Delete a file from the vault."""
    client = get_client()
    params: dict[str, Any] = {}
    if project:
        params["project"] = project
    return client.request(
        "DELETE", f"/platform/api/files/{app}/{file_path}", params=params
    )


class CloudFilesBackend:
    """Cloud implementation of FilesBackend — wraps FileVault REST API.

    Parameters
    ----------
    app : str
        App identifier for namespacing files.
    project : str, optional
        Project identifier for scoping.
    """

    def __init__(self, app: str, *, project: Optional[str] = None, **kwargs):
        self._app = app
        self._project = project

    def read(self, path: str, *, binary: bool = False) -> Union[str, bytes]:
        """Read file content via REST API."""
        result = download(self._app, path, project=self._project)
        content = result.get("content", "")
        if binary and isinstance(content, str):
            import base64

            return base64.b64decode(content)
        return content

    def write(self, path: str, content: Union[str, bytes]) -> None:
        """Write content to a file via REST API."""
        upload(self._app, path, content, project=self._project)

    def list(
        self,
        directory: str = "",
        *,
        extensions: Optional[List[str]] = None,
    ) -> List[str]:
        """List file paths in a directory via REST API."""
        ext_str = ",".join(extensions) if extensions else None
        result = list_files(
            self._app, path=directory, project=self._project, extensions=ext_str
        )
        return result.get("files", [])

    def exists(self, path: str) -> bool:
        """Check if a file exists via REST API."""
        try:
            download(self._app, path, project=self._project)
            return True
        except Exception:
            return False

    def delete(self, path: str) -> None:
        """Delete a file via REST API."""
        result = delete(self._app, path, project=self._project)
        if not result.get("success", True):
            raise FileNotFoundError(f"File not found: {path!r}")

    def rename(self, old_path: str, new_path: str) -> None:
        """Rename/move a file via download+upload+delete."""
        content = self.read(old_path, binary=True)
        self.write(new_path, content)
        self.delete(old_path)

    def copy(self, src_path: str, dest_path: str) -> None:
        """Copy a file via download+upload."""
        content = self.read(src_path, binary=True)
        self.write(dest_path, content)

    def __repr__(self) -> str:
        return f"CloudFilesBackend(app={self._app!r})"


def cloud_files_factory(root=None, *, app: str = "", **kwargs):
    """Factory for CloudFilesBackend — used with register_backend."""
    return CloudFilesBackend(app=app or str(root or "default"), **kwargs)


# EOF
