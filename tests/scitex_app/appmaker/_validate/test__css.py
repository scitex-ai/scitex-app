#!/usr/bin/env python3
"""Tests for scitex_app/appmaker/_validate/_css.py."""

from __future__ import annotations

import functools

import pytest

from scitex_app.appmaker._validate import validate
from scitex_app.appmaker._validate._css import (
    CssScanReport,
    NotAnAppDirectoryError,
    css_files,
    validate_css_canonical,
)


def _app(tmp_path, css, name="a.css"):
    """A fixture that is actually an APP — manifest and all.

    It did not write a manifest until 0.20.0, which meant every test in this
    file ran against a directory the rule considers out of scope. The suite
    was green and the in-scope path was the one nobody exercised.
    """
    (tmp_path / "manifest.json").write_text("{}", encoding="utf-8")
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
    (tmp_path / "manifest.json").write_text("{}", encoding="utf-8")
    (tmp_path / "static").mkdir()
    # Act
    report = validate_css_canonical(tmp_path)
    # Assert
    assert (report.files_scanned, report.scanned_nothing) == (0, True)


# --------------------------------------------------------------------------
# THE POPULATION — refusing a root this rule is not about.
# --------------------------------------------------------------------------


def test_a_root_without_a_manifest_is_refused_not_counted(tmp_path):
    """A repo root pools shell and infrastructure CSS this rule never covered,
    so a count taken there is real and not about app code.

    This used to return the count beside a `root_looks_like_an_app: False`
    caveat. On 2026-09-06 scitex-hub ran it on their repo root, got 604 files
    / 346 findings against a right answer of 15, and carried the 346 forward
    as a 12.8x regression in this detector — with the caveat present, a
    >=300-file floor asserted, and a positive control firing. Both controls
    passed: one asked whether the walk found files, the other whether the rule
    could fire, and neither could ask whether the tree was in scope.
    """
    # Arrange
    static = tmp_path / "static"
    static.mkdir()
    (static / "a.css").write_text("#workspace-layout { color: red }\n", encoding="utf-8")
    # Act
    raised = pytest.raises(NotAnAppDirectoryError)
    # Assert
    with raised:
        validate_css_canonical(tmp_path)


def _refusal_message(tmp_path):
    """The refusal's text, for tests that assert on what it tells the caller."""
    (tmp_path / "static").mkdir()
    with pytest.raises(NotAnAppDirectoryError) as excinfo:
        validate_css_canonical(tmp_path)
    return str(excinfo.value)


def _legacy_manifest_refusal(tmp_path):
    """The refusal for a directory carrying a manifest in another format."""
    (tmp_path / "static").mkdir()
    (tmp_path / "manifest.yaml").write_text("name: notebook\n", encoding="utf-8")
    with pytest.raises(NotAnAppDirectoryError) as excinfo:
        validate_css_canonical(tmp_path)
    return str(excinfo.value)


def test_a_manifest_in_another_format_is_named_in_the_refusal(tmp_path):
    """scitex-hub's apps/legacy/notebook_app carries a manifest.YAML and ships
    CSS, so "not an app directory" is simply false about it. Naming what WAS
    found is what separates the two causes for the caller."""
    # Arrange
    message = _legacy_manifest_refusal(tmp_path)
    # Act
    names_what_it_found = "manifest.yaml" in message
    # Assert
    assert names_what_it_found


def test_a_legacy_manifest_is_not_called_the_wrong_directory(tmp_path):
    """The two causes need different fixes and the old message gave only the
    first. Telling this caller to "loop over your app dirs" sends them to do
    the thing they already did — the directory WAS in their loop, and this
    call is why it got skipped."""
    # Arrange
    message = _legacy_manifest_refusal(tmp_path)
    # Act
    misdirects = "loop over your app dirs" in message
    # Assert
    assert not misdirects


def test_a_bare_directory_still_says_nothing_manifest_shaped_was_found(tmp_path):
    """THE CONTROL for the pair above. Without it, "names what it found" is
    equally consistent with a message that always mentions a legacy manifest,
    and "does not misdirect" with one that never gives directions at all."""
    # Arrange
    message = _refusal_message(tmp_path)
    # Act
    says_nothing_found = "nothing else manifest-shaped" in message
    # Assert
    assert says_nothing_found


def test_the_refusal_names_the_missing_manifest(tmp_path):
    """An error that only states what broke is half-written — name the file
    whose absence decided it, so the caller can check it themselves."""
    # Arrange
    message = _refusal_message(tmp_path)
    # Act
    names_it = "manifest.json" in message
    # Assert
    assert names_it


def test_the_refusal_says_to_call_it_per_app(tmp_path):
    """The caller who hits this is pointing at a repo root, and the next move
    — loop the app dirs — is not guessable from 'not an app directory'."""
    # Arrange
    message = _refusal_message(tmp_path)
    # Act
    advises_next_step = "per app" in message
    # Assert
    assert advises_next_step


def test_css_files_still_walks_a_non_app_tree(tmp_path):
    """The refusal belongs to the RULE, not to the walk. Counting stylesheets
    in a tree is a question with an honest answer, and a caller sweeping app
    dirs needs it — so gating both would remove the escape hatch the refusal
    tells them to use."""
    # Arrange
    static = tmp_path / "static"
    static.mkdir()
    (static / "a.css").write_text("body { color: red }\n", encoding="utf-8")
    # Act
    found = css_files(tmp_path)
    # Assert
    assert len(found) == 1


def test_the_report_carries_no_in_scope_flag(tmp_path):
    """`root_looks_like_an_app` is gone rather than pinned True. A field that
    cannot vary is not information, and leaving it would advertise a state the
    refusal makes unreachable — the menu listing a dish the kitchen stopped
    serving."""
    # Arrange
    app = _app(tmp_path, "body { color: red }\n")
    # Act
    report = validate_css_canonical(app)
    # Assert
    assert not hasattr(report, "root_looks_like_an_app")


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


# --------------------------------------------------------------------------
# FUNCTIONAL PSEUDO-CLASSES — a comma inside `:is()` is not a selector list
#
# scitex-hub reported these against 0.14.4. Their concrete example already
# passed the canonical; the HYPOTHETICAL they offered beside it did not. Both
# are here, because which of the two fired was not predictable from reading
# the regex — it turned on whether `(` happens to be a boundary character.
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "css",
    [
        "body > :first-child:not(header):not(main):not(footer) { display: none !important }\n",
        ":is(header, footer) .x { color: red !important }\n",
        ":where(footer) .x { color: red !important }\n",
        ".x:has(footer) { color: red !important }\n",
        ":has(:not(footer)) .x { color: red !important }\n",
    ],
    ids=["not", "is-list", "where", "has", "nested"],
)
def test_footer_inside_a_functional_pseudo_class_is_not_a_footer_rule(tmp_path, css):
    """`:is()` / `:not()` / `:where()` / `:has()` take selector LISTS, so their
    commas are internal and the leftmost test reads an argument as a second
    selector. `:not(footer)` is the sharpest of these: the rule EXCLUDES a
    footer and the detector called that targeting one.

    hub's real file — `body > :first-child:not(header):not(main):not(footer)`
    in `public_app/css/pricing.css` — already passed, because `(` is not one of
    the boundary characters. Their generalisation was right anyway and their
    example was not the case that proved it.
    """
    # Arrange
    app = _app(tmp_path, css)
    # Act
    report = validate_css_canonical(app)
    # Assert
    assert not report.findings


def test_hiding_a_footer_named_only_inside_a_pseudo_class_is_not_reported(tmp_path):
    """The `display:none` half had the SAME hole and could not be fixed in the
    same place: it ran once per file over the whole content, so it had no
    selector to strip. It now reads the rule block's own selector, which is why
    the two footer checks share one definition of "the subject is a bare
    footer" instead of two that drift apart."""
    # Arrange
    app = _app(tmp_path, ":is(header, footer) .x { display: none }\n")
    # Act
    report = validate_css_canonical(app)
    # Assert
    assert not report.findings


