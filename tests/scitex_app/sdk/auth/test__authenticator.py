#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Test file for: scitex_app/sdk/auth/_authenticator.py, _users.py, _password.py

"""Tests for the authentication decision itself.

Keys here are built as GENUINE ssh-ed25519 blobs rather than hand-typed
strings, and that is not fussiness. The first end-to-end run of this package
used a hand-typed fixture whose base64 did not decode; it authenticated
successfully and logged a fingerprint reading "<unparseable>", which hid a real
defect — parse_authorized_keys accepted undecodable material, and since matching
is string equality a corrupted line kept granting access. A fixture that fakes
the shape fakes the bug along with it.
"""

from __future__ import annotations

import base64
import struct

import pytest

from scitex_app.sdk.auth import (
    AuthNotConfigured,
    Outcome,
    fingerprint,
    get_authenticator,
    hash_password,
    parse_authorized_keys,
)

PASSWORD = "correct horse battery staple"


def _ed25519_material(filler: bytes) -> str:
    """A real ssh-ed25519 blob: len+name, then len+32 bytes of key."""
    name = b"ssh-ed25519"
    point = (filler * 32)[:32]
    blob = struct.pack(">I", len(name)) + name + struct.pack(">I", 32) + point
    return base64.b64encode(blob).decode("ascii")


MINE = _ed25519_material(b"\x01")
OTHER = _ed25519_material(b"\x02")


@pytest.fixture
def project(tmp_path):
    """A project-scoped auth directory with one fully configured user."""
    root = tmp_path / "proj"
    users = root / ".scitex" / "cards" / "auth" / "users" / "ywatanabe"
    users.mkdir(parents=True)
    auth = root / ".scitex" / "cards" / "auth"
    for directory in (auth, auth / "users", users):
        directory.chmod(0o700)
    (auth / "cardsd_config").write_text(
        "PubkeyAuthentication yes\nPasswordAuthentication yes\n"
        "StrictModes yes\nLogLevel DEBUG2\n"
    )
    keys = users / "authorized_keys"
    keys.write_text(f"ssh-ed25519 {MINE} ywatanabe@note-win\n")
    keys.chmod(0o600)
    password = users / "password"
    password.write_text(hash_password(PASSWORD))
    password.chmod(0o600)
    return root


@pytest.fixture
def auth(project):
    return get_authenticator("cards", project_dir=project)


def test_correct_password_is_accepted(auth):
    # Arrange
    # Act
    result = auth.password("ywatanabe", PASSWORD)
    # Assert
    assert result.accepted is True


def test_accepted_result_carries_the_directory_name_as_subject(auth):
    # Arrange
    # Act
    result = auth.password("ywatanabe", PASSWORD)
    # Assert
    assert result.username == "ywatanabe"


def test_wrong_password_is_rejected(auth):
    # Arrange
    # Act
    result = auth.password("ywatanabe", "hunter2")
    # Assert
    assert result.accepted is False


def test_wrong_password_reports_wrong_credential(auth):
    # Arrange
    # Act
    result = auth.password("ywatanabe", "hunter2")
    # Assert
    assert result.outcome is Outcome.WRONG_CREDENTIAL


def test_unknown_user_does_not_raise(auth):
    # Arrange
    # Act
    result = auth.password("mallory", PASSWORD)
    # Assert
    assert result.accepted is False


def test_unknown_user_is_distinguishable_only_in_the_outcome(auth):
    # Arrange
    # Act
    result = auth.password("mallory", PASSWORD)
    # Assert
    assert result.outcome is Outcome.NO_SUCH_USER


def test_matching_public_key_is_accepted(auth):
    # Arrange
    # Act
    result = auth.publickey("ywatanabe", "ssh-ed25519", MINE)
    # Assert
    assert result.accepted is True


def test_non_matching_public_key_is_rejected(auth):
    # Arrange
    # Act
    result = auth.publickey("ywatanabe", "ssh-ed25519", OTHER)
    # Assert
    assert result.accepted is False


