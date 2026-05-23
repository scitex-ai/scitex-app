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
    def test_uses_list_entries_if_available_len_result_is_2(self, tmp_path):
        # Arrange
        # Arrange
        class FakeBackend:
            def list_entries(self, directory=""):
                return [
                    {"path": "a.txt", "type": "file"},
                    {"path": "subdir", "type": "directory"},
                ]

        # Act
        result = _list_entries(FakeBackend(), "")
        # Act
        # Assert
        # Assert
        assert len(result) == 2

    def test_uses_list_entries_if_available_result_0_path_a_txt(self, tmp_path):
        # Arrange
        # Arrange
        class FakeBackend:
            def list_entries(self, directory=""):
                return [
                    {"path": "a.txt", "type": "file"},
                    {"path": "subdir", "type": "directory"},
                ]

        # Act
        result = _list_entries(FakeBackend(), "")
        # Act
        # Assert
        # Assert
        assert result[0]["path"] == "a.txt"

    def test_falls_back_to_root_attr_file_txt_in_paths(self, tmp_path):
        # Arrange
        # Arrange
        (tmp_path / "file.txt").write_text("content", encoding="utf-8")
        (tmp_path / "subdir").mkdir()
        backend = make_backend(tmp_path)
        entries = _list_entries(backend, "")
        paths = [e["path"] for e in entries]
        # Act
        types = {e["path"]: e["type"] for e in entries}
        # Act
        # Assert
        # Assert
        assert "file.txt" in paths

    def test_falls_back_to_root_attr_subdir_in_paths(self, tmp_path):
        # Arrange
        # Arrange
        (tmp_path / "file.txt").write_text("content", encoding="utf-8")
        (tmp_path / "subdir").mkdir()
        backend = make_backend(tmp_path)
        entries = _list_entries(backend, "")
        paths = [e["path"] for e in entries]
        # Act
        types = {e["path"]: e["type"] for e in entries}
        # Act
        # Assert
        # Assert
        assert "subdir" in paths

    def test_falls_back_to_root_attr_types_file_txt_file(self, tmp_path):
        # Arrange
        # Arrange
        (tmp_path / "file.txt").write_text("content", encoding="utf-8")
        (tmp_path / "subdir").mkdir()
        backend = make_backend(tmp_path)
        entries = _list_entries(backend, "")
        paths = [e["path"] for e in entries]
        # Act
        types = {e["path"]: e["type"] for e in entries}
        # Act
        # Assert
        # Assert
        assert types["file.txt"] == "file"

    def test_falls_back_to_root_attr_types_subdir_directory(self, tmp_path):
        # Arrange
        # Arrange
        (tmp_path / "file.txt").write_text("content", encoding="utf-8")
        (tmp_path / "subdir").mkdir()
        backend = make_backend(tmp_path)
        entries = _list_entries(backend, "")
        paths = [e["path"] for e in entries]
        # Act
        types = {e["path"]: e["type"] for e in entries}
        # Act
        # Assert
        # Assert
        assert types["subdir"] == "directory"

    def test_root_attr_nonexistent_directory(self, tmp_path):
        """Returns empty list when directory does not exist."""
        # Arrange
        backend = make_backend(tmp_path)
        # Act
        result = _list_entries(backend, "nonexistent")
        # Assert
        assert result == []

    def test_last_resort_list_fallback_all_e_type_file_for_e_in_result(self, tmp_path):
        # Arrange
        # Arrange
        class MinimalBackend:
            def list(self, directory="", *, extensions=None):
                return ["a.txt", "b.yaml"]

        # Act
        result = _list_entries(MinimalBackend(), "")
        # Act
        # Assert
        # Assert
        assert all(e["type"] == "file" for e in result)

    def test_last_resort_list_fallback_e_path_for_e_in_result_a_txt_b_yaml(
        self, tmp_path
    ):
        # Arrange
        # Arrange
        class MinimalBackend:
            def list(self, directory="", *, extensions=None):
                return ["a.txt", "b.yaml"]

        # Act
        result = _list_entries(MinimalBackend(), "")
        # Act
        # Assert
        # Assert
        assert [e["path"] for e in result] == ["a.txt", "b.yaml"]


