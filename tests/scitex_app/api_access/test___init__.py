#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""The declared ``(kind, action)`` pair, composed with ``scitex_dev.access``.

``scitex_app.api_access`` turns a DECLARED pair plus a principal into the core's
``AccessFilter`` and, for a list endpoint, into the Django ``Q`` that admits
exactly the rows the core's ``check()`` allows. This suite proves that, and it
proves it as EQUIVALENCE with the core rather than as agreement with a
hand-written expectation:

  * the PAIR VERDICT agrees with the core in both directions — a pair this module
    accepts is a pair the core accepts, and a pair it refuses is a pair the core
    refuses (so the refusals are not a stricter rule that would drop what the
    core grants, the divergence class fixed on PR #198);
  * the COMPOSED FILTER is field-identical to ``accessible()``'s, across the
    core's own random fixtures and every principal they mention;
  * the COMPOSED Q admits exactly ``check()``'s refs, over a real SQLite table.

DEPENDENCY GATE, exactly as ``test_access_django.py``: the core is optional, so
the differential arms call ``pytest.skip`` with a named reason when
``scitex_dev.access`` is absent (scitex-app's pinned CI). ``api_access`` itself
imports cleanly without the core and without Django — only ``compose_list_q``
needs the ORM — so collection never fails there. Under
``SCITEX_ACCESS_STRICT=1`` (the ci.yml conformance job) a skip is a failure, so
this suite cannot pass by not running against the core.

AAA markers on their own lines (STX-TQ002); one assertion per test (STX-TQ007).
"""

from __future__ import annotations

import os

import django
import pytest
from django.conf import settings
from django.db import connection, models

# WHY THE REAL DATABASE IS CONFIGURED ONLY FOR THE STRICT PROOF RUN — the same
# reasoning, and the same block, as test_access_django.py. Django settings are
# PROCESS-GLOBAL and pytest imports every module it will run into one process
# (one per xdist worker under CI's `-n auto`), so a real DATABASES["default"]
# here would leak into a sibling suite that asserts "this process really has no
# database" — a true precondition about the process it runs in, not a
# disagreement about this module. The Q-backed arms are therefore the POINT of
# the isolated conformance step, which sets SCITEX_ACCESS_STRICT=1 (the same flag
# that turns any skip into a failure); everywhere else this module configures the
# same empty DATABASES as its siblings and those arms skip with the reason the
# `_db` fixture gives. The blocks must agree, because the module order in a
# worker is not ours to choose.
_ACCESS_STRICT_PROOF = os.environ.get("SCITEX_ACCESS_STRICT") == "1"

if not settings.configured:
    settings.configure(
        DEFAULT_CHARSET="utf-8",
        ALLOWED_HOSTS=["*"],
        # In-memory SQLite so the composed Q is exercised against a real table,
        # not a mock — ONLY in the proof run (see above).
        DATABASES=(
            {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": ":memory:"}}
            if _ACCESS_STRICT_PROOF
            else {}
        ),
        INSTALLED_APPS=["django.contrib.contenttypes"],
    )
    django.setup()

from scitex_app import access_django as _ad  # noqa: E402
from scitex_app import api_access  # noqa: E402


class _CompositionRow(models.Model):
    """A concrete ``AccessScopedModel`` standing in for any app's content row.

    A DISTINCT ``db_table`` from ``test_access_django.py``'s stand-in: both
    modules can land in one pytest process, and two models sharing a table would
    make the second one's schema operation a collision rather than a test.
    """

    access_ref = models.CharField(max_length=512)
    access_parent = models.CharField(max_length=512, null=True, blank=True)
    access_owner = models.CharField(max_length=256)
    access_public = models.BooleanField(default=False)

    objects = _ad.AccessScopedManager()

    class Meta:
        app_label = "contenttypes"
        db_table = "api_access_composition_row"


@pytest.fixture(scope="module")
def _core():
    """The core plus its conformance tools, or a named skip when absent."""
    try:
        from scitex_dev import access as core
        from scitex_dev.access import testing
    except ImportError:
        pytest.skip(
            "scitex_dev.access not installed — composition cannot be proven "
            "against the real core until the access release ships "
            "(pip install -U scitex-dev)."
        )
    return core, testing


@pytest.fixture()
def _db():
    """THE single guarded DB fixture: skip cleanly where no DB is configured.

    In the full tests/scitex_app run a sibling configures ``DATABASES={}``, which
    Django turns into the DUMMY backend; the isolated conformance job provides a
    real default, so the cases run non-skipped there. Mirrors the repo's ``_chat``
    convention: "no database" is either no ENGINE at all or the DUMMY sentinel —
    testing ``not settings.DATABASES`` would miss the dummy case and crash
    instead of skipping.
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
        if _CompositionRow._meta.db_table not in connection.introspection.table_names():
            with connection.schema_editor() as se:
                se.create_model(_CompositionRow)
    except Exception as exc:
        pytest.skip(
            f"DB not usable in this process ({type(exc).__name__}) — the "
            "conformance job is the authoritative home for this case"
        )
    yield _CompositionRow
    try:
        _CompositionRow.objects.all().delete()
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Helpers: the two verdicts, taken from the same pair, so they can be compared.
# ---------------------------------------------------------------------------


def _pair_battery(core, testing):
    """Candidate pairs: the fixture's real ones, near-misses, and non-pairs.

    Built from the core's OWN fixture registry rather than a hand-written kind
    list, so the battery follows the core if its kinds change. Padded variants
    are included deliberately: ``AccessClaim`` strips its members, and stripping
    must not make this module accept a pair the core would refuse.
    """
    fixture = testing.random_fixture(seed=3)
    pairs: list[tuple[str, str]] = []
    for spec in fixture.kinds.values():
        actions = sorted(spec.actions)
        for action in actions:
            pairs.append((spec.name, action))
            pairs.append((f"  {spec.name}  ", f"  {action}  "))
        pairs.append((spec.name, "no_such_action"))
        pairs.append(("no.such.kind", actions[0]))
    pairs += [
        ("", "view"),
        ("view", ""),
        ("   ", "view"),
        ("no.such.kind", "view"),
    ]
    return fixture, pairs


def _mine(core, fixture, pair):
    """``(accepted, pair_as_the_core_will_be_asked)`` for this module's path.

    The pair the core is asked about is the CLAIM's pair when the claim
    constructed (stripped) and the raw candidate when it did not: comparing
    against a normalization this module performed would hide a divergence rather
    than prove there is none.
    """
    principal = core.Principal.parse("user:u0")
    try:
        claim = api_access.AccessClaim(*pair)
    except api_access.UnknownAccessPairError:
        return False, pair
    try:
        api_access.compose_filter(
            claim,
            principal,
            grants=fixture.grants,
            memberships=fixture.memberships,
            kinds=fixture.kinds,
        )
    except api_access.UnknownAccessPairError:
        return False, claim.pair
    return True, claim.pair


def _theirs(core, fixture, pair):
    """What the core itself decides about this pair."""
    principal = core.Principal.parse("user:u0")
    try:
        core.accessible(
            principal,
            pair[1],
            pair[0],
            grants=fixture.grants,
            memberships=fixture.memberships,
            kinds=fixture.kinds,
        )
    except (core.AccessConfigError, core.AccessUnresolved):
        return False
    return True


def _filter_fields(access_filter):
    """Every documented ``AccessFilter`` field, as a comparable tuple.

    Field-by-field rather than ``==`` on the object: it keeps the assertion
    meaningful if the core ever gives ``AccessFilter`` a custom ``__eq__``.
    """
    return (
        access_filter.kind,
        access_filter.action,
        access_filter.required_role,
        access_filter.owners,
        access_filter.resources,
        access_filter.parents,
        access_filter.public,
        access_filter.ceiling,
    )


def _load_fixture(model, fixture):
    """Put the fixture's resources into the real table, one row per resource."""
    model.objects.all().delete()
    model.objects.bulk_create(
        model(
            access_ref=resource.ref,
            access_parent=resource.parent,
            access_owner=str(resource.owner),
            access_public=resource.is_public,
        )
        for resource in fixture.resources
    )


def _admitted(model, fixture, principal, pair):
    """The refs the composed Q admits for this DECLARED pair and principal."""
    q = api_access.compose_list_q(
        api_access.AccessClaim(*pair),
        principal,
        grants=fixture.grants,
        memberships=fixture.memberships,
        kinds=fixture.kinds,
    )
    return {row.access_ref for row in model.objects.filter(q)}


# ---------------------------------------------------------------------------
# The claim itself (pure).
# ---------------------------------------------------------------------------


def test_a_blank_kind_is_refused():
    """A pair whose kind was never stated is refused, not filled in."""
    # Arrange
    error = None
    # Act
    try:
        api_access.AccessClaim("", "view")
    except api_access.UnknownAccessPairError as exc:
        error = exc
    # Assert
    assert error is not None and "kind" in str(error)


def test_a_blank_action_is_refused():
    """The action half is refused on the same terms as the kind half."""
    # Arrange
    error = None
    # Act
    try:
        api_access.AccessClaim("conformance.doc", "   ")
    except api_access.UnknownAccessPairError as exc:
        error = exc
    # Assert
    assert error is not None and "action" in str(error)


def test_a_non_text_kind_is_refused():
    """A non-string kind is refused by name rather than attribute-errored later."""
    # Arrange
    error = None
    # Act
    try:
        api_access.AccessClaim(5, "view")
    except api_access.UnknownAccessPairError as exc:
        error = exc
    # Assert
    assert error is not None and "kind" in str(error)


def test_a_claim_reports_its_pair_stripped():
    """The claim stores validated text: the pair it reports is the pair it is."""
    # Arrange
    claim = api_access.AccessClaim("  conformance.doc  ", "  view  ")
    # Act
    pair = claim.pair
    # Assert
    assert pair == ("conformance.doc", "view")


# ---------------------------------------------------------------------------
# The dependency gates (pure: the importers are the seam, nothing is patched).
# ---------------------------------------------------------------------------


def _raising(exc):
    """An importer that always raises ``exc`` — the injectable absent case."""

    def _import(name):
        raise exc

    return _import


def test_a_missing_core_is_a_named_error():
    """Absence of the core module is reported as the named error."""
    # Arrange
    importer = _raising(ModuleNotFoundError("no module named 'scitex_dev.access'", name="scitex_dev.access"))
    # Act
    error = None
    try:
        api_access.load_core(importer=importer)
    except api_access.AccessCoreMissingError as exc:
        error = exc
    # Assert
    assert error is not None


def test_a_missing_core_parent_module_is_also_the_named_error():
    """A build without the whole ``scitex_dev`` distribution is the same state."""
    # Arrange
    importer = _raising(ModuleNotFoundError("no module named 'scitex_dev'", name="scitex_dev"))
    # Act
    error = None
    try:
        api_access.load_core(importer=importer)
    except api_access.AccessCoreMissingError as exc:
        error = exc
    # Assert
    assert error is not None


def test_an_unrelated_missing_module_is_not_laundered_into_absence():
    """Only the core's own absence is 'not installed'; anything else propagates."""
    # Arrange
    importer = _raising(ModuleNotFoundError("no module named 'something-else'", name="something_else"))
    # Act
    error = None
    try:
        api_access.load_core(importer=importer)
    except ModuleNotFoundError as exc:
        error = exc
    # Assert
    assert error is not None and error.name == "something_else"


def test_a_broken_installed_core_is_not_laundered_into_absence():
    """An ImportError raised INSIDE the core is a defect, not a missing dep."""
    # Arrange
    importer = _raising(ImportError("cannot import name 'check' from scitex_dev.access"))
    # Act
    error = None
    try:
        api_access.load_core(importer=importer)
    except ImportError as exc:
        error = exc
    # Assert
    assert error is not None and not isinstance(error, api_access.AccessCoreMissingError)


def test_composition_refuses_when_the_core_is_absent():
    """Composing against an absent core is a raised state, never a permissive filter."""
    # Arrange
    importer = _raising(ModuleNotFoundError("no module named 'scitex_dev.access'", name="scitex_dev.access"))
    # Act
    error = None
    try:
        api_access.compose_filter(api_access.AccessClaim("conformance.doc", "view"), None, importer=importer)
    except api_access.AccessCoreMissingError as exc:
        error = exc
    # Assert
    assert error is not None


def test_a_missing_django_is_a_named_error(_core):
    """The ORM half names its own absence (the filter half needs no framework).

    The pair is resolved FIRST (a declaration defect must not be reported as a
    missing framework), so a valid pair and a real registry are prerequisites of
    reaching the adapter gate at all.
    """
    # Arrange
    core, testing = _core
    fixture = testing.random_fixture(seed=3)
    adapter_importer = _raising(ModuleNotFoundError("no module named 'django'", name="django"))
    # Act
    error = None
    try:
        api_access.compose_list_q(
            api_access.AccessClaim("conformance.doc", "view"),
            core.Principal.parse("user:u0"),
            kinds=fixture.kinds,
            adapter_importer=adapter_importer,
        )
    except api_access.DjangoAdapterMissingError as exc:
        error = exc
    # Assert
    assert error is not None


def test_an_unrelated_adapter_import_error_propagates(_core):
    """A failure inside the adapter is not reported as 'Django is missing'."""
    # Arrange
    core, testing = _core
    fixture = testing.random_fixture(seed=3)
    adapter_importer = _raising(ModuleNotFoundError("no module named 'scitex_ui'", name="scitex_ui"))
    # Act
    error = None
    try:
        api_access.compose_list_q(
            api_access.AccessClaim("conformance.doc", "view"),
            core.Principal.parse("user:u0"),
            kinds=fixture.kinds,
            adapter_importer=adapter_importer,
        )
    except ModuleNotFoundError as exc:
        error = exc
    # Assert
    assert error is not None and error.name == "scitex_ui"


def _missing_exceptions():
    """Every exception shape the two 'is the core missing?' predicates decide on."""
    return (
        ModuleNotFoundError("core", name="scitex_dev.access"),
        ModuleNotFoundError("parent", name="scitex_dev"),
        ModuleNotFoundError("unrelated", name="something_else"),
        ModuleNotFoundError("nameless"),
        ImportError("broken core"),
        ValueError("not an import error at all"),
    )


def test_the_missing_core_predicate_agrees_with_the_django_adapter():
    """One question, one answer: the two predicates must not disagree in-process."""
    # Arrange
    decisions = [
        (api_access._missing_core(exc), _ad._missing_access(exc)) for exc in _missing_exceptions()
    ]
    # Act
    disagreements = [pair for pair in decisions if pair[0] != pair[1]]
    # Assert
    assert disagreements == []


# ---------------------------------------------------------------------------
# The pair verdict, differentially against the core.
# ---------------------------------------------------------------------------


def test_the_pair_verdict_agrees_with_the_core(_core):
    """Accept/refuse is the CORE's decision, mirrored — not a stricter rule.

    Both directions matter: a pair this module refuses that the core accepts
    would drop declarations the core grants, and a pair it accepts that the core
    refuses would compose a filter nobody authorized.
    """
    # Arrange
    core, testing = _core
    fixture, pairs = _pair_battery(core, testing)
    disagreements = []
    # Act
    for pair in pairs:
        mine, pair_the_core_is_asked = _mine(core, fixture, pair)
        if mine != _theirs(core, fixture, pair_the_core_is_asked):
            disagreements.append((pair, pair_the_core_is_asked, mine))
    # Assert
    assert disagreements == []


def test_an_unregistered_kind_names_the_pair_and_the_known_kinds(_core):
    """The refusal is actionable at the declaration site: pair + what is registered."""
    # Arrange
    core, testing = _core
    fixture = testing.random_fixture(seed=3)
    error = None
    # Act
    try:
        api_access.compose_filter(
            api_access.AccessClaim("no.such.kind", "view"),
            core.Principal.parse("user:u0"),
            kinds=fixture.kinds,
        )
    except api_access.UnknownAccessPairError as exc:
        error = exc
    # Assert
    assert error is not None and "no.such.kind" in str(error) and "conformance.doc" in str(error)


def test_an_undefined_action_names_the_actions_the_kind_declares(_core):
    """An action the kind does not declare is refused, never widened to read."""
    # Arrange
    core, testing = _core
    fixture = testing.random_fixture(seed=3)
    error = None
    # Act
    try:
        api_access.compose_filter(
            api_access.AccessClaim("conformance.doc", "publish"),
            core.Principal.parse("user:u0"),
            kinds=fixture.kinds,
        )
    except api_access.UnknownAccessPairError as exc:
        error = exc
    # Assert
    assert error is not None and "publish" in str(error) and "share" in str(error)


def test_an_undefined_action_never_yields_a_public_filter(_core):
    """The specific widening this module refuses: no read/public fallback."""
    # Arrange
    core, testing = _core
    fixture = testing.random_fixture(seed=3)
    result = None
    # Act
    try:
        result = api_access.compose_filter(
            api_access.AccessClaim("conformance.doc", "view_all"),
            core.Principal.parse("user:u0"),
            kinds=fixture.kinds,
        )
    except api_access.UnknownAccessPairError:
        result = "refused"
    # Assert
    assert result == "refused"


def test_the_composed_filter_is_identical_to_the_cores_accessible(_core):
    """Field-identical, across the core's fixtures, askers, kinds and actions.

    This is the equality the Q proof then inherits from: if the composed filter
    IS the core's filter, then ``to_q`` — already proven against ``check()`` in
    test_access_django.py — admits exactly the core's rows here too.
    """
    # Arrange
    core, testing = _core
    mismatches = []
    # Act
    for seed in range(8):
        fixture = testing.random_fixture(seed)
        for principal in testing.askers_of(fixture):
            for spec in fixture.kinds.values():
                for action in sorted(spec.actions):
                    claim = api_access.AccessClaim(spec.name, action)
                    mine = api_access.compose_filter(
                        claim,
                        principal,
                        grants=fixture.grants,
                        memberships=fixture.memberships,
                        kinds=fixture.kinds,
                    )
                    theirs = core.accessible(
                        principal,
                        action,
                        spec.name,
                        grants=fixture.grants,
                        memberships=fixture.memberships,
                        kinds=fixture.kinds,
                    )
                    if _filter_fields(mine) != _filter_fields(theirs):
                        mismatches.append((seed, str(principal), spec.name, action))
    # Assert
    assert mismatches == []


# ---------------------------------------------------------------------------
# The composed Q, over a real table.
# ---------------------------------------------------------------------------


def test_the_composed_q_admits_exactly_what_check_allows(_db, _core):
    """THE row-level proof: a DECLARED pair, a real queryset, the core's own check().

    The pair is driven the way a list endpoint would drive it — compose the Q
    from the declaration, filter a real table — and the admitted refs must equal
    the refs ``check()`` allows resource by resource, for every principal the
    core's fixture mentions and every action the kind declares.
    """
    # Arrange
    core, testing = _core
    fixture = testing.random_fixture(seed=11)
    _load_fixture(_db, fixture)
    mismatches = []
    # Act
    for spec in fixture.kinds.values():
        resources = [r for r in fixture.resources if r.kind == spec.name]
        for principal in testing.askers_of(fixture):
            for action in sorted(spec.actions):
                admitted = _admitted(_db, fixture, principal, (spec.name, action))
                for resource in resources:
                    allowed = core.check(
                        principal,
                        action,
                        resource,
                        grants=fixture.grants,
                        memberships=fixture.memberships,
                        kinds=fixture.kinds,
                    ).is_allowed
                    if allowed != (resource.ref in admitted):
                        mismatches.append((str(principal), spec.name, action, resource.ref))
    # Assert
    assert mismatches == []


def test_the_composed_q_is_to_q_of_the_composed_filter(_db, _core):
    """The wiring itself: the list helper translates the filter it composed."""
    # Arrange
    core, testing = _core
    fixture = testing.random_fixture(seed=11)
    pair = ("conformance.doc", "view")
    principal = core.Principal.parse("user:u0")
    # Act
    composed = api_access.compose_list_q(
        api_access.AccessClaim(*pair),
        principal,
        grants=fixture.grants,
        memberships=fixture.memberships,
        kinds=fixture.kinds,
    )
    translated = _ad.to_q(
        api_access.compose_filter(
            api_access.AccessClaim(*pair),
            principal,
            grants=fixture.grants,
            memberships=fixture.memberships,
            kinds=fixture.kinds,
        )
    )
    # Assert
    assert str(composed) == str(translated)


def test_a_principal_without_a_grant_admits_no_private_row(_db, _core):
    """The over-admission class PR #198 caught: an empty grant set is no match.

    A principal with no grants and no memberships must not have an empty filter
    silently degrade into match-all — the failure mode that admits every row.
    """
    # Arrange
    core, testing = _core
    fixture = testing.random_fixture(seed=11)
    _load_fixture(_db, fixture)
    private_refs = {
        resource.ref for resource in fixture.resources if not resource.is_public
    }
    # Act
    admitted = _admitted(_db, fixture, core.Principal.parse("user:nobody"), ("conformance.doc", "edit"))
    # Assert
    assert admitted & private_refs == set()


def test_a_public_row_is_admitted_for_a_read_action(_db, _core):
    """Positive control: the arms above are not passing because nothing is admitted."""
    # Arrange
    core, testing = _core
    fixture = testing.random_fixture(seed=11)
    _load_fixture(_db, fixture)
    public_refs = {
        resource.ref
        for resource in fixture.resources
        if resource.is_public and resource.kind == "conformance.doc"
    }
    # Act
    admitted = _admitted(_db, fixture, core.Principal.parse("user:nobody"), ("conformance.doc", "view"))
    # Assert
    assert admitted & public_refs == public_refs


def test_a_write_action_does_not_admit_a_public_row(_db, _core):
    """Public means read for a signed-in user — never a write the world may do."""
    # Arrange
    core, testing = _core
    fixture = testing.random_fixture(seed=11)
    _load_fixture(_db, fixture)
    public_refs = {
        resource.ref
        for resource in fixture.resources
        if resource.is_public and resource.kind == "conformance.doc"
    }
    # Act
    admitted = _admitted(_db, fixture, core.Principal.parse("user:nobody"), ("conformance.doc", "edit"))
    # Assert
    assert admitted & public_refs == set()

# EOF
