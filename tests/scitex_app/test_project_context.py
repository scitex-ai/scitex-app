#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""The leaf-facing project-context contract (scitex-hub PR 923).

SSOT: scitex-hub ``docs/product/PRIVATE_BETA_LOGIN_TO_WOW.md``.

    "Project context is selected once and carried across every leaf app."
    "Canonical project picker ... displays user-facing project names, never
     internal ``MASTER/`` paths."
    "Real users never receive a silently created or selected example project."
    "UI actions map to stable named commands so mouse, touch, keyboard,
     macros, and agents invoke the same operations."

WHAT THESE TESTS PIN, and why each one can fail:

  * the authorized DESCRIPTOR a leaf is handed, and that it carries no
    filesystem path — the MASTER-path rule made structural;
  * the provider/slot contract this module consumes, asserted against
    scitex-ui's own published shape so the two cannot drift;
  * route/query and session persistence, each measured across TWO requests;
  * the stable named change-project command, addressed by identity;
  * fail-closed missing / invalid / denied states, including that a REFUSED
    command leaves the previous selection untouched;
  * TWO-USER ISOLATION: one user's project never resolves for another user.

One assertion per test (STX-TQ007); AAA markers on their own lines (STX-TQ002).
No mocks (PA-306): ``_RecordedProvider`` below is a real in-memory provider, so
the tests exercise the production code path end to end.

The provider is injected rather than read from Django settings on purpose: it
keeps this suite runnable where scitex-ui is absent (scitex-app's own CI runs
without it), which is also why the protocol shape is asserted separately.
"""

from __future__ import annotations

import dataclasses

import django
import pytest
from django.conf import settings
from django.test import RequestFactory

if not settings.configured:
    # Identical in every scitex-app django test module: Django configures
    # settings once per process and the module order is not ours to choose, so
    # the blocks must agree or the fixture depends on luck.
    settings.configure(
        DEFAULT_CHARSET="utf-8",
        ALLOWED_HOSTS=["*"],
        DATABASES={},
        INSTALLED_APPS=["django.contrib.contenttypes"],
    )
    django.setup()

from scitex_app.project_context import (  # noqa: E402
    CHANGE_PROJECT_COMMAND,
    PROJECT_QUERY_PARAM,
    STANDALONE_PROVIDER_PATH,
    STATE_DENIED,
    STATE_NONE,
    STATE_OK,
    STATE_UNAVAILABLE,
    ActiveProject,
    ProjectDeniedError,
    ProjectResolution,
    ProjectUnavailableError,
    change_project,
    project_context,
    resolve_active_project,
)

#: Two users, disjoint project sets. THE FIXTURE THE CARD REQUIRES: isolation is
#: only measurable with more than one user's data present, so a single-user
#: fixture would pass while the leak is live.
_ACCESS = {
    "alice": ["neuro-paper", "grant-2026"],
    "bob": ["bob-only"],
}

_NAMES = {
    "neuro-paper": "Neuro paper",
    "grant-2026": "Grant 2026",
    "bob-only": "Bob only",
}


class _Entry:
    """One provider entry. ``detail`` mirrors scitex-ui's path-bearing field."""

    def __init__(self, id: str, name: str, detail: str = "") -> None:
        self.id = id
        self.name = name
        self.detail = detail


class _RecordedProvider:
    """A real in-memory provider: two users, disjoint projects, stored choice.

    Not a mock. It implements scitex-ui's three-method protocol for real, so a
    failure here is a failure of the production resolution path.
    """

    def __init__(self, user: str) -> None:
        self.user = user
        self.stored: dict[str, str] = {}
        self.remembered: list[tuple[str, str]] = []

    def list_projects(self, request=None):
        return [
            # detail deliberately carries an INTERNAL path, exactly as
            # scitex-ui's LocalProjectProvider fills it, so the descriptor's
            # refusal to expose one is measured and not merely asserted in prose.
            _Entry(pid, _NAMES[pid], detail=f"/internal/MASTER/{pid}")
            for pid in _ACCESS[self.user]
        ]

    def last_visited(self, request=None):
        return self.stored.get(self.user)

    def remember(self, request, project_id):
        self.stored[self.user] = project_id
        self.remembered.append((self.user, project_id))


