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
    def test_explicit_arg(self, tmp_path):
        assert get_base_dir(tmp_path) == tmp_path.resolve()

    def test_env_var(self, tmp_path, monkeypatch):
        monkeypatch.setenv("SCITEX_BASE_DIR", str(tmp_path))
        assert get_base_dir() == tmp_path.resolve()

    def test_explicit_arg_overrides_env(self, tmp_path, monkeypatch):
        other = tmp_path / "other"
        other.mkdir()
        monkeypatch.setenv("SCITEX_BASE_DIR", str(tmp_path))
        assert get_base_dir(other) == other.resolve()

    def test_raises_when_no_source(self, monkeypatch):
        monkeypatch.delenv("SCITEX_BASE_DIR", raising=False)
        with pytest.raises(ValueError, match="No base directory"):
            get_base_dir()


# ---------------------------------------------------------------------------
# resolve_user_project_dir
# ---------------------------------------------------------------------------


class TestResolveUserProjectDir:
    def test_existing_dir(self, tmp_path):
        proj = tmp_path / "data" / "users" / "alice" / "proj" / "myapp"
        proj.mkdir(parents=True)
        result = resolve_user_project_dir("alice", "myapp", base_dir=tmp_path)
        assert result == proj

    def test_missing_dir(self, tmp_path):
        result = resolve_user_project_dir("alice", "noapp", base_dir=tmp_path)
        assert result is None


# ---------------------------------------------------------------------------
# resolve_published_project_dir
# ---------------------------------------------------------------------------


class TestResolvePublishedProjectDir:
    def test_existing_dir(self, tmp_path):
        proj = tmp_path / "data" / "projects" / "myproj"
        proj.mkdir(parents=True)
        result = resolve_published_project_dir("myproj", base_dir=tmp_path)
        assert result == proj

    def test_missing_dir(self, tmp_path):
        result = resolve_published_project_dir("nope", base_dir=tmp_path)
        assert result is None


# ---------------------------------------------------------------------------
# resolve_manifest
# ---------------------------------------------------------------------------


class TestResolveManifest:
    def test_reads_valid_manifest(self, tmp_path):
        (tmp_path / "manifest.json").write_text('{"name": "test"}')
        assert resolve_manifest(tmp_path) == {"name": "test"}

    def test_missing_manifest(self, tmp_path):
        assert resolve_manifest(tmp_path) == {}

    def test_invalid_json(self, tmp_path):
        (tmp_path / "manifest.json").write_text("{broken")
        assert resolve_manifest(tmp_path) == {}


# ---------------------------------------------------------------------------
# find_partial_template
# ---------------------------------------------------------------------------


class TestFindPartialTemplate:
    def test_flat_layout(self, tmp_path):
        tpl = tmp_path / "index_partial.html"
        tpl.write_text("<div>flat</div>")
        assert find_partial_template(tmp_path) == tpl

    def test_nested_layout(self, tmp_path):
        nested = tmp_path / "myapp" / "index_partial.html"
        nested.parent.mkdir()
        nested.write_text("<div>nested</div>")
        assert find_partial_template(tmp_path) == nested

    def test_missing(self, tmp_path):
        assert find_partial_template(tmp_path) is None

    def test_nonexistent_dir(self, tmp_path):
        assert find_partial_template(tmp_path / "nope") is None


# ---------------------------------------------------------------------------
# resolve_template_dir / resolve_static_dir
# ---------------------------------------------------------------------------


class TestResolveDirs:
    def test_template_dir_exists(self, tmp_path):
        (tmp_path / "templates").mkdir()
        assert resolve_template_dir(tmp_path) == tmp_path / "templates"

    def test_template_dir_missing(self, tmp_path):
        assert resolve_template_dir(tmp_path) is None

    def test_static_dir_exists(self, tmp_path):
        (tmp_path / "static").mkdir()
        assert resolve_static_dir(tmp_path) == tmp_path / "static"

    def test_static_dir_missing(self, tmp_path):
        assert resolve_static_dir(tmp_path) is None


# ---------------------------------------------------------------------------
# parse_dev_module_name
# ---------------------------------------------------------------------------


class TestParseDevModuleName:
    def test_valid(self):
        assert parse_dev_module_name("dev__alice__myapp") == ("alice", "myapp")

    def test_not_dev_prefix(self):
        assert parse_dev_module_name("writer") is None

    def test_wrong_parts_count(self):
        assert parse_dev_module_name("dev__only") is None
        assert parse_dev_module_name("dev__a__b__c") is None


# ---------------------------------------------------------------------------
# safe_iterdir
# ---------------------------------------------------------------------------


class TestSafeIterdir:
    def test_skips_hidden(self, tmp_path):
        (tmp_path / ".hidden").mkdir()
        (tmp_path / "visible").mkdir()
        result = list(safe_iterdir(tmp_path))
        assert len(result) == 1
        assert result[0].name == "visible"

    def test_nonexistent_dir(self, tmp_path):
        result = list(safe_iterdir(tmp_path / "nope"))
        assert result == []


# ---------------------------------------------------------------------------
# validate_project_structure
# ---------------------------------------------------------------------------


class TestValidateProjectStructure:
    def test_valid_flat(self, tmp_path):
        (tmp_path / "templates").mkdir()
        (tmp_path / "templates" / "index_partial.html").write_text("<div/>")
        ok, msg = validate_project_structure(tmp_path)
        assert ok is True
        assert msg == "ok"

    def test_missing_templates(self, tmp_path):
        ok, msg = validate_project_structure(tmp_path)
        assert ok is False
        assert "templates" in msg

    def test_missing_partial(self, tmp_path):
        (tmp_path / "templates").mkdir()
        ok, msg = validate_project_structure(tmp_path)
        assert ok is False
        assert "index_partial" in msg

    def test_nonexistent(self, tmp_path):
        ok, msg = validate_project_structure(tmp_path / "nope")
        assert ok is False


# EOF
