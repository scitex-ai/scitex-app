"""Tests for scitex_app/appmaker/_validate/_privileges.py."""

from __future__ import annotations

import json

from scitex_app.appmaker._validate import (
    VALID_PRIVILEGE_TYPES,
    validate_privileges,
)


def _manifest(tmp_path, privileges):
    data = {"name": "my_app"}
    if privileges is not None:
        data["privileges"] = privileges
    (tmp_path / "manifest.json").write_text(json.dumps(data), encoding="utf-8")
    return validate_privileges(tmp_path)


def test_a_valid_declaration_is_accepted(tmp_path):
    # Arrange
    # Act
    found = _manifest(tmp_path, [{"type": "filesystem", "scope": "readonly"}])
    # Assert
    assert found == []


def test_an_unknown_privilege_type_is_reported(tmp_path):
    # Arrange
    # Act
    found = _manifest(tmp_path, [{"type": "gpu", "scope": "none"}])
    # Assert
    assert any("Unknown privilege type" in e for e in found)


def test_a_scope_from_the_wrong_type_is_reported(tmp_path):
    """`readonly` is a filesystem scope; declaring it for `network` is a typo."""
    # Arrange
    # Act
    found = _manifest(tmp_path, [{"type": "network", "scope": "readonly"}])
    # Assert
    assert any("Invalid scope" in e for e in found)


def test_a_non_dict_entry_is_reported(tmp_path):
    # Arrange
    # Act
    found = _manifest(tmp_path, ["filesystem"])
    # Assert
    assert any("not a dict" in e for e in found)


def test_a_non_list_privileges_key_is_reported(tmp_path):
    # Arrange
    # Act
    found = _manifest(tmp_path, {"type": "api"})
    # Assert
    assert found == ["manifest.json 'privileges' must be a list"]


def test_no_privileges_key_reports_nothing(tmp_path):
    """This rule checks the SHAPE of a declaration, not that one exists.

    Whether an app MUST declare its privileges is a platform decision. Asserting
    it here would smuggle a requirement in under the name of a format check.
    """
    # Arrange
    # Act
    found = _manifest(tmp_path, None)
    # Assert
    assert found == []


def test_a_missing_manifest_reports_nothing(tmp_path):
    """validate_manifest() already reports that, as an error; not twice."""
    # Arrange — tmp_path holds no manifest.json
    # Act
    found = validate_privileges(tmp_path)
    # Assert
    assert found == []


def test_the_valid_types_are_the_three_the_platform_grants(tmp_path):
    # Arrange
    # Act
    types = sorted(VALID_PRIVILEGE_TYPES)
    # Assert
    assert types == ["api", "filesystem", "network"]


# EOF
