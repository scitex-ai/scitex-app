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
    "NotAnAppDirectoryError",
    "SHARED_COMPONENT_CLASSES",
    "SHELL_INSTANCE_NAMES",
    "SHELL_TOKEN_PREFIXES",
    "css_files",
    "validate_css_canonical",
]

from ._css_match import (
    _FOOTER_ELEMENT,
    _matched_names,
    _rule_blocks,
    _strip_excluded,
    _strip_pseudo_args,
)
from ._css_tables import (
    _CHECKED,
    _NOT_CHECKED,
    APP_CONTAINERS,
    BODY_STATE_CLASSES,
    SHARED_COMPONENT_CLASSES,
    SHELL_INSTANCE_NAMES,
    SHELL_INSTANCE_PREFIXES,
    SHELL_TOKEN_PREFIXES,
)
from ._css_finding import CssFinding

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
    details: tuple[CssFinding, ...] = ()

    def __post_init__(self) -> None:
        if self.files_scanned < 0:
            raise ValueError("files_scanned cannot be negative")
        if self.findings and self.files_scanned == 0:
            raise ValueError(
                "findings reported against zero scanned files — the numerator "
                "and denominator disagree about what was read"
            )
        # THE TWO REPRESENTATIONS MUST NOT DRIFT. `findings` is the string form
        # kept for existing consumers and `details` is the record form; they
        # describe the same findings, so a report where they disagree is a bug
        # in this module, not a caller error. Checked here rather than trusted,
        # because the whole point of adding `details` is that someone will act
        # on it instead of the prose.
        if self.details and tuple(str(d) for d in self.details) != self.findings:
            raise ValueError(
                "findings and details disagree — the string form and the "
                "record form must describe the same findings, in order"
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
        # THIS USED TO CARRY A `root_looks_like_an_app` CAVEAT, AND THE CAVEAT
        # DID NOT WORK. Preserved rather than deleted, because the reasoning
        # error is the lesson. It read:
        #
        #     NOT a refusal. Scanning a tree deliberately is legitimate, and
        #     this rule cannot know the caller's intent. What it can do is say
        #     that the root does not look like the thing the parameter is named
        #     after — the same way `files_scanned == 0` reads NOT SCANNED.
        #
        # The analogy is what broke it. `scanned_nothing` changes the NUMBER
        # (there is none); the root caveat left `346` sitting there, printable.
        # On 2026-09-06 scitex-hub ran this on their repo root, got 604 files /
        # 346 findings against a right answer of 15, and carried the 346 into
        # two messages as a 12.8x regression in this detector — with the caveat
        # in the report the whole time. They had asserted a >=300-file floor AND
        # fired a positive control; both passed, because one asked whether the
        # walk found files and the other whether the rule could fire, and
        # neither could ask whether the TREE was in scope.
        #
        # A NUMBER PRINTED NEXT TO A CAVEAT STILL GETS PRINTED — their words,
        # asking for this refusal. So the wrong population no longer produces a
        # number at all; see `validate_css_canonical`.
        return head + "\n  checked: " + "; ".join(self.checked) + "\n  NOT checked: " + "; ".join(
            self.not_checked
        )


class NotAnAppDirectoryError(ValueError):
    """Raised when the scan root is not one app, so no count would be about
    app code.

    A distinct type rather than a bare ValueError because a caller sweeping
    many directories has a legitimate reason to catch exactly this one and
    skip, without also swallowing the malformed-report errors this module
    raises for its own bugs.
    """


def css_files(app_dir: str | Path) -> list[Path]:
    """The stylesheets this rule reads — the denominator of a result.

    Takes any directory: this is the walk, and a caller sweeping a tree of
    apps is expected to use it per app. Unlike `validate_css_canonical` it
    does NOT require a manifest, because counting files in a tree is a
    question with an honest answer.

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




def validate_css_canonical(app_dir: str | Path) -> CssScanReport:
    """Tiers 1 and 2 of the workspace CSS rule. UNARMED; `validate()` does not
    call this. See the module docstring for what it does not check.

    Scopes to ONE app and REFUSES anything else — see
    `NotAnAppDirectoryError`. To sweep a tree, loop over its app directories
    and call this per app; `css_files()` is exported for the walk.
    """
    root = Path(app_dir)
    # AN APP DIRECTORY HAS A manifest.json; A REPO ROOT DOES NOT. Checked
    # BEFORE the walk, so the expensive part never runs for a root whose
    # answer would not have been about app code anyway.
    if not (root / "manifest.json").is_file():
        # TWO CAUSES REACH THIS LINE AND THEY NEED DIFFERENT FIXES. Until
        # 0.20.1 the message said only the first, which sent the second
        # somewhere useless: "loop over your app dirs" tells a caller to do
        # the thing they already did — the directory WAS in their loop and
        # this call is why it got skipped.
        #
        #   no manifest at all      -> not an app. Wrong target. Their fix.
        #   a manifest in another   -> an app this rule cannot read. The
        #   format                     manifest is the problem, not the aim.
        #
        # Raised by scitex-hub against 0.20.0: apps/legacy/notebook_app
        # carries a manifest.yaml (name/label/version/icon/...) and ships
        # CSS, so "not an app directory" is simply false about it.
        other = sorted(
            p.name
            for p in root.glob("manifest.*")
            if p.is_file() and p.name != "manifest.json"
        )
        if other:
            raise NotAnAppDirectoryError(
                f"{root} has no manifest.json, but it does have "
                f"{', '.join(other)} — so this looks like an app whose "
                f"manifest this rule cannot read, NOT the wrong directory. "
                f"Only manifest.json is read: the fix is in that app, not in "
                f"how you called this. If it is genuinely current, give it a "
                f"manifest.json; if it predates that format, it is out of "
                f"scope for this rule and skipping it is correct."
            )
        raise NotAnAppDirectoryError(
            f"{root} is not an app directory (no manifest.json, and nothing "
            f"else manifest-shaped). This rule scopes to ONE app: a repo root "
            f"pools shell and infrastructure CSS it was never written for, so "
            f"a count taken here would be real and not about app code. Pass "
            f"an app directory, or loop over your app dirs and call this per "
            f"app — css_files() is exported if you need the walk itself."
        )
    files = css_files(app_dir)
    found: list[CssFinding] = []

    def add(rule, tier, rel, line, selector, message, subject=""):
        """ONE PLACE THAT BUILDS A FINDING. Eight call sites used to format
        their own string, which is how the prefix and the message drifted
        apart into something a consumer had to re-parse."""
        found.append(
            CssFinding(
                rule=rule,
                tier=tier,
                path=str(rel),
                line=line,
                selector=selector,
                message=message,
                subject=subject,
            )
        )

    for css_file in files:
        try:
            content = strip_css_comments(
                css_file.read_text(encoding="utf-8", errors="replace")
            )
        except OSError:
            continue
        rel = css_file.relative_to(root)

        for selector, body, line in _rule_blocks(content):
            # TWO strippers, for two different questions — see
            # `_strip_excluded`. `targets` is what this rule STYLES;
            # `bare` is the selector list with every internal comma removed.
            targets = _strip_excluded(selector)
            bare = _strip_pseudo_args(targets)
            # TIER 1 — any mention.
            for name in _matched_names(targets, SHELL_INSTANCE_NAMES):
                add(
                    "shell-instance-name", "1", rel, line, selector,
                    f"selector {selector!r} names {name!r}, which the "
                    f"shell renders and owns — style your own nodes instead",
                    subject=name,
                )
            for prefix in SHELL_INSTANCE_PREFIXES:
                if prefix in targets:
                    add(
                        "shell-instance-prefix", "1", rel, line, selector,
                        f"selector {selector!r} names the shell-owned "
                        f"{prefix}* family — style your own nodes instead",
                        subject=prefix,
                    )

            # TIER 2a — containers and shared components: !important only.
            if "!important" in body:
                for name in _matched_names(targets, APP_CONTAINERS):
                    add(
                        "important-on-app-container", "2a", rel, line, selector,
                        f"!important on {name!r} in {selector!r} — the app "
                        f"renders INSIDE it; style your children, never the box",
                        subject=name,
                    )
                for name in _matched_names(targets, SHARED_COMPONENT_CLASSES):
                    add(
                        "important-on-shared-component", "2a", rel, line,
                        selector,
                        f"!important on the shared component {name!r} in "
                        f"{selector!r} — your own instance is yours to style, "
                        f"but !important reaches the shell's instances too",
                        subject=name,
                    )

                if _FOOTER_ELEMENT.search(bare):
                    add(
                        "important-on-shell-footer", "2a", rel, line, selector,
                        f"!important on the shell's footer element in "
                        f"{selector!r} — an app may render its own <footer>, "
                        f"but a bare `footer` rule reaches the shell's too",
                        subject="footer",
                    )

            # TIER 2b — tokens: read freely, never redefine at :root.
            if re.search(r"(^|[\s,])(:root|html)([\s,]|$)", targets):
                for prefix in SHELL_TOKEN_PREFIXES:
                    if re.search(rf"^\s*{re.escape(prefix)}", body, re.MULTILINE):
                        add(
                            "redefines-shell-tokens", "2b", rel, line, selector,
                            f"redefines {prefix}* tokens at {selector!r} "
                            f"— read them with var(), never redefine them for "
                            f"the whole shell",
                            subject=prefix,
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
                add(
                    "hides-shell-footer", "2b", rel, line, selector,
                    f"must not hide the shell's footer, and "
                    f"{selector!r} is not scoped to the app's own",
                    subject="footer",
                )

            # TIER 2c — setting shell state. Reading it (`body.zen-mode .mine`)
            # is fine; a rule whose SUBJECT is the body state class is not.
            #
            # ALSO MOVED INSIDE the loop, for the line number. It ran per FILE
            # against `body\s*\{[^}]*<state>`, which is the same rule this
            # expresses per block — `body` as the whole selector, the state
            # named in the declarations — but could report no position.
            if selector.strip() == "body":
                for state in BODY_STATE_CLASSES:
                    if state in body:
                        add(
                            "sets-shell-state", "2c", rel, line, selector,
                            f"sets the shell state class "
                            f"{state!r} — the shell owns this state; react to "
                            f"it, do not drive it",
                            subject=state,
                        )

    # Every report that reaches here is about ONE app: the manifest check at
    # the top refused anything else, so there is no in-scope flag to carry.
    return CssScanReport(
        findings=tuple(str(f) for f in found),
        files_scanned=len(files),
        details=tuple(found),
    )


# EOF