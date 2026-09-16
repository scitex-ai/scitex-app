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


# EOF
