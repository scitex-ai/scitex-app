#!/usr/bin/env python3
# Timestamp: 2026-03-13
# File: tests/test__filesystem.py

"""Tests for FileSystemBackend."""

import pytest

from scitex_app.sdk._filesystem import FileSystemBackend


@pytest.fixture
def backend(tmp_path):
    """Create a FileSystemBackend rooted at a temp directory."""
    return FileSystemBackend(tmp_path)


class TestRead:
    def test_read_text(self, backend, tmp_path):
        (tmp_path / "hello.txt").write_text("world", encoding="utf-8")
        assert backend.read("hello.txt") == "world"

    def test_read_binary(self, backend, tmp_path):
        (tmp_path / "data.bin").write_bytes(b"\x00\x01\x02")
        assert backend.read("data.bin", binary=True) == b"\x00\x01\x02"

    def test_read_missing_raises(self, backend):
        with pytest.raises(FileNotFoundError):
            backend.read("nonexistent.txt")


class TestWrite:
    def test_write_text(self, backend, tmp_path):
        backend.write("out.txt", "hello")
        assert (tmp_path / "out.txt").read_text(encoding="utf-8") == "hello"

    def test_write_binary(self, backend, tmp_path):
        backend.write("out.bin", b"\xff\xfe")
        assert (tmp_path / "out.bin").read_bytes() == b"\xff\xfe"

    def test_write_creates_parents(self, backend, tmp_path):
        backend.write("sub/dir/file.txt", "nested")
        assert (tmp_path / "sub" / "dir" / "file.txt").exists()


class TestList:
    def test_list_root(self, backend, tmp_path):
        (tmp_path / "a.txt").touch()
        (tmp_path / "b.yaml").touch()
        result = backend.list()
        assert "a.txt" in result
        assert "b.yaml" in result

    def test_list_with_extension_filter(self, backend, tmp_path):
        (tmp_path / "a.txt").touch()
        (tmp_path / "b.yaml").touch()
        result = backend.list(extensions=[".yaml"])
        assert "b.yaml" in result
        assert "a.txt" not in result

    def test_list_empty_dir(self, backend):
        result = backend.list("nonexistent")
        assert result == []


class TestExists:
    def test_exists_true(self, backend, tmp_path):
        (tmp_path / "present.txt").touch()
        assert backend.exists("present.txt") is True

    def test_exists_false(self, backend):
        assert backend.exists("absent.txt") is False


class TestDelete:
    def test_delete_file(self, backend, tmp_path):
        (tmp_path / "doomed.txt").write_text("bye", encoding="utf-8")
        backend.delete("doomed.txt")
        assert not (tmp_path / "doomed.txt").exists()

    def test_delete_missing_raises(self, backend):
        with pytest.raises(FileNotFoundError):
            backend.delete("ghost.txt")


class TestRename:
    def test_rename(self, backend, tmp_path):
        (tmp_path / "old.txt").write_text("content", encoding="utf-8")
        backend.rename("old.txt", "new.txt")
        assert not (tmp_path / "old.txt").exists()
        assert (tmp_path / "new.txt").read_text(encoding="utf-8") == "content"

    def test_rename_missing_raises(self, backend):
        with pytest.raises(FileNotFoundError):
            backend.rename("nope.txt", "dest.txt")

    def test_rename_exists_raises(self, backend, tmp_path):
        (tmp_path / "a.txt").touch()
        (tmp_path / "b.txt").touch()
        with pytest.raises(FileExistsError):
            backend.rename("a.txt", "b.txt")


class TestCopy:
    def test_copy(self, backend, tmp_path):
        (tmp_path / "src.txt").write_text("data", encoding="utf-8")
        backend.copy("src.txt", "dst.txt")
        assert (tmp_path / "src.txt").exists()
        assert (tmp_path / "dst.txt").read_text(encoding="utf-8") == "data"

    def test_copy_missing_raises(self, backend):
        with pytest.raises(FileNotFoundError):
            backend.copy("missing.txt", "dst.txt")


class TestPathTraversal:
    def test_traversal_blocked(self, backend):
        with pytest.raises(ValueError, match="Path traversal"):
            backend.read("../../etc/passwd")


class TestProtocolCompliance:
    def test_implements_protocol(self, backend):
        from scitex_app.sdk._protocol import FilesBackend

        assert isinstance(backend, FilesBackend)
