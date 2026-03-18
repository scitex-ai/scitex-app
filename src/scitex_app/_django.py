#!/usr/bin/env python3
# Timestamp: 2026-03-17
# File: scitex_app/_django.py

"""scitex_app._django --- Optional Django integration base classes.

Requires Django to be installed. Import guard at module level.

Usage::

    from scitex_app._django import ScitexAppConfig, scitex_api_dispatch, scitex_editor_page
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

try:
    from django.apps import AppConfig
    from django.http import HttpResponse, JsonResponse
    from django.views.decorators.csrf import csrf_exempt
except ImportError as e:
    raise ImportError(
        "scitex_app._django requires Django. Install with: pip install django"
    ) from e

logger = logging.getLogger(__name__)

# Required fields in manifest.json
MANIFEST_REQUIRED = {"name", "slug", "label", "version", "icon"}


class ScitexAppConfig(AppConfig):
    """Base Django AppConfig for SciTeX apps.

    Automatically loads and validates manifest.json from the app directory.

    Usage::

        class MyAppConfig(ScitexAppConfig):
            name = "myapp._django"
            label = "myapp"
            verbose_name = "My App"
    """

    default_auto_field = "django.db.models.BigAutoField"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._manifest: Optional[Dict[str, Any]] = None

    @property
    def manifest(self) -> Dict[str, Any]:
        """Load and cache manifest.json from the app directory."""
        if self._manifest is None:
            manifest_path = Path(self.path) / "manifest.json"
            if manifest_path.exists():
                self._manifest = json.loads(manifest_path.read_text())
            else:
                self._manifest = {}
                logger.warning(
                    "[%s] No manifest.json found at %s", self.label, manifest_path
                )
        return self._manifest

    @property
    def app_slug(self) -> str:
        return self.manifest.get("slug", self.label)

    @property
    def app_version(self) -> str:
        return self.manifest.get("version", "0.0.0")

    @property
    def app_icon(self) -> str:
        return self.manifest.get("icon", "fas fa-puzzle-piece")

    @property
    def is_standalone(self) -> bool:
        return self.manifest.get("standalone", False)

    @property
    def frontend_type(self) -> str:
        return self.manifest.get("frontend_type", "django")

    def validate_manifest(self) -> List[str]:
        """Validate manifest.json. Returns list of error messages (empty = valid)."""
        errors = []
        missing = MANIFEST_REQUIRED - set(self.manifest.keys())
        if missing:
            errors.append(f"Missing required fields: {', '.join(sorted(missing))}")
        return errors


def scitex_editor_page(
    static_dir: Path,
    index_file: str = "index.html",
    fallback_message: str = "React build not found. Run: npm run build",
) -> Callable:
    """Factory: create a view that serves the React SPA from static_dir.

    Args:
        static_dir: Path to the app's static/built files.
        index_file: Name of the HTML entry point.
        fallback_message: Message when build is missing.
    """

    def view(request):
        html_path = static_dir / index_file
        if html_path.exists():
            return HttpResponse(html_path.read_text())
        return HttpResponse(
            f"<html><body><h1>{fallback_message}</h1></body></html>",
            status=503,
        )

    return view


def scitex_api_dispatch(
    handlers: Dict[str, Callable],
    parameterized: Optional[List[Tuple[str, Callable]]] = None,
    no_editor_endpoints: Optional[set] = None,
    get_editor: Optional[Callable] = None,
) -> Callable:
    """Factory: create a csrf_exempt API dispatch view.

    Args:
        handlers: Dict mapping endpoint string to handler(request, editor).
        parameterized: List of (prefix, handler) for path-parameterized endpoints.
        no_editor_endpoints: Set of endpoints that work without an editor.
        get_editor: Optional callable(request) returning editor object (or None).

    Returns:
        A Django view function: api_dispatch(request, endpoint).
    """
    _parameterized = parameterized or []
    _no_editor = no_editor_endpoints or set()

    @csrf_exempt
    def dispatch(request, endpoint):
        editor = get_editor(request) if get_editor else None

        # Check if endpoint needs editor
        needs_editor = endpoint not in _no_editor
        for prefix, _ in _parameterized:
            if endpoint.startswith(prefix):
                needs_editor = False
                break

        if editor is None and needs_editor:
            handler = handlers.get(endpoint)
            if handler:
                return JsonResponse(
                    {"error": "No context loaded. Select a file to begin."},
                    status=400,
                )

        # Exact match handlers
        handler = handlers.get(endpoint)
        if handler:
            try:
                return handler(request, editor)
            except Exception as e:
                logger.exception("API error on /%s", endpoint)
                return JsonResponse({"error": str(e)}, status=500)

        # Parameterized handlers
        for prefix, handler in _parameterized:
            if endpoint.startswith(prefix):
                param = endpoint[len(prefix) :]
                try:
                    return handler(request, editor, param)
                except Exception as e:
                    logger.exception("API error on /%s%s", prefix, param)
                    return JsonResponse({"error": str(e)}, status=500)

        return JsonResponse({"error": f"Unknown endpoint: {endpoint}"}, status=404)

    return dispatch


def scitex_urlpatterns(views_module) -> list:
    """Generate standard URL patterns for a SciTeX app.

    Expects views_module to have ``editor_page`` and ``api_dispatch`` attributes.

    Usage::

        # In your urls.py:
        from scitex_app._django import scitex_urlpatterns
        from . import views
        urlpatterns = scitex_urlpatterns(views)
    """
    from django.urls import path

    return [
        path("", views_module.editor_page, name="editor"),
        path("<path:endpoint>", views_module.api_dispatch, name="api"),
    ]


# EOF
