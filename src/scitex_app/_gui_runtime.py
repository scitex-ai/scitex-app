#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# File: scitex_app/_gui_runtime.py

"""Shared runtime state for scaffolded apps' standalone GUI launcher.

Generalizes scitex-writer's `gui serve/status/stop` runtime module
(scitex-writer PR #316) so every SciTeX app built on scitex_app.embed
gets the same safe launcher instead of re-copying it: bind the fixed
port or fail loud, refuse a second instance when a live pid is
recorded, self-heal stale state when the recorded pid is dead, and
identify a foreign port holder via /proc (no `ss`/`lsof` shell-out,
which are absent from minimal containers).

State lives at ``<scope>/.scitex/<package>/runtime/gui.json`` per the
fleet runtime-state-db layout (scitex-dev skill
``general/01_ecosystem/13_runtime-state-db-layout.md``), keyed by the
caller's own package name so multiple apps running locally do not
collide.

Pure state logic only -- no Click, no Django. Each consumer's CLI
layer owns argument parsing and process spawning.
"""

from __future__ import annotations

import json
import os
import re
import signal
import time
from pathlib import Path
from typing import Optional, Union

PathLike = Union[str, Path]

_STATE_FIELDS = ("pid", "port", "host", "project", "started_at")


def state_path_env_var(package: str) -> str:
    """Return the env-var name that overrides `package`'s state path.

    ``SCITEX_<PACKAGE>_GUI_STATE`` (package name uppercased, non-alnum
    chars -> ``_``) -- matches scitex-writer's pre-existing
    ``SCITEX_WRITER_GUI_STATE`` convention.
    """
    return "SCITEX_" + re.sub(r"[^A-Za-z0-9]", "_", package).upper() + "_GUI_STATE"


def state_path(package: str) -> Path:
    """Resolve the GUI state-file path for `package`.

    ``SCITEX_<PACKAGE>_GUI_STATE`` overrides the resolved path -- the
    only channel available to subprocess-driven end-to-end CLI tests
    (``python -m mypkg gui serve`` in a subprocess), which cannot
    inject a path via function arguments across a process boundary.
    This repo bans mocks/monkeypatch (PA-306), so this env var is what
    makes ``gui serve``'s real CLI path testable without writing to the
    developer's actual runtime state. Falls back to the fleet
    local-state convention (scitex_config.local_state.runtime_path)
    when unset.
    """
    override = os.environ.get(state_path_env_var(package))
    if override:
        return Path(override)

    from scitex_config._ecosystem import local_state

    return Path(local_state.runtime_path(package, "gui.json"))


def read_state(path: PathLike) -> Optional[dict]:
    """Return the persisted state dict, or None when absent/corrupt."""
    p = Path(path)
    try:
        loaded = json.loads(p.read_text())
    except (OSError, ValueError):
        return None
    return loaded if isinstance(loaded, dict) else None


def write_state(
    pid: int,
    port: int,
    host: str,
    project: str,
    path: PathLike,
) -> Path:
    """Persist the running server's coordinates; returns the state-file path."""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    state = {
        "pid": pid,
        "port": port,
        "host": host,
        "project": project,
        "started_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
    }
    p.write_text(json.dumps(state, indent=2))
    return p


def clear_state(path: PathLike) -> None:
    """Remove the state file. Idempotent."""
    p = Path(path)
    try:
        p.unlink()
    except OSError:
        pass


def pid_alive(pid: int) -> bool:
    """True when ``pid`` refers to a live process we could signal.

    A zombie still answers signal 0 but is already dead -- without this
    check ``stop()`` would poll an exited-but-unreaped server for the
    full timeout and report ``terminated=False``.
    """
    if not isinstance(pid, int) or pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    try:
        stat = Path(f"/proc/{pid}/stat").read_text()
        if stat.rpartition(")")[2].split()[0] == "Z":
            return False
    except (OSError, IndexError):
        pass
    return True


def status(path: PathLike) -> dict:
    """Report the server's state, self-healing a stale file.

    A state file whose pid is dead (crash, kill -9) is removed so the
    next launch auto-serves instead of pointing at a dead port.
    """
    state = read_state(path)
    if state is None:
        return {"running": False}
    if not pid_alive(state.get("pid", -1)):
        clear_state(path)
        return {"running": False, "stale_state_cleared": True}
    url = f"http://{state.get('host')}:{state.get('port')}"
    return {"running": True, "url": url, **{k: state.get(k) for k in _STATE_FIELDS}}


def _listening_socket_inodes(port: int) -> set[str]:
    """Socket inodes of every process LISTENing on ``port``, from /proc/net."""
    inodes: set[str] = set()
    for proc_net in ("/proc/net/tcp", "/proc/net/tcp6"):
        try:
            lines = Path(proc_net).read_text().splitlines()[1:]
        except OSError:
            continue
        for line in lines:
            fields = line.split()
            if len(fields) < 10:
                continue
            # local_address is "HEXADDR:HEXPORT"; state 0A == TCP_LISTEN.
            _, _, hex_port = fields[1].rpartition(":")
            if fields[3] != "0A" or int(hex_port, 16) != port:
                continue
            inodes.add(fields[9])
    return inodes


def port_holder(port: int) -> Optional[dict]:
    """Identify the process LISTENing on ``port``: ``{pid, name}``, or None.

    Reads /proc directly rather than shelling out to ``ss``/``lsof``,
    which are absent from many containers -- a hint that silently
    disappears in the exact minimal environment where it is needed
    most is not a hint.

    Only processes the caller can see are reported: an inode we cannot
    map to a pid (another user's process) yields ``{pid: None}``, so
    the caller says "another process" rather than inventing a wrong one.
    """
    inodes = _listening_socket_inodes(port)
    if not inodes:
        return None
    for proc_dir in Path("/proc").iterdir():
        if not proc_dir.name.isdigit():
            continue
        try:
            fds = list((proc_dir / "fd").iterdir())
        except OSError:
            continue  # not ours / vanished -- keep scanning
        for fd in fds:
            try:
                target = os.readlink(fd)
            except OSError:
                continue
            if target[8:-1] not in inodes or not target.startswith("socket:["):
                continue
            try:
                name = (proc_dir / "comm").read_text().strip()
            except OSError:
                name = "?"
            return {"pid": int(proc_dir.name), "name": name}
    return {"pid": None, "name": None}


def stop(path: PathLike, timeout: float = 5.0) -> dict:
    """SIGTERM the recorded server and clear the state file. Idempotent."""
    current = status(path)
    if not current.get("running"):
        return {"stopped": False, "running": False}
    pid = current["pid"]
    try:
        os.kill(pid, signal.SIGTERM)
    except OSError as exc:
        return {"stopped": False, "running": True, "pid": pid, "error": str(exc)}
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline and pid_alive(pid):
        time.sleep(0.1)
    clear_state(path)
    return {"stopped": True, "pid": pid, "terminated": not pid_alive(pid)}


# EOF
