#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""The shared leaf-application version-display contract.

Every leaf package shows its OWN installed version, continuously, and never a
hardcoded or hand-written manifest number. The version is read from
``importlib.metadata`` (the single source of truth); an editable checkout, a
stripped env, or a missing dist degrades to an explicit, LABELLED local
fallback rather than a crash or a fabricated release number.

This module is the source of truth for the accessor. The two other surfaces
build on it:
  - ``scitex_app.context_processors``  (the CONTINUOUS display — register once
    in TEMPLATES, the version renders on every page);
  - ``ScitexAppConfig.app_version``     (the per-app accessor, in ``_django.py``).

WHY importlib.metadata and not the manifest: a hand-written manifest ``version``
is FORBIDDEN by the validator (validator.py) because it drifts — 2026-07
incident: manifests pinned at 0.14.0 while the packages shipped 2.25.0 /
0.29.9 / 1.4.2, so every app tile showed a wrong version. Reading the installed
dist is the only source that is always true.
"""

from __future__ import annotations

from typing import Optional

#: Fallback version label when the installed dist cannot be read — an editable
#: checkout, a stripped env, or a `pip_package` that is not installed. Labelled
#: (not silent) so it is never mistaken for a real release number.
_LOCAL_VERSION_FALLBACK = "0.0.0+local"


def package_version(package: Optional[str] = None) -> str:
    """Read a package's installed version via importlib.metadata.

    The shared accessor: a leaf app calls it with its own dist name (its
    manifest's ``pip_package``) to display what is ACTUALLY installed. No
    argument means scitex-app's own version, so the SDK has a working accessor
    too.

    The fallback is EXPLICIT and labelled: any read failure (no package,
    PackageNotFoundError, a stripped env) returns ``"0.0.0+local"`` — never a
    raise, never a hardcoded release number. A development install degrades to
    an honest "local" label, not a lie about which version is running.
    """
    dist_name = package or "scitex-app"
    try:
        from importlib.metadata import version

        return version(dist_name)
    except Exception:
        return _LOCAL_VERSION_FALLBACK