def test_a_body_class_scoped_footer_rule_is_declared_not_silently_allowed(tmp_path):
    """THE ONE HUB FOUND THAT I CANNOT FIX, asserted as a KNOWN zero.

        body.scholar-page footer { display: none }

    Not leftmost, so this rule passes it — and unlike `.myapp footer` it DOES
    reach the shell's footer, because the shell's <footer> is inside <body>.
    The two selectors differ only in whether the scoping element contains the
    shell's node, which is a DOM fact and not a string fact: tier 3 wearing
    another hat.

    And it must not simply be banned. hub does this deliberately and documents
    it shell-side (`workspace_app/context_processors.py:179` — "body
    .workspace-page hides .site-footer, so the page's own legal…"), so a ban
    would fail their design rather than catch a defect. What the shell permits
    is the shell's to state; the validator's job here is to say it did not
    look, which `not_checked` now does.
    """
    # Arrange
    app = _app(tmp_path, "body.scholar-page footer { display: none !important }\n")
    # Act
    report = validate_css_canonical(app)
    # Assert — silent, and the silence is declared.
    hidden = "BODY-CLASS-scoped" in " ".join(report.not_checked)
    assert (bool(report.findings), hidden) == (False, True)


# --------------------------------------------------------------------------
# EXCLUDED vs MATCHED — the distinction #144 did not make
#
# scitex-hub ran 0.15.0 against their own tree (develop@4ec9c4066, 428 files,
# 29 findings) and the first real-population run found this in ten minutes.
# Their `:not()` half was right; their `:is()` half was not, and taking their
# suggested list wholesale would have turned a false positive into a false
# negative.
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "css",
    [
        'div[class*="editor"]:not(.panel-resizer) { overflow: visible !important }\n',
        ":not(#workspace-layout) { color: red }\n",
        ":not(.wft-node) { color: red }\n",
        ":not(#main-content) { color: red !important }\n",
        ".x:has(.panel-resizer) { color: red !important }\n",
        ":has(:not(.panel-resizer)) { color: red !important }\n",
    ],
    ids=["hub-real", "tier1-id", "tier1-prefix", "tier2-container", "has", "nested"],
)
def test_a_name_that_is_excluded_or_conditional_is_not_a_target(tmp_path, css):
    """`:not(X)` EXCLUDES X; `:has(X)` makes X a condition on an ancestor. In
    neither is X styled, so a protected name appearing there is not a target.

    The first case is hub's, from `writer_app/css/editor/editor.css:177` — a
    rule about editors that explicitly excludes resizers, reported as styling
    one. The same file's OTHER finding is genuine (`.panel-resizer::before {
    z-index: 100 !important }`), so the file is 1 real + 1 false rather than
    two of either, which is the whole reason a finding count is not a defect
    count.
    """
    # Arrange
    app = _app(tmp_path, css)
    # Act
    report = validate_css_canonical(app)
    # Assert
    assert not report.findings


def test_a_name_inside_a_matching_pseudo_class_IS_still_a_target(tmp_path):
    """THE HALF OF HUB'S SUGGESTION I DID NOT TAKE, and the reason the module
    carries two strippers instead of one.

    hub proposed `:is(.foo, .h-resizer)` as a must-NOT-fire case beside their
    `:not()` finding. But `:is()` is a MATCHING pseudo-class: this rule applies
    `!important` to every `.h-resizer` on the page, including the shell's.
    Blanking `:is()` for the membership question — the obvious way to reuse
    the stripper #144 already had — would have converted their false positive
    into a false negative, silently.

    The two questions are genuinely different:

        membership  is this protected name a TARGET of this rule?
        leftmost    does this selector list BEGIN with a bare `footer`?

    and only the second one wants every internal comma gone.
    """
    # Arrange
    app = _app(tmp_path, ":is(.foo, .h-resizer) { color: red !important }\n")
    # Act
    report = validate_css_canonical(app)
    # Assert
    assert len(report.findings) == 1


def test_a_footer_subject_under_a_leading_is_is_the_declared_residual(tmp_path):
    """`:is(header, footer) { …!important }` DOES reach the shell's footer and
    this rule does not report it — asserted as a KNOWN zero.

    The leftmost test drops every comma inside `:is()`, because keeping them
    would fire on the far commoner `:is(header, footer) .x { … }`, where the
    footer is an ANCESTOR and the subject is `.x`. Telling those apart means
    knowing which compound is the subject, which is the parser again.

    Both shapes are asserted here, in the same test, so the trade is visible:
    the miss below is the price of the pass above it, not an oversight.
    """
    # Arrange
    (tmp_path / "a").mkdir()
    (tmp_path / "b").mkdir()
    subject = _app(tmp_path / "a", ":is(header, footer) { padding: 0 !important }\n")
    ancestor = _app(tmp_path / "b", ":is(header, footer) .x { color: red !important }\n")
    # Act
    missed = validate_css_canonical(subject).findings
    correct = validate_css_canonical(ancestor).findings
    # Assert — the ancestor form is right, the subject form is the declared gap.
    assert (bool(missed), bool(correct)) == (False, False)


