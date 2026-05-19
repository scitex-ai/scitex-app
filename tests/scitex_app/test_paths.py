#!/usr/bin/env python3
# Timestamp: 2026-03-16
# File: tests/test__paths.py

"""Tests for scitex_app.paths module."""

from __future__ import annotations


import pytest

from scitex_app.paths import (
    find_partial_template,
    get_base_dir,
    parse_dev_module_name,
    resolve_manifest,
    resolve_static_dir,
    resolve_template_dir,
    resolve_user_project_dir,
    resolve_published_project_dir,
    safe_iterdir,
    validate_project_structure,
)


# ---------------------------------------------------------------------------
# get_base_dir
# ---------------------------------------------------------------------------


class TestGetBaseDir:
    def test_explicit_arg_get_base_dir_tmp_path_tmp_path_resolve(self, tmp_path):
        # Arrange
        # Act
        # Assert
        assert get_base_dir(tmp_path) == tmp_path.resolve()

    def test_env_var_get_base_dir_tmp_path_resolve(self, tmp_path, monkeypatch):
        # Arrange
        # Act
        monkeypatch.setenv("SCITEX_BASE_DIR", str(tmp_path))
        # Assert
        assert get_base_dir() == tmp_path.resolve()

    def test_explicit_arg_overrides_env(self, tmp_path, monkeypatch):
        # Arrange
        other = tmp_path / "other"
        other.mkdir()
        # Act
        monkeypatch.setenv("SCITEX_BASE_DIR", str(tmp_path))
        # Assert
        assert get_base_dir(other) == other.resolve()

    def test_raises_when_no_source(self, monkeypatch):
        # Arrange
        # Act
        monkeypatch.delenv("SCITEX_BASE_DIR", raising=False)
        # Assert
        with pytest.raises(ValueError, match="No base directory"):
            get_base_dir()


# ---------------------------------------------------------------------------
# resolve_user_project_dir
# ---------------------------------------------------------------------------


class TestResolveUserProjectDir:
    def test_existing_dir_result_equals_proj_2(self, tmp_path):
        # Arrange
        proj = tmp_path / "data" / "users" / "alice" / "proj" / "myapp"
        proj.mkdir(parents=True)
        # Act
        result = resolve_user_project_dir("alice", "myapp", base_dir=tmp_path)
        # Assert
        assert result == proj

    def test_missing_dir_result_is_none_2(self, tmp_path):
        # Arrange
        # Act
        result = resolve_user_project_dir("alice", "noapp", base_dir=tmp_path)
        # Assert
        assert result is None


# ---------------------------------------------------------------------------
# resolve_published_project_dir
# ---------------------------------------------------------------------------


class TestResolvePublishedProjectDir:
    def test_existing_dir_result_equals_proj_2(self, tmp_path):
        # Arrange
        proj = tmp_path / "data" / "projects" / "myproj"
        proj.mkdir(parents=True)
        # Act
        result = resolve_published_project_dir("myproj", base_dir=tmp_path)
        # Assert
        assert result == proj

    def test_missing_dir_result_is_none_2(self, tmp_path):
        # Arrange
        # Act
        result = resolve_published_project_dir("nope", base_dir=tmp_path)
        # Assert
        assert result is None


# ---------------------------------------------------------------------------
# resolve_manifest
# ---------------------------------------------------------------------------


class TestResolveManifest:
    def test_reads_valid_manifest(self, tmp_path):
        # Arrange
        # Act
        (tmp_path / "manifest.json").write_text('{"name": "test"}')
        # Assert
        assert resolve_manifest(tmp_path) == {"name": "test"}

    def test_missing_manifest_resolve_manifest_tmp_path(self, tmp_path):
        # Arrange
        # Act
        # Assert
        assert resolve_manifest(tmp_path) == {}

    def test_invalid_json_resolve_manifest_tmp_path(self, tmp_path):
        # Arrange
        # Act
        (tmp_path / "manifest.json").write_text("{broken")
        # Assert
        assert resolve_manifest(tmp_path) == {}


# ---------------------------------------------------------------------------
# find_partial_template
# ---------------------------------------------------------------------------


class TestFindPartialTemplate:
    def test_flat_layout_find_partial_template_tmp_path_tpl(self, tmp_path):
        # Arrange
        tpl = tmp_path / "index_partial.html"
        # Act
        tpl.write_text("<div>flat</div>")
        # Assert
        assert find_partial_template(tmp_path) == tpl

    def test_nested_layout_find_partial_template_tmp_path_nested(self, tmp_path):
        # Arrange
        nested = tmp_path / "myapp" / "index_partial.html"
        nested.parent.mkdir()
        # Act
        nested.write_text("<div>nested</div>")
        # Assert
        assert find_partial_template(tmp_path) == nested

    def test_missing_find_partial_template_tmp_path_is_none(self, tmp_path):
        # Arrange
        # Act
        # Assert
        assert find_partial_template(tmp_path) is None

    def test_nonexistent_dir_result_equals_case(self, tmp_path):
        # Arrange
        # Act
        # Assert
        assert find_partial_template(tmp_path / "nope") is None


