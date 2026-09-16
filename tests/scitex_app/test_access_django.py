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


def test_django_to_q_matches_check(_testing):
    """THE proof: my Django translation agrees with the core's check().

    assert_equivalent raises AssertionError on any mismatch; returning None
    means every (principal, action, resource) in 40 random fixtures was
    decided identically by check() and by the Django queryset.
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
def _fc_table():
    """Create the fail-closed table, or skip the test when the process has no
    usable default database.

    In the full pytest-matrix run the sibling ``_chat`` tests configure Django
    with ``DATABASES={}`` (their PA-306 convention) before this module runs, so
    the module-top ``:memory:`` setup is skipped and there is no table to
    create. The conformance job (ci.yml access-conformance) and any DB-backed
    run do have one, so these cases run there. A skip is the correct outcome
    when the process genuinely has no DB; it is NOT the conformance battery's
    skip (that one is gated on the core import, a separate condition).
    """
    # The conformance job (ci.yml) runs this module in a clean single process
    # with a :memory: DB, so the DB-backed cases run non-skipped there. In the
    # full matrix run the _chat tests configure settings with DATABASES={}
    # first, so this module's :memory: setup is skipped and connection is in a
    # half-configured state — table creation then raises. A skip is the
    # correct outcome in that case; the authoritative proof is the conformance
    # job, not the matrix.
    if "default" not in settings.DATABASES:
        pytest.skip("no default database configured in this process")
    try:
        if "access_django_fail_closed_row" not in connection.introspection.table_names():
            with connection.schema_editor() as se:
                se.create_model(_FailClosedRow)
    except Exception as exc:
        pytest.skip(f"DB not usable in this process ({type(exc).__name__}) — the conformance job is the authoritative home for this case")
    yield
    try:
        _FailClosedRow.objects.all().delete()
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


def test_save_accepts_canonical_row(_fc_table):
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


def test_scoped_query_excludes_null_owner_row(_testing):
    """Even a null-owner row that bypassed save() is excluded at query time
    (the canonical conjunct in to_q), so bad data fails closed, not wide."""
    # Arrange
    _core, _testing = _testing
    if "access_django_nullowner_row" not in connection.introspection.table_names():
        with connection.schema_editor() as se:
            se.create_model(_NullableOwnerRow)
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


# EOF
