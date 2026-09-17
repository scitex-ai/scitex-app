#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""`to_q` admits exactly the rows the core's `check()` allows.

The conformance proof the ADR commits to: a Django ``Q`` translation of
``AccessFilter`` is only as good as its agreement with ``check()`` on a single
row. ``scitex_dev.access.testing.assert_equivalent`` runs the core's own
``check()`` over every (principal, action, resource) in a battery of random
fixtures and demands the selector return exactly the allowed refs. Here the
selector is a real in-memory SQLite queryset filtered by
``_ScopedRow.objects.scoped(...)`` — i.e. the actual ``to_q``.

DEPENDENCY GATE: importing ``scitex_dev.access.testing`` is guarded. In
scitex-app's own CI (which pins an older scitex-dev) the proof cannot run and
is skipped with a named reason; ``access_django`` itself imports cleanly
(it does not touch ``scitex_dev`` at module load, only inside
``AccessScopedManager.scoped``), so this test's collection never fails there.
When the access release lands, the proof runs and is the merge gate.
"""

from __future__ import annotations

import django
import pytest
from django.conf import settings
from django.db import connection, models

if not settings.configured:
    # In-memory SQLite so the Q is exercised against a real table, not a mock.
    settings.configure(
        DEFAULT_CHARSET="utf-8",
        ALLOWED_HOSTS=["*"],
        DATABASES={"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": ":memory:"}},
        INSTALLED_APPS=["django.contrib.contenttypes"],
    )
    django.setup()

# Safe at import time: access_django only imports scitex_dev inside
# AccessScopedManager.scoped, never at module load.
from scitex_app import access_django as _ad  # noqa: E402


class _ScopedRow(models.Model):
    """A concrete ``AccessScopedModel`` standing in for any app's content row.

    ``objects = _ad.AccessScopedManager()`` is bound to this model by Django's
    model metaclass, so ``_ScopedRow.objects.scoped(filter)`` is the real,
    production code path (not a re-bound instance).
    """

    access_ref = models.CharField(max_length=512)
    access_parent = models.CharField(max_length=512, null=True, blank=True)
    access_owner = models.CharField(max_length=256)
    access_public = models.BooleanField(default=False)

    objects = _ad.AccessScopedManager()

    class Meta:
        app_label = "contenttypes"
        db_table = "access_django_scoped_row"


@pytest.fixture(scope="module")
def _testing():
    """Import the core's conformance runner once; skip the module if absent."""
    try:
        from scitex_dev import access as _core
        from scitex_dev.access import testing as _testing
    except ImportError:
        pytest.skip(
            "scitex_dev.access not installed — the conformance proof cannot run "
            "until the access release ships (pip install -U scitex-dev)."
        )
    return _core, _testing


def _ensure_table() -> None:
    if "access_django_scoped_row" not in connection.introspection.table_names():
        with connection.schema_editor() as se:
            se.create_model(_ScopedRow)


def _select_with_django(access_filter, fixture):
    """The selector the core's assert_equivalent feeds ``check()`` against."""
    _ensure_table()
    _ScopedRow.objects.all().delete()
    _ScopedRow.objects.bulk_create(
        _ScopedRow(
            access_ref=r.ref,
            access_parent=r.parent,
            access_owner=str(r.owner),
            access_public=r.is_public,
        )
        for r in fixture.resources
    )
    return {row.access_ref for row in _ScopedRow.objects.scoped(access_filter)}


def test_django_to_q_matches_check(_db, _testing):
    """THE proof: my Django translation agrees with the core's check().

    assert_equivalent raises AssertionError on any mismatch; returning None
    means every (principal, action, resource) in 40 random fixtures was
    decided identically by check() and by the Django queryset.

    Routes through _db (hub review 3, item 2): in the full tests/scitex_app
    run a sibling configures Django with DATABASES={} -> dummy, so this skips
    there; in the isolated conformance job it runs non-skipped.
    """
    # Arrange
    _core, _testing = _testing
    # Act
    result = _testing.assert_equivalent(_select_with_django, seeds=range(40))
    # Assert
    assert result is None