def test_the_subject_residual_is_named_in_the_report(tmp_path):
    """A gap the caller cannot see is a check that cannot fail. This one is in
    `not_checked` beside tier 3 and the body-class footer, so a green from this
    rule carries all three."""
    # Arrange
    app = _app(tmp_path, ".mine { color: red }\n")
    # Act
    report = validate_css_canonical(app)
    # Assert
    assert "SUBJECT" in " ".join(report.not_checked)


# --------------------------------------------------------------------------
# A LONGER NAME IS A DIFFERENT NAME — and one rule is one finding
#
# Both found inside scitex-hub's second step-2 run (0.15.1, 428 files), and
# both attributed by them to their own code rather than to this rule. The
# report said "writer minted a class inside the shell's BEM namespace", which
# is true and worth raising with writer — but it is not what the finding said.
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "css",
    [
        ".stx-shell-sidebar__header-compact { color: red !important }\n",
        ".panel-resizer-custom { width: 4px !important }\n",
        ".h-resizer-x { color: red !important }\n",
        "#main-content-2 { color: red !important }\n",
        "#workspace-layout-old { color: red }\n",
        ".workspace-pane-mine { color: red }\n",
    ],
    ids=["hub-real", "resizer", "h-resizer", "container", "tier1-id", "tier1-class"],
)
def test_a_name_that_merely_extends_a_protected_one_is_a_different_name(tmp_path, css):
    """`.stx-shell-sidebar__header` and `.stx-shell-sidebar__header-compact` are
    unrelated selectors; a rule on the second cannot touch the first. `in` said
    otherwise, and the finding it produced NAMED A CLASS THE SELECTOR DOES NOT
    CONTAIN.

    `-` is a legal class-name character, so the guard is `(?![\\w-])` — the same
    boundary the footer rule already carried and this one did not. The leading
    side needs none: `.foo` cannot occur inside `.my-foo`, because the `.` is
    part of the token.
    """
    # Arrange
    app = _app(tmp_path, css)
    # Act
    report = validate_css_canonical(app)
    # Assert
    assert not report.findings


@pytest.mark.parametrize(
    "css",
    [
        ".stx-shell-sidebar__header:hover { color: red !important }\n",
        ".stx-shell-sidebar__header::before { color: red !important }\n",
        ".stx-shell-sidebar__header.mine { color: red !important }\n",
        ".stx-shell-sidebar__header .x { color: red !important }\n",
        ".mine, .panel-resizer { color: red !important }\n",
        "#main-content > .x { color: red !important }\n",
    ],
    ids=["pseudo-class", "pseudo-elem", "compound", "descendant", "list", "child"],
)
def test_a_separator_that_is_not_a_name_character_still_selects_it(tmp_path, css):
    """THE OTHER DIRECTION, which is the half a boundary fix usually breaks.
    `:`, `.`, ` `, `,` and `>` all end a class name, so every one of these
    really does select the protected node and must still report — exactly once.
    """
    # Arrange
    app = _app(tmp_path, css)
    # Act
    report = validate_css_canonical(app)
    # Assert
    assert len(report.findings) == 1


@pytest.mark.parametrize(
    "css", [".wft-node { color: red }\n", ".editor-split-pane { color: red }\n"],
    ids=["wft", "editor-split"],
)
def test_a_prefix_family_is_still_matched_by_prefix(tmp_path, css):
    """`SHELL_INSTANCE_PREFIXES` are prefix FAMILIES on purpose — `.wft-` is
    meant to match `.wft-node`, and the boundary rule above must not reach them.
    That distinction is precisely what `in` erased: it made every exact name
    behave like a prefix."""
    # Arrange
    app = _app(tmp_path, css)
    # Act
    report = validate_css_canonical(app)
    # Assert
    assert len(report.findings) == 1


