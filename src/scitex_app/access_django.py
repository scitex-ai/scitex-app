#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Django adapter for the ``scitex_dev.access`` primitive.

The core (``scitex_dev.access``) is backend-neutral: ``accessible()`` returns an
``AccessFilter`` — the set of owner / resource / parent refs a principal may
reach — and ``check()`` decides one resource. A backend turns that filter into
its own query so a LIST view admits exactly the rows ``check()`` would admit on
a single row. This module is the Django half of that contract.

The one rule, copied verbatim from ``scitex_dev.access._filter.AccessFilter``:

    a resource matches when
        (public and resource is public)
        or (grant_match(self) and (ceiling is None or grant_match(ceiling)))

    grant_match(f) = owner in f.owners
                     or ref in f.resources
                     or (parent is not None and parent in f.parents)

``to_q`` is the Q-translation of that rule. It is model-agnostic: it names the
four fields an ``AccessScopedModel`` must carry (``access_ref``,
``access_parent``, ``access_owner``, ``access_public``), and Django resolves
them against the concrete model at ``filter`` time. ``testing.assert_equivalent``
proves the translation against the core's own ``check()``.

DEPENDENCY GATE: the adapter imports ``scitex_dev.access``. That package is
merged to scitex-dev develop but not yet on a PyPI release, so in scitex-app's
own CI (which pins an older scitex-dev) the import is guarded and the test is
skipped with a named reason — the module still imports cleanly, it just cannot
prove itself until the release lands. The translation is unchanged either way.
"""

from __future__ import annotations

from types import ModuleType
from typing import TYPE_CHECKING, Any, Optional

from django.db import models
from django.db.models import Q

if TYPE_CHECKING:  # pragma: no cover - typing only; runtime uses the guarded import
    from scitex_dev.access import AccessFilter


class ScitexDevAccessMissingError(RuntimeError):
    """``scitex_dev.access`` is not installed, so the Django adapter cannot
    translate a filter. The fix is ``pip install -U scitex-dev`` once the access
    release ships — until then list scoping is unavailable, not broken."""

    def __init__(self) -> None:
        super().__init__(
            "scitex_app.access_django needs scitex_dev.access, which is not installed. "
            "Run: pip install -U scitex-dev  (the access release is pending)."
        )


def _load_core() -> ModuleType:
    """Import ``scitex_dev.access`` lazily and guard the missing-release case.

    Re-read on every call (a ``find_spec``-style probe, not a cached module) so
    the guard is correct whether the package was installed before or after this
    module imported, and so a test can monkeypatch it in either direction.
    """
    try:
        from scitex_dev import access as _core  # noqa: WPS433 - the guarded import
    except ImportError as exc:  # the not-yet-released case
        raise ScitexDevAccessMissingError() from exc
    return _core


def to_q(access_filter: "AccessFilter") -> Q:
    """Translate an ``AccessFilter`` into the ``Q`` that admits its rows.

    Mirrors ``AccessFilter.matches`` exactly (see the module docstring). The
    ``ceiling`` (an agent's owner-allowance) is AND-ed onto the non-public
    branch only, and never recurses — the core builds it with ``public=False``
    and applies it via ``matches_grants``, which this reproduces.
    """

    def grant_match_q(f: "AccessFilter") -> Q:
        # Mirror ``matches_grants``: OR over owner/resource/parent membership.
        # An empty grant set matches NOTHING, so the empty-OR must be a
        # no-match clause, not ``Q()`` (which Django treats as "match all").
        clauses = []
        if f.owners:
            clauses.append(Q(access_owner__in=f.owners))
        if f.resources:
            clauses.append(Q(access_ref__in=f.resources))
        if f.parents:
            clauses.append(Q(access_parent__in=f.parents))
        if not clauses:
            return Q(pk__in=[])  # matches nothing
        q = clauses[0]
        for c in clauses[1:]:
            q = q | c
        return q

    # ``matches`` checks the kind first; a row is only admitted if its
    # ``access_ref`` (``kind:path``) is of the filter's kind.
    kind_q = Q(access_ref__startswith=f"{access_filter.kind}:")

    non_public = grant_match_q(access_filter)
    if access_filter.ceiling is not None:
        non_public = non_public & grant_match_q(access_filter.ceiling)

    allowed = non_public
    if access_filter.public:
        allowed = allowed | Q(access_public=True)
    return kind_q & allowed


class AccessScopedManager(models.Manager["Any"]):
    """A manager that scopes its queryset to one principal's filter.

    ``scoped(access_filter)`` returns ``self.get_queryset().filter(to_q(...))``
    — the list view's one-line call. The core is what decides; this only
    translates the decision into a query.
    """

    def scoped(self, access_filter: "AccessFilter") -> "models.QuerySet[Any]":
        _load_core()  # fail loud (named) if the dependency is absent
        return self.get_queryset().filter(to_q(access_filter))


class AccessScopedModel(models.Model):
    """Mixin: the four fields ``to_q`` names, plus the scoped manager.

    A concrete model adds its own content columns and inherits
    ``objects.scoped(filter)``. ``access_ref`` is the ``kind:path`` the core
    reasons over; ``access_parent`` is that of its container (``None`` when
    top-level); ``access_owner`` is the owner principal's ``str`` form;
    ``access_public`` is the visibility flag.

    No Hub ORM, no Notification, no raw filesystem path, no guest identity —
    only the value fields the core already defines.
    """

    access_ref = models.CharField(max_length=512)
    access_parent = models.CharField(max_length=512, null=True, blank=True)
    access_owner = models.CharField(max_length=256)
    access_public = models.BooleanField(default=False)

    objects = AccessScopedManager()

    class Meta:
        abstract = True


__all__ = [
    "AccessScopedManager",
    "AccessScopedModel",
    "ScitexDevAccessMissingError",
    "_load_core",
    "to_q",
]

# EOF
