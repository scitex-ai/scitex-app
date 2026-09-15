#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""The one-line plugin contract: a ``scitex.apps`` entry point makes a hub app.

Mirrors src/scitex_app/plugins.py (PS-204). Real ``EntryPoint`` objects, no mocks.
"""

from __future__ import annotations

from importlib.metadata import EntryPoint
from types import SimpleNamespace

from scitex_app.plugins import (
    ENTRY_POINT_GROUP,
    PluginApp,
    app_config_path,
    app_module_of,
    discover_plugin_apps,
    installed_app_paths,
    mount_route,
)


def _ep(name, value):
    return EntryPoint(name=name, value=value, group=ENTRY_POINT_GROUP)


def test_entry_point_value_becomes_installed_apps_path():
    # Arrange
    value = "figrecipe._django.apps:FigRecipeEditorConfig"
    # Act
    path = app_config_path(value)
    # Assert
    assert path == "figrecipe._django.apps.FigRecipeEditorConfig"


def test_bare_and_appconfig_entries_name_the_same_app_module():
    # Arrange
    entries = ["figrecipe._django", "figrecipe._django.apps.FigRecipeEditorConfig"]
    # Act
    modules = {app_module_of(e) for e in entries}
    # Assert
    assert modules == {"figrecipe._django"}


def test_discovery_is_sorted_and_first_name_wins():
    # Arrange
    eps = [_ep("b", "b.apps:B"), _ep("a", "a.apps:A"), _ep("a", "other.apps:X")]
    # Act
    found = discover_plugin_apps(eps)
    # Assert
    assert [p.app_config for p in found] == ["a.apps.A", "b.apps.B"]


def test_plugin_replaces_hand_written_entry_in_place():
    # Arrange
    existing = ["scitex_ui", "figrecipe._django", "scitex_writer._django.apps.W"]
    plugins = [PluginApp("figrecipe", "figrecipe._django.apps.FigRecipeEditorConfig")]
    # Act
    merged = installed_app_paths(existing, plugins)
    # Assert
    assert merged == [
        "scitex_ui",
        "figrecipe._django.apps.FigRecipeEditorConfig",
        "scitex_writer._django.apps.W",
    ]


def test_new_plugin_is_appended():
    # Arrange
    plugins = [PluginApp("hello", "hello_world.apps.HelloWorldConfig")]
    # Act
    merged = installed_app_paths(["scitex_ui"], plugins)
    # Assert
    assert merged == ["scitex_ui", "hello_world.apps.HelloWorldConfig"]


def test_mount_route_defaults_to_apps_slug():
    # Arrange
    config = SimpleNamespace(label="hello_world", manifest={"slug": "hello-world"})
    # Act
    route = mount_route(config)
    # Assert
    assert route == "apps/hello-world/"


def test_mount_route_honours_manifest_url():
    # Arrange
    config = SimpleNamespace(label="x", manifest={"slug": "x", "url": "/apps/u/x/"})
    # Act
    route = mount_route(config)
    # Assert
    assert route == "apps/u/x/"
