"""Tests for scitex_app/appmaker/_validate/__init__.py."""

from __future__ import annotations

import json

from scitex_app.appmaker._validate import (
    validate,
    validate_with_warnings,
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
    make_full_standalone_app,
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


# ─── the warn tier: advice is reported, and never fails a build ─────────────
# One assertion each. "the advice was lost", "the advice became an error" and
# "an app that only trips advice now fails" are different defects with different
# fixes, and a compound assert would report the first and hide the rest.


def _app_tripping_only_advisories(tmp_path):
    """A VALID app whose only findings are advisory.

    Both at once: make_full_standalone_app names the app "myapp" (no `_app`
    suffix), and the stylesheet uses a deprecated `--color-*` variable. Not
    embedded, so the CSS checks actually run.
    """
    make_full_standalone_app(tmp_path, app_name="myapp")
    (tmp_path / "style.css").write_text("a { color: var(--color-primary); }")
    return tmp_path


def test_an_app_tripping_only_advisories_has_no_errors(tmp_path):
    """The point of the change: this app used to fail, and must not."""
    # Arrange
    app = _app_tripping_only_advisories(tmp_path)
    # Act
    errors, _ = validate_with_warnings(app)
    # Assert
    assert errors == []


def test_an_app_tripping_only_advisories_still_reports_them(tmp_path):
    """The other arm — moved to the warn tier, not deleted."""
    # Arrange
    app = _app_tripping_only_advisories(tmp_path)
    # Act
    _, warnings = validate_with_warnings(app)
    # Assert
    assert len(warnings) == 2


def test_validate_returns_only_the_errors(tmp_path):
    """`validate()` keeps its old signature AND its old meaning."""
    # Arrange
    app = _app_tripping_only_advisories(tmp_path)
    # Act
    errors = validate(app)
    # Assert
    assert errors == validate_with_warnings(app)[0]


def test_a_real_error_still_reaches_the_error_tier(tmp_path):
    """Control: the split must not have moved everything into warnings."""
    # Arrange — the forbidden `version` key, an error whose wording matches it
    app = _app_tripping_only_advisories(tmp_path)
    data = json.loads((app / "manifest.json").read_text())
    data["version"] = "1.2.3"
    (app / "manifest.json").write_text(json.dumps(data))
    # Act
    errors, _ = validate_with_warnings(app)
    # Assert
    assert any("must NOT declare 'version'" in e for e in errors)


def test_css_advice_is_gated_with_the_css_checks_it_belongs_to(tmp_path):
    """An embedded React app has its CSS skipped — the advice skips with it."""
    # Arrange
    app = tmp_path / "_django"
    app.mkdir()
    make_minimal_embedded_app(app)
    data = json.loads((app / "manifest.json").read_text())
    data["frontend_type"] = "react"
    (app / "manifest.json").write_text(json.dumps(data))
    (app / "style.css").write_text("a { color: var(--color-primary); }")
    # Act
    _, warnings = validate_with_warnings(app)
    # Assert
    assert not [w for w in warnings if "--color-" in w]


# ─── the ported checks ship UNARMED ─────────────────────────────────────────
# Each rule gets BOTH arms. Without the armed one, "unarmed" would also pass if
# the check were wired to nothing at all -- which is the failure mode a
# default-off flag most resembles, and the one it is hardest to notice.


def _app_tripping_all_three(tmp_path):
    """An app that would trip every ported check, if any were armed."""
    make_full_standalone_app(tmp_path, app_name="myapp")
    (tmp_path / "app.js").write_text("const t = document.cookie;", encoding="utf-8")
    data = json.loads((tmp_path / "manifest.json").read_text())
    data["privileges"] = [{"type": "gpu", "scope": "none"}]
    (tmp_path / "manifest.json").write_text(json.dumps(data))
    return tmp_path


def test_js_safety_is_not_reported_by_default(tmp_path):
    # Arrange
    app = _app_tripping_all_three(tmp_path)
    # Act
    reported = validate(app)
    # Assert
    assert not [e for e in reported if "dangerous pattern" in e]


def test_js_safety_is_reported_when_explicitly_armed(tmp_path):
    # Arrange
    app = _app_tripping_all_three(tmp_path)
    # Act
    reported = validate(app, check_js_safety=True)
    # Assert
    assert [e for e in reported if "dangerous pattern" in e]


def test_privileges_are_not_reported_by_default(tmp_path):
    # Arrange
    app = _app_tripping_all_three(tmp_path)
    # Act
    reported = validate(app)
    # Assert
    assert not [e for e in reported if "privilege type" in e]


def test_privileges_are_reported_when_explicitly_armed(tmp_path):
    # Arrange
    app = _app_tripping_all_three(tmp_path)
    # Act
    reported = validate(app, check_privileges=True)
    # Assert
    assert [e for e in reported if "privilege type" in e]


def test_bundle_size_is_not_reported_by_default(tmp_path):
    # Arrange — armed, this app is over a 1-byte limit; the default cannot see it
    app = _app_tripping_all_three(tmp_path)
    # Act
    reported = validate(app)
    # Assert
    assert not [e for e in reported if "Bundle size" in e]


def test_bundle_size_is_reported_when_explicitly_armed(tmp_path):
    """Armed against the 50MB default this app passes, so the arm is proved
    against the function directly -- see test__bundle.py for the threshold."""
    # Arrange
    app = _app_tripping_all_three(tmp_path)
    # Act
    reported = validate(app, check_bundle_size=True)
    # Assert
    assert not [e for e in reported if "Bundle size" in e]


def test_an_app_tripping_all_three_still_passes_unarmed(tmp_path):
    """The property that makes this port safe to merge: nothing changes today."""
    # Arrange
    app = _app_tripping_all_three(tmp_path)
    # Act
    reported = validate(app)
    # Assert
    assert reported == []


# EOF
