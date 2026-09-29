"""Tests for scitex_app/authz.py — the verdict type, and can() that returns it.

One assertion each. Every rule here is a promise made to scitex-ui before they
wrote their display component, so each arm names the promise it holds.

THE ARMS SPLIT IN TWO, deliberately, and the split is by what they need:

  * contract arms — can()'s resolve-before-render behaviour and the
    absent-dependency predicate. These need NO core (`importer` is a seam), so
    they are unconditional and can never skip.
  * decision arms — the core's decision becoming this package's Verdict. These
    need scitex_dev.access and are guarded by `_core`; under
    SCITEX_ACCESS_STRICT=1 tests/scitex_app/conftest.py upgrades that guard to a
    FAILURE, which is what makes it a proof rather than a silent skip.
"""

from __future__ import annotations

import importlib
import subprocess
import sys

import pytest

from scitex_app.authz import (
    ALLOWED,
    CORE_MODULE,
    DENIED,
    DENIED_NOT_ENTITLED,
    DENIED_NOT_SIGNED_IN,
    UNRESOLVED,
    VERDICT_KINDS,
    AccessPrimitiveMissingError,
    DataScope,
    ResolveNotAttemptedError,
    ResolveState,
    ScopeError,
    Verdict,
    VerdictError,
    _missing_access_primitive,
    allowed,
    can,
    denied,
    denied_not_entitled,
    denied_not_signed_in,
    scope_for,
    scope_from_decision,
    unresolved,
    verdict_from_decision,
)


# ─── the five kinds, and that there are exactly five ────────────────────────


def test_there_are_exactly_five_kinds():
    """WAS FOUR UNTIL 2026-09-05. Changed deliberately, in the same commit that
    added the fifth, and the reason the count is asserted at all is that this
    test is what forced the change to be a conversation.

    It fired twice: once when I found a second unresolved axis and wanted to
    add `unresolved` unilaterally, and once when the implementation finally
    required it. Both times the red said "tell scitex-ui first", and both times
    that was the correct instruction — their switch is exhaustive over these
    values and a new one is a COMPILE error on their side.

    So this is not a count for its own sake. Adding a sixth must be the same
    kind of event: coordinated, and ordered TS-first, because the cross-package
    check reads their INSTALLED wheel and Python-first goes red in a way this
    side cannot clear.
    """
    # Arrange
    # Act
    count = len(VERDICT_KINDS)
    # Assert
    assert count == 5


def test_unresolved_carries_no_payload():
    """The reason resolution failed must not reach a page.

    It does not change what the UI renders, and naming it discloses that the
    service behind this gate is down to a reader who is not authenticated to
    it — the same argument that kept the unresolved axis name out of the DOM.
    """
    # Arrange
    verdict = unresolved()
    # Act
    plain = verdict.to_dict()
    # Assert
    assert plain == {"kind": UNRESOLVED}


def test_unresolved_is_not_a_denial():
    """It must never be foldable into the kind that asserts the user is out.

    denied-because-not-signed-in CLAIMS the user is signed out. When resolution
    failed we do not have that claim, and rendering it tells the user to sign
    in to a service we could not reach.
    """
    # Arrange
    verdict = unresolved()
    # Act
    kind = verdict.kind
    # Assert
    assert kind not in (DENIED, DENIED_NOT_SIGNED_IN, DENIED_NOT_ENTITLED)


def test_a_sign_in_url_is_refused_on_unresolved():
    # Arrange — offering a route on a verdict that does not know the answer
    # invites the user to act on a state we have not established.
    kind = UNRESOLVED
    # Act
    refusal = _refusal(kind=kind, sign_in_url="/accounts/signin")
    # Assert
    assert refusal is not None


def test_an_upgrade_url_is_refused_on_unresolved():
    # Arrange
    kind = UNRESOLVED
    # Act
    refusal = _refusal(kind=kind, upgrade_url="/pricing/")
    # Assert
    assert refusal is not None


def test_allowed_carries_no_payload():
    # Arrange
    # Act
    verdict = allowed()
    # Assert
    assert verdict.to_dict() == {"kind": ALLOWED}


def test_denied_carries_no_payload():
    """The promise: a plain denial must not hint at a route that does not exist."""
    # Arrange
    # Act
    verdict = denied()
    # Assert
    assert verdict.to_dict() == {"kind": DENIED}


def test_not_signed_in_carries_the_sign_in_url():
    # Arrange
    # Act
    verdict = denied_not_signed_in("/accounts/signin")
    # Assert
    assert verdict.to_dict() == {
        "kind": DENIED_NOT_SIGNED_IN,
        "sign_in_url": "/accounts/signin",
    }


def test_not_entitled_carries_the_entitlement_identifier():
    # Arrange
    # Act
    verdict = denied_not_entitled("hub.member")
    # Assert
    assert verdict.to_dict() == {
        "kind": DENIED_NOT_ENTITLED,
        "entitlement": "hub.member",
    }


# ─── the validator: it must FAIL, and say what to do about it ──────────────
#
# `pytest.raises` COUNTS AS AN ASSERTION here (STX-TQ007), so a raises block
# plus a message check would be two claims in one test -- and the rule is right
# that the first failure would hide the second. The helper below turns the
# refusal into a VALUE, so each test makes exactly one claim and can still
# assert on the message.
#
# Asserting on the message rather than merely on the type is the point: the
# caller is a developer building a verdict in the wrong shape, and the message
# is the only thing that tells them WHICH FIELD. An error that says only what
# broke is half-written.


def _refusal(**kwargs):
    """Build a Verdict and return the VerdictError it raised, or None."""
    try:
        Verdict(**kwargs)
    except VerdictError as exc:
        return exc
    return None


