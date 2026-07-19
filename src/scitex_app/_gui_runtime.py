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
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Union

PathLike = Union[str, Path]

_STATE_FIELDS = ("pid", "port", "host", "project", "started_at")

#: Declared ``PortHolder.status`` values. Nothing else is ever set.
HOLDER_FREE = "free"
HOLDER_IDENTIFIED = "identified"
HOLDER_UNREADABLE = "unreadable"


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


def _argv_of(pid: int) -> tuple[str, ...]:
    """Full argv of ``pid`` from /proc/<pid>/cmdline; empty when unreadable."""
    try:
        raw = Path(f"/proc/{pid}/cmdline").read_bytes()
    except OSError:
        return ()
    return tuple(part for part in raw.decode("utf-8", "replace").split("\0") if part)


def _normalize(text: str) -> str:
    """Lowercase ``text`` with every non-alphanumeric run collapsed to ``_``.

    Bracketed by ``_`` so a token test is a whole-token test: it makes
    ``scitex_writer`` match ``scitex-writer`` and
    ``/opt/venv/scitex_writer/__main__.py``, while ``myscitex_writerx``
    correctly does NOT match.
    """
    return "_" + re.sub(r"[^A-Za-z0-9]+", "_", text).strip("_").lower() + "_"


def argv_is_ours(argv: tuple[str, ...], package: str) -> bool:
    """True when ``argv`` proves the process is an instance of ``package``.

    Ownership is proven from the ARGV, never from the process NAME: a
    ``comm`` of "python" names nothing, and every Python server on the
    box shares it -- killing on that basis would kill strangers. The
    argv, by contrast, carries the module or console-script that was
    actually run.
    """
    token = _normalize(package)
    return any(token in _normalize(arg) for arg in argv)


@dataclass(frozen=True)
class PortHolder:
    """Who is LISTENing on a port -- one shape, every signal three-valued.

    ``status`` is always one of the declared ``HOLDER_*`` constants, so
    a caller never has to guess which keys exist on this call.
    ``ours`` is deliberately ``True`` / ``False`` / ``None`` (unknown):
    collapsing "we could not look" into "someone else's" is how a
    diagnostic module ships a confident wrong answer.
    """

    port: int
    status: str
    pid: Optional[int] = None
    name: Optional[str] = None
    argv: tuple[str, ...] = ()
    ours: Optional[bool] = None

    def __post_init__(self) -> None:
        if self.status not in (HOLDER_FREE, HOLDER_IDENTIFIED, HOLDER_UNREADABLE):
            raise ValueError(f"unknown PortHolder.status: {self.status!r}")
        if self.status == HOLDER_IDENTIFIED and self.pid is None:
            raise ValueError("PortHolder.status='identified' requires a pid")
        if self.status != HOLDER_IDENTIFIED and self.pid is not None:
            raise ValueError(f"PortHolder.status={self.status!r} must not carry a pid")
        if self.status != HOLDER_IDENTIFIED and self.ours is not None:
            raise ValueError(f"PortHolder.status={self.status!r} cannot know 'ours'")

    @property
    def in_use(self) -> bool:
        """True when something holds the port, identified or not."""
        return self.status != HOLDER_FREE


def port_holder(port: int, package: Optional[str] = None) -> PortHolder:
    """Identify the process LISTENing on ``port``.

    Reads /proc directly rather than shelling out to ``ss``/``lsof``,
    which are absent from many containers -- a hint that silently
    disappears in the exact minimal environment where it is needed
    most is not a hint.

    When ``package`` is given, ``ours`` reports whether the holder's
    argv proves it is an instance of that package (see
    :func:`argv_is_ours`) -- the only evidence on which a caller may
    terminate it.

    Returns ``status=HOLDER_UNREADABLE`` when the port IS held but no
    pid could be attributed. That is genuinely ambiguous -- another
    user's process, or (routinely, inside our agent containers)
    /proc/<pid>/fd denying us even for a process we own. Reporting it
    as "another user's" would be a guess stated as a fact.
    """
    inodes = _listening_socket_inodes(port)
    if not inodes:
        return PortHolder(port=port, status=HOLDER_FREE)
    for proc_dir in Path("/proc").iterdir():
        if not proc_dir.name.isdigit():
            continue
        try:
            fds = list((proc_dir / "fd").iterdir())
        except OSError:
            continue  # denied / vanished -- keep scanning
        for fd in fds:
            try:
                target = os.readlink(fd)
            except OSError:
                continue
            if not target.startswith("socket:[") or target[8:-1] not in inodes:
                continue
            pid = int(proc_dir.name)
            try:
                name = (proc_dir / "comm").read_text().strip()
            except OSError:
                name = None
            argv = _argv_of(pid)
            return PortHolder(
                port=port,
                status=HOLDER_IDENTIFIED,
                pid=pid,
                name=name,
                argv=argv,
                ours=argv_is_ours(argv, package) if package and argv else None,
            )
    return PortHolder(port=port, status=HOLDER_UNREADABLE)


def terminate(pid: int, timeout: float = 5.0) -> dict:
    """SIGTERM ``pid`` and wait for it to die. Reports what actually happened."""
    if not pid_alive(pid):
        return {"signalled": False, "terminated": True, "pid": pid}
    try:
        os.kill(pid, signal.SIGTERM)
    except OSError as exc:
        return {"signalled": False, "terminated": False, "pid": pid, "error": str(exc)}
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline and pid_alive(pid):
        time.sleep(0.1)
    return {"signalled": True, "terminated": not pid_alive(pid), "pid": pid}


def stop(path: PathLike, timeout: float = 5.0) -> dict:
    """SIGTERM the recorded server and clear the state file. Idempotent."""
    current = status(path)
    if not current.get("running"):
        return {"stopped": False, "running": False}
    pid = current["pid"]
    result = terminate(pid, timeout=timeout)
    if not result["signalled"] and "error" in result:
        return {"stopped": False, "running": True, "pid": pid, "error": result["error"]}
    clear_state(path)
    return {"stopped": True, "pid": pid, "terminated": result["terminated"]}


# EOF
