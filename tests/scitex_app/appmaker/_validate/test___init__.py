"""Tests for scitex_app/appmaker/_validate/__init__.py."""

from __future__ import annotations

import json

from scitex_app.appmaker._validate import (
    validate,
    validate_templates,
    validate_css,
    _is_embedded_package,
    REQUIRED_FILES,
    FORBIDDEN_PATTERNS,
    MANIFEST_REQUIRED_KEYS,
    PROTECTED_SELECTORS,
    FORBIDDEN_BLOCK_OVERRIDES,
)
from ._helpers import (
    make_minimal_embedded_app,
)


# ---------------------------------------------------------------------------
# Tests: full validate() pipeline
# ---------------------------------------------------------------------------


class TestFullValidate:
    def test_embedded_app_with_all_required_files_passes(self, tmp_path):
        # Arrange
        make_minimal_embedded_app(tmp_path)
        # Act
        errors = validate(tmp_path)
        # Assert
        assert errors == []

    def test_missing_manifest_produces_errors(self, tmp_path):
        # Arrange
        (tmp_path / "views.py").touch()
        (tmp_path / "urls.py").touch()
        # Act
        errors = validate(tmp_path)
        # Assert
        assert len(errors) > 0

    def test_nonexistent_directory_produces_error(self, tmp_path):
        # Arrange
        # Act
        errors = validate(tmp_path / "does_not_exist")
        # Assert
        assert any("does not exist" in e for e in errors)

    def test_security_errors_included_in_full_validate(self, tmp_path):
        # Arrange
        make_minimal_embedded_app(tmp_path)
        (tmp_path / "utils.py").write_text("import subprocess\n", encoding="utf-8")
        # Act
        errors = validate(tmp_path)
        # Assert
        assert any("subprocess" in e for e in errors)

    def test_embedded_skips_template_and_css_checks(self, tmp_path):
        """Embedded apps skip template and CSS validation."""
        # Arrange
        make_minimal_embedded_app(tmp_path)
        # Add a CSS file that would fail standalone checks
        (tmp_path / "bad.css").write_text("footer { display: none; }")
        errors = validate(tmp_path)
        # CSS check is still run for embedded — only template check is skipped
        # But embedded=True means validate_templates/validate_css skipped
        # Actually _is_embedded_package=True skips those two checks
        # Act
        css_errors = [e for e in errors if "footer" in e]
        # Assert
        assert css_errors == []  # CSS skipped for embedded


# ---------------------------------------------------------------------------
# Tests: constants
# ---------------------------------------------------------------------------


class TestConstants:
    def test_required_files_list_views_py_in_required_files(self):
        # Arrange
        # Act
        # Assert
        # Arrange
        # Act
        # Assert
        assert "views.py" in REQUIRED_FILES

    def test_required_files_list_urls_py_in_required_files(self):
        # Arrange
        # Act
        # Assert
        # Arrange
        # Act
        # Assert
        assert "urls.py" in REQUIRED_FILES

    def test_required_files_list_manifest_json_in_required_files(self):
        # Arrange
        # Act
        # Assert
        # Arrange
        # Act
        # Assert
        assert "manifest.json" in REQUIRED_FILES


    def test_forbidden_patterns_list_subprocess_in_pattern_names(self):
        # Arrange
        # Arrange
        # Act
        pattern_names = [name for _, name in FORBIDDEN_PATTERNS]
        # Act
        # Assert
        # Assert
        assert "subprocess" in pattern_names

    def test_forbidden_patterns_list_eval_in_pattern_names(self):
        # Arrange
        # Arrange
        # Act
        pattern_names = [name for _, name in FORBIDDEN_PATTERNS]
        # Act
        # Assert
        # Assert
        assert "eval()" in pattern_names


    def test_manifest_required_keys_name_in_manifest_required_keys(self):
        # Arrange
        # Act
        # Assert
        # Arrange
        # Act
        # Assert
        assert "name" in MANIFEST_REQUIRED_KEYS

    def test_manifest_required_keys_slug_in_manifest_required_keys(self):
        # Arrange
        # Act
        # Assert
        # Arrange
        # Act
        # Assert
        assert "slug" in MANIFEST_REQUIRED_KEYS

    def test_manifest_required_keys_license_in_manifest_required_keys(self):
        # Arrange
        # Act
        # Assert
        # Arrange
        # Act
        # Assert
        assert "license" in MANIFEST_REQUIRED_KEYS

    def test_manifest_required_keys_pip_package_in_manifest_required_keys(self):
        # Arrange
        # Act
        # Assert
        assert "pip_package" in MANIFEST_REQUIRED_KEYS


    def test_protected_selectors_len_protected_selectors_0(self):
        # Arrange
        # Act
        # Assert
        # Arrange
        # Act
        # Assert
        assert len(PROTECTED_SELECTORS) > 0

    def test_protected_selectors_any_stx_shell_in_s_for_s_in_protected_selectors(self):
        # Arrange
        # Act
        # Assert
        # Arrange
        # Act
        # Assert
        assert any("stx-shell" in s for s in PROTECTED_SELECTORS)


    def test_forbidden_block_overrides(self):
        # Arrange
        # Act
        # Assert
        assert len(FORBIDDEN_BLOCK_OVERRIDES) > 0