def test_an_unknown_kind_is_refused():
    # Arrange
    kind = "maybe"
    # Act
    refusal = _refusal(kind=kind)
    # Assert
    assert refusal is not None


def test_the_refusal_names_the_offending_value():
    # Arrange
    kind = "maybe"
    # Act
    refusal = _refusal(kind=kind)
    # Assert
    assert "maybe" in str(refusal)


def test_the_refusal_lists_the_kinds_that_would_have_worked():
    """The actionable half: naming the valid set is the fix, not the diagnosis."""
    # Arrange
    kind = "maybe"
    # Act
    refusal = _refusal(kind=kind)
    # Assert
    assert ALLOWED in str(refusal)


def test_not_signed_in_without_a_url_is_refused():
    """Without the URL the caller must know where sign-in lives — the exact
    duplication the payload exists to remove."""
    # Arrange
    kind = DENIED_NOT_SIGNED_IN
    # Act
    refusal = _refusal(kind=kind)
    # Assert
    assert "sign_in_url" in str(refusal)


def test_not_entitled_without_an_identifier_is_refused():
    # Arrange
    kind = DENIED_NOT_ENTITLED
    # Act
    refusal = _refusal(kind=kind)
    # Assert
    assert "entitlement" in str(refusal)


def test_a_plain_denial_carrying_a_sign_in_url_is_refused():
    """The other direction, and the one a stylistic rule would have missed.

    Offering a route on a verdict that is not about signing in tells the user
    to do something that cannot help. The validator enforces absence, not just
    presence.
    """
    # Arrange
    url = "/accounts/signin"
    # Act
    refusal = _refusal(kind=DENIED, sign_in_url=url)
    # Assert
    assert "must not carry sign_in_url" in str(refusal)


def test_allowed_carrying_an_entitlement_is_refused():
    # Arrange
    entitlement = "hub.member"
    # Act
    refusal = _refusal(kind=ALLOWED, entitlement=entitlement)
    # Assert
    assert "must not carry entitlement" in str(refusal)


# ─── properties scitex-ui depends on ────────────────────────────────────────


def _assignment_outcome(verdict):
    """Try to mutate a verdict; return the exception raised, or None."""
    try:
        verdict.kind = ALLOWED
    except Exception as exc:  # frozen dataclasses raise FrozenInstanceError
        return exc
    return None


def test_a_verdict_cannot_be_edited_after_construction():
    """A caller that can edit one can turn a denial into an approval."""
    # Arrange
    verdict = denied()
    # Act
    outcome = _assignment_outcome(verdict)
    # Assert
    assert outcome is not None


def test_there_is_no_allowed_boolean_property():
    """DELIBERATE ABSENCE, asserted so nobody adds it as a convenience.

    `if verdict.allowed:` reads naturally, passes review, and silently treats
    "sign in first" as identical to "never" — the collapse this whole type
    exists to prevent.
    """
    # Arrange
    verdict = allowed()
    # Act
    has_boolean_shortcut = hasattr(verdict, "allowed")
    # Assert
    assert has_boolean_shortcut is False


def test_absent_payload_keys_are_omitted_rather_than_null():
    """A null would make every consumer write a truthiness check where the
    kind already answered the question."""
    # Arrange
    verdict = allowed()
    # Act
    keys = set(verdict.to_dict())
    # Assert
    assert keys == {"kind"}


def test_the_serialised_form_needs_no_scitex_app_types_to_read():
    """scitex-ui must be testable with hand-written fixtures and scitex-app
    absent, so everything that crosses the boundary is plain data."""
    # Arrange
    verdict = denied_not_signed_in("/accounts/signin")
    # Act
    plain = verdict.to_dict()
    # Assert
    assert all(isinstance(v, str) for v in plain.values())


# ─── upgrade_url: OPTIONAL, and its absence has ONE meaning ─────────────────
#
# scitex-ui's requirement when they approved this payload: pin what absence
# MEANS, because absence is a normal case here and an unpinned normal case is
# where a consumer guesses. Absent = no upgrade surface configured (render
# inert). Absent != "not yet resolved" — that is the `unresolved` kind.


def test_upgrade_url_is_carried_when_supplied():
    # Arrange
    verdict = denied_not_entitled("pro", upgrade_url="/pricing/")
    # Act
    plain = verdict.to_dict()
    # Assert
    assert plain["upgrade_url"] == "/pricing/"


def test_upgrade_url_is_optional_and_omitted_when_absent():
    # Arrange — a hub that sells nothing has no upgrade surface, so this is a
    # normal verdict rather than a malformed one.
    verdict = denied_not_entitled("pro")
    # Act
    keys = set(verdict.to_dict())
    # Assert
    assert keys == {"kind", "entitlement"}


def test_an_absent_upgrade_url_is_not_an_error():
    """The asymmetry with sign_in_url, asserted rather than described.

    sign_in_url is REQUIRED on its kind; upgrade_url is not. If this ever
    becomes required, a self-hosted hub with nothing to sell can no longer
    build a legal not-entitled verdict.
    """
    # Arrange
    # Act
    verdict = denied_not_entitled("pro")
    # Assert
    assert verdict.upgrade_url is None


def test_upgrade_url_is_refused_on_a_plain_denial():
    # Arrange — a route to upgrade on a verdict that is not about entitlement
    # tells the user to do something that cannot help.
    kind = DENIED
    # Act
    refusal = _refusal(kind=kind, upgrade_url="/pricing/")
    # Assert
    assert refusal is not None


def test_the_upgrade_url_refusal_names_the_field():
    # Arrange — the caller is a developer building the wrong shape; the message
    # is the only thing that tells them WHICH field is at fault.
    kind = DENIED
    # Act
    refusal = _refusal(kind=kind, upgrade_url="/pricing/")
    # Assert
    assert "upgrade_url" in str(refusal)


