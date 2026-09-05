"""Workspace frame rules — what an app's templates and CSS must not do to the shell."""

from __future__ import annotations

from ._comments import strip_css_comments, strip_html_comments
import re
from pathlib import Path

from ._app_layout import _get_app_name

# Frame selectors that app CSS must not style
PROTECTED_SELECTORS = [
    ".stx-shell-sidebar",
    ".stx-shell-sidebar__title",
    ".panel-resizer",
    "footer",
]

# Forbidden frame block overrides
FORBIDDEN_BLOCK_OVERRIDES = [
    "workspace_worktree_pane",
    "workspace_ai_pane",
    "workspace_viewer_pane",
    "workspace_apps_pane",
]


def validate_templates(app_dir: str | Path) -> list[str]:
    """Check template compliance with workspace frame rules."""
    errors = []
    root = Path(app_dir)
    app_name = _get_app_name(root)
    if not app_name:
        return errors

    index_html = root / "templates" / app_name / "index.html"
    if not index_html.exists():
        return errors

    try:
        raw = index_html.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return errors

    # COMMENTS ARE STRIPPED, AND HERE IT MATTERS IN BOTH DIRECTIONS.
    #
    # The checks below are PRESENCE tests, so a comment does not merely add a
    # spurious finding — it can SATISFY A REQUIREMENT. Measured on 0.14.2 with
    # controls: a page carrying `global_base.html` and `block content` only
    # inside an HTML comment, and extending nothing, reported ZERO errors.
    #
    # That is a false NEGATIVE in a check that runs by DEFAULT, which makes it
    # the opposite of, and worse than, every other instance of this blindness:
    # those were noisy, this one was silent. The forbidden-override loop below
    # has the ordinary false POSITIVE — a commented-out override reported.
    # One strip fixes both.
    content = strip_html_comments(raw)

    # Must extend global_base.html
    if "global_base.html" not in content:
        errors.append("index.html must extend 'global_base.html'")

    # Must have {% block content %}
    if "block content" not in content:
        errors.append("index.html must define {% block content %}")

    # Must NOT override frame blocks
    for block_name in FORBIDDEN_BLOCK_OVERRIDES:
        if f"block {block_name}" in content:
            errors.append(f"index.html must not override '{{% block {block_name} %}}'")

    return errors


def validate_css(app_dir: str | Path) -> list[str]:
    """Check CSS compliance with workspace frame rules."""
    errors = []
    root = Path(app_dir)

    for css_file in root.rglob("*.css"):
        if ".git" in str(css_file):
            continue
        try:
            raw = css_file.read_text(encoding="utf-8", errors="replace")
            # A rule quoted inside `/* ... */` is documentation, not a
            # declaration the browser applies. Measured on 0.14.2: live 1,
            # commented-out also 1. This is the shape that took down every PR
            # in a peer repository when a path quoted in a CSS comment was
            # read as a live reference.
            content = strip_css_comments(raw)
        except OSError:
            continue
        relpath = css_file.relative_to(root)

        # The deprecated --color-* finding is ADVISORY and lives in
        # validate_css_advisory(), not here. See that function for why.

        # Check for !important on protected selectors
        for selector in PROTECTED_SELECTORS:
            pattern = re.escape(selector) + r"[^{]*\{[^}]*!important"
            if re.search(pattern, content, re.DOTALL):
                errors.append(f"{relpath}: must not use !important on '{selector}'")

        # Check for footer hiding
        if re.search(r"footer\s*\{[^}]*display\s*:\s*none", content, re.DOTALL):
            errors.append(f"{relpath}: must not hide the footer")

    return errors


def validate_css_advisory(app_dir: str | Path) -> list[str]:
    """CSS findings that are ADVICE, not failures.

    The deprecated `--color-*` variables still RENDER; using them is drift from
    the workspace spec, not a broken app. This finding's own source comment read
    "Warn about deprecated ..." while the finding went into `errors` like every
    other one — and the only consumer exits 1 on any error, so the comment and
    the behaviour disagreed and the behaviour won.
    """
    warnings = []
    root = Path(app_dir)

    for css_file in root.rglob("*.css"):
        if ".git" in str(css_file):
            continue
        try:
            raw = css_file.read_text(encoding="utf-8", errors="replace")
            # A rule quoted inside `/* ... */` is documentation, not a
            # declaration the browser applies. Measured on 0.14.2: live 1,
            # commented-out also 1. This is the shape that took down every PR
            # in a peer repository when a path quoted in a CSS comment was
            # read as a live reference.
            content = strip_css_comments(raw)
        except OSError:
            continue
        if re.search(r"var\(--color-", content):
            relpath = css_file.relative_to(root)
            warnings.append(
                f"{relpath}: use --workspace-* or --text-* CSS variables "
                f"instead of --color-* (see workspace template spec)"
            )

    return warnings


# EOF
