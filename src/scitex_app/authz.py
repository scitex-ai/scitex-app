"""The answer to "may this actor do this?" — as a value, not a boolean.

`can()` IS NOT HERE YET. This module ships the VERDICT it will return, because
scitex-ui is building the display side against a shape agreed in conversation,
and a contract that lives only in a message thread drifts. Shipping the type
makes their fixtures real rather than a transcription of prose.

WHY A TAGGED VALUE RATHER THAN A BOOLEAN. Four things a caller must be able to
tell apart, and only one of them means "no, and nothing you do changes that":

    allowed                        yes
    denied                         no, and signing in would not help
    denied-because-not-signed-in   sign in, then ask again
    denied-because-not-entitled    signed in, lacks the entitlement THIS hub
                                   requires

A boolean collapses the last three into one, and the UI then has to reconstruct
which it was — from a message string, or from state it fetches separately. Two
places would know the reason, and they would disagree eventually. That is the
drift the single-home rule exists to prevent, so the reason travels WITH the
answer.

WHY THE PAYLOAD TRAVELS TOO. `denied-because-not-signed-in` without a sign-in
URL means the component hardcodes a route or the app passes it alongside — and
then two places know where sign-in lives. Same argument, one level down.

THE VERDICT CROSSES A PACKAGE BOUNDARY, so it is plain data. scitex-ui renders
it and MUST NOT depend on scitex-app: a UI package importing the state package
is the mirror of "the CLI and MCP surfaces must not pull scitex-ui", and
accepting one while breaking the other turns a boundary into a cycle. Hence
`to_dict()`, and hence nothing here needs scitex-app installed to be understood.

NOT DECIDED HERE, deliberately: HOW entitlement is determined. scitex-app stores
no plan, no tier, no price — it asks the hub's token API and reports the answer.
A paywall compiled into the SDK would put one deployment's commercial policy
into every self-hosted install.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

#: The four answers. `kind` is always exactly one of these.
ALLOWED = "allowed"
DENIED = "denied"
DENIED_NOT_SIGNED_IN = "denied-because-not-signed-in"
DENIED_NOT_ENTITLED = "denied-because-not-entitled"

VERDICT_KINDS = (ALLOWED, DENIED, DENIED_NOT_SIGNED_IN, DENIED_NOT_ENTITLED)

# Which kinds carry which payload. The validator enforces BOTH directions --
# present when required, and absent when not -- because "denied carries nothing"
# is a promise about what reaches a page, not a stylistic preference.
_REQUIRES_SIGN_IN_URL = (DENIED_NOT_SIGNED_IN,)
_REQUIRES_ENTITLEMENT = (DENIED_NOT_ENTITLED,)

# PERMITS, not REQUIRES — and the difference is the contract.
#
# `sign_in_url` is REQUIRED on its kind: sign-in always exists, so its absence
# would be a bug and scitex-ui writes no defensive branch for it.
#
# `upgrade_url` is OPTIONAL, because a self-hosted hub may sell nothing and have
# no upgrade surface at all. That makes ABSENCE a normal case, so the contract
# has to say what absence MEANS — otherwise a consumer seeing no url cannot tell
# "there is nowhere to send you" from "we have not found out yet", and will pick
# one. scitex-ui asked for this to be pinned before they wire their route.
#
#     ABSENT  ==  this hub has no upgrade surface configured. Render inert:
#                 state the entitlement, offer no action.
#     ABSENT  !=  "not yet resolved". An unresolved verdict is not this kind at
#                 all — that is the `unresolved` kind agreed with scitex-ui on
#                 2026-09-04, and conflating them here would put the same
#                 three-value collapse back one layer down.
_PERMITS_UPGRADE_URL = (DENIED_NOT_ENTITLED,)


class VerdictError(ValueError):
    """A verdict was constructed that cannot mean anything.

    Raised where the verdict is BUILT rather than where it is read, so a
    malformed answer fails in the code that produced it instead of three layers
    downstream in a template.
    """


@dataclass(frozen=True)
class Verdict:
    """One authorization answer. Always this shape; `kind` is the discriminant.

    Frozen because a verdict is a fact about a moment, and a caller that can
    edit one can turn a denial into an approval by assignment.

    THERE IS DELIBERATELY NO `.allowed` BOOLEAN PROPERTY. It would be one
    character shorter than `verdict.kind == ALLOWED` and would reintroduce
    exactly the collapse this type exists to prevent: `if verdict.allowed:`
    reads naturally, passes review, and silently treats "sign in first" as
    identical to "never". Callers that genuinely want a two-way branch should
    write the comparison and see themselves doing it.
    """

    kind: str
    sign_in_url: Optional[str] = None
    entitlement: Optional[str] = None
    upgrade_url: Optional[str] = None

    def __post_init__(self) -> None:
        if self.kind not in VERDICT_KINDS:
            raise VerdictError(
                f"unknown verdict kind {self.kind!r}; "
                f"expected one of {', '.join(VERDICT_KINDS)}"
            )

        needs_url = self.kind in _REQUIRES_SIGN_IN_URL
        if needs_url and not self.sign_in_url:
            raise VerdictError(
                f"{self.kind} requires sign_in_url — without it the caller "
                "has to know where sign-in lives, which is the duplication "
                "this payload exists to avoid"
            )
        if not needs_url and self.sign_in_url is not None:
            raise VerdictError(
                f"{self.kind} must not carry sign_in_url — offering a route "
                "on a verdict that is not about signing in tells the user to "
                "do something that will not help"
            )

        needs_entitlement = self.kind in _REQUIRES_ENTITLEMENT
        if needs_entitlement and not self.entitlement:
            raise VerdictError(
                f"{self.kind} requires entitlement — naming which one is "
                "missing is the whole difference from a plain denial"
            )
        if not needs_entitlement and self.entitlement is not None:
            raise VerdictError(f"{self.kind} must not carry entitlement")

        # One-directional on purpose: refused where it does not belong, never
        # required where it does. See _PERMITS_UPGRADE_URL.
        if self.kind not in _PERMITS_UPGRADE_URL and self.upgrade_url is not None:
            raise VerdictError(
                f"{self.kind} must not carry upgrade_url — an upgrade route "
                "only means anything on a verdict that says an entitlement is "
                "what is missing"
            )

    def to_dict(self) -> dict[str, Any]:
        """Plain JSON-safe data for the far side of a package boundary.

        Absent payload keys are OMITTED rather than sent as null, so the
        serialised form matches the type exactly: a key present means it
        applies. A `null` would make every consumer write a truthiness check
        where the kind already answered the question.
        """
        out: dict[str, Any] = {"kind": self.kind}
        if self.sign_in_url is not None:
            out["sign_in_url"] = self.sign_in_url
        if self.entitlement is not None:
            out["entitlement"] = self.entitlement
        if self.upgrade_url is not None:
            out["upgrade_url"] = self.upgrade_url
        return out


def allowed() -> Verdict:
    """Yes."""
    return Verdict(kind=ALLOWED)


def denied() -> Verdict:
    """No, and nothing the user can do changes it.

    Carries no payload BY CONSTRUCTION, not by convention: there is no route to
    access, so a verdict that hinted at one would be a lie rendered into a page.
    """
    return Verdict(kind=DENIED)


def denied_not_signed_in(sign_in_url: str) -> Verdict:
    """No, but signing in would change the answer."""
    return Verdict(kind=DENIED_NOT_SIGNED_IN, sign_in_url=sign_in_url)


def denied_not_entitled(
    entitlement: str, upgrade_url: Optional[str] = None
) -> Verdict:
    """Signed in, but lacking the entitlement THIS hub requires.

    `entitlement` is an IDENTIFIER naming what is missing. Confirmed with
    scitex-hub 2026-09-04: it names a PLAN-shaped requirement — the plan id or
    tier string their entitlement API returns — and never a token SCOPE. Their
    scopes (`*`, `api`, `mcp`, `publish`) say what a token may do on a user's
    behalf; entitlement is a property of the user's subscription, independent
    of which token they presented.

    An earlier version of this docstring said "never a plan name", which read
    as a prohibition on the very thing hub says belongs here. The intent was
    narrower and is restated: an IDENTIFIER, not a DISPLAY NAME and not a
    price. `pro` yes; "Pro Plus — $20/mo" no. scitex-ui renders a sentence from
    the kind; it does not render commercial policy.

    `upgrade_url` is OPTIONAL and its ABSENCE IS MEANINGFUL — see
    _PERMITS_UPGRADE_URL. Absent means this hub has no upgrade surface
    configured, so render inert; it never means "not yet resolved".

    On scitex.ai it is the pricing page. Note what that page deliberately is
    NOT: hub's `billing_checkout` is a POST target, not somewhere a user can be
    sent, and filling this with it would hand scitex-ui a route that cannot be
    followed. The value is supplied BY THE HUB rather than built here, because
    the hub URL is configurable and a self-hosted deployment's answer differs.

    WORTH KNOWING WHEN READING FINDINGS: as of 2026-09-04 hub sells no plan
    (`BILLING_PLANS=[]` on prod, pending Stripe review), so every user is
    currently unentitled for paid features. This kind is therefore the MAJORITY
    path today, not a rare edge — which is precisely why it must render as
    not-entitled rather than as a plain denial. "You need a plan that does not
    exist yet" is recoverable information; "no" is not.
    """
    return Verdict(
        kind=DENIED_NOT_ENTITLED,
        entitlement=entitlement,
        upgrade_url=upgrade_url,
    )


__all__ = [
    "ALLOWED",
    "DENIED",
    "DENIED_NOT_ENTITLED",
    "DENIED_NOT_SIGNED_IN",
    "VERDICT_KINDS",
    "Verdict",
    "VerdictError",
    "allowed",
    "denied",
    "denied_not_entitled",
    "denied_not_signed_in",
]

# EOF