# ---------------------------------------------------------------------------
# Tests: build_tree basics
# ---------------------------------------------------------------------------


class TestBuildTreeBasics:
    def test_empty_directory_returns_empty(self, tmp_path):
        # Arrange
        backend = make_backend(tmp_path)
        # Act
        result = build_tree(backend, "")
        # Assert
        assert result == []

    def test_single_file_included_len_result_is_1(self, tmp_path):
        # Arrange
        # Arrange
        (tmp_path / "readme.txt").write_text("hello", encoding="utf-8")
        backend = make_backend(tmp_path)
        # Act
        result = build_tree(backend)
        # Act
        # Assert
        # Assert
        assert len(result) == 1

    def test_single_file_included_result_0_name_readme_txt(self, tmp_path):
        # Arrange
        # Arrange
        (tmp_path / "readme.txt").write_text("hello", encoding="utf-8")
        backend = make_backend(tmp_path)
        # Act
        result = build_tree(backend)
        # Act
        # Assert
        # Assert
        assert result[0]["name"] == "readme.txt"

    def test_single_file_included_result_0_type_file(self, tmp_path):
        # Arrange
        # Arrange
        (tmp_path / "readme.txt").write_text("hello", encoding="utf-8")
        backend = make_backend(tmp_path)
        # Act
        result = build_tree(backend)
        # Act
        # Assert
        # Assert
        assert result[0]["type"] == "file"

    def test_single_file_included_result_0_path_readme_txt(self, tmp_path):
        # Arrange
        # Arrange
        (tmp_path / "readme.txt").write_text("hello", encoding="utf-8")
        backend = make_backend(tmp_path)
        # Act
        result = build_tree(backend)
        # Act
        # Assert
        # Assert
        assert result[0]["path"] == "readme.txt"

    def test_directory_with_files_produces_nested_tree_data_in_names(self, tmp_path):
        # Arrange
        # Arrange
        subdir = tmp_path / "data"
        subdir.mkdir()
        (subdir / "a.txt").write_text("a")
        backend = make_backend(tmp_path)
        result = build_tree(backend)
        # Should contain directory 'data' with children
        # Act
        names = {item["name"] for item in result}
        # Act
        # Assert
        # Assert
        assert "data" in names

    def test_directory_with_files_produces_nested_tree_data_node_type_directory(
        self, tmp_path
    ):
        # Arrange
        # Arrange
        subdir = tmp_path / "data"
        subdir.mkdir()
        (subdir / "a.txt").write_text("a")
        backend = make_backend(tmp_path)
        result = build_tree(backend)
        # Act
        data_node = next(item for item in result if item["name"] == "data")
        # Assert
        assert data_node["type"] == "directory"

    def test_directory_with_files_produces_nested_tree_a_txt_in_children_names(
        self, tmp_path
    ):
        # Arrange
        subdir = tmp_path / "data"
        subdir.mkdir()
        (subdir / "a.txt").write_text("a")
        backend = make_backend(tmp_path)
        result = build_tree(backend)
        data_node = next(item for item in result if item["name"] == "data")
        # Act
        children_names = {c["name"] for c in data_node["children"]}
        # Assert
        assert "a.txt" in children_names

    def test_empty_subdirectory_excluded(self, tmp_path):
        """Empty directories must not appear in the tree."""
        # Arrange
        (tmp_path / "empty_dir").mkdir()
        backend = make_backend(tmp_path)
        # Act
        result = build_tree(backend)
        # Assert
        assert result == []

    def test_result_sorted_alphabetically_case_insensitive(self, tmp_path):
        # Arrange
        (tmp_path / "Zebra.txt").write_text("z")
        (tmp_path / "apple.txt").write_text("a")
        (tmp_path / "Mango.txt").write_text("m")
        backend = make_backend(tmp_path)
        result = build_tree(backend)
        # Act
        names = [item["name"] for item in result]
        # Assert
        assert names == sorted(names, key=str.lower)


# ---------------------------------------------------------------------------
# Tests: hidden files
# ---------------------------------------------------------------------------