def _request(query: dict | None = None):
    return RequestFactory().get("/", data=query or {})


# ── The authorized descriptor ────────────────────────────────────────────────


def test_explicit_project_resolves_to_an_authorized_descriptor():
    # Arrange
    provider = _RecordedProvider("alice")
    request = _request({"project": "neuro-paper"})
    # Act
    resolution = resolve_active_project(request, provider)
    # Assert
    assert resolution.project == ActiveProject(id="neuro-paper", name="Neuro paper")


def test_a_resolved_project_reports_the_ok_state():
    # Arrange
    provider = _RecordedProvider("alice")
    request = _request({"project": "neuro-paper"})
    # Act
    state = resolve_active_project(request, provider).state
    # Assert
    assert state == STATE_OK


def test_descriptor_exposes_no_filesystem_path():
    # Arrange — the provider fills ``detail`` with an internal MASTER path.
    provider = _RecordedProvider("alice")
    request = _request({"project": "neuro-paper"})
    # Act
    payload = resolve_active_project(request, provider).project.as_dict()
    # Assert
    assert "MASTER" not in repr(payload)


def test_descriptor_name_is_the_user_facing_label():
    # Arrange
    provider = _RecordedProvider("alice")
    request = _request({"project": "grant-2026"})
    # Act
    name = resolve_active_project(request, provider).project.name
    # Assert — a label, never the id-as-path and never the internal detail
    assert name == "Grant 2026"


def test_a_provider_entry_without_a_name_falls_back_to_its_id():
    # Arrange — a nameless entry must not become an empty or invented label.
    class _Nameless(_RecordedProvider):
        def list_projects(self, request=None):
            return [_Entry("grant-2026", "")]

    provider = _Nameless("alice")
    request = _request({"project": "grant-2026"})
    # Act
    resolution = resolve_active_project(request, provider)
    # Assert
    assert resolution.project.name == "grant-2026"


# ── The provider / slot contract ─────────────────────────────────────────────


def test_the_consumed_provider_protocol_matches_scitex_ui():
    """The wrapper and scitex-ui must not drift into two different protocols.

    Read from the INSTALLED scitex-ui when it is present; when it is absent
    (scitex-app's own CI), the assertion is skipped rather than weakened —
    a skip is visible, whereas a relaxed assertion is not.
    """
    # Arrange
    import pytest

    scitex_ui_project_scope = pytest.importorskip("scitex_ui.project_scope")
    # Act
    declared = {
        "list_projects",
        "last_visited",
        "remember",
    } <= set(dir(scitex_ui_project_scope.ProjectProvider))
    # Assert
    assert declared


def test_the_query_param_agrees_with_scitex_ui():
    # Arrange
    import pytest

    scitex_ui_project_scope = pytest.importorskip("scitex_ui.project_scope")
    # Act
    agreed = scitex_ui_project_scope.PROJECT_QUERY_PARAM == PROJECT_QUERY_PARAM
    # Assert
    assert agreed


# ── Route/query and session persistence ──────────────────────────────────────


def test_an_explicit_project_is_remembered_for_the_next_request():
    # Arrange
    provider = _RecordedProvider("alice")
    # Act
    resolve_active_project(_request({"project": "grant-2026"}), provider)
    # Assert
    assert provider.stored["alice"] == "grant-2026"


def test_the_stored_project_carries_across_requests_without_a_query_param():
    # Arrange
    provider = _RecordedProvider("alice")
    provider.remember(_request(), "neuro-paper")
    # Act — a later request that names no project at all
    resolution = resolve_active_project(_request(), provider)
    # Assert
    assert resolution.project.id == "neuro-paper"


def test_an_explicit_project_overrides_the_stored_one():
    # Arrange
    provider = _RecordedProvider("alice")
    provider.remember(_request(), "neuro-paper")
    # Act
    resolution = resolve_active_project(_request({"project": "grant-2026"}), provider)
    # Assert
    assert resolution.project.id == "grant-2026"


# ── Fail-closed states ───────────────────────────────────────────────────────


def test_no_selection_reports_none_rather_than_picking_one():
    # Arrange — two accessible projects and no stored choice.
    provider = _RecordedProvider("alice")
    # Act
    resolution = resolve_active_project(_request(), provider)
    # Assert — the app shows its picker; nothing is auto-selected
    assert resolution.state == STATE_NONE


