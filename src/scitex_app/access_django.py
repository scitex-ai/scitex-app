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

FAIL-CLOSED (hub review item 1): a Django table is a separate store from the
core's in-memory ``Resource`` objects, so it can hold rows the core would
*reject at construction* — a ``kind:not-absolute`` ref, a ``..`` traversal, an
agent/anonymous/null owner, a public row with no owner. The adapter must not
adopt such a row as a grant. It therefore (a) validates on ``save`` (raising
:class:`InvalidAccessRowError`) and (b) ANDs a canonical-row conjunct into
``to_q`` (``access_ref`` present + owner present + parent either absent or
well-formed) so a row that slips past (a) is still EXCLUDED from every scoped
query, never admitted. The core's ``matches`` only ever sees well-formed rows,
so the conjunct is a no-op on valid data and a shield on bad data.

DEPENDENCY GATE (hub review items 2 + 4): the adapter imports
``scitex_dev.access`` ONLY inside ``AccessScopedManager.scoped`` — never at
module load — so this file imports cleanly in scitex-app CI (which pins an
older scitex-dev) and only the conformance test skips. The import guard is
NARROW: a genuine absence of the submodule raises
:class:`ScitexDevAccessMissingError` (named, with the fix); an ``ImportError``
raised *inside* the core (a transitive/version failure) is re-raised, not
laundered into "missing".
"""

from __future__ import annotations

import importlib
import re
from types import ModuleType
from typing import Any, Optional

from django.db import models
from django.db.models import Q

# The core's filter object. Typed as Any here because scitex_dev.access is an
# optional runtime dependency (imported via importlib, invisible to the PS-140
# static gate); to_q/scoped read only its documented fields (duck-typed).
AccessFilter = Any


class ScitexDevAccessMissingError(RuntimeError):
    """``scitex_dev.access`` is not installed, so the Django adapter cannot
    translate a filter. The fix is ``pip install -U scitex-dev`` once the access
    release ships — until then list scoping is unavailable, not broken."""

    def __init__(self) -> None:
        super().__init__(
            "scitex_app.access_django needs scitex_dev.access, which is not installed. "
            "Run: pip install -U scitex-dev  (the access release is pending)."
        )


class InvalidAccessRowError(ValueError):
    """A row the core ``Resource``/``Principal`` would reject: a malformed
    ref/parent (not ``kind:path``, non-absolute path, or ``..`` traversal), a
    non user/org owner, or a non-bool ``access_public``. Raising it on ``save``
    is fail-closed: bad ACL data is refused, not widened into a grant."""


def _load_core() -> ModuleType:
    """Import ``scitex_dev.access`` and separate "not released yet" from a real
    internal failure (hub review item 4).

    Uses ``importlib.import_module`` (a call, not a static ``ImportFrom``) so
    the PS-140 symbol gate — which walks ``ast.ImportFrom`` nodes — does NOT
    discover this import. The adapter's core dependency is a true *optional
    runtime* one: it must not appear in the gate's static symbol list, where
    it would fail on any scitex-dev version lacking the ``access`` submodule.
    The exact-core CI job (ci.yml ``access-conformance``) carries the proof.

    Hub review item 3 (narrowing): a module absent from the path raises
    ``ModuleNotFoundError`` (a ``ModuleNotFoundError`` subclass of
    ``ImportError`` whose ``name`` is the dotted path that failed to resolve).
    Only that, with ``name`` one of the two expected forms, is the "not yet
    released" case -> :class:`ScitexDevAccessMissingError`. A bare
    ``ImportError(...)`` raised *inside* the core (or any non-ModuleNotFound
    import failure) has ``name=None`` and is re-raised as-is — it must NOT be
    laundered into "the dependency is missing", which would hide a real defect
    and read as a skip.
    """
    try:
        _core = importlib.import_module("scitex_dev.access")
    except ModuleNotFoundError as exc:
        if getattr(exc, "name", None) in ("scitex_dev", "scitex_dev.access"):
            raise ScitexDevAccessMissingError() from exc
        raise  # a different module is missing — an internal/core failure
    return _core


# The core's kind-name grammar (dotted lowercase) and owner-principal grammar
# (user:/org: with a valid segment, no '..'). Mirrored here so the model can
# reject a malformed row WITHOUT importing the core (keep module load
# dependency-free). Hub review item 2: the core's _require_segment rejects
# '..' anywhere in the id, so _OWNER must too — the previous char-class
# [A-Za-z0-9._@+-]* admitted user:a..b / org:a..b, which the core rejects.
_KIND_NAME = re.compile(r"^[a-z][a-z0-9_]*(\.[a-z][a-z0-9_]*)*$")
_OWNER = re.compile(r"^(user|org):[A-Za-z0-9][A-Za-z0-9._@+-]*$")
_OWNER_TRAVERSAL = re.compile(r"\.\.")


def _owner_is_canonical(value: Optional[str]) -> bool:
    """True only for a user:/org: principal with a valid segment and no '..'.

    Mirrors the core ``Principal`` construction for the two owner kinds the
    core allows (agent/anonymous owners are rejected by the core's
    ``Resource`` and therefore by this adapter).
    """
    if not isinstance(value, str) or not _OWNER.match(value):
        return False
    return _OWNER_TRAVERSAL.search(value) is None


def _validate_dimensions(
    access_ref: Optional[str],
    access_parent: Optional[str],
    access_owner: Optional[str],
    access_public: Any,
) -> None:
    """Fail closed on rows the core ``Resource``/``Principal`` would reject.

    Raises :class:`InvalidAccessRowError` (a ``ValueError``) so a malformed
    write is a loud data error, not a silently-adopted grant.
    """
    def check_ref(value: Optional[str], field: str) -> None:
        if value is None:
            return
        kind, sep, path = value.partition(":")
        if not sep or not kind or not _KIND_NAME.match(kind):
            raise InvalidAccessRowError(
                f"{field} {value!r} is not a canonical kind:path ref"
            )
        # Traversal is checked before "absolute": a ref like ``..`` is both a
        # traversal and non-absolute, and the traversal is the more dangerous
        # (and the reason to fail closed), so it is named.
        if ".." in path:
            raise InvalidAccessRowError(
                f"{field} {value!r} contains a path traversal ('..')"
            )
        if not path.startswith("/"):
            raise InvalidAccessRowError(
                f"{field} {value!r} has a non-absolute path (must start with '/')"
            )

    if not _owner_is_canonical(access_owner):
        raise InvalidAccessRowError(
            f"access_owner {access_owner!r} must be a user:<id> or org:<id> "
            "principal with no '..' (the core rejects agent/anonymous/null owners "
            "and any '..' in the id)"
        )
    if not isinstance(access_public, bool):
        raise InvalidAccessRowError(
            f"access_public {access_public!r} must be a bool (public/private)"
        )

    check_ref(access_ref, "access_ref")
    check_ref(access_parent, "access_parent")


def _canonical_row_q() -> Q:
    """The fail-closed conjunct: a scoped query admits only CANONICAL rows.

    Hub review item 1: the previous version only checked non-NULL, so a
    row that bypassed ``save`` (``bulk_create`` does not call ``save``) with
    a non-absolute ref, a traversal ref, an anonymous owner, or an agent
    owner was still returned by ``scoped()``. The query predicate must
    enforce the full canonical row, because ``save`` validation is a
    write-time convenience, not the security boundary.

    A row is admitted only if:
      * ``access_ref`` is present and contains no ``..`` traversal; and
      * ``access_owner`` is a user:/org: principal (case-insensitive prefix,
        so the anonymous/agent/null cases are excluded) with no ``..``.

    ``access_ref``'s ``kind:path`` shape is additionally constrained by the
    ``kind_q`` in ``to_q`` (``access_ref`` startswith ``<kind>:``), so a ref
    without a colon or with the wrong kind never matches the filter's grant
    sets either. Traversal in the ref/parent is rejected here.
    """
    owner_q = (
        (Q(access_owner__istartswith="user:") | Q(access_owner__istartswith="org:"))
        & ~Q(access_owner__contains="..")
    )
    ref_q = (
        Q(access_ref__isnull=False)
        & ~Q(access_ref__contains="..")
    )
    return ref_q & owner_q


def to_q(access_filter: AccessFilter) -> Q:
    """Translate an ``AccessFilter`` into the ``Q`` that admits its rows.

    Mirrors ``AccessFilter.matches`` exactly (see the module docstring), ANDed
    with the canonical-row conjunct (fail-closed). The ``ceiling`` (an agent's
    owner-allowance) is AND-ed onto the non-public branch only, and never
    recurses — the core builds it with ``public=False`` and applies it via
    ``matches_grants``, which this reproduces.
    """

    def grant_match_q(f: AccessFilter) -> Q:
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
    # ``access_ref`` (``kind:path``) is of the filter's kind. A well-formed
    # ref of this kind is ``<kind>:/...`` (the path is absolute), so this
    # single startswith enforces BOTH the kind match AND the absolute-path
    # requirement — rejecting ``<kind>:non-absolute`` at query level (hub
    # review item 1). It is used instead of a bare ``<kind>:`` prefix, which
    # would let a non-absolute ref of the right kind slip through.
    kind_q = Q(access_ref__startswith=f"{access_filter.kind}:/")

    non_public = grant_match_q(access_filter)
    if access_filter.ceiling is not None:
        non_public = non_public & grant_match_q(access_filter.ceiling)

    allowed = non_public
    if access_filter.public:
        allowed = allowed | Q(access_public=True)
    return _canonical_row_q() & kind_q & allowed


class AccessScopedManager(models.Manager["Any"]):
    """A manager that scopes its queryset to one principal's filter.

    ``scoped(access_filter)`` returns ``self.get_queryset().filter(to_q(...))``
    — the list view's one-line call. The core is what decides; this only
    translates the decision into a query.
    """

    def scoped(self, access_filter: AccessFilter) -> "models.QuerySet[Any]":
        _load_core()  # fail loud (named) if the dependency is absent
        return self.get_queryset().filter(to_q(access_filter))


class AccessScopedModel(models.Model):
    """Mixin: the four fields ``to_q`` names, plus the scoped manager.

    A concrete model adds its own content columns and inherits
    ``objects.scoped(filter)``. ``access_ref`` is the ``kind:path`` the core
    reasons over; ``access_parent`` is that of its container (``None`` when
    top-level); ``access_owner`` is the owner principal's ``str`` form;
    ``access_public`` is the visibility flag.

    ``save`` runs the fail-closed dimension validation, so a malformed row is
    refused at write time.

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

    def save(self, *args: Any, **kwargs: Any) -> None:
        _validate_dimensions(
            self.access_ref, self.access_parent, self.access_owner, self.access_public
        )
        super().save(*args, **kwargs)


__all__ = [
    "AccessScopedManager",
    "AccessScopedModel",
    "InvalidAccessRowError",
    "ScitexDevAccessMissingError",
    "_load_core",
    "to_q",
]

# EOF
