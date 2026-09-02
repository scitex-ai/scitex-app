"""Tests for scitex_app/appmaker/_validate/_manifest.py."""

from __future__ import annotations

import json

from scitex_app.appmaker._validate import (
    validate_manifest,
    validate_manifest_advisory,
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

    def test_name_without_app_suffix_is_not_an_error(self, tmp_path):
        """The suffix convention is advice; enforcing it made it unclearable."""
        # Arrange
        data = {k: "value" for k in MANIFEST_REQUIRED_KEYS}
        data["name"] = "mybadname"  # no _app suffix
        write_manifest(tmp_path, data)
        # Act
        errors = validate_manifest(tmp_path)
        # Assert
        assert not [e for e in errors if "_app" in e or "-app" in e]

    def test_name_without_app_suffix_is_an_advisory(self, tmp_path):
        """The other arm: moved to the warn tier, NOT deleted.

        Without this, the assertion above would also pass if the finding had
        simply been dropped -- which is the failure a "stop enforcing it" change
        most resembles.
        """
        # Arrange
        data = {k: "value" for k in MANIFEST_REQUIRED_KEYS}
        data["name"] = "mybadname"
        write_manifest(tmp_path, data)
        # Act
        warnings = validate_manifest_advisory(tmp_path)
        # Assert
        assert any("_app" in w or "-app" in w for w in warnings)

    def test_name_with_app_suffix_raises_no_advisory(self, tmp_path):
        # Arrange
        data = {k: "value" for k in MANIFEST_REQUIRED_KEYS}
        data["name"] = "my_app"
        write_manifest(tmp_path, data)
        # Act
        warnings = validate_manifest_advisory(tmp_path)
        # Assert
        assert warnings == []

    def test_advisory_on_a_missing_manifest_is_silent(self, tmp_path):
        """validate_manifest() already reports this, as an error; not twice."""
        # Arrange — tmp_path holds no manifest.json
        # Act
        warnings = validate_manifest_advisory(tmp_path)
        # Assert
        assert warnings == []

    def test_advisory_on_unparseable_json_is_silent(self, tmp_path):
        # Arrange
        (tmp_path / "manifest.json").write_text("{not json", encoding="utf-8")
        # Act
        warnings = validate_manifest_advisory(tmp_path)
        # Assert
        assert warnings == []

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
