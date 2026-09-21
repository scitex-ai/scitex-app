#!/usr/bin/env python3
"""Compose a DECLARED ``(kind, action)`` access pair with ``scitex_dev.access``.

A leaf DECLARES the claim it makes on a resource kind (:class:`AccessClaim`); a
host COMPOSES it. This module is the composing half: it turns

    declared pair  +  principal  +  grants  +  memberships

into (a) the core's ``AccessFilter`` — the refs that principal may reach for that
kind and action, via the core's ``accessible()`` — and (b), for a LIST endpoint,
the Django ``Q`` that admits exactly those rows, via
:func:`scitex_app.access_django.to_q`. A list filtered by (b) therefore admits
exactly what the core's ``check()`` admits for one row, which is the property
that keeps a declared API surface and its access decision from drifting apart.

WHY THE PAIR AND NOT AN ACTION NAME (hub ruling, 2026-09-17, fixed). The claim is
an explicit ``(kind, action)`` pair because it is injective: ``view`` on a figure
and ``view`` on a dataset are different claims, and a single action name lets two
kinds collide into one declaration neither a reviewer nor the core can tell
apart. The single-name alternative is rejected, not merely unused.

FAIL CLOSED, LOUDLY, AND BY NAME — there is no default pair anywhere, because
every default would be a guess with access consequences: ``read``/public would
WIDEN the claim, and an empty filter would silently DROP rows.

* a blank or non-text member is refused (:class:`UnknownAccessPairError`): a pair
  whose half was never stated is not a pair;
* a kind the core does not register, or an action that kind's own spec does not
  declare, is refused with the pair AND what the core knows — the registered
  kinds, or the actions that kind declares. The pair is never resolved by
  guessing the nearest action;
* a missing core is a NAMED error (:class:`AccessCoreMissingError`), not a bare
  ``ImportError``: "the dependency is not installed" is a state the caller is
  told about, not a traceback to interpret.

EQUIVALENCE, NOT STRICTNESS. The refusals above are not a stricter rule than the
core's — they are the SAME rule, and the differential arms in
``tests/scitex_app/api_access/`` prove it in both directions: a pair this module
accepts is a pair the core accepts, and a pair it refuses is a pair the core
refuses. That is deliberate. A stricter rule is not extra safety: a rule the core
does not have drops declarations the core would have granted, which is exactly
the divergence class ``to_q``'s parent grammar was fixed for (hub verdict
2026-09-17 on PR #198).

WHAT THIS MODULE DOES NOT DO, so a reader does not assume it. It does not carry
the pair INTO the merged declaration contract: ``scitex_app.api_plugin``'s
``AuthScope`` (five review rounds, merged as 78c6b28) still has no pair field, so
composing takes the pair as an explicit input rather than reading it off a route.
That keeps a reviewed public contract untouched, at the cost of leaving the
route↔pair BINDING to the caller; carrying the pair on ``AuthScope`` would close
that gap and is a public-surface decision recorded against the card
(``app-api-plugin-access-composition-20260917``) rather than taken here.

WHY THIS IS A SUBPACKAGE (``api_access/__init__.py``) AND NOT A ROOT MODULE:
``src/scitex_app`` sits at exactly PS-108b's flat-file threshold (15 counted
modules; the rule fires ABOVE 15), so a new root-level module would turn the
audit red for everyone — the collision the card
``app-package-root-at-ps108b-file-threshold-20260917`` predicts, dodged here
rather than fixed. The public name is unchanged (``scitex_app.api_access``); only
the on-disk shape differs, matching ``shell_contract`` and ``project_context``.

DEPENDENCY GATES, both optional at runtime. ``scitex_dev.access`` is imported
through an injectable importer (``importlib.import_module`` by default — a CALL,
not a static ``ImportFrom``, so it is invisible to the PS-140 symbol gate) and
only when a pair is composed; Django is imported only by :func:`compose_list_q`,
because ``scitex_app.access_django`` imports it. The module therefore imports,
and its filter-composition arms run, with NEITHER installed; only the
Django-backed arms need the ORM.
"""

from __future__ import annotations

import importlib
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from types import ModuleType
from typing import Any

from scitex_app.api_plugin import ApiPluginContractError

#: An injectable module importer. ``importlib.import_module`` by default; tests
#: supply a fake so "the dependency is absent" and "the dependency failed
#: internally" are exercised as pure inputs, with no module patched (PA-306).
_Importer = Callable[[str], ModuleType]

#: The core's module: the one implementation of the access decision.
CORE_MODULE = "scitex_dev.access"

#: The Django adapter module, imported only by :func:`compose_list_q`.
DJANGO_ADAPTER_MODULE = "scitex_app.access_django"

