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


# EOF
