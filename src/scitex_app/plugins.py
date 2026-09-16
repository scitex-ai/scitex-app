#!/usr/bin/env python3
# File: scitex_app/plugins.py

"""Install a SciTeX app into a hub with one line: ``pip install <package>``.

A package becomes a hub app by declaring ONE entry point in the
``scitex.apps`` group whose value is its ``ScitexAppConfig`` subclass::

    [project.entry-points."scitex.apps"]
    figrecipe = "figrecipe._django.apps:FigRecipeEditorConfig"

The host (scitex-hub, or any Django project) then:

1. appends :func:`installed_app_paths` to ``INSTALLED_APPS`` (settings time —
   entry-point values are read as strings, nothing is imported, so settings
   never pull in Django app code);
2. mounts ``include(f"{config.name}.urls")`` at :func:`mount_route` for each
   of :func:`loaded_plugin_configs` (urls time);
3. lists the app on its launcher from ``config.manifest``.

Pre-installed apps use the same path: the hub's own dependency list pins
them, the entry point does the rest.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List, Optional

ENTRY_POINT_GROUP = "scitex.apps"


@dataclass(frozen=True)
class PluginApp:
    """One ``scitex.apps`` entry point, read without importing it."""

    name: str
    app_config: str
    distribution: str = ""

    @property
    def app_module(self) -> str:
        return app_module_of(self.app_config)


def app_config_path(entry_point_value: str) -> str:
    """``"pkg._django.apps:Cfg"`` -> ``"pkg._django.apps.Cfg"`` (INSTALLED_APPS form)."""
    module, _, attr = entry_point_value.strip().partition(":")
    return f"{module}.{attr}" if attr else module


def app_module_of(installed_app: str) -> str:
    """The Django app package an INSTALLED_APPS entry points at.

    ``"pkg._django.apps.Cfg"`` and ``"pkg._django"`` both give ``"pkg._django"``,
    so a discovered entry can replace a hand-written one for the same app.
    """
    parts = installed_app.split(".")
    if len(parts) > 1 and parts[-1][:1].isupper():
        parts = parts[:-1]
    if len(parts) > 1 and parts[-1] == "apps":
        parts = parts[:-1]
    return ".".join(parts)


def discover_plugin_apps(entry_points: Optional[Iterable] = None) -> List[PluginApp]:
    """Every installed ``scitex.apps`` entry point, sorted by name, first wins."""
    if entry_points is None:
        from importlib.metadata import entry_points as _entry_points

        entry_points = _entry_points(group=ENTRY_POINT_GROUP)
    found = {}
    for ep in entry_points:
        if ep.name in found:
            continue
        dist = getattr(getattr(ep, "dist", None), "name", "") or ""
        found[ep.name] = PluginApp(ep.name, app_config_path(ep.value), dist)
    return [found[k] for k in sorted(found)]


def installed_app_paths(
    existing: Iterable[str] = (), plugins: Optional[Iterable[PluginApp]] = None
) -> List[str]:
    """``existing`` INSTALLED_APPS with every discovered plugin merged in.

    A plugin whose app package is already listed replaces that entry in place
    (order kept); the rest are appended.
    """
    plugins = discover_plugin_apps() if plugins is None else list(plugins)
    by_module = {p.app_module: p.app_config for p in plugins}
    merged: List[str] = []
    for entry in existing:
        merged.append(by_module.pop(app_module_of(entry), entry))
    merged.extend(by_module.values())
    return merged


def loaded_plugin_configs(plugins: Optional[Iterable[PluginApp]] = None) -> list:
    """The ready AppConfig instances of discovered plugins (needs Django set up)."""
    from django.apps import apps

    wanted = {p.app_config for p in (discover_plugin_apps() if plugins is None else plugins)}
    return [
        cfg
        for cfg in apps.get_app_configs()
        if f"{type(cfg).__module__}.{type(cfg).__qualname__}" in wanted
    ]


def mount_route(config) -> str:
    """Where a plugin is mounted: manifest ``url`` if given, else ``apps/<slug>/``."""
    manifest = getattr(config, "manifest", None) or {}
    url = (manifest.get("url") or "").strip("/")
    slug = manifest.get("slug") or getattr(config, "label", "")
    return f"{url}/" if url else f"apps/{slug}/"


__all__ = [
    "ENTRY_POINT_GROUP",
    "PluginApp",
    "app_config_path",
    "app_module_of",
    "discover_plugin_apps",
    "installed_app_paths",
    "loaded_plugin_configs",
    "mount_route",
]

# EOF
