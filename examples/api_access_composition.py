#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Composing a DECLARED ``(kind, action)`` access pair, end to end.

A leaf declares the claim it makes on a resource kind — ``(kind, action)`` —
and the host composes it into the access decision. This example does both
halves and shows the property the composition exists for: the rows a LIST
endpoint serves are exactly the rows the core's ``check()`` allows, so a
declared API surface and its access decision cannot drift apart.

It also shows the fail-closed half: a pair the core does not define is REFUSED
by name, never widened to a read/public filter.

Requires ``scitex_dev.access`` (the access release). The Django section is
skipped with a printed reason when Django is not installed.

Usage:
    python api_access_composition.py
"""

from __future__ import annotations

import sys


def _core_or_exit():
    """The access core, or a one-line reason this example cannot run."""
    try:
        from scitex_dev import access as core
    except ImportError:
        print(
            "scitex_dev.access is not installed, so there is nothing to "
            "compose. Run: pip install -U scitex-dev"
        )
        sys.exit(0)
    return core


def main() -> None:
    core = _core_or_exit()
    from scitex_app.api_access import (
        AccessClaim,
        UnknownAccessPairError,
        compose_filter,
        compose_list_q,
    )

    # 1. The KIND a leaf declares, published the way the core discovers kinds:
    #    a KindSpec naming the kind, its path prefix and its actions, each action
    #    mapped to the role it requires. Here it is registered locally so the
    #    example is self-contained; a real leaf publishes it through the
    #    `scitex_dev.access.kinds` entry point.
    figure_kind = core.KindSpec(
        name="figrecipe.figure",
        path_prefix="/figures",
        actions={"view": "read", "edit": "write", "share": "admin"},
        package="figrecipe",
    )
    kinds = core.KindRegistry([figure_kind])

    # 2. The DECLARED pair, and the principal asking for it.
    claim = AccessClaim("figrecipe.figure", "view")
    alice = core.Principal.parse("user:alice")

    # 3. The grant that makes the decision true for one figure only.
    grant = core.Grant(
        principal=alice, role="read", target="figrecipe.figure:/figures/plot-1", default=False
    )

    access_filter = compose_filter(claim, alice, grants=(grant,), kinds=kinds)
    print(f"declared pair      : {claim.pair}")
    print(f"required role      : {access_filter.required_role}")
    print(f"granted resources  : {sorted(access_filter.resources)}")
    print(f"public rows allowed: {access_filter.public}")

    # 4. The list endpoint's predicate: the rows this principal may see.
    if _django_available():
        rows = _seed_and_compose(core, kinds, grant, compose_list_q, claim, alice)
        admitted = sorted(row for row in rows)
        print(f"rows the list serves: {admitted}")

        # 5. The property: the Q admits exactly what check() allows, row by row.
        resource = core.Resource(
            kind="figrecipe.figure",
            path="/figures/plot-1",
            owner=core.Principal.parse("user:bob"),
        )
        decision = core.check(
            alice, "view", resource, grants=(grant,), memberships=(), kinds=kinds
        )
        print(
            f"check() on {resource.ref}: allowed={decision.is_allowed} "
            f"(reason={decision.reason}) — agrees with the query: "
            f"{decision.is_allowed == (resource.ref in admitted)}"
        )
    else:
        print("django is not installed — skipping the list-endpoint section")

    # 6. Fail closed: an action the kind does not declare, and a kind nobody
    #    registered. Both are refused by name, and neither degrades to a filter.
    for candidate in (AccessClaim("figrecipe.figure", "publish"), AccessClaim("nosuch.kind", "view")):
        try:
            compose_filter(candidate, alice, grants=(grant,), kinds=kinds)
            print(f"UNEXPECTED: {candidate.pair} composed")
        except UnknownAccessPairError as exc:
            print(f"refused by name: {candidate.pair} -> {str(exc).splitlines()[0]}")


def _django_available() -> bool:
    """True when the ORM half of the composition can be demonstrated here."""
    try:
        import django  # noqa: F401
    except ImportError:
        return False
    return True


def _seed_and_compose(core, kinds, grant, compose_list_q, claim, principal):
    """A real table, the composed Q, and the refs it admits."""
    import django
    from django.conf import settings

    if not settings.configured:
        settings.configure(
            DEFAULT_CHARSET="utf-8",
            ALLOWED_HOSTS=["*"],
            DATABASES={"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": ":memory:"}},
            INSTALLED_APPS=["django.contrib.contenttypes"],
        )
        django.setup()

    from django.db import connection, models

    from scitex_app.access_django import AccessScopedManager

    class FigureRow(models.Model):
        """A figure, carrying the four fields an access-scoped row needs."""

        access_ref = models.CharField(max_length=512)
        access_parent = models.CharField(max_length=512, null=True, blank=True)
        access_owner = models.CharField(max_length=256)
        access_public = models.BooleanField(default=False)

        objects = AccessScopedManager()

        class Meta:
            app_label = "contenttypes"
            db_table = "example_api_access_figure_row"

    if FigureRow._meta.db_table not in connection.introspection.table_names():
        with connection.schema_editor() as se:
            se.create_model(FigureRow)

    # Two figures owned by someone else: one shared with alice, one not.
    FigureRow.objects.all().delete()
    FigureRow.objects.bulk_create(
        [
            FigureRow(
                access_ref="figrecipe.figure:/figures/plot-1",
                access_owner="user:bob",
                access_public=False,
            ),
            FigureRow(
                access_ref="figrecipe.figure:/figures/plot-2",
                access_owner="user:bob",
                access_public=False,
            ),
        ]
    )

    q = compose_list_q(claim, principal, grants=(grant,), kinds=kinds)
    return {row.access_ref for row in FigureRow.objects.filter(q)}


if __name__ == "__main__":
    main()

# EOF
