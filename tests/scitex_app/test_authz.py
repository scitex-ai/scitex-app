"""Tests for scitex_app/authz.py — the verdict type.

One assertion each. Every rule here is a promise made to scitex-ui before they
wrote their display component, so each arm names the promise it holds.
"""

from __future__ import annotations

from scitex_app.authz import (
    ALLOWED,
    DENIED,
    DENIED_NOT_ENTITLED,
    DENIED_NOT_SIGNED_IN,
    VERDICT_KINDS,
    ResolveState,
    Verdict,
    VerdictError,
    allowed,
    denied,
    denied_not_entitled,
    denied_not_signed_in,
)


# ─── the four kinds, and that there are exactly four ────────────────────────


def test_there_are_exactly_four_kinds():
    """A fifth is REQUIRED the moment a verdict is fetched client-side.

    Adding one is a deliberate, coordinated change — scitex-ui's switch is
    exhaustive over these — so this asserts the count rather than leaving a
    fifth to appear quietly.
    """
    # Arrange
    # Act
    count = len(VERDICT_KINDS)
    # Assert
    assert count == 4


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


# EOF