#: The core's filter object. Typed ``Any`` because ``scitex_dev.access`` is an
#: optional runtime dependency; composition reads only its documented surface
#: and hands it to ``access_django.to_q``, which reads the same surface.
AccessFilter = Any

#: The Django ``Q`` :func:`compose_list_q` returns. ``Any`` for the same reason:
#: naming the type would import Django at module load.
Query = Any


class AccessCoreMissingError(RuntimeError):
    """``scitex_dev.access`` is not installed, so no pair can be composed.

    The same shape as :class:`scitex_app.access_django.ScitexDevAccessMissingError`:
    composition is UNAVAILABLE rather than silently permissive, and the fix is
    named. Deliberately not an ``ImportError`` — an import failure is what
    happened, not what it means, and a caller deciding "can this deployment
    serve scoped lists?" must be able to catch the meaning.
    """

    def __init__(self) -> None:
        super().__init__(
            "scitex_app.api_access needs scitex_dev.access to compose a declared "
            "(kind, action) pair, and it is not installed. "
            "Run: pip install -U scitex-dev  (the access release is pending)."
        )


class DjangoAdapterMissingError(RuntimeError):
    """Django is not installed, so the ORM half of composition is unavailable.

    Raised only by :func:`compose_list_q`, the one entry point that needs the
    ORM. Compose a filter instead when Django is genuinely absent — the filter
    is backend-neutral and needs no web framework.
    """

    def __init__(self) -> None:
        super().__init__(
            "scitex_app.api_access.compose_list_q needs the Django ORM "
            "(scitex_app.access_django imports django), and django is not "
            "installed. Run: pip install -U 'scitex-app[all]', or compose the "
            "backend-neutral filter with compose_filter() instead."
        )


class UnknownAccessPairError(ApiPluginContractError):
    """The declared pair is not one the core defines — or is not a pair at all.

    A subclass of :class:`ApiPluginContractError` because the claim comes from a
    DECLARATION, so a wrong pair is a declaration defect and a host guarding its
    own declarations should not have to know which layer noticed. Covers all
    three refusals — a blank member, an unregistered kind, an action the kind
    does not declare — so one catch covers "this pair cannot be composed", and
    the message names the pair and what the core knows.
    """


def _missing_core(exc: BaseException) -> bool:
    """True only for the "``scitex_dev.access`` is not installed yet" case.

    The same narrowness as :func:`scitex_app.access_django._missing_access`:
    only a ``ModuleNotFoundError`` naming the core or its parent module is
    "absent". An ``ImportError`` raised INSIDE an installed core is a real
    failure and propagates instead of being laundered into "not installed",
    which would read as a skip and hide a defect. The two predicates are proven
    to agree by a differential arm, so "the core is missing" cannot mean two
    things in one package.
    """
    return isinstance(exc, ModuleNotFoundError) and getattr(exc, "name", None) in (
        "scitex_dev",
        CORE_MODULE,
    )


def _require_claim_text(value: object, what: str) -> str:
    """Return ``value`` stripped, or refuse a pair member that was never stated."""
    if not isinstance(value, str) or not value.strip():
        raise UnknownAccessPairError(
            f"{what} is {value!r}; a declared access pair names a resource kind "
            "and an action, both non-blank text. Fail closed: a blank half is "
            "refused, never filled in with a default."
        )
    return value.strip()


@dataclass(frozen=True)
class AccessClaim:
    """The claim a scoped route makes: the resource KIND and the ACTION.

    A pair, not a name, and both members validated here — the same rule the core
    applies when it resolves the pair, so a claim that constructs is a claim the
    core can be asked about.
    """

    kind: str
    action: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "kind", _require_claim_text(self.kind, "access-claim kind"))
        object.__setattr__(
            self, "action", _require_claim_text(self.action, "access-claim action")
        )

    @property
    def pair(self) -> tuple[str, str]:
        """``(kind, action)`` — what a refusal names and a test asserts on."""
        return (self.kind, self.action)


def load_core(*, importer: _Importer = importlib.import_module) -> ModuleType:
    """Import ``scitex_dev.access``, or raise the NAMED missing-core error.

    The importer is injectable so the absent case is a pure input: a fake raising
    ``ModuleNotFoundError("scitex_dev.access")`` must produce
    :class:`AccessCoreMissingError`, and one raising a ``ModuleNotFoundError``
    for an UNRELATED module must propagate.
    """
    try:
        return importer(CORE_MODULE)
    except ImportError as exc:
        if _missing_core(exc):
            raise AccessCoreMissingError() from exc
        raise


