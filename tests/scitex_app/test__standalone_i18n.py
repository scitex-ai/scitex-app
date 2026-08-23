#!/usr/bin/env python3
"""Standalone i18n: activation, and saying so when a catalog is missing.

Measured 2026-08-23: catalog DISCOVERY was already free (Django auto-discovers
`<app>/locale/`), but nothing ever called activate(), so a standalone app shipped
a working Japanese catalog and rendered English forever. scitex-hub found the
mirror image in their stack — activation wired, catalog empty. Both fall back
silently to the source string.

No fixtures reach into process state: every helper takes its inputs as
arguments, so the tests need no environment patching (PA-306 forbids mocks).

One assertion each.
"""

from scitex_app._standalone import (
    _declared_languages,
    _language_settings,
    _languages_missing_catalogs,
)


def test_declared_languages_parses_a_comma_list():
    # Arrange — the SCITEX_LANGUAGES shape a deployer writes.
    spec = "en,ja"
    # Act
    langs = _declared_languages(spec)
    # Assert
    assert langs == [("en", "en"), ("ja", "ja")]


def test_declared_languages_tolerates_spaces():
    # Arrange — a human-written list has spaces, and a code of " ja" would
    # never match a browser's Accept-Language.
    spec = "en, ja"
    # Act
    langs = _declared_languages(spec)
    # Assert
    assert ("ja", "ja") in langs


def test_unset_languages_yields_no_setting_at_all():
    # Arrange — the distinction that matters: passing LANGUAGES=[] would assert
    # "this app supports NO languages", the opposite of "the app did not say".
    # Omitting the key leaves Django's own default intact.
    spec = ""
    # Act
    settings = _language_settings(spec)
    # Assert
    assert settings == {}


def test_declared_languages_produce_a_languages_setting():
    # Arrange — the other arm: when the app does say, the setting appears.
    spec = "ja"
    # Act
    settings = _language_settings(spec)
    # Assert
    assert settings["LANGUAGES"] == [("ja", "ja")]


def test_a_language_with_no_compiled_catalog_is_reported():
    # Arrange — the anti-silent-fallback check. scitex_app itself ships no
    # locale/, so any language is uncompiled there. This is the exact shape
    # scitex-hub hit: declared in LANGUAGES, no .mo anywhere, renders English.
    codes = ["ja"]
    # Act
    missing = _languages_missing_catalogs(codes, ["scitex_app"])
    # Assert
    assert missing == ["ja"]


def test_an_unimportable_module_is_skipped_rather_than_raising():
    # Arrange — a host may list an app that is not installed in this
    # environment. Discovery must degrade, not crash the server at startup.
    codes = ["ja"]
    # Act
    missing = _languages_missing_catalogs(codes, ["no_such_module_at_all"])
    # Assert
    assert missing == ["ja"]


def test_no_languages_declared_means_nothing_to_report():
    # Arrange — the arm that stops the check becoming noise for every app that
    # never asked for translation.
    codes = []
    # Act
    missing = _languages_missing_catalogs(codes, ["scitex_app"])
    # Assert
    assert missing == []
