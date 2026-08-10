#!/usr/bin/env python3
# Timestamp: 2026-07-13
# File: tests/scitex_app/test_embed.py

"""Tests for scitex_app.embed — the public host-embedding API surface."""

from __future__ import annotations

import scitex_app
import scitex_app.embed as embed
from scitex_app import _django, _standalone


def test_embed_run_standalone_is_standalone_impl():
    # Arrange
    # Act
    # Assert
    assert embed.run_standalone is _standalone.run_standalone


def test_embed_scitex_app_config_is_django_impl():
    # Arrange
    # Act
    # Assert
    assert embed.ScitexAppConfig is _django.ScitexAppConfig


def test_embed_scitex_api_dispatch_is_django_impl():
    # Arrange
    # Act
    # Assert
    assert embed.scitex_api_dispatch is _django.scitex_api_dispatch


def test_embed_scitex_editor_page_is_django_impl():
    # Arrange
    # Act
    # Assert
    assert embed.scitex_editor_page is _django.scitex_editor_page


def test_embed_scitex_urlpatterns_is_django_impl():
    # Arrange
    # Act
    # Assert
    assert embed.scitex_urlpatterns is _django.scitex_urlpatterns


def test_embed_reachable_via_lazy_attribute_on_package():
    # Arrange
    # Act
    resolved = scitex_app.embed
    # Assert
    assert resolved is embed


def test_embed_in_public_all():
    # Arrange
    # Act
    # Assert
    assert "embed" in scitex_app.__all__


def test_embed_all_exports_resolve_to_non_none():
    # Arrange
    missing = [name for name in embed.__all__ if getattr(embed, name) is None]
    # Act
    # Assert
    assert missing == []
