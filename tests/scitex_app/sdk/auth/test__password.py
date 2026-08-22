#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Test file for: scitex_app/sdk/auth/_password.py

"""Tests for password hashing and verification.

The tests that matter most here are the ones asserting a bad stored hash
RAISES rather than returning False. A caller that cannot tell "wrong password"
from "corrupt credential file" debugs the wrong one, and a silent False looks
exactly like a working rejection — so the file stays broken and nobody learns.
"""

from __future__ import annotations

import pytest

from scitex_app.sdk.auth import HashFormatError, hash_password, verify_password

PASSWORD = "correct horse battery staple"


def test_a_fresh_hash_verifies():
    # Arrange
    stored = hash_password(PASSWORD)
    # Act
    ok = verify_password(stored, PASSWORD)
    # Assert
    assert ok is True


def test_a_wrong_password_does_not_verify():
    # Arrange
    stored = hash_password(PASSWORD)
    # Act
    ok = verify_password(stored, "hunter2")
    # Assert
    assert ok is False


def test_the_same_password_hashes_differently_each_time():
    # Arrange
    # A fresh random salt per hash, so two users with the same password do not
    # share a stored value.
    first = hash_password(PASSWORD)
    # Act
    second = hash_password(PASSWORD)
    # Assert
    assert first != second


def test_the_hash_declares_its_algorithm():
    # Arrange
    # Act
    stored = hash_password(PASSWORD)
    # Assert
    assert stored.startswith("$scrypt$")


def test_the_hash_records_its_parameters():
    # Arrange
    # Recorded IN the string so raising the cost later does not invalidate
    # hashes already stored.
    # Act
    stored = hash_password(PASSWORD)
    # Assert
    assert "n=16384" in stored


def test_a_bare_digest_is_rejected_rather_than_failing_quietly():
    # Arrange
    raised = None
    # Act
    try:
        verify_password("5e884898da28047151d0e56f8dc62927", PASSWORD)
    except HashFormatError as exc:
        raised = exc
    # Assert
    assert raised is not None


def test_an_unknown_algorithm_is_rejected():
    # Arrange
    raised = None
    # Act
    try:
        verify_password("$madeup$x=1$c2FsdA==$aGFzaA==", PASSWORD)
    except HashFormatError as exc:
        raised = exc
    # Assert
    assert raised is not None


def test_unreadable_parameters_are_rejected():
    # Arrange
    raised = None
    # Act
    try:
        verify_password("$scrypt$n=abc,r=8,p=1$c2FsdA==$aGFzaA==", PASSWORD)
    except HashFormatError as exc:
        raised = exc
    # Assert
    assert raised is not None


def test_invalid_base64_in_the_hash_is_rejected():
    # Arrange
    raised = None
    # Act
    try:
        verify_password("$scrypt$n=16384,r=8,p=1$!!!$aGFzaA==", PASSWORD)
    except HashFormatError as exc:
        raised = exc
    # Assert
    assert raised is not None


def test_an_unknown_algorithm_error_names_what_is_supported():
    # Arrange
    raised = None
    # Act
    try:
        verify_password("$madeup$x=1$c2FsdA==$aGFzaA==", PASSWORD)
    except HashFormatError as exc:
        raised = exc
    # Assert
    assert "scrypt" in str(raised)


def test_surrounding_whitespace_in_a_stored_hash_is_tolerated():
    # Arrange
    # The hash is read from a file, and files end with a newline.
    stored = f"  {hash_password(PASSWORD)}\n"
    # Act
    ok = verify_password(stored, PASSWORD)
    # Assert
    assert ok is True


# EOF
