#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tests for scitex_app/_chat/_backends.py — default-model env resolution.

Covers the LLM_MODEL -> SCITEX_APP_LLM_MODEL migration: the unprefixed name is
a published contract, so it is aliased rather than renamed, and the pick must
never be silent when both are set.

These set the REAL process environment through a yield fixture that restores
it on teardown -- `_resolve_default_model` reads `os.environ` itself, so
substituting reality is both possible and cheap here.
"""

from __future__ import annotations

import logging
import os

import pytest

from scitex_app._chat._backends import _DEFAULT_LLM_MODEL, _resolve_default_model

_VARS = ("SCITEX_APP_LLM_MODEL", "LLM_MODEL")


@pytest.fixture
def env():
    """Set/clear the real env vars, restoring prior values on teardown."""
    saved = {name: os.environ.get(name) for name in _VARS}

    def apply(**values):
        for name in _VARS:
            os.environ.pop(name, None)
        for name, value in values.items():
            os.environ[name] = value

    yield apply
    for name, value in saved.items():
        if value is None:
            os.environ.pop(name, None)
        else:
            os.environ[name] = value


def test_returns_builtin_default_when_neither_var_is_set(env):
    # Arrange
    env()
    # Act
    resolved = _resolve_default_model()
    # Assert
    assert resolved == _DEFAULT_LLM_MODEL


def test_prefixed_var_is_used_when_set(env):
    # Arrange
    env(SCITEX_APP_LLM_MODEL="anthropic/prefixed-model")
    # Act
    resolved = _resolve_default_model()
    # Assert
    assert resolved == "anthropic/prefixed-model"


def test_legacy_var_still_works(env):
    # Arrange
    env(LLM_MODEL="anthropic/legacy-model")
    # Act
    resolved = _resolve_default_model()
    # Assert
    assert resolved == "anthropic/legacy-model"


def test_legacy_var_warns_naming_its_replacement(env, caplog):
    # Arrange
    env(LLM_MODEL="anthropic/legacy-model")
    # Act
    with caplog.at_level(logging.WARNING):
        _resolve_default_model()
    # Assert
    assert "SCITEX_APP_LLM_MODEL" in caplog.text


def test_prefixed_wins_when_both_are_set(env):
    # Arrange
    env(
        SCITEX_APP_LLM_MODEL="anthropic/prefixed-model",
        LLM_MODEL="anthropic/legacy-model",
    )
    # Act
    resolved = _resolve_default_model()
    # Assert
    assert resolved == "anthropic/prefixed-model"


def test_conflict_between_both_vars_is_logged_not_silent(env, caplog):
    # Arrange
    env(
        SCITEX_APP_LLM_MODEL="anthropic/prefixed-model",
        LLM_MODEL="anthropic/legacy-model",
    )
    # Act
    with caplog.at_level(logging.WARNING):
        _resolve_default_model()
    # Assert
    assert "anthropic/legacy-model" in caplog.text


def test_agreeing_duplicate_values_do_not_warn_about_a_conflict(env, caplog):
    # Arrange
    env(
        SCITEX_APP_LLM_MODEL="anthropic/same-model",
        LLM_MODEL="anthropic/same-model",
    )
    # Act
    with caplog.at_level(logging.WARNING):
        _resolve_default_model()
    # Assert
    assert "disagree" not in caplog.text
