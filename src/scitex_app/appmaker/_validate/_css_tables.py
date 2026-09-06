#!/usr/bin/env python3
"""WHAT THE SHELL OWNS — the measured tables, and the rule's declared scope.

Split out of `_css.py` on 2026-09-06 (528 lines against a 512 limit). This
half is PURE DATA and every entry in it is a fact about scitex-hub's tree
rather than a decision of mine: the tiering came from their 2026-09-04
measurement, `.panel-resizer` moved tier on their re-count, and the footer
compromise came from a shell comment they quoted. When any of it is wrong,
it is wrong because their tree changed — which is why it lives apart from
the matching logic in `_css_match.py`, where the errors are mine.
"""

from __future__ import annotations

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
    "the protected-name tables are a LOWER BOUND, not the shell's full "
    "vocabulary. scitex-ui measured five sites where the shell adds a "
    "CALLER-SUPPLIED class name (ClipboardHandler.ts:234, TreeInitHandler.ts:57, "
    "ContextMenuHandler.ts:122/:140/:165), so no static list over their tree can "
    "be complete — and a name they add later goes unmatched here with nothing on "
    "their side failing. A known example today: `.stx-shell-resizer--*` is "
    "shell-rendered (_Resizer.ts:41/42/172/231) and absent from these tables "
    "pending its tier",
    "a BODY-CLASS-scoped footer rule (`body.myapp-page footer {display:none}`) "
    "— it is not leftmost, so this rule passes it, and unlike `.myapp footer` "
    "it DOES reach the shell's footer, which lives inside <body>. The two "
    "differ only in whether the scoping element contains the shell's node, "
    "which is a DOM fact and not a string fact. It is also a documented shell "
    "pattern rather than a defect, so the rule is the shell's to state before "
    "it can be enforced (same parser, same card)",
)


# EOF
