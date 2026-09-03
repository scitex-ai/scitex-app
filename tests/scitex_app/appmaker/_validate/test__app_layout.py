"""Tests for scitex_app/appmaker/_validate/_app_layout.py."""

from __future__ import annotations

import json

from scitex_app.appmaker._validate import (
    validate_structure,
    _is_embedded_package,
    _get_frontend_type,
    _get_app_name,
)
from ._helpers import (
    write_manifest,
    make_minimal_embedded_app,
    make_full_standalone_app,
)



# ---------------------------------------------------------------------------
# Tests: _is_embedded_package
# ---------------------------------------------------------------------------


class TestIsEmbeddedPackage:
    def test_underscore_prefix_is_embedded(self, tmp_path):
        # Arrange
        embedded_dir = tmp_path / "_django"
        # Act
        embedded_dir.mkdir()
        # Assert
        assert _is_embedded_package(embedded_dir) is True

    def test_normal_name_without_manifest_is_not_embedded(self, tmp_path):
        # Arrange
        app_dir = tmp_path / "myapp"
        # Act
        app_dir.mkdir()
        # Assert
        assert _is_embedded_package(app_dir) is False

    def test_manifest_embedded_package_true(self, tmp_path):
        # Arrange
        # Act
        write_manifest(tmp_path, {"embedded_package": True})
        # Assert
        assert _is_embedded_package(tmp_path) is True

    def test_manifest_embedded_package_false(self, tmp_path):
        # Arrange
        # Act
        write_manifest(tmp_path, {"embedded_package": False})
        # Assert
        assert _is_embedded_package(tmp_path) is False

    def test_manifest_missing_embedded_package_key(self, tmp_path):
        # Arrange
        # Act
        write_manifest(tmp_path, {"name": "myapp"})
        # Assert
        assert _is_embedded_package(tmp_path) is False


# ---------------------------------------------------------------------------
# Tests: _get_frontend_type
# ---------------------------------------------------------------------------


class TestGetFrontendType:
    def test_returns_frontend_type_from_manifest(self, tmp_path):
        # Arrange
        # Act
        write_manifest(tmp_path, {"frontend_type": "react"})
        # Assert
        assert _get_frontend_type(tmp_path) == "react"

    def test_returns_empty_string_when_not_set(self, tmp_path):
        # Arrange
        # Act
        write_manifest(tmp_path, {"name": "app"})
        # Assert
        assert _get_frontend_type(tmp_path) == ""

    def test_returns_empty_string_when_no_manifest(self, tmp_path):
        # Arrange
        # Act
        # Assert
        assert _get_frontend_type(tmp_path) == ""


# ---------------------------------------------------------------------------
# Tests: _get_app_name
# ---------------------------------------------------------------------------


class TestGetAppName:
    def test_returns_name_from_manifest(self, tmp_path):
        # Arrange
        # Act
        write_manifest(tmp_path, {"name": "my_awesome_app"})
        # Assert
        assert _get_app_name(tmp_path) == "my_awesome_app"

    def test_falls_back_to_dir_name(self, tmp_path):
        # No manifest — should return dir name
        # Arrange
        # Act
        # Assert
        assert _get_app_name(tmp_path) == tmp_path.name

    def test_invalid_manifest_json_falls_back_to_dir_name(self, tmp_path):
        # Arrange
        # Act
        (tmp_path / "manifest.json").write_text("{broken", encoding="utf-8")
        # Assert
        assert _get_app_name(tmp_path) == tmp_path.name


# ---------------------------------------------------------------------------
# Tests: validate_structure
# ---------------------------------------------------------------------------


class TestValidateStructure:
    def test_missing_directory_returns_error(self, tmp_path):
        # Arrange
        # Act
        errors = validate_structure(tmp_path / "nonexistent")
        # Assert
        assert any("does not exist" in e for e in errors)

    def test_embedded_app_only_requires_core_files(self, tmp_path):
        # Arrange
        make_minimal_embedded_app(tmp_path)
        # Act
        errors = validate_structure(tmp_path)
        # Assert
        assert errors == []

    def test_missing_views_py_adds_error(self, tmp_path):
        # Arrange
        make_minimal_embedded_app(tmp_path)
        (tmp_path / "views.py").unlink()
        # Act
        errors = validate_structure(tmp_path)
        # Assert
        assert any("views.py" in e for e in errors)

    def test_missing_urls_py_adds_error(self, tmp_path):
        # Arrange
        make_minimal_embedded_app(tmp_path)
        (tmp_path / "urls.py").unlink()
        # Act
        errors = validate_structure(tmp_path)
        # Assert
        assert any("urls.py" in e for e in errors)

    def test_standalone_app_requires_apps_py(self, tmp_path):
        # Arrange
        make_full_standalone_app(tmp_path, "myapp")
        (tmp_path / "apps.py").unlink()
        # Act
        errors = validate_structure(tmp_path)
        # Assert
        assert any("apps.py" in e for e in errors)

    def test_standalone_app_requires_license(self, tmp_path):
        # Arrange
        make_full_standalone_app(tmp_path, "myapp")
        (tmp_path / "LICENSE").unlink()
        # Act
        errors = validate_structure(tmp_path)
        # Assert
        assert any("LICENSE" in e for e in errors)

    def test_standalone_app_requires_readme(self, tmp_path):
        # Arrange
        make_full_standalone_app(tmp_path, "myapp")
        (tmp_path / "README.md").unlink()
        # Act
        errors = validate_structure(tmp_path)
        # Assert
        assert any("README.md" in e for e in errors)

    def test_standalone_app_requires_partial_template(self, tmp_path):
        # Arrange
        make_full_standalone_app(tmp_path, "myapp")
        partial = tmp_path / "templates" / "myapp" / "index_partial.html"
        partial.unlink()
        # Act
        errors = validate_structure(tmp_path)
        # Assert
        assert any("index_partial.html" in e for e in errors)

    def test_standalone_app_requires_agents_config(self, tmp_path):
        # Arrange
        make_full_standalone_app(tmp_path, "myapp")
        (tmp_path / ".agents" / "agents.json").unlink()
        (tmp_path / ".agents" / "README.md").unlink() if (
            tmp_path / ".agents" / "README.md"
        ).exists() else None
        # Act
        errors = validate_structure(tmp_path)
        # Assert
        assert any(".agents" in e for e in errors)

    def test_react_frontend_skips_template_check(self, tmp_path):
        """React apps skip the template check."""
        # Arrange
        write_manifest(
            tmp_path,
            {
                "name": "react_app",
                "slug": "react-app",
                "label": "React App",
                "pip_package": "react-app",
                "icon": "fa",
                "license": "MIT",
                "frontend_type": "react",
                "dependencies": {"python": []},
            },
        )
        (tmp_path / "apps.py").touch()
        (tmp_path / "views.py").touch()
        (tmp_path / "urls.py").touch()
        (tmp_path / "LICENSE").write_text("MIT")
        (tmp_path / "README.md").write_text("# React App")
        agents_dir = tmp_path / ".agents"
        agents_dir.mkdir()
        (agents_dir / "agents.json").write_text("{}")
        # Act
        errors = validate_structure(tmp_path)
        # No error about missing template
        # Assert
        assert not any("index_partial.html" in e for e in errors)


# EOF
