#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""The declarative leaf-app scope contract (operator ledger #48, #144-149).

A leaf app declares, in its manifest, whether it is USER-scoped (default) or
PROJECT-scoped. That single declaration drives one rule: the global Hub header
MUST NEVER force a Current-Project selector.

  - user-scoped    -> emits NO scope marker; renders with no project switcher.
  - project-scoped -> emits a per-app marker the workspace surface reads.

This is the SDK-side contract for the operator's 2026-09-10 ruling. The
selector UI lives in scitex-ui / the host surface — this module only DECLARES
the scope and emits the marker. It does not fork any UI primitive.

One assertion per test (STX-TQ007); AAA markers on their own lines (STX-TQ002).
No mocks (PA-306). The test mirrors src/scitex_app/_app_scope.py 1:1 (PS-204).
"""

from __future__ import annotations

import json
import types
from pathlib import Path

import django
from django.conf import settings
from django.test import RequestFactory

if not settings.configured:
    # One real app so "is a ScitexAppConfig mounted" can be asked in BOTH
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

from scitex_app._app_scope import (  # noqa: E402
    DEFAULT_SCOPE,
    SCOPE_META_NAME,
    SCOPE_PROJECT,
    SCOPE_USER,
    VALID_SCOPES,
    app_scope_context,
    normalize_scope,
    scope_meta_tag,
)
from scitex_app._django import ScitexAppConfig  # noqa: E402
from scitex_app._app_scope import _inject_scope_meta  # noqa: E402
from scitex_app.appmaker._validate._manifest import validate_manifest  # noqa: E402


class TestNormalizeScope:
    def test_none_defaults_to_user(self):
        # Arrange
        value = None
        # Act
        got = normalize_scope(value)
        # Assert
        assert got == DEFAULT_SCOPE

    def test_empty_defaults_to_user(self):
        # Arrange
        value = "   "
        # Act
        got = normalize_scope(value)
        # Assert
        assert got == SCOPE_USER

    def test_project_normalizes_to_lower(self):
        # Arrange
        value = "PROJECT"
        # Act
        got = normalize_scope(value)
        # Assert
        assert got == SCOPE_PROJECT

    def test_user_normalizes_to_lower(self):
        # Arrange
        value = "User"
        # Act
        got = normalize_scope(value)
        # Assert
        assert got == SCOPE_USER

    def test_typed_scope_raises_and_names_the_enum(self):
        # Arrange — a typo'd scope must fail loud, never degrade to a guess.
        value = "workspace"
        # Act
        try:
            normalize_scope(value)
        except ValueError as exc:
            # Assert — it raised, and the message names the closed enum.
            assert "must be one of" in str(exc)
        else:
            raise AssertionError("normalize_scope did not raise for a typo'd scope")


class TestScopeMetaTag:
    def test_user_emits_no_marker(self):
        # Arrange — the no-selector rule made structural: user-scoped emits
        # nothing, so there is no marker to render.
        scope = SCOPE_USER
        # Act
        got = scope_meta_tag(scope)
        # Assert
        assert got == ""

    def test_project_emits_the_marker(self):
        # Arrange
        scope = SCOPE_PROJECT
        # Act
        got = scope_meta_tag(scope)
        # Assert
        assert SCOPE_META_NAME in got

    def test_marker_carries_the_project_value(self):
        # Arrange
        got = scope_meta_tag(SCOPE_PROJECT)
        # Act
        carries = f'content="{SCOPE_PROJECT}"' in got
        # Assert
        assert carries is True

    def test_marker_uses_the_mount_meta_sibling_name(self):
        # Arrange — the marker is a sibling of stx-mount, same injection point.
        expected = "stx-app-scope"
        # Act
        matches = SCOPE_META_NAME == expected
        # Assert
        assert matches is True


class TestInjectScopeMeta:
    def test_user_scope_leaves_html_unchanged(self):
        # Arrange — the no-selector rule: a user-scoped page is byte-identical
        # to the scope-unaware case.
        html = "<html><head></head><body></body></html>"
        # Act
        got = _inject_scope_meta(html, SCOPE_USER)
        # Assert
        assert got == html

    def test_project_scope_inserts_marker_after_head(self):
        # Arrange
        html = "<html><head></head><body></body></html>"
        # Act
        got = _inject_scope_meta(html, SCOPE_PROJECT)
        # Assert
        assert SCOPE_META_NAME in got

    def test_project_scope_marker_lands_in_head(self):
        # Arrange
        html = "<html><head></head><body></body></html>"
        # Act
        got = _inject_scope_meta(html, SCOPE_PROJECT)
        # Assert — the marker is after the <head> open tag, before </head>.
        assert got.index(SCOPE_META_NAME) < got.index("</head>")


def _make_app_config(tmp_path: Path, scope_value) -> ScitexAppConfig:
    mod = types.ModuleType("myapp._django")
    mod.__file__ = str(tmp_path / "__init__.py")
    cfg = ScitexAppConfig("myapp._django", mod)
    manifest = {
        "name": "myapp",
        "slug": "myapp",
        "label": "My App",
        "pip_package": "my-app",
        "icon": "fas fa-puzzle-piece",
        "license": "MIT",
    }
    if scope_value is not None:
        manifest["scope"] = scope_value
    (tmp_path / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    return cfg


class TestAppConfigScopeAccessors:
    def test_omitted_scope_defaults_to_user(self, tmp_path):
        # Arrange
        cfg = _make_app_config(tmp_path, None)
        # Act
        got = cfg.app_scope
        # Assert
        assert got == SCOPE_USER

    def test_project_scope_is_project_scoped(self, tmp_path):
        # Arrange
        cfg = _make_app_config(tmp_path, "project")
        # Act
        got = cfg.is_project_scoped
        # Assert
        assert got is True

    def test_user_scope_is_not_project_scoped(self, tmp_path):
        # Arrange
        cfg = _make_app_config(tmp_path, "user")
        # Act
        got = cfg.is_project_scoped
        # Assert
        assert got is False


class TestContextProcessor:
    def test_no_scitex_app_mounted_yields_user(self):
        # Arrange — contenttypes is the only mounted app, so no ScitexAppConfig.
        request = RequestFactory().get("/")
        # Act
        ctx = app_scope_context(request)
        # Assert
        assert ctx["app_scope"] == SCOPE_USER


class TestManifestScopeValidation:
    def _write_manifest(self, tmp_path: Path, scope_value) -> Path:
        manifest = {
            "name": "myapp",
            "slug": "myapp",
            "label": "My App",
            "pip_package": "my-app",
            "icon": "fas fa-puzzle-piece",
            "license": "MIT",
        }
        if scope_value is not None:
            manifest["scope"] = scope_value
        (tmp_path / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
        return tmp_path

    def test_valid_project_scope_passes(self, tmp_path):
        # Arrange
        app_dir = self._write_manifest(tmp_path, "project")
        # Act
        errors = validate_manifest(app_dir)
        # Assert
        assert not any("scope" in e for e in errors)

    def test_valid_user_scope_passes(self, tmp_path):
        # Arrange
        app_dir = self._write_manifest(tmp_path, "user")
        # Act
        errors = validate_manifest(app_dir)
        # Assert
        assert not any("scope" in e for e in errors)

    def test_omitted_scope_passes(self, tmp_path):
        # Arrange
        app_dir = self._write_manifest(tmp_path, None)
        # Act
        errors = validate_manifest(app_dir)
        # Assert
        assert not any("scope" in e for e in errors)

    def test_typed_scope_is_a_manifest_error(self, tmp_path):
        # Arrange — a typo'd scope must fail loud at validation, not render.
        app_dir = self._write_manifest(tmp_path, "workspace")
        # Act
        errors = validate_manifest(app_dir)
        # Assert
        assert any("scope" in e for e in errors)

    def test_non_string_scope_is_a_manifest_error(self, tmp_path):
        # Arrange
        manifest = {
            "name": "myapp",
            "slug": "myapp",
            "label": "My App",
            "pip_package": "my-app",
            "icon": "fas fa-puzzle-piece",
            "license": "MIT",
            "scope": 42,
        }
        (tmp_path / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
        # Act
        errors = validate_manifest(tmp_path)
        # Assert
        assert any("scope" in e for e in errors)
