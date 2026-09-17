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

THE CONJUNCT IS "WHAT THE CORE ACCEPTS", PER FIELD, NOT ONE GRAMMAR FOR ALL
THREE (hub verdict 2026-09-17, PR #198 re-review at bbfbb9a). The core applies
DIFFERENT rules to the three dimensions, so a single strict grammar was itself
a divergence — measured: the core accepted rows whose parent was
``Doc:/parent``/``doc:/../parent``/``:/parent`` while the query rejected them,
i.e. a row the core GRANTED was silently dropped (check=True/query=False).
Each field therefore mirrors the core's OWN rule for that field:
``access_ref`` = canonical ``kind:/...`` with no ``..`` (the core's ``Resource``
path rule), ``access_owner`` = ``user:``/``org:`` with a valid segment (the
core's ``Principal``/``Resource`` owner rule), ``access_parent`` = the core's
``split_resource_ref`` shape only (see ``_PARENT_REF`` — kind case and ``..``
are NOT checked there, because the core does not check them). A diverging rule
is not "extra safety": in one direction it drops rows the core grants, in the
other it admits rows the core would reject, and both break the equivalence this
module exists to provide.

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


def _missing_access(exc: BaseException) -> bool:
    """True only if ``exc`` is the "``scitex_dev.access`` not installed yet" case.

    Hub review item 3 (narrowing), made a pure predicate so it can be tested
    WITHOUT mocking (PA-306 §3): a module absent from the path raises
    ``ModuleNotFoundError`` (a subclass of ``ImportError``) whose ``name`` is
    the dotted path that failed to resolve. Only the two expected forms are
    the missing case. Everything else — a bare ``ImportError`` raised *inside*
    the core, or a ``ModuleNotFoundError`` for an unrelated module — is a real
    failure that must propagate, not be laundered into "the dependency is
    missing" (which would hide a defect and read as a skip).
    """
    return isinstance(exc, ModuleNotFoundError) and getattr(exc, "name", None) in (
        "scitex_dev",
        "scitex_dev.access",
    )


def _load_core() -> ModuleType:
    """Import ``scitex_dev.access`` and separate "not released yet" from a real
    internal failure.

    Uses ``importlib.import_module`` (a call, not a static ``ImportFrom``) so
    the PS-140 symbol gate — which walks ``ast.ImportFrom`` nodes — does NOT
    discover this import. The adapter's core dependency is a true *optional
    runtime* one: it must not appear in the gate's static symbol list, where
    it would fail on any scitex-dev version lacking the ``access`` submodule.
    The exact-core CI job (ci.yml ``access-conformance``) carries the proof.

    The missing-case decision is :func:`_missing_access` (pure, unit-tested);
    this wrapper just applies it to whatever the import raises.
    """
    try:
        return importlib.import_module("scitex_dev.access")
    except ImportError as exc:  # ModuleNotFoundError is a subclass
        if _missing_access(exc):
            raise ScitexDevAccessMissingError() from exc
        raise  # a real import failure — do not masquerade it as "absent"


# The core's kind-name grammar (dotted lowercase) and owner-principal grammar
# (user:/org: with a valid segment, no '..'). Mirrored here so the model can
# reject a malformed row WITHOUT importing the core (keep module load
# dependency-free). Hub review item 2: the core's _require_segment rejects
# '..' anywhere in the id, so _OWNER must too — the previous char-class
# [A-Za-z0-9._@+-]* admitted user:a..b / org:a..b, which the core rejects.
_KIND_NAME = re.compile(r"^[a-z][a-z0-9_]*(\.[a-z][a-z0-9_]*)*$")
_OWNER = re.compile(r"^(user|org):[A-Za-z0-9][A-Za-z0-9._@+-]*$")
_OWNER_TRAVERSAL = re.compile(r"\.\.")
# The ref/parent query predicate, DERIVED from _KIND_NAME (the save grammar's
# kind pattern) so the query and the write path cannot diverge (hub review 3,
# item 1): a row admitted at query time is one the core would accept at
# construction. _KIND_NAME is "<kind>" anchored; here the same kind fragment is
# required to be immediately followed by ":/" — i.e. the path is absolute —
# which is exactly check_ref's "path.startswith('/')" for the field as a whole.
# Traversal ("..") is excluded separately, matching check_ref's ".. in path".
#
# THIS PATTERN IS FOR THE ROW'S OWN IDENTITY (access_ref) ONLY. A PARENT is a
# different grammar: see _PARENT_REF below, which mirrors the core instead of
# the save path, because the core's own parent rule is looser than this one.
_REF_QUERY = re.compile(_KIND_NAME.pattern.rstrip("$") + r":/")

# The PARENT grammar, taken from the CORE ITSELF rather than from this
# module's stricter save grammar. Hub verdict 2026-09-17 (PR #198 re-review at
# bbfbb9a, blocker): "core accepts inherited parents Doc:/parent,
# doc:/../parent, :/parent, adapter query rejects; reproduced
# check=True/query=False" — a silent UNDER-REPORT, which is the one failure a
# filter translation must not have.
#
# MEASURED against the exact core (scitex-dev 72e8891584d8,
# ``scitex_dev.access._types.split_resource_ref`` + ``Resource.__post_init__``):
#
#   'Doc:/parent'       -> accepted   (kind CASE is not checked for a parent)
#   'doc:/../parent'    -> accepted   (a parent is compared by STRING equality
#                                      against the default grants; only a
#                                      resource's OWN path is '..'-checked)
#   ':/parent'          -> accepted   (empty kind is not checked for a parent)
#   'doc:/parent'       -> accepted
#   'doc:relative'      -> REFUSED    (path does not start with '/')
#   'doc:'              -> REFUSED    (no path at all)
#
# So the accept condition is exactly "contains a ':' AND the part after the
# FIRST ':' starts with '/'", which is what this pattern encodes ('::/x' is
# refused because the part after the first ':' is ':/x'). Mirrored rather than
# invented: a row whose parent fails this shape is one the core cannot
# construct a Resource from, so excluding it AGREES with the core; a row whose
# parent passes it is a resource the core decides on, and the adapter
# translates that decision instead of overriding it.
_PARENT_REF = re.compile(r"^[^:]*:/")


def _owner_is_canonical(value: Optional[str]) -> bool:
    """True only for a user:/org: principal with a valid segment and no '..'.

    Mirrors the core ``Principal`` construction for the two owner kinds the
    core allows (agent/anonymous owners are rejected by the core's
    ``Resource`` and therefore by this adapter).
    """
    if not isinstance(value, str) or not _OWNER.match(value):
        return False
    return _OWNER_TRAVERSAL.search(value) is None


def _check_parent(value: Optional[str], field: str) -> None:
    """Fail closed on a parent the core could not put on a ``Resource``.

    The grammar is the CORE's (``split_resource_ref``), measured rather than
    assumed: a parent must contain ``':'`` and the part after the FIRST ``':'``
    must start with ``'/'``. Kind case and traversal are deliberately NOT
    checked here — the core does not check them for a parent, and a rule the
    core does not have is a divergence, not extra safety (hub verdict
    2026-09-17). ``None`` is the top-level case and stays valid.
    """
    if value is None:
        return
    if not isinstance(value, str) or not _PARENT_REF.match(value):
        raise InvalidAccessRowError(
            f"{field} {value!r} is not a ref the access core accepts as a "
            "parent: it must contain ':' with the part after it starting with "
            "'/' (the core's own split_resource_ref rule)"
        )


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
    # The PARENT uses the CORE's grammar, not check_ref's: measured against the
    # exact core, a parent is accepted when it contains ':' and its remainder
    # starts with '/' — kind case and '..' are NOT checked there (see
    # _PARENT_REF). Using the stricter save grammar here was what produced
    # check=True/query=False for 'Doc:/parent', 'doc:/../parent' and ':/parent'
    # (hub verdict 2026-09-17), so save() must accept what the core accepts or
    # the two paths disagree again in the other direction.
    _check_parent(access_parent, "access_parent")


def _canonical_row_q() -> Q:
    """The fail-closed conjunct: a scoped query admits only CANONICAL rows.

    Hub review 3, item 1: the previous version checked owner with a
    case-insensitive prefix (``istartswith``) and never checked ``access_parent``
    at all, so it admitted save-invalid ``user:`` (empty id), ``USER:u1``
    (uppercase — the save grammar's owner prefix is case-sensitive), and a
    malformed ``access_parent`` (``doc:relative``, ``doc:/../x``) through a
    resource/owner grant. The query predicate must be IDENTICAL to the
    save/core grammar for owner AND parent.

    It therefore re-uses the SAME compiled patterns the write path checks
    (``_KIND_NAME``/``_REF_QUERY`` for ref+parent, ``_OWNER`` for owner) so the
    two cannot diverge: a row admitted at query time is one the core would
    accept at construction. SQLite's REGEX (Django 6) makes this portable on
    the in-memory DB the conformance job uses.
    """
    ref_q = Q(access_ref__regex=_REF_QUERY.pattern) & ~Q(access_ref__contains="..")
    owner_q = Q(access_owner__regex=_OWNER.pattern) & ~Q(access_owner__contains="..")
    # access_parent is nullable: it must be either absent OR a ref the CORE
    # accepts as a parent (_PARENT_REF — kind case and '..' are not checked
    # there, because the core does not check them either). Hub verdict
    # 2026-09-17: the previous, stricter parent clause made the query reject
    # parents the core accepts, so a row the core GRANTED was silently dropped
    # (check=True/query=False). The clause now mirrors the core; a parent the
    # core cannot construct a Resource from ('doc:relative', 'doc:') is still
    # excluded, which is agreement rather than strictness.
    parent_q = Q(access_parent__isnull=True) | Q(
        access_parent__regex=_PARENT_REF.pattern
    )
    return ref_q & owner_q & parent_q


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
    "_PARENT_REF",
    "_check_parent",
    "_load_core",
    "_missing_access",
    "to_q",
]

# EOF