def test_public_flag_is_true_for_read_actions(_testing):
    """The core sets ``public=True`` only when the required role is read."""
    # Arrange
    _core, _testing = _testing
    fixture = _testing.random_fixture(0)
    doc_kind = fixture.kinds["conformance.doc"]
    # Act
    f_view = _core.accessible(
        _core.Principal.parse("user:u0"), "view", doc_kind.name,
        grants=fixture.grants, memberships=fixture.memberships, kinds=fixture.kinds,
    )
    # Assert
    assert f_view.public is True


def test_public_flag_is_false_for_write_actions(_testing):
    """A write/admin action never admits public rows without a grant."""
    # Arrange
    _core, _testing = _testing
    fixture = _testing.random_fixture(0)
    doc_kind = fixture.kinds["conformance.doc"]
    # Act
    f_share = _core.accessible(
        _core.Principal.parse("user:u0"), "share", doc_kind.name,
        grants=fixture.grants, memberships=fixture.memberships, kinds=fixture.kinds,
    )
    # Assert
    assert f_share.public is False


# --------------------------------------------------------------------------
# FAIL-CLOSED (hub review item 1): rows the core Resource/Principal would
# reject must be refused on write AND excluded from every scoped query.
# These are deterministic SQLite cases, independent of the conformance battery.
# --------------------------------------------------------------------------


class _FailClosedRow(_ad.AccessScopedModel):
    """A concrete model carrying the mixin's save() validation."""

    class Meta:
        app_label = "contenttypes"
        db_table = "access_django_fail_closed_row"


@pytest.fixture()
def _db():
    """THE single guarded DB fixture. Every database-backed test in this module
    requests it, so a process with no usable default database (the full
    tests/scitex_app run, where a sibling configures Django with DATABASES={}
    and Django substitutes the DUMMY backend) SKIPS those cases cleanly instead
    of ERRORING on the dead connection. In the isolated conformance job
    (ci.yml access-conformance) the module-top :memory: setup provides a real
    default, so the cases run non-skipped.

    Mirrors the repo's _chat guard convention: 'no database' is either no
    ENGINE at all or the DUMMY sentinel — testing ``not settings.DATABASES``
    would miss the dummy case and crash instead of skip.
    """
    default = (getattr(settings, "DATABASES", None) or {}).get("default") or {}
    engine = default.get("ENGINE") or ""
    if not engine or engine.endswith(".dummy"):
        pytest.skip(
            "no usable default database in this process (the full-suite run "
            "configures DATABASES={} -> dummy). The conformance job runs these "
            "cases non-skipped against a real :memory: DB."
        )
    try:
        for model in (_ScopedRow, _FailClosedRow, _NullableOwnerRow):
            if model._meta.db_table not in connection.introspection.table_names():
                with connection.schema_editor() as se:
                    se.create_model(model)
    except Exception as exc:
        pytest.skip(
            f"DB not usable in this process ({type(exc).__name__}) — the conformance job is the authoritative home for this case"
        )
    yield _ScopedRow
    try:
        _ScopedRow.objects.all().delete()
        _FailClosedRow.objects.all().delete()
        _NullableOwnerRow.objects.all().delete()
    except Exception:
        pass


def test_save_refuses_non_absolute_ref():
    """A non-absolute ref is refused (the core Resource rejects it too).
    Validation raises before any DB access, so no table is required."""
    # Arrange
    row = _FailClosedRow(access_ref="doc:not-absolute", access_owner="user:u0")
    # Act
    error = None
    try:
        row.save()
    except _ad.InvalidAccessRowError as exc:
        error = exc
    # Assert
    assert error is not None and "non-absolute" in str(error)


def test_save_refuses_traversal_ref():
    """A ``..`` traversal in the ref is refused (fail closed, no path escape)."""
    # Arrange
    row = _FailClosedRow(access_ref="doc:../x", access_owner="user:u0")
    # Act
    error = None
    try:
        row.save()
    except _ad.InvalidAccessRowError as exc:
        error = exc
    # Assert
    assert error is not None and "traversal" in str(error)


def test_save_refuses_non_canonical_kind():
    """A non-dotted-lowercase kind (``Doc``) is refused."""
    # Arrange
    row = _FailClosedRow(access_ref="Doc:/x", access_owner="user:u0")
    # Act
    error = None
    try:
        row.save()
    except _ad.InvalidAccessRowError as exc:
        error = exc
    # Assert
    assert error is not None and "canonical" in str(error)