def test_nothing_selected_hands_over_no_project():
    # Arrange
    provider = _RecordedProvider("alice")
    # Act
    project = resolve_active_project(_request(), provider).project
    # Assert
    assert project is None


def test_an_unknown_project_is_denied():
    # Arrange
    provider = _RecordedProvider("alice")
    # Act
    resolution = resolve_active_project(_request({"project": "no-such"}), provider)
    # Assert
    assert resolution.state == STATE_DENIED


def test_a_denied_explicit_project_never_falls_back_to_the_stored_one():
    """The defect this rule exists for: substituting a project nobody asked for."""
    # Arrange
    provider = _RecordedProvider("alice")
    provider.remember(_request(), "neuro-paper")
    # Act
    resolution = resolve_active_project(_request({"project": "no-such"}), provider)
    # Assert
    assert resolution.project is None


def test_a_stored_project_that_is_no_longer_accessible_reports_none():
    # Arrange — the stored id is not in this user's accessible set.
    provider = _RecordedProvider("alice")
    provider.remember(_request(), "bob-only")
    # Act
    resolution = resolve_active_project(_request(), provider)
    # Assert
    assert resolution.state == STATE_NONE


def test_no_provider_reports_unavailable_without_inventing_a_project():
    # Arrange — an explicit provider of None falls through to the host lookup,
    # which finds none in this process.
    request = _request()
    # Act
    resolution = resolve_active_project(request)
    # Assert
    assert resolution.state == STATE_UNAVAILABLE


def test_unavailable_state_names_why():
    # Arrange
    request = _request()
    # Act
    reason = resolve_active_project(request).reason
    # Assert — an operator reading the state learns the actual cause
    assert reason


def test_a_resolution_that_is_not_ok_cannot_carry_a_project():
    # Arrange
    inconsistent = {"state": STATE_NONE, "project": ActiveProject("a", "A")}
    # Act
    try:
        ProjectResolution(**inconsistent)
    except ValueError:
        raised = True
    else:
        raised = False
    # Assert
    assert raised


# ── The named change-project command ─────────────────────────────────────────


def test_the_command_has_a_stable_declared_name():
    # Arrange
    expected = "scitex.project.change"
    # Act
    name = CHANGE_PROJECT_COMMAND
    # Assert
    assert name == expected


def test_the_command_changes_and_persists_the_active_project():
    # Arrange
    provider = _RecordedProvider("alice")
    # Act
    changed = change_project(_request(), "grant-2026", provider)
    # Assert
    assert changed == ActiveProject(id="grant-2026", name="Grant 2026")


def test_the_command_is_visible_to_the_next_request():
    # Arrange
    provider = _RecordedProvider("alice")
    # Act
    change_project(_request(), "grant-2026", provider)
    # Assert
    assert provider.last_visited(_request()) == "grant-2026"


def test_the_command_refuses_an_inaccessible_project():
    # Arrange
    provider = _RecordedProvider("alice")
    # Act
    denied = False
    try:
        change_project(_request(), "bob-only", provider)
    except ProjectDeniedError:
        denied = True
    # Assert
    assert denied


def test_a_refused_command_leaves_the_previous_selection_untouched():
    """A refused command must not half-apply."""
    # Arrange
    provider = _RecordedProvider("alice")
    provider.remember(_request(), "neuro-paper")
    # Act
    try:
        change_project(_request(), "bob-only", provider)
    except ProjectDeniedError:
        pass
    # Assert
    assert provider.last_visited(_request()) == "neuro-paper"


def test_a_refused_command_records_nothing():
    # Arrange
    provider = _RecordedProvider("alice")
    # Act
    try:
        change_project(_request(), "no-such", provider)
    except ProjectDeniedError:
        pass
    # Assert
    assert provider.remembered == []


def test_the_command_refuses_an_empty_id():
    # Arrange
    provider = _RecordedProvider("alice")
    # Act
    refused = False
    try:
        change_project(_request(), "", provider)
    except ValueError:
        refused = True
    # Assert
    assert refused


# ── Two-user isolation ───────────────────────────────────────────────────────


