#!/usr/bin/env python3
"""The canonical workspace-CSS rule — tiers 1 and 2 of three.

WHY THIS MODULE EXISTS. Three implementations of one spec lived across two
repositories: `validator.py`'s AppValidator (8 selectors, "any mention is an
error"), `_frame.py`'s validate_css (4 selectors, "!important only"), and
scitex-hub's own copy, which is the ORIGIN of the second. They disagreed in
both directions on the same input:

    #main-content { color: red }     passed one, failed the other
    footer { display: none }         the reverse

scitex-hub measured the shell on 2026-09-04 — 30 agents, HEAD pinned, a control
in every loop, `defined_at` per row — and the table did not correct my list, it
INVALIDATED MY INSTRUMENT. The rule is ownership BY NODE, not by name:

    a node the SHELL renders / sizes / queries        -> no-touch
    the container the app renders INTO                -> no-!important
    shared design tokens                              -> read, never redefine
    a SHARED COMPONENT class (apps render their own
    resizers, toggle buttons, sidebar elements)       -> FREE on the app's own
                                                        nodes, no-touch on the
                                                        SHELL's instances

The last line is why "does this stylesheet MENTION the name" is answerable and
is the WRONG QUESTION. `.stx-shell-*` occurs 842 times across 114 files and is
not blanket no-touch: hub's own apps render nodes carrying
`stx-shell-sidebar__title/__content/__header`, and 42 app-level selector lines
style them today. A mention-ban fails all 42 — correct code.

WHAT MAKES TIER 1 SOUND ANYWAY. A substring scan cannot see nodes, so tier 1 is
restricted to names an app can NEVER legitimately own: ids (singular by
definition — no app renders its own `#workspace-layout`) and the shell's own
root classes. For those, "mentions it" and "selects the shell's node" coincide.
Everything an app might own an INSTANCE of is tier 2, where only the abusive
operations error. The tiering is not a severity ranking; it is the line between
where the proxy holds and where it does not.

WHAT THIS DELIBERATELY DOES NOT CHECK — see `CssScanReport.not_checked`, which
carries it in the RETURN VALUE rather than only here.

Tier 3 is the structural rule that an app's selectors must be scoped under the
app's own root. A bare `[data-pane]{}` or `.panel-toggle-btn{}` selects the
shell's frame WITHOUT MENTIONING ANY PROTECTED NAME, so no name-based validator
— mine, hub's, or this one — can see it. That needs a parser.

Shipping tiers 1+2 without tier 3 was hub's call, and their condition was that
the result must SAY SO: a validator blind to a whole class is a check that
cannot fail for that class, and its green will be read as "this app's CSS is
properly scoped" by someone with no reason to doubt it. Between us in one
evening we produced three of those — their 1,116 files/0 findings that meant NOT
SCANNED, my two peer repos reported "clean" from directories that did not exist,
and a shipped skill doc that said "opt-in" for two releases after the rule was
armed. A green that names its own blind spot is honest; a bare one teaches
people to trust it for what it never looked at.

UNARMED. `validate()` does not call this. Arming waits on hub re-measuring their
own five findings against THIS implementation, from a stated ref, with the
denominator from `css_files()` rather than a second walk.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from ._comments import strip_css_comments
from ._prefix import PREFIX_SKIP_DIRS

__all__ = [
    "APP_CONTAINERS",
    "BODY_STATE_CLASSES",
    "CssScanReport",
    "SHARED_COMPONENT_CLASSES",
    "SHELL_INSTANCE_NAMES",
    "SHELL_TOKEN_PREFIXES",
    "css_files",
    "validate_css_canonical",
]

#: TIER 1 — nodes the shell renders, sizes or queries, whose names an app can
#: never legitimately own. Ids are singular by definition and these classes are
#: the shell's own roots, so "mentions it" and "selects the shell's node"
#: coincide here and nowhere else. Any mention is an error.
SHELL_INSTANCE_NAMES = (
    "#workspace-layout",
    "#workspace-content",
    "#workspace-shell",
    "#pane-chat",
    "#pane-console",
    "#pane-editor",
    "#pane-module",
    "#ai-panel-container",
    "#stx-shell-ai-panel",
    "#ws-worktree-sidebar",
    "#ws-viewer-sidebar",
    "#ws-worktree-tree",
    "#ws-module-loading",
    "#site-footer",
    "#app-loading-screen",
    ".workspace-pane",
    ".workspace-sidebar",
    ".workspace-three-col",
    ".workspace-files-tree",
    ".global-header",
    ".module-tab-bar",
    ".repo-monitor",
)

#: TIER 1, prefix form. Same reasoning; these families are entirely shell-owned.
SHELL_INSTANCE_PREFIXES = (
    ".editor-split-",
    ".ws-viewer-",
    ".wft-",
    ".stx-shell-ai-",
)

#: TIER 2 — the containers an app's own markup is rendered INTO. The app styles
#: its children freely; it must not `!important` the box itself.
APP_CONTAINERS = (
    "#main-content",
    "#app-mount",
    ".ws-module-pane",
)

#: TIER 2 — shared components apps are REQUIRED to render their own instances
#: of. Free on the app's nodes; only `!important` errors. `.panel-toggle-btn` is
#: documented as one apps must render (hub MASTER/03_SHARED_UI_COMPONENTS.md:186;
#: writer renders three), and the shell renders ZERO `.h-resizer`/`.v-resizer`.
SHARED_COMPONENT_CLASSES = (
    #: MEASURED 2026-09-05 by scitex-hub, correcting their own 09-04 summary:
    #: apps render `.panel-resizer` 41 times across NINE apps against the
    #: shell's 6, so it is the same family as `.h-resizer` (shell renders zero)
    #: and NOT the no-touch class their one-line summary grouped it with. Tier 1
    #: here would have failed correct code in nine apps.
    ".panel-resizer",
    ".stx-shell-sidebar",
    ".stx-shell-sidebar__title",
    ".stx-shell-sidebar__header",
    ".stx-shell-sidebar__content",
    ".h-resizer",
    ".v-resizer",
    ".panel-toggle-btn",
)

#: TIER 2 — the shell's own footer element, by measurement and by compromise.
#:
#: `#site-footer` is TIER 1 above: 3 shell-side renders, ZERO app-side.
#: A BARE `footer` element selector is different and the honest rule would be
#: tier 1 — such a selector CANNOT be scoped to the app's own node, so it
#: reaches the shell's `<footer>` by construction. scitex-hub measured one app
#: legitimately rendering its own (`public_app public_status.html:73`,
#: `<footer class="status-footer">`), confirmed by a shell comment saying the
#: workspace page hides `.site-footer` so a page may carry its own legal line.
#:
#: (a) IS NOT IMPLEMENTABLE BY SUBSTRING, which is why this is (b). Banning the
#: token `footer` cannot tell the selector `footer` from `.status-footer`,
#: `.site-footer` or `--footer-height` — it would flag that app's correct
#: class. That is tier 3's problem wearing a different hat.
#:
#: RESIDUAL RISK, declared in `not_checked` rather than left implicit: an app
#: writing `footer { color: red }` WITHOUT `!important` restyles the shell's
#: footer and this rule does not see it. Revisit when the parser lands.
#: LEFTMOST position only — `footer` starting a selector, or following a comma.
#: `.myapp footer` is SCOPED to the app's own subtree and cannot reach the
#: shell's element, so it is correct code and must not report. Measured: the
#: first version matched any position and flagged `.myapp footer { ... }`,
#: which is exactly the false-positive class this whole rule exists to avoid.
#:
#: This is PARTIAL scope detection and it does not generalise. "Is `footer` the
#: leftmost token" is answerable by substring; "is the leftmost token the APP'S
#: OWN root" is tier 3 and is not. It removes one specific false positive, not
#: the class.
_FOOTER_ELEMENT = re.compile(r"(^|,)\s*footer(?![\w-])")

#: Blank the ARGUMENTS of functional pseudo-classes before the leftmost test.
#:
#: `:is(header, footer) .x` puts `footer` after a COMMA, so the leftmost rule
#: reads it as a second selector in a list and fires. It is not one — it is an
#: argument, and `:is()` / `:not()` / `:where()` / `:has()` all take selector
#: lists whose commas are internal. `:not(footer)` is the sharpest case: the
#: rule EXCLUDES a footer and the detector called that targeting one.
#:
#: scitex-hub found this against 0.14.4 in `public_app/css/pricing.css`
#: (`body > :first-child:not(header):not(main):not(footer)`), which the
#: canonical already passed — `(` is not a boundary. The hole was in the
#: HYPOTHETICAL they offered beside it, `:is(header, footer)`, which fires.
#: Their concrete example was already handled and their generalisation was
#: right anyway; measuring both is what separated them.
#:
#: Blanking rather than deleting keeps offsets and the leftmost/`,` structure
#: intact, so nothing else shifts under the test.
_PSEUDO_ARGS = re.compile(r"\(([^()]*)\)")


def _strip_pseudo_args(selector: str) -> str:
    """Replace the contents of every parenthesised group with spaces. Applied
    repeatedly so nested groups (`:has(:not(footer))`) collapse from the inside
    out.

    FOR THE LEFTMOST TEST ONLY. It answers a STRUCTURAL question — "does this
    selector list begin with a bare `footer`?" — for which every internal comma
    is noise regardless of which pseudo-class it sits in. Do not reach for it
    to answer the membership question below; see `_strip_excluded` for why the
    two cannot share one stripper.
    """
    previous = None
    while previous != selector:
        previous = selector
        selector = _PSEUDO_ARGS.sub(lambda m: "(" + " " * len(m.group(1)) + ")", selector)
    return selector


#: `:not(X)` EXCLUDES X and `:has(X)` makes X a condition on an ancestor. In
#: neither is X styled, so a protected name appearing there is not a target.
_EXCLUDED_ARG = re.compile(r":(?:not|has)\([^()]*\)", re.IGNORECASE)


def _strip_excluded(selector: str) -> str:
    """Blank `:not(...)` and `:has(...)` whole, repeatedly so nesting collapses
    from the inside out.

    DELIBERATELY NOT `_strip_pseudo_args`, AND THIS IS THE OPPOSITE OF THE
    USUAL LESSON. Two strippers here are not one rule implemented twice: they
    answer two different questions, and collapsing them breaks one of the two.

        membership  "is this protected name a TARGET of this rule?"
                    `:not(.panel-resizer)` excludes it     -> not a target
                    `:is(.foo, .h-resizer)` MATCHES it     -> IS a target
        leftmost    "does this selector list begin with a bare `footer`?"
                    every internal comma is noise, `:is()` included

    So membership must keep `:is()` / `:where()` contents and drop `:not()` /
    `:has()`; the leftmost test must drop all four. Blanking everything for
    membership would silently stop reporting `:is(.foo, .h-resizer)
    {!important}`, which really does style the shell's resizers.

    scitex-hub proposed `:is(.foo, .h-resizer)` and `:where(.stx-shell-sidebar)`
    as must-NOT-fire cases alongside their `:not()` finding. The `:not()` half
    was right and is fixed here; the `:is()` half is not — `:is()` is a
    matching pseudo-class, and treating it like `:not()` would have converted
    their false positive into a false negative.
    """
    previous = None
    while previous != selector:
        previous = selector
        selector = _EXCLUDED_ARG.sub(lambda m: " " * len(m.group(0)), selector)
    return selector

#: TIER 2 — shared design tokens. An app may READ them with `var(--x)`; it must
#: not REDEFINE them at `:root`, which changes them for the whole shell.
SHELL_TOKEN_PREFIXES = ("--color-", "--workspace-", "--stx-")

#: TIER 2 — body classes the SHELL sets to express state. An app may style
#: itself differently when one is present; setting one drives the shell.
BODY_STATE_CLASSES = (
    "zen-mode",
    "footer-collapsed",
    "element-inspector-selection-mode",
)

_CHECKED = (
    "references to shell-owned ids and root classes",
    "!important against app containers and shared components",
    ":root redefinition of shared design tokens",
    "setting shell body-state classes",
)

_NOT_CHECKED = (
    "whether an app's rules are SCOPED under the app's own root — a bare "
    "`[data-pane]{}` selects the shell's frame while mentioning no protected "
    "name, and no name-based rule can see it (needs a parser; tracked on "
    "app-css-tier3-structural-scoping-needs-a-parser-20260905)",
    "whether a bare `footer` rule without !important reaches the SHELL's "
    "footer — the honest rule is 'any mention', but a substring test cannot "
    "tell the selector `footer` from `.status-footer` or `--footer-height`, "
    "and one app legitimately renders its own (same parser, same card)",
    "a `footer` that is the SUBJECT of a leading matching pseudo-class "
    "(`:is(header, footer) {…!important}`) — the leftmost test drops every "
    "comma inside `:is()` / `:where()`, because keeping them would fire on the "
    "far commoner `:is(header, footer) .x {…}`, where the footer is an "
    "ANCESTOR and the subject is `.x`. Separating the two needs to know which "
    "compound is the subject (same parser, same card)",
    "a BODY-CLASS-scoped footer rule (`body.myapp-page footer {display:none}`) "
    "— it is not leftmost, so this rule passes it, and unlike `.myapp footer` "
    "it DOES reach the shell's footer, which lives inside <body>. The two "
    "differ only in whether the scoping element contains the shell's node, "
    "which is a DOM fact and not a string fact. It is also a documented shell "
    "pattern rather than a defect, so the rule is the shell's to state before "
    "it can be enforced (same parser, same card)",
)


@dataclass(frozen=True)
class CssScanReport:
    """A fixed shape, because an ad-hoc return is how "I could not tell"
    silently becomes "yes".

    `files_scanned` is the DENOMINATOR and it is here rather than left to the
    caller: 0 findings across 0 files is NOT SCANNED, and a caller who computes
    the denominator with their own walk can produce a large one beside a clean
    numerator from ours — two instruments pointed at different trees. That is
    not hypothetical; it cost a peer a whole measurement on 2026-09-05.

    `not_checked` is the blind spot, in the return value. A caller rendering a
    green without it is claiming something this rule never looked at.
    """

    findings: tuple[str, ...] = ()
    files_scanned: int = 0
    checked: tuple[str, ...] = _CHECKED
    not_checked: tuple[str, ...] = _NOT_CHECKED

    def __post_init__(self) -> None:
        if self.files_scanned < 0:
            raise ValueError("files_scanned cannot be negative")
        if self.findings and self.files_scanned == 0:
            raise ValueError(
                "findings reported against zero scanned files — the numerator "
                "and denominator disagree about what was read"
            )

    @property
    def scanned_nothing(self) -> bool:
        """True when this result says NOT SCANNED rather than CLEAN."""
        return self.files_scanned == 0

    def summary(self) -> str:
        """One line a human can act on, denominator and blind spot included."""
        head = (
            "NOT SCANNED — 0 stylesheets found"
            if self.scanned_nothing
            else f"{len(self.findings)} finding(s) across {self.files_scanned} stylesheet(s)"
        )
        return head + "\n  checked: " + "; ".join(self.checked) + "\n  NOT checked: " + "; ".join(
            self.not_checked
        )


def css_files(app_dir: str | Path) -> list[Path]:
    """The stylesheets this rule reads — the denominator of a result.

    Exported so a caller never writes a second walk. Skip names are matched
    RELATIVE to the scan root, so a scan rooted inside `.worktrees/` or
    `node_modules/` is not silently emptied by an ancestor the caller did not
    choose (0.14.4; the defect cost scitex-hub a 1,116-file report that had in
    fact read nothing).
    """
    root = Path(app_dir)
    if not root.exists():
        raise FileNotFoundError(
            f"cannot scan {root}: no such path. 'No findings' from a path that "
            f"is not there is indistinguishable from a clean tree, so this "
            f"refuses rather than reporting clean."
        )
    if not root.is_dir():
        raise NotADirectoryError(f"cannot scan {root}: not a directory.")
    out = []
    for path in sorted(root.rglob("*.css")):
        if any(p in PREFIX_SKIP_DIRS for p in path.relative_to(root).parts):
            continue
        out.append(path)
    return out


def _rule_blocks(content: str):
    """(selector, body) for each top-level rule. Not a parser — see the module
    docstring. Enough to attribute a declaration to the selector it sits under,
    which is all tiers 1 and 2 need."""
    for m in re.finditer(r"([^{}]+)\{([^{}]*)\}", content, re.DOTALL):
        yield m.group(1).strip(), m.group(2)


def validate_css_canonical(app_dir: str | Path) -> CssScanReport:
    """Tiers 1 and 2 of the workspace CSS rule. UNARMED; `validate()` does not
    call this. See the module docstring for what it does not check."""
    files = css_files(app_dir)
    root = Path(app_dir)
    findings: list[str] = []

    for css_file in files:
        try:
            content = strip_css_comments(
                css_file.read_text(encoding="utf-8", errors="replace")
            )
        except OSError:
            continue
        rel = css_file.relative_to(root)

        for selector, body in _rule_blocks(content):
            # TWO strippers, for two different questions — see
            # `_strip_excluded`. `targets` is what this rule STYLES;
            # `bare` is the selector list with every internal comma removed.
            targets = _strip_excluded(selector)
            bare = _strip_pseudo_args(targets)
            # TIER 1 — any mention.
            for name in SHELL_INSTANCE_NAMES:
                if name in targets:
                    findings.append(
                        f"{rel}: selector {selector!r} names {name!r}, which the "
                        f"shell renders and owns — style your own nodes instead"
                    )
            for prefix in SHELL_INSTANCE_PREFIXES:
                if prefix in targets:
                    findings.append(
                        f"{rel}: selector {selector!r} names the shell-owned "
                        f"{prefix}* family — style your own nodes instead"
                    )

            # TIER 2a — containers and shared components: !important only.
            if "!important" in body:
                for name in APP_CONTAINERS:
                    if name in targets:
                        findings.append(
                            f"{rel}: !important on {name!r} — the app renders "
                            f"INSIDE it; style your children, never the box"
                        )
                for name in SHARED_COMPONENT_CLASSES:
                    if name in targets:
                        findings.append(
                            f"{rel}: !important on the shared component {name!r} "
                            f"— your own instance is yours to style, but "
                            f"!important reaches the shell's instances too"
                        )

                if _FOOTER_ELEMENT.search(bare):
                    findings.append(
                        f"{rel}: !important on the shell's footer element — "
                        f"an app may render its own <footer>, but a bare "
                        f"`footer` rule reaches the shell's too"
                    )

            # TIER 2b — tokens: read freely, never redefine at :root.
            if re.search(r"(^|[\s,])(:root|html)([\s,]|$)", targets):
                for prefix in SHELL_TOKEN_PREFIXES:
                    if re.search(rf"^\s*{re.escape(prefix)}", body, re.MULTILINE):
                        findings.append(
                            f"{rel}: redefines {prefix}* tokens at {selector!r} "
                            f"— read them with var(), never redefine them for "
                            f"the whole shell"
                        )

            # TIER 2b(ii) — hiding the shell's footer, with or without
            # !important. Carried over from the rule this replaces, where
            # scitex-hub's baseline found a real instance.
            #
            # MOVED INSIDE the rule loop. It used to run once per FILE against
            # a `footer … { … display:none }` regex over the whole content,
            # which carried the same pseudo-class hole as the check above and
            # could not be fixed in the same place. Reading the block's own
            # selector makes the two footer checks share one definition of
            # "this selector's subject is a bare footer" instead of two that
            # drift.
            if _FOOTER_ELEMENT.search(bare) and re.search(
                r"display\s*:\s*none", body
            ):
                findings.append(f"{rel}: must not hide the shell's footer")

        # TIER 2c — setting shell state. Reading it (`body.zen-mode .mine`) is
        # fine; a rule whose SUBJECT is the body state class is not.
        for state in BODY_STATE_CLASSES:
            if re.search(rf"body\s*\{{[^}}]*{re.escape(state)}", content, re.DOTALL):
                findings.append(
                    f"{rel}: sets the shell state class {state!r} — the shell "
                    f"owns this state; react to it, do not drive it"
                )

    return CssScanReport(findings=tuple(findings), files_scanned=len(files))


# EOF
