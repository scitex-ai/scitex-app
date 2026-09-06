"""Tests for scitex_app/appmaker/_validate/_js.py."""

from __future__ import annotations

import re

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


# ─── the false positive that the fleet measurement removed ──────────────────
# writer/_django was the ONLY app package producing a finding, and the finding
# was `re.exec(line)` in a while loop (editor.js:812). Armed as ported, this
# rule's first act would have been to fail a peer's build over a regex
# iteration. These two arms keep that from coming back.


def test_regexp_exec_is_not_reported(tmp_path):
    """The exact shape measured in writer: correct, ordinary JavaScript."""
    # Arrange
    # Act
    found = _app_with_js(tmp_path, "while ((m = re.exec(line)) !== null) {}")
    # Assert
    assert found == []


def test_the_python_only_patterns_are_gone(tmp_path):
    """`subprocess` in a browser bundle describes no JavaScript hazard."""
    # Arrange
    # Act
    leftovers = [
        p
        for p in DANGEROUS_JS_PATTERNS
        if any(k in p for k in ("subprocess", "__import__", "os.system", "exec"))
    ]
    # Assert
    assert leftovers == []


# EOF


def test_a_commented_out_dangerous_call_is_documentation(tmp_path):
    """The file that best explains why an `eval()` was removed looked
    identical to the file that still calls it. Measured on the shipped
    0.14.2: live 1 finding, commented-out ALSO 1 finding.

    `strip_js_comments` had existed since 2026-09-03 with this exact argument
    in its docstring, written for a different rule. The rule was not missing —
    its SCOPE was implicit, and it had never been carried here.
    """
    # Arrange
    from scitex_app.appmaker._validate import validate_js

    (tmp_path / "app.js").write_text('// removed in 0.9: eval("2+2");\n', encoding="utf-8")
    # Act
    reported = validate_js(tmp_path)
    # Assert
    assert not reported


def test_a_live_call_after_a_comment_is_still_reported(tmp_path):
    """The control, and the direction that matters more: a stripper that hides
    too much converts the false positive above into a false negative."""
    # Arrange
    from scitex_app.appmaker._validate import validate_js

    (tmp_path / "app.js").write_text(
        '// removed: eval("1");\neval("2+2");\n', encoding="utf-8"
    )
    # Act
    reported = validate_js(tmp_path)
    # Assert
    assert reported


def test_appvalidator_and_the_cli_share_one_pattern_list():
    """ONE DECLARATION, NOT TWO KEPT IN STEP BY HAND.

    These were nine patterns in `validator.py` and five here, and the gap was
    not a disagreement — it was a MEASURED NARROWING that landed in one
    implementation only. Four of the original nine (`__import__`, `os.system`,
    `subprocess`, `exec\\s*\\(`) are the Python forbidden list copy-pasted into
    a JS scanner, removed here after measuring the fleet and left standing
    there.

    scitex-writer hit the survivor on 2026-09-06 through `AppValidator`:
    `while ((match = re.exec(line)) !== null)` — `RegExp.prototype.exec` in a
    tokenizer loop — reported as a dangerous pattern. They raised it instead of
    renaming the variable to dodge the checker.

    Asserted as IDENTITY rather than equality on purpose: two lists that happen
    to be equal today is exactly the state this repo was in yesterday.
    """
    # Arrange
    from scitex_app.validator import DANGEROUS_JS_PATTERNS as from_validator
    # Act
    shared = from_validator is DANGEROUS_JS_PATTERNS
    # Assert
    assert shared


def test_a_regexp_exec_call_is_not_a_dangerous_pattern():
    """writer's actual line, kept as a fixture so the narrowing cannot be
    undone by someone re-adding the Python patterns."""
    # Arrange
    line = "while ((match = re.exec(line)) !== null) {"
    # Act
    hits = [p for p in DANGEROUS_JS_PATTERNS if re.search(p, line)]
    # Assert
    assert hits == []


def test_the_narrowed_list_still_catches_real_browser_hazards():
    """THE CONTROL. Without it, "no match" above is equally consistent with
    "the list is correct" and "the list is empty"."""
    # Arrange
    hazardous = "eval(userInput); document.cookie = stolen;"
    # Act
    hits = [p for p in DANGEROUS_JS_PATTERNS if re.search(p, hazardous)]
    # Assert
    assert len(hits) == 2


def test_the_pattern_list_cannot_be_mutated_by_a_caller():
    """A LIST HERE WOULD BE MUTABLE SHARED STATE.

    The object is imported by scitex_app.validator, so with a list any importer
    could `.append()` a pattern and change validation for every caller in the
    interpreter — including a test that forgets to undo it. Raised by
    scitex-writer 2026-09-06 as the one part of their answer that is a live bug
    rather than a preference.

    Asserts the TYPE rather than catching AttributeError, because a caller that
    reaches for `.append()` on a tuple is already a bug the reader should see.
    """
    # Arrange / Act
    kind = type(DANGEROUS_JS_PATTERNS)
    # Assert
    assert kind is tuple