def test_upgrade_url_is_refused_on_not_signed_in():
    # Arrange — the kind that already carries a route carries only its own.
    kind = DENIED_NOT_SIGNED_IN
    # Act
    refusal = _refusal(
        kind=kind, sign_in_url="/accounts/signin", upgrade_url="/pricing/"
    )
    # Assert
    assert refusal is not None


def test_upgrade_url_is_refused_on_allowed():
    # Arrange
    kind = ALLOWED
    # Act
    refusal = _refusal(kind=kind, upgrade_url="/pricing/")
    # Assert
    assert refusal is not None


# ─── the resolve state, which the tripwire below now watches ────────────────
#
# These describe the type; the tripwire describes the CONSTRAINT and was
# written first, deliberately, while there was nothing to constrain.


def test_there_are_exactly_three_resolve_states():
    """A fourth would add a branch to can()'s A/B split without saying so.

    Same reason the kind count is asserted above: the split is exhaustive over
    these, so a fourth state must be a deliberate edit rather than something
    that appears.
    """
    # Arrange
    # Act
    count = len(ResolveState)
    # Assert
    assert count == 3


def test_not_attempted_is_distinct_from_failed():
    """The one collapse that makes the whole decomposition unimplementable.

    NOT_ATTEMPTED must RAISE (a caller who never resolved has violated the
    contract) and FAILED must RETURN a verdict (a real operating state the
    screen must still draw). Held as one value they are the same state and
    can() cannot choose.
    """
    # Arrange
    # Act
    same = ResolveState.NOT_ATTEMPTED is ResolveState.FAILED
    # Assert
    assert same is False


def test_a_resolve_state_is_not_a_string():
    """It must not be able to leak into anything serialised.

    A `str` subclass would survive `json.dumps` and a stray `to_dict()`, and
    what it would leak is that resolution FAILED — i.e. that the service behind
    this gate is currently down, to a reader who is not authenticated to it.
    That is the same disclosure argument that kept the unresolved AXIS NAME out
    of the DOM; this is the mechanical half of it.
    """
    # Arrange
    state = ResolveState.FAILED
    # Act
    is_str = isinstance(state, str)
    # Assert
    assert is_str is False


# ─── the resolve-state tripwire ─────────────────────────────────────────────
#
# A TRIPWIRE, NOT A CHECK. It guards a decision made 2026-09-04 with scitex-ui
# about code that does not exist yet, and it is written to FAIL the moment that
# code appears — which is the only moment the decision can be violated.
#
# THE DECISION. `can()` must distinguish two causes of "unresolved":
#
#     A. the caller never resolved        -> RAISE (a contract violation;
#                                            returning a verdict renders a BUG
#                                            as a legitimate "not yet known" UI)
#     B. resolution attempted and FAILED  -> return an `unresolved` verdict
#        (hub unreachable, timeout, 5xx)     (a real operating state; the screen
#                                            must still draw something)
#
# THAT IS ONLY IMPLEMENTABLE IF THE RESOLVE RESULT IS THREE-VALUED:
#
#     NOT_ATTEMPTED | FAILED | RESOLVED
#
# Held as "a value, or None" it is TWO-valued, A and B become the same state,
# and the decomposition silently becomes unimplementable. That is the same
# three-value collapse this repo hit three times in one week (pass/fail/skip;
# DIVERGED/AGREE/CANNOT-TELL) — recorded here BEFORE the code rather than found
# in it afterwards.
#
# WHY A TRIPWIRE AND NOT A COMMENT. scitex-ui's objection to the card note, and
# it is correct: a constraint written in prose fails NOTHING when someone writes
# the resolver two-valued. It passes review, the suite is green, and nobody is
# told the decomposition just died. That is §2's declaration-that-evaporates,
# one step before it becomes a gate that cannot fail.
#
# IT ASSERTS THE SHAPE, NOT THE ABSENCE — rewritten 2026-09-04 on scitex-ui's
# argument, which is better than the version I shipped hours earlier.
#
# The first draft asserted that NO resolver exists, so it went red the moment
# someone added one. That punishes CORRECT work: the person who implements the
# resolver properly is the first casualty, and the red means "progress" rather
# than "defect". Repeated, that teaches a reader that red is something to push
# past — the same harm as a permanently-red retired workflow.
#
# This version is silent while the resolver is absent and substantive the moment
# it appears. Red here always means the same thing: the three-valued constraint
# was violated. So it never fires on correct work, and its meaning is constant.
#
# A conditional guard that is vacuous today is exactly the gate-that-cannot-fail
# this file is about — which is why it is CALIBRATED in the commit that
# introduced it: a two-valued resolver makes it red, a three-valued one keeps it
# green, both observed rather than reasoned.


_RESOLVE_STATES = frozenset({"NOT_ATTEMPTED", "FAILED", "RESOLVED"})


def _resolve_state_members():
    """Members of any resolve-state type in authz, or None when there is none.

    THREE-VALUED ITSELF, deliberately, since that is the property it guards:
      None  -> no resolver yet (guard is vacuous, and says so)
      set() -> a resolver exists but exposes no members (guard must FAIL: its
               subject changed shape and it can no longer check what it claims)
      names -> compare
    """
    import scitex_app.authz as authz_module

    found = [
        getattr(authz_module, n)
        for n in dir(authz_module)
        if "Resolve" in n or "resolve" in n
    ]
    if not found:
        return None
    names = set()
    for obj in found:
        names |= {
            m for m in dir(obj) if m.isupper() and not m.startswith("_")
        }
    return names


