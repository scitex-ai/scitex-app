#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Test file for: scitex_app/sdk/auth/_paths.py

"""Tests for auth-directory resolution and the ssh-parallel file names."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from scitex_app.sdk.auth import (
    UnsafeUsername,
    auth_dir_candidates,
    client_config_path,
    resolve_auth_dir,
    server_config_path,
    user_dir,
    validate_username,
)
from scitex_app.sdk.auth._paths import AUTH_DIR_ENV_TEMPLATE


@pytest.fixture
def auth_env():
    """Set/restore the per-app auth-dir override around a test.

    Real env manipulation, restored on teardown, so tests do not leak into
    each other.
    """
    touched: list[str] = []
    saved: dict[str, str | None] = {}

    def _set(app, value):
        name = AUTH_DIR_ENV_TEMPLATE.format(app_upper=app.upper().replace("-", "_"))
        if name not in saved:
            saved[name] = os.environ.get(name)
            touched.append(name)
        if value is None:
            os.environ.pop(name, None)
        else:
            os.environ[name] = str(value)

    try:
        yield _set
    finally:
        for name in touched:
            if saved[name] is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = saved[name]


def test_project_candidate_comes_before_home(tmp_path):
    # Arrange
    # Act
    candidates = auth_dir_candidates("cards", tmp_path)
    # Assert
    assert candidates[0] == tmp_path / ".scitex" / "cards" / "auth"


def test_home_is_the_fallback_candidate(tmp_path):
    # Arrange
    # Act
    candidates = auth_dir_candidates("cards", tmp_path)
    # Assert
    assert candidates[-1] == Path.home() / ".scitex" / "cards" / "auth"


def test_without_a_project_only_home_is_considered():
    # Arrange
    # Act
    candidates = auth_dir_candidates("cards", None)
    # Assert
    assert len(candidates) == 1


def test_env_override_replaces_every_candidate(tmp_path, auth_env):
    # Arrange
    # Falling back PAST an explicit override would mean the operator asked for
    # one file and silently got another.
    auth_env("cards", tmp_path / "elsewhere")
    # Act
    candidates = auth_dir_candidates("cards", tmp_path)
    # Assert
    assert candidates == [tmp_path / "elsewhere"]


def test_resolve_returns_none_when_nothing_is_configured(tmp_path, auth_env):
    # Arrange
    auth_env("neverconfigured", tmp_path / "absent")
    # Act
    resolved = resolve_auth_dir("neverconfigured", tmp_path)
    # Assert
    assert resolved is None


def test_resolve_prefers_the_project_directory(tmp_path):
    # Arrange
    project_auth = tmp_path / ".scitex" / "cards" / "auth"
    project_auth.mkdir(parents=True)
    # Act
    resolved = resolve_auth_dir("cards", tmp_path)
    # Assert
    assert resolved == project_auth


def test_server_config_is_named_like_sshd_config(tmp_path):
    # Arrange
    # Act
    path = server_config_path(tmp_path, "cards")
    # Assert
    assert path.name == "cardsd_config"


def test_client_config_is_named_like_ssh_config(tmp_path):
    # Arrange
    # Act
    path = client_config_path(tmp_path, "cards")
    # Assert
    assert path.name == "cards_config"


def test_identity_is_carried_by_the_directory_name(tmp_path):
    # Arrange
    # Act
    path = user_dir(tmp_path, "ywatanabe")
    # Assert
    assert path == tmp_path / "users" / "ywatanabe"


# ---------------------------------------------------------------------------
# USERNAME VALIDATION — the input an attacker controls.
#
# These did not exist, and their absence is why a path traversal survived 87
# tests: every username fixture was well-formed, so nothing exercised the one
# value a client supplies. Same failure mode as the hand-typed ed25519 fixture
# that hid the undecodable-key bug — a fixture that looks like real input tests
# only inputs that look real.
#
# Reported by scitex-app with a working exploit; reproduced before fixing.
# ---------------------------------------------------------------------------


def test_a_plain_name_is_accepted():
    # Arrange
    # Act
    result = validate_username("ywatanabe")
    # Assert
    assert result == "ywatanabe"


def test_a_traversal_username_is_refused():
    # Arrange
    raised = None
    # Act
    try:
        validate_username("../../../../../elsewhere")
    except UnsafeUsername as exc:
        raised = exc
    # Assert
    assert raised is not None


def test_an_absolute_username_is_refused():
    # Arrange
    # pathlib DISCARDS the left operand when the right is absolute:
    # Path("/a/users") / "/tmp/x" is Path("/tmp/x"). No ".." required, and no
    # inspection of the joined path would reveal it.
    raised = None
    # Act
    try:
        validate_username("/tmp/elsewhere")
    except UnsafeUsername as exc:
        raised = exc
    # Assert
    assert raised is not None


def test_a_bare_parent_reference_is_refused():
    # Arrange
    raised = None
    # Act
    try:
        validate_username("..")
    except UnsafeUsername as exc:
        raised = exc
    # Assert
    assert raised is not None


def test_a_bare_current_reference_is_refused():
    # Arrange
    raised = None
    # Act
    try:
        validate_username(".")
    except UnsafeUsername as exc:
        raised = exc
    # Assert
    assert raised is not None


def test_an_embedded_forward_slash_is_refused():
    # Arrange
    raised = None
    # Act
    try:
        validate_username("alice/bob")
    except UnsafeUsername as exc:
        raised = exc
    # Assert
    assert raised is not None


def test_an_embedded_backslash_is_refused():
    # Arrange
    # Refused on every platform, not only where it is the native separator: a
    # name legal here must not become a path when the store is read elsewhere.
    raised = None
    # Act
    try:
        validate_username("alice\\bob")
    except UnsafeUsername as exc:
        raised = exc
    # Assert
    assert raised is not None


def test_an_empty_username_is_refused():
    # Arrange
    raised = None
    # Act
    try:
        validate_username("")
    except UnsafeUsername as exc:
        raised = exc
    # Assert
    assert raised is not None


def test_a_nul_byte_in_a_username_is_refused():
    # Arrange
    # Constructed with chr(0) rather than written literally: a NUL in source is
    # its own hazard, and tooling that scans for one should not find it here.
    raised = None
    # Act
    try:
        validate_username("al" + chr(0) + "ice")
    except UnsafeUsername as exc:
        raised = exc
    # Assert
    assert raised is not None


def test_user_dir_returns_a_child_of_users_for_a_plain_name(tmp_path):
    # Arrange
    (tmp_path / "users" / "alice").mkdir(parents=True)
    # Act
    resolved = user_dir(tmp_path, "alice")
    # Assert
    assert resolved == tmp_path / "users" / "alice"


def test_a_symlinked_user_directory_is_refused(tmp_path):
    # Arrange
    # The STRING check cannot see this: "sneaky" is a perfectly good name. Only
    # containment-after-resolve catches it, which is why user_dir resolves.
    outside = tmp_path / "outside"
    outside.mkdir()
    (tmp_path / "users").mkdir()
    (tmp_path / "users" / "sneaky").symlink_to(outside)
    raised = None
    # Act
    try:
        user_dir(tmp_path, "sneaky")
    except UnsafeUsername as exc:
        raised = exc
    # Assert
    assert raised is not None


def test_the_refusal_names_the_offending_username(tmp_path):
    # Arrange
    raised = None
    # Act
    try:
        validate_username("alice/bob")
    except UnsafeUsername as exc:
        raised = exc
    # Assert
    assert "alice/bob" in str(raised)


def test_a_newline_in_a_username_is_refused():
    # Arrange
    # NOT a traversal — authentication already fails for this name. It is an
    # AUDIT-INTEGRITY rule: the username reaches the Trace, and a Trace is
    # rendered into a log, so a name containing a newline can write a whole
    # forged line such as "Accepted password for root" into the record that
    # exists to explain what happened. sshd escapes non-printables in logged
    # usernames for exactly this reason.
    hostile = "alice" + chr(10) + "Accepted password for root"
    raised = None
    # Act
    try:
        validate_username(hostile)
    except UnsafeUsername as exc:
        raised = exc
    # Assert
    assert raised is not None


def test_a_control_character_in_a_username_is_refused():
    # Arrange
    raised = None
    # Act
    try:
        validate_username("alice" + chr(7))
    except UnsafeUsername as exc:
        raised = exc
    # Assert
    assert raised is not None


def test_the_non_printable_refusal_names_the_offending_index():
    # Arrange
    # The offending character cannot be echoed into the message — that would
    # reproduce the injection inside the refusal. The INDEX locates it without
    # carrying it.
    raised = None
    # Act
    try:
        validate_username("alice" + chr(10) + "x")
    except UnsafeUsername as exc:
        raised = exc
    # Assert
    assert "index 5" in str(raised)


# EOF
