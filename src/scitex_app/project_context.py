#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# File: scitex_app/project_context.py

"""The leaf-facing project-context API: one selected project, carried to every app.

SSOT: scitex-hub PR 923, ``docs/product/PRIVATE_BETA_LOGIN_TO_WOW.md``.

    "Project context is selected once and carried across every leaf app."
    "Canonical project picker is always visible and displays user-facing
     project names, never internal ``MASTER/`` paths."
    "Real users never receive a silently created or selected example project."
    "UI actions map to stable named commands so mouse, touch, keyboard,
     macros, and agents invoke the same operations."

WHERE THIS SITS. Three packages, three jobs, no overlap:

    scitex-hub    owns user/project AUTHORITY and integration. It knows which
                  projects a user may access and serves that as the host
                  provider.
    scitex-ui     owns the PROVIDER PROTOCOL (``ProjectProvider``,
                  ``ProjectEntry``, ``resolve_project``) and the picker's
                  rendering.
    scitex-app    owns this module: what a LEAF APP is handed, the fail-closed
                  states around it, and the stable named command that changes
                  it.

THIS MODULE DOES NOT RE-IMPLEMENT scitex-ui's resolution. ``resolve_project``
already fixes the precedence (explicit, then last visited, then nothing) and a
second implementation here would be a forked producer with no link between the
two — the failure the shell guard in scitex-ui calls a HALF-PAIR. The provider
is consumed through scitex-ui when it is installed, so the two cannot drift.

WHY A WRAPPER AT ALL, given scitex-ui can resolve. Because a leaf app needs
three things scitex-ui's view-layer function does not give it: a DISPLAY-SAFE
descriptor, a state it can render an honest empty/denied/unavailable arm from,
and a named command. ``resolve_project`` returns an id or ``None``; ``None``
covers "nothing selected", "not yours", and "no provider" alike, and a leaf
that renders all three as the same blank page ships the silent-failure defect
the product rules forbid.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional, Protocol, runtime_checkable

__all__ = [
    "CHANGE_PROJECT_COMMAND",
    "PROJECT_QUERY_PARAM",
    "STANDALONE_PROVIDER_PATH",
    "STATE_DENIED",
    "STATE_NONE",
    "STATE_OK",
    "STATE_UNAVAILABLE",
    "VALID_STATES",
    "ActiveProject",
    "ProjectDeniedError",
    "ProjectResolution",
    "ProjectUnavailableError",
    "change_project",
    "project_context",
    "project_provider_endpoint",
    "resolve_active_project",
]

#: The query parameter carrying an explicit project, agreed with scitex-ui
#: (``scitex_ui.project_scope.PROJECT_QUERY_PARAM``). An explicit project wins
#: over the stored one — that is the route/query half of persistence.
PROJECT_QUERY_PARAM = "project"

#: The stable command name for changing the active project.
#:
#: STABLE AND NAMED, not a URL and not a method name, because every input
#: modality has to reach the same operation: a mouse click, a touch, a keyboard
#: binding, a recorded macro, and an agent all address this one identity. A
#: command spelled as a URL breaks the moment the mount prefix changes, and one
#: spelled as a Python function name is unreachable from the browser.
CHANGE_PROJECT_COMMAND = "scitex.project.change"

#: Declared resolution states. Nothing else is ever set.
#:
#: ``ok``          a project is selected and the user may access it.
#: ``none``        nothing selected (or the stored project is gone). The app
#:                 shows its picker. THIS IS NOT AN ERROR.
#: ``denied``      an explicit project was asked for and is not accessible.
#: ``unavailable`` no provider is configured, so no project CAN be resolved.
STATE_OK = "ok"
STATE_NONE = "none"
STATE_DENIED = "denied"
STATE_UNAVAILABLE = "unavailable"
VALID_STATES = (STATE_OK, STATE_NONE, STATE_DENIED, STATE_UNAVAILABLE)


@runtime_checkable
class _ProjectProvider(Protocol):
    """The slice of scitex-ui's provider protocol this module consumes.

    STRUCTURAL, not an import of ``scitex_ui.ProjectProvider``: scitex-ui is an
    OPTIONAL dependency of scitex-app (the launcher raises
    ``ScitexUiRequiredError`` rather than requiring it), so this module must
    work — and be testable — with scitex-ui absent. Declaring the three methods
    the contract needs keeps that possible without importing the package, and
    ``tests/scitex_app/test_project_context.py`` asserts this shape still
    matches scitex-ui's, so the two cannot drift apart silently.
    """

    def list_projects(self, request: Any) -> list:
        """Projects this request's user can access, in display order."""
        ...

    def last_visited(self, request: Any) -> Optional[str]:
        """The stored last visited project id, or None."""
        ...

    def remember(self, request: Any, project_id: str) -> None:
        """Store ``project_id`` as the last visited project."""
        ...