# ---------------------------------------------------------------------------
# resolve_template_dir / resolve_static_dir
# ---------------------------------------------------------------------------


class TestResolveDirs:
    def test_template_dir_exists(self, tmp_path):
        # Arrange
        # Act
        (tmp_path / "templates").mkdir()
        # Assert
        assert resolve_template_dir(tmp_path) == tmp_path / "templates"

    def test_template_dir_missing(self, tmp_path):
        # Arrange
        # Act
        # Assert
        assert resolve_template_dir(tmp_path) is None

    def test_static_dir_exists(self, tmp_path):
        # Arrange
        # Act
        (tmp_path / "static").mkdir()
        # Assert
        assert resolve_static_dir(tmp_path) == tmp_path / "static"

    def test_static_dir_missing(self, tmp_path):
        # Arrange
        # Act
        # Assert
        assert resolve_static_dir(tmp_path) is None


# ---------------------------------------------------------------------------
# parse_dev_module_name
# ---------------------------------------------------------------------------


class TestParseDevModuleName:
    def test_valid_parse_dev_module_name_dev_alice_myapp_alice_myapp(self):
        # Arrange
        # Act
        # Assert
        assert parse_dev_module_name("dev__alice__myapp") == ("alice", "myapp")

    def test_not_dev_prefix(self):
        # Arrange
        # Act
        # Assert
        assert parse_dev_module_name("writer") is None

    def test_wrong_parts_count_parse_dev_module_name_dev_only_is_none(self):
        # Arrange
        # Act
        # Assert
        # Arrange
        # Act
        # Assert
        assert parse_dev_module_name("dev__only") is None

    def test_wrong_parts_count_parse_dev_module_name_dev_a_b_c_is_none(self):
        # Arrange
        # Act
        # Assert
        # Arrange
        # Act
        # Assert
        assert parse_dev_module_name("dev__a__b__c") is None



# ---------------------------------------------------------------------------
# safe_iterdir
# ---------------------------------------------------------------------------


class TestSafeIterdir:
    def test_skips_hidden_len_result_is_1(self, tmp_path):
        # Arrange
        # Arrange
        (tmp_path / ".hidden").mkdir()
        (tmp_path / "visible").mkdir()
        # Act
        result = list(safe_iterdir(tmp_path))
        # Act
        # Assert
        # Assert
        assert len(result) == 1

    def test_skips_hidden_result_0_name_visible(self, tmp_path):
        # Arrange
        # Arrange
        (tmp_path / ".hidden").mkdir()
        (tmp_path / "visible").mkdir()
        # Act
        result = list(safe_iterdir(tmp_path))
        # Act
        # Assert
        # Assert
        assert result[0].name == "visible"


    def test_nonexistent_dir_result_equals_case(self, tmp_path):
        # Arrange
        # Act
        result = list(safe_iterdir(tmp_path / "nope"))
        # Assert
        assert result == []


# ---------------------------------------------------------------------------
# validate_project_structure
# ---------------------------------------------------------------------------


class TestValidateProjectStructure:
    def test_valid_flat_ok_is_true(self, tmp_path):
        # Arrange
        # Arrange
        (tmp_path / "templates").mkdir()
        (tmp_path / "templates" / "index_partial.html").write_text("<div/>")
        # Act
        ok, msg = validate_project_structure(tmp_path)
        # Act
        # Assert
        # Assert
        assert ok is True

    def test_valid_flat_msg_equals_ok(self, tmp_path):
        # Arrange
        # Arrange
        (tmp_path / "templates").mkdir()
        (tmp_path / "templates" / "index_partial.html").write_text("<div/>")
        # Act
        ok, msg = validate_project_structure(tmp_path)
        # Act
        # Assert
        # Assert
        assert msg == "ok"


    def test_missing_templates_ok_is_false(self, tmp_path):
        # Arrange
        # Arrange
        # Act
        ok, msg = validate_project_structure(tmp_path)
        # Act
        # Assert
        # Assert
        assert ok is False

    def test_missing_templates_templates_in_msg(self, tmp_path):
        # Arrange
        # Arrange
        # Act
        ok, msg = validate_project_structure(tmp_path)
        # Act
        # Assert
        # Assert
        assert "templates" in msg


    def test_missing_partial_ok_is_false(self, tmp_path):
        # Arrange
        # Arrange
        (tmp_path / "templates").mkdir()
        # Act
        ok, msg = validate_project_structure(tmp_path)
        # Act
        # Assert
        # Assert
        assert ok is False

    def test_missing_partial_index_partial_in_msg(self, tmp_path):
        # Arrange
        # Arrange
        (tmp_path / "templates").mkdir()
        # Act
        ok, msg = validate_project_structure(tmp_path)
        # Act
        # Assert
        # Assert
        assert "index_partial" in msg


    def test_nonexistent_ok_is_false(self, tmp_path):
        # Arrange
        # Act
        ok, msg = validate_project_structure(tmp_path / "nope")
        # Assert
        assert ok is False


# EOF
