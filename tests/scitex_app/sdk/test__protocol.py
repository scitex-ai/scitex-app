#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tests for scitex_app/sdk/_protocol.py — FilesBackend Protocol contract."""

from __future__ import annotations

from typing import List, Optional, Union

from scitex_app.sdk._filesystem import FileSystemBackend
from scitex_app.sdk._protocol import FilesBackend


class _FullStub:
    """Implements every method on FilesBackend."""

    def read(self, path: str, *, binary: bool = False) -> Union[str, bytes]:
        return "" if not binary else b""

    def write(self, path: str, content: Union[str, bytes]) -> None:
        pass

    def list(
        self, directory: str = "", *, extensions: Optional[List[str]] = None
    ) -> List[str]:
        return []

    def exists(self, path: str) -> bool:
        return False

    def delete(self, path: str) -> None:
        pass

    def rename(self, old_path: str, new_path: str) -> None:
        pass

    def copy(self, src_path: str, dest_path: str) -> None:
        pass


class _MissingMethods:
    pass


def test_filesystem_backend_satisfies_protocol(tmp_path):
    backend = FileSystemBackend(tmp_path)
    assert isinstance(backend, FilesBackend)


def test_full_stub_satisfies_protocol():
    assert isinstance(_FullStub(), FilesBackend)


def test_partial_implementation_fails_runtime_check():
    assert not isinstance(_MissingMethods(), FilesBackend)