def test_save_refuses_agent_owner():
    """The core requires an owner to be a user or org, never an agent."""
    # Arrange
    row = _FailClosedRow(access_ref="doc:/x", access_owner="agent:u0/a0")
    # Act
    error = None
    try:
        row.save()
    except _ad.InvalidAccessRowError as exc:
        error = exc
    # Assert
    assert error is not None and "user:<id> or org:<id>" in str(error)


def test_save_refuses_anonymous_owner():
    """An anonymous owner is refused (the core rejects it as an owner)."""
    # Arrange
    row = _FailClosedRow(access_ref="doc:/x", access_owner="anonymous")
    # Act
    error = None
    try:
        row.save()
    except _ad.InvalidAccessRowError as exc:
        error = exc
    # Assert
    assert error is not None and "user:<id> or org:<id>" in str(error)


def test_save_refuses_non_bool_public():
    """A non-bool access_public is refused (visibility is public/private only)."""
    # Arrange
    row = _FailClosedRow(access_ref="doc:/x", access_owner="user:u0", access_public="yes")
    # Act
    error = None
    try:
        row.save()
    except _ad.InvalidAccessRowError as exc:
        error = exc
    # Assert
    assert error is not None and "bool" in str(error)


def test_save_accepts_canonical_row(_db):
    # Arrange
    good = _FailClosedRow(access_ref="doc:/x", access_owner="user:u0", access_public=False)
    # Act
    good.save()
    # Assert
    assert good.pk is not None


class _NullableOwnerRow(_ad.AccessScopedModel):
    """A model whose owner column is nullable, so a legacy null-owner row can
    exist at the DB layer — exactly the row the canonical conjunct must exclude
    at query time even though it bypassed save() validation."""

    access_owner = models.CharField(max_length=256, null=True, blank=True)

    class Meta:
        app_label = "contenttypes"
        db_table = "access_django_nullowner_row"


def test_scoped_query_excludes_null_owner_row(_db, _testing):
    """Even a null-owner row that bypassed save() is excluded at query time
    (the canonical conjunct in to_q), so bad data fails closed, not wide.

    Routes through _db (hub review 3, item 2): skips in the full run (dummy
    DB), runs non-skipped in the conformance job.
    """
    # Arrange
    _core, _testing = _testing
    _NullableOwnerRow.objects.all().delete()
    # A good row (owner present) and a bad row (owner NULL), inserted at the DB
    # layer so the bad row is not caught by save() validation.
    _NullableOwnerRow.objects.create(access_ref="doc:/good", access_owner="user:u1")
    connection.cursor().execute(
        "INSERT INTO access_django_nullowner_row"
        "(access_ref, access_parent, access_owner, access_public) VALUES ('doc:/bad', NULL, NULL, 0)"
    )
    f = _core.AccessFilter(
        kind="doc", action="view", required_role="read",
        owners=frozenset(["user:u1"]), resources=frozenset(),
        parents=frozenset(), public=False, ceiling=None,
    )
    # Act
    got = {r.access_ref for r in _NullableOwnerRow.objects.scoped(f)}
    # Assert
    assert got == {"doc:/good"}


# --------------------------------------------------------------------------
# HUB REVIEW DIFFERENTIALS (m_51e5890c6891): the query/DB predicate must
# enforce the FULL canonical row, because bulk_create bypasses save(). These
# insert bad rows at the DB layer and assert scoped() EXCLUDES them, then
# assert the owner grammar matches the core (no '..' divergence).
# --------------------------------------------------------------------------


def _raw_insert(model, ref, owner, public=0, parent=None):
    """Bypass save() validation: insert directly at the DB layer, the way
    bulk_create or a legacy row would. This is the fail-closed threat model:
    the query predicate must exclude the row, not save()."""
    parent_sql = "NULL" if parent is None else f"'{parent}'"
    connection.cursor().execute(
        f"INSERT INTO {model._meta.db_table} "
        f"(access_ref, access_parent, access_owner, access_public) "
        f"VALUES ('{ref}', {parent_sql}, '{owner}', {int(public)})"
    )


def _make_filter(owners=None, resources=None, parents=None, public=False):
    """A core AccessFilter with only the grant dimensions the test needs."""
    from scitex_dev import access as _core
    return _core.AccessFilter(
        kind="doc", action="view", required_role="read",
        owners=frozenset(owners or ()), resources=frozenset(resources or ()),
        parents=frozenset(parents or ()), public=public, ceiling=None,
    )


