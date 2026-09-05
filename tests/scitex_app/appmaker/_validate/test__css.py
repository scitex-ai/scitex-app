#!/usr/bin/env python3
"""Tests for scitex_app/appmaker/_validate/_css.py."""

from __future__ import annotations

import pytest

from scitex_app.appmaker._validate import validate
from scitex_app.appmaker._validate._css import (
    CssScanReport,
    css_files,
    validate_css_canonical,
)


def _app(tmp_path, css, name="a.css"):
    static = tmp_path / "static"
    static.mkdir()
    (static / name).write_text(css, encoding="utf-8")
    return tmp_path


# --------------------------------------------------------------------------
# TIER 1 — names an app can never legitimately own.
# --------------------------------------------------------------------------


def test_a_shell_owned_id_is_reported_on_any_mention(tmp_path):
    """Tier 1 is restricted to ids and shell root classes precisely because an
    app can never own one: ids are singular, so "mentions it" and "selects the
    shell's node" coincide. That coincidence is what makes a substring test
    sound HERE and unsound for shared components."""
    # Arrange
    app = _app(tmp_path, "#workspace-layout { color: red }\n")
    # Act
    report = validate_css_canonical(app)
    # Assert
    assert len(report.findings) == 1


def test_a_shell_owned_class_family_is_reported_by_prefix(tmp_path):
    """`.wft-*` is 232 occurrences of shell-rendered file-tree chrome. The
    family is entirely shell-owned, so the prefix carries the same soundness
    as the exact names."""
    # Arrange
    app = _app(tmp_path, ".wft-node { color: red }\n")
    # Act
    report = validate_css_canonical(app)
    # Assert
    assert len(report.findings) == 1


# --------------------------------------------------------------------------
# TIER 2 — names an app MAY own an instance of. Only abuse errors.
# --------------------------------------------------------------------------


def test_styling_your_own_children_inside_a_container_is_allowed(tmp_path):
    """THE CONTROL THAT DEFINES TIER 2. `#main-content` is the box the app is
    rendered INTO — 81 occurrences in hub's shell. The old AppValidator failed
    any mention of it, which is why one entry point passed this and the other
    failed it. The app styles its children freely."""
    # Arrange
    app = _app(tmp_path, "#main-content .mine { color: red }\n")
    # Act
    report = validate_css_canonical(app)
    # Assert
    assert not report.findings


def test_important_on_the_container_itself_is_reported(tmp_path):
    """The box is not the app's to force. Style your children, never the box."""
    # Arrange
    app = _app(tmp_path, "#main-content { color: red !important }\n")
    # Act
    report = validate_css_canonical(app)
    # Assert
    assert len(report.findings) == 1


def test_a_shared_component_on_the_apps_own_node_is_free(tmp_path):
    """THE CASE A MENTION-BAN GETS WRONG, and the reason hub's table
    invalidated my instrument rather than correcting my list.

    The shell renders ZERO `.h-resizer`; apps render their own. hub's own apps
    carry 42 app-level selector lines on shared-component classes today, and
    validator.py's mention-ban would fail all 42 — correct code.
    """
    # Arrange
    app = _app(tmp_path, ".h-resizer { width: 4px }\n")
    # Act
    report = validate_css_canonical(app)
    # Assert
    assert not report.findings


def test_important_on_a_shared_component_reaches_the_shells_instances(tmp_path):
    """Your own instance is yours; `!important` is not scoped to it."""
    # Arrange
    app = _app(tmp_path, ".panel-toggle-btn { color: red !important }\n")
    # Act
    report = validate_css_canonical(app)
    # Assert
    assert len(report.findings) == 1


def test_reading_a_shared_token_is_allowed(tmp_path):
    """Tokens are read-only, not untouchable. `var(--color-fg)` is the
    prescribed way to match the shell's theme."""
    # Arrange
    app = _app(tmp_path, ".mine { color: var(--color-fg) }\n")
    # Act
    report = validate_css_canonical(app)
    # Assert
    assert not report.findings


