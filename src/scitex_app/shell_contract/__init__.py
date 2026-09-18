"""The mount-side app-shell contract: the props a leaf hands to the shell.

A leaf app (FigRecipe, Writer, Scholar, Stats, ...) does not own the header or
the navigation chrome — the presentation layer does (``scitex_ui``'s
``app-shell`` / ``standalone_shell``). What the leaf OWNS is the GENERIC
declaration of what belongs in that chrome:

  * **title**     the leaf's human name ("FigRecipe"), from its manifest label;
  * **version**   the leaf's INSTALLED package version — read through
                  ``ScitexAppConfig.app_version`` / ``package_version``, never a
                  hand-written manifest number (2026-07 incident: manifests
                  pinned at 0.14.0 while the packages shipped 2.25.0 / 0.29.9 /
                  1.4.2, so every tile showed a wrong version);
  * **project provider**  where the per-app project selector gets its projects
                  (URL + current + navigate target), or NOTHING for a
                  user-scoped app — see ``scitex_app._app_scope``: the global
                  header must never force a Project selector, and a user-scoped
                  app renders with no picker at all;
  * **actions**   header/command-bar entries, each pointing at a named command
                  or an href;
  * **named commands**  the command ids the leaf exposes, in the shape the
                  keymap registry already uses (``id -> {label, group,
                  sequence}``), so keyboard, touch and mouse reach the SAME
                  action by the same name.

WHAT THIS MODULE IS NOT. It carries no app business logic and no markup: it
does not know what "Save recipe" does, only that the leaf exposes an action by
that label bound to that command id. Rendering, gesture handling, 44px targets,
cascading selectors and overlay insets live in the presentation layer; this is
the DATA half of that split, and the split is the point — the alternative
measured in the fleet was each leaf hand-rolling its own header and drifting.

WHY THE PROPS ARE EMITTED AS ONE JSON META TAG. A reader with no writer is not
half a feature; it is a feature that reaches nobody. ``scitex_ui``'s
``mount.ts`` shipped a reader before anything emitted its marker, and every
consumer got a ``MountPrefixMissingError`` (see ``scitex_ui.mount``). So this
module ships the WRITER together with the shape: :func:`shell_props_meta_tag`
renders ``<meta name="stx-app-shell" content="{...json...}">``, the same
injection point as ``stx-mount`` and ``stx-app-scope``, and the absence of that
tag is a meaningful state ("nobody declared shell props") rather than an empty
one to be guessed at.

FAIL LOUD, NEVER GUESS. Every field is validated at construction: a blank
title, a scope typo, a duplicate action/command id, an action with no
affordance at all, or a project provider on a user-scoped app all RAISE. Each
of those renders as a page that looks perfectly fine — which is exactly the
class of defect this contract exists to prevent, so degrading to a guessed
value is not an option.

ZERO THIRD-PARTY DEPENDENCIES and no Django import at module scope: scitex-app's
base install is stdlib + click/rich/scitex-config, and the leaf-side surfaces
(CLI, MCP) must stay importable without Django.
"""

from __future__ import annotations

import html
import json
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

#: Name of the emitted ``<meta>``. The presentation layer reads this name; a
#: single-name contract is why it is a module constant rather than a literal
#: inlined at each call site.
SHELL_PROPS_META_NAME = "stx-app-shell"

#: Template-context key holding the same payload, for host surfaces that
#: render their own tag instead of using :func:`shell_props_meta_tag`.
SHELL_PROPS_CONTEXT_KEY = "stx_shell_props"

#: Default group for a command that declares none. Mirrors the keymap
#: registry's global group so an app's own commands sort together.
DEFAULT_COMMAND_GROUP = "App"

#: The ``<head>`` opening tag, and NOT ``<header>``. The delimiter after the
#: name is what stops ``<header>`` from matching; same rule as the mount and
#: scope markers.
_HEAD_OPEN_RE = re.compile(r"<head(?:\s[^>]*)?>", re.IGNORECASE)


class ShellContractError(ValueError):
    """A shell-props declaration is malformed.

    Raised at construction rather than rendered around: every condition this
    catches produces a page that renders fine, so silence would ship the defect.
    """


def _require_text(value: object, what: str) -> str:
    """Return ``value`` stripped, or raise if it is not non-blank text."""
    if not isinstance(value, str) or not value.strip():
        raise ShellContractError(
            f"{what} must be a non-blank string (got {value!r}); an empty "
            f"{what} renders as nothing at all and looks identical to a "
            "correctly configured app"
        )
    return value.strip()


