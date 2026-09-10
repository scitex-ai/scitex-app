#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""The shared leaf-app version-display contract.

Every leaf package shows its OWN installed version, continuously, and never a
hardcoded or hand-written manifest number. The version is read from
importlib.metadata (the single source of truth) with an explicit, labelled
development fallback. This is the contract a leaf app (or the host chrome)
consumes; the per-app adoption lives in the consumers' own repos.

WHAT IT PINS (the 2026-07 incident this exists to prevent): manifests were
pinned at 0.14.0 while the packages shipped 2.25.0 / 0.29.9 / 1.4.2, so every
app tile showed a WRONG version. ``ScitexAppConfig.app_version`` used to read
``manifest["version"]`` — the forbidden, drifting source. It must read the
installed dist instead.

No mocks (PA-306): the fallback is exercised against a package that genuinely
does not exist, and app_version is exercised against a real temp app module
with a real manifest.json.
"""

from __future__ import annotations

import json
import types
from pathlib import Path

import django
from django.conf import settings
from django.test import RequestFactory

if not settings.configured:
    # One real app so "is a ScitexAppConfig mounted" can be asked in both
    # directions. Identical in every scitex-app django test module: Django
    # configures settings once per process and the module order is not ours to
    # choose, so the blocks must agree or the fixture depends on luck.
    settings.configure(
        DEFAULT_CHARSET="utf-8",
        ALLOWED_HOSTS=["*"],
        DATABASES={},
        INSTALLED_APPS=["django.contrib.contenttypes"],
    )
    django.setup()

from scitex_app import context_processors  # noqa: E402
from scitex_app._django import (  # noqa: E402
    ScitexAppConfig,
    _LOCAL_VERSION_FALLBACK,
    package_version,
)

# The dist name scitex-app ships under (its own pyproject [project] name).
_SCITEX_APP_DIST = "scitex-app"


def test_package_version_reads_the_installed_dist():
    """For a package that IS installed, it returns importlib.metadata's answer
    — the actual installed version, not a constant."""
    # Arrange
    expected = package_version(_SCITEX_APP_DIST)
    # Act — importlib.metadata is the source of truth
    from importlib.metadata import version as _dist_version

    # Assert — they must agree, and it must be a plausible PEP 440 version,
    # never the dev fallback (scitex-app IS installed in the test env).
    assert expected == _dist_version(_SCITEX_APP_DIST)
    assert expected != _LOCAL_VERSION_FALLBACK
    assert expected.count(".") >= 1  # looks like a real version


def test_package_version_falls_back_labelled_for_a_missing_dist():
    """A package that is NOT installed degrades to the EXPLICIT, LABELLED local
    fallback — it does not raise and does not invent a release number."""
    # Arrange — a dist name that cannot plausibly be installed here.
    missing = "scitex-app-not-a-real-dist-zz"
    # Act
    got = package_version(missing)
    # Assert
    assert got == _LOCAL_VERSION_FALLBACK
    assert "local" in got  # the label, so it is never mistaken for a release


def test_package_version_defaults_to_scitex_app():
    """No argument -> scitex-app's own installed version (the SDK accessor)."""
    # Act
    got = package_version()
    # Assert
    assert got == package_version(_SCITEX_APP_DIST)


def _make_app_config(tmp_path: Path, pip_package: str, manifest_extra: dict) -> ScitexAppConfig:
    """Build a real ScitexAppConfig backed by a temp app module + manifest."""
    mod = types.ModuleType("myapp._django")
    mod.__file__ = str(tmp_path / "__init__.py")
    cfg = ScitexAppConfig("myapp._django", mod)
    manifest = {
        "name": "myapp",
        "slug": "myapp",
        "label": "My App",
        "pip_package": pip_package,
        "icon": "fas fa-puzzle-piece",
        "license": "MIT",
    }
    manifest.update(manifest_extra)
    (tmp_path / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    return cfg


def test_app_version_reads_pip_package_not_manifest_version(tmp_path):
    """THE core guarantee: app_version is the INSTALLED version of pip_package,
    and IGNORES a hand-written manifest 'version' (the forbidden, drifting
    source) even if one is present."""
    # Arrange — a manifest that (illegally) declares a version that DIFFERS from
    # the installed scitex-app. If app_version read the manifest, it would
    # return this stale number.
    stale = "0.14.0"
    cfg = _make_app_config(tmp_path, _SCITEX_APP_DIST, {"version": stale})
    # Act
    got = cfg.app_version
    # Assert — it is the installed version, not the manifest's stale one.
    assert got == package_version(_SCITEX_APP_DIST)
    assert got != stale


def test_app_version_falls_back_when_pip_package_is_missing(tmp_path):
    """A leaf whose pip_package is not installed gets the labelled fallback,
    never a crash and never a hardcoded number."""
    # Arrange
    cfg = _make_app_config(tmp_path, "no-such-leaf-dist-zz", {})
    # Act
    got = cfg.app_version
    # Assert
    assert got == _LOCAL_VERSION_FALLBACK


def test_context_processor_exposes_the_scitex_app_version():
    """The continuous surface: a request yields the SDK's installed version,
    so a page can render {{ scitex_app_version }} without the view passing it."""
    # Arrange
    request = RequestFactory().get("/")
    # Act
    ctx = context_processors.scitex_app_version(request)
    # Assert
    assert ctx["scitex_app_version"] == package_version(_SCITEX_APP_DIST)


def test_public_surface_exports_the_accessor():
    """Leaf apps import ONE surface, not a private module."""
    from scitex_app.embed import package_version as exported  # noqa: F401

    assert exported is not None
    assert exported(_SCITEX_APP_DIST) == package_version(_SCITEX_APP_DIST)
