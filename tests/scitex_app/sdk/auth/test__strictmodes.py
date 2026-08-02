#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Test file for: scitex_app/sdk/auth/_strictmodes.py

"""Tests for the permission refusals.

The load-bearing case here is the ASYMMETRY: a secret must not be group/other
READABLE, a public file only must not be group/other WRITABLE. Those are two
different rules and ssh has them for a reason. If someone later "simplifies"
this to one rule, the 0644-authorized_keys test below is what stops them —
0644 is the mode ssh itself permits, and a package that refuses it is a package
that rejects working configurations copied from ssh documentation.

Real chmod on real files in tmp_path throughout. Mocking the permission bits
would test that the code reads a mock, which is not the property in question.
"""

from __future__ import annotations

import pytest

from scitex_app.sdk.auth import StrictModesError
from scitex_app.sdk.auth._strictmodes import (
    check_directory,
    check_public_file,
    check_secret_file,
)


@pytest.fixture
def secret(tmp_path):
    path = tmp_path / "password"
    path.write_text("$scrypt$n=16384,r=8,p=1$c2FsdA==$aGFzaA==")
    path.chmod(0o600)
    return path


@pytest.fixture
def public(tmp_path):
    path = tmp_path / "authorized_keys"
    path.write_text("ssh-ed25519 AAAA comment\n")
    path.chmod(0o600)
    return path


def test_secret_at_0600_is_accepted(secret):
    # Arrange
    secret.chmod(0o600)
    raised = None
    # Act
    try:
        check_secret_file(secret)
    except StrictModesError as exc:
        raised = exc
    # Assert
    assert raised is None


def test_secret_readable_by_group_is_refused(secret):
    # Arrange
    secret.chmod(0o640)
    raised = None
    # Act
    try:
        check_secret_file(secret)
    except StrictModesError as exc:
        raised = exc
    # Assert
    assert raised is not None


def test_secret_readable_by_other_is_refused(secret):
    # Arrange
    secret.chmod(0o604)
    raised = None
    # Act
    try:
        check_secret_file(secret)
    except StrictModesError as exc:
        raised = exc
    # Assert
    assert raised is not None


def test_secret_refusal_reports_the_offending_mode(secret):
    # Arrange
    secret.chmod(0o644)
    raised = None
    # Act
    try:
        check_secret_file(secret)
    except StrictModesError as exc:
        raised = exc
    # Assert
    assert raised.mode == 0o644


def test_secret_refusal_names_a_chmod_that_fixes_it(secret):
    # Arrange
    secret.chmod(0o644)
    raised = None
    # Act
    try:
        check_secret_file(secret)
    except StrictModesError as exc:
        raised = exc
    # Assert
    assert "chmod 600" in raised.remedy


def test_public_file_at_0644_is_accepted_exactly_as_ssh_does(public):
    # Arrange
    # 0644 is the mode ssh itself permits for authorized_keys. Refusing it would
    # reject configurations copied straight from ssh documentation.
    public.chmod(0o644)
    raised = None
    # Act
    try:
        check_public_file(public)
    except StrictModesError as exc:
        raised = exc
    # Assert
    assert raised is None


def test_public_file_writable_by_group_is_refused(public):
    # Arrange
    public.chmod(0o660)
    raised = None
    # Act
    try:
        check_public_file(public)
    except StrictModesError as exc:
        raised = exc
    # Assert
    assert raised is not None


def test_public_file_writable_by_other_is_refused(public):
    # Arrange
    public.chmod(0o606)
    raised = None
    # Act
    try:
        check_public_file(public)
    except StrictModesError as exc:
        raised = exc
    # Assert
    assert raised is not None


def test_directory_at_0700_is_accepted(tmp_path):
    # Arrange
    directory = tmp_path / "auth"
    directory.mkdir()
    directory.chmod(0o700)
    raised = None
    # Act
    try:
        check_directory(directory)
    except StrictModesError as exc:
        raised = exc
    # Assert
    assert raised is None


def test_directory_writable_by_others_is_refused(tmp_path):
    # Arrange
    # A writable directory defeats every check on the files inside it.
    directory = tmp_path / "auth"
    directory.mkdir()
    directory.chmod(0o777)
    raised = None
    # Act
    try:
        check_directory(directory)
    except StrictModesError as exc:
        raised = exc
    # Assert
    assert raised is not None


def test_strict_modes_error_is_a_permission_error(secret):
    # Arrange
    secret.chmod(0o644)
    raised = None
    # Act
    try:
        check_secret_file(secret)
    except PermissionError as exc:
        raised = exc
    # Assert
    assert raised is not None


# EOF