def test_one_rule_produces_one_finding_even_when_two_names_nest(tmp_path):
    """`.stx-shell-sidebar` and `.stx-shell-sidebar__header` are BOTH in
    `SHARED_COMPONENT_CLASSES` and both substring-matched the same selector, so
    ONE declaration produced TWO findings under two names.

    That inflates any count taken from this rule — hub's eight `__header-compact`
    findings were four rules — and a count that inflates is worse than one that
    is merely incomplete, because it reads as MORE evidence than exists. The
    most specific match is the one that describes the selector.
    """
    # Arrange
    app = _app(tmp_path, ".stx-shell-sidebar__header { color: red !important }\n")
    # Act
    report = validate_css_canonical(app)
    # Assert
    assert len(report.findings) == 1


def test_two_genuinely_different_names_still_report_twice(tmp_path):
    """The de-duplication drops a name CONTAINED IN another matched name, not
    any second finding. `.panel-resizer` and `.h-resizer` are distinct targets
    and neither contains the other, so both are reported — otherwise the fix
    for an inflated count would quietly become an undercount."""
    # Arrange
    app = _app(tmp_path, ".panel-resizer, .h-resizer { color: red !important }\n")
    # Act
    report = validate_css_canonical(app)
    # Assert
    assert len(report.findings) == 2


# --------------------------------------------------------------------------
# A FINDING MUST CARRY WHAT IT TAKES TO CHECK IT
#
# scitex-hub described their own failure precisely enough to remove it:
#
#   "The rule I have been quoting at myself all evening is 'a finding is a
#    claim about a string, so open the match'. I opened the FILE. Opening the
#    match means reading the string the tool actually emitted and checking it
#    appears where the tool says it does. I did not do the last step, and it
#    is the step."
#
# They went to the file, found a class that LOOKED like the reported one, and
# wrote a correct paragraph about the wrong object. Their verdict happened to
# be right, which is worse than wrong — a wrong verdict gets challenged.
#
# That step was hard because four of the eight messages named a class without
# quoting the selector, and none carried a line. A warning would not have
# helped; the finding now carries both, so "does the named thing appear where
# it says?" is answerable from the finding text alone.
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "css",
    [
        "#workspace-layout { color: red }\n",
        ".wft-node { color: red }\n",
        "#main-content { color: red !important }\n",
        ".panel-resizer { color: red !important }\n",
        "footer { padding: 0 !important }\n",
        "footer { display: none }\n",
        ":root { --color-fg: red }\n",
        "body { zen-mode: 1 }\n",
    ],
    ids=["tier1", "prefix", "container", "shared", "footer", "hide", "token", "state"],
)
def test_every_finding_names_a_position(tmp_path, css):
    """`file:line:` on every one, so nobody has to search a file for a class
    name that may occur in several places. hub landed on a nearby rule doing
    exactly that."""
    # Arrange
    app = _app(tmp_path, css)
    # Act
    report = validate_css_canonical(app)
    # Assert
    assert all(f.startswith("static/a.css:1:") for f in report.findings)


@pytest.mark.parametrize(
    "css",
    [
        "#workspace-layout { color: red }\n",
        "#main-content { color: red !important }\n",
        ".panel-resizer { color: red !important }\n",
        "footer { padding: 0 !important }\n",
        ":root { --color-fg: red }\n",
    ],
    ids=["tier1", "container", "shared", "footer", "token"],
)
def test_every_finding_quotes_the_selector_it_came_from(tmp_path, css):
    """THE MECHANICAL FORM OF "OPEN THE MATCH". With the selector in the
    message, checking a finding no longer requires opening the file at all —
    the reader can see whether the named thing is actually in the selector the
    tool matched.

    This is the check that would have caught the substring bug on sight: the
    finding said `.stx-shell-sidebar__header` and the selector was
    `.stx-shell-sidebar__header-compact`, and putting the two side by side is
    all it takes. Four of the message forms did not quote the selector, which
    is why nobody could put them side by side.
    """
    # Arrange — the selector is the whole line up to the brace.
    selector = css.split("{")[0].strip()
    app = _app(tmp_path, css)
    # Act
    report = validate_css_canonical(app)
    # Assert
    assert all(repr(selector) in f for f in report.findings)


