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

#: `export const MOUNT_META_NAME = "stx-mount";` — read from the shipped source.
_TS_CONSTANT = re.compile(
    r"""export\s+const\s+MOUNT_META_NAME\s*=\s*['"]([^'"]+)['"]"""
)


#: The fallback declaration in embed.py's `except ImportError` branch. Matched
#: from SOURCE because with Django installed the name is re-imported, so the
#: fallback literal is unreachable at runtime and invisible to a comparison.
_PY_FALLBACK_CONSTANT = re.compile(
    r"""^\s+MOUNT_META_NAME\s*=\s*['"]([^'"]+)['"]""", re.MULTILINE
)


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


def _mount_ts() -> Path | None:
    root = _scitex_ui_root()
    if root is None:
        return None
    candidate = root / "static" / "scitex_ui" / "ts" / "_base" / "mount.ts"
    return candidate if candidate.exists() else None


def _ts_marker_name() -> str | None:
    """The marker name as the BROWSER will look for it, from mount.ts."""
    path = _mount_ts()
    if path is None:
        return None
    found = _TS_CONSTANT.search(path.read_text(encoding="utf-8"))
    return found.group(1) if found else None


@pytest.fixture
def ts_marker_name() -> str:
    """The marker name from scitex_ui's shipped TypeScript.

    Skips rather than fails when scitex-ui is absent, so scitex-app keeps its
    one-way independence. The reason names WHAT WENT UNCHECKED, because a skip
    and a pass are indistinguishable in a summary line.
    """
    name = _ts_marker_name()
    if name is None:
        pytest.skip(
            "scitex-ui is not installed, or its wheel no longer ships "
            "static/scitex_ui/ts/_base/mount.ts — the TypeScript half of the "
            "stx-mount contract was NOT checked by this run"
        )
    return name


@pytest.fixture
def ui_marker_name() -> str:
    """The marker name from scitex_ui's Python side."""
    if _scitex_ui_root() is None:
        pytest.skip(
            "scitex-ui is not installed — its Python half of the stx-mount "
            "contract was NOT checked by this run"
        )
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


def test_the_typescript_reader_agrees_with_the_python_emitter(ts_marker_name):
    """The cross-LANGUAGE half, and the one no Python-only check can see."""
    # Arrange
    expected = MOUNT_META_NAME
    # Act
    actual = ts_marker_name
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


# EOF