def test_redefining_a_shared_token_at_root_is_reported(tmp_path):
    """`:root` is global. An app redefining a shell token changes it for every
    other app on the page."""
    # Arrange
    app = _app(tmp_path, ":root { --color-fg: red; }\n")
    # Act
    report = validate_css_canonical(app)
    # Assert
    assert len(report.findings) == 1


def test_reacting_to_a_shell_state_class_is_allowed(tmp_path):
    """`body.zen-mode .mine` reads the state the shell set. That is the
    intended use."""
    # Arrange
    app = _app(tmp_path, "body.zen-mode .mine { color: red }\n")
    # Act
    report = validate_css_canonical(app)
    # Assert
    assert not report.findings


def test_setting_a_shell_state_class_is_reported(tmp_path):
    """React to it; do not drive it. The shell owns the state."""
    # Arrange
    app = _app(tmp_path, "body { zen-mode: 1 }\n")
    # Act
    report = validate_css_canonical(app)
    # Assert
    assert len(report.findings) == 1


# --------------------------------------------------------------------------
# THE REPORT SHAPE — the blind spot and the denominator are in the RETURN
# VALUE, not only in prose.
# --------------------------------------------------------------------------


def test_the_report_carries_its_own_blind_spot(tmp_path):
    """scitex-hub's condition for approving a ship without tier 3, and they
    said they would rather I refuse the decision than take it without this:

        "a validator that cannot see [data-pane]{} is not merely incomplete —
         it is a check that CANNOT FAIL for an entire class, and a green from
         it will be read as 'this app's CSS is properly scoped' by people with
         no reason to suspect otherwise."

    Carried in the return value so a caller cannot render a green without it.
    A docstring would have satisfied the letter and not the point.
    """
    # Arrange
    app = _app(tmp_path, ".mine { color: red }\n")
    # Act
    report = validate_css_canonical(app)
    # Assert — clean, and still saying what it never looked at.
    assert (bool(report.findings), bool(report.not_checked)) == (False, True)


def test_an_empty_scope_reads_NOT_SCANNED_rather_than_clean(tmp_path):
    """0 findings across 0 files is not a clean app. The denominator is in the
    report because a caller computing it with their own walk can pair a large
    one with our clean numerator — two instruments pointed at different trees.
    That cost a peer a whole measurement on 2026-09-05: 1,116 files reported
    beside 0 findings, having in fact read nothing."""
    # Arrange
    (tmp_path / "static").mkdir()
    # Act
    report = validate_css_canonical(tmp_path)
    # Assert
    assert (report.files_scanned, report.scanned_nothing) == (0, True)


def test_a_report_cannot_claim_findings_against_zero_files():
    """The validator on the shape, so a malformed answer fails where it is
    built rather than three layers downstream."""
    # Arrange
    bad = {"findings": ("x",), "files_scanned": 0}
    # Act
    raised = pytest.raises(ValueError)
    # Assert
    with raised:
        CssScanReport(**bad)


# --------------------------------------------------------------------------
# THE DENOMINATOR ITSELF
# --------------------------------------------------------------------------


def test_css_files_skips_dependencies_inside_the_app(tmp_path):
    """The app's own stylesheets, not its dependencies'."""
    # Arrange
    (tmp_path / "static").mkdir()
    (tmp_path / "static" / "a.css").write_text("a{}", encoding="utf-8")
    dep = tmp_path / "node_modules" / "pkg"
    dep.mkdir(parents=True)
    (dep / "b.css").write_text("b{}", encoding="utf-8")
    # Act
    names = [p.name for p in css_files(tmp_path)]
    # Assert
    assert names == ["a.css"]


def test_css_files_scans_a_root_that_sits_inside_a_skipped_directory(tmp_path):
    """Skip names match RELATIVE to the scan root. A caller whose hooks require
    work to happen in `.worktrees/` — scitex-hub's do — must not have their
    files deleted by an ancestor they did not choose. That defect (0.14.4) cost
    hub a 1,116-file report that had read nothing."""
    # Arrange
    root = tmp_path / "repo" / ".worktrees" / "topic"
    (root / "static").mkdir(parents=True)
    (root / "static" / "a.css").write_text("a{}", encoding="utf-8")
    # Act
    names = [p.name for p in css_files(root)]
    # Assert
    assert names == ["a.css"]