# --------------------------------------------------------------------------
# BEM MODIFIERS — a state of the same component, not a different name
#
# 0.15.2's `(?![\w-])` boundary fixed one false positive and introduced a
# false NEGATIVE: it stopped matching `--modifier` forms the shell really
# renders. scitex-ui found it, and their fixtures below are MEASURED render
# sites in their TypeScript, not names either of us reasoned about.
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "css",
    [
        ".stx-shell-sidebar--collapsed { color: red !important }\n",
        ".panel-resizer--dragging { width: 4px !important }\n",
        ".stx-shell-sidebar__header--compact { color: red !important }\n",
    ],
    ids=["ui-measured", "modifier", "element-then-modifier"],
)
def test_a_bem_modifier_is_the_same_component_in_a_state(tmp_path, css):
    """`.stx-shell-sidebar--collapsed` IS rendered by the shell
    (`_Sidebar.ts:85, :103`), so an app `!important`ing it reaches a real shell
    node. 0.15.2's boundary silently permitted exactly that for two releases.

    The first case is scitex-ui's, measured in their TS rather than proposed.
    Their first scan for it returned ZERO — the classes are built with template
    literals, invisible to a literal-string search — and they declined to report
    that zero because the asymmetry looked implausible. Had they reported it I
    would have kept the boundary and shipped the hole a third time.
    """
    # Arrange
    app = _app(tmp_path, css)
    # Act
    report = validate_css_canonical(app)
    # Assert
    assert len(report.findings) == 1


@pytest.mark.parametrize(
    "css",
    [
        ".stx-shell-sidebar__header-compact { color: red !important }\n",
        ".panel-resizer-custom { width: 4px !important }\n",
        ".h-resizer-x { color: red !important }\n",
    ],
    ids=["writer-minted", "resizer", "h-resizer"],
)
def test_a_trailing_word_is_still_a_different_name(tmp_path, css):
    """THE HALF THE GRAMMAR MUST NOT SWALLOW. `--compact` is a modifier of a
    component; `-compact` is part of a different component's name.

    Extending the grammar to `__[\\w-]+` would cover ui's `__segment--current`
    and simultaneously re-admit writer's `__header-compact`, which the shell
    renders none of. A grammar cannot separate those: the difference is whether
    the shell renders that element, which is a fact about hub's tree. So
    ELEMENTS stay table entries and only MODIFIERS get grammar.
    """
    # Arrange
    app = _app(tmp_path, css)
    # Act
    report = validate_css_canonical(app)
    # Assert
    assert not report.findings


def test_the_tables_declare_themselves_a_lower_bound(tmp_path):
    """scitex-ui measured FIVE sites where the shell adds a caller-supplied
    class name, so no static list over their tree can ever be complete.

    They asked for the rule to be built sound-but-incomplete rather than
    assumed exhaustive, and for that to live in the PAYLOAD rather than only in
    a doc — because a table presented as complete is the gate that cannot fail
    wearing a list. `.stx-shell-resizer--*` is the known example today: shell
    -rendered, and absent from the tables pending its tier.
    """
    # Arrange
    app = _app(tmp_path, ".mine { color: red }\n")
    # Act
    report = validate_css_canonical(app)
    # Assert
    assert "LOWER BOUND" in " ".join(report.not_checked)


# ---------------------------------------------------------------------------
# THE REPORT'S SHAPE — added 2026-09-06 from scitex-hub's two findings against
# 0.16.1: the rule could not tell an app dir from a repo root, and its findings
# were prose their consumer had to substring-match.
# ---------------------------------------------------------------------------


def _app(tmp_path, css, *, manifest=True):
    """An app directory: a manifest.json and one stylesheet."""
    d = tmp_path / "app"
    (d / "static").mkdir(parents=True)
    (d / "static" / "a.css").write_text(css, encoding="utf-8")
    if manifest:
        (d / "manifest.json").write_text("{}", encoding="utf-8")
    return d


def test_a_root_without_a_manifest_yields_no_number_at_all():
    """THE 604-FILE TRAP, now closed by refusing instead of caveating.

    scitex-hub scanned their repo ROOT through a parameter named `app_dir` and
    got 604 files / 346 findings where the app population had 15. Their
    enumeration control agreed exactly with an independent walk — two
    instruments, same number, same wrong tree.

    Until 0.20.0 this returned the 346 beside `root_looks_like_an_app: False`,
    and the three tests here asserted that the caveat was present, correct, and
    not always-on. Every one of them passed while hub carried the 346 forward
    as a 12.8x regression. THE CAVEAT WAS NEVER THE FAILING PART — it was
    there, it was right, and a number beside it still gets read. So the
    assertion changed from "is the doubt reported" to "is a number produced",
    because only the second is what burned a caller.
    """
    # Arrange
    import tempfile
    from pathlib import Path as _P
    d = _app(_P(tempfile.mkdtemp()), ".mine { color: red }\n", manifest=False)
    # Act
    raised = pytest.raises(NotAnAppDirectoryError)
    # Assert
    with raised:
        validate_css_canonical(d)