def test_a_resolve_state_if_present_is_three_valued():
    """Vacuous until a resolver exists; substantive from the moment it does.

    NOT_ATTEMPTED and FAILED must stay distinct: collapsing them makes
    can()'s A/B split unimplementable (caller-never-resolved must RAISE,
    resolution-attempted-and-failed must return an `unresolved` verdict).
    """
    # Arrange
    members = _resolve_state_members()
    # Act
    verdict = _RESOLVE_STATES if members is None else members
    # Assert
    assert verdict == _RESOLVE_STATES


# ─── can(): the contract arms. These need NO core. ──────────────────────────
#
# `importer` is a seam, so each of these pins one behaviour of can() ITSELF
# without depending on a released dependency. That is deliberate: the
# resolve-before-render contract is the part scitex-ui's screen depends on, and
# it must not become unverifiable the day the core is absent from an env.


def _exploding_importer(name):
    """A core import that must NEVER happen in the arm using it."""
    raise AssertionError(f"the core ({name}) was imported where it must not be")


def _absent_importer(name):
    """The exact failure an install without the access release produces."""
    raise ModuleNotFoundError(f"No module named '{name}'", name=name)


def test_can_raises_before_anything_is_resolved():
    """NOT_ATTEMPTED is a CONTRACT VIOLATION, and it RAISES rather than returns.

    Returning `unresolved` here would render a bug as a legitimate "not yet
    known" screen — permanently, because the bug would never appear as anything
    else. This is decision A of the tripwire above.
    """
    # Arrange — the core is unreachable on purpose: a caller who never resolved
    # has nothing to ask the core about.
    # Act
    error = None
    try:
        can(object(), "view", object(), state=ResolveState.NOT_ATTEMPTED, importer=_exploding_importer)
    except ResolveNotAttemptedError as exc:
        error = exc
    # Assert
    assert error is not None


def test_the_contract_violation_is_a_verdict_error():
    """So a caller already handling "you asked for a verdict wrongly" needs no

    second except clause — and, more importantly, so nothing here is a Verdict:
    a contract violation must not be renderable.
    """
    # Arrange
    # Act
    is_verdict_error = issubclass(ResolveNotAttemptedError, VerdictError)
    # Assert
    assert is_verdict_error is True


def test_can_returns_unresolved_when_resolution_was_attempted_and_failed():
    """FAILED RETURNS instead of raising. Decision B of the tripwire.

    A hub that is unreachable or 5xx-ing is a real operating state the screen
    must still draw; raising here would push every app author into try/except
    writing their own unknown-display, scattering the judgement this module
    exists to hold in one place.
    """
    # Arrange — the core must not be consulted: nothing has been resolved to ask
    # it about. `_exploding_importer` proves that by failing if it is.
    # Act
    verdict = can(object(), "view", object(), state=ResolveState.FAILED, importer=_exploding_importer)
    # Assert
    assert verdict.to_dict() == {"kind": UNRESOLVED}


def test_a_failed_resolution_is_not_a_denial():
    """The collapse this whole module exists to prevent, asserted on can().

    `unresolved` and `denied` are different answers: one says "we do not know",
    the other says "no". A caller that treats them alike tells a signed-in user
    to sign in, or hides content that is merely unreachable.
    """
    # Arrange
    # Act
    kind = can(object(), "view", object(), state=ResolveState.FAILED, importer=_exploding_importer).kind
    # Assert
    assert kind not in (DENIED, DENIED_NOT_SIGNED_IN, DENIED_NOT_ENTITLED)


def test_can_refuses_by_name_when_the_core_is_not_installed():
    """An install that CANNOT decide must not look like one that decided "no".

    Only one of those two is fixed by configuring something, and a caller
    reading `denied` would go looking for a grant that does not exist.
    """
    # Arrange
    # Act
    error = None
    try:
        can(object(), "view", object(), state=ResolveState.RESOLVED, importer=_absent_importer)
    except AccessPrimitiveMissingError as exc:
        error = exc
    # Assert
    assert error is not None


def test_the_missing_core_refusal_names_the_fix():
    """A named error whose message does not say what to install is a diagnosis

    without a remedy, and the reader is a developer at a shell.
    """
    # Arrange
    # Act
    error = None
    try:
        can(object(), "view", object(), state=ResolveState.RESOLVED, importer=_absent_importer)
    except AccessPrimitiveMissingError as exc:
        error = exc
    # Assert
    assert "scitex-dev" in str(error)


def test_the_missing_core_predicate_agrees_with_its_sibling():
    """"The core is missing" must not mean two things inside one package.

    authz now carries the THIRD same-shaped predicate. The other two are
    ``api_access._missing_core`` and ``access_django._missing_access``, each
    written separately because each module must stay importable without the
    others' dependencies. A third copy is only honest if something pins the
    three together.

    WHY ONLY ONE SIBLING IS READ HERE: importing ``access_django`` requires
    CONFIGURED Django settings, and configuring Django in this process is the
    process-global side effect that poisons a pytest-xdist worker for the
    ``_chat`` suite's "this process really has no database" assertions. So the
    leg pinned here is authz<->api_access, and the third leg is pinned
    transitively where it can be read safely — tests/scitex_app/
    api_access/test___init__.py compares api_access against access_django
    case-by-case, so agreement here plus agreement there IS agreement among all
    three. A pure arm (PA-306 §3: hand-built exceptions, no mocking).
    """
    # Arrange — a true case for each accepted spelling, plus three that must NOT
    # be laundered into "absent". The controls matter more than the positives: a
    # predicate that answered True everywhere would pass an agreement check alone.
    from scitex_app import api_access

    cases = [
        ModuleNotFoundError("no scitex_dev", name="scitex_dev"),
        ModuleNotFoundError("no scitex_dev.access", name=CORE_MODULE),
        ImportError("a real failure inside an installed core"),
        ModuleNotFoundError("no yaml", name="yaml"),
        RuntimeError("not an import error at all"),
    ]
    # Act
    rows = [
        (_missing_access_primitive(exc), api_access._missing_core(exc)) for exc in cases
    ]
    # Assert — both agree on every case, AND the agreed answer is not vacuously
    # one-valued.
    assert all(len(set(row)) == 1 for row in rows) and {row[0] for row in rows} == {True, False}


