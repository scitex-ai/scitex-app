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