def _registry_and_spec(
    core: ModuleType, claim: AccessClaim, kinds: Mapping[str, Any] | None
) -> tuple[Mapping[str, Any], Any]:
    """The registry the pair resolves against, and the kind's spec.

    Refuses loudly on either half of an unknown pair, naming the pair AND what
    the core knows: the registered kinds, or the actions this kind declares. No
    nearest-match, no default action, no read fallback. The registry handed to
    :func:`compose_filter` is the SAME object returned here, so the spec that
    validated the pair is the spec that fixes its required role.
    """
    registry: Mapping[str, Any] = kinds if kinds is not None else core.discover_kinds()
    spec = registry.get(claim.kind)
    if spec is None:
        raise UnknownAccessPairError(
            f"access pair {claim.pair} names a resource kind the access core "
            f"does not register; the core knows {sorted(registry)}. A pair no "
            "kind spec defines cannot be composed — declare the kind from an "
            "installed scitex_dev.access.kinds provider, or fix the name."
        )
    declared = tuple(sorted(spec.actions))
    if claim.action not in spec.actions:
        raise UnknownAccessPairError(
            f"access pair {claim.pair} names an action the kind "
            f"{claim.kind!r} does not declare; it declares {list(declared)}. "
            "Fail closed: an undefined action is refused, never defaulted to a "
            "read/public filter."
        )
    return registry, spec


def compose_filter(
    claim: AccessClaim,
    principal: Any,
    *,
    grants: Iterable[Any] = (),
    memberships: Iterable[Any] = (),
    kinds: Mapping[str, Any] | None = None,
    importer: _Importer = importlib.import_module,
) -> AccessFilter:
    """The core's ``AccessFilter`` for the DECLARED pair and this principal.

    ``principal``, ``grants`` and ``memberships`` are the core's own values
    (``Principal``, ``Grant``, ``Membership``) and are passed through untouched,
    because inventing them here would make composition the authority on who
    someone is. ``kinds`` is the core's own registry seam — the registry the pair
    is resolved against, defaulting to the installed kinds — and the same
    registry is handed to ``accessible()``.

    Raises :class:`UnknownAccessPairError` for a pair the core does not define,
    and :class:`AccessCoreMissingError` when the core is not installed. It never
    returns a filter the pair did not earn.
    """
    core = load_core(importer=importer)
    registry, _spec = _registry_and_spec(core, claim, kinds)
    return core.accessible(
        principal,
        claim.action,
        claim.kind,
        grants=grants,
        memberships=memberships,
        kinds=registry,
    )


def _load_django_adapter(*, importer: _Importer = importlib.import_module) -> ModuleType:
    """Import ``scitex_app.access_django``, or raise the NAMED missing-Django error.

    Lazy for the reason in the module docstring: that adapter imports Django at
    module load, and this module must import without it. A ``django`` that is
    absent is named; anything else that fails inside the adapter propagates.
    """
    try:
        return importer(DJANGO_ADAPTER_MODULE)
    except ImportError as exc:
        if isinstance(exc, ModuleNotFoundError) and getattr(exc, "name", "").split(".")[
            0
        ] == "django":
            raise DjangoAdapterMissingError() from exc
        raise


def compose_list_q(
    claim: AccessClaim,
    principal: Any,
    *,
    grants: Iterable[Any] = (),
    memberships: Iterable[Any] = (),
    kinds: Mapping[str, Any] | None = None,
    importer: _Importer = importlib.import_module,
    adapter_importer: _Importer = importlib.import_module,
) -> Query:
    """The Django ``Q`` admitting exactly the rows :func:`compose_filter` allows.

    For a LIST endpoint: ``access_django.to_q(compose_filter(...))`` — the
    translation of the composed filter, which is the same filter the core uses to
    decide one row. The pair is NOT inspected to guess whether the endpoint is a
    list: "GET means list" would silently turn a detail endpoint into a list
    filter, so the caller, which knows which route it is serving, says so by
    calling this.

    PRECONDITION: the host's Django is configured and set up, exactly as it must
    be before any app's models are imported — ``scitex_app.access_django``
    defines a concrete model, so it is that kind of module. Django's own
    ``ImproperlyConfigured`` is the signal for a host that skipped those startup
    steps; this composer does not reinterpret it.

    Raises everything :func:`compose_filter` raises — BEFORE Django is touched, so
    a refusal is a declaration error rather than an import error — plus
    :class:`DjangoAdapterMissingError` when Django itself is absent.
    """
    access_filter = compose_filter(
        claim,
        principal,
        grants=grants,
        memberships=memberships,
        kinds=kinds,
        importer=importer,
    )
    return _load_django_adapter(importer=adapter_importer).to_q(access_filter)


__all__ = [
    "CORE_MODULE",
    "DJANGO_ADAPTER_MODULE",
    "AccessClaim",
    "AccessCoreMissingError",
    "AccessFilter",
    "DjangoAdapterMissingError",
    "Query",
    "UnknownAccessPairError",
    "_missing_core",
    "compose_filter",
    "compose_list_q",
    "load_core",
]

# EOF