def test_importing_this_module_does_not_import_the_core():
    """`authz` stays stdlib-only at module load, so importing it cannot fail or

    slow down on a deployment without the access release — and the PS-140 static
    symbol gate never sees a dependency that is genuinely optional.

    A SUBPROCESS, because an in-process check would be order-dependent: any other
    test in the session that imports the core would make this pass regardless of
    what this module does.
    """
    # Arrange
    code = (
        "import sys, scitex_app.authz; "
        "print('scitex_dev' in sys.modules or 'scitex_dev.access' in sys.modules)"
    )
    # Act
    completed = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True, check=False
    )
    # Assert
    assert (completed.returncode, completed.stdout.strip()) == (0, "False")


# ─── can(): the decision arms. These need scitex_dev.access. ────────────────


@pytest.fixture(scope="module")
def _core():
    """The access core, or a named skip — mirrors test_access_django.py's guard.

    The skip is live for any environment whose scitex-dev predates the access
    release (the `dev` group's floor is ``scitex-dev>=0.11.7``). Under
    SCITEX_ACCESS_STRICT=1, tests/scitex_app/conftest.py upgrades it to a
    FAILURE, which is how the authoritative job proves these arms RAN.
    """
    try:
        from scitex_dev import access as core
    except ImportError:
        pytest.skip(
            "scitex_dev.access not installed — the decision arms cannot run "
            "against the core (pip install -U scitex-dev)."
        )
    return core


#: A kind this file registers itself, through the core's own seam, so the arms
#: depend on NO package's entry point being installed.
_KIND = "authz.testdoc"


def _kinds(core):
    """A one-kind registry, built through the core's own extension point."""

    def provide():
        return [
            core.KindSpec(
                name=_KIND,
                path_prefix="/",
                actions={"view": "read", "edit": "write", "share": "admin"},
            )
        ]

    return core.discover_kinds(include_entry_points=False, extra_providers=[provide])


def _world(core):
    """The one resource and the three principals every arm below reasons over."""
    alice = core.Principal.parse("user:alice")
    return alice, core.Resource(kind=_KIND, path="/users/alice/d1", owner=alice)


def test_can_allows_the_owner(_core):
    """The baseline the rest are measured against: with no grants and no
    memberships, the owner still holds admin."""
    # Arrange
    alice, resource = _world(_core)
    # Act
    verdict = can(alice, "edit", resource, state=ResolveState.RESOLVED, kinds=_kinds(_core))
    # Assert
    assert verdict.to_dict() == {"kind": ALLOWED}


def test_can_denies_a_signed_in_stranger(_core):
    """A denial, NOT a sign-in prompt: this user is already signed in, so
    offering a route would tell them to do something that cannot help."""
    # Arrange
    _alice, resource = _world(_core)
    bob = _core.Principal.parse("user:bob")
    # Act
    verdict = can(bob, "view", resource, state=ResolveState.RESOLVED, kinds=_kinds(_core))
    # Assert
    assert verdict.to_dict() == {"kind": DENIED}


def test_can_asks_an_anonymous_actor_to_sign_in(_core):
    """The core decides this from the principal alone, and can() must carry its
    sign-in route out — the payload that keeps the component from hardcoding
    one."""
    # Arrange
    _alice, resource = _world(_core)
    anonymous = _core.Principal.parse("anonymous")
    # Act
    verdict = can(
        anonymous,
        "view",
        resource,
        state=ResolveState.RESOLVED,
        kinds=_kinds(_core),
        sign_in_url="/accounts/signin/",
    )
    # Assert
    assert verdict.to_dict() == {
        "kind": DENIED_NOT_SIGNED_IN,
        "sign_in_url": "/accounts/signin/",
    }


def test_a_not_signed_in_verdict_without_a_route_is_refused(_core):
    """Omitting the one payload that kind requires fails LOUD, out of the
    validator that owns the rule — it is never invented here."""
    # Arrange
    _alice, resource = _world(_core)
    anonymous = _core.Principal.parse("anonymous")
    # Act
    error = None
    try:
        can(anonymous, "view", resource, state=ResolveState.RESOLVED, kinds=_kinds(_core))
    except VerdictError as exc:
        error = exc
    # Assert
    assert error is not None


def test_can_honours_an_explicit_grant(_core):
    """The rules are the CORE's, not a second implementation: a grant the core
    admits must be admitted through can() too."""
    # Arrange
    _alice, resource = _world(_core)
    bob = _core.Principal.parse("user:bob")
    grant = _core.Grant(bob, "read", resource.ref)
    # Act
    verdict = can(
        bob, "view", resource, state=ResolveState.RESOLVED, kinds=_kinds(_core),
        grants=[grant], memberships=[],
    )
    # Assert
    assert verdict.to_dict() == {"kind": ALLOWED}


def test_can_carries_an_entitlement_denial_from_an_adapter(_core):
    """ENTITLEMENT IS THE ONE KIND check() CANNOT PRODUCE — it is a plan the HUB
    knows, so an enforcer that consulted the hub hands its own decision through
    the same mapping. Without this arm one of the five kinds would be
    unreachable from the primitive."""
    # Arrange
    alice, resource = _world(_core)
    decision = _core.AccessDecision(
        request=_core.AccessRequest(principal=alice, action="edit", resource=resource.ref),
        reason=_core.Reason.NOT_ENTITLED,
        detail="needs the pro plan",
        hint="upgrade",
    )
    # Act
    verdict = verdict_from_decision(decision, entitlement="pro", upgrade_url="/pricing/")
    # Assert
    assert verdict.to_dict() == {
        "kind": DENIED_NOT_ENTITLED,
        "entitlement": "pro",
        "upgrade_url": "/pricing/",
    }


