"""Dangerous patterns in an app's JavaScript.

PORTED VERBATIM from `scitex_app.validator.AppValidator.validate_js`, which
works, is covered by tests, and is called by NOTHING. The shipped skill doc
(07_backend-validation.md) told app developers the pipeline included it while
the CLI ran no `.js` file at all — the checks existed, were listed, and never
executed.

The pattern list is carried over UNCHANGED, deliberately, so this commit is a
move rather than a judgement. Two things about it are already known to be wrong
and are being MEASURED rather than guessed at (see validate_js):
its false-positive behaviour on real built bundles is the whole reason the check
ships unarmed.
"""

from __future__ import annotations

import re
from pathlib import Path

# Verbatim from validator.py. `__import__`, `os.system`, `subprocess` and
# `exec(` are the PYTHON forbidden list, copy-pasted into a JS scanner — and
# `exec(` in particular matches `regex.exec(str)`, which is ordinary correct
# JavaScript. Not narrowed here: narrowing at the same time as moving would make
# it impossible to tell which change caused a difference in findings.
DANGEROUS_JS_PATTERNS = [
    r"\beval\s*\(",
    r"\bFunction\s*\(",
    r"\bdocument\.cookie\b",
    r"\bwindow\.parent\b",
    r"\bwindow\.top\b",
    r"\b__import__\b",
    r"\bos\.system\b",
    r"\bsubprocess\b",
    r"\bexec\s*\(",
]

JS_SCAN_SUFFIXES = ("*.js", "*.ts", "*.tsx", "*.jsx")

# NOTE THE DELIBERATE DISAGREEMENT WITH _prefix.PREFIX_SKIP_DIRS, which does NOT
# skip `dist` or `assets`. The two rules want opposite things from build output:
#
#   prefix safety   MUST read the built bundle — the shipped URL lives there,
#                   and the TS source can disagree with it
#   this rule       MUST NOT — minified vendor code contains `eval(`,
#                   `Function(` and `exec(` as a matter of course, so scanning
#                   dist would report the app for code it did not write
#
# Same repo, same kind of scan, opposite decisions, both intentional.
JS_SKIP_DIRS = {"node_modules", "dist", ".vite", "_docs", "__pycache__", "assets"}


def validate_js(app_dir: str | Path) -> list[str]:
    """Check JS/TS source files for dangerous patterns.

    NOT ARMED. `validate()` skips this unless `check_js_safety=True`, exactly as
    the mount-prefix rule shipped: a new scanner is a RECORD until it has been
    run against trees whose correct answer is already known, in both directions.

    Why that matters more here than usual: `document.cookie`, `window.parent`
    and `window.top` are frame-escape and cookie-reading primitives and SciTeX
    apps render inside hub's shell, so the rule is worth having — but the same
    list contains `exec\\s*\\(`, which every use of `RegExp.prototype.exec`
    matches. Arming it before measuring would fail peer repos on correct code,
    which is how a security rule gets switched off permanently.
    """
    errors = []
    root = Path(app_dir)

    for ext in JS_SCAN_SUFFIXES:
        for js_file in sorted(root.rglob(ext)):
            if JS_SKIP_DIRS & set(js_file.relative_to(root).parts):
                continue
            try:
                content = js_file.read_text(errors="replace")
            except OSError:
                continue

            rel = js_file.relative_to(root)
            for pattern in DANGEROUS_JS_PATTERNS:
                if re.search(pattern, content):
                    errors.append(
                        f"{rel}: contains dangerous pattern matching '{pattern}'"
                    )

    return errors


# EOF
