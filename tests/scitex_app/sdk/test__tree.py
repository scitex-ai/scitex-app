#!/usr/bin/env python3
# Timestamp: 2026-03-21
# File: tests/test__tree.py

"""Tests for sdk/_tree.py — build_tree function."""

from __future__ import annotations

from pathlib import Path

from scitex_app.sdk._tree import build_tree, _list_entries
from scitex_app.sdk._filesystem import FileSystemBackend


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_backend(tmp_path: Path) -> FileSystemBackend:
    return FileSystemBackend(tmp_path)


# ---------------------------------------------------------------------------
# Tests: _list_entries
# ---------------------------------------------------------------------------


class TestListEntries:
    def test_uses_list_entries_if_available(self, tmp_path):
        """If backend has list_entries(), it is used directly."""

        class FakeBackend:
            def list_entries(self, directory=""):
                return [
                    {"path": "a.txt", "type": "file"},
                    {"path": "subdir", "type": "directory"},
                ]

        result = _list_entries(FakeBackend(), "")
        assert len(result) == 2
        assert result[0]["path"] == "a.txt"

    def test_falls_back_to_root_attr(self, tmp_path):
        """Falls back to backend._root pathlib traversal."""
        (tmp_path / "file.txt").write_text("content", encoding="utf-8")
        (tmp_path / "subdir").mkdir()

        backend = make_backend(tmp_path)
        entries = _list_entries(backend, "")
        paths = [e["path"] for e in entries]
        types = {e["path"]: e["type"] for e in entries}

        assert "file.txt" in paths
        assert "subdir" in paths
        assert types["file.txt"] == "file"
        assert types["subdir"] == "directory"

    def test_root_attr_nonexistent_directory(self, tmp_path):
        """Returns empty list when directory does not exist."""
        backend = make_backend(tmp_path)
        result = _list_entries(backend, "nonexistent")
        assert result == []

    def test_last_resort_list_fallback(self, tmp_path):
        """Falls back to backend.list() when no _root or list_entries."""

        class MinimalBackend:
            def list(self, directory="", *, extensions=None):
                return ["a.txt", "b.yaml"]

        result = _list_entries(MinimalBackend(), "")
        assert all(e["type"] == "file" for e in result)
        assert [e["path"] for e in result] == ["a.txt", "b.yaml"]


# ---------------------------------------------------------------------------
# Tests: build_tree basics
# ---------------------------------------------------------------------------


class TestBuildTreeBasics:
    def test_empty_directory_returns_empty(self, tmp_path):
        backend = make_backend(tmp_path)
        result = build_tree(backend, "")
        assert result == []

    def test_single_file_included(self, tmp_path):
        (tmp_path / "readme.txt").write_text("hello", encoding="utf-8")
        backend = make_backend(tmp_path)
        result = build_tree(backend)
        assert len(result) == 1
        assert result[0]["name"] == "readme.txt"
        assert result[0]["type"] == "file"
        assert result[0]["path"] == "readme.txt"

    def test_directory_with_files_produces_nested_tree(self, tmp_path):
        subdir = tmp_path / "data"
        subdir.mkdir()
        (subdir / "a.txt").write_text("a")
        backend = make_backend(tmp_path)
        result = build_tree(backend)
        # Should contain directory 'data' with children
        names = {item["name"] for item in result}
        assert "data" in names
        data_node = next(item for item in result if item["name"] == "data")
        assert data_node["type"] == "directory"
        children_names = {c["name"] for c in data_node["children"]}
        assert "a.txt" in children_names

    def test_empty_subdirectory_excluded(self, tmp_path):
        """Empty directories must not appear in the tree."""
        (tmp_path / "empty_dir").mkdir()
        backend = make_backend(tmp_path)
        result = build_tree(backend)
        assert result == []

    def test_result_sorted_alphabetically_case_insensitive(self, tmp_path):
        (tmp_path / "Zebra.txt").write_text("z")
        (tmp_path / "apple.txt").write_text("a")
        (tmp_path / "Mango.txt").write_text("m")
        backend = make_backend(tmp_path)
        result = build_tree(backend)
        names = [item["name"] for item in result]
        assert names == sorted(names, key=str.lower)


# ---------------------------------------------------------------------------
# Tests: hidden files
# ---------------------------------------------------------------------------


class TestSkipHidden:
    def test_hidden_files_skipped_by_default(self, tmp_path):
        (tmp_path / ".hidden").write_text("secret")
        (tmp_path / "visible.txt").write_text("ok")
        backend = make_backend(tmp_path)
        result = build_tree(backend)
        names = {item["name"] for item in result}
        assert ".hidden" not in names
        assert "visible.txt" in names

    def test_hidden_dirs_skipped_by_default(self, tmp_path):
        hidden_dir = tmp_path / ".git"
        hidden_dir.mkdir()
        (hidden_dir / "config").write_text("git config")
        backend = make_backend(tmp_path)
        result = build_tree(backend)
        assert result == []

    def test_hidden_files_included_when_skip_hidden_false(self, tmp_path):
        (tmp_path / ".env").write_text("key=value")
        backend = make_backend(tmp_path)
        result = build_tree(backend, skip_hidden=False)
        names = {item["name"] for item in result}
        assert ".env" in names


