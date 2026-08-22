#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Test file for: scitex_app/sdk/auth/_users.py

"""Tests for identity loading and authorized_keys parsing.

Keys are built as GENUINE ssh-ed25519 blobs rather than hand-typed strings.
That is not fussiness: the first end-to-end run used a hand-typed fixture whose
base64 did not decode, it authenticated successfully, and it logged a
fingerprint reading "<unparseable>". A fixture that fakes the shape fakes the
bug along with it — the defect it hid is covered below.
"""

from __future__ import annotations

import base64
import struct

import pytest

from scitex_app.sdk.auth import (
    AuthConfig,
    Tristate,
    hash_password,
    list_identities,
    load_identity,
    parse_authorized_keys,
)


def _ed25519_material(filler: bytes) -> str:
    """A real ssh-ed25519 blob: len+name, then len+32 bytes of key."""
    name = b"ssh-ed25519"
    blob = (
        struct.pack(">I", len(name)) + name + struct.pack(">I", 32) + (filler * 32)[:32]
    )
    return base64.b64encode(blob).decode("ascii")


MINE = _ed25519_material(b"\x01")


@pytest.fixture
def strict_config():
    return AuthConfig(strict_modes=Tristate.YES)


@pytest.fixture
def auth_dir(tmp_path):
    """An auth directory with one fully configured user."""
    users = tmp_path / "users" / "ywatanabe"
    users.mkdir(parents=True)
    for directory in (tmp_path, tmp_path / "users", users):
        directory.chmod(0o700)
    keys = users / "authorized_keys"
    keys.write_text(f"ssh-ed25519 {MINE} ywatanabe@note-win\n")
    keys.chmod(0o600)
    password = users / "password"
    password.write_text(hash_password("secret"))
    password.chmod(0o600)
    return tmp_path


def test_a_well_formed_key_line_is_parsed():
    # Arrange
    text = f"ssh-ed25519 {MINE} ywatanabe@note-win\n"
    # Act
    keys = parse_authorized_keys(text)
    # Assert
    assert len(keys) == 1


def test_the_comment_is_kept_so_a_human_can_tell_keys_apart():
    # Arrange
    text = f"ssh-ed25519 {MINE} ywatanabe@note-win\n"
    # Act
    keys = parse_authorized_keys(text)
    # Assert
    assert keys[0].comment == "ywatanabe@note-win"


def test_comments_and_blank_lines_are_skipped():
    # Arrange
    text = f"# my laptop\n\nssh-ed25519 {MINE} host\n"
    # Act
    keys = parse_authorized_keys(text)
    # Assert
    assert len(keys) == 1


def test_an_undecodable_key_is_not_loaded():
    # Arrange
    # Matching is string equality, so an undecodable line would still MATCH and
    # keep granting access while its fingerprint named nothing.
    text = "ssh-ed25519 !!!not-base64!!! corrupt@host\n"
    # Act
    keys = parse_authorized_keys(text)
    # Assert
    assert keys == ()


def test_a_truncated_key_is_not_loaded():
    # Arrange
    # Decodes as base64 but is too short to be an SSH blob header.
    text = "ssh-ed25519 QQ== short@host\n"
    # Act
    keys = parse_authorized_keys(text)
    # Assert
    assert keys == ()


def test_one_bad_line_does_not_discard_the_good_ones():
    # Arrange
    # Refusing the whole file would let one typo revoke every other user's
    # working key — a typo becoming an outage.
    text = f"ssh-ed25519 !!!bad!!! x\nssh-ed25519 {MINE} good@host\n"
    # Act
    keys = parse_authorized_keys(text)
    # Assert
    assert len(keys) == 1


def test_an_option_prefixed_line_is_skipped_not_stripped():
    # Arrange
    # A restriction we do not implement must never be dropped while the key it
    # guards stays live.
    text = f'command="/bin/false" ssh-ed25519 {MINE} restricted@host\n'
    # Act
    keys = parse_authorized_keys(text)
    # Assert
    assert keys == ()


def test_a_line_of_the_wrong_algorithm_family_is_skipped():
    # Arrange
    text = f"not-a-key-type {MINE} x\n"
    # Act
    keys = parse_authorized_keys(text)
    # Assert
    assert keys == ()


def test_a_configured_user_loads(auth_dir, strict_config):
    # Arrange
    # Act
    identity = load_identity(auth_dir, "ywatanabe", strict_config)
    # Assert
    assert identity is not None


def test_a_loaded_identity_takes_its_name_from_the_directory(auth_dir, strict_config):
    # Arrange
    # Act
    identity = load_identity(auth_dir, "ywatanabe", strict_config)
    # Assert
    assert identity.name == "ywatanabe"


def test_an_unknown_user_loads_as_none_rather_than_raising(auth_dir, strict_config):
    # Arrange
    # Raising would let a caller distinguish "no such user" from "wrong
    # password" by exception type — a user-enumeration oracle for free.
    # Act
    identity = load_identity(auth_dir, "mallory", strict_config)
    # Assert
    assert identity is None


def test_a_user_with_no_password_file_reports_no_password(auth_dir, strict_config):
    # Arrange
    (auth_dir / "users" / "ywatanabe" / "password").unlink()
    # Act
    identity = load_identity(auth_dir, "ywatanabe", strict_config)
    # Assert
    assert identity.has_password is False


def test_a_user_with_no_keys_file_reports_no_key(auth_dir, strict_config):
    # Arrange
    (auth_dir / "users" / "ywatanabe" / "authorized_keys").unlink()
    # Act
    identity = load_identity(auth_dir, "ywatanabe", strict_config)
    # Assert
    assert identity.has_key is False


def test_identities_are_listed_without_reading_credentials(auth_dir):
    # Arrange
    (auth_dir / "users" / "alice").mkdir()
    # Act
    names = list_identities(auth_dir)
    # Assert
    assert names == ("alice", "ywatanabe")


def test_listing_an_auth_dir_with_no_users_returns_empty(tmp_path):
    # Arrange
    # Act
    names = list_identities(tmp_path)
    # Assert
    assert names == ()


# EOF