def test_scoped_excludes_bulk_bypassed_bad_rows(_db, _testing):
    """Hub review 3, item 1: bulk_create bypasses save(); scoped() must still
    exclude save-invalid rows at QUERY level.

    The grant is a RESOURCE grant (the row's ref is in filter.resources), NOT
    an owner grant — so the canonical owner check is NOT masked by the grant
    and is what actually excludes the bad-owner rows. A good row (valid ref +
    valid owner) is admitted; each bad class is excluded.
    """
    # Arrange
    _core, _testing = _testing
    _NullableOwnerRow.objects.all().delete()
    good = "doc:/good"
    _raw_insert(_NullableOwnerRow, good, "user:u1")
    # (ref, owner) bad rows — ref is valid & granted; owner is save-invalid.
    bad = {
        "doc:/e": "user:",        # empty owner id
        "doc:/u": "USER:u1",      # uppercase owner (save grammar is case-sensitive)
        "doc:/a": "agent:u1/a0",  # agent owner
        "doc:/n": "anonymous",    # anonymous owner
    }
    for ref, owner in bad.items():
        _raw_insert(_NullableOwnerRow, ref, owner)
    f = _make_filter(resources=[good] + list(bad.keys()))
    # Act
    got = {r.access_ref for r in _NullableOwnerRow.objects.scoped(f)}
    # Assert
    assert got == {good}


def test_scoped_excludes_null_owner_via_public_grant(_db, _testing):
    """Hub review 3, item 1: a public read grant admits public rows; a NULL
    owner that bypassed save() must still be excluded by the canonical
    conjunct (public=True does not imply a valid owner)."""
    # Arrange
    _core, _testing = _testing
    _NullableOwnerRow.objects.all().delete()
    _raw_insert(_NullableOwnerRow, "doc:/pub", "user:u1", public=1)
    _raw_insert(_NullableOwnerRow, "doc:/pubnull", "x", public=1)
    connection.cursor().execute(
        "INSERT INTO access_django_nullowner_row"
        "(access_ref, access_parent, access_owner, access_public) VALUES ('doc:/null', NULL, NULL, 1)"
    )
    f = _make_filter(public=True)  # read -> public rows, no explicit grants
    # Act
    got = {r.access_ref for r in _NullableOwnerRow.objects.scoped(f)}
    # Assert
    assert got == {"doc:/pub"}


def test_scoped_admits_a_core_constructible_parent_when_the_core_grants(_db, _testing):
    """Hub verdict 2026-09-17 (PR #198 re-review, blocker): `doc:/../x` as a
    PARENT is constructible in the core (`split_resource_ref` is shape-only;
    only a resource's OWN path is '..'-checked), so a row the core grants must
    not be dropped by the query. This supersedes the earlier, stricter parent
    clause, which is what produced check=True/query=False."""
    # Arrange
    _core, _testing = _testing
    _NullableOwnerRow.objects.all().delete()
    ref = "doc:/trav"
    _raw_insert(_NullableOwnerRow, ref, "user:u1", parent="doc:/../x")
    f = _make_filter(resources=[ref])
    # Act
    got = {r.access_ref for r in _NullableOwnerRow.objects.scoped(f)}
    # Assert — admitted, because the core admits it (ref + owner canonical).
    assert got == {ref}


def test_scoped_excludes_a_parent_the_core_cannot_construct(_db, _testing):
    """The other direction of the same rule: `doc:relative` is NOT a ref the
    core can construct a Resource from, so excluding it AGREES with the core
    (there is no resource for check() to grant)."""
    # Arrange
    _core, _testing = _testing
    _NullableOwnerRow.objects.all().delete()
    good, bad = "doc:/child", "doc:/rel"
    _raw_insert(_NullableOwnerRow, good, "user:u1", parent="doc:/parent")
    _raw_insert(_NullableOwnerRow, bad, "user:u1", parent="doc:relative")
    f = _make_filter(resources=[good, bad])
    # Act
    got = {r.access_ref for r in _NullableOwnerRow.objects.scoped(f)}
    # Assert
    assert got == {good}