class TestSkipHidden:
    def test_hidden_files_skipped_by_default_hidden_not_in_names(self, tmp_path):
        # Arrange
        # Arrange
        (tmp_path / ".hidden").write_text("secret")
        (tmp_path / "visible.txt").write_text("ok")
        backend = make_backend(tmp_path)
        result = build_tree(backend)
        # Act
        names = {item["name"] for item in result}
        # Act
        # Assert
        # Assert
        assert ".hidden" not in names

    def test_hidden_files_skipped_by_default_visible_txt_in_names(self, tmp_path):
        # Arrange
        # Arrange
        (tmp_path / ".hidden").write_text("secret")
        (tmp_path / "visible.txt").write_text("ok")
        backend = make_backend(tmp_path)
        result = build_tree(backend)
        # Act
        names = {item["name"] for item in result}
        # Act
        # Assert
        # Assert
        assert "visible.txt" in names

    def test_hidden_dirs_skipped_by_default(self, tmp_path):
        # Arrange
        hidden_dir = tmp_path / ".git"
        hidden_dir.mkdir()
        (hidden_dir / "config").write_text("git config")
        backend = make_backend(tmp_path)
        # Act
        result = build_tree(backend)
        # Assert
        assert result == []

    def test_hidden_files_included_when_skip_hidden_false(self, tmp_path):
        # Arrange
        (tmp_path / ".env").write_text("key=value")
        backend = make_backend(tmp_path)
        result = build_tree(backend, skip_hidden=False)
        # Act
        names = {item["name"] for item in result}
        # Assert
        assert ".env" in names


# ---------------------------------------------------------------------------
# Tests: extension filtering
# ---------------------------------------------------------------------------