# ---------------------------------------------------------------------------
# Tests: extension filtering
# ---------------------------------------------------------------------------


class TestExtensionFilter:
    def test_filter_by_single_extension(self, tmp_path):
        (tmp_path / "config.yaml").write_text("key: value")
        (tmp_path / "script.py").write_text("print(1)")
        (tmp_path / "data.csv").write_text("a,b")
        backend = make_backend(tmp_path)
        result = build_tree(backend, extensions=[".yaml"])
        names = {item["name"] for item in result}
        assert "config.yaml" in names
        assert "script.py" not in names
        assert "data.csv" not in names

    def test_filter_by_multiple_extensions(self, tmp_path):
        (tmp_path / "config.yaml").write_text("key: value")
        (tmp_path / "script.py").write_text("print(1)")
        (tmp_path / "data.csv").write_text("a,b")
        backend = make_backend(tmp_path)
        result = build_tree(backend, extensions=[".yaml", ".py"])
        names = {item["name"] for item in result}
        assert "config.yaml" in names
        assert "script.py" in names
        assert "data.csv" not in names

    def test_extension_filter_case_insensitive(self, tmp_path):
        (tmp_path / "IMAGE.PNG").write_text("fake png")
        backend = make_backend(tmp_path)
        result = build_tree(backend, extensions=[".png"])
        names = {item["name"] for item in result}
        assert "IMAGE.PNG" in names

    def test_directories_always_traversed_for_extension_filter(self, tmp_path):
        """Directories are traversed to find matching files even with extension filter."""
        subdir = tmp_path / "assets"
        subdir.mkdir()
        (subdir / "style.css").write_text("body {}")
        backend = make_backend(tmp_path)
        result = build_tree(backend, extensions=[".css"])
        assert len(result) == 1
        assert result[0]["type"] == "directory"
        assert result[0]["name"] == "assets"
        assert result[0]["children"][0]["name"] == "style.css"

    def test_no_filter_includes_all_files(self, tmp_path):
        (tmp_path / "a.txt").write_text("a")
        (tmp_path / "b.yaml").write_text("b")
        backend = make_backend(tmp_path)
        result = build_tree(backend)
        assert len(result) == 2


# ---------------------------------------------------------------------------
# Tests: max_depth
# ---------------------------------------------------------------------------


class TestMaxDepth:
    def test_max_depth_zero_returns_empty(self, tmp_path):
        (tmp_path / "file.txt").write_text("content")
        backend = make_backend(tmp_path)
        result = build_tree(backend, max_depth=0)
        assert result == []

    def test_max_depth_one_excludes_grandchildren(self, tmp_path):
        subdir = tmp_path / "level1"
        subdir.mkdir()
        level2 = subdir / "level2"
        level2.mkdir()
        (level2 / "deep.txt").write_text("deep")
        (subdir / "shallow.txt").write_text("shallow")
        backend = make_backend(tmp_path)
        # depth=1 means level1/ can have children but not level2/
        result = build_tree(backend, max_depth=2)
        assert len(result) == 1
        level1_node = result[0]
        child_names = {c["name"] for c in level1_node["children"]}
        assert "shallow.txt" in child_names

    def test_default_max_depth_reaches_nested_content(self, tmp_path):
        deep = tmp_path / "a" / "b" / "c"
        deep.mkdir(parents=True)
        (deep / "file.txt").write_text("found")
        backend = make_backend(tmp_path)
        result = build_tree(backend)
        # Should recursively find file.txt
        assert len(result) == 1
        assert result[0]["type"] == "directory"


# ---------------------------------------------------------------------------
# Tests: custom backend with list_entries
# ---------------------------------------------------------------------------


class TestCustomBackend:
    def test_build_tree_with_custom_backend(self):
        """build_tree works with any backend implementing list_entries()."""

        class FlatBackend:
            def list_entries(self, directory=""):
                if directory == "":
                    return [
                        {"path": "docs", "type": "directory"},
                        {"path": "readme.md", "type": "file"},
                    ]
                elif directory == "docs":
                    return [
                        {"path": "docs/guide.md", "type": "file"},
                    ]
                return []

        result = build_tree(FlatBackend())
        # docs/ should appear with children, readme.md at root
        names = {item["name"] for item in result}
        assert "docs" in names
        assert "readme.md" in names

        docs_node = next(item for item in result if item["name"] == "docs")
        assert docs_node["type"] == "directory"
        assert docs_node["children"][0]["name"] == "guide.md"

    def test_permission_error_in_subdir_is_skipped(self, tmp_path):
        """PermissionError on a sub-directory is silently skipped."""

        class BackendWithPermError:
            def list_entries(self, directory=""):
                if directory == "":
                    return [
                        {"path": "restricted", "type": "directory"},
                        {"path": "ok.txt", "type": "file"},
                    ]
                raise PermissionError("no access")

        result = build_tree(BackendWithPermError())
        names = {item["name"] for item in result}
        # 'restricted' is skipped (PermissionError), 'ok.txt' included
        assert "restricted" not in names
        assert "ok.txt" in names


# EOF
