"""The `stx-mount` marker name must agree across packages AND across languages.

WHAT THIS GUARDS. The name is a contract: the server emits
`<meta name="stx-mount">` and the client reads it. Both halves hardcode the
string, and they live in different packages and different languages:

    scitex_app/_django.py            MOUNT_META_NAME = "stx-mount"   RENDERS it
    scitex_app/embed.py              MOUNT_META_NAME = "stx-mount"   fallback
    scitex_ui/mount.py               MOUNT_META_NAME = "stx-mount"
    scitex_ui .../ts/_base/mount.ts  export const MOUNT_META_NAME    READS it

Four declarations, one decision, and until this file nothing enforced that they
agree. scitex_ui's own comment says "Must match ``MOUNT_META_NAME`` in
mount.ts" — the honest version, naming the coupling while admitting there is no
mechanism.

WHY A COMMENT IS NOT ENOUGH, concretely. Rename the constant on one side only
and the failure is silent and asymmetric. Server emits the new name, client
reads the old: `querySelector` returns null and the prescribed client code
throws, which is at least loud. The other ordering degrades to a page that
renders perfectly and whose API calls 404 only when mounted under a prefix —
the quiet failure this whole contract exists to prevent.

WHY IT IS SAFE TO READ scitex_ui HERE. scitex-app does NOT depend on scitex-ui
and must not: scitex-ui is the presentation layer, and this SDK's CLI and MCP
surfaces are required to stay headless. These tests SKIP when scitex-ui is
absent, so the dependency is one-way and optional. They run in the CI job that
installs scitex-ui for the reference example.

WHAT THAT COSTS, said plainly: that job is deliberately NOT a required context,
so this is a RECORD rather than a gate — visible on a pull request, blocking
nothing. Promoting it is tracked on
app-arm-the-example-leg-once-it-has-a-track-record. A skipped test and a passing
test look identical in a summary line, which is exactly why the skip reason
below names what was not checked.

THE GENERAL PROBLEM, of which this is instance one: a constant shared between
scitex-app's Python and scitex-ui's TypeScript, with nothing connecting them.
Instance two is the authorization verdict's `kind` strings, which scitex-ui
mirrors as a TypeScript union. Same shape, same fix — this file is the worked
example that one follows.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from scitex_app._django import MOUNT_META_NAME

#: `export const MOUNT_META_NAME = "stx-mount";` — anchored on the DECLARATION,
#: not on the bare string, so prose mentioning the name cannot satisfy it.
_TS_CONSTANT = re.compile(
    r"""export\s+const\s+MOUNT_META_NAME\s*=\s*['"]([^'"]+)['"]"""
)

#: The fallback declaration in embed.py's `except ImportError` branch. Matched
#: from SOURCE because with Django installed the name is re-imported, so the
#: fallback literal is unreachable at runtime and invisible to a comparison.
_PY_FALLBACK_CONSTANT = re.compile(
    r"""^\s+MOUNT_META_NAME\s*=\s*['"]([^'"]+)['"]""", re.MULTILINE
)

_TS_LINE_COMMENT = re.compile(r"//.*?$", re.MULTILINE)
_TS_BLOCK_COMMENT = re.compile(r"/\*.*?\*/", re.DOTALL)

_MOUNT_TS_RELPATH = Path("static") / "scitex_ui" / "ts" / "_base" / "mount.ts"


def _strip_ts_comments(source: str) -> str:
    """Remove // and /* */ comments before searching for a declaration.

    WHY: a substring detector INVERTS ON DOCUMENTATION. Without this, a file
    that had removed the real constant but kept a commented-out one — or merely
    discussed it in a comment — would still satisfy the search, and the file
    that best explains itself looks identical to the file with the defect.

    MEASURED, not assumed: before this, `// export const MOUNT_META_NAME =
    "stx-OLD";` matched and yielded "stx-OLD". scitex-ui hit the same shape in
    their own guard an hour earlier, on a docstring explaining why a helper
    does not exist.
    """
    return _TS_BLOCK_COMMENT.sub("", _TS_LINE_COMMENT.sub("", source))


def _read_ts_constant(source: str) -> str | None:
    """The declared value from TypeScript source, ignoring comments. Pure."""
    found = _TS_CONSTANT.search(_strip_ts_comments(source))
    return found.group(1) if found else None


def _scitex_app_root() -> Path:
    """This package's directory, for reading its own source."""
    import scitex_app

    return Path(scitex_app.__file__).resolve().parent


def _scitex_ui_root() -> Path | None:
    """The installed scitex_ui package, or None when it is not installed."""
    try:
        import scitex_ui
    except ImportError:
        return None
    return Path(scitex_ui.__file__).resolve().parent


@pytest.fixture
def scitex_ui_root() -> Path:
    """scitex-ui's installed root, skipping when it is absent.

    NOT INSTALLED IS THE ONLY LEGITIMATE SKIP. scitex-app does not depend on
    scitex-ui and must not, so its absence is expected and cannot be a failure.
    Everything past this point is a real signal.
    """
    root = _scitex_ui_root()
    if root is None:
        pytest.skip(
            "scitex-ui is not installed — the cross-package half of the "
            "stx-mount contract was NOT checked by this run"
        )
    return root


