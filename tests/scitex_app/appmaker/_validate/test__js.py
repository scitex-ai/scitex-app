"""Tests for scitex_app/appmaker/_validate/_js.py."""

from __future__ import annotations

from scitex_app.appmaker._validate import (
    DANGEROUS_JS_PATTERNS,
    validate_js,
)


# ─── the scan itself ────────────────────────────────────────────────────────
# One assertion each: "the scan is dead", "the skip list is wrong" and "a real
# pattern stopped matching" are different defects with different fixes.


def _app_with_js(tmp_path, source, relpath="app.js"):
    target = tmp_path / relpath
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(source, encoding="utf-8")
    return validate_js(tmp_path)


def test_document_cookie_is_reported(tmp_path):
    # Arrange — a cookie read from inside hub's shell.
    # Act
    found = _app_with_js(tmp_path, "const t = document.cookie;")
    # Assert
    assert len(found) == 1


def test_window_parent_is_reported(tmp_path):
    # Arrange — frame escape.
    # Act
    found = _app_with_js(tmp_path, "window.parent.postMessage('x', '*');")
    # Assert
    assert len(found) == 1


def test_clean_javascript_is_not_reported(tmp_path):
    """The direction that catches a rule which flags everything."""
    # Arrange
    # Act
    found = _app_with_js(tmp_path, "export const add = (a, b) => a + b;")
    # Assert
    assert found == []


def test_typescript_is_scanned_too(tmp_path):
    # Arrange — the suffix list claims .ts; this is the arm that proves it.
    # Act
    found = _app_with_js(tmp_path, "const t = document.cookie;", "src/app.ts")
    # Assert
    assert len(found) == 1


def test_node_modules_is_skipped(tmp_path):
    # Arrange — a dependency's code is not the app's code.
    # Act
    found = _app_with_js(tmp_path, "eval('1+1');", "node_modules/dep/index.js")
    # Assert
    assert found == []


def test_built_output_is_skipped(tmp_path):
    """DELIBERATELY opposite to the prefix rule, which scans dist on purpose.

    Minified vendor code contains eval( and Function( as a matter of course, so
    scanning build output here would report an app for code it did not write.
    """
    # Arrange
    # Act
    found = _app_with_js(tmp_path, "eval('1+1');", "dist/bundle.js")
    # Assert
    assert found == []


# ─── the known false positive, asserted rather than left to be discovered ───


def test_regexp_exec_is_reported_and_that_is_a_known_false_positive(tmp_path):
    """`exec(` is in the list because the PYTHON list was copy-pasted into it.

    `regex.exec(str)` is ordinary, correct JavaScript. This test does not
    endorse the finding — it PINS it, so that narrowing the pattern list later
    is a visible change to a recorded behaviour rather than a silent one, and so
    that nobody arms this rule believing it has no false-positive class.
    """
    # Arrange
    # Act
    found = _app_with_js(tmp_path, "const m = /a(b)/.exec(input);")
    # Assert
    assert len(found) == 1


def test_the_pattern_list_still_carries_the_python_leftovers(tmp_path):
    """Pins the ported list verbatim, so a narrowing is deliberate."""
    # Arrange
    # Act
    leftovers = [p for p in DANGEROUS_JS_PATTERNS if "subprocess" in p]
    # Assert
    assert leftovers == [r"\bsubprocess\b"]


# EOF
