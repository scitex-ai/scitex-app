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

One assertion per test (STX-TQ007); AAA markers on their own lines (STX-TQ002).
No mocks (PA-306): the fallback is exercised against a package that genuinely
does not exist, and app_version against a real temp app module + manifest.
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
    # Arrange — importlib.metadata is the source of truth for the answer.
    from importlib.metadata import version as _dist_version

    expected = _dist_version(_SCITEX_APP_DIST)
    # Act
    got = package_version(_SCITEX_APP_DIST)
    # Assert — the accessor returns the actually-installed version.
    assert got == expected


def test_package_version_does_not_fake_a_release_when_installed():
    # Arrange — scitex-app IS installed in the test env, so its answer must
    # be a real PEP 440 version, never the dev fallback.
    fallback = _LOCAL_VERSION_FALLBACK
    # Act
    got = package_version(_SCITEX_APP_DIST)
    # Assert — it is not the "local" label.
    assert got != fallback


def test_package_version_falls_back_labelled_for_a_missing_dist():
    # Arrange — a dist name that cannot plausibly be installed here.
    missing = "scitex-app-not-a-real-dist-zz"
    # Act
    got = package_version(missing)
    # Assert — the EXPLICIT local label, not a crash and not a release number.
    assert got == _LOCAL_VERSION_FALLBACK


def test_package_version_fallback_is_labelled_local():
    # Arrange — the fallback must carry a "local" marker so it is never
    # mistaken for a shipped version.
    label = _LOCAL_VERSION_FALLBACK
    # Act
    contains = "local" in label
    # Assert
    assert contains is True


def test_package_version_defaults_to_scitex_app():
    # Arrange — no argument means "scitex-app itself".
    no_arg = package_version()
    named = package_version(_SCITEX_APP_DIST)
    # Act
    equal = no_arg == named
    # Assert
    assert equal is True


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
    # Arrange — a manifest that (illegally) declares a version DIFFERENT from
    # the installed scitex-app. If app_version read the manifest, it would
    # return this stale number.
    stale = "0.14.0"
    cfg = _make_app_config(tmp_path, _SCITEX_APP_DIST, {"version": stale})
    # Act
    got = cfg.app_version
    # Assert — it is the installed version, NOT the manifest's stale one.
    assert got != stale


def test_app_version_matches_the_installed_dist(tmp_path):
    # Arrange
    cfg = _make_app_config(tmp_path, _SCITEX_APP_DIST, {"version": "0.14.0"})
    # Act
    got = cfg.app_version
    # Assert — it agrees with the shared accessor for the same dist.
    assert got == package_version(_SCITEX_APP_DIST)


def test_app_version_falls_back_when_pip_package_is_missing(tmp_path):
    # Arrange — a leaf whose pip_package is not installed.
    cfg = _make_app_config(tmp_path, "no-such-leaf-dist-zz", {})
    # Act
    got = cfg.app_version
    # Assert — the labelled local fallback, never a crash or a number.
    assert got == _LOCAL_VERSION_FALLBACK


def test_context_processor_exposes_the_scitex_app_version():
    # Arrange
    request = RequestFactory().get("/")
    # Act
    ctx = context_processors.scitex_app_version(request)
    # Assert — the key is present (the value is then checked separately).
    assert "scitex_app_version" in ctx


def test_context_processor_value_is_the_installed_version():
    # Arrange
    request = RequestFactory().get("/")
    # Act
    ctx = context_processors.scitex_app_version(request)
    # Assert — it is the SDK's installed version, so a page renders it
    # without the view passing it (the "continuous" half of the contract).
    assert ctx["scitex_app_version"] == package_version(_SCITEX_APP_DIST)


def test_public_surface_exports_the_accessor():
    # Arrange — leaf apps import ONE surface, not a private module.
    from scitex_app.embed import package_version as exported

    # Act
    is_function = callable(exported)
    # Assert
    assert is_function is True