def test_one_users_project_does_not_resolve_for_another_user():
    # Arrange — alice's project, bob's provider.
    provider = _RecordedProvider("bob")
    # Act
    resolution = resolve_active_project(_request({"project": "neuro-paper"}), provider)
    # Assert
    assert resolution.project is None


def test_one_users_project_is_denied_for_another_user_not_silently_ignored():
    # Arrange
    provider = _RecordedProvider("bob")
    # Act
    state = resolve_active_project(_request({"project": "neuro-paper"}), provider).state
    # Assert
    assert state == STATE_DENIED


def test_one_users_stored_project_does_not_leak_into_another_users_session():
    # Arrange — alice selects a project; bob has his own provider.
    alice = _RecordedProvider("alice")
    change_project(_request(), "neuro-paper", alice)
    bob = _RecordedProvider("bob")
    # Act
    resolution = resolve_active_project(_request(), bob)
    # Assert
    assert resolution.project is None


def test_another_users_change_command_cannot_target_a_foreign_project():
    # Arrange
    provider = _RecordedProvider("bob")
    # Act
    denied = False
    try:
        change_project(_request(), "neuro-paper", provider)
    except ProjectDeniedError:
        denied = True
    # Assert
    assert denied


# ── The mount handoff ────────────────────────────────────────────────────────


def test_the_context_processor_hands_over_the_active_project():
    # Arrange
    provider = _RecordedProvider("alice")
    provider.remember(_request(), "neuro-paper")
    # Act
    context = project_context(_request(), provider)
    # Assert
    assert context["active_project"] == {"id": "neuro-paper", "name": "Neuro paper"}


def test_the_context_processor_reports_the_state_for_every_render():
    # Arrange
    provider = _RecordedProvider("alice")
    # Act
    context = project_context(_request(), provider)
    # Assert
    assert context["project_state"] == STATE_NONE


def test_the_context_processor_carries_the_command_name():
    """The command travels with the context so every input modality can address it."""
    # Arrange
    provider = _RecordedProvider("alice")
    # Act
    context = project_context(_request(), provider)
    # Assert
    assert context["project_command"] == CHANGE_PROJECT_COMMAND


def test_the_context_processor_hands_over_no_project_when_denied():
    # Arrange
    provider = _RecordedProvider("alice")
    # Act
    context = project_context(_request({"project": "bob-only"}), provider)
    # Assert
    assert context["active_project"] is None


# ── The contract's own shape ─────────────────────────────────────────────────


def test_project_resolution_is_frozen():
    # Arrange
    resolution = ProjectResolution(state=STATE_NONE)
    # Act
    frozen = dataclasses.is_dataclass(resolution) and resolution.__dataclass_params__.frozen
    # Assert
    assert frozen


# ── Provider failures are 'unavailable', not 'denied' and not 'none' ─────────


class _FailingProvider:
    """A provider that cannot answer. Real, not a mock: it simply raises."""

    def list_projects(self, request=None):
        raise OSError("the project store is unreachable")

    def last_visited(self, request=None):
        raise OSError("the project store is unreachable")

    def remember(self, request, project_id):
        raise OSError("the project store is unreachable")


def test_a_failing_provider_reports_unavailable():
    # Arrange
    provider = _FailingProvider()
    # Act
    state = resolve_active_project(_request(), provider).state
    # Assert
    assert state == STATE_UNAVAILABLE


def test_a_failing_provider_never_reads_as_no_project():
    """'we could not ask' must not masquerade as 'you have none'."""
    # Arrange
    provider = _FailingProvider()
    # Act
    state = resolve_active_project(_request(), provider).state
    # Assert
    assert state != STATE_NONE


def test_a_failing_provider_names_itself_in_the_reason():
    # Arrange
    provider = _FailingProvider()
    # Act
    reason = resolve_active_project(_request(), provider).reason
    # Assert
    assert "unreachable" in reason


def test_the_command_raised_on_a_failing_provider_is_not_a_permission_answer():
    # Arrange
    provider = _FailingProvider()
    # Act
    raised = None
    try:
        change_project(_request(), "neuro-paper", provider)
    except Exception as exc:
        raised = exc
    # Assert
    assert isinstance(raised, ProjectUnavailableError)


# ── The standalone provider (the mount handoff) ──────────────────────────────


