"""Tests for scitex_app/appmaker/_validate/_dependencies.py."""

from __future__ import annotations


from scitex_app.appmaker._validate import (
    validate_dependencies,
)
from ._helpers import (
    write_manifest,
)


# ---------------------------------------------------------------------------
# Tests: validate_dependencies
# ---------------------------------------------------------------------------


class TestValidateDependencies:
    def test_no_manifest_returns_no_errors(self, tmp_path):
        # Arrange
        # Act
        errors = validate_dependencies(tmp_path)
        # Assert
        assert errors == []

    def test_missing_dependencies_field_adds_error(self, tmp_path):
        # Arrange
        write_manifest(tmp_path, {"name": "myapp"})
        # Act
        errors = validate_dependencies(tmp_path)
        # Assert
        assert any("dependencies" in e for e in errors)

    def test_valid_dependencies_passes(self, tmp_path):
        # Arrange
        write_manifest(
            tmp_path, {"name": "myapp", "dependencies": {"python": ["django>=4.0"]}}
        )
        # Act
        errors = validate_dependencies(tmp_path)
        # Assert
        assert errors == []

    def test_dependencies_not_dict_adds_error(self, tmp_path):
        # Arrange
        write_manifest(tmp_path, {"name": "myapp", "dependencies": ["django"]})
        # Act
        errors = validate_dependencies(tmp_path)
        # Assert
        assert any("must be a JSON object" in e for e in errors)

    def test_unknown_dependency_type_adds_error(self, tmp_path):
        # Arrange
        write_manifest(
            tmp_path, {"name": "myapp", "dependencies": {"alien": ["something"]}}
        )
        # Act
        errors = validate_dependencies(tmp_path)
        # Assert
        assert any("unknown dependency type" in e.lower() for e in errors)

    def test_dependency_value_not_list_adds_error(self, tmp_path):
        # Arrange
        write_manifest(
            tmp_path, {"name": "myapp", "dependencies": {"python": "django"}}
        )
        # Act
        errors = validate_dependencies(tmp_path)
        # Assert
        assert any("must be a list" in e for e in errors)

    def test_dependency_items_not_strings_adds_error(self, tmp_path):
        # Arrange
        write_manifest(
            tmp_path, {"name": "myapp", "dependencies": {"python": [1, 2, 3]}}
        )
        # Act
        errors = validate_dependencies(tmp_path)
        # Assert
        assert any("must be strings" in e for e in errors)

    def test_all_valid_dependency_types(self, tmp_path):
        # Arrange
        write_manifest(
            tmp_path,
            {
                "name": "myapp",
                "dependencies": {
                    "python": ["django"],
                    "system": ["git"],
                    "node": ["react"],
                    "r": ["ggplot2"],
                    "other": ["some-tool"],
                },
            },
        )
        # Act
        errors = validate_dependencies(tmp_path)
        # Assert
        assert errors == []


# EOF
