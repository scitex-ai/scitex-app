#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""The declarative leaf-app scope contract (operator ledger #48, #144-149).

A leaf app declares, in its manifest, whether it is USER-scoped or
PROJECT-scoped. That single declaration drives the ONE rule this contract
enforces: the global Hub header MUST NEVER force a Current-Project selector.

  - user-scoped   -> emits NO project-scope marker; the app renders with no
                     project switcher at all.
  - project-scoped-> emits a project-scope marker the per-app workspace
                     surface (NOT the global header) reads to offer project
                     selection, preserving each app's own active/last project
                     and permissions.

This is the SDK-side contract for the operator's 2026-09-10 ruling (no
project switcher in the global top header; project selection belongs on the
project/workspace surface). The selector UI + its styling live in scitex-ui /
the host surface — this module only DECLARES the scope and emits the marker
that tells that surface "this app is project-scoped". It does not fork any UI
primitive.

The marker is a sibling of the existing ``stx-mount`` meta (MOUNT_META_NAME):
same shape, same injection point, but it names a SCOPE, not a path.
"""

from __future__ import annotations

from typing import Optional

#: The two declared scopes. A CLOSED enum: anything else is a hard manifest
#: error (fail loud, per the consuming-agent rules) rather than a silent guess.
SCOPE_USER = "user"
SCOPE_PROJECT = "project"
VALID_SCOPES = (SCOPE_USER, SCOPE_PROJECT)

#: Default when a manifest omits ``scope``. ``user`` is the safe default: it
#: renders with NO selector, which is the direction the operator's ruling
#: wants. A project-scoped app must opt in explicitly, so an omission never
#: accidentally forces a global project picker.
DEFAULT_SCOPE = SCOPE_USER

#: <meta> name carrying the app's declared scope to the browser. Sibling of
#: MOUNT_META_NAME ("stx-mount"): same injection machinery, different meaning
#: (scope, not mount path).
SCOPE_META_NAME = "stx-app-scope"


def normalize_scope(value: Optional[str]) -> str:
    """Return the canonical scope for a raw manifest value.

    ``None`` / empty -> the safe default (``"user"``). A value already in
    ``VALID_SCOPES`` (case-insensitive) is returned lower-cased. Any other
    value RAISES ``ValueError`` — a typo'd scope must fail loud at
    validation/render, never degrade to a guessed scope.
    """
    if value is None or (isinstance(value, str) and not value.strip()):
        return DEFAULT_SCOPE
    norm = str(value).strip().lower()
    if norm in VALID_SCOPES:
        return norm
    raise ValueError(
        f"manifest 'scope' must be one of {VALID_SCOPES} (got {value!r}). "
        f"'{SCOPE_PROJECT}' opts the app into a per-app project selector; "
        f"'{SCOPE_USER}' (the default) renders with none."
    )


def scope_meta_tag(scope: Optional[str]) -> str:
    """The ``<meta>`` tag for a scope, or ``""`` for the user-scoped default.

    Only a PROJECT-scoped app emits a marker — the marker is precisely what
    tells the workspace surface "offer project selection here". A user-scoped
    app emits nothing, so there is literally no selector affordance to render.
    This is the 'user-scoped apps render without a project switcher' rule made
    structural, not aspirational.
    """
    if normalize_scope(scope) == SCOPE_PROJECT:
        return f'<meta name="{SCOPE_META_NAME}" content="{SCOPE_PROJECT}">'
    return ""


def _inject_scope_meta(html: str, scope: Optional[str]) -> str:
    """Insert ``scope_meta_tag(scope)`` after the ``<head>`` open tag.

    Mirrors ``_inject_mount_meta`` (same placement rules: after the ``<head>``
    open tag, prepended if absent). Returns the html unchanged when the scope
    emits no marker (the user-scoped default), so a user-scoped page is
    byte-identical to the scope-unaware case.
    """
    tag = scope_meta_tag(scope)
    if not tag:
        return html
    from django.utils.html import escape  # noqa: F401  (kept for symmetry)

    import re

    _head_open = re.compile(r"<head(?:\s[^>]*)?>", re.IGNORECASE)
    match = _head_open.search(html)
    if match:
        return html[: match.end()] + tag + html[match.end() :]
    return tag + html


def app_scope_context(request) -> dict:
    """Context processor: expose the mounted app's scope to templates.

    Resolves the mounted ``ScitexAppConfig`` (the one carrying a ``scope``)
    and adds ``app_scope`` (``"user"`` or ``"project"``) to every template.
    A user-scoped / absent app yields ``"user"``. The host surface reads this
    to decide whether to render a project selector — and it is the per-app
    surface that renders one, never the global header.
    """
    try:
        from django.apps import apps

        from ._django import ScitexAppConfig
    except ImportError:
        return {"app_scope": DEFAULT_SCOPE}

    for app_config in apps.get_app_configs():
        if isinstance(app_config, ScitexAppConfig):
            try:
                return {"app_scope": app_config.app_scope}
            except Exception:
                return {"app_scope": DEFAULT_SCOPE}
    return {"app_scope": DEFAULT_SCOPE}
