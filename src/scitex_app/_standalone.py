"""Shared standalone launcher for SciTeX apps.

Provides a minimal Django server with the full workspace shell
(sidebar, three-column layout, file tree, AI panel) from scitex-ui.

Any app can use this to run locally with the same UX as scitex-cloud:

    from scitex_app._standalone import run_standalone
    run_standalone(app_module="figrecipe._django", port=5050)
"""

from __future__ import annotations

import os
import threading
import webbrowser
from pathlib import Path
from typing import Optional


def run_standalone(
    app_module: str,
    port: int = 8050,
    host: str = "127.0.0.1",
    open_browser: bool = True,
    hot_reload: bool = False,
    working_dir: Optional[str] = None,
    desktop: bool = False,
    extra_installed_apps: Optional[list[str]] = None,
    extra_staticfiles_dirs: Optional[list[str]] = None,
    extra_env: Optional[dict[str, str]] = None,
) -> None:
    """Launch a standalone workspace with the full shell.

    Parameters
    ----------
    app_module : str
        Dotted path to the app's Django module (e.g. "figrecipe._django").
    port : int
        Server port (default: 8050).
    host : str
        Host to bind (default: "127.0.0.1").
    open_browser : bool
        Whether to open browser automatically.
    hot_reload : bool
        Enable Django auto-reload.
    working_dir : str, optional
        Working directory for the file tree.
    desktop : bool
        Launch as native desktop window via pywebview.
    extra_installed_apps : list[str], optional
        Additional Django apps to include.
    extra_staticfiles_dirs : list[str], optional
        Additional static file directories.
    extra_env : dict[str, str], optional
        Additional environment variables.
    """
    # Set env vars before Django setup
    if working_dir:
        os.environ["SCITEX_WORKING_DIR"] = str(Path(working_dir).resolve())
    elif "SCITEX_WORKING_DIR" not in os.environ:
        os.environ["SCITEX_WORKING_DIR"] = str(Path.cwd())

    if extra_env:
        os.environ.update(extra_env)

    # Configure and start Django
    _configure_django(app_module, extra_installed_apps, extra_staticfiles_dirs)

    import django

    django.setup()

    url = f"http://{host}:{port}/"

    if open_browser and not desktop:
        threading.Timer(1.5, webbrowser.open, args=[url]).start()

    if desktop:
        try:
            import webview

            threading.Thread(
                target=_run_server, args=(host, port, hot_reload), daemon=True
            ).start()

            import time

            time.sleep(1.0)
            webview.create_window("SciTeX App", url, width=1400, height=900)
            webview.start()
            return
        except ImportError:
            print(
                "pywebview not installed. Falling back to browser.\n"
                "Install with: pip install pywebview"
            )
            if open_browser:
                threading.Timer(1.5, webbrowser.open, args=[url]).start()

    _run_server(host, port, hot_reload)


def _configure_django(
    app_module: str,
    extra_installed_apps: Optional[list[str]] = None,
    extra_staticfiles_dirs: Optional[list[str]] = None,
) -> None:
    """Configure Django settings for standalone mode."""
    import django.conf

    if django.conf.settings.configured:
        return

    installed_apps = [
        "django.contrib.staticfiles",
        app_module,
    ]

    # Add scitex-ui for shared workspace shell components
    try:
        import scitex_ui  # noqa: F401

        installed_apps.append("scitex_ui")
    except ImportError:
        pass

    if extra_installed_apps:
        installed_apps.extend(extra_installed_apps)

    # Resolve static file directories
    staticfiles_dirs: list[str] = []

    # App's own static dir
    app_static = _resolve_module_static(app_module)
    if app_static:
        staticfiles_dirs.append(app_static)

    # scitex-app's standalone shell template static
    shell_static = str(Path(__file__).parent / "_standalone_static")
    if Path(shell_static).is_dir():
        staticfiles_dirs.append(shell_static)

    if extra_staticfiles_dirs:
        staticfiles_dirs.extend(extra_staticfiles_dirs)

    django.conf.settings.configure(
        SECRET_KEY=os.environ.get("DJANGO_SECRET_KEY", "scitex-standalone-dev-key"),
        DEBUG=os.environ.get("DJANGO_DEBUG", "true").lower() == "true",
        ALLOWED_HOSTS=["127.0.0.1", "localhost", "0.0.0.0"],
        INSTALLED_APPS=installed_apps,
        MIDDLEWARE=[
            "django.middleware.security.SecurityMiddleware",
            "django.middleware.common.CommonMiddleware",
        ],
        ROOT_URLCONF=f"{app_module}.urls",
        TEMPLATES=[
            {
                "BACKEND": "django.template.backends.django.DjangoTemplates",
                "DIRS": [],
                "APP_DIRS": True,
                "OPTIONS": {
                    "context_processors": [
                        "django.template.context_processors.request",
                    ],
                },
            },
        ],
        DATABASES={},
        STATIC_URL="/static/",
        STATICFILES_DIRS=staticfiles_dirs,
    )


def _resolve_module_static(module_path: str) -> Optional[str]:
    """Find the static/ dir inside a module."""
    try:
        import importlib

        mod = importlib.import_module(module_path)
        mod_dir = Path(mod.__file__).parent
        static_dir = mod_dir / "static"
        if static_dir.is_dir():
            return str(static_dir)
    except (ImportError, AttributeError, TypeError):
        pass
    return None


def _run_server(host: str, port: int, hot_reload: bool) -> None:
    """Start Django development server."""
    from django.core.management import call_command

    noreload = [] if hot_reload else ["--noreload"]
    call_command("runserver", f"{host}:{port}", *noreload)


# EOF