@dataclass(frozen=True)
class ActiveProject:
    """A project as a LEAF APP is allowed to see it.

    TWO FIELDS, and the omission is the point. scitex-ui's ``ProjectEntry``
    also carries ``detail``, which ``LocalProjectProvider`` fills with the
    project's filesystem path. That field is provider-internal: rendering it
    puts an internal path in front of a user, which the product rules forbid
    ("never internal ``MASTER/`` paths"). A descriptor with no path field
    cannot leak one, so this is structural rather than a rule someone has to
    remember.

    ``name`` is the user-facing label. A provider that returns an empty name
    falls back to the id — never to a path, and never to an invented label.
    """

    id: str
    name: str

    def __post_init__(self) -> None:
        if not self.id:
            raise ValueError("ActiveProject requires a non-empty id")
        if not self.name:
            raise ValueError(
                "ActiveProject requires a non-empty name; a project with no "
                "user-facing label must not reach a display slot"
            )

    def as_dict(self) -> dict:
        """The JSON-safe shape for templates and the browser."""
        return {"id": self.id, "name": self.name}


@dataclass(frozen=True)
class ProjectResolution:
    """One shape for every outcome, so a caller never guesses which keys exist.

    Mirrors ``scitex_app._gui_runtime.PortHolder``: the state is a declared
    constant, and the invariants below make an inconsistent resolution
    impossible to construct rather than merely unlikely to be written.
    """

    state: str
    project: Optional[ActiveProject] = None
    reason: str = ""

    def __post_init__(self) -> None:
        if self.state not in VALID_STATES:
            raise ValueError(f"unknown project state: {self.state!r}")
        if self.state == STATE_OK and self.project is None:
            raise ValueError("state='ok' requires a project")
        if self.state != STATE_OK and self.project is not None:
            raise ValueError(
                f"state={self.state!r} must not carry a project — a resolution "
                "that is not 'ok' has no active project to hand over"
            )

    @property
    def ok(self) -> bool:
        """True only when a project was resolved."""
        return self.state == STATE_OK


class ProjectDeniedError(PermissionError):
    """An explicit project was requested that this user may not access.

    An EXCEPTION rather than a falsy return, because the caller wrote a command
    whose entire meaning is "make this project active". Silently leaving the
    old project selected would look like success while the UI said otherwise —
    and the fail-closed rule requires the request be REFUSED, not downgraded.
    """


class ProjectUnavailableError(RuntimeError):
    """No project context could be computed, so no command could be applied.

    DISTINCT FROM :class:`ProjectDeniedError` on purpose. "You may not" and "we
    could not ask" call for different responses — one is a permission answer,
    the other is an outage — and collapsing them would tell a user they lack
    access to something that was never checked.
    """


#: Where the standalone launcher registers its provider.
#:
#: A dotted path, because that is the channel scitex-ui reads
#: (``settings.SCITEX_PROJECT_PROVIDER``), so a standalone app resolves its
#: project through the SAME code path a hosted app does. The name is public so
#: the launcher and any consumer can agree on it without a second constant.
STANDALONE_PROVIDER_PATH = "scitex_app.project_context.StandaloneProjectProvider"


def _host_provider() -> tuple[Optional[_ProjectProvider], str]:
    """The host's registered provider, or ``(None, reason)``.

    Never guesses. When scitex-ui is absent, or no provider is configured, the
    reason names WHICH of those it is, so an operator reading an
    ``unavailable`` state learns the actual cause instead of a blank page.
    """
    try:
        from scitex_ui.project_scope import host_project_provider
    except ImportError:
        return None, "scitex-ui is not installed, so no provider can be resolved"
    try:
        provider = host_project_provider()
    except Exception as exc:  # Django not configured, bad dotted path, ...
        return None, f"the configured provider could not be loaded: {exc}"
    if provider is None:
        reason = (
            "no project provider is configured "
            "(settings.SCITEX_PROJECT_PROVIDER is empty)"
        )
        return None, reason
    return provider, ""


def _accessible(provider: _ProjectProvider, request: Any) -> dict[str, ActiveProject]:
    """Every project ``request``'s user may access, keyed by id.

    A provider entry without an id, or with an empty name, is SKIPPED rather
    than repaired: inventing a label or an id for it would put a made-up
    project in a picker.
    """
    found: dict[str, ActiveProject] = {}
    for entry in provider.list_projects(request):
        entry_id = getattr(entry, "id", "") or ""
        if not entry_id:
            continue
        name = getattr(entry, "name", "") or entry_id
        found[entry_id] = ActiveProject(id=entry_id, name=name)
    return found


