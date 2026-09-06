#!/usr/bin/env python3
"""The shipped example must pass the validator this package ships.

WHY THIS FILE EXISTS. On 2026-09-06 `examples/hello_world_app` — the app
developers copy — failed `scitex-app app validate` on EIGHT counts, including
declaring the `version` key whose own rejection message cites the incident
where every hub app tile displayed a wrong version. The reference
implementation prescribed the defect the validator exists to catch, and nothing
noticed for as long as the example had existed, because nothing ever ran one
against the other.

A gate whose own example cannot pass it is not a gate anyone will run. Written
as a TEST rather than a note in the README because a note is a request and a
test is a barrier (§7: pave the road behind you).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from scitex_app.appmaker import validate_with_warnings

#: The example, from THIS checkout rather than an installed copy — the point is
#: that the file in the repository is the one that stays valid.
EXAMPLE = (
    Path(__file__).resolve().parents[2]
    / "examples"
    / "hello_world_app"
    / "hello_world"
)


def test_the_example_directory_is_where_this_test_thinks_it_is():
    """A path that does not exist yields zero errors from a naive check, which
    reads exactly like a clean bill. Assert the target BEFORE asserting
    anything about it — this repository shipped two peer scans that reported
    "clean" from directories that did not exist (0.14.1), and the whole point
    of a denominator is to make that state distinguishable."""
    # Arrange
    manifest = EXAMPLE / "manifest.json"
    # Act
    found = EXAMPLE.is_dir() and manifest.is_file()
    # Assert
    assert found, f"example app not found at {EXAMPLE}"


def test_the_shipped_example_passes_the_shipped_validator():
    """Zero ERRORS from the same entry point the CLI calls.

    Not `AppValidator`: `scitex-app app validate` is what a developer runs, and
    the two entry points are not interchangeable — they do not even take the
    same directory (this one wants the app dir; AppValidator resolves
    `_django/manifest.json` from a package root).
    """
    # Arrange
    app = EXAMPLE
    # Act
    errors, _ = validate_with_warnings(app)
    # Assert — the message carries the findings, so a failure is actionable
    # without re-running anything by hand.
    assert errors == [], "\n".join(["example app fails its own validator:", *errors])


def test_the_example_declares_no_version_key():
    """Asserted SEPARATELY from the pass above, because this is the one the
    example got wrong in the direction that teaches the defect.

    If a future change relaxes the `version` rule, this test still fails and
    forces the example to be looked at — whereas the blanket "zero errors"
    test would silently start passing with the key back in place.
    """
    # Arrange
    import json

    manifest = json.loads((EXAMPLE / "manifest.json").read_text(encoding="utf-8"))
    # Act
    declared = "version" in manifest
    # Assert
    assert not declared, (
        "manifest.json declares 'version'; the version is derived at runtime "
        "from pip_package via importlib.metadata"
    )


@pytest.mark.parametrize(
    "relpath",
    [
        "LICENSE",
        "README.md",
        ".agents/README.md",
        "templates/hello_world/page.html",
        "templates/hello_world/index_partial.html",
    ],
    ids=["license", "readme", "agents", "standalone", "partial"],
)
def test_the_example_carries_both_template_shapes_and_its_own_paperwork(relpath):
    """Named individually so a deletion says WHICH file went, rather than
    surfacing as one opaque validator error.

    The two templates are the substantive half: `page.html` is the standalone
    shape and owns the document, `index_partial.html` is the workspace shape
    and renders into the shell's container. The example carried only the first,
    so the shape with the harder rules — no <head>, therefore no marker of its
    own, therefore read the shell's — was the one it did not demonstrate.
    """
    # Arrange
    target = EXAMPLE / relpath
    # Act
    present = target.is_file()
    # Assert
    assert present, f"{relpath} missing from the example app"
