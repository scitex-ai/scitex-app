#!/usr/bin/env python3
# Timestamp: 2026-03-13
# File: scitex_app/sdk/__init__.py

"""App SDK — write-once interface for local + cloud SciTeX apps.

Usage (standalone / local):
    from scitex_app.sdk import get_files

    files = get_files("./my_project")
    content = files.read("recipes/my_recipe.yaml")
    files.write("output/result.png", png_bytes)

Usage (cloud, auto-detected via SCITEX_API_TOKEN):
    files = get_files()  # routes through cloud REST API

Usage (remote local, via SCITEX_API_URL):
    import os
    os.environ["SCITEX_API_TOKEN"] = "your-token"
    os.environ["SCITEX_API_URL"] = "https://scitex.ai"
    files = get_files()  # routes to remote cloud
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Callable, Dict, Optional, Union

from ._protocol import FilesBackend

# Backend registry: name -> factory callable
_registry: Dict[str, Callable[..., FilesBackend]] = {}


def register_backend(name: str, factory: Callable[..., FilesBackend]) -> None:
    """Register a files backend factory.

    Parameters
    ----------
    name : str
        Backend identifier (e.g., "cloud", "s3").
    factory : callable
        Callable(root, **kwargs) -> FilesBackend instance.
    """
    _registry[name] = factory


def get_files(
    root: Optional[Union[str, Path]] = None,
    *,
    backend: Optional[str] = None,
    **kwargs: Any,
) -> FilesBackend:
    """Get a files backend instance.

    Auto-detection logic:
    1. If ``backend`` is specified, use that.
    2. If ``SCITEX_API_TOKEN`` env var is set and "cloud" backend
       is registered, use cloud.
    3. Otherwise, use filesystem (default).

    Parameters
    ----------
    root : str or Path, optional
        Root directory for filesystem backend. Defaults to cwd.
    backend : str, optional
        Explicit backend name. If None, auto-detected.

    Returns
    -------
    FilesBackend
        A backend instance.

    Raises
    ------
    KeyError
        If the requested backend is not registered.
    """
    if backend:
        if backend not in _registry:
            raise KeyError(
                f"Backend {backend!r} not registered. "
                f"Available: {list(_registry.keys())}"
            )
        return _registry[backend](root, **kwargs)

    if os.environ.get("SCITEX_API_TOKEN"):
        if "cloud" not in _registry:
            # Auto-register cloud backend when token is available
            from ._cloud_files import cloud_files_factory

            _registry["cloud"] = cloud_files_factory
        return _registry["cloud"](root, **kwargs)

    from ._filesystem import FileSystemBackend

    return FileSystemBackend(root or Path.cwd())


# Cloud service modules (accessible but not in __all__)
from . import _cloud_data as data  # noqa: E402,F401
from . import _cloud_external as external  # noqa: E402,F401
from . import _cloud_files as files  # noqa: E402,F401
from . import _cloud_jobs as jobs  # noqa: E402,F401
from . import _cloud_scitex as scitex  # noqa: E402,F401
from ._client import PlatformClient  # noqa: E402,F401
from ._client import get_client  # noqa: E402,F401
from ._client import reset_client  # noqa: E402,F401
from ._cloud_files import CloudFilesBackend  # noqa: E402,F401

__all__ = [
    # Core (minimal public API)
    "FilesBackend",
    "get_files",
    "register_backend",
    # Cloud client
    "PlatformClient",
    "get_client",
    "reset_client",
    "CloudFilesBackend",
    # Cloud service modules
    "data",
    "files",
    "jobs",
    "scitex",
    "external",
]

# EOF
