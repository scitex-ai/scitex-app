"""Shared machinery for the cross-package, cross-language agreement checks.

WHY THIS MODULE EXISTS. There are now two constants that scitex-app declares in
Python and scitex-ui mirrors in TypeScript — the `stx-mount` marker name and the
authorization verdict's `kind` strings — with nothing but a comment connecting
each pair. Both checks need the same three things, and the comment stripper in
particular is LOAD-BEARING rather than incidental:

    strip_ts_comments    a substring detector INVERTS ON DOCUMENTATION, so a
                         commented-out declaration must not satisfy a search
    installed_scitex_ui_root   the optional, one-way dependency
    installed_scitex_app_root  this package, for reading its own source

NAMED `installed_*` DELIBERATELY. The first version called them
`scitex_ui_root`/`scitex_app_root`, which COLLIDED with a pytest fixture of
the same name in the mount check: the fixture shadowed the import, so the
helper call inside it resolved to the fixture function itself. Two tests
errored. Caught by running the pre-refactor file against the same venv as a
control — it passed 9/9, which is what proved the breakage was mine rather
than a change in the installed wheel.

Keeping a second copy of the stripper beside the second check would be the exact
defect these files exist to catch: one decision, two declarations, nothing
enforcing that they agree. Measured 2026-09-03 — `// export const NAME = "old";`
matches a declaration-anchored pattern and yields the stale value, so the
stripper is not a nicety and a divergent copy of it would be a real hole.

NOT A TEST MODULE. The leading underscore keeps pytest from collecting it; it
mirrors the existing `_validate/_helpers.py` convention.
"""

from __future__ import annotations

import re
from pathlib import Path

_TS_LINE_COMMENT = re.compile(r"//.*?$", re.MULTILINE)
_TS_BLOCK_COMMENT = re.compile(r"/\*.*?\*/", re.DOTALL)


def strip_ts_comments(source: str) -> str:
    """Remove // and /* */ comments before searching for a declaration.

    WHY: a substring detector INVERTS ON DOCUMENTATION. Without this, a file
    that had removed the real constant but kept a commented-out one — or merely
    discussed it in a comment — would still satisfy the search, and the file
    that best explains itself looks identical to the file with the defect.

    MEASURED, not assumed: before this, `// export const MOUNT_META_NAME =
    "stx-OLD";` matched and yielded "stx-OLD". scitex-ui hit the same shape in
    their own guard an hour earlier, on a docstring explaining why a helper
    does not exist. They then hit it a THIRD time on 2026-09-03, grepping this
    repo for the kinds check and matching the PROSE in the sibling module's
    docstring that describes it — they read the hit instead of counting it.
    """
    return _TS_BLOCK_COMMENT.sub("", _TS_LINE_COMMENT.sub("", source))


def installed_scitex_app_root() -> Path:
    """This package's directory, for reading its own source."""
    import scitex_app

    return Path(scitex_app.__file__).resolve().parent


def installed_scitex_ui_root() -> Path | None:
    """The installed scitex_ui package, or None when it is not installed.

    scitex-app does NOT depend on scitex-ui and must not: scitex-ui is the
    presentation layer and this SDK's CLI and MCP surfaces stay headless. The
    absence is therefore expected and is the ONLY legitimate skip.
    """
    try:
        import scitex_ui
    except ImportError:
        return None
    return Path(scitex_ui.__file__).resolve().parent


def installed_scitex_ui_version() -> str:
    """The installed scitex-ui version, or a reason it could not be read.

    ALWAYS RETURNS A STRING, never raises and never returns None, because its
    only caller is a FAILURE MESSAGE. A version lookup that explodes while
    building the text explaining a failure replaces a legible red with a
    confusing one.

    WHY A FAILURE MESSAGE NEEDS THIS AT ALL. This check reads the INSTALLED
    scitex-ui, and CI installs it UNPINNED. During a PyPI propagation window a
    leg can therefore resolve a wheel OLDER than the kind under test, and the
    comparison then fails truthfully about the wheel and falsely about the
    contract. Without the version in the text, that red is indistinguishable
    from a genuine divergence — measured by scitex-ui 2026-09-05, whose own
    release had /pypi/<pkg>/json reporting the previous version while
    /pypi/<pkg>/<new>/json already returned 200, and whose matrix legs resolved
    different indexes 0.68 seconds apart.

    THIS IS THE LEGIBLE-RED HALF ONLY. It does not let the MACHINE tell the two
    apart; that needs a three-valued result and is a prerequisite of ARMING
    this leg, tracked separately. Naming the limit because a message that makes
    a human's job easy is otherwise mistaken for a fix.
    """
    from importlib.metadata import PackageNotFoundError, version

    try:
        return version("scitex-ui")
    except PackageNotFoundError:  # pragma: no cover - the skip arm covers it
        return "not installed"
    except Exception as exc:  # pragma: no cover - defensive, see docstring
        return f"unreadable ({type(exc).__name__})"