def resolve_active_project(
    request: Any,
    provider: Optional[_ProjectProvider] = None,
    explicit: Optional[str] = None,
) -> ProjectResolution:
    """Resolve the project this request should open, fail-closed.

    Precedence, identical to ``scitex_ui.project_scope.resolve_project``
    because it is the same rule and not a second one:

    1. An ``explicit`` project (argument, else ``?project=``) wins. If the user
       may not access it, the result is ``denied`` — it NEVER falls back to the
       stored project, because the caller asked for a different one and
       silently substituting another is the failure this rule exists to stop.
    2. Otherwise the stored last-visited project, if it is still accessible.
    3. Otherwise ``none``: the app shows its picker. Nothing is auto-selected,
       and no example project is ever created or chosen on a user's behalf.
    """
    resolved_provider = provider
    if resolved_provider is None:
        resolved_provider, reason = _host_provider()
        if resolved_provider is None:
            return ProjectResolution(state=STATE_UNAVAILABLE, reason=reason)

    if explicit is None:
        explicit = _explicit_from_request(request)

    try:
        accessible = _accessible(resolved_provider, request)
    except Exception as exc:
        # Fail CLOSED, not loudly-500. A provider that cannot answer must not
        # make the page unrenderable, and it must never be read as "no project"
        # (which would show an empty picker as if the user had none) or as "ok".
        # `unavailable` is the declared state for exactly this, and the reason
        # travels with it so the cause is readable rather than merely absent.
        return ProjectResolution(
            state=STATE_UNAVAILABLE,
            reason=f"the project provider failed to list projects: {exc}",
        )

    if explicit:
        if explicit not in accessible:
            return ProjectResolution(
                state=STATE_DENIED,
                reason=(
                    f"project {explicit!r} is not accessible to this user. "
                    "Refused rather than falling back: the requested project "
                    "either does not exist or belongs to someone else, and a "
                    "distinction is not disclosed because telling them apart "
                    "would confirm another user's project exists."
                ),
            )
        # An explicit project BECOMES the stored one. This is the persistence
        # half of the rule: a link carrying ?project=foo has to survive the
        # next navigation, or "selected once and carried across every leaf app"
        # holds only for as long as the query string is on the URL. Written
        # AFTER the access check, so a refused project is never persisted.
        resolved_provider.remember(request, explicit)
        return ProjectResolution(state=STATE_OK, project=accessible[explicit])

    try:
        stored = resolved_provider.last_visited(request)
    except Exception as exc:
        return ProjectResolution(
            state=STATE_UNAVAILABLE,
            reason=f"the project provider failed to report the stored project: {exc}",
        )
    if stored and stored in accessible:
        return ProjectResolution(state=STATE_OK, project=accessible[stored])

    return ProjectResolution(
        state=STATE_NONE,
        reason=(
            "no project is selected (or the stored one is no longer "
            "accessible); the app shows its picker"
        ),
    )


def _explicit_from_request(request: Any) -> Optional[str]:
    """``?project=`` from the request, or None. Any request shape is tolerated.

    A request without ``GET`` is legitimate here — this function is also called
    from view code that resolved the project from a URL path instead, where the
    caller passes ``explicit`` itself.
    """
    get = getattr(request, "GET", None)
    if get is None:
        return None
    try:
        value = get.get(PROJECT_QUERY_PARAM)
    except Exception:
        return None
    return value or None


def project_context(request: Any, provider: Optional[_ProjectProvider] = None) -> dict:
    """Context processor: hand every leaf template its project context.

    Register once and a mounted app renders its project surface without the
    view having to pass anything::

        TEMPLATES[0]["OPTIONS"]["context_processors"] += [
            "scitex_app.project_context.project_context",
        ]

    The COMMAND NAME travels with the context on purpose. The picker's change
    action is addressed by identity (``project_command``), not by a URL the
    template would have to build — so the shell, a keyboard binding, a recorded
    macro and an agent all invoke the same operation, and none of them breaks
    when the mount prefix changes.

    Keys: ``active_project`` (dict or None), ``project_state`` (a declared
    state), ``project_command``.
    """
    resolution = resolve_active_project(request, provider)
    return {
        "active_project": (
            resolution.project.as_dict() if resolution.project else None
        ),
        "project_state": resolution.state,
        "project_command": CHANGE_PROJECT_COMMAND,
        # The slot travels with the context too: a leaf that renders a picker
        # affordance needs to know WHERE to fetch the list from, and the answer
        # is the host's, not something the leaf may construct.
        "project_provider_endpoint": project_provider_endpoint(),
    }


