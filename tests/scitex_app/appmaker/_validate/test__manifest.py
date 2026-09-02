"""Tests for scitex_app/appmaker/_validate/_manifest.py."""

from __future__ import annotations

import json

from scitex_app.appmaker._validate import (
    validate_manifest,
    MANIFEST_REQUIRED_KEYS,
)
from ._helpers import (
    write_manifest,
)


# ---------------------------------------------------------------------------
# Tests: validate_manifest
# ---------------------------------------------------------------------------


class TestValidateManifest:
    def test_missing_manifest_returns_error(self, tmp_path):
        # Arrange
        # Act
        errors = validate_manifest(tmp_path)
        # Assert
        assert any("not found" in e for e in errors)

    def test_invalid_json_returns_error(self, tmp_path):
        # Arrange
        (tmp_path / "manifest.json").write_text("{bad json}", encoding="utf-8")
        # Act
        errors = validate_manifest(tmp_path)
        # Assert
        assert any("not valid JSON" in e for e in errors)

    def test_non_object_manifest_returns_error(self, tmp_path):
        # Arrange
        (tmp_path / "manifest.json").write_text("[1, 2, 3]", encoding="utf-8")
        # Act
        errors = validate_manifest(tmp_path)
        # Assert
        assert any("must be a JSON object" in e for e in errors)

    def test_missing_required_keys_adds_errors(self, tmp_path):
        # Arrange
        (tmp_path / "manifest.json").write_text(json.dumps({"name": "myapp"}))
        # Act
        errors = validate_manifest(tmp_path)
        # All keys other than "name" should trigger errors
        # Assert
        assert len(errors) > 0

    def test_all_required_keys_present(self, tmp_path):
        # Arrange
        data = {k: "value" for k in MANIFEST_REQUIRED_KEYS}
        data["name"] = "my_app"
        data["slug"] = "my-app"
        data["label"] = "My App"
        data["icon"] = "fas fa-star"
        data["license"] = "MIT"
        write_manifest(tmp_path, data)
        # Act
        errors = validate_manifest(tmp_path)
        # Assert
        assert errors == []

    def test_name_without_app_suffix_adds_error(self, tmp_path):
        # Arrange
        data = {k: "value" for k in MANIFEST_REQUIRED_KEYS}
        data["name"] = "mybadname"  # no _app suffix
        write_manifest(tmp_path, data)
        # Act
        errors = validate_manifest(tmp_path)
        # Assert
        assert any("_app" in e or "-app" in e for e in errors)

    def test_name_with_app_suffix_accepted(self, tmp_path):
        # Arrange
        data = {k: "value" for k in MANIFEST_REQUIRED_KEYS}
        data["name"] = "my_app"
        write_manifest(tmp_path, data)
        errors = validate_manifest(tmp_path)
        # Act
        name_errors = [e for e in errors if "_app" in e or "-app" in e]
        # Assert
        assert name_errors == []

    def test_version_key_forbidden_adds_error(self, tmp_path):
        # A hand-written 'version' key is forbidden — the version derives at
        # runtime from the installed 'pip_package' (importlib.metadata).
        # Arrange
        data = {k: "value" for k in MANIFEST_REQUIRED_KEYS}
        data["name"] = "my_app"
        data["version"] = "1.0.0"
        write_manifest(tmp_path, data)
        # Act
        errors = validate_manifest(tmp_path)
        # Assert
        assert any("must NOT declare 'version'" in e for e in errors)

    def test_missing_pip_package_adds_error(self, tmp_path):
        # pip_package is required — the single source of truth for the version.
        # Arrange
        data = {k: "value" for k in MANIFEST_REQUIRED_KEYS if k != "pip_package"}
        data["name"] = "my_app"
        write_manifest(tmp_path, data)
        # Act
        errors = validate_manifest(tmp_path)
        # Assert
        assert any("pip_package" in e for e in errors)


# EOF