def test_a_real_app_still_gets_its_report():
    """THE CONTROL. Without it, the refusal above is equally consistent with
    'refuses the wrong population' and 'refuses everything' — and a rule that
    refuses everything would also have passed every test in this file that
    only checks for raising."""
    # Arrange
    import tempfile
    from pathlib import Path as _P
    d = _app(_P(tempfile.mkdtemp()), ".mine { color: red }\n")
    # Act
    report = validate_css_canonical(d)
    # Assert
    assert report.files_scanned == 1


def test_every_finding_has_a_record_beside_it():
    # Arrange
    import tempfile
    from pathlib import Path as _P
    d = _app(_P(tempfile.mkdtemp()), "#workspace-shell { color: red }\n")
    # Act
    report = validate_css_canonical(d)
    # Assert
    assert len(report.details) == len(report.findings) == 1


def test_a_record_stringifies_to_the_line_it_replaces():
    """The prose form is KEPT, not replaced. A consumer that formats findings
    for a human keeps working unchanged."""
    # Arrange
    import tempfile
    from pathlib import Path as _P
    d = _app(
        _P(tempfile.mkdtemp()),
        "#workspace-shell { color: red }\n"
        ".stx-shell-sidebar { color: red !important }\n",
    )
    # Act
    report = validate_css_canonical(d)
    # Assert
    assert report.findings and tuple(str(x) for x in report.details) == report.findings


def test_a_consumer_can_branch_on_rule_without_reading_the_message():
    """THE WHOLE POINT. hub mis-bucketed 316 findings into 'other' by keyword
    -matching the message — 'using exactly the substring reasoning this rule
    exists to discourage'."""
    # Arrange
    import tempfile
    from pathlib import Path as _P
    d = _app(_P(tempfile.mkdtemp()), "#workspace-shell { color: red }\n")
    # Act
    rules = [x.rule for x in validate_css_canonical(d).details]
    # Assert
    assert rules == ["shell-instance-name"]


def test_a_record_carries_the_protected_name_it_matched():
    # Arrange
    import tempfile
    from pathlib import Path as _P
    d = _app(_P(tempfile.mkdtemp()), "#workspace-shell { color: red }\n")
    # Act
    subjects = [x.subject for x in validate_css_canonical(d).details]
    # Assert
    assert subjects == ["#workspace-shell"]


def test_a_report_whose_two_forms_disagree_is_refused():
    """The string form and the record form describe the same findings. A
    report where they diverge is a bug in this module, so it fails where it is
    built rather than three layers downstream in hub's bucketing."""
    # Arrange
    from scitex_app.appmaker._validate import CssFinding
    detail = CssFinding(
        rule="shell-instance-name",
        tier="1",
        path="a.css",
        line=1,
        selector=".x",
        message="something",
    )
    # Act
    build = functools.partial(
        CssScanReport,
        findings=("a.css:1: SOMETHING ELSE",),
        files_scanned=1,
        details=(detail,),
    )
    # Assert
    with pytest.raises(ValueError, match="disagree"):
        build()


def test_a_finding_without_a_position_is_refused():
    # Arrange
    from scitex_app.appmaker._validate import CssFinding
    # Act
    build = functools.partial(
        CssFinding,
        rule="r", tier="1", path="a.css", line=0, selector=".x", message="m",
    )
    # Assert
    with pytest.raises(ValueError, match="1-based"):
        build()


def test_a_finding_without_a_rule_is_refused():
    """An empty `rule` forces a consumer back to matching the message text,
    which is the defect this record exists to remove."""
    # Arrange
    from scitex_app.appmaker._validate import CssFinding
    # Act
    build = functools.partial(
        CssFinding,
        rule="", tier="1", path="a.css", line=1, selector=".x", message="m",
    )
    # Assert
    with pytest.raises(ValueError, match="branch on"):
        build()