def change_project(
    request: Any, project_id: str, provider: Optional[_ProjectProvider] = None
) -> ActiveProject:
    """The ``scitex.project.change`` command: make ``project_id`` the active one.

    THE ONE OPERATION every input modality addresses. It is named rather than
    bound to a route so a click, a keystroke, a macro and an agent are all
    calling this and not four implementations of it.

    Fails closed in both directions, and changes NOTHING when it refuses:

    * an unknown or unauthorised id raises :class:`ProjectDeniedError`, and the
      previously stored project is left untouched — a refused command must not
      half-apply;
    * a provider that cannot answer raises :class:`ProjectUnavailableError`,
      which is NOT the same answer as "you may not";
    * an empty id raises ``ValueError``: there is no such thing as changing to
      "no project", and accepting one would clear the user's selection by
      accident.
    """
    if not project_id:
        raise ValueError(
            "change_project requires a project id; an empty id would clear the "
            "user's selection rather than change it"
        )

    resolved_provider = provider
    if resolved_provider is None:
        resolved_provider, reason = _host_provider()
        if resolved_provider is None:
            raise ProjectUnavailableError(f"cannot change project: {reason}")

    try:
        accessible = _accessible(resolved_provider, request)
    except Exception as exc:
        raise ProjectUnavailableError(
            f"cannot change project: the provider failed to list projects: {exc}"
        ) from exc

    if project_id not in accessible:
        raise ProjectDeniedError(
            f"project {project_id!r} is not accessible to this user; the "
            "active project is unchanged"
        )

    resolved_provider.remember(request, project_id)
    return accessible[project_id]


def project_provider_endpoint() -> str:
    """The URL a picker fetches projects from, or ``""`` when nothing is declared.

    THE SLOT, as opposed to the RESOLUTION this module already owns. Resolution
    answers "which project is active"; the slot answers "where does anyone find
    out" — and it is a slot rather than a fixed path because only the host knows
    its own URL layout. scitex-ui owns both ends of it: the setting below and
    the ``<meta name="stx-project-provider">`` that advertises the URL to client
    code.

    DELEGATED, NOT REDECLARED. The obvious implementation copies the setting
    name (``SCITEX_PROJECT_PROVIDER_URL``) and its own reverse() call in here.
    That would make scitex-app a SECOND producer of a name scitex-ui already
    owns — two copies with no link between them, drifting silently, which is the
    forked-producer shape this contract exists to avoid. So the names are read
    from scitex-ui when it is installed, and this module only exposes the answer.

    FAIL-CLOSED: ``""`` when scitex-ui is absent, when no URL is declared, or
    when the declared name does not reverse. An empty endpoint is the truth —
    "no picker slot here" — whereas a guessed path or a self-link would render a
    picker that fetches the wrong thing.
    """
    try:
        from scitex_ui.project_scope import host_project_provider_url
    except ImportError:
        return ""
    try:
        return host_project_provider_url() or ""
    except Exception:
        # A broken reverse() must not take down a leaf page whose only
        # job here was to advertise a slot.
        return ""


def _standalone_provider_class():
    """``LocalProjectProvider`` bound to the standalone working directory.

    EXISTS BECAUSE THE LAUNCHER HAD NO PROVIDER TO REGISTER. scitex-ui reads a
    provider from ``settings.SCITEX_PROJECT_PROVIDER`` as a dotted path and
    instantiates it with NO arguments (see ``host_project_provider``), so a
    class needing a ``root`` — ``LocalProjectProvider`` — cannot be named there
    directly. This binds the root the launcher already resolved
    (``SCITEX_WORKING_DIR``, which ``run_standalone`` sets) and nothing else.

    Nothing is selected by construction: ``LocalProjectProvider`` lists the
    folders under the root and reports last-visited as absent until a user or a
    command stores one, so a fresh standalone session resolves to ``none`` and
    shows its picker. That is the documented standalone behaviour, and it is
    what keeps this from being an implicit example selection.

    Imported lazily: subclassing scitex-ui's provider must not make importing
    this module require scitex-ui, which scitex-app deliberately does not.
    """
    import os

    from scitex_ui.project_scope import LocalProjectProvider

    class StandaloneProjectProvider(LocalProjectProvider):
        """Every non-hidden folder under the standalone working directory."""

        def __init__(self) -> None:
            super().__init__(
                root=os.environ.get("SCITEX_WORKING_DIR") or os.getcwd()
            )

    return StandaloneProjectProvider


def __getattr__(name: str):
    """Resolve ``StandaloneProjectProvider`` on first use (PEP 562).

    A module-level attribute rather than a factory call, because
    ``import_string(STANDALONE_PROVIDER_PATH)`` has to FIND it here — the
    dotted path is the only channel the host setting offers. Defining the class
    eagerly at import time is what this avoids: it would make scitex-ui a hard
    import requirement of a module that must work without it.
    """
    if name == "StandaloneProjectProvider":
        return _standalone_provider_class()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


# EOF
