"""The answer to "may this actor do this?" — as a value, not a boolean.

TWO QUESTIONS, ONE VOCABULARY. `can()` answers for ONE resource ("may this
actor do this?") and `scope_for()` answers for a LIST ("which rows may this
actor see?"). Both return a value carrying the same five kinds — this module
ships the VERDICT those answers are expressed in, because scitex-ui is building
the display side against a shape agreed in conversation, and a contract that
lives only in a message thread drifts. Shipping the type makes their fixtures
real rather than a transcription of prose.

WHY A TAGGED VALUE RATHER THAN A BOOLEAN. Five things a caller must be able to
tell apart, and only one of them means "no, and nothing you do changes that":

    allowed                        yes
    denied                         no, and signing in would not help
    denied-because-not-signed-in   sign in, then ask again
    denied-because-not-entitled    signed in, lacks the entitlement THIS hub
                                   requires
    unresolved                     WE DO NOT KNOW. Resolution was attempted and
                                   failed. Not a denial, and must never be
                                   rendered as one.

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

import scitex_logging as slogging
import importlib
import os
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from enum import Enum
from types import ModuleType
from typing import Any, Optional

log = slogging.getLogger(__name__)

#: The five answers. `kind` is always exactly one of these.
ALLOWED = "allowed"
DENIED = "denied"
DENIED_NOT_SIGNED_IN = "denied-because-not-signed-in"
DENIED_NOT_ENTITLED = "denied-because-not-entitled"

#: WE DO NOT KNOW. Added 2026-09-05, jointly with scitex-ui, because the
#: implementation required it and not before -- `can()` is committed
#: SYNCHRONOUS AND TOTAL, so when an input was resolved and resolution FAILED
#: there has to be a value to return. Without this kind that case has none.
#:
#: ONE `unresolved`, never one per axis. Which input was unresolved does not
#: change what the UI does -- don't assert, don't offer a route, say "not yet
#: known" -- and a kind per axis would grow this enum without bound, breaking
#: scitex-ui's exhaustive switch on every addition. Capped at five.
#:
#: NOT the same as any denial. denied-because-not-signed-in asserts the user is
#: signed OUT, which is a claim we do not have when resolution failed.
UNRESOLVED = "unresolved"

VERDICT_KINDS = (
    ALLOWED,
    DENIED,
    DENIED_NOT_SIGNED_IN,
    DENIED_NOT_ENTITLED,
    UNRESOLVED,
)

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


def unresolved() -> Verdict:
    """We do not know: resolution was attempted and did not succeed.

    Carries NO payload, and the validator refuses one FOR FREE -- every payload
    arm is written as an exclusion, so a kind absent from the _REQUIRES_ /
    _PERMITS_ tuples lands in the refusing branch by default. Measured before
    this kind existed rather than assumed, with a control: the same upgrade_url
    is still ACCEPTED on DENIED_NOT_ENTITLED, so the refusals mean something.

    WHAT MUST NOT TRAVEL HERE IS THE REASON -- timeout, misconfiguration,
    network. It does not change what the UI renders, and naming it discloses
    that the service behind this gate is currently down, to a reader who is not
    authenticated to it. Same argument that kept the unresolved AXIS NAME out
    of the DOM. A server-side log is where that belongs.

    NOT FOR A CALLER WHO NEVER RESOLVED AT ALL. That is a contract violation --
    "resolve before render" is the documented step -- and `can()` must RAISE,
    so a BUG is not rendered as a legitimate "not yet known" UI forever.
    `ResolveState` is what tells the two apart: NOT_ATTEMPTED raises, FAILED
    returns this.
    """
    return Verdict(kind=UNRESOLVED)


# ─── resolving the inputs a verdict is computed FROM ────────────────────────
#
# NOT PART OF THE VERDICT CONTRACT. `Verdict` crosses a package boundary as
# plain data; this does not cross anything. It describes how far `can()`'s
# CALLER got in resolving auth and entitlement before asking, and it exists
# only inside this package.


class ResolveState(Enum):
    """How far resolution got. THREE-valued, and the third value is the point.

    `can()` is synchronous and total: it answers from state already resolved,
    and resolving is an explicit step BEFORE it. So `can()` must be able to
    tell apart two situations that a "value, or None" field renders identical:

        NOT_ATTEMPTED   the caller never resolved. A CONTRACT VIOLATION --
                        "resolve before render" is the documented step. can()
                        RAISES, because returning an `unresolved` verdict here
                        would render a BUG as a legitimate "not yet known" UI,
                        permanently and invisibly.

        FAILED          resolution was attempted and did not succeed -- hub
                        unreachable, timeout, 5xx. NOT a bug; a real operating
                        state, and the screen must still draw something. can()
                        RETURNS a verdict, because raising here pushes every
                        app author into try/except writing their own
                        unknown-display, scattering the judgement this module
                        exists to hold in one place.

        RESOLVED        an answer is available.

    Held as "a value, or None", NOT_ATTEMPTED and FAILED become the same state
    and that whole split silently becomes unimplementable. Agreed with
    scitex-ui 2026-09-04; guarded since by a tripwire in this module's tests
    that was written BEFORE this type existed, and which this type is the first
    thing to make substantive.

    WHY AN ENUM AND NOT STRINGS, unlike the verdict kinds directly above. Those
    are strings because they are SERIALISED and read by another language. These
    are not, and must not be: a string state would be one `to_dict()` away from
    leaking "the service behind this gate is currently down" into page source,
    which is availability information about a system the reader is not
    authenticated to. Deliberately not a `str` subclass, so that leak cannot
    happen by accident.

    WHAT THIS TYPE DELIBERATELY DOES NOT DO: carry the resolved VALUE. A
    container pairing state with value (refusing RESOLVED-without-a-value, the
    way `Verdict` refuses a payload on the wrong kind) is the obvious next
    shape and was considered here. It is not built because nothing resolves
    anything yet -- there is no resolver, no hub URL configuration and no token
    storage -- so its fields would be invented rather than observed. Recorded
    as a deliberate omission so the next reader does not have to re-derive it.
    """

    NOT_ATTEMPTED = "not-attempted"
    FAILED = "failed"
    RESOLVED = "resolved"


# ---------------------------------------------------------------------------
# HUB CONFIGURATION. Decomposition item 3, and the DEFAULT IS THE DECISION.
# ---------------------------------------------------------------------------

#: The one environment variable that names this deployment's hub.
HUB_URL_ENV = "SCITEX_APP_HUB_URL"

#: Emitted at most once per process. `warnings`/logging are per-CALL surfaces
#: and `can()` is called per render, so an unconditional warning would fire
#: hundreds of times on one page and be scrolled past — noise that reads as
#: silence. Once, loudly, is what "うるさく失敗する" buys.
_hub_hint_emitted = False


def hub_url(env: Mapping[str, str] | None = None) -> str | None:
    """This deployment's hub, or None meaning THERE IS NO HUB.

    NONE IS THE DEFAULT, AND THAT IS A RULING RATHER THAN A CONVENIENCE.
    Operator, 2026-09-06, via scitex-hub:

        「ハブなしを規定にしてもらってで、うるさく失敗するヒントは出すでいいと思います」
        — make no-hub the default, and it is fine to fail noisily with hints.

    WHY NOT DEFAULT TO THE HOSTED HUB. A default of `https://scitex.ai` makes
    "no hub" UNEXPRESSIBLE BY OMISSION: a self-hosted install that configures
    nothing would contact our service at its first authorization check, chosen
    by nobody. The two failure modes are not symmetric in DETECTABILITY, which
    is the argument that decided it:

        default no-hub, but a hub was wanted
            every hub-dependent action returns `denied`. The operator SEES the
            missing features and goes looking for configuration. Wrong, loud,
            self-correcting.

        default scitex.ai, but isolation was wanted
            it silently contacts us and everything WORKS. The only symptom is
            in a log the install's own operator cannot read. Invisible to
            exactly the person who would care.

    One failure announces itself to whoever can fix it; the other does not.

    AND THE STRUCTURAL REASON, which is this module's whole subject: a non-empty
    default COLLAPSES A THREE-VALUED STATE INTO TWO. "no hub configured", "hub
    configured but unreachable" and "hub configured and answering" must stay
    distinguishable — see `ResolveState` and the `denied` / `unresolved` split.
    Defaulting to a URL makes UNCONFIGURED indistinguishable from CONFIGURED, so
    the honest state stops being representable rather than merely being unusual.

    AN EMPTY OR BLANK VALUE READS AS NO HUB, not as a malformed URL. Setting the
    variable to "" is how an operator says "explicitly none" in a shell profile
    or a compose file where deleting the line is awkward, and treating that as a
    configuration error would punish the person who was being explicit.

    Takes `env` so the resolution is testable without mutating the process —
    a module that reads `os.environ` directly can only be tested by a fixture
    that leaks into every other test in the file.
    """
    source = os.environ if env is None else env
    raw = source.get(HUB_URL_ENV, "")
    stripped = raw.strip()
    return stripped or None


def denied_no_hub(*, action: str | None = None) -> Verdict:
    """The verdict for a hub-dependent action on an install with NO HUB — and
    the noisy hint, on the developer channel only.

    TWO SURFACES, DELIBERATELY SEPARATE, and this function is where the
    separation is enforced rather than described:

        the VERDICT   plain `denied`. Payload-free BY CONSTRUCTION — the
                      dataclass validator refuses one. It crosses into page
                      source as `data-stx-gate` and is read by someone who is
                      not authenticated to this deployment.

        the HINT      a WARNING on this package's logger, naming the variable
                      to set. Never reaches the DOM.

    WHY THE HINT IS NOT IN THE VERDICT, given the ruling asked for hints. The
    audiences differ. The person who installed this and configured nothing can
    act on "set SCITEX_APP_HUB_URL"; a VISITOR to someone else's deployment cannot,
    and putting the reason in the page re-opens the disclosure question settled
    with scitex-ui on 2026-09-05 — a failure reason in page source tells an
    unauthenticated reader something about a service they cannot see.

    The ruling's wording (「ヒントは出す」) does not name an audience. This is my
    reading, recorded so it can be overturned rather than discovered: if the
    intent was that the PAGE VISITOR sees the hint, the payload rule reopens and
    scitex-ui must be in that conversation, because theirs is the component that
    renders the verdict.
    """
    global _hub_hint_emitted
    if not _hub_hint_emitted:
        _hub_hint_emitted = True
        log.warning(
            "no hub is configured, so every hub-dependent action is denied. "
            "This is the DEFAULT: an unconfigured install contacts nothing. "
            "Set %s=<your hub> to enable them, or ignore this if this "
            "deployment is meant to run standalone.%s",
            HUB_URL_ENV,
            f" (first denied action: {action})" if action else "",
        )
    return denied()


def _reset_hub_hint_for_testing() -> None:
    """Clear the once-per-process latch.

    EXISTS ONLY FOR TESTS, and named so that is unmistakable at the call site.
    Without it the second test to assert the hint fires would pass or fail
    depending on which test ran first — an order-dependent suite, which is a
    gate whose result depends on something other than the code under test.
    """
    global _hub_hint_emitted
    _hub_hint_emitted = False


# ---------------------------------------------------------------------------
# CAN(). Everything above this line ships the ANSWER; this asks the question.
# ---------------------------------------------------------------------------
#
# WHY TWO FUNCTIONS AND NOT ONE. `scitex_dev.access.check()` is a PURE function
# of its arguments — no session, no database, no hub — so `can()` can simply
# call it, and that is the ordinary path. What `check()` cannot decide is
# ENTITLEMENT: `Reason.NOT_ENTITLED` exists in the core and NO code path inside
# `check()` produces it, because entitlement is a plan the HUB knows and not a
# token scope (see `denied_not_entitled`). So the decision->verdict mapping is
# factored out as `verdict_from_decision()`, and an entitlement enforcer that
# consulted the hub hands its own `AccessDecision` through the SAME mapping.
# One vocabulary on the far side of the package boundary; two producers, which
# is the truth rather than an inconvenience.

#: The module that carries the decision rules, named once so the
#: absent-dependency predicate and the error message cannot disagree.
CORE_MODULE = "scitex_dev.access"

#: Type of the injectable importer seam. ``Any``-free on purpose: the seam is
#: `str -> ModuleType` and nothing else, so a test cannot pass something that
#: silently changes the contract.
_Importer = Callable[[str], ModuleType]


class AccessPrimitiveMissingError(RuntimeError):
    """``scitex_dev.access`` is not installed, so ``can()`` cannot decide.

    The same shape as :class:`scitex_app.access_django.ScitexDevAccessMissingError`
    and :class:`scitex_app.api_access.AccessCoreMissingError`, for the same
    reason: deciding is UNAVAILABLE rather than silently permissive, and the fix
    is named. Deliberately not an ``ImportError`` — an import failure is what
    happened, not what it means, and a deployment asking \"can this install
    enforce access at all?\" must be able to catch the meaning.
    """

    def __init__(self) -> None:
        super().__init__(
            "scitex_app.authz.can() needs scitex_dev.access to decide an access "
            f"question, and {CORE_MODULE} is not installed. "
            "Run: pip install -U scitex-dev"
        )


class ResolveNotAttemptedError(VerdictError):
    """``can()`` was called before anyone resolved who was asking.

    A CONTRACT VIOLATION rather than a denial, which is why it RAISES. The
    documented step is resolve-then-render, and returning an `unresolved` verdict
    here would render a BUG as a legitimate \"not yet known\" screen — silently
    and permanently, because the bug never surfaces as anything else.
    `ResolveState` exists to keep the two causes of \"unresolved\" apart; this is
    the half that must not be returned.

    A ``VerdictError`` rather than a bare ``ValueError`` so a caller already
    handling \"you built/asked for a verdict wrong\" needs no second except
    clause. It is emphatically NOT a ``Verdict``: nothing about it should reach
    a page.
    """


def _missing_access_primitive(exc: BaseException) -> bool:
    """True only for the \"``scitex_dev.access`` is not installed yet\" case.

    The same narrowness as :func:`scitex_app.access_django._missing_access` and
    :func:`scitex_app.api_access._missing_core`: only a ``ModuleNotFoundError``
    naming the core or its parent module counts as absent. An ``ImportError``
    raised INSIDE an installed core is a REAL failure and propagates instead of
    being laundered into \"not installed\" — which would read as a skip and hide
    a defect. A differential test pins this predicate to its sibling, so \"the
    core is missing\" cannot mean two things in one package.
    """
    return isinstance(exc, ModuleNotFoundError) and getattr(exc, "name", None) in (
        "scitex_dev",
        CORE_MODULE,
    )


def _load_access_primitive(*, importer: _Importer = importlib.import_module) -> ModuleType:
    """Import the core, separating \"not released yet\" from a real failure.

    Via ``importlib.import_module`` — a CALL, not a static ``ImportFrom`` — for
    the same reason ``access_django`` does it: this is a true OPTIONAL runtime
    dependency and must not appear in the package's static symbol list, where it
    would fail on any scitex-dev version that lacks ``access``. ``importer`` is
    the test seam; the default is the real one.
    """
    try:
        return importer(CORE_MODULE)
    except ImportError as exc:  # ModuleNotFoundError is a subclass
        if _missing_access_primitive(exc):
            raise AccessPrimitiveMissingError() from exc
        raise  # a real import failure — do not masquerade it as "absent"


def verdict_from_decision(
    decision: Any,
    *,
    sign_in_url: Optional[str] = None,
    entitlement: Optional[str] = None,
    upgrade_url: Optional[str] = None,
) -> Verdict:
    """Render a core ``AccessDecision`` as this package's ``Verdict``.

    IDENTITY ON KIND, NOT A TRANSLATION TABLE. ``scitex_dev.access.DecisionKind``
    says so in its own words — \"The five answers; the strings match
    scitex_app.authz's Verdict kinds\" — and its members carry these strings
    verbatim, so the kind crosses BY VALUE. A table here would be a second place
    the five names live, and the next rename would have to be made in both.

    WHY THIS IS A FUNCTION AND NOT JUST ``.value``: the two payload-bearing kinds
    cannot be built from the kind alone. `Verdict` REFUSES a not-signed-in
    verdict with no route and a not-entitled verdict with no identifier — its
    validator enforces BOTH directions — so the payload must be supplied by
    whoever knows it. That is the HUB, not this module: a sign-in route or an
    upgrade URL compiled in here would put ONE deployment's routes into every
    self-hosted install, which is the argument `denied_not_entitled` already
    makes for `upgrade_url`. The payload is passed through untouched, so an
    absent one fails LOUD in the validator that owns the rule instead of being
    invented here.

    A payload the deciding kind does NOT carry is FORWARDED NOWHERE — it is not
    attached to the verdict, so the page-facing rule (`Verdict`: a route on a
    denial that is not about signing in tells the user to do something that
    cannot help) still holds, and the natural call site stays legal: a render
    path that has its deployment's routes in hand can pass them on EVERY call
    without first knowing which kind it will get back. Deliberately not an
    error, because such a caller is doing the right thing; deliberately not
    threaded through either, because the verdict is what reaches the page.

    TOTAL over the core's kinds, and a kind the core grows and this module does
    not know lands in `Verdict`'s own unknown-kind refusal — loud AT the
    boundary, which is where a sixth kind has to become a conversation with
    scitex-ui rather than a silent branch (see `VERDICT_KINDS`).
    """
    kind = decision.kind.value
    # Built through `Verdict` rather than through the named constructors, which
    # are one-line wrappers over exactly these calls: it keeps the payload
    # pass-through honest about being Optional while leaving the
    # required-payload rule in the ONE place that owns it — the validator.
    if kind == DENIED_NOT_SIGNED_IN:
        return Verdict(kind=DENIED_NOT_SIGNED_IN, sign_in_url=sign_in_url)
    if kind == DENIED_NOT_ENTITLED:
        return Verdict(
            kind=DENIED_NOT_ENTITLED, entitlement=entitlement, upgrade_url=upgrade_url
        )
    return Verdict(kind=kind)


def can(
    actor: Any,
    action: str,
    resource: Any,
    *,
    state: ResolveState,
    grants: Iterable[Any] = (),
    memberships: Iterable[Any] = (),
    kinds: Any = None,
    sign_in_url: Optional[str] = None,
    entitlement: Optional[str] = None,
    upgrade_url: Optional[str] = None,
    importer: _Importer = importlib.import_module,
) -> Verdict:
    """May ``actor`` do ``action`` to ``resource``? SYNCHRONOUS AND TOTAL.

    The one question every app asks instead of hand-rolling a gate. The decision
    RULES are not reimplemented here: they are the core's
    (``scitex_dev.access.check`` — owner / grant / inherited / org / public, the
    agent ceiling, no staff bypass), and this function's job is to (a) enforce
    the resolve-before-render contract and (b) express the answer in the ONE
    vocabulary scitex-ui already renders.

    ARGUMENTS, and why each is not a convenience:

        actor, action, resource
            The core's ``Principal`` / ``str`` / ``Resource``. Typed ``Any``
            because ``scitex_dev.access`` is an OPTIONAL runtime dependency
            imported through a call (invisible to the PS-140 static gate), so
            naming its types here would import the core at module load — the
            thing `access_django` deliberately avoids.

        state
            `ResolveState`, and the reason this signature has a keyword that a
            boolean would have hidden. NOT_ATTEMPTED RAISES (a caller who never
            resolved has violated the contract), FAILED RETURNS `unresolved()`
            (a real operating state the screen must still draw), RESOLVED
            decides. Held as \"a value, or None\" the first two are one state and
            this function cannot choose — the tripwire in this module's tests
            was written before this function existed, to guard exactly that.

        grants, memberships
            What the caller resolved. Passed through to ``check()`` unchanged.
            An entitlement enforcer that needs to attach an external decision
            should call :func:`verdict_from_decision` instead.

        sign_in_url, entitlement, upgrade_url
            The payloads for the two kinds that carry one — supplied BY THE
            DEPLOYMENT, never derived here (see :func:`verdict_from_decision`).
            A deployment's render path can pass them on EVERY call, because a
            payload the returned kind does not carry is simply not attached; you
            do not have to know the verdict in advance to supply them. Omitting
            one that the returned kind DOES require fails loud, out of
            `Verdict`'s validator, which is the one place that rule lives.

    FAILS CLOSED AND LOUD on a missing core (:class:`AccessPrimitiveMissingError`)
    rather than returning `denied`: an install that cannot decide and an install
    that decided \"no\" are different situations, and only one of them is fixed by
    configuring something.
    """
    if state is ResolveState.NOT_ATTEMPTED:
        raise ResolveNotAttemptedError(
            "can() was called with ResolveState.NOT_ATTEMPTED. Resolve who is "
            "asking — and whether they are entitled — BEFORE rendering, then call "
            "can() with ResolveState.RESOLVED, or with ResolveState.FAILED if "
            "resolution was attempted and did not succeed. Returning `unresolved` "
            "here would render a bug as a legitimate 'not yet known' screen."
        )
    if state is ResolveState.FAILED:
        return unresolved()

    # state is RESOLVED: an answer is available, so ask the core for it.
    core = _load_access_primitive(importer=importer)
    decision = core.check(
        actor, action, resource, grants=grants, memberships=memberships, kinds=kinds
    )
    return verdict_from_decision(
        decision,
        sign_in_url=sign_in_url,
        entitlement=entitlement,
        upgrade_url=upgrade_url,
    )


# ---------------------------------------------------------------------------
# SCOPE_FOR(). can() answers about ONE resource; this answers about a LIST.
# ---------------------------------------------------------------------------
#
# WHY THIS DOES NOT RESTATE THE RULES. `scitex_dev.access.accessible()` already
# returns the row-set a principal holds — owner / explicit ref / inherited
# parent / public, plus the agent ceiling — and ADR 0002 §2 names that value
# "the data-scope half". So what was missing was never the RULE; it was an
# ANSWER AN APP CAN HOLD. A bare filter cannot say "we could not find out who is
# asking", and a list rendered from the empty filter TELLS A SIGNED-IN PERSON
# THEY HAVE NO CONTENT when the truth is that nobody checked — the same collapse
# `Verdict` exists to prevent, one row-set down. The filter therefore travels
# WITH the verdict kind that produced it (:class:`DataScope`).
#
# NOT `_app_scope`, AND THE NEAR-MISS IS WHY THE NAME DIFFERS. `scitex_app.
# _app_scope` declares a manifest's RENDERING scope (SCOPE_USER / SCOPE_PROJECT:
# does this app get a project selector) — a fact about a PAGE. This is a fact
# about ROWS. Two different things answering to "scope" is how a reader
# concludes one of them does not exist, so the value is named with the ADR's own
# phrase for this half instead of sharing the word.
#
# "OWN / ORG / OPERATOR" IS DERIVED, NOT A FOURTH VOCABULARY. The ask that
# produced this function enumerated three scopes; the approved design superseded
# that enumeration. A principal is `user:` / `org:` / `agent:` / `anonymous` —
# `scitex_dev.scope`'s vocabulary, not a parallel one — "own" is an owner match,
# "org" arrives through a :class:`Membership`, and an operator is an ordinary
# `org:` grant rather than a fourth kind of person ("treat everyone the same, me
# or a customer"). All three therefore fall OUT of the filter, and an enum here
# would be exactly the second vocabulary the operator ruled out.


class ScopeError(VerdictError):
    """A scope was constructed that cannot mean anything.

    A ``VerdictError`` for the same reason :class:`ResolveNotAttemptedError` is
    one: a caller already handling "you built or asked for a verdict-family
    value wrong" needs no second except clause, and nothing about either should
    reach a page.
    """


@dataclass(frozen=True)
class DataScope:
    """Which rows an actor may see — and WHICH ANSWER that row-set is.

    Two fields, and the second exists because of the first. ``kind`` is one of
    :data:`VERDICT_KINDS` (the same five strings scitex-ui already switches on,
    so a scoped-empty list renders through the switch a denied detail page
    renders through — the operator's "route scoped empties through the verdict,
    not through HTTP status"); ``access_filter`` is the core's ``AccessFilter``
    and is present on ``allowed`` and on NOTHING ELSE.

    WHY THE FILTER IS WITHHELD RATHER THAN EMPTIED on the other four kinds. An
    empty filter is a claim — "there are no rows for you" — and every non-allowed
    kind is a case where we are not entitled to make it: a denial is a decision
    about an action, ``unresolved`` is the absence of a decision, and rendering
    either as "no content" invents an answer. So an app cannot accidentally
    query with a scope that did not earn one; it has to read ``kind`` and render
    the state, which is the work the five kinds exist to force.

    ``access_filter`` is the core's object, passed through untouched, so both
    documented downstreams work unchanged: ``scitex_dev.access.select(scope.
    access_filter, resources)`` in memory, and ``scitex_app.access_django.
    to_q(scope.access_filter)`` for a queryset. This type adds no query
    grammar of its own — a translation invented here would be a second place
    the row rule lives.

    THERE IS DELIBERATELY NO ``.allowed`` BOOLEAN PROPERTY, for the reason
    :class:`Verdict` gives, and it would be worse here: ``if scope.allowed:``
    reads naturally and makes "we could not decide" indistinguishable from
    "nothing for you", which is the exact confusion this pairing removes.

    AND NO ``to_dict()``. :class:`Verdict` has one because it crosses a package
    boundary into scitex-ui, which has no access to the core. A scope does not
    cross anything: the filter is meaningless to a renderer, and the part that
    does cross — ``kind`` — is already a plain string. Serialising a filter
    would invent a wire format no consumer asked for.
    """

    kind: str
    access_filter: Any = None

    def __post_init__(self) -> None:
        if self.kind not in VERDICT_KINDS:
            raise ScopeError(
                f"unknown scope kind {self.kind!r}; "
                f"expected one of {', '.join(VERDICT_KINDS)}"
            )
        if self.kind == ALLOWED and self.access_filter is None:
            raise ScopeError(
                "an allowed scope requires access_filter — without one the "
                "caller has nothing to filter rows by, and 'allowed, unnamed "
                "row set' is not a state any app can act on"
            )
        if self.kind != ALLOWED and self.access_filter is not None:
            raise ScopeError(
                f"{self.kind} must not carry access_filter — the four "
                "non-allowed kinds mean we are not entitled to claim anything "
                "about the rows, and a filter here would be used as if we were"
            )


def scope_from_decision(decision: Any, *, access_filter: Any = None) -> DataScope:
    """Render a core ``AccessDecision`` as a :class:`DataScope`.

    THE ENTITLEMENT SEAM, and the list-side twin of :func:`verdict_from_decision`
    for the same reason: ``denied-because-not-entitled`` is a plan the HUB knows
    and no path inside the core produces, so an enforcer that consulted the hub
    hands its own decision through this mapping rather than inventing a kind.

    IDENTITY ON KIND, like its twin — the core's ``DecisionKind`` members carry
    these strings verbatim, and the drift gate in this module's tests fails here
    rather than at scitex-ui's exhaustive switch.

    ``access_filter`` is supplied BY WHOEVER KNOWS IT and is attached on
    ``allowed`` only. A filter passed on a call that returns any other kind is
    FORWARDED NOWHERE rather than refused, mirroring ``verdict_from_decision``'s
    payload rule: the natural call site is a render path that has its grants
    loaded already and does not know the answer in advance, and refusing it
    would make that call site illegal.
    """
    kind = decision.kind.value
    if kind == ALLOWED:
        return DataScope(kind=ALLOWED, access_filter=access_filter)
    return DataScope(kind=kind)


def scope_for(
    actor: Any,
    action: str,
    kind: str,
    *,
    state: ResolveState,
    grants: Iterable[Any] = (),
    memberships: Iterable[Any] = (),
    kinds: Any = None,
    importer: _Importer = importlib.import_module,
) -> DataScope:
    """Which rows of ``kind`` may ``actor`` reach by ``action``? TOTAL.

    The list-side sibling of :func:`can`, on the SAME resolve-before-render
    contract and the same vocabulary. ``actor`` is the core's ``Principal``;
    the rules are the core's (``accessible()`` — owner / grant / inherited /
    membership / public, capped for an agent by its owner); what this function
    adds is (a) the resolve-before-render contract and (b) an answer that
    distinguishes "no rows" from "not known".

    ``action`` IS REQUIRED, with no default, and that is a decision rather than
    terseness. The obvious default — ``read``, because a list is a read — WIDENS
    the row set: ``accessible()`` sets ``public`` only for a ``read``-tier
    action, so defaulting would hand an app its owner/ref/parent rows PLUS every
    public row when the endpoint it is actually serving wanted a narrower
    question. `scitex_app.api_access` refuses a defaulted pair for exactly this
    reason, and the same refusal applies to half a pair.

    ARGUMENT-BY-ARGUMENT, matching :func:`can`:

        state
            NOT_ATTEMPTED RAISES (:class:`ResolveNotAttemptedError`, the same
            class the single-resource path raises, because it is one contract);
            FAILED returns an ``unresolved`` scope with NO filter, which is
            fail closed — an app that renders it shows the locked/empty content
            area rather than every row, and one that reads ``kind`` can say
            "not yet known" instead of "nothing for you"; RESOLVED decides.

        grants, memberships, kinds
            What the caller resolved, passed through to ``accessible()``
            unchanged. Inventing them here would make this function the
            authority on who someone is.

    RAISES :class:`AccessPrimitiveMissingError` when the core is absent —
    "this install cannot decide" is not "this actor may see nothing", and only
    one of those is fixed by configuring something.

    AN UNREGISTERED KIND IS ``unresolved``, NOT AN EXCEPTION. The core raises
    ``AccessUnresolved`` because it has no filter to return; a note here HAS a
    value to return, and the core's own vocabulary already answers this case —
    ``check()`` reports ``kind-unregistered`` as ``unresolved``, so translating
    it to anything else would make the two surfaces disagree about the same
    deployment. An action the kind does not declare still PROPAGATES
    (``AccessConfigError``): that is a declaration defect, and ``check()``
    raises it too.
    """
    if state is ResolveState.NOT_ATTEMPTED:
        raise ResolveNotAttemptedError(
            "scope_for() was called with ResolveState.NOT_ATTEMPTED. Resolve "
            "who is asking BEFORE rendering, then call scope_for() with "
            "ResolveState.RESOLVED, or with ResolveState.FAILED if resolution "
            "was attempted and did not succeed. Returning a scope here would "
            "let a bug render as 'this user has no content' — silently, and "
            "looking exactly like a correct empty list."
        )
    if state is ResolveState.FAILED:
        return DataScope(kind=UNRESOLVED)

    core = _load_access_primitive(importer=importer)
    try:
        access_filter = core.accessible(
            actor,
            action,
            kind,
            grants=grants,
            memberships=memberships,
            kinds=kinds,
        )
    except core.AccessUnresolved:
        return DataScope(kind=UNRESOLVED)
    return DataScope(kind=ALLOWED, access_filter=access_filter)


__all__ = [
    "ALLOWED",
    "CORE_MODULE",
    "HUB_URL_ENV",
    "DENIED",
    "DENIED_NOT_ENTITLED",
    "DENIED_NOT_SIGNED_IN",
    "AccessPrimitiveMissingError",
    "DataScope",
    "ResolveNotAttemptedError",
    "ResolveState",
    "ScopeError",
    "UNRESOLVED",
    "VERDICT_KINDS",
    "Verdict",
    "VerdictError",
    "allowed",
    "can",
    "denied",
    "denied_no_hub",
    "denied_not_entitled",
    "denied_not_signed_in",
    "hub_url",
    "scope_for",
    "scope_from_decision",
    "unresolved",
    "verdict_from_decision",
]

# EOF