@pytest.fixture
def mount_ts_source(scitex_ui_root: Path) -> str:
    """The shipped mount.ts, FAILING if scitex-ui is installed without it.

    THE THREE-VALUED POINT, and the defect this fixture was rewritten to fix:
    the first version returned None both when scitex-ui was ABSENT and when it
    was PRESENT BUT NO LONGER SHIPPING THE FILE, so both skipped identically.
    Those are different facts. The second means the wheel changed shape beneath
    a check that depends on it, and a check whose subject has vanished must say
    so rather than quietly not run.

    found-and-agrees / found-and-differs / NOT FOUND — three outcomes, three
    reports. Raised by scitex-ui, who spotted that their newly-merged
    dim/types.ts has shipped in no release yet, so a naive "read and compare"
    would find nothing, have nothing to disagree with, and pass.
    """
    path = scitex_ui_root / _MOUNT_TS_RELPATH
    assert path.exists(), (
        f"scitex-ui is installed but does not ship {_MOUNT_TS_RELPATH} — "
        "this check's subject has moved or been removed. Update the path "
        "rather than deleting the check: a cross-language constant with no "
        "reader-side verification is how the marker silently diverges."
    )
    return path.read_text(encoding="utf-8")


@pytest.fixture
def ui_marker_name(scitex_ui_root: Path) -> str:
    """The marker name from scitex_ui's Python side."""
    from scitex_ui.mount import MOUNT_META_NAME as ui_name

    return ui_name


def test_the_python_marker_name_is_the_contract_value():
    """Calibration. Every comparison below is meaningless if this drifts.

    Asserts the literal rather than comparing two variables, so a rename that
    changed BOTH sides together still fails here and forces a deliberate
    decision — the contract is published in shipped docs and read by apps we
    do not control.
    """
    # Arrange
    # Act
    name = MOUNT_META_NAME
    # Assert
    assert name == "stx-mount"


def test_the_typescript_reader_agrees_with_the_python_emitter(mount_ts_source):
    """The cross-LANGUAGE half, and the one no Python-only check can see."""
    # Arrange
    expected = MOUNT_META_NAME
    # Act
    actual = _read_ts_constant(mount_ts_source)
    # Assert
    assert actual == expected


def test_the_scitex_ui_python_side_agrees_too(ui_marker_name):
    """Their mount.py renders the marker for shell-rendered apps.

    For an app extending scitex_ui's shell — the reference example does — it is
    THIS constant that reaches the browser, not scitex-app's. So it is the one
    whose disagreement would be invisible from inside this repo.
    """
    # Arrange
    expected = MOUNT_META_NAME
    # Act
    actual = ui_marker_name
    # Assert
    assert actual == expected


def test_the_embed_fallback_literal_agrees_with_the_renderer():
    """embed.py declares the name a SECOND time, in its no-Django fallback.

    READ FROM SOURCE, NOT IMPORTED, and that distinction is the whole test.
    `embed` imports the constant from `_django` inside a try, falling back to
    its own literal only when Django is absent. So with Django installed
    `embed.MOUNT_META_NAME` IS `_django.MOUNT_META_NAME` — the same object —
    and comparing them asserts that a thing equals itself.

    I wrote that tautology first. The positive control caught it: renaming the
    Python constant failed three tests and this one PASSED, which is the
    signature of a check that cannot fail. Reading the literal out of the source
    compares two genuinely independent declarations, which is what the fallback
    is.
    """
    # Arrange
    source = (Path(_scitex_app_root()) / "embed.py").read_text(encoding="utf-8")
    # Act
    fallback = _PY_FALLBACK_CONSTANT.search(source)
    # Assert
    assert fallback is not None and fallback.group(1) == MOUNT_META_NAME


# ─── the detector itself, on inputs whose answer is known ──────────────────
#
# `_read_ts_constant` is pure, so these need no scitex-ui, no file, and no
# installed package. A detector that has never returned a known answer is not
# a measurement.


def test_a_real_declaration_is_read():
    """Calibration: the arms below mean nothing if this does not fire."""
    # Arrange
    source = 'export const MOUNT_META_NAME = "stx-mount";'
    # Act
    found = _read_ts_constant(source)
    # Assert
    assert found == "stx-mount"


def test_a_commented_out_declaration_is_not_read():
    """MEASURED DEFECT, fixed: this returned "stx-OLD" before comment-stripping.

    A file that removed the real constant but kept a commented one would have
    satisfied the check with a stale value — the detector inverting on
    documentation.
    """
    # Arrange
    source = '// export const MOUNT_META_NAME = "stx-OLD";'
    # Act
    found = _read_ts_constant(source)
    # Assert
    assert found is None


def test_a_block_commented_declaration_is_not_read():
    # Arrange
    source = '/* export const MOUNT_META_NAME = "stx-OLD"; */'
    # Act
    found = _read_ts_constant(source)
    # Assert
    assert found is None


def test_prose_naming_the_constant_is_not_read():
    """The subtler half: discussion of the name must not count as the name."""
    # Arrange
    source = '// MOUNT_META_NAME is "stx-mount" and must match the Python side\n'
    # Act
    found = _read_ts_constant(source)
    # Assert
    assert found is None


def test_a_real_declaration_beside_a_stale_comment_still_wins():
    """The realistic file: both present, and the CODE is what counts."""
    # Arrange
    source = (
        '// was: export const MOUNT_META_NAME = "stx-OLD";\n'
        'export const MOUNT_META_NAME = "stx-mount";\n'
    )
    # Act
    found = _read_ts_constant(source)
    # Assert
    assert found == "stx-mount"


# EOF
