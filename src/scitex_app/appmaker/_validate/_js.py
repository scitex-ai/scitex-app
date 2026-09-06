"""Dangerous patterns in an app's JavaScript.

PORTED VERBATIM from `scitex_app.validator.AppValidator.validate_js`, which
works, is covered by tests, and is called by NOTHING. The shipped skill doc
(07_backend-validation.md) told app developers the pipeline included it while
the CLI ran no `.js` file at all — the checks existed, were listed, and never
executed.

The pattern list was ported unchanged and then NARROWED on measurement — see
DANGEROUS_JS_PATTERNS for the numbers and the one false positive that decided
it. The check still ships unarmed.
"""

from __future__ import annotations

from ._comments import strip_js_comments
import re
from pathlib import Path

# NARROWED FROM validator.py's NINE, on measurement rather than on taste.
#
# Four of the original nine — `__import__`, `os.system`, `subprocess`,
# `exec\s*\(` — are the PYTHON forbidden list copy-pasted into a JS scanner. Run
# against the fleet's two available app packages after the port:
#
#     scholar/_django    0 findings
#     writer/_django     1 finding   `exec\s*\(`
#                                    static/writer/js/editor.js:812
#                                    while ((match = re.exec(line)) !== null)
#
# That is a regex iteration loop: correct, ordinary JavaScript. So 100% of the
# findings this rule produced on the real fleet were FALSE, and all of them came
# from a Python pattern that cannot describe a JavaScript hazard. Armed as
# ported, its first act would have been to fail writer's build over a `while`
# loop — which is how a security rule gets switched off and stays off.
#
# The five kept below fired ZERO times across both repos, so narrowing costs no
# true positive that has ever been observed here.
#
# `exec(` IS dangerous in Node (`child_process.exec`), and this pattern cannot
# tell that from `RegExp.exec`. These are browser bundles, so Node is not the
# threat model; if server-side JS ever ships, the rule to add is one that names
# child_process, not one that matches every `.exec(`.
# A TUPLE, NOT A LIST, AND THAT IS THE POINT. This object is imported by
# scitex_app.validator, so a module-level list would be mutable shared state:
# anything that imports it could `.append()` a pattern and change validation for
# every caller in that interpreter — including a test that forgets to undo it.
# A tuple makes that unrepresentable. Rebuilding the module rebuilds the object,
# so nothing is lost. (scitex-writer, 2026-09-06, as a consumer of both names.)
DANGEROUS_JS_PATTERNS = (
    r"\beval\s*\(",
    r"\bFunction\s*\(",
    r"\bdocument\.cookie\b",
    r"\bwindow\.parent\b",
    r"\bwindow\.top\b",
)

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
# THE ONE SKIP LIST FOR THIS FAMILY. scitex_app.validator imports this as
# SKIP_DIRS rather than declaring a second one — it declared its own for months,
# byte-identical and a separate object, which is the state that preceded both
# previous drifts (the JS pattern list, 0.16.2; the manifest key list, 0.18.0).
# Equal today is exactly how those two started.
#
# A FROZENSET, not a set: it is imported by two modules, so a mutable set would
# let any importer .add() or .discard() a directory and change what every caller
# in the interpreter scans. PREFIX_SKIP_DIRS below is already a frozenset; this
# now matches. Both uses are `&` intersection, which is unaffected.
#
# NAME NOTE: `JS_` is too narrow for what this now serves — AppValidator's
# `_should_skip` uses it for the CSS walk as well as the JS one. Renaming an
# exported name is a wider change than this one and is recorded on
# app-appvalidator-css-check-is-a-substring-scan-20260906 rather than done here.
JS_SKIP_DIRS = frozenset(
    {"node_modules", "dist", ".vite", "_docs", "__pycache__", "assets"}
)


def validate_js(app_dir: str | Path) -> list[str]:
    """Check JS/TS source files for dangerous patterns.

    NOT ARMED. `validate()` skips this unless `check_js_safety=True`, exactly as
    the mount-prefix rule shipped: a new scanner is a RECORD until it has been
    run against trees whose correct answer is already known, in both directions.

    Why the rule is worth having: `document.cookie`, `window.parent` and
    `window.top` are cookie-reading and frame-escape primitives, and SciTeX apps
    render inside hub's shell.

    Why it is still unarmed after narrowing: the remaining five fired ZERO times
    across the fleet's two available app packages. Zero findings is consistent
    with "the fleet is clean" AND with "the scan did not run", and only one of
    those is worth arming a gate on. What is missing is a KNOWN-BAD tree — a
    real app carrying a real finding — and the fixtures in the tests are mine,
    so they cannot supply that: a control derived from my own tool agrees with
    my own tool. Arm this when a peer reports a finding I did not construct.
    """
    errors = []
    root = Path(app_dir)

    for ext in JS_SCAN_SUFFIXES:
        for js_file in sorted(root.rglob(ext)):
            if JS_SKIP_DIRS & set(js_file.relative_to(root).parts):
                continue
            try:
                raw = js_file.read_text(errors="replace")
            except OSError:
                continue
            # Comments are not code. Without this the file that DOCUMENTS a
            # removed `eval()` is indistinguishable from the file that still
            # calls it — measured on 0.14.2: live 1, commented-out also 1.
            content = strip_js_comments(raw)

            rel = js_file.relative_to(root)
            for pattern in DANGEROUS_JS_PATTERNS:
                if re.search(pattern, content):
                    errors.append(
                        f"{rel}: contains dangerous pattern matching '{pattern}'"
                    )

    return errors


# EOF