# --------------------------------------------------------------------------
# HUB VERDICT 2026-09-17 (PR #198 re-review at bbfbb9a): `filter.parents`
# DIFFERENTIALS. For each parent form the hub named — plus the canonical
# control — the core's own per-row decision (`AccessFilter.matches` on a real
# Resource built from the row) and the adapter's query must be EQUAL. A
# divergence in either direction is the blocker: check=True/query=False drops
# a row the core grants (what was measured), and check=False/query=True would
# admit one the core denies.
# --------------------------------------------------------------------------

#: (label, parent) pairs: the three forms the core ACCEPTS and the adapter used
#: to reject, plus the canonical control.
_PARENT_FORMS = (
    ("uppercase-kind", "Doc:/parent"),
    ("traversal", "doc:/../parent"),
    ("empty-kind", ":/parent"),
    ("canonical", "doc:/parent"),
)


@pytest.mark.parametrize("label,parent", _PARENT_FORMS)
def test_parent_form_differential_check_equals_query(label, parent, _db, _testing):
    """check() and to_q() must agree for every parent form the core accepts."""
    # Arrange
    _core, _testing = _testing
    _NullableOwnerRow.objects.all().delete()
    ref = "doc:/child"
    _raw_insert(_NullableOwnerRow, ref, "user:u1", parent=parent)
    row = _NullableOwnerRow.objects.first()
    f = _make_filter(parents=[parent])
    resource = _core.Resource(
        kind="doc",
        path="/child",
        owner=_core.Principal("user", "u1"),
        parent=parent,
    )
    # Act
    check = f.matches(resource)
    query = {r.access_ref for r in _NullableOwnerRow.objects.scoped(f)} == {ref}
    # Assert — equal in BOTH directions for this form.
    assert check is query


@pytest.mark.parametrize("label,parent", _PARENT_FORMS)
def test_parent_form_is_admitted_by_the_query(label, parent, _db, _testing):
    """The measured blocker itself: each form must actually be RETURNED (the
    core grants it), not merely agree with a False check()."""
    # Arrange
    _core, _testing = _testing
    _NullableOwnerRow.objects.all().delete()
    ref = "doc:/child"
    _raw_insert(_NullableOwnerRow, ref, "user:u1", parent=parent)
    f = _make_filter(parents=[parent])
    # Act
    got = {r.access_ref for r in _NullableOwnerRow.objects.scoped(f)}
    # Assert
    assert got == {ref}


def test_a_parent_the_core_denies_is_not_admitted_by_the_query(_db, _testing):
    """Control in the denying direction: a parent NOT in the filter is denied
    by check() and must not be returned by the query either."""
    # Arrange
    _core, _testing = _testing
    _NullableOwnerRow.objects.all().delete()
    ref = "doc:/child"
    _raw_insert(_NullableOwnerRow, ref, "user:u1", parent="doc:/other")
    row = _NullableOwnerRow.objects.first()
    f = _make_filter(parents=["doc:/parent"])
    resource = _core.Resource(
        kind="doc", path="/child", owner=_core.Principal("user", "u1"), parent="doc:/other"
    )
    # Act
    check = f.matches(resource)
    query = {r.access_ref for r in _NullableOwnerRow.objects.scoped(f)} == {ref}
    # Assert
    assert (check, query) == (False, False)


def test_save_accepts_the_core_parent_forms(_db, _testing):
    """save() must accept what the core accepts, or the write path becomes the
    divergent side (the same class of bug, mirrored)."""
    # Arrange
    _NullableOwnerRow.objects.all().delete()
    parents = [parent for _label, parent in _PARENT_FORMS]
    # Act
    errors = []
    for parent in parents:
        row = _NullableOwnerRow(access_ref="doc:/child", access_parent=parent, access_owner="user:u1")
        try:
            row.save()
        except _ad.InvalidAccessRowError as exc:
            errors.append((parent, exc))
    # Assert — none of the core's forms is refused at write time.
    assert errors == []


def test_save_refuses_a_parent_the_core_cannot_construct():
    """`doc:relative` has no leading '/', so the core refuses it as a parent
    and so must save()."""
    # Arrange
    row = _NullableOwnerRow(access_ref="doc:/child", access_parent="doc:relative", access_owner="user:u1")
    # Act
    error = None
    try:
        row.save()
    except _ad.InvalidAccessRowError as exc:
        error = exc
    # Assert
    assert error is not None


