"""Tests for scitex_app/appmaker/_validate/_prefix.py."""

from __future__ import annotations

import json

from scitex_app.appmaker._validate import (
    validate,
    validate_prefix_safety,
)


# broken", "the platform exemption is gone" and "embedded apps are skipped" are
# different defects with different fixes.

from scitex_app.appmaker._validate import validate_prefix_safety


def _app_with_js(tmp_path, source, name="app.js"):
    (tmp_path / name).write_text(source, encoding="utf-8")
    return validate_prefix_safety(tmp_path)


def test_a_root_absolute_request_url_is_reported(tmp_path):
    # Arrange — ignores the mount outright; the loud failure.
    source = 'fetch("/api/search");'
    # Act
    found = _app_with_js(tmp_path, source)
    # Assert
    assert len(found) == 1


def test_a_relative_request_url_is_reported_as_inferred_base(tmp_path):
    # Arrange — the QUIET failure scitex-scholar measured: resolves against the
    # document URL, so it works at "/app/" and 404s at "/app".
    source = 'fetch("api/search");'
    # Act
    found = _app_with_js(tmp_path, source)
    # Assert
    assert "inferred-base" in found[0]


def test_a_platform_route_is_not_reported(tmp_path):
    # Arrange — hub owns this route, it lives at the server root, and prefixing
    # it BREAKS it. Flagging it would make the rule advise a regression.
    source = 'fetch("/platform/api/context/");'
    # Act
    found = _app_with_js(tmp_path, source)
    # Assert
    assert found == []


def test_an_absolute_external_url_is_not_reported(tmp_path):
    # Arrange — a different origin entirely; no mount applies.
    source = 'fetch("https://example.com/api/search");'
    # Act
    found = _app_with_js(tmp_path, source)
    # Assert
    assert found == []


def test_a_url_bound_to_a_variable_before_fetching_is_reported(tmp_path):
    # Arrange — the shape that defeated the first draft. Calibrating against
    # scitex-scholar's shipped wheel found 1 of 3 known sites because the other
    # two bind the literal first and fetch it on the next line.
    source = 'const url = `/api/graph/network?doi=${doi}`;\nconst r = await fetch(url);'
    # Act
    found = _app_with_js(tmp_path, source)
    # Assert
    assert len(found) == 1


def test_an_embedded_package_is_still_scanned(tmp_path):
    # Arrange — the wrong-population arm. validate() skips template/CSS checks
    # for embedded packages, and EVERY app carrying this defect is an embedded
    # `_django` package. A prefix rule inheriting that skip would pass forever
    # on exactly the apps it exists to measure.
    (tmp_path / "manifest.json").write_text('{"embedded_package": true}', encoding="utf-8")
    (tmp_path / "bundle.js").write_text('fetch("/api/search");', encoding="utf-8")
    # Act
    found = validate_prefix_safety(tmp_path)
    # Assert
    assert len(found) == 1


def test_build_output_directories_are_scanned_not_skipped(tmp_path):
    # Arrange — the committed built bundle is what SHIPS, and it can disagree
    # with the TS source (scitex-writer's offending anchor lives in one).
    # validator.py's SKIP_DIRS excludes "assets"/"dist"; this rule must not.
    assets = tmp_path / "static" / "writer" / "assets"
    assets.mkdir(parents=True)
    (assets / "index.js").write_text('fetch("/api/pdf?download=1");', encoding="utf-8")
    # Act
    found = validate_prefix_safety(tmp_path)
    # Assert
    assert len(found) == 1


def test_validate_does_not_report_prefix_findings_by_default(tmp_path):
    # Arrange — UNARMED is the shipped state. If this test ever fails, the rule
    # has silently started failing three peer repos' builds for work two of them
    # have not begun. This is the arm that protects them, not the code.
    from scitex_app.appmaker._validate import validate as _validate

    (tmp_path / "bundle.js").write_text('fetch("/api/search");', encoding="utf-8")
    # Act
    reported = _validate(tmp_path)
    # Assert
    assert not [e for e in reported if "does not resolve under an app mount" in e]


def test_validate_reports_prefix_findings_when_explicitly_armed(tmp_path):
    # Arrange — the other arm. Without it, "unarmed" above would also pass if
    # the check were wired up to nothing at all, which is the failure mode the
    # default-off flag most resembles.
    from scitex_app.appmaker._validate import validate as _validate

    (tmp_path / "bundle.js").write_text('fetch("/api/search");', encoding="utf-8")
    # Act
    reported = _validate(tmp_path, check_prefix_safety=True)
    # Assert
    assert [e for e in reported if "does not resolve under an app mount" in e]


# ─── template/CSS skip is keyed on frontend_type, not on the directory name ──
# Four arms, one assertion each — this is a truth table, and a compound assert
# would report "the table is wrong" instead of "this row is wrong".


# ─── variable-prefixed URLs are a THIRD value, not a violation ──────────────
# 0.9.0 flagged `${STX_MOUNT}/api/x` — the exact code its own remediation text
# prescribes — because it collapsed "variable-prefixed" into "inferred-base".
# Reported by scitex-scholar against their CORRECTED tree.

def test_the_prescribed_mount_prefix_form_is_not_flagged(tmp_path):
    # Arrange — this IS the fix. Flagging it tells an app to undo correct work.
    source = "const url = `${STX_MOUNT}/api/search?${params}`;"
    # Act
    found = _app_with_js(tmp_path, source)
    # Assert
    assert found == []


def test_the_concatenated_mount_prefix_form_is_not_flagged(tmp_path):
    # Arrange — the other documented spelling, base + "/path". Both forms are
    # correct and both must pass; only the template one regressed in 0.9.0.
    source = 'fetch(STX_MOUNT + "/api/graph/health");'
    # Act
    found = _app_with_js(tmp_path, source)
    # Assert
    assert found == []