def _embedded_app_with_bad_css(tmp_path, frontend_type):
    """An embedded app whose CSS breaks a workspace frame rule."""
    import json as _json

    app = tmp_path / "_django"
    app.mkdir()
    manifest = {"embedded_package": True}
    if frontend_type is not None:
        manifest["frontend_type"] = frontend_type
    (app / "manifest.json").write_text(_json.dumps(manifest), encoding="utf-8")
    (app / "app.css").write_text("footer { display: none; }", encoding="utf-8")
    from scitex_app.appmaker._validate import validate_css

    return app, validate_css(app)


def test_the_css_rule_itself_fires_on_this_fixture(tmp_path):
    # Arrange — calibration. Every arm below asserts about whether validate_css
    # RUNS; that is meaningless unless the rule would fire on this input.
    _app, direct = _embedded_app_with_bad_css(tmp_path, "vanilla")
    # Act
    fired = len(direct)
    # Assert
    assert fired == 1


def test_an_embedded_non_react_app_is_css_validated(tmp_path):
    # Arrange — THE FIX. scitex-scholar's shape: embedded, frontend_type
    # "vanilla", hand-written CSS, previously skipped on the directory name.
    from scitex_app.appmaker._validate import validate as _validate

    app, _ = _embedded_app_with_bad_css(tmp_path, "vanilla")
    # Act
    reported = _validate(app)
    # Assert
    assert [e for e in reported if "footer" in e]


def test_an_embedded_react_app_is_still_skipped(tmp_path):
    # Arrange — compiled output is not hand-written and must not be linted for
    # frame conventions. This is the behaviour the old comment intended.
    from scitex_app.appmaker._validate import validate as _validate

    app, _ = _embedded_app_with_bad_css(tmp_path, "react")
    # Act
    reported = _validate(app)
    # Assert
    assert not [e for e in reported if "footer" in e]


def test_an_embedded_app_with_no_declared_frontend_type_is_still_skipped(tmp_path):
    # Arrange — conservative arm. An undeclared app may be a React build, and
    # guessing would invent findings on compiled output. Preserves today.
    from scitex_app.appmaker._validate import validate as _validate

    app, _ = _embedded_app_with_bad_css(tmp_path, None)
    # Act
    reported = _validate(app)
    # Assert
    assert not [e for e in reported if "footer" in e]


# ─── variable-prefixed URLs are a THIRD value, not a violation ──────────────
# 0.9.0 flagged `${STX_MOUNT}/api/x` — the exact code its own remediation text
# prescribes — because it collapsed "variable-prefixed" into "inferred-base".
# Reported by scitex-scholar against their CORRECTED tree.


# EOF