def test_the_parent_predicate_agrees_with_the_core_own_splitter(_testing):
    """The strongest form of the alignment: the adapter's predicate is pinned
    to the CORE'S OWN function rather than to a re-derived grammar. Runs in the
    conformance job (and any env with the core installed); skipped otherwise,
    with the reason naming what was not checked."""
    # Arrange
    _core, _testing = _testing
    from scitex_dev.access._types import split_resource_ref

    candidates = [
        "doc:/parent",
        "Doc:/parent",
        "doc:/../parent",
        ":/parent",
        "::/x",
        "doc:relative",
        "doc:",
        "",
        "/parent",
        "doc:/a/b",
    ]
    # Act
    disagreements = []
    for candidate in candidates:
        try:
            split_resource_ref(candidate)
            core_accepts = True
        except Exception:
            core_accepts = False
        adapter_accepts = bool(_ad._PARENT_REF.match(candidate))
        if core_accepts is not adapter_accepts:
            disagreements.append((candidate, core_accepts, adapter_accepts))
    # Assert — no candidate where the two grammars disagree.
    assert disagreements == []



def test_owner_traversal_refused_user():
    """Hub item 2: the core rejects '..' in a user principal id; the owner
    grammar must agree (user:a..b is not canonical)."""
    # Arrange
    row = _FailClosedRow(access_ref="doc:/x", access_owner="user:a..b")
    # Act
    error = None
    try:
        row.save()
    except _ad.InvalidAccessRowError as exc:
        error = exc
    # Assert
    assert error is not None, "user:a..b should be refused (core rejects '..')"


def test_owner_traversal_refused_org():
    """Hub item 2 (org form): org:a..b is refused, matching the core."""
    # Arrange
    row = _FailClosedRow(access_ref="doc:/x", access_owner="org:a..b")
    # Act
    error = None
    try:
        row.save()
    except _ad.InvalidAccessRowError as exc:
        error = exc
    # Assert
    assert error is not None, "org:a..b should be refused (core rejects '..')"


def test_owner_traversal_excluded_at_query(_db, _testing):
    """Hub item 2 (query side): an owner containing '..' that bypassed save()
    is excluded by scoped() — the core would never have produced it. Granted
    via a resource grant so the canonical owner check is the gate."""
    # Arrange
    _core, _testing = _testing
    _NullableOwnerRow.objects.all().delete()
    _raw_insert(_NullableOwnerRow, "doc:/dot", "user:a..b")
    f = _make_filter(resources=["doc:/dot"])
    # Act
    got = {r.access_ref for r in _NullableOwnerRow.objects.scoped(f)}
    # Assert
    assert got == set()


def test_missing_access_maps_module_not_found_to_missing():
    """Hub item 3: a ModuleNotFoundError naming scitex_dev.access (the
    not-yet-released case) is recognized as missing."""
    # Arrange
    exc = ModuleNotFoundError("No module named 'scitex_dev.access'", name="scitex_dev.access")
    # Act
    missing = _ad._missing_access(exc)
    # Assert
    assert missing is True


def test_missing_access_maps_root_module_not_found_to_missing():
    """Hub item 3: a ModuleNotFoundError naming the scitex_dev root (no
    submodule) is also the missing case."""
    # Arrange
    exc = ModuleNotFoundError("No module named 'scitex_dev'", name="scitex_dev")
    # Act
    missing = _ad._missing_access(exc)
    # Assert
    assert missing is True


def test_missing_access_rejects_bare_internal_import_error():
    """Hub item 3: a bare ImportError raised INSIDE the core (no name) is a
    real failure, NOT the missing case."""
    # Arrange
    exc = ImportError("internal core failure")  # no .name attribute -> None
    # Act
    missing = _ad._missing_access(exc)
    # Assert
    assert missing is False


def test_missing_access_rejects_unrelated_module_not_found():
    """Hub item 3: a ModuleNotFoundError for a DIFFERENT module (an internal
    transitive dep of the core) is not the 'access missing' case."""
    # Arrange
    exc = ModuleNotFoundError("No module named 'some_internal'", name="some_internal")
    # Act
    missing = _ad._missing_access(exc)
    # Assert
    assert missing is False


# EOF