def test_a_url_prefixed_by_an_unknown_variable_is_not_reported(tmp_path):
    # Arrange — UNKNOWN, deliberately not collapsed into "violation". Whether
    # `someBase` holds the mount needs its value, which a scanner lacks.
    source = "const url = `${someBase}/api/search`;"
    # Act
    found = _app_with_js(tmp_path, source)
    # Assert
    assert found == []


def test_a_genuinely_root_absolute_url_is_still_flagged(tmp_path):
    # Arrange — the arm that stops this fix becoming a blanket amnesty. Without
    # it, returning None for everything would satisfy all three tests above.
    source = 'fetch("/api/search");'
    # Act
    found = _app_with_js(tmp_path, source)
    # Assert
    assert len(found) == 1


def test_a_genuinely_relative_url_is_still_flagged(tmp_path):
    # Arrange — same guard for the inferred-base class, which is the one the
    # fix narrowed. If narrowing went too far this is what catches it.
    source = 'fetch("api/search");'
    # Act
    found = _app_with_js(tmp_path, source)
    # Assert
    assert len(found) == 1


# EOF


# ─── false positives measured on real trees, 2026-09-03 ─────────────────────
# Both were found by running the scan against scitex-writer's shipped package,
# not by inspection. A CORRECT tree is the only place a false positive is
# visible, and these two were invisible in every fixture I had written.


def test_an_xhr_method_is_not_reported_as_a_url(tmp_path):
    """`xhr.open("GET", url)` — the FIRST literal is the method, not the URL.

    Measured in writer's bundle as: inferred-base request URL 'GET'. 'GET'
    cannot be prefixed, so the remediation text told the author to join a verb
    to the mount.
    """
    # Arrange
    source = 'const x = new XMLHttpRequest; x.open("GET", u, true);'
    # Act
    found = _app_with_js(tmp_path, source)
    # Assert
    assert not [e for e in found if "'GET'" in e]


def test_an_xhr_url_argument_is_still_reported(tmp_path):
    """The other arm: skipping the method must not skip the URL beside it."""
    # Arrange
    source = 'const x = new XMLHttpRequest; x.open("GET", "api/search", true);'
    # Act
    found = _app_with_js(tmp_path, source)
    # Assert
    assert [e for e in found if "api/search" in e]


def test_a_bundler_config_is_not_scanned(tmp_path):
    """Build config runs at BUILD time and reaches no browser.

    Measured in writer as vite.config.ts:5 — `new URL(".", import.meta.url)`,
    Node's __dirname idiom. The rule's own docstring already excluded build
    config; the code did not.
    """
    # Arrange
    source = 'const __dirname = fileURLToPath(new URL(".", import.meta.url));'
    # Act
    found = _app_with_js(tmp_path, source, "vite.config.ts")
    # Assert
    assert found == []


def test_an_ordinary_source_file_is_still_scanned(tmp_path):
    """Control: the skip must be keyed on the config name, not on the shape."""
    # Arrange
    source = 'const __dirname = fileURLToPath(new URL(".", import.meta.url));'
    # Act
    found = _app_with_js(tmp_path, source, "app.ts")
    # Assert
    assert len(found) == 1


# EOF


# ─── comments are not code, and URLs are not comments ───────────────────────
#
# Third instance in one night of a detector inverting on documentation. The
# controls below run in BOTH directions, because "stripped comments correctly"
# and "blunted the scanner" produce an identical green suite otherwise.


def test_a_commented_out_request_is_not_reported(tmp_path):
    """MEASURED DEFECT, shipping since 0.9.0.

    A file whose only match sat in a comment produced a finding telling the
    author to fix a call they had already removed.
    """
    # Arrange
    source = '// legacy, replaced in 0.9: fetch("/api/old");'
    # Act
    found = _app_with_js(tmp_path, source)
    # Assert
    assert found == []


def test_a_block_commented_request_is_not_reported(tmp_path):
    # Arrange
    source = '/* fetch("/api/old"); */'
    # Act
    found = _app_with_js(tmp_path, source)
    # Assert
    assert found == []


def test_a_real_request_beside_a_stale_comment_is_still_reported(tmp_path):
    """The arm that separates "stripped correctly" from "stripped everything"."""
    # Arrange
    source = '// old: fetch("/api/v1");\nfetch("/api/v2");'
    # Act
    found = _app_with_js(tmp_path, source)
    # Assert
    assert len(found) == 1


def test_a_trailing_comment_does_not_hide_the_code_before_it(tmp_path):
    # Arrange
    source = 'fetch("/api/x");  // TODO: use the mount prefix'
    # Act
    found = _app_with_js(tmp_path, source)
    # Assert
    assert len(found) == 1


def test_a_double_slash_inside_a_url_is_not_treated_as_a_comment(tmp_path):
    """THE FALSE-NEGATIVE RISK, and the reason this is not a regex.

    `//` opens every absolute URL. A naive `//.*$` would truncate the string,
    the scanner would misread what remains, and a finding would vanish with
    nothing saying why — trading a false positive for a false negative, which
    is the worse direction.
    """
    # Arrange — root-absolute, and containing `//` in a nested literal
    source = 'const u = "https://cdn.example.com/x"; fetch("/api/y");'
    # Act
    found = _app_with_js(tmp_path, source)
    # Assert
    assert len(found) == 1


def test_line_numbers_survive_comment_stripping(tmp_path):
    """Comments become blanks, not deletions, so findings still point at the
    real line in the file on disk."""
    # Arrange
    source = '// a\n// b\nfetch("/api/z");'
    # Act
    found = _app_with_js(tmp_path, source)
    # Assert
    assert ":3:" in found[0]


# EOF
