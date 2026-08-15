#!/usr/bin/env python3
# Timestamp: 2026-03-17
# File: scitex_app/_django.py

"""scitex_app._django --- Optional Django integration base classes.

Requires Django to be installed. Import guard at module level.

This is an implementation module — consumers should import from the
public ``scitex_app.embed`` surface, not from here directly::

    from scitex_app.embed import ScitexAppConfig, scitex_api_dispatch, scitex_editor_page
"""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

try:
    from django.apps import AppConfig
    from django.http import HttpResponse, JsonResponse
    from django.utils.html import escape
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


#: Name of the <meta> tag carrying the app's mount prefix to the browser.
#: Client code reads this to build API URLs that work under any mount.
MOUNT_META_NAME = "stx-mount"

#: The <head> opening tag, and NOT <header>. The delimiter after the name is
#: required, so `<header` cannot match: `<head>`, `<head lang="en">` do, and
#: the search stops at that tag's own closing `>`.
_HEAD_OPEN_TAG = re.compile(r"<head(?:\s[^>]*)?>", re.IGNORECASE)


def _inject_mount_meta(html: str, mount_prefix: str) -> str:
    """Return `html` with a <meta> carrying `mount_prefix` in its head.

    Deliberately a STRING INSERTION rather than a Django template render.
    A built SPA's index.html routinely contains `{{` / `{%` inside inlined
    JS, which the template engine would try to interpret; running these
    files through it would break bundles for reasons that have nothing to
    do with mounting. This adds exactly one tag and touches nothing else.

    When there is no <head> the tag is prepended instead. That is still
    correct — the HTML parser hoists a leading <meta> into the head — and
    it means the prefix is never silently dropped for an unusual document.

    The opening tag is matched as `<head>` or `<head ...>` specifically.
    A plain substring search for "<head" also matches `<header`, which put
    the marker inside a <header> element for documents that have one and no
    real head. The tag stayed findable, so the contract held, but the
    placement contradicted the paragraph above.
    """
    tag = f'<meta name="{MOUNT_META_NAME}" content="{escape(mount_prefix)}">'
    match = _HEAD_OPEN_TAG.search(html)
    if match:
        return html[: match.end()] + tag + html[match.end() :]
    return tag + html


def scitex_editor_page(
    static_dir: Path,
    index_file: str = "index.html",
    fallback_message: str = "React build not found. Run: npm run build",
) -> Callable:
    """Factory: create a view that serves the React SPA from static_dir.

    The served HTML carries a ``<meta name="stx-mount" content="...">``
    naming the prefix the app is mounted under — "/" standalone, or
    "/apps/u/<module>/" as a scitex-hub built-in app.

    This is what lets ONE codebase run in both modes. `scitex_urlpatterns`
    is already prefix-agnostic on the server side (its patterns are
    relative, so `include()` works under any root), but until now nothing
    told the BROWSER where it was mounted. Client code had no supported
    way to learn it, so leaves hardcoded "/" — which works perfectly
    standalone and breaks silently once embedded.

    The value is derived server-side from ``request.path``: this view is
    registered at the mount root (``path("", ...)``), so its request path
    IS the prefix. Never guess it client-side.

    Args:
        static_dir: Path to the app's static/built files.
        index_file: Name of the HTML entry point.
        fallback_message: Message when build is missing.
    """

    def view(request):
        html_path = static_dir / index_file
        if html_path.exists():
            mount_prefix = request.path if request.path.endswith("/") else request.path + "/"
            return HttpResponse(_inject_mount_meta(html_path.read_text(), mount_prefix))
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
        from scitex_app.embed import scitex_urlpatterns
        from . import views
        urlpatterns = scitex_urlpatterns(views)
    """
    from django.urls import path

    return [
        path("", views_module.editor_page, name="editor"),
        path("<path:endpoint>", views_module.api_dispatch, name="api"),
    ]


# EOF
