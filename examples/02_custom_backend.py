#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Registering and using a custom backend.

Defines a minimal in-memory backend, registers it via ``register_backend``,
then exercises read/write/list/exists through ``get_files(backend=...)``.

Usage:
    python 02_custom_backend.py
"""

import scitex as stx

from scitex_app.sdk import get_files, register_backend


class InMemoryBackend:
    """Simple in-memory backend for demonstration."""

    def __init__(self, root=None, **kwargs):
        self._store = {}

    def read(self, path, *, binary=False):
        if path not in self._store:
            raise FileNotFoundError(f"File not found: {path!r}")
        return self._store[path]

    def write(self, path, content):
        self._store[path] = content

    def list(self, directory="", *, extensions=None):
        results = []
        prefix = f"{directory}/" if directory else ""
        for key in sorted(self._store.keys()):
            if key.startswith(prefix):
                if extensions and not any(key.endswith(ext) for ext in extensions):
                    continue
                results.append(key)
        return results

    def exists(self, path):
        return path in self._store

    def delete(self, path):
        if path not in self._store:
            raise FileNotFoundError(f"File not found: {path!r}")
        del self._store[path]

    def rename(self, old_path, new_path):
        if old_path not in self._store:
            raise FileNotFoundError(f"File not found: {old_path!r}")
        if new_path in self._store:
            raise FileExistsError(f"File already exists: {new_path!r}")
        self._store[new_path] = self._store.pop(old_path)

    def copy(self, src_path, dest_path):
        if src_path not in self._store:
            raise FileNotFoundError(f"File not found: {src_path!r}")
        self._store[dest_path] = self._store[src_path]


@stx.session
def main(
    CONFIG=stx.session.INJECTED,
    logger=stx.session.INJECTED,
):
    """Register an in-memory backend and round-trip through the SDK."""
    # Register the custom backend
    register_backend("memory", InMemoryBackend)

    # Use it
    files = get_files(backend="memory")
    files.write("hello.txt", "Hello from in-memory backend!")
    logger.info(f"Read: {files.read('hello.txt')}")
    logger.info(f"Files: {files.list()}")
    logger.info(f"Exists: {files.exists('hello.txt')}")

    logger.info("\nCustom backend works!")
    return 0


if __name__ == "__main__":
    main()