def test_a_payload_the_deciding_kind_does_not_carry_is_not_forwarded(_core):
    """A render path that has its deployment's routes in hand can pass them on
    EVERY call without knowing the verdict in advance — so a payload that does
    not apply must not reach the verdict, and must not be an error either.

    Both halves matter: forwarding it would put a sign-in route on a page that
    is not about signing in, and refusing the call would make the natural call
    site illegal.
    """
    # Arrange
    alice, resource = _world(_core)
    decision = _core.check(alice, "edit", resource, grants=[], memberships=[], kinds=_kinds(_core))
    # Act
    verdict = verdict_from_decision(decision, sign_in_url="/accounts/signin/", upgrade_url="/pricing/")
    # Assert
    assert verdict.to_dict() == {"kind": ALLOWED}


def test_the_core_decision_kinds_are_the_verdict_kinds(_core):
    """THE DRIFT GATE. The mapping in verdict_from_decision is an identity on
    `kind`, which is only safe while the two vocabularies are literally the same
    strings — across a package boundary, in two repositories, with nothing else
    in between to say why.

    This is the arm that fails the day one side renames, and it fails HERE
    rather than at scitex-ui's exhaustive switch.
    """
    # Arrange
    # Act
    core_kinds = {member.value for member in _core.DecisionKind}
    # Assert
    assert core_kinds == set(VERDICT_KINDS)


# ─── scope_for(): the LIST path. Contract arms first — these need no core. ──
#
# `can()` answers about ONE resource; `scope_for()` answers about a LIST, and
# the value it returns exists to keep "there are no rows for you" apart from "we
# could not find out who you are". The contract arms hold that apart with no
# core installed; the decision arms then hold the row RULE to the core's own
# filter rather than to a hand-written expectation.


def test_a_scope_refuses_an_unknown_kind():
    """A row-set whose answer is not one of the five is not an answer.

    `DataScope` validates against `VERDICT_KINDS` — the same tuple the drift
    gate pins to the core's `DecisionKind` — so a sixth kind has to become a
    conversation with scitex-ui on BOTH surfaces rather than a branch one of
    them grows alone.
    """
    # Arrange
    error = None
    # Act
    try:
        DataScope(kind="probably-fine", access_filter=object())
    except ScopeError as exc:
        error = exc
    # Assert
    assert error is not None


def test_an_allowed_scope_requires_a_filter():
    """`allowed` with nothing to filter by is not a state an app can act on: it
    would have to either show every row or guess, and both are the bug class this
    type removes."""
    # Arrange
    error = None
    # Act
    try:
        DataScope(kind=ALLOWED)
    except ScopeError as exc:
        error = exc
    # Assert
    assert error is not None


def test_a_non_allowed_scope_must_not_carry_a_filter():
    """BOTH DIRECTIONS, like `Verdict`'s payload rule, and this is the direction
    that matters: a filter on `unresolved` would be USED, and using it renders
    "nobody checked" as "you have no content"."""
    # Arrange
    error = None
    # Act
    try:
        DataScope(kind=UNRESOLVED, access_filter=object())
    except ScopeError as exc:
        error = exc
    # Assert
    assert error is not None


def _scope_assignment_outcome(scope):
    """Try to mutate a scope; return the exception raised, or None.

    ``setattr`` rather than an attribute assignment so the intent — "is this
    frozen?" — is what is being tested, not the attribute's type.
    """
    try:
        setattr(scope, "access_filter", object())
    except Exception as exc:  # frozen dataclasses raise FrozenInstanceError
        return exc
    return None


def test_a_scope_cannot_be_edited_after_construction():
    """A scope is a fact about a moment; a caller able to edit one could turn
    four non-allowed kinds into an allowed one by assignment."""
    # Arrange
    scope = DataScope(kind=UNRESOLVED)
    # Act
    outcome = _scope_assignment_outcome(scope)
    # Assert
    assert outcome is not None


def test_there_is_no_allowed_boolean_property_on_a_scope():
    """The same prohibition as `Verdict`, and it bites harder here: on a LIST
    `if scope.allowed:` makes "we could not decide" indistinguishable from
    "nothing for you" — the two states a sign-in failure and an empty account
    produce, which is exactly the incident this primitive exists to stop."""
    # Arrange
    # Act
    has_allowed = hasattr(DataScope(kind=UNRESOLVED), "allowed")
    # Assert
    assert has_allowed is False


def test_scope_for_raises_before_anything_is_resolved():
    """ONE resolve-before-render contract, so the list path raises for the same
    violation the single-resource path raises for. Returning a scope here would
    let a bug render as a correct-looking empty list — silently, and forever.

    `_exploding_importer` proves the core is never consulted: a caller who never
    resolved has nothing to ask it about.
    """
    # Arrange
    # Act
    error = None
    try:
        scope_for(
            object(),
            "view",
            _KIND,
            state=ResolveState.NOT_ATTEMPTED,
            importer=_exploding_importer,
        )
    except ResolveNotAttemptedError as exc:
        error = exc
    # Assert
    assert error is not None


def test_the_scope_contract_violation_is_the_single_resource_one():
    """The same CLASS, not a parallel one: an app that already handles the
    verdict-side violation needs no second except clause, which is what makes
    this one contract rather than two that drift."""
    # Arrange
    # Act
    raised = None
    try:
        scope_for(
            object(),
            "view",
            _KIND,
            state=ResolveState.NOT_ATTEMPTED,
            importer=_exploding_importer,
        )
    except VerdictError as exc:
        raised = exc
    # Assert
    assert isinstance(raised, ResolveNotAttemptedError)


