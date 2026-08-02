#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Test file for: scitex_app/sdk/auth/_config.py

"""Tests for the sshd_config-shaped parser.

These pin BEHAVIOUR, not wording. Every assertion here is about something a
config author could observe and depend on -- that a typo is fatal, that the
first occurrence wins, that unset is distinguishable from no. None of them
assert the exact text of a message, because message wording is meant to improve
and a test that freezes it turns every improvement into a failing test.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from scitex_app.sdk.auth import (
    AuthConfig,
    ConfigError,
    LogLevel,
    Tristate,
    parse_config,
)


@pytest.fixture
def config_file(tmp_path):
    """A writable path for one config, and its containing directory."""
    return tmp_path / "cardsd_config"


def test_missing_file_is_not_an_error(tmp_path):
    # Arrange
    absent = tmp_path / "does-not-exist"
    # Act
    config = parse_config(absent)
    # Assert
    assert config.pubkey_authentication is Tristate.UNSET


def test_missing_file_still_permits_pubkey_by_default(tmp_path):
    # Arrange
    absent = tmp_path / "does-not-exist"
    # Act
    config = parse_config(absent)
    # Assert
    assert config.pubkey_enabled is True


def test_unset_is_distinguishable_from_explicit_no(config_file):
    # Arrange
    config_file.write_text("PasswordAuthentication no\n")
    # Act
    config = parse_config(config_file)
    # Assert
    assert config.pubkey_authentication is Tristate.UNSET


def test_explicit_no_is_recorded_as_no(config_file):
    # Arrange
    config_file.write_text("PasswordAuthentication no\n")
    # Act
    config = parse_config(config_file)
    # Assert
    assert config.password_authentication is Tristate.NO


def test_unknown_keyword_is_fatal(config_file):
    # Arrange
    config_file.write_text("PasswordAuthetication no\n")
    raised = None
    # Act
    try:
        parse_config(config_file)
    except ConfigError as exc:
        raised = exc
    # Assert
    assert raised is not None


def test_unknown_keyword_error_names_the_line(config_file):
    # Arrange
    config_file.write_text("# a comment\n\nPasswordAuthetication no\n")
    raised = None
    # Act
    try:
        parse_config(config_file)
    except ConfigError as exc:
        raised = exc
    # Assert
    assert raised.lineno == 3


def test_unknown_keyword_error_suggests_the_real_spelling(config_file):
    # Arrange
    config_file.write_text("PasswordAuthetication no\n")
    raised = None
    # Act
    try:
        parse_config(config_file)
    except ConfigError as exc:
        raised = exc
    # Assert
    assert "PasswordAuthentication" in raised.remedy


def test_non_yes_no_value_is_rejected(config_file):
    # Arrange
    config_file.write_text("PubkeyAuthentication maybe\n")
    raised = None
    # Act
    try:
        parse_config(config_file)
    except ConfigError as exc:
        raised = exc
    # Assert
    assert raised is not None


def test_keyword_with_no_value_is_rejected(config_file):
    # Arrange
    config_file.write_text("PubkeyAuthentication\n")
    raised = None
    # Act
    try:
        parse_config(config_file)
    except ConfigError as exc:
        raised = exc
    # Assert
    assert raised is not None


def test_first_occurrence_wins_as_sshd_does(config_file):
    # Arrange
    config_file.write_text("PasswordAuthentication no\nPasswordAuthentication yes\n")
    # Act
    config = parse_config(config_file)
    # Assert
    assert config.password_authentication is Tristate.NO


def test_both_methods_disabled_is_rejected_at_load(config_file):
    # Arrange
    config_file.write_text("PubkeyAuthentication no\nPasswordAuthentication no\n")
    raised = None
    # Act
    try:
        parse_config(config_file)
    except ConfigError as exc:
        raised = exc
    # Assert
    assert raised is not None


def test_absolute_authorized_keys_file_is_rejected(config_file):
    # Arrange
    config_file.write_text("AuthorizedKeysFile /etc/passwd\n")
    raised = None
    # Act
    try:
        parse_config(config_file)
    except ConfigError as exc:
        raised = exc
    # Assert
    assert raised is not None


def test_keywords_are_case_insensitive(config_file):
    # Arrange
    config_file.write_text("pubkeyauthentication YES\n")
    # Act
    config = parse_config(config_file)
    # Assert
    assert config.pubkey_authentication is Tristate.YES


def test_comments_and_blank_lines_are_ignored(config_file):
    # Arrange
    config_file.write_text("\n# comment\n\n   # indented comment\nStrictModes no\n")
    # Act
    config = parse_config(config_file)
    # Assert
    assert config.strict_modes is Tristate.NO


def test_debug1_corresponds_to_dash_v(config_file):
    # Arrange
    config_file.write_text("LogLevel DEBUG1\n")
    # Act
    config = parse_config(config_file)
    # Assert
    assert config.log_level is LogLevel.from_verbosity(1)


def test_debug3_corresponds_to_dash_vvv(config_file):
    # Arrange
    config_file.write_text("LogLevel DEBUG3\n")
    # Act
    config = parse_config(config_file)
    # Assert
    assert config.log_level is LogLevel.from_verbosity(3)


def test_more_than_three_v_saturates_at_debug3():
    # Arrange
    # Act
    level = LogLevel.from_verbosity(9)
    # Assert
    assert level is LogLevel.DEBUG3


def test_bare_debug_is_a_synonym_for_debug1(config_file):
    # Arrange
    config_file.write_text("LogLevel DEBUG\n")
    # Act
    config = parse_config(config_file)
    # Assert
    assert config.log_level is LogLevel.DEBUG1


def test_strict_modes_defaults_to_enabled():
    # Arrange
    config = AuthConfig()
    # Act
    enabled = config.strict_modes_enabled
    # Assert
    assert enabled is True


def test_unset_tristate_is_not_enabled():
    # Arrange
    value = Tristate.UNSET
    # Act
    enabled = value.enabled
    # Assert
    assert enabled is False


def test_seen_records_keyword_order(config_file):
    # Arrange
    config_file.write_text("StrictModes yes\nLogLevel DEBUG2\n")
    # Act
    config = parse_config(config_file)
    # Assert
    assert config.seen == ("StrictModes", "LogLevel")


# EOF
