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
        MOUNT_META_NAME,
        MountPrefixMismatch,
        ScitexAppConfig,
        mount_prefix,
        scitex_api_dispatch,
        scitex_editor_page,
        scitex_urlpatterns,
    )
except ImportError:
    # _django requires Django; keep embed importable for consumers that
    # only need the standalone launcher (which lazy-imports Django itself).
    MOUNT_META_NAME = "stx-mount"  # the name is a contract, not Django's
    MountPrefixMismatch = None  # type: ignore[assignment]
    ScitexAppConfig = None  # type: ignore[assignment]
    mount_prefix = None  # type: ignore[assignment]
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


def gui_port_holder(port: int, package: Optional[str] = None) -> "_gr.PortHolder":
    """Identify the process LISTENing on `port` (via /proc, no `ss`/`lsof`).

    Pass `package` to have the result report whether the holder is an
    instance of OUR OWN app (proven from its argv).
    """
    return _gr.port_holder(port, package)


def _port_is_free(host: str, port: int) -> bool:
    """True when `host:port` can be bound right now."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        try:
            sock.bind((host, port))
        except OSError:
            return False
    return True


def _port_taken_message(package: str, host: str, holder: "_gr.PortHolder") -> str:
    """Explain who holds the port and give paste-ready commands to fix it.

    Every remedy offered here must actually work for the case that
    printed it. `--force` is offered only when the holder is provably
    our own app -- the one case where `serve_gui` will act on it.
    Naming a flag that then refuses is the same bug as an install hint
    that installs nothing.
    """
    port = holder.port
    lines = [f"Error: port {port} is already in use on {host}."]
    if holder.status == _gr.HOLDER_UNREADABLE:
        lines += [
            "Held by: unknown -- something is listening, but this process is not",
            "  allowed to read /proc/<pid>/fd, so the holder cannot be identified.",
            "  (Routine inside our agent containers, even for a process we own.)",
        ]
    elif holder.ours:
        lines.append(
            f"Held by: an orphaned {package} GUI (pid {holder.pid}) "
            "that never cleared its state file."
        )
    else:
        lines.append(f"Held by: {holder.name or '?'} (pid {holder.pid}) -- not a {package} GUI.")
        lines.append(f"  argv: {' '.join(holder.argv) if holder.argv else 'unreadable'}")
    lines += ["", "Fix it with one of:"]
    if holder.ours:
        lines.append(f"  {package} gui --force            # reclaim the orphan and serve here")
    lines.append(f"  {package} gui --port {port + 1}   # serve on a free port")
    if holder.pid is not None and not holder.ours:
        lines.append(f"  kill {holder.pid}{' ' * 26}# stop it yourself, then serve again")
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

    `--force` (``force=True``) stops the instance recorded in our own
    runtime state AND reclaims an ORPHANED instance of our own -- one
    holding the port after dying without clearing its state file,
    which is invisible to ``status()`` and is the very case the flag
    exists for. It never touches a process it cannot prove is ours,
    and ownership is proven from the holder's argv, not its name.

    Parameters
    ----------
    package : str
        Short package/CLI name (used for the runtime-state path and
        the printed remedy commands).
    project_dir : str
        Project directory recorded in the runtime state (informational).
    port, host : the address to bind.
    force : bool
        Stop a previous instance of OUR OWN server -- recorded or
        orphaned -- then serve.
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
        holder = _gr.port_holder(port, package)
        # An orphan of ours -- it died without clearing its state file, so
        # status() above could not see it. This is exactly what --force is
        # for, and refusing here would make the flag a lie.
        if force and holder.ours:
            click.echo(f"Reclaiming port {port} from an orphaned {package} GUI (pid {holder.pid}).")
            result = _gr.terminate(holder.pid)
            if not result["terminated"]:
                click.echo(
                    f"Error: could not stop pid {holder.pid}"
                    f"{': ' + result['error'] if result.get('error') else ' (still alive)'}.\n"
                    f"\nFix it with one of:\n"
                    f"  kill -9 {holder.pid}\n"
                    f"  {package} gui --port {port + 1}",
                    err=True,
                )
                return 1
        if not _port_is_free(host, port):
            click.echo(_port_taken_message(package, host, holder), err=True)
            return 1
    _gr.write_state(os.getpid(), port, host, str(project_dir), resolved_state_path)
    try:
        run_server()
    finally:
        _gr.clear_state(resolved_state_path)
    return 0


__all__ = [
    "run_standalone",
    "MOUNT_META_NAME",
    "MountPrefixMismatch",
    "mount_prefix",
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
