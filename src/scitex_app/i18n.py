#!/usr/bin/env python3
"""Gettext i18n for SciTeX leaf apps: settings, catalog placement, extraction, compile.

Every leaf keeps its catalogs in ``<django app path>/locale`` so Django finds
them both standalone and mounted in the hub, with no LOCALE_PATHS entry::

    <app>/locale/ja/LC_MESSAGES/django.po     templates + Python
    <app>/locale/ja/LC_MESSAGES/djangojs.po   TS/JS (read by scitex-ui's gettext.ts)

Update and compile them with::

    scitex-app translations extract figrecipe._django -l ja
    scitex-app translations compile figrecipe._django

A standalone settings module takes its language setup from here::

    from scitex_app.i18n import i18n_settings, with_locale_middleware
    globals().update(i18n_settings())
    MIDDLEWARE = with_locale_middleware(MIDDLEWARE)
"""

from __future__ import annotations

import importlib.util
import os
from pathlib import Path
from typing import Iterable, Sequence, Union

__all__ = [
    "SUPPORTED_LANGUAGES",
    "LOCALE_MIDDLEWARE",
    "TEMPLATE_EXTENSIONS",
    "SCRIPT_EXTENSIONS",
    "IGNORED_SOURCE_PATTERNS",
    "i18n_settings",
    "with_locale_middleware",
    "app_locale_dir",
    "misplaced_locale_dirs",
    "uncompiled_catalogs",
    "untranslated_msgids",
    "compile_catalogs",
    "make_messages",
    "check_app_locales",
]

SUPPORTED_LANGUAGES = [("en", "English"), ("ja", "日本語")]

LOCALE_MIDDLEWARE = "django.middleware.locale.LocaleMiddleware"

TEMPLATE_EXTENSIONS = ("html", "txt", "py")

SCRIPT_EXTENSIONS = ("js", "ts", "tsx")

#: Built bundles under static/ would otherwise be extracted a second time, minified.
IGNORED_SOURCE_PATTERNS = ("node_modules", "static", "tests", "dist")


def i18n_settings() -> dict:
    """Django settings for English by default with Japanese available."""
    return {
        "USE_I18N": True,
        "LANGUAGE_CODE": "en",
        "LANGUAGES": list(SUPPORTED_LANGUAGES),
    }


def with_locale_middleware(middleware: Sequence[str]) -> list[str]:
    """Return ``middleware`` with LocaleMiddleware after sessions and before CommonMiddleware."""
    stack = [entry for entry in middleware if entry != LOCALE_MIDDLEWARE]
    session = "django.contrib.sessions.middleware.SessionMiddleware"
    common = "django.middleware.common.CommonMiddleware"
    if common in stack:
        position = stack.index(common)
    elif session in stack:
        position = stack.index(session) + 1
    else:
        position = len(stack)
    stack.insert(position, LOCALE_MIDDLEWARE)
    return stack


def app_locale_dir(app_module: str) -> Path:
    """``<django app path>/locale`` for an importable app package such as ``figrecipe._django``."""
    spec = importlib.util.find_spec(app_module)
    if spec is None or not spec.submodule_search_locations:
        raise ValueError(f"{app_module!r} is not an importable package")
    return Path(list(spec.submodule_search_locations)[0]) / "locale"


def misplaced_locale_dirs(app_module: str) -> list[Path]:
    """Locale dirs in the app's parent packages, which Django never reads for this app."""
    found = []
    package = app_module
    while "." in package:
        package = package.rsplit(".", 1)[0]
        candidate = app_locale_dir(package)
        if any(candidate.rglob("*.po")):
            found.append(candidate)
    return found


def uncompiled_catalogs(locale_dir: Path) -> list[Path]:
    """``.po`` files with no ``.mo`` beside them, so the running app shows English.

    Presence only: a git checkout does not preserve mtimes, so age would warn falsely.
    """
    return [
        po_path
        for po_path in sorted(Path(locale_dir).rglob("*.po"))
        if not po_path.with_suffix(".mo").exists()
    ]


def untranslated_msgids(po_path: Path) -> list[str]:
    """Msgids with an empty or fuzzy translation in one ``.po`` file."""
    from babel.messages.pofile import read_po

    po_path = Path(po_path)
    # The locale sets nplurals; without it a one-form Japanese plural reads as half-translated.
    with po_path.open(encoding="utf-8") as handle:
        catalog = read_po(handle, locale=po_path.parent.parent.name)
    missing = []
    for message in catalog:
        if not message.id:
            continue
        translations = message.string if isinstance(message.string, tuple) else (message.string,)
        if message.fuzzy or not all(translations):
            missing.append(message.id if isinstance(message.id, str) else message.id[0])
    return missing


def compile_catalogs(locale_dir: Path) -> list[Path]:
    """Compile every ``.po`` under ``locale_dir`` to ``.mo`` with babel.

    babel rather than ``compilemessages``: msgfmt is missing from the production image.
    """
    from babel.messages.mofile import write_mo
    from babel.messages.pofile import read_po

    written = []
    for po_path in sorted(Path(locale_dir).rglob("*.po")):
        with po_path.open(encoding="utf-8") as handle:
            catalog = read_po(handle, locale=po_path.parent.parent.name)
        mo_path = po_path.with_suffix(".mo")
        with mo_path.open("wb") as handle:
            write_mo(handle, catalog)
        written.append(mo_path)
    return written


def make_messages(app: Union[str, Path], locales: Iterable[str] = ("ja",)) -> Path:
    """Run ``makemessages`` for the ``django`` and ``djangojs`` domains inside the app package.

    ``app`` is an importable package name or the package directory itself.
    Needs GNU gettext's ``xgettext`` and ``msgmerge`` on PATH.
    """
    from django.core.management import call_command

    locale_dir = Path(app) / "locale" if isinstance(app, Path) else app_locale_dir(app)
    locale_dir.mkdir(exist_ok=True)
    domains = (("django", TEMPLATE_EXTENSIONS), ("djangojs", SCRIPT_EXTENSIONS))
    previous_cwd = os.getcwd()
    # makemessages walks the current directory and writes to ./locale.
    os.chdir(locale_dir.parent)
    try:
        for domain, extensions in domains:
            call_command(
                "makemessages",
                locale=list(locales),
                domain=domain,
                extensions=list(extensions),
                ignore_patterns=list(IGNORED_SOURCE_PATTERNS),
                no_obsolete=True,
                add_location="file",
                verbosity=0,
            )
    finally:
        os.chdir(previous_cwd)
    return locale_dir


def check_app_locales(app_configs=None, **kwargs) -> list:
    """Django system check: catalogs outside the app path, and uncompiled catalogs."""
    from django.apps import apps
    from django.core import checks

    from ._django import ScitexAppConfig

    configs = app_configs if app_configs is not None else apps.get_app_configs()
    messages = []
    for config in configs:
        if not isinstance(config, ScitexAppConfig):
            continue
        for misplaced in misplaced_locale_dirs(config.name):
            messages.append(
                checks.Warning(
                    f"{config.name}: catalogs at {misplaced} are never loaded for this app.",
                    hint=f"Move them to {app_locale_dir(config.name)}.",
                    obj=config.name,
                    id="scitex_app.W001",
                )
            )
        for po_path in uncompiled_catalogs(Path(config.path) / "locale"):
            messages.append(
                checks.Warning(
                    f"{po_path} has no compiled .mo, so this language renders English.",
                    hint=f"Run: scitex-app translations compile {config.name}",
                    obj=config.name,
                    id="scitex_app.W002",
                )
            )
    return messages


# EOF