def test_the_standalone_provider_path_names_this_module():
    # Arrange
    expected_module = "scitex_app.project_context"
    # Act
    module_path, _, attribute = STANDALONE_PROVIDER_PATH.rpartition(".")
    # Assert — so settings.SCITEX_PROJECT_PROVIDER can resolve it
    assert module_path == expected_module and attribute


def test_an_unknown_module_attribute_still_raises():
    # Arrange
    import scitex_app.project_context as module

    # Act
    try:
        _ = module.no_such_attribute
    except AttributeError as exc:
        raised = exc
    else:
        raised = None
    # Assert
    assert raised is not None


def test_the_standalone_provider_lists_the_working_directory(tmp_path=None):
    # Arrange — scitex-ui supplies LocalProjectProvider; absent in scitex-app's
    # own CI, where the assertion is SKIPPED rather than weakened.
    import os
    import tempfile

    import pytest

    pytest.importorskip("scitex_ui.project_scope")
    root = tempfile.mkdtemp(prefix="stx-projects-")
    os.makedirs(os.path.join(root, "alpha"))
    os.makedirs(os.path.join(root, "beta"))
    os.environ["SCITEX_WORKING_DIR"] = root
    # Act
    provider = _standalone_provider()
    ids = {entry.id for entry in provider.list_projects(None)}
    # Assert
    assert ids == {"alpha", "beta"}


def test_the_standalone_provider_selects_nothing_on_a_fresh_session():
    """The 'no silent example selection' rule, measured at the provider."""
    # Arrange
    import os
    import tempfile

    import pytest

    pytest.importorskip("scitex_ui.project_scope")
    root = tempfile.mkdtemp(prefix="stx-projects-")
    os.makedirs(os.path.join(root, "alpha"))
    os.environ["SCITEX_WORKING_DIR"] = root
    # Act
    resolution = resolve_active_project(_request(), _standalone_provider())
    # Assert — projects EXIST, so 'none' here is the fail-closed answer
    assert resolution.state == STATE_NONE


def _standalone_provider():
    """Build the launcher's provider the way the host setting does."""
    from django.utils.module_loading import import_string

    return import_string(STANDALONE_PROVIDER_PATH)()


# ── The provider/picker slot ─────────────────────────────────────────────────


def test_the_slot_is_empty_when_nothing_is_declared():
    """Fail-closed: no declared endpoint means no slot, not a guessed one."""
    # Arrange
    from scitex_app.project_context import project_provider_endpoint

    # Act
    endpoint = project_provider_endpoint()
    # Assert
    assert endpoint == ""


def test_the_slot_is_never_the_site_root():
    """A self-link would fetch the app's own root and look like a working picker."""
    # Arrange
    from scitex_app.project_context import project_provider_endpoint

    # Act
    endpoint = project_provider_endpoint()
    # Assert
    assert endpoint != "/"


def test_the_slot_returns_a_declared_literal_path():
    # Arrange
    pytest.importorskip("scitex_ui.project_scope")
    from django.test import override_settings

    from scitex_app.project_context import project_provider_endpoint

    declared = "/platform/api/project-scope"
    # Act
    with override_settings(SCITEX_PROJECT_PROVIDER_URL=declared):
        endpoint = project_provider_endpoint()
    # Assert
    assert endpoint == declared


def test_the_setting_name_we_delegate_through_is_scitex_uis():
    """One producer of the name, asserted rather than assumed."""
    # Arrange
    scitex_ui_project_scope = pytest.importorskip("scitex_ui.project_scope")
    # Act
    name = scitex_ui_project_scope.PROJECT_PROVIDER_URL_SETTING
    # Assert
    assert name == "SCITEX_PROJECT_PROVIDER_URL"


def test_the_advertised_meta_name_is_the_one_client_code_reads():
    # Arrange
    scitex_ui_project_scope = pytest.importorskip("scitex_ui.project_scope")
    # Act
    meta = scitex_ui_project_scope.PROJECT_PROVIDER_META_NAME
    # Assert
    assert meta == "stx-project-provider"


def test_the_context_carries_the_slot_for_the_template():
    # Arrange
    provider = _RecordedProvider("alice")
    # Act
    context = project_context(_request(), provider)
    # Assert
    assert "project_provider_endpoint" in context
