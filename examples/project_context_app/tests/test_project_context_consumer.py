#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""The reference consumer's claims, as an executable test.

WHAT A REFERENCE CONSUMER HAS TO PROVE, and why each assertion here can fail:

  * a leaf renders the state it was HANDED — no arm is invented, and `none`
    and `unavailable` do not render identically;
  * a refused change is a refusal the caller can see, and it leaves the active
    project ALONE;
  * two users do not see each other's projects;
  * no filesystem path reaches the page.

Provider-backed arms need scitex-ui (it supplies ``LocalProjectProvider`` and
``host_project_provider``); scitex-app's own CI runs without it, so those arms
are SKIPPED there rather than weakened. The arms that run everywhere — the
`unavailable` render, the refusal mapping, and "a page never 500s" — are the
ones that hold with no provider at all, which is the state a fresh host is in.

The fixture is the SHIPPED standalone provider, so this exercises production
code end to end. No mocks (PA-306).
"""

from __future__ import annotations

import os
import tempfile

import django
import pytest
from django.conf import settings

_PROVIDER = "scitex_app.project_context.StandaloneProjectProvider"

if not settings.configured:
    settings.configure(
        DEFAULT_CHARSET="utf-8",
        ALLOWED_HOSTS=["*"],
        DATABASES={},
        INSTALLED_APPS=["django.contrib.contenttypes", "scitex_app", "project_context"],
        ROOT_URLCONF="project_context.urls",
        TEMPLATES=[
            {
                "BACKEND": "django.template.backends.django.DjangoTemplates",
                "DIRS": [],
                "APP_DIRS": True,
                "OPTIONS": {},
            }
        ],
        SCITEX_PROJECT_PROVIDER=_PROVIDER,
    )
    django.setup()

from django.test import Client  # noqa: E402


def _projects_root(*names: str) -> str:
    """A project root holding ``names`` as folders — what a provider lists."""
    root = tempfile.mkdtemp(prefix="stx-consumer-")
    for name in names:
        os.makedirs(os.path.join(root, name))
    return root


def _client() -> Client:
    return Client()


# ── Arms that hold with no provider at all ───────────────────────────────────


def test_the_page_renders_rather_than_500s():
    """A provider that cannot answer must not make a leaf page unrenderable."""
    # Arrange
    os.environ["SCITEX_WORKING_DIR"] = _projects_root()
    client = _client()
    # Act
    response = client.get("/")
    # Assert
    assert response.status_code == 200


def test_the_page_reports_a_state_it_was_handed():
    # Arrange
    os.environ["SCITEX_WORKING_DIR"] = _projects_root()
    client = _client()
    # Act
    body = client.get("/").content.decode()
    # Assert
    assert 'data-state="' in body


def test_the_unavailable_arm_renders_distinctly_from_no_selection():
    """`we could not ask` and `you have none` must not look the same.

    Rendered directly from the template, because the two arms cannot both be
    reached through one configured process — and distinctness of the two
    renderings is the claim, not the code path that produces each state.
    """
    # Arrange
    from django.template.loader import render_to_string

    # Act
    unavailable = render_to_string(
        "project_context/projects.html", {"project_state": "unavailable"}
    )
    nothing = render_to_string(
        "project_context/projects.html", {"project_state": "none"}
    )
    # Assert
    assert "temporarily unavailable" in unavailable and "temporarily unavailable" not in nothing


def test_the_change_endpoint_refuses_a_non_post():
    # Arrange
    os.environ["SCITEX_WORKING_DIR"] = _projects_root()
    client = _client()
    # Act
    response = client.get("/change")
    # Assert
    assert response.status_code == 405


# ── Provider-backed arms ─────────────────────────────────────────────────────


def test_no_project_is_selected_on_a_fresh_session():
    """Two projects EXIST, so `none` here is the fail-closed answer."""
    # Arrange
    pytest.importorskip("scitex_ui.project_scope")
    os.environ["SCITEX_WORKING_DIR"] = _projects_root("alpha", "beta")
    client = _client()
    # Act
    body = client.get("/").content.decode()
    # Assert
    assert 'data-state="none"' in body


def test_an_explicit_project_renders_as_the_active_one():
    # Arrange
    pytest.importorskip("scitex_ui.project_scope")
    os.environ["SCITEX_WORKING_DIR"] = _projects_root("alpha", "beta")
    client = _client()
    # Act
    body = client.get("/?project=alpha").content.decode()
    # Assert
    assert 'data-project-id="alpha"' in body


def test_the_selection_persists_to_the_next_page_load():
    # Arrange
    pytest.importorskip("scitex_ui.project_scope")
    os.environ["SCITEX_WORKING_DIR"] = _projects_root("alpha", "beta")
    client = _client()
    client.get("/?project=alpha")
    # Act
    body = client.get("/").content.decode()
    # Assert
    assert 'data-project-id="alpha"' in body


def test_an_unknown_project_renders_denied_and_not_a_substitute():
    # Arrange
    pytest.importorskip("scitex_ui.project_scope")
    os.environ["SCITEX_WORKING_DIR"] = _projects_root("alpha", "beta")
    client = _client()
    client.get("/?project=alpha")
    # Act
    body = client.get("/?project=not-mine").content.decode()
    # Assert — denied, and NOT the stored project the user did not ask for
    assert 'data-state="denied"' in body and 'data-project-id="alpha"' not in body


def test_no_filesystem_path_reaches_the_page():
    # Arrange
    pytest.importorskip("scitex_ui.project_scope")
    os.environ["SCITEX_WORKING_DIR"] = _projects_root("alpha")
    client = _client()
    # Act
    body = client.get("/?project=alpha").content.decode()
    # Assert
    assert os.environ["SCITEX_WORKING_DIR"] not in body


def test_the_page_never_shows_an_internal_master_path():
    # Arrange
    pytest.importorskip("scitex_ui.project_scope")
    os.environ["SCITEX_WORKING_DIR"] = _projects_root("alpha")
    client = _client()
    # Act
    body = client.get("/?project=alpha").content.decode()
    # Assert
    assert "MASTER" not in body


# ── Two-user isolation, at the consumer ──────────────────────────────────────


def test_one_users_project_is_not_offered_to_another_user():
    """Two roots are two users' project sets; neither resolves the other's."""
    # Arrange
    pytest.importorskip("scitex_ui.project_scope")
    os.environ["SCITEX_WORKING_DIR"] = _projects_root("alice-only")
    alice = _client()
    alice.get("/?project=alice-only")
    os.environ["SCITEX_WORKING_DIR"] = _projects_root("bob-only")
    bob = _client()
    # Act
    body = bob.get("/").content.decode()
    # Assert — bob has no stored project, and alice's is not his to inherit
    assert 'data-state="none"' in body


def test_another_users_change_command_is_refused():
    # Arrange
    pytest.importorskip("scitex_ui.project_scope")
    os.environ["SCITEX_WORKING_DIR"] = _projects_root("bob-only")
    client = _client()
    # Act
    response = client.post("/change", {"project": "alice-only"})
    # Assert
    assert response.status_code == 403


def test_a_refused_change_leaves_the_active_project_alone():
    # Arrange
    pytest.importorskip("scitex_ui.project_scope")
    os.environ["SCITEX_WORKING_DIR"] = _projects_root("alice-only")
    client = _client()
    client.get("/?project=alice-only")
    # Act
    client.post("/change", {"project": "not-mine"})
    # Assert
    body = client.get("/").content.decode()
    assert 'data-project-id="alice-only"' in body


def test_an_accessible_change_is_applied_and_reported():
    # Arrange
    pytest.importorskip("scitex_ui.project_scope")
    os.environ["SCITEX_WORKING_DIR"] = _projects_root("alpha", "beta")
    client = _client()
    # Act
    response = client.post("/change", {"project": "beta"})
    # Assert
    assert response.json() == {"id": "beta", "name": "beta"}
