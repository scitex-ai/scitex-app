"""Workspace frame rules — what an app's templates and CSS must not do to the shell."""

from __future__ import annotations

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
        content = index_html.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return errors

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
            content = css_file.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        relpath = css_file.relative_to(root)

        # Warn about deprecated --color-* variables
        if re.search(r"var\(--color-", content):
            errors.append(
                f"{relpath}: use --workspace-* or --text-* CSS variables "
                f"instead of --color-* (see workspace template spec)"
            )

        # Check for !important on protected selectors
        for selector in PROTECTED_SELECTORS:
            pattern = re.escape(selector) + r"[^{]*\{[^}]*!important"
            if re.search(pattern, content, re.DOTALL):
                errors.append(f"{relpath}: must not use !important on '{selector}'")

        # Check for footer hiding
        if re.search(r"footer\s*\{[^}]*display\s*:\s*none", content, re.DOTALL):
            errors.append(f"{relpath}: must not hide the footer")

    return errors


# EOF