def test_a_failed_resolution_yields_unresolved_with_no_filter():
    """FAILED RETURNS rather than raising — a hub that is unreachable is a real
    operating state the screen must still draw — and it returns the FAIL-CLOSED
    shape: `unresolved` carries no filter, so an app cannot query with it."""
    # Arrange
    # Act
    scope = scope_for(
        object(),
        "view",
        _KIND,
        state=ResolveState.FAILED,
        importer=_exploding_importer,
    )
    # Assert
    assert (scope.kind, scope.access_filter) == (UNRESOLVED, None)


def test_a_failed_resolution_carries_the_same_kind_on_both_surfaces():
    """THE DRIFT GATE BETWEEN THE TWO PATHS. `can()` and `scope_for()` fail the
    same way — a hub that is unreachable is unreachable for a detail page too —
    so one renderer branch must cover both, and a LIST must not invent a
    different answer for a state the detail page already names.

    Asserted as an EQUALITY between the two surfaces rather than against the
    literal `unresolved`, and that is not stylistic: the literal version passed
    under calibration, when `scope_for` was made to fail OPEN (an allowed, empty
    row set) on a failed resolution — an arm that cannot fail measures nothing.
    """
    # Arrange
    # Act
    from_a_list = scope_for(
        object(), "view", _KIND, state=ResolveState.FAILED, importer=_exploding_importer
    ).kind
    from_one_resource = can(
        object(), "view", object(), state=ResolveState.FAILED, importer=_exploding_importer
    ).kind
    # Assert
    assert (from_a_list, from_one_resource) == (UNRESOLVED, UNRESOLVED)


def test_scope_for_refuses_by_name_when_the_core_is_not_installed():
    """An install that CANNOT decide must not look like one that decided "no
    rows for you": only one of those is fixed by configuring something, and an
    empty list is the one of the two a developer does not investigate."""
    # Arrange
    # Act
    error = None
    try:
        scope_for(
            object(), "view", _KIND, state=ResolveState.RESOLVED, importer=_absent_importer
        )
    except AccessPrimitiveMissingError as exc:
        error = exc
    # Assert
    assert error is not None


def test_the_scope_missing_core_refusal_names_the_fix():
    """A named error whose message does not say what to install is a diagnosis
    without a remedy, and the reader is a developer at a shell."""
    # Arrange
    # Act
    error = None
    try:
        scope_for(
            object(), "view", _KIND, state=ResolveState.RESOLVED, importer=_absent_importer
        )
    except AccessPrimitiveMissingError as exc:
        error = exc
    # Assert
    assert "scitex-dev" in str(error)


def test_scope_from_decision_requires_a_filter_for_allowed():
    """The mapping must not INVENT a row set. An enforcer that decided `allowed`
    and did not bring a filter has not answered the list question, and a scope
    built anyway would be a claim nobody made."""
    # Arrange
    class _Decision:
        kind = type("_K", (), {"value": ALLOWED})()

    error = None
    # Act
    try:
        scope_from_decision(_Decision())
    except ScopeError as exc:
        error = exc
    # Assert
    assert error is not None


def test_scope_from_decision_withholds_a_filter_from_a_non_allowed_kind():
    """The pass-through rule, mirroring `verdict_from_decision`'s payload rule:
    a render path holding its grants already can pass the filter on every call,
    because a filter the deciding kind does not carry is forwarded nowhere
    rather than being refused (which would make the natural call site illegal)."""
    # Arrange
    class _Decision:
        kind = type("_K", (), {"value": DENIED_NOT_ENTITLED})()

    # Act
    scope = scope_from_decision(_Decision(), access_filter=object())
    # Assert
    assert (scope.kind, scope.access_filter) == (DENIED_NOT_ENTITLED, None)


# --- scope_for(): the decision arms. These need scitex_dev.access. ---------


@pytest.fixture(scope="module")
def _fixtures(_core):
    """The core's random-fixture generator, imported dynamically.

    A separate fixture rather than ``_core.testing``: ``scitex_dev.access`` does
    not import its ``testing`` submodule, so reaching it through the core module
    would depend on some other test having imported it first — an
    order-dependent arm, which is the thing this suite's guards exist to avoid.
    Imported by CALL rather than by a static ``import`` statement because the
    core is an optional runtime dependency of this package, and that is the same
    discipline every source module here follows.
    """
    return importlib.import_module("scitex_dev.access.testing")


