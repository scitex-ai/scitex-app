#!/usr/bin/env python3
"""scitex_app.i18n: settings, catalog placement, compile, untranslated report, extraction."""

import shutil
from pathlib import Path

import pytest

from scitex_app.i18n import (
    LOCALE_MIDDLEWARE,
    app_locale_dir,
    check_app_locales,
    compile_catalogs,
    i18n_settings,
    make_messages,
    misplaced_locale_dirs,
    uncompiled_catalogs,
    untranslated_msgids,
    with_locale_middleware,
)

FIXTURE_LEAF = Path(__file__).parent / "i18n_fixture" / "leaf"
FIXTURE_APP = "tests.scitex_app.i18n_fixture.leaf._django"

JAPANESE_PO = """msgid ""
msgstr ""
"Language: ja\\n"
"Content-Type: text/plain; charset=UTF-8\\n"

msgid "Save"
msgstr "保存"

msgid "Undo"
msgstr ""

#, fuzzy
msgid "Export"
msgstr "エクスポート"
"""


def _write_catalog(root: Path, text: str = JAPANESE_PO) -> Path:
    po_path = root / "ja" / "LC_MESSAGES" / "djangojs.po"
    po_path.parent.mkdir(parents=True)
    po_path.write_text(text, encoding="utf-8")
    return po_path


def test_i18n_settings_default_to_english():
    # Arrange
    expected = "en"
    # Act
    settings = i18n_settings()
    # Assert
    assert settings["LANGUAGE_CODE"] == expected


def test_i18n_settings_offer_japanese():
    # Arrange
    expected = "ja"
    # Act
    settings = i18n_settings()
    # Assert
    assert expected in dict(settings["LANGUAGES"])


def test_with_locale_middleware_inserts_before_common_middleware():
    # Arrange
    middleware = [
        "django.contrib.sessions.middleware.SessionMiddleware",
        "django.middleware.common.CommonMiddleware",
    ]
    # Act
    stack = with_locale_middleware(middleware)
    # Assert
    assert stack.index(LOCALE_MIDDLEWARE) == 1


def test_with_locale_middleware_does_not_duplicate_the_entry():
    # Arrange
    middleware = [LOCALE_MIDDLEWARE, "django.middleware.common.CommonMiddleware"]
    # Act
    stack = with_locale_middleware(middleware)
    # Assert
    assert stack.count(LOCALE_MIDDLEWARE) == 1


def test_app_locale_dir_is_inside_the_django_app_package():
    # Arrange
    app_module = FIXTURE_APP
    # Act
    locale_dir = app_locale_dir(app_module)
    # Assert
    assert locale_dir == FIXTURE_LEAF / "_django" / "locale"


def test_misplaced_locale_dirs_finds_catalogs_in_the_parent_package():
    # Arrange
    app_module = FIXTURE_APP
    # Act
    misplaced = misplaced_locale_dirs(app_module)
    # Assert
    assert misplaced == [FIXTURE_LEAF / "locale"]


def test_check_app_locales_warns_about_misplaced_catalogs():
    # Arrange
    from scitex_app._django import ScitexAppConfig
    from tests.scitex_app.i18n_fixture.leaf import _django as leaf_module

    config = ScitexAppConfig(FIXTURE_APP, leaf_module)
    # Act
    messages = check_app_locales([config])
    # Assert
    assert [message.id for message in messages] == ["scitex_app.W001"]


def test_uncompiled_catalogs_lists_a_po_without_mo(tmp_path):
    # Arrange
    po_path = _write_catalog(tmp_path)
    # Act
    uncompiled = uncompiled_catalogs(tmp_path)
    # Assert
    assert uncompiled == [po_path]


def test_compile_catalogs_writes_the_mo_beside_the_po(tmp_path):
    # Arrange
    po_path = _write_catalog(tmp_path)
    # Act
    compile_catalogs(tmp_path)
    # Assert
    assert po_path.with_suffix(".mo").is_file()


def test_untranslated_msgids_reports_empty_and_fuzzy_entries(tmp_path):
    # Arrange
    po_path = _write_catalog(tmp_path)
    # Act
    missing = untranslated_msgids(po_path)
    # Assert
    assert missing == ["Undo", "Export"]


def test_untranslated_msgids_accepts_a_single_japanese_plural_form(tmp_path):
    # Arrange
    po_path = _write_catalog(
        tmp_path,
        '"Plural-Forms: nplurals=1; plural=0;\\n"\n\n'
        'msgid "%s figure"\nmsgid_plural "%s figures"\nmsgstr[0] "%s 個の図"\n',
    )
    # Act
    missing = untranslated_msgids(po_path)
    # Assert
    assert missing == []


@pytest.mark.skipif(shutil.which("xgettext") is None, reason="GNU gettext not installed")
def test_make_messages_extracts_tsx_strings_into_djangojs(tmp_path):
    # Arrange
    app_dir = tmp_path / "_django"
    shutil.copytree(FIXTURE_LEAF / "_django", app_dir)
    make_messages(app_dir, ["ja"])
    # Act
    catalog = (app_dir / "locale" / "ja" / "LC_MESSAGES" / "djangojs.po").read_text()
    # Assert
    assert 'msgid "Saving…"' in catalog


@pytest.mark.skipif(shutil.which("xgettext") is None, reason="GNU gettext not installed")
def test_make_messages_extracts_template_strings_into_django(tmp_path):
    # Arrange
    app_dir = tmp_path / "_django"
    shutil.copytree(FIXTURE_LEAF / "_django", app_dir)
    make_messages(app_dir, ["ja"])
    # Act
    catalog = (app_dir / "locale" / "ja" / "LC_MESSAGES" / "django.po").read_text()
    # Assert
    assert 'msgid "Gallery"' in catalog
