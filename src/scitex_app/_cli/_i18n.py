"""``scitex-app translations`` — extract, compile and validate a leaf app's gettext catalogs."""

from __future__ import annotations

import click


@click.group("translations")
def translations():
    """Extract, compile and validate an app's translations (<app>/locale)."""


@translations.command("extract")
@click.argument("app_module")
@click.option("-l", "--locale", "locales", multiple=True, default=("ja",), show_default=True)
@click.option("--dry-run", is_flag=True, help="Show where the catalogs would be written.")
@click.option("-y", "--yes", is_flag=True, help="Assume yes; extraction rewrites existing .po files.")
def extract(app_module, locales, dry_run, yes):
    """Run makemessages for django.po (templates, Python) and djangojs.po (JS, TS, TSX).

    \b
    Example:
        scitex-app translations extract figrecipe._django -l ja
    """
    from scitex_app.i18n import app_locale_dir, make_messages

    if dry_run:
        click.echo(f"Would update {', '.join(locales)} catalogs in {app_locale_dir(app_module)}")
        return
    locale_dir = make_messages(app_module, locales)
    click.echo(f"Updated catalogs in {locale_dir}")


@translations.command("compile")
@click.argument("app_module")
@click.option("--dry-run", is_flag=True, help="List the catalogs without writing .mo files.")
@click.option("-y", "--yes", is_flag=True, help="Assume yes; compiling overwrites existing .mo files.")
def compile_(app_module, dry_run, yes):
    """Compile every .po of the app to .mo (babel; no msgfmt needed).

    \b
    Example:
        scitex-app translations compile figrecipe._django
    """
    from scitex_app.i18n import app_locale_dir, compile_catalogs

    locale_dir = app_locale_dir(app_module)
    if dry_run:
        for po_path in sorted(locale_dir.rglob("*.po")):
            click.echo(f"Would compile {po_path}")
        return
    for mo_path in compile_catalogs(locale_dir):
        click.echo(f"Compiled {mo_path}")


@translations.command("validate")
@click.argument("app_module")
def validate(app_module):
    """Exit 1 when a catalog is untranslated, uncompiled or outside the app path.

    \b
    Example:
        scitex-app translations validate figrecipe._django
    """
    from scitex_app.i18n import (
        app_locale_dir,
        misplaced_locale_dirs,
        uncompiled_catalogs,
        untranslated_msgids,
    )

    locale_dir = app_locale_dir(app_module)
    problems = [f"misplaced catalogs: {path}" for path in misplaced_locale_dirs(app_module)]
    problems += [f"not compiled: {path}" for path in uncompiled_catalogs(locale_dir)]
    for po_path in sorted(locale_dir.rglob("*.po")):
        problems += [f"untranslated in {po_path.name}: {msgid}" for msgid in untranslated_msgids(po_path)]
    for problem in problems:
        click.echo(problem)
    if problems:
        raise SystemExit(1)
    click.echo(f"{app_module}: catalogs complete")
