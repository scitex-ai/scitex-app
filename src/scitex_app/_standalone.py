"""Shared standalone launcher for SciTeX apps.

Provides a minimal Django server with the full workspace shell
(sidebar, three-column layout, file tree, AI panel) from scitex-ui.

Any app can use this to run locally with the same UX as scitex-hub:

    from scitex_app.embed import run_standalone
    run_standalone(app_module="figrecipe._django")
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
    _configure_django(app_module, extra_installed_apps, extra_staticfiles_dirs, host=host)
    _warn_about_uncompiled_languages(app_module, extra_installed_apps)

    import django

    django.setup()

    url = f"http://{host}:{port}/"

    if open_browser and not desktop:
        threading.Timer(1.5, webbrowser.open, args=[url]).start()

    if desktop:
        try:
            import webview
        except ImportError:
            print(
                "pywebview not installed. Falling back to browser.\n"
                "Install with: pip install pywebview"
            )
            if open_browser:
                threading.Timer(1.5, webbrowser.open, args=[url]).start()
        else:
            # Guard narrowed to the optional import only: a failure inside
            # webview.create_window/start must propagate, not be mistaken
            # for "pywebview not installed" and silently downgrade to a
            # shell-less server (scitex-writer _server.run(), fixed 2.30.0).
            threading.Thread(
                target=_run_server, args=(host, port, hot_reload), daemon=True
            ).start()

            import time

            time.sleep(1.0)
            webview.create_window("SciTeX App", url, width=1400, height=900)
            webview.start()
            return

    _run_server(host, port, hot_reload)


# ── What a bind implies ───────────────────────────────────────────────────────
# VERBATIM from scitex-scholar's _django/_server.py (PR #137, ad439af,
# 2026-09-02), by scitex-hub's ruling as coordinator: scholar and figrecipe
# carry the same block until this one is released, then replace theirs with an
# import. Keep it byte-for-byte with theirs; fix bugs here first, then sync.

_LOOPBACK = ("127.0.0.1", "localhost")
_BIND_ALL = "0.0.0.0"


def _interface_ipv4_addresses() -> list[str]:
    """Every IPv4 address assigned to a network interface on this machine.

    Read from the INTERFACES (SIOCGIFADDR per `socket.if_nameindex()` entry),
    not from name resolution. `getaddrinfo(gethostname())` was the first
    attempt and it FAILED THE LIVE CHECK while passing the unit test: inside a
    container the hostname resolves to an address that is not the LAN
    interface, so `--host 0.0.0.0` still answered 400 to the real address.
    The unit test had only asserted the hostname was present -- it could not
    fail for the case that mattered. Interfaces cannot lie about which
    addresses they hold. Linux/macOS ioctl; returns [] where unavailable.
    """
    import socket

    try:
        import fcntl
        import struct
    except ImportError:  # not a POSIX platform
        return []

    _SIOCGIFADDR = 0x8915
    found: list[str] = []
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        for _, name in socket.if_nameindex():
            try:
                packed = fcntl.ioctl(
                    s.fileno(),
                    _SIOCGIFADDR,
                    struct.pack("256s", name[:15].encode()),
                )
            except OSError:
                continue  # interface with no IPv4 address
            addr = socket.inet_ntoa(packed[20:24])
            if not addr.startswith("127.") and addr not in found:
                found.append(addr)
    return found


def _local_addresses() -> list[str]:
    """This machine's hostname plus every IPv4 address its interfaces hold.

    Used only for the 0.0.0.0 bind. Loopback is excluded because settings.py
    already lists it.
    """
    import socket

    found: list[str] = []
    hostname = socket.gethostname()
    if hostname:
        found.append(hostname)
    found.extend(a for a in _interface_ipv4_addresses() if a not in found)
    return found


def _hosts_to_allow(host: str) -> list[str]:
    """What a given ``--host`` bind implies for ALLOWED_HOSTS. Pure function.

    Binding to an address IS the statement that you intend to be reached on
    it, so contribute it rather than making the caller set an env var to
    permit what they already asked for:

        127.0.0.1 / localhost   -> []            settings.py lists loopback
        0.0.0.0                 -> hostname + this machine's interface addresses
        anything else           -> [host]

    The 0.0.0.0 rule is what makes DEBUG=False the safe default WITHOUT
    reintroducing the bug #126 fixed: a bind-all server receives requests whose
    Host header is the real interface address, and "0.0.0.0" in ALLOWED_HOSTS
    never matches that. Measured 2026-09-02 on the published 1.9.0 wheel:
    `--host 0.0.0.0` with DJANGO_DEBUG=false answered 400 to every real
    address while loopback answered 200.
    """
    if host in _LOOPBACK:
        return []
    if host == _BIND_ALL:
        return _local_addresses()
    return [host]


def _allowed_hosts(host: str, extra_hosts: str = "") -> list[str]:
    """ALLOWED_HOSTS for a server bound to `host`.

    BINDING TO AN ADDRESS IS THE STATEMENT THAT YOU INTEND TO BE REACHED ON IT,
    so the bound host is always allowed. Without this, `serve --host <addr>`
    starts cleanly, prints "serving at http://<addr>:<port>", and then answers
    400 Bad Request to every caller — the banner says the opposite of the truth,
    so the first place anyone looks is the network.

    Reported by scitex-scholar 2026-08-23 after hitting it exposing scholar on
    the tailnet; measured identically in scitex-writer, figrecipe and
    scitex-storage, and here.

    `extra_hosts` is a comma-separated string contributing additional names, for
    the proxy/tunnel case where the reachable name is not the bound address. The
    caller reads `SCITEX_ALLOWED_HOSTS` and passes it in: keeping the env read
    OUT of this function makes it pure, so its tests need no fixture that
    reaches into process state. PA-306 forbids mocks, and the first draft of
    these tests used `monkeypatch` precisely because the function was impure —
    the rule was pointing at the design, not at the test.

    Deliberately NOT widened to `["*"]` under DEBUG. That is what the leaves are
    doing, and it is defensible there, but these apps ship no authentication —
    `"*"` plus no auth makes every reachable address an unauthenticated reader,
    and DJANGO_DEBUG defaults to "true". Allowing exactly what was asked for
    fixes the silent 400 without widening anything.
    """
    hosts = ["127.0.0.1", "localhost", "0.0.0.0"]
    # What the bind IMPLIES, not the bind string: "0.0.0.0" was already in the
    # base list, so `--host 0.0.0.0` used to contribute nothing, and a request
    # carrying the real interface address in its Host header was refused with
    # 400 (measured 2026-09-02 by scholar on 1.9.0 and by figrecipe on 0.34.6).
    for contributed in _hosts_to_allow(host):
        if contributed not in hosts:
            hosts.append(contributed)
    hosts.extend(h.strip() for h in extra_hosts.split(",") if h.strip())
    return hosts



# ── Internationalisation ─────────────────────────────────────────────────────
# Catalog DISCOVERY is free: Django auto-discovers `<app>/locale/<lang>/
# LC_MESSAGES/django.mo` for anything in INSTALLED_APPS, with no LOCALE_PATHS
# entry and no cooperation from the host. Measured 2026-08-23.
#
# ACTIVATION is what was missing, and it is the whole defect. Without
# LocaleMiddleware nothing ever calls activate(), so a standalone app shipped a
# working Japanese catalog, loaded it, and rendered English forever. Note the
# symmetry with scitex-hub, who found the mirror image in their own stack:
#
#     hub          activation wired, catalog EMPTY
#     standalone   catalog works, activation ABSENT
#
# Both fall back SILENTLY to the source string, so both read as "nobody has
# translated it yet" rather than "the mechanism is broken". That is why
# _languages_missing_catalogs exists below: declaring a language you cannot
# render should say so, not degrade quietly.


def _declared_languages(spec: str) -> list[tuple[str, str]]:
    """Parse SCITEX_LANGUAGES ("en,ja") into Django's LANGUAGES shape.

    Returns [] when unset, which leaves Django's own LANGUAGES (every language
    Django ships) in place. Restricting the list is opt-in because an app that
    names no languages should not thereby lose the ones Django already supports.
    """
    codes = [c.strip() for c in spec.split(",") if c.strip()]
    return [(c, c) for c in codes]


def _languages_missing_catalogs(codes: list[str], app_modules: list[str]) -> list[str]:
    """Declared languages with no compiled catalog in any of `app_modules`.

    This is the anti-silent-fallback check. gettext falls back to the source
    string when a catalog is absent, which is indistinguishable from "not
    translated yet" — so a language named in LANGUAGES with no `.mo` anywhere is
    reported at startup rather than discovered by a reader who wonders why the
    page is in English.

    Looks for the COMPILED artifact only. A `.po` without its `.mo` is exactly
    the shape that ships green: the translation exists in the repo and does not
    exist in the running process.

    Takes both lists as arguments so it is pure and needs no Django app registry
    — it runs before django.setup().
    """
    import importlib.util

    missing = []
    for code in codes:
        found = False
        for module in app_modules:
            try:
                spec = importlib.util.find_spec(module)
            except (ImportError, ValueError):
                continue
            if spec is None or not spec.origin:
                continue
            mo = (
                Path(spec.origin).parent
                / "locale"
                / code
                / "LC_MESSAGES"
                / "django.mo"
            )
            if mo.is_file():
                found = True
                break
        if not found:
            missing.append(code)
    return missing


def _language_settings(spec: str) -> dict:
    """`{"LANGUAGES": [...]}` when SCITEX_LANGUAGES is set, `{}` otherwise.

    Returned as a dict to splat rather than a value, because passing
    `LANGUAGES=[]` would mean "this app supports no languages" — the opposite of
    "the app did not say". Omitting the key leaves Django's default intact.
    """
    declared = _declared_languages(spec)
    return {"LANGUAGES": declared} if declared else {}


def _warn_about_uncompiled_languages(
    app_module: str, extra_installed_apps: Optional[list[str]] = None
) -> None:
    """Say so when a declared language has no compiled catalog.

    Printed rather than raised: a missing translation must not stop a server
    from starting, and refusing to serve English because Japanese is missing
    would be worse than the bug. But it must not be SILENT either — that is the
    whole failure mode, and it is why this exists at all.
    """
    codes = [c for c, _ in _declared_languages(os.environ.get("SCITEX_LANGUAGES", ""))]
    if not codes:
        return
    modules = [app_module, "scitex_ui", *(extra_installed_apps or [])]
    missing = _languages_missing_catalogs(codes, modules)
    if not missing:
        return
    print(
        f"WARNING: SCITEX_LANGUAGES declares {', '.join(missing)} but no compiled "
        f"catalog (locale/<lang>/LC_MESSAGES/django.mo) was found for "
        f"{'it' if len(missing) == 1 else 'them'} in {', '.join(modules)}. "
        f"Those languages will render the source strings, which looks like "
        f"'not translated yet' rather than 'the catalog was never compiled'. "
        f"Note `django-admin compilemessages` needs the gettext `msgfmt` binary, "
        f"which is absent from several SciTeX images — compile at build time and "
        f"ship the .mo inside the distribution."
    )

def _configure_django(
    app_module: str,
    extra_installed_apps: Optional[list[str]] = None,
    extra_staticfiles_dirs: Optional[list[str]] = None,
    host: str = "127.0.0.1",
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
        ALLOWED_HOSTS=_allowed_hosts(
            host, os.environ.get("SCITEX_ALLOWED_HOSTS", "")
        ),
        INSTALLED_APPS=installed_apps,
        MIDDLEWARE=[
            "django.middleware.security.SecurityMiddleware",
            # BEFORE CommonMiddleware, per Django's own ordering requirement.
            # Without this nothing activates a language and every catalog is
            # inert no matter how complete it is.
            "django.middleware.locale.LocaleMiddleware",
            "django.middleware.common.CommonMiddleware",
        ],
        USE_I18N=True,
        LANGUAGE_CODE=os.environ.get("SCITEX_LANGUAGE_CODE", "en-us"),
        **_language_settings(os.environ.get("SCITEX_LANGUAGES", "")),
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