@dataclass(frozen=True)
class ShellAction:
    """One action offered in the shell chrome.

    An action is an AFFORDANCE, so it must have somewhere to go: ``command``
    (a named command id the keymap registry resolves) or ``href`` (a URL).
    Both missing is refused — a button that does nothing renders exactly like
    a working one, which is the same silent dead end scitex-hub measured on
    ``/apps/storage/`` (zero anchor elements, HTTP 200, nothing to click).
    """

    id: str
    label: str
    command: str | None = None
    href: str | None = None
    order: int = 0

    def __post_init__(self) -> None:
        _require_text(self.id, "action id")
        _require_text(self.label, "action label")
        if not self.command and not self.href:
            raise ShellContractError(
                f"action {self.id!r} declares neither 'command' nor 'href'; "
                "an action with no affordance renders as a control that does "
                "nothing, indistinguishable from a working one. Declare the "
                "named command it triggers, or the href it opens."
            )
        if not isinstance(self.order, int) or isinstance(self.order, bool):
            raise ShellContractError(
                f"action {self.id!r} has a non-integer order ({self.order!r}); "
                "ordering must not depend on string comparison"
            )

    def as_payload(self) -> dict[str, Any]:
        """The action's JSON shape. ``command``/``href`` omitted when unset."""
        payload: dict[str, Any] = {
            "id": self.id,
            "label": self.label,
            "order": self.order,
        }
        if self.command:
            payload["command"] = self.command
        if self.href:
            payload["href"] = self.href
        return payload


@dataclass(frozen=True)
class ShellCommand:
    """A named command the leaf exposes to the shell.

    Same shape as the presentation layer's keymap registry entries
    (``label`` / ``group`` / ``sequence``), so the id is the stable name that
    keyboard, touch and mouse all resolve to — which is what "touch/mouse/
    keyboard parity" means in practice: one command, three ways in, no
    per-platform aliases.
    """

    id: str
    label: str
    group: str = DEFAULT_COMMAND_GROUP
    sequence: str | None = None

    def __post_init__(self) -> None:
        _require_text(self.id, "command id")
        _require_text(self.label, "command label")
        _require_text(self.group, "command group")
        if self.sequence is not None:
            _require_text(self.sequence, "command sequence")

    def as_payload(self) -> dict[str, Any]:
        """The command's JSON shape, mirroring the keymap registry's keys."""
        payload: dict[str, Any] = {
            "label": self.label,
            "group": self.group,
        }
        if self.sequence:
            payload["sequence"] = self.sequence
        return payload


@dataclass(frozen=True)
class ProjectProvider:
    """Where a project-scoped app's selector gets its projects.

    A DECLARATION, not a fetch: ``url`` is the provider endpoint the shell
    calls (the shape ``scitex_ui``'s ``_project_picker.html`` already reads as
    ``data-provider-url``), ``current`` is the active project id, ``navigate``
    where a selection goes, and ``placeholder`` the empty-selection label.

    The SDK does not know what a project IS — it only carries the app's
    declaration to the surface that renders it.
    """

    url: str
    current: str = ""
    navigate: str = ""
    placeholder: str = ""

    def __post_init__(self) -> None:
        _require_text(self.url, "project provider url")

    def as_payload(self) -> dict[str, Any]:
        """The provider's JSON shape, omitting empty optional fields."""
        payload: dict[str, Any] = {"url": self.url}
        for key in ("current", "navigate", "placeholder"):
            value = getattr(self, key)
            if value:
                payload[key] = value
        return payload


