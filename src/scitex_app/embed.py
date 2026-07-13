#!/usr/bin/env python3
# Timestamp: 2026-07-13
# File: scitex_app/embed.py

"""scitex_app.embed --- Public host-embedding API for SciTeX apps.

Wraps the Django integration base classes (``_django.py``) and the
standalone launcher (``_standalone.py``) behind one stable, public
import path, so host apps (figrecipe, writer, scitex-todo, storage, ...)
no longer need to reach into ``scitex_app._django`` / ``scitex_app._standalone``
directly.

Usage::

    from scitex_app.embed import run_standalone
    run_standalone(app_module="figrecipe._django", port=31298)

Or, mounting inside an existing Django project::

    from scitex_app.embed import ScitexAppConfig, scitex_urlpatterns
"""

from __future__ import annotations

from ._standalone import run_standalone

try:
    from ._django import (
        ScitexAppConfig,
        scitex_api_dispatch,
        scitex_editor_page,
        scitex_urlpatterns,
    )
except ImportError:
    # _django requires Django; keep embed importable for consumers that
    # only need the standalone launcher (which lazy-imports Django itself).
    ScitexAppConfig = None  # type: ignore[assignment]
    scitex_api_dispatch = None  # type: ignore[assignment]
    scitex_editor_page = None  # type: ignore[assignment]
    scitex_urlpatterns = None  # type: ignore[assignment]

__all__ = [
    "run_standalone",
    "ScitexAppConfig",
    "scitex_api_dispatch",
    "scitex_editor_page",
    "scitex_urlpatterns",
]

# EOF
