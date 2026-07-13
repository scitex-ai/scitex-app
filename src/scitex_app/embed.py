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

import os
import socket
from pathlib import Path
from typing import Callable, Optional, Union

from . import _gui_runtime as _gr
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


def gui_status(package: str, state_path: Optional[Union[str, Path]] = None) -> dict:
    """Report whether `package`'s standalone GUI server is running.

    `state_path` overrides the resolved runtime-state path -- real
    dependency injection for tests/callers with a custom scope,
    instead of monkeypatching internals.
    """
    return _gr.status(state_path if state_path is not None else _gr.state_path(package))


def gui_stop(
    package: str,
    timeout: float = 5.0,
    state_path: Optional[Union[str, Path]] = None,
) -> dict:
    """Stop `package`'s standalone GUI server (SIGTERM the recorded pid)."""
    return _gr.stop(
        state_path if state_path is not None else _gr.state_path(package),
        timeout=timeout,
    )


def gui_port_holder(port: int) -> Optional[dict]:
    """Identify the process LISTENing on `port` (via /proc, no `ss`/`lsof`)."""
    return _gr.port_holder(port)


def _port_is_free(host: str, port: int) -> bool:
    """True when `host:port` can be bound right now."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        try:
            sock.bind((host, port))
        except OSError:
            return False
    return True


def _port_taken_message(package: str, host: str, port: int) -> str:
    """Explain who holds `port` and give paste-ready commands to fix it.

    This path means the port is held by something not tracked in our
    runtime state -- an orphaned server, or an unrelated process.
    `--force` only stops the server recorded in our own state, so it
    is deliberately NOT offered here for a foreign holder: a hint that
    does not work is worse than no hint.
    """
    holder = _gr.port_holder(port)
    lines = [f"Error: port {port} is already in use on {host}."]
    if holder and holder.get("pid"):
        lines.append(f"Held by: {holder['name']} (pid {holder['pid']})")
    elif holder:
        lines.append("Held by: a process owned by another user.")
    else:
        lines.append("Held by: unknown (the listening process could not be read).")
    lines += ["", "Fix it with one of:"]
    lines.append(f"  {package} gui --port {port + 1}   # serve on a free port")
    if holder and holder.get("pid"):
        lines.append(f"  kill {holder['pid']}{' ' * 26}# stop it, then serve again")
    return "\n".join(lines)


def serve_gui(
    package: str,
    project_dir: str,
    port: int,
    host: str,
    force: bool,
    run_server: Callable[[], None],
    state_path: Optional[Union[str, Path]] = None,
) -> int:
    """Guarded launcher for a scaffolded app's `gui` command.

    Binds exactly `port`, or fails loud -- never silently drifts to
    the next free port. Refuses a second instance when a live pid is
    recorded (printing the running URL + pid), self-heals a stale
    recorded pid, and identifies a foreign port holder via /proc.
    `--force` (``force=True``) stops only the instance recorded in our
    own runtime state; it never kills a process it does not own.

    Parameters
    ----------
    package : str
        Short package/CLI name (used for the runtime-state path and
        the printed remedy commands).
    project_dir : str
        Project directory recorded in the runtime state (informational).
    port, host : the address to bind.
    force : bool
        Stop a previous instance of OUR OWN recorded server, then serve.
    run_server : Callable[[], None]
        Zero-arg callable that BLOCKS running the actual dev server
        (e.g. ``functools.partial(run_standalone, app_module=..., port=port)``).
    state_path : optional
        Overrides the resolved runtime-state path -- real dependency
        injection for tests/callers with a custom scope.

    Returns
    -------
    int
        Process exit code: 0 on clean shutdown, 1 on refusal.
    """
    import click

    resolved_state_path = state_path if state_path is not None else _gr.state_path(package)
    current = _gr.status(resolved_state_path)
    if current.get("running"):
        if not force:
            click.echo(
                f"Error: {package} GUI already running at {current['url']} "
                f"(pid {current['pid']}).\n"
                "\nFix it with one of:\n"
                f"  open {current['url']}\n"
                f"  {package} gui --force            # stop it and serve here",
                err=True,
            )
            return 1
        click.echo(f"Stopping the GUI at {current['url']} (pid {current['pid']}).")
        _gr.stop(resolved_state_path)
    if not _port_is_free(host, port):
        click.echo(_port_taken_message(package, host, port), err=True)
        return 1
    _gr.write_state(os.getpid(), port, host, str(project_dir), resolved_state_path)
    try:
        run_server()
    finally:
        _gr.clear_state(resolved_state_path)
    return 0


__all__ = [
    "run_standalone",
    "ScitexAppConfig",
    "scitex_api_dispatch",
    "scitex_editor_page",
    "scitex_urlpatterns",
    "serve_gui",
    "gui_status",
    "gui_stop",
    "gui_port_holder",
]

# EOF