class TestExtensionFilter:
    def test_filter_by_single_extension_config_yaml_in_names(self, tmp_path):
        # Arrange
        # Arrange
        (tmp_path / "config.yaml").write_text("key: value")
        (tmp_path / "script.py").write_text("print(1)")
        (tmp_path / "data.csv").write_text("a,b")
        backend = make_backend(tmp_path)
        result = build_tree(backend, extensions=[".yaml"])
        # Act
        names = {item["name"] for item in result}
        # Act
        # Assert
        # Assert
        assert "config.yaml" in names

    def test_filter_by_single_extension_script_py_not_in_names(self, tmp_path):
        # Arrange
        # Arrange
        (tmp_path / "config.yaml").write_text("key: value")
        (tmp_path / "script.py").write_text("print(1)")
        (tmp_path / "data.csv").write_text("a,b")
        backend = make_backend(tmp_path)
        result = build_tree(backend, extensions=[".yaml"])
        # Act
        names = {item["name"] for item in result}
        # Act
        # Assert
        # Assert
        assert "script.py" not in names

    def test_filter_by_single_extension_data_csv_not_in_names(self, tmp_path):
        # Arrange
        # Arrange
        (tmp_path / "config.yaml").write_text("key: value")
        (tmp_path / "script.py").write_text("print(1)")
        (tmp_path / "data.csv").write_text("a,b")
        backend = make_backend(tmp_path)
        result = build_tree(backend, extensions=[".yaml"])
        # Act
        names = {item["name"] for item in result}
        # Act
        # Assert
        # Assert
        assert "data.csv" not in names

    def test_filter_by_multiple_extensions_config_yaml_in_names(self, tmp_path):
        # Arrange
        # Arrange
        (tmp_path / "config.yaml").write_text("key: value")
        (tmp_path / "script.py").write_text("print(1)")
        (tmp_path / "data.csv").write_text("a,b")
        backend = make_backend(tmp_path)
        result = build_tree(backend, extensions=[".yaml", ".py"])
        # Act
        names = {item["name"] for item in result}
        # Act
        # Assert
        # Assert
        assert "config.yaml" in names

    def test_filter_by_multiple_extensions_script_py_in_names(self, tmp_path):
        # Arrange
        # Arrange
        (tmp_path / "config.yaml").write_text("key: value")
        (tmp_path / "script.py").write_text("print(1)")
        (tmp_path / "data.csv").write_text("a,b")
        backend = make_backend(tmp_path)
        result = build_tree(backend, extensions=[".yaml", ".py"])
        # Act
        names = {item["name"] for item in result}
        # Act
        # Assert
        # Assert
        assert "script.py" in names

    def test_filter_by_multiple_extensions_data_csv_not_in_names(self, tmp_path):
        # Arrange
        # Arrange
        (tmp_path / "config.yaml").write_text("key: value")
        (tmp_path / "script.py").write_text("print(1)")
        (tmp_path / "data.csv").write_text("a,b")
        backend = make_backend(tmp_path)
        result = build_tree(backend, extensions=[".yaml", ".py"])
        # Act
        names = {item["name"] for item in result}
        # Act
        # Assert
        # Assert
        assert "data.csv" not in names

    def test_extension_filter_case_insensitive(self, tmp_path):
        # Arrange
        (tmp_path / "IMAGE.PNG").write_text("fake png")
        backend = make_backend(tmp_path)
        result = build_tree(backend, extensions=[".png"])
        # Act
        names = {item["name"] for item in result}
        # Assert
        assert "IMAGE.PNG" in names

    def test_directories_always_traversed_for_extension_filter_len_result_is_1(
        self, tmp_path
    ):
        # Arrange
        # Arrange
        subdir = tmp_path / "assets"
        subdir.mkdir()
        (subdir / "style.css").write_text("body {}")
        backend = make_backend(tmp_path)
        # Act
        result = build_tree(backend, extensions=[".css"])
        # Act
        # Assert
        # Assert
        assert len(result) == 1

    def test_directories_always_traversed_for_extension_filter_result_0_type_directory(
        self, tmp_path
    ):
        # Arrange
        # Arrange
        subdir = tmp_path / "assets"
        subdir.mkdir()
        (subdir / "style.css").write_text("body {}")
        backend = make_backend(tmp_path)
        # Act
        result = build_tree(backend, extensions=[".css"])
        # Act
        # Assert
        # Assert
        assert result[0]["type"] == "directory"

    def test_directories_always_traversed_for_extension_filter_result_0_name_assets(
        self, tmp_path
    ):
        # Arrange
        # Arrange
        subdir = tmp_path / "assets"
        subdir.mkdir()
        (subdir / "style.css").write_text("body {}")
        backend = make_backend(tmp_path)
        # Act
        result = build_tree(backend, extensions=[".css"])
        # Act
        # Assert
        # Assert
        assert result[0]["name"] == "assets"

    def test_directories_always_traversed_for_extension_filter_result_0_children_0_name_style_css(
        self, tmp_path
    ):
        # Arrange
        # Arrange
        subdir = tmp_path / "assets"
        subdir.mkdir()
        (subdir / "style.css").write_text("body {}")
        backend = make_backend(tmp_path)
        # Act
        result = build_tree(backend, extensions=[".css"])
        # Act
        # Assert
        # Assert
        assert result[0]["children"][0]["name"] == "style.css"

    def test_no_filter_includes_all_files(self, tmp_path):
        # Arrange
        (tmp_path / "a.txt").write_text("a")
        (tmp_path / "b.yaml").write_text("b")
        backend = make_backend(tmp_path)
        # Act
        result = build_tree(backend)
        # Assert
        assert len(result) == 2


# ---------------------------------------------------------------------------
# Tests: max_depth
# ---------------------------------------------------------------------------


