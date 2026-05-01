#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Integration tests for scitex_app.sdk's backend-registry surface.

Exercises the public entry points exposed by `scitex_app.sdk.__init__`
(``get_files``, ``register_backend``, the ``_registry`` dict, and the
``SCITEX_API_TOKEN`` cloud auto-detection path). Lives under
`tests/custom/` because it crosses three modules (`__init__`,
`_filesystem`, `_cloud_files`) and the registry has no single src
counterpart — `__init__.py` is not a per-file mirror target under
audit-project §2.
"""

from __future__ import annotations

import pytest

from scitex_app.sdk import FilesBackend, get_files, register_backend
from scitex_app.sdk._filesystem import FileSystemBackend


class TestGetFiles:
    def test_default_returns_filesystem(self, tmp_path):
        files = get_files(tmp_path)
        assert isinstance(files, FileSystemBackend)

    def test_default_uses_cwd(self):
        files = get_files()
        assert isinstance(files, FileSystemBackend)

    def test_explicit_backend_not_registered(self):
        with pytest.raises(KeyError, match="not registered"):
            get_files(backend="nonexistent")


class TestRegisterBackend:
    def test_register_and_use(self, tmp_path):
        class MockBackend:
            def __init__(self, root, **kwargs):
                self.root = root

            def read(self, path, *, binary=False):
                return "mock"

            def write(self, path, content):
                pass

            def list(self, directory="", *, extensions=None):
                return []

            def exists(self, path):
                return False

            def delete(self, path):
                pass

            def rename(self, old_path, new_path):
                pass

            def copy(self, src_path, dest_path):
                pass

        register_backend("mock", MockBackend)
        try:
            files = get_files(tmp_path, backend="mock")
            assert files.read("any") == "mock"
        finally:
            # Clean up registry
            from scitex_app.sdk import _registry

            _registry.pop("mock", None)

    def test_cloud_auto_detection(self, tmp_path, monkeypatch):
        """When SCITEX_API_TOKEN is set and cloud backend registered, use cloud."""

        class FakeCloud:
            def __init__(self, root, **kwargs):
                self.kind = "cloud"

            def read(self, path, *, binary=False):
                return "cloud-content"

            def write(self, path, content):
                pass

            def list(self, directory="", *, extensions=None):
                return []

            def exists(self, path):
                return True

            def delete(self, path):
                pass

            def rename(self, old_path, new_path):
                pass

            def copy(self, src_path, dest_path):
                pass

        register_backend("cloud", FakeCloud)
        monkeypatch.setenv("SCITEX_API_TOKEN", "test-token")
        try:
            files = get_files(tmp_path)
            assert hasattr(files, "kind") and files.kind == "cloud"
        finally:
            from scitex_app.sdk import _registry

            _registry.pop("cloud", None)


class TestProtocol:
    def test_filesystem_satisfies_protocol(self, tmp_path):
        files = get_files(tmp_path)
        assert isinstance(files, FilesBackend)
