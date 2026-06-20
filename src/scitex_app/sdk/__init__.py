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
from ._tree import build_tree

# Backend registry: name -> factory callable
_registry: Dict[str, Callable[..., FilesBackend]] = {}


def register_backend(name: str, factory: Callable[..., FilesBackend]) -> None:
    """Register a files backend factory.

    Parameters
    ----------
    name : str
        Backend identifier (e.g., "cloud", "s3").
    factory : callable
        Callable(root, ``**kwargs``) -> ``FilesBackend`` instance.
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


__all__ = [
    "FilesBackend",
    "get_files",
    "register_backend",
    "build_tree",
]


# Internal cloud modules — accessible via scitex_app.sdk._client etc.
# but NOT part of the public API contract. Use scitex_hub.sdk for
# cloud service access (data, files, jobs, scitex, external).
def __getattr__(name: str) -> Any:
    """Lazy-load cloud internals on demand (not in __all__)."""
    _lazy = {
        "PlatformClient": ("._client", "PlatformClient"),
        "get_client": ("._client", "get_client"),
        "reset_client": ("._client", "reset_client"),
        "CloudFilesBackend": ("._cloud_files", "CloudFilesBackend"),
        "data": (".", "_cloud_data"),
        "files": (".", "_cloud_files"),
        "jobs": (".", "_cloud_jobs"),
        "scitex": (".", "_cloud_scitex"),
        "external": (".", "_cloud_external"),
    }
    if name in _lazy:
        import importlib

        mod_path, attr = _lazy[name]
        if mod_path == ".":
            return importlib.import_module(f".{attr}", __package__)
        mod = importlib.import_module(mod_path, __package__)
        return getattr(mod, attr)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


# EOF
