#!/usr/bin/env python3
# Timestamp: 2026-03-21
# File: tests/test__validator.py

"""Tests for scitex_app/validator.py — AppValidator class."""

from __future__ import annotations

import json
from pathlib import Path


from scitex_app.validator import (
    AppValidator,
    ValidationResult,
    MANIFEST_REQUIRED_FIELDS,
    VALID_PRIVILEGE_TYPES,
    VALID_FILESYSTEM_SCOPES,
    VALID_NETWORK_SCOPES,
    VALID_API_SCOPES,
    SHELL_SELECTORS,
    DANGEROUS_JS_PATTERNS,
    DEFAULT_MAX_BUNDLE_SIZE,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def write_manifest(path: Path, data: dict) -> None:
    (path / "manifest.json").write_text(json.dumps(data), encoding="utf-8")


def make_valid_manifest(path: Path) -> None:
    write_manifest(
        path,
        {
            "name": "test_app",
            "slug": "test-app",
            "label": "Test App",
            "version": "1.0.0",
            "icon": "fas fa-flask",
        },
    )


# ---------------------------------------------------------------------------
# Tests: ValidationResult dataclass
# ---------------------------------------------------------------------------


class TestValidationResult:
    def test_initial_state_is_passed(self):
        result = ValidationResult()
        assert result.passed is True
        assert result.errors == []
        assert result.warnings == []

    def test_add_error_sets_passed_false(self):
        result = ValidationResult()
        result.add_error("something is broken")
        assert result.passed is False
        assert "something is broken" in result.errors

    def test_add_warning_does_not_fail(self):
        result = ValidationResult()
        result.add_warning("minor issue")
        assert result.passed is True
        assert "minor issue" in result.warnings

    def test_multiple_errors_accumulate(self):
        result = ValidationResult()
        result.add_error("err1")
        result.add_error("err2")
        assert len(result.errors) == 2
        assert result.passed is False


# ---------------------------------------------------------------------------
# Tests: validate_manifest
# ---------------------------------------------------------------------------


class TestValidateManifest:
    def test_valid_manifest_in_root(self, tmp_path):
        make_valid_manifest(tmp_path)
        validator = AppValidator(tmp_path)
        validator.validate_manifest()
        assert validator._result.passed is True
        assert validator._result.manifest is not None

    def test_valid_manifest_in_django_subdir(self, tmp_path):
        django_dir = tmp_path / "_django"
        django_dir.mkdir()
        make_valid_manifest(django_dir)
        validator = AppValidator(tmp_path)
        validator.validate_manifest()
        assert validator._result.passed is True

    def test_missing_manifest_adds_error(self, tmp_path):
        validator = AppValidator(tmp_path)
        validator.validate_manifest()
        assert validator._result.passed is False
        assert any("No manifest.json" in e for e in validator._result.errors)

    def test_invalid_json_adds_error(self, tmp_path):
        (tmp_path / "manifest.json").write_text("{broken json", encoding="utf-8")
        validator = AppValidator(tmp_path)
        validator.validate_manifest()
        assert validator._result.passed is False
        assert any("invalid JSON" in e for e in validator._result.errors)

    def test_missing_fields_adds_error(self, tmp_path):
        write_manifest(tmp_path, {"name": "test_app"})
        validator = AppValidator(tmp_path)
        validator.validate_manifest()
        assert validator._result.passed is False
        assert any("missing required fields" in e for e in validator._result.errors)

    def test_all_required_fields_present(self, tmp_path):
        data = {field: "value" for field in MANIFEST_REQUIRED_FIELDS}
        data["version"] = "1.0.0"
        write_manifest(tmp_path, data)
        validator = AppValidator(tmp_path)
        validator.validate_manifest()
        errors = [e for e in validator._result.errors if "missing" in e.lower()]
        assert errors == []

    def test_non_string_name_adds_error(self, tmp_path):
        write_manifest(
            tmp_path,
            {"name": 123, "slug": "x", "label": "x", "version": "1.0.0", "icon": "x"},
        )
        validator = AppValidator(tmp_path)
        validator.validate_manifest()
        assert any("name must be a string" in e for e in validator._result.errors)

    def test_non_semver_version_adds_warning(self, tmp_path):
        write_manifest(
            tmp_path,
            {
                "name": "x",
                "slug": "x",
                "label": "x",
                "version": "alpha",
                "icon": "x",
            },
        )
        validator = AppValidator(tmp_path)
        validator.validate_manifest()
        assert any("semver" in w for w in validator._result.warnings)

    def test_privileges_extracted_from_manifest(self, tmp_path):
        privs = [{"type": "filesystem", "scope": "project"}]
        write_manifest(
            tmp_path,
            {
                "name": "x",
                "slug": "x",
                "label": "x",
                "version": "1.0.0",
                "icon": "x",
                "privileges": privs,
            },
        )
        validator = AppValidator(tmp_path)
        validator.validate_manifest()
        assert validator._result.privileges == privs


# ---------------------------------------------------------------------------
# Tests: validate_structure
# ---------------------------------------------------------------------------


class TestValidateStructure:
    def test_no_django_dir_adds_warning(self, tmp_path):
        validator = AppValidator(tmp_path)
        validator.validate_structure()
        assert any("_django" in w for w in validator._result.warnings)

    def test_django_dir_with_required_files_passes(self, tmp_path):
        django_dir = tmp_path / "_django"
        django_dir.mkdir()
        (django_dir / "views.py").touch()
        (django_dir / "urls.py").touch()
        validator = AppValidator(tmp_path)
        validator.validate_structure()
        assert validator._result.passed is True

    def test_django_dir_missing_views_adds_error(self, tmp_path):
        django_dir = tmp_path / "_django"
        django_dir.mkdir()
        (django_dir / "urls.py").touch()
        # views.py is missing
        validator = AppValidator(tmp_path)
        validator.validate_structure()
        assert validator._result.passed is False
        assert any("views.py" in e for e in validator._result.errors)

    def test_django_dir_missing_urls_adds_error(self, tmp_path):
        django_dir = tmp_path / "_django"
        django_dir.mkdir()
        (django_dir / "views.py").touch()
        # urls.py is missing
        validator = AppValidator(tmp_path)
        validator.validate_structure()
        assert validator._result.passed is False
        assert any("urls.py" in e for e in validator._result.errors)

    def test_app_path_is_django_dir_itself(self, tmp_path):
        """If app_path has views.py at root level, treat it as the _django dir."""
        (tmp_path / "views.py").touch()
        (tmp_path / "urls.py").touch()
        validator = AppValidator(tmp_path)
        validator.validate_structure()
        # Should pass since views.py and urls.py are present
        assert validator._result.passed is True


# ---------------------------------------------------------------------------
# Tests: validate_css
# ---------------------------------------------------------------------------


class TestValidateCss:
    def test_clean_css_passes(self, tmp_path):
        css = tmp_path / "styles.css"
        css.write_text("body { margin: 0; }", encoding="utf-8")
        validator = AppValidator(tmp_path)
        validator.validate_css()
        assert validator._result.passed is True

    def test_shell_selector_in_css_adds_error(self, tmp_path):
        bad_selector = next(iter(SHELL_SELECTORS))
        css = tmp_path / "bad.css"
        css.write_text(f"{bad_selector} {{ color: red; }}", encoding="utf-8")
        validator = AppValidator(tmp_path)
        validator.validate_css()
        assert validator._result.passed is False
        assert any("shell selector" in e for e in validator._result.errors)

    def test_skip_dirs_excluded_from_css_scan(self, tmp_path):
        """CSS files in node_modules/ are not scanned."""
        skip_dir = tmp_path / "node_modules"
        skip_dir.mkdir()
        bad_selector = next(iter(SHELL_SELECTORS))
        css = skip_dir / "vendor.css"
        css.write_text(f"{bad_selector} {{ color: red; }}", encoding="utf-8")
        validator = AppValidator(tmp_path)
        validator.validate_css()
        # Should pass — node_modules is skipped
        assert validator._result.passed is True

    def test_multiple_shell_selectors_each_add_error(self, tmp_path):
        content = "\n".join(f"{s} {{ color: red; }}" for s in list(SHELL_SELECTORS)[:2])
        css = tmp_path / "multi.css"
        css.write_text(content, encoding="utf-8")
        validator = AppValidator(tmp_path)
        validator.validate_css()
        assert len(validator._result.errors) >= 2


# ---------------------------------------------------------------------------
# Tests: validate_js
# ---------------------------------------------------------------------------


class TestValidateJs:
    def test_clean_js_passes(self, tmp_path):
        js = tmp_path / "app.js"
        js.write_text("console.log('hello');", encoding="utf-8")
        validator = AppValidator(tmp_path)
        validator.validate_js()
        assert validator._result.passed is True

    def test_eval_in_js_adds_error(self, tmp_path):
        js = tmp_path / "bad.js"
        js.write_text("eval('dangerous code');", encoding="utf-8")
        validator = AppValidator(tmp_path)
        validator.validate_js()
        assert validator._result.passed is False
        assert any("dangerous pattern" in e for e in validator._result.errors)

    def test_subprocess_in_js_adds_error(self, tmp_path):
        js = tmp_path / "bad.js"
        js.write_text("const subprocess = require('child_process');", encoding="utf-8")
        validator = AppValidator(tmp_path)
        validator.validate_js()
        assert validator._result.passed is False

    def test_document_cookie_adds_error(self, tmp_path):
        js = tmp_path / "tracker.js"
        js.write_text("let c = document.cookie;", encoding="utf-8")
        validator = AppValidator(tmp_path)
        validator.validate_js()
        assert validator._result.passed is False

    def test_typescript_file_scanned(self, tmp_path):
        ts = tmp_path / "component.ts"
        ts.write_text("eval('bad');", encoding="utf-8")
        validator = AppValidator(tmp_path)
        validator.validate_js()
        assert validator._result.passed is False

    def test_skip_dirs_excluded_from_js_scan(self, tmp_path):
        """JS files in dist/ are not scanned."""
        dist_dir = tmp_path / "dist"
        dist_dir.mkdir()
        js = dist_dir / "bundle.js"
        js.write_text("eval('build artifact');", encoding="utf-8")
        validator = AppValidator(tmp_path)
        validator.validate_js()
        # dist is in SKIP_DIRS — should pass
        assert validator._result.passed is True


# ---------------------------------------------------------------------------
# Tests: validate_bundle_size
# ---------------------------------------------------------------------------


class TestValidateBundleSize:
    def test_small_bundle_passes(self, tmp_path):
        (tmp_path / "small.txt").write_text("tiny file", encoding="utf-8")
        validator = AppValidator(tmp_path)
        validator.validate_bundle_size()
        assert validator._result.passed is True

    def test_oversized_bundle_adds_error(self, tmp_path):
        big = tmp_path / "big.bin"
        # Write more than 50MB
        big.write_bytes(b"x" * (DEFAULT_MAX_BUNDLE_SIZE + 1))
        validator = AppValidator(tmp_path)
        validator.validate_bundle_size()
        assert validator._result.passed is False
        assert any("exceeds limit" in e for e in validator._result.errors)

    def test_custom_max_bundle_size(self, tmp_path):
        (tmp_path / "data.bin").write_bytes(b"x" * 1000)
        validator = AppValidator(tmp_path, max_bundle_size=500)
        validator.validate_bundle_size()
        assert validator._result.passed is False

    def test_node_modules_excluded_from_bundle_size(self, tmp_path):
        nm = tmp_path / "node_modules"
        nm.mkdir()
        # Write a huge file in node_modules — should be excluded
        (nm / "vendor.js").write_bytes(b"x" * (DEFAULT_MAX_BUNDLE_SIZE + 1))
        (tmp_path / "app.js").write_text("console.log(1);")
        validator = AppValidator(tmp_path)
        validator.validate_bundle_size()
        assert validator._result.passed is True


# ---------------------------------------------------------------------------
# Tests: validate_privileges
# ---------------------------------------------------------------------------


class TestValidatePrivileges:
    def _validator_with_privs(self, tmp_path, privileges):
        validator = AppValidator(tmp_path)
        validator._result.privileges = privileges
        return validator

    def test_valid_filesystem_privilege(self, tmp_path):
        privs = [{"type": "filesystem", "scope": "project"}]
        v = self._validator_with_privs(tmp_path, privs)
        v.validate_privileges()
        assert v._result.passed is True

    def test_valid_network_privilege(self, tmp_path):
        privs = [{"type": "network", "scope": "none"}]
        v = self._validator_with_privs(tmp_path, privs)
        v.validate_privileges()
        assert v._result.passed is True

    def test_valid_api_privilege(self, tmp_path):
        privs = [{"type": "api", "scope": "scitex"}]
        v = self._validator_with_privs(tmp_path, privs)
        v.validate_privileges()
        assert v._result.passed is True

    def test_unknown_privilege_type_adds_error(self, tmp_path):
        privs = [{"type": "database", "scope": "all"}]
        v = self._validator_with_privs(tmp_path, privs)
        v.validate_privileges()
        assert v._result.passed is False
        assert any("Unknown privilege type" in e for e in v._result.errors)

    def test_invalid_scope_for_filesystem_adds_error(self, tmp_path):
        privs = [{"type": "filesystem", "scope": "all"}]
        v = self._validator_with_privs(tmp_path, privs)
        v.validate_privileges()
        assert v._result.passed is False
        assert any("Invalid scope" in e for e in v._result.errors)

    def test_invalid_scope_for_network_adds_error(self, tmp_path):
        privs = [{"type": "network", "scope": "project"}]
        v = self._validator_with_privs(tmp_path, privs)
        v.validate_privileges()
        assert v._result.passed is False

    def test_invalid_scope_for_api_adds_error(self, tmp_path):
        privs = [{"type": "api", "scope": "database"}]
        v = self._validator_with_privs(tmp_path, privs)
        v.validate_privileges()
        assert v._result.passed is False

    def test_non_dict_privilege_adds_error(self, tmp_path):
        privs = ["not-a-dict"]
        v = self._validator_with_privs(tmp_path, privs)
        v.validate_privileges()
        assert v._result.passed is False
        assert any("not a dict" in e for e in v._result.errors)

    def test_multiple_valid_privileges(self, tmp_path):
        privs = [
            {"type": "filesystem", "scope": "readonly"},
            {"type": "api", "scope": "llm"},
        ]
        v = self._validator_with_privs(tmp_path, privs)
        v.validate_privileges()
        assert v._result.passed is True


# ---------------------------------------------------------------------------
# Tests: full validate() pipeline
# ---------------------------------------------------------------------------


class TestFullValidate:
    def test_valid_app_passes_all_checks(self, tmp_path):
        make_valid_manifest(tmp_path)
        django_dir = tmp_path / "_django"
        django_dir.mkdir()
        (django_dir / "views.py").touch()
        (django_dir / "urls.py").touch()
        validator = AppValidator(tmp_path)
        result = validator.validate()
        assert result.passed is True
        assert result.errors == []

    def test_multiple_issues_collected(self, tmp_path):
        """validate() collects errors from multiple checks."""
        # No manifest and no _django dir
        validator = AppValidator(tmp_path)
        result = validator.validate()
        assert result.passed is False
        assert len(result.errors) >= 1

    def test_validate_returns_fresh_result_on_repeated_calls(self, tmp_path):
        make_valid_manifest(tmp_path)
        validator = AppValidator(tmp_path)
        result1 = validator.validate()
        result2 = validator.validate()
        # Both should be independent results
        assert result1 is not result2

    def test_privileges_validated_when_manifest_present(self, tmp_path):
        write_manifest(
            tmp_path,
            {
                "name": "x",
                "slug": "x",
                "label": "x",
                "version": "1.0.0",
                "icon": "x",
                "privileges": [{"type": "invalid_type", "scope": "none"}],
            },
        )
        validator = AppValidator(tmp_path)
        result = validator.validate()
        assert any("Unknown privilege type" in e for e in result.errors)


# ---------------------------------------------------------------------------
# Tests: constants
# ---------------------------------------------------------------------------


class TestConstants:
    def test_manifest_required_fields(self):
        assert "name" in MANIFEST_REQUIRED_FIELDS
        assert "slug" in MANIFEST_REQUIRED_FIELDS
        assert "label" in MANIFEST_REQUIRED_FIELDS
        assert "version" in MANIFEST_REQUIRED_FIELDS
        assert "icon" in MANIFEST_REQUIRED_FIELDS

    def test_valid_privilege_types(self):
        assert "filesystem" in VALID_PRIVILEGE_TYPES
        assert "network" in VALID_PRIVILEGE_TYPES
        assert "api" in VALID_PRIVILEGE_TYPES

    def test_valid_filesystem_scopes(self):
        assert "project" in VALID_FILESYSTEM_SCOPES
        assert "readonly" in VALID_FILESYSTEM_SCOPES
        assert "none" in VALID_FILESYSTEM_SCOPES

    def test_valid_network_scopes(self):
        assert "none" in VALID_NETWORK_SCOPES
        assert "allowlist" in VALID_NETWORK_SCOPES

    def test_valid_api_scopes(self):
        assert "scitex" in VALID_API_SCOPES
        assert "llm" in VALID_API_SCOPES
        assert "none" in VALID_API_SCOPES

    def test_dangerous_js_patterns_is_non_empty(self):
        assert len(DANGEROUS_JS_PATTERNS) > 0

    def test_shell_selectors_is_non_empty(self):
        assert len(SHELL_SELECTORS) > 0

    def test_default_max_bundle_size(self):
        assert DEFAULT_MAX_BUNDLE_SIZE == 50 * 1024 * 1024


# EOF