def test_trace_names_the_offered_key_by_fingerprint(auth):
    # Arrange
    expected = fingerprint("ssh-ed25519", OTHER)
    # Act
    result = auth.publickey("ywatanabe", "ssh-ed25519", OTHER)
    lines = result.trace.rendered(auth.config.log_level)
    # Assert
    assert any(expected in line for line in lines)


def test_trace_at_info_hides_the_per_candidate_detail(auth):
    # Arrange
    from scitex_app.sdk.auth import LogLevel

    # Act
    result = auth.publickey("ywatanabe", "ssh-ed25519", OTHER)
    lines = result.trace.rendered(LogLevel.INFO)
    # Assert
    assert not any("no match against" in line for line in lines)


def test_trace_at_debug2_shows_the_per_candidate_detail(auth):
    # Arrange
    from scitex_app.sdk.auth import LogLevel

    # Act
    result = auth.publickey("ywatanabe", "ssh-ed25519", OTHER)
    lines = result.trace.rendered(LogLevel.DEBUG2)
    # Assert
    assert any("no match against" in line for line in lines)


def test_trace_never_contains_the_supplied_password(auth):
    # Arrange
    secret = "a-very-distinctive-secret-value"
    # Act
    result = auth.password("ywatanabe", secret)
    lines = result.trace.rendered(auth.config.log_level)
    # Assert
    assert not any(secret in line for line in lines)


def test_trace_never_contains_the_stored_hash(auth, project):
    # Arrange
    stored = (
        (project / ".scitex" / "cards" / "auth" / "users" / "ywatanabe" / "password")
        .read_text()
        .strip()
    )
    # Act
    result = auth.password("ywatanabe", "hunter2")
    lines = result.trace.rendered(auth.config.log_level)
    # Assert
    assert not any(stored in line for line in lines)


def test_undecodable_key_line_is_not_loaded_as_a_credential():
    # Arrange
    text = f"ssh-ed25519 {MINE} good@host\nssh-ed25519 !!!not-base64!!! corrupt@host\n"
    # Act
    keys = parse_authorized_keys(text)
    # Assert
    assert len(keys) == 1


def test_undecodable_key_cannot_authenticate_by_string_equality(project, auth):
    # Arrange
    users = project / ".scitex" / "cards" / "auth" / "users" / "ywatanabe"
    keys = users / "authorized_keys"
    keys.write_text("ssh-ed25519 !!!not-base64!!! corrupt@host\n")
    keys.chmod(0o600)
    # Act
    result = auth.publickey("ywatanabe", "ssh-ed25519", "!!!not-base64!!!")
    # Assert
    assert result.accepted is False


def test_option_prefixed_key_line_is_skipped_not_silently_stripped():
    # Arrange
    # A restriction we do not implement must never be dropped while the key it
    # guards stays live.
    text = f'command="/bin/false" ssh-ed25519 {MINE} restricted@host\n'
    # Act
    keys = parse_authorized_keys(text)
    # Assert
    assert keys == ()


def test_disabled_password_auth_reports_method_disabled(project):
    # Arrange
    auth_dir = project / ".scitex" / "cards" / "auth"
    (auth_dir / "cardsd_config").write_text(
        "PubkeyAuthentication yes\nPasswordAuthentication no\n"
    )
    authenticator = get_authenticator("cards", project_dir=project)
    # Act
    result = authenticator.password("ywatanabe", PASSWORD)
    # Assert
    assert result.outcome is Outcome.METHOD_DISABLED


def test_identities_lists_configured_users(auth):
    # Arrange
    # Act
    names = auth.identities()
    # Assert
    assert names == ("ywatanabe",)


def test_missing_auth_directory_raises_and_names_every_path_tried(tmp_path):
    # Arrange
    raised = None
    # Act
    try:
        get_authenticator("scholar", project_dir=tmp_path)
    except AuthNotConfigured as exc:
        raised = exc
    # Assert
    assert ".scitex/scholar/auth" in str(raised)


def test_project_directory_takes_precedence_over_home(auth, project):
    # Arrange
    expected = project / ".scitex" / "cards" / "auth"
    # Act
    resolved = auth.auth_dir
    # Assert
    assert resolved == expected


# EOF