def test_css_files_refuses_a_path_that_is_not_there(tmp_path):
    """"No findings" from a path that does not exist is indistinguishable from
    a clean tree."""
    # Arrange
    missing = tmp_path / "nope"
    # Act
    raised = pytest.raises(FileNotFoundError)
    # Assert
    with raised:
        css_files(missing)


def test_a_commented_out_violation_is_documentation(tmp_path):
    """Inherited from `strip_css_comments`, and asserted here because the
    canonical is a new caller of it — a rule quoted inside `/* ... */` is not a
    declaration the browser applies. This is the shape that failed every pull
    request in a peer repository."""
    # Arrange
    app = _app(tmp_path, "/* old: #workspace-layout { color: red } */\n.mine{}\n")
    # Act
    report = validate_css_canonical(app)
    # Assert
    assert not report.findings


# --------------------------------------------------------------------------
# THE TWO ANSWERS THAT CAME FROM MEASUREMENT, NOT FROM ME
#
# Both of these I had wrong, and both were settled by scitex-hub counting
# their own tree (ref `develop@4ec9c4066`) rather than by either of us
# reasoning about what an app "should" do.
# --------------------------------------------------------------------------


def test_a_shared_resizer_on_the_apps_own_node_is_tier_2_not_tier_1(tmp_path):
    """`.panel-resizer` was TIER 1 in my draft — a mention-ban — and that was
    the single most expensive error in this rule, because it fails CORRECT
    code across nine applications.

        "apps render it 41 times across nine apps against the shell's 6 ...
         your current tier 1 for `.panel-resizer` WOULD FAIL CORRECT CODE in
         nine apps. My 09-04 one-line summary that grouped it with
         `.stx-shell-*` as no-touch is the error; the measured table beside it
         was right and I compressed it wrongly when I wrote the summary.
         Take the table."        — scitex-hub, from a fresh count

    Note which artefact won: the TABLE, not the SUMMARY of the table. The
    summary was the compression of a measurement, and the compression is where
    the fact was lost.
    """
    # Arrange
    app = _app(tmp_path, ".panel-resizer { width: 4px }\n")
    # Act
    report = validate_css_canonical(app)
    # Assert
    assert not report.findings


def test_important_on_a_shared_resizer_still_reaches_the_shells_six(tmp_path):
    """Tier 2 is not permission; it is the narrower ban. The shell renders six
    `.panel-resizer` nodes, and `!important` is not scoped to the app's 41."""
    # Arrange
    app = _app(tmp_path, ".panel-resizer { width: 4px !important }\n")
    # Act
    report = validate_css_canonical(app)
    # Assert
    assert len(report.findings) == 1


def test_important_on_a_bare_footer_element_is_reported(tmp_path):
    """hub chose (b) over the semantically-correct (a), FOR A STATED REASON:

        "SEMANTICALLY (a) is right ... BUT (a) IS NOT IMPLEMENTABLE BY
         SUBSTRING. So: (b) now."

    (a) — "does this rule reach the shell's footer?" — needs a parser to
    answer. A rule this instrument cannot evaluate is not a stricter rule, it
    is a rule that silently evaluates to something else. (b) is the part a
    substring test can actually decide, and the remainder is DECLARED in
    `not_checked` rather than implied to be covered.
    """
    # Arrange
    app = _app(tmp_path, "footer { padding: 0 !important }\n")
    # Act
    report = validate_css_canonical(app)
    # Assert
    assert len(report.findings) == 1


def test_hiding_a_bare_footer_element_is_reported(tmp_path):
    """The one unconditional ban that survives from the pre-canonical rule:
    `display:none` on an unscoped `footer` removes the shell's footer for the
    whole workspace, not just for the app's own pane."""
    # Arrange
    app = _app(tmp_path, "footer { display: none }\n")
    # Act
    report = validate_css_canonical(app)
    # Assert
    assert len(report.findings) == 1


