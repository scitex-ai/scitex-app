"""Shared leaf-app version-display context processors.

Every SciTeX leaf app shows its OWN installed version, continuously (on every
page, not once in a footer) and never hardcoded. The version is read from
importlib.metadata via the shared ``package_version()`` in ``scitex_app._django``
(the single source of truth — see the 2026-07 incident where hand-written
manifest versions drifted from the shipped packages).

A host app registers the processor it needs in TEMPLATES OPTIONS
``context_processors``:

    "context_processors": [
        "scitex_app.context_processors.scitex_app_version",   # the SDK itself
        "scitex_app.context_processors.app_version",          # a mounted leaf app
    ]

``scitex_app_version`` adds ``scitex_app_version`` (the scitex-app SDK's own
installed version). ``app_version`` reads the mounted app's ``ScitexAppConfig``
and adds ``app_version`` (the leaf's OWN package version, from its
``pip_package``). Both degrade to the labelled ``"0.0.0+local"`` fallback for
editable checkouts / a missing dist — they never raise and never emit a
hardcoded release number.
"""

from __future__ import annotations


def scitex_app_version(request) -> dict:
    """Add the scitex-app SDK's own installed version to every template.

    Continuous: registered once in TEMPLATES context_processors, it runs on
    every request, so a page can always render ``{{ scitex_app_version }}``
    without the view having to pass it.
    """
    from ._django import package_version

    return {"scitex_app_version": package_version()}


def app_version(request) -> dict:
    """Add the MOUNTED leaf app's own installed version to the template.

    Resolves the mounted app's ``ScitexAppConfig`` (the one that carries a
    ``pip_package``) and reports ``{{ app_version }}`` as that package's
    installed version. If no scitex_app-managed app is mounted, the key is
    absent rather than a wrong value.
    """
    try:
        from django.apps import apps

        from ._django import ScitexAppConfig
    except ImportError:
        return {}

    result: dict = {}
    for app_config in apps.get_app_configs():
        if isinstance(app_config, ScitexAppConfig):
            result["app_version"] = app_config.app_version
            result["app_label"] = app_config.label
            break
    return result
