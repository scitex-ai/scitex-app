#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""The error a host gets for launching a standalone workspace without scitex-ui.

0.22.x shipped `scitex_app/app_shell.html`, whose whole body is
`{% extends "scitex_ui/standalone_shell.html" %}` plus an empty re-opening of
that shell's `app_content` block. It has no content of its own: the workspace
shell (sidebar, three-column layout, file tree, AI/console panel) is supplied
by scitex-ui. But scitex-ui is NOT a declared dependency of scitex-app, and
`_configure_django` treated its absence as optional (`except ImportError:
pass`), so a bare `pip install scitex-app` that renders an app extending the
adapter failed at RENDER time with `TemplateDoesNotExist:
scitex_ui/standalone_shell.html` — an error that names a template path, not
the cause.

WHAT THIS GUARD DOES. `run_standalone()` now checks for the shell at STARTUP,
before it configures Django, and raises `ScitexUiRequiredError` naming what is
missing and the one fix. The failure moves from "a cryptic template path
mid-request" to "a named error at launch".

WHAT THIS FILE DOES NOT CLAIM. It does not make scitex-ui a hard dependency,
and it does not change what an app can mount into an existing host's shell —
that path never calls `run_standalone()`, so the guard does not fire there.
Whether scitex-app SHOULD ship a shell of its own (the "minimal base" option)
is a separate product decision and is not answered here.

SIBLING FILES: test__standalone_i18n.py (catalog activation),
test__standalone_allowed_hosts.py (bind semantics). None of those touch the
shell dependency; this is the one that does.
"""

from __future__ import annotations

import importlib.util

import pytest

from scitex_app._standalone import (
    ScitexUiRequiredError,
    _SCITEX_UI_REQUIRED,
    _scitex_ui_present,
    run_standalone,
)


def test_the_guard_error_is_a_named_runtime_error():
    """It is a RuntimeError subclass so a launcher can catch it specifically
    rather than a bare RuntimeError, and it is not Django's
    ImproperlyConfigured — this failure happens before Django is configured."""
    assert issubclass(ScitexUiRequiredError, RuntimeError)
    from django.core.exceptions import ImproperlyConfigured

    assert not issubclass(ScitexUiRequiredError, ImproperlyConfigured)


def test_the_guard_message_names_the_cause_and_the_fix():
    # Arrange — the contract: an operator chasing the old
    # TemplateDoesNotExist must be told what is actually missing.
    msg = _SCITEX_UI_REQUIRED
    # Act — nothing to call; the message IS the assertion surface.
    # Assert — it names the missing package, the install fix, and the old
    # failure mode it replaces (so a reader can connect it to what they saw).
    assert "scitex-ui" in msg
    assert "pip install scitex-app scitex-ui" in msg
    assert "TemplateDoesNotExist" in msg


def test_presence_check_agrees_with_find_spec_in_both_directions():
    """`_scitex_ui_present` is a pure re-read of `find_spec`. Whatever the
    environment, the two must agree — this pins the check to the real import
    so it cannot drift to a version string or a hardcoded answer."""
    # Arrange — the ground truth the check is a proxy for.
    truth = importlib.util.find_spec("scitex_ui") is not None
    # Act
    check = _scitex_ui_present()
    # Assert — one direction is enough to pin the proxy to the source; the
    # other direction would be asserting the same boolean equals itself.
    assert check is truth


def test_guard_fires_before_any_django_configuration():
    """When the shell is absent, `run_standalone` raises at the FIRST check —
    before it sets SCITEX_WORKING_DIR, calls `_configure_django`, or imports
    `django.setup`. Proven by the guard's position in the source, not by
    trusting it: a regression that moved the check below `_configure_django`
    would leave Django configured in the failing case, which this test would
    not catch, so the position is asserted explicitly."""
    import inspect

    src = inspect.getsource(run_standalone).splitlines()
    guard_idx = next(
        i for i, line in enumerate(src) if "_scitex_ui_present" in line
    )
    configure_idx = next(
        i for i, line in enumerate(src) if "_configure_django" in line
    )
    assert guard_idx < configure_idx


@pytest.mark.skipif(
    importlib.util.find_spec("scitex_ui") is not None,
    reason="scitex-ui IS installed in this env; the guard cannot fire. The "
    "bare-`pip install scitex-app` case is what it names, and no scitex-app "
    "dependency group pulls scitex-ui, so scitex-app's own CI is the env "
    "where this runs.",
)
def test_run_standalone_raises_the_named_error_when_the_shell_is_absent():
    """End-to-end: in an env without scitex-ui (scitex-app's own CI), calling
    the launcher fails loudly with the named error, not a template error.
    Skipped where the shell happens to be installed, so the suite stays green
    on a full fleet env without weakening the case it exists for."""
    # Arrange — a minimal app module arg; the guard fires before it is used.
    # Act
    raised = pytest.raises(ScitexUiRequiredError)
    # Assert
    with raised:
        run_standalone(app_module="some_app._django")