def test_a_bare_footer_rule_with_ordinary_declarations_is_the_declared_gap(tmp_path):
    """The residual that (a) leaves behind, asserted so it is a KNOWN zero
    rather than an assumed one. This app's `footer{}` may well reach the
    shell's footer — the instrument cannot tell, `not_checked` says so, and
    this test exists to make the silence deliberate and visible in the suite.
    """
    # Arrange
    app = _app(tmp_path, "footer { padding: 0 }\n")
    # Act
    report = validate_css_canonical(app)
    # Assert
    assert not report.findings


@pytest.mark.parametrize(
    "css",
    [
        ".myapp footer { padding: 0 !important }\n",
        ".myapp footer { display: none }\n",
        ".status-footer { color: red !important }\n",
        ".site-footer { color: red !important }\n",
        ":root { --footer-height: 40px }\n",
    ],
    ids=["scoped-important", "scoped-hidden", "status-footer", "site-footer", "token"],
)
def test_a_footer_that_is_not_the_shells_footer_is_not_a_finding(tmp_path, css):
    """THE FALSE POSITIVES, which are the half of a detector only a CORRECT
    tree can show you. The first two are an app scoping a footer inside its
    own subtree — exactly what the rule exists to permit — and the last three
    are names that merely CONTAIN the word.

    `.status-footer` / `.site-footer` / `--footer-height` are hub's controls,
    named by them when they answered; the two scoped forms are mine, found by
    running the narrowed rule against code that ought to pass. Both halves
    belong here: a substring detector is only as good as the cases it declines
    to fire on.
    """
    # Arrange
    app = _app(tmp_path, css)
    # Act
    report = validate_css_canonical(app)
    # Assert
    assert not report.findings


def test_the_shells_own_footer_id_stays_tier_1(tmp_path):
    """The element-name softening does not reach the ID. `#site-footer` is
    singular and the shell's, so mention and selection coincide — the
    condition tier 1 requires."""
    # Arrange
    app = _app(tmp_path, "#site-footer { padding: 0 }\n")
    # Act
    report = validate_css_canonical(app)
    # Assert
    assert len(report.findings) == 1


# --------------------------------------------------------------------------
# THE ARMING SWITCH ITSELF
# --------------------------------------------------------------------------


def test_the_canonical_rule_is_off_until_someone_turns_it_on(tmp_path):
    """UNARMED, asserted WITH ITS OWN POSITIVE CONTROL in the same expression.

    The control is not decoration. On 2026-09-05 an "is it still off?" test in
    this repository passed for a reason that had nothing to do with the flag —
    the rule was not reachable at all — and it would have gone on passing after
    arming. A test that asserts an absence proves nothing unless the same test
    shows the presence it is the absence OF, and the two halves must be
    inseparable or someone will delete the inconvenient one.
    """
    # Arrange — a violation the canonical rule reports and `validate_css` does
    # not, so what moves between the two halves can only be the new rule.
    app = _app(tmp_path, ".panel-toggle-btn { color: red !important }\n")
    # Act
    off = [e for e in validate(app) if "panel-toggle-btn" in e]
    on = [e for e in validate(app, check_css_canonical=True) if "panel-toggle-btn" in e]
    # Assert — silent by default, and demonstrably able to speak.
    assert (off, bool(on)) == ([], True)


def test_the_flagged_path_and_the_direct_call_agree(tmp_path):
    """`validate()` returns a flat list and drops the denominator, so these two
    surfaces cannot be checked against each other by shape. Check them on
    CONTENT instead: whatever the report carries as findings is exactly what
    the gate raises. If they ever diverge, the number a person reads and the
    number that fails their build are different numbers."""
    # Arrange
    app = _app(tmp_path, "#workspace-layout { color: red }\n")
    # Act
    direct = validate_css_canonical(app).findings
    gated = [e for e in validate(app, check_css_canonical=True) if "workspace-layout" in e]
    # Assert
    assert list(direct) == gated