class TestMaxDepth:
    def test_max_depth_zero_returns_empty(self, tmp_path):
        # Arrange
        (tmp_path / "file.txt").write_text("content")
        backend = make_backend(tmp_path)
        # Act
        result = build_tree(backend, max_depth=0)
        # Assert
        assert result == []

    def test_max_depth_one_excludes_grandchildren_len_result_is_1(self, tmp_path):
        # Arrange
        # Arrange
        subdir = tmp_path / "level1"
        subdir.mkdir()
        level2 = subdir / "level2"
        level2.mkdir()
        (level2 / "deep.txt").write_text("deep")
        (subdir / "shallow.txt").write_text("shallow")
        backend = make_backend(tmp_path)
        # depth=1 means level1/ can have children but not level2/
        # Act
        result = build_tree(backend, max_depth=2)
        # Act
        # Assert
        # Assert
        assert len(result) == 1

    def test_max_depth_one_excludes_grandchildren_shallow_txt_in_child_names(
        self, tmp_path
    ):
        # Arrange
        # Arrange
        subdir = tmp_path / "level1"
        subdir.mkdir()
        level2 = subdir / "level2"
        level2.mkdir()
        (level2 / "deep.txt").write_text("deep")
        (subdir / "shallow.txt").write_text("shallow")
        backend = make_backend(tmp_path)
        # depth=1 means level1/ can have children but not level2/
        result = build_tree(backend, max_depth=2)
        level1_node = result[0]
        # Act
        child_names = {c["name"] for c in level1_node["children"]}
        # Assert
        assert "shallow.txt" in child_names

    def test_default_max_depth_reaches_nested_content_len_result_is_1(self, tmp_path):
        # Arrange
        # Arrange
        deep = tmp_path / "a" / "b" / "c"
        deep.mkdir(parents=True)
        (deep / "file.txt").write_text("found")
        backend = make_backend(tmp_path)
        # Act
        result = build_tree(backend)
        # Act
        # Assert
        # Assert
        assert len(result) == 1

    def test_default_max_depth_reaches_nested_content_result_0_type_directory(
        self, tmp_path
    ):
        # Arrange
        # Arrange
        deep = tmp_path / "a" / "b" / "c"
        deep.mkdir(parents=True)
        (deep / "file.txt").write_text("found")
        backend = make_backend(tmp_path)
        # Act
        result = build_tree(backend)
        # Act
        # Assert
        # Assert
        assert result[0]["type"] == "directory"


# ---------------------------------------------------------------------------
# Tests: custom backend with list_entries
# ---------------------------------------------------------------------------


class TestCustomBackend:
    def test_build_tree_with_custom_backend_docs_in_names(self):
        # Arrange
        # Arrange
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
        # Act
        names = {item["name"] for item in result}
        # Act
        # Assert
        # Assert
        assert "docs" in names

    def test_build_tree_with_custom_backend_readme_md_in_names(self):
        # Arrange
        # Arrange
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
        # Act
        names = {item["name"] for item in result}
        # Act
        # Assert
        # Assert
        assert "readme.md" in names

    def test_build_tree_with_custom_backend_docs_node_type_directory(self):
        # Arrange
        # Arrange
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
        # Act
        docs_node = next(item for item in result if item["name"] == "docs")
        # Assert
        assert docs_node["type"] == "directory"

    def test_build_tree_with_custom_backend_docs_node_children_0_name_guide_md(self):
        # Arrange
        # Arrange
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
        docs_node = next(item for item in result if item["name"] == "docs")
        # Act
        first_child_name = docs_node["children"][0]["name"]
        # Assert
        assert first_child_name == "guide.md"

    def test_permission_error_in_subdir_is_skipped_restricted_not_in_names(
        self, tmp_path
    ):
        # Arrange
        # Arrange
        class BackendWithPermError:
            def list_entries(self, directory=""):
                if directory == "":
                    return [
                        {"path": "restricted", "type": "directory"},
                        {"path": "ok.txt", "type": "file"},
                    ]
                raise PermissionError("no access")

        result = build_tree(BackendWithPermError())
        # Act
        names = {item["name"] for item in result}
        # Act
        # Assert
        # Assert
        assert "restricted" not in names

    def test_permission_error_in_subdir_is_skipped_ok_txt_in_names(self, tmp_path):
        # Arrange
        # Arrange
        class BackendWithPermError:
            def list_entries(self, directory=""):
                if directory == "":
                    return [
                        {"path": "restricted", "type": "directory"},
                        {"path": "ok.txt", "type": "file"},
                    ]
                raise PermissionError("no access")

        result = build_tree(BackendWithPermError())
        # Act
        names = {item["name"] for item in result}
        # Act
        # Assert
        # Assert
        assert "ok.txt" in names


# EOF