@dataclass(frozen=True)
class ShellProps:
    """The whole declaration one mounted leaf hands to the shell chrome.

    Assembled with :func:`shell_props_from_app_config` (which reads the real
    ``ScitexAppConfig``) or constructed directly in a test.
    """

    app: str
    title: str
    version: str
    scope: str
    project: ProjectProvider | None = None
    actions: Sequence[ShellAction] = field(default_factory=tuple)
    commands: Sequence[ShellCommand] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        _require_text(self.app, "app slug")
        _require_text(self.title, "app title")
        _require_text(self.version, "app version")

        from .._app_scope import SCOPE_PROJECT, normalize_scope

        # normalize_scope raises on a typo rather than guessing, and this is
        # the one field that decides whether a project picker may appear.
        scope = normalize_scope(self.scope)
        object.__setattr__(self, "scope", scope)

        if scope != SCOPE_PROJECT and self.project is not None:
            raise ShellContractError(
                f"app {self.app!r} is {scope}-scoped but declares a project "
                "provider. A user-scoped app renders with NO project selector "
                "(the global header never forces one), so a provider here is "
                "an affordance that must not exist. Drop the provider, or "
                "declare scope='project'."
            )

        object.__setattr__(self, "actions", tuple(self.actions))
        object.__setattr__(self, "commands", tuple(self.commands))
        self._refuse_duplicate_ids(self.actions, "action")
        self._refuse_duplicate_ids(self.commands, "command")

    @staticmethod
    def _refuse_duplicate_ids(items: Sequence[Any], what: str) -> None:
        """Raise if two entries share an id.

        The id is the identity the client resolves by, so a duplicate is not a
        cosmetic problem: it makes "which one runs?" depend on iteration order,
        and both entries render as if they were distinct.
        """
        seen: list[str] = []
        for item in items:
            if item.id in seen:
                raise ShellContractError(
                    f"duplicate {what} id {item.id!r}; ids are what the client "
                    "resolves commands and actions by, so two entries sharing "
                    "one make the outcome depend on iteration order"
                )
            seen.append(item.id)

    def as_payload(self) -> dict[str, Any]:
        """The JSON payload, deterministically ordered.

        Actions and commands are emitted in a stable order (declared
        ``order``, then id) so two renders of one declaration are byte-identical
        — which is what makes the emitted tag comparable across a server render
        and a client re-read.
        """
        payload: dict[str, Any] = {
            "app": self.app,
            "title": self.title,
            "version": self.version,
            "scope": self.scope,
            "actions": [
                action.as_payload()
                for action in sorted(self.actions, key=lambda a: (a.order, a.id))
            ],
            "commands": {
                command.id: command.as_payload()
                for command in sorted(self.commands, key=lambda c: c.id)
            },
        }
        if self.project is not None:
            payload["project"] = self.project.as_payload()
        return payload


def shell_props_from_app_config(
    app_config: Any,
    *,
    project: ProjectProvider | None = None,
    actions: Sequence[ShellAction] = (),
    commands: Sequence[ShellCommand] = (),
) -> ShellProps:
    """Build :class:`ShellProps` from a mounted ``ScitexAppConfig``.

    Title, version and scope come from the app's OWN declarations — manifest
    ``label`` (falling back to the config's ``verbose_name``), the installed
    dist via ``app_config.app_version``, and ``app_config.app_scope``. Nothing
    is re-derived here, so the version shown in the chrome cannot drift from
    the version the rest of the SDK reports.

    ``project``, ``actions`` and ``commands`` are the leaf's own declarations:
    they are passed in rather than read from the manifest because the manifest
    schema is closed (a new key is a published-contract change), and because an
    app's actions are Python (a view name, a command id) rather than data.
    """
    manifest: Mapping[str, Any] = getattr(app_config, "manifest", {}) or {}
    title = manifest.get("label") or getattr(app_config, "verbose_name", "")
    return ShellProps(
        app=getattr(app_config, "app_slug", getattr(app_config, "label", "")),
        title=title,
        version=app_config.app_version,
        scope=app_config.app_scope,
        project=project,
        actions=actions,
        commands=commands,
    )


def shell_props_json(props: ShellProps) -> str:
    """Compact, key-sorted JSON for ``props`` — no spaces, stable bytes."""
    return json.dumps(
        props.as_payload(), separators=(",", ":"), sort_keys=True, ensure_ascii=False
    )


def shell_props_meta_tag(props: ShellProps) -> str:
    """The ``<meta>`` tag the shell chrome reads, carrying the props as JSON.

    The payload is HTML-escaped: it can legitimately contain quotes and angle
    brackets (a label, a placeholder), and an unescaped one would terminate
    the attribute early — producing a tag the reader silently cannot parse.
    """
    payload = html.escape(shell_props_json(props), quote=True)
    return f'<meta name="{SHELL_PROPS_META_NAME}" content="{payload}">'


def inject_shell_props(html_source: str, props: ShellProps) -> str:
    """Insert the props tag after the ``<head>`` open tag.

    Same placement rules as the ``stx-mount`` and ``stx-app-scope`` markers:
    after ``<head ...>``, prepended when the document has no ``<head>`` at all
    (a fragment render is not an excuse to drop the declaration).
    """
    tag = shell_props_meta_tag(props)
    head_open = _HEAD_OPEN_RE.search(html_source)
    if head_open:
        return html_source[: head_open.end()] + tag + html_source[head_open.end() :]
    return tag + html_source


def shell_props_context(props: ShellProps) -> dict[str, Any]:
    """Template context exposing the payload under :data:`SHELL_PROPS_CONTEXT_KEY`.

    For a host surface that renders its own tag (a non-Django template, or a
    shell that injects props itself) — the Django path uses
    :func:`shell_props_meta_tag` / :func:`inject_shell_props` instead.
    """
    return {SHELL_PROPS_CONTEXT_KEY: props.as_payload()}