def _filter_fields(access_filter):
    """Every documented ``AccessFilter`` field, as a comparable tuple.

    Field-by-field rather than ``==`` on the object, so the assertion stays
    meaningful if the core ever gives ``AccessFilter`` a custom ``__eq__``. The
    same helper, for the same reason, as tests/scitex_app/api_access/.
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


def test_the_scope_filter_is_the_cores_own_filter(_core, _fixtures):
    """NOT A SECOND IMPLEMENTATION, asserted rather than asserted-about-in-prose.

    The returned filter is field-identical to ``accessible()``'s over the core's
    own random fixtures and every principal they mention. This is what licenses
    the two documented downstreams to keep working unchanged — ``core.select()``
    in memory and ``scitex_app.access_django.to_q()`` for a queryset, whose Q
    proof lives in that suite — because the thing they receive is literally the
    core's object, not a lookalike.
    """
    # Arrange
    core, testing = _core, _fixtures
    mismatches = []
    examined = 0
    # Act
    for seed in range(6):
        fixture = testing.random_fixture(seed)
        for principal in testing.askers_of(fixture):
            for spec in fixture.kinds.values():
                for action in sorted(spec.actions):
                    scope = scope_for(
                        principal,
                        action,
                        spec.name,
                        state=ResolveState.RESOLVED,
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
                    examined += 1
                    if _filter_fields(scope.access_filter) != _filter_fields(theirs):
                        mismatches.append((seed, str(principal), spec.name, action))
    # Assert
    assert mismatches == [] and examined > 0


def test_the_scope_filter_admits_exactly_what_check_allows(_core, _fixtures):
    """THE ROW-LEVEL PROOF, and the reason the two surfaces cannot drift: a
    filter is a claim about MANY rows, `check()` is a decision about ONE, and
    the whole point of the primitive is that a list shows what a detail page
    would let you open. For every principal the fixture mentions, every kind and
    every action, the refs the filter admits must equal the refs `check()`
    allows — resource by resource, in both directions.
    """
    # Arrange
    core, testing = _core, _fixtures
    mismatches = []
    examined = 0
    # Act
    for seed in range(6):
        fixture = testing.random_fixture(seed)
        for spec in fixture.kinds.values():
            resources = [r for r in fixture.resources if r.kind == spec.name]
            for principal in testing.askers_of(fixture):
                for action in sorted(spec.actions):
                    scope = scope_for(
                        principal,
                        action,
                        spec.name,
                        state=ResolveState.RESOLVED,
                        grants=fixture.grants,
                        memberships=fixture.memberships,
                        kinds=fixture.kinds,
                    )
                    admitted = {
                        r.ref for r in core.select(scope.access_filter, resources)
                    }
                    for resource in resources:
                        allowed = core.check(
                            principal,
                            action,
                            resource,
                            grants=fixture.grants,
                            memberships=fixture.memberships,
                            kinds=fixture.kinds,
                        ).is_allowed
                        examined += 1
                        if allowed != (resource.ref in admitted):
                            mismatches.append(
                                (seed, str(principal), spec.name, action, resource.ref)
                            )
    # Assert
    assert mismatches == [] and examined > 0


def test_a_stranger_gets_an_allowed_scope_that_admits_nothing(_core):
    """THE DISTINCTION THE TYPE EXISTS FOR, on a real decision. A signed-in
    stranger is not an error and not a denial of a LIST — they are allowed to
    ask, and the answer is an empty row set. That must be a DIFFERENT value from
    the unresolved one, because "no content for you" and "nobody checked" are
    rendered differently and only one of them is fixed by retrying."""
    # Arrange
    core = _core
    alice = core.Principal.parse("user:alice")
    bob = core.Principal.parse("user:bob")
    resource = core.Resource(kind=_KIND, path="/users/alice/d1", owner=alice)
    # Act
    scope = scope_for(bob, "view", _KIND, state=ResolveState.RESOLVED, kinds=_kinds(core))
    # Assert
    assert (scope.kind, core.select(scope.access_filter, [resource])) == (ALLOWED, [])


def test_an_unsigned_in_actor_gets_public_rows_only(_core):
    """The core's public rule reaches the list path unchanged: read-tier public
    is visible to everyone, signed in or not — so an anonymous actor gets a
    NON-EMPTY allowed scope here. Worth pinning because "anonymous therefore
    sees nothing" is the plausible-looking assumption that would make this
    module's fail-closed discipline look like the whole story, and it is false.
    """
    # Arrange
    core = _core
    alice = core.Principal.parse("user:alice")
    anonymous = core.Principal.parse("anonymous")
    private = core.Resource(kind=_KIND, path="/users/alice/d1", owner=alice)
    public = core.Resource(
        kind=_KIND, path="/users/alice/d2", owner=alice, visibility="public"
    )
    # Act
    scope = scope_for(
        anonymous, "view", _KIND, state=ResolveState.RESOLVED, kinds=_kinds(core)
    )
    # Assert
    assert core.select(scope.access_filter, [private, public]) == [public]


def test_an_unregistered_kind_is_unresolved_and_carries_no_filter(_core):
    """NOT AN EXCEPTION, and not "allowed, empty". The core raises
    ``AccessUnresolved`` because it has no filter to return; this note HAS a
    value to return, and the core's own vocabulary already answers this case
    (``check()`` reports ``kind-unregistered`` as ``unresolved``). Translating
    it to anything else would make the list surface and the detail surface
    disagree about the SAME deployment."""
    # Arrange
    core = _core
    alice = core.Principal.parse("user:alice")
    # Act
    scope = scope_for(
        alice, "view", "authz.no-such-kind", state=ResolveState.RESOLVED, kinds=_kinds(core)
    )
    # Assert
    assert (scope.kind, scope.access_filter) == (UNRESOLVED, None)


def test_an_agents_scope_is_capped_by_its_owner(_core):
    """THE INTERSECTION RULE, on the case scitex-cards nominated as canonical: a
    card can be owned by a user and assigned to an agent, so the agent's reach
    must never exceed its owner's.

    BOTH DIRECTIONS IN ONE ASSERTION, deliberately: without the control (owner
    granted too) an arm that admitted nothing at all would pass, and an arm that
    cannot admit anything measures nothing.
    """
    # Arrange
    core = _core
    kinds = _kinds(core)
    alice = core.Principal.parse("user:alice")
    bot = core.Principal.parse("agent:alice/bot")
    bob = core.Principal.parse("user:bob")
    resource = core.Resource(kind=_KIND, path="/users/bob/d9", owner=bob)
    delegated = core.Grant(principal=bot, role="write", target=resource.ref)
    owner_too = core.Grant(principal=alice, role="write", target=resource.ref)
    # Act
    def admitted(grants):
        scope = scope_for(
            bot, "edit", _KIND, state=ResolveState.RESOLVED, grants=grants, kinds=kinds
        )
        return core.select(scope.access_filter, [resource])

    # Assert
    assert (admitted([delegated]), admitted([delegated, owner_too])) == ([], [resource])


# EOF
