#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Where an app's auth material lives, and in what order it is looked for.

    <project>/.scitex/<app>/auth/     checked FIRST
    ~/.scitex/<app>/auth/             fallback

The project-first rule is the operator's ("あとは、<project-dir>/.scitex/cards/auth/
を優先にする、というのも筋が通りますよね？"). It is the same precedence the
store already uses, so an app author learns ONE resolution rule rather than
two, and a project can carry its own invited users without touching the
machine-wide set.

WHY THERE IS NO /etc EQUIVALENT. sshd reads /etc/ssh/sshd_config because it is a
system daemon serving every OS user, so its policy cannot live in any one user's
home. A SciTeX app is not that: it serves its owner and the people they invite.
The operator called a /etc layer やりすぎ and he is right — a third tier that no
app ever writes to is a tier that goes stale and misleads.

NAMING, kept parallel to ssh so the two transfer:

    ssh_config   -> <app>_config     the CLIENT side: which identity to present
    sshd_config  -> <app>d_config    the SERVER side: which methods to accept

so an app named ``cards`` gets ``cards_config`` and ``cardsd_config``. The
trailing ``d`` means daemon in both systems, which is the point.
"""

from __future__ import annotations

import os
from pathlib import Path

__all__ = [
    "AUTH_DIR_ENV_TEMPLATE",
    "auth_dir_candidates",
    "client_config_path",
    "resolve_auth_dir",
    "server_config_path",
    "user_dir",
]

#: ``-F configfile`` is ssh's escape hatch for "use this file, not the usual
#: one", and every non-trivial deployment eventually needs one. An env var is
#: the form that survives a process launched by systemd, which is how these
#: boards actually run.
AUTH_DIR_ENV_TEMPLATE = "SCITEX_{app_upper}_AUTH_DIR"


def _env_override(app: str) -> Path | None:
    name = AUTH_DIR_ENV_TEMPLATE.format(app_upper=app.upper().replace("-", "_"))
    raw = os.environ.get(name)
    return Path(raw).expanduser() if raw else None


def auth_dir_candidates(app: str, project_dir: Path | None = None) -> list[Path]:
    """Every directory that could hold ``app``'s auth material, best first.

    Returned even when they do not exist, because "which paths did you look at"
    is the first question anyone asks when auth does not behave, and an error
    that cannot answer it sends the reader guessing. ``ssh -v`` prints exactly
    this list for the same reason.
    """
    override = _env_override(app)
    if override is not None:
        # An explicit override is the ONLY candidate. Falling back past it would
        # mean the operator asked for one file and got another, silently.
        return [override]

    candidates: list[Path] = []
    if project_dir is not None:
        candidates.append(Path(project_dir) / ".scitex" / app / "auth")
    candidates.append(Path.home() / ".scitex" / app / "auth")
    return candidates


def resolve_auth_dir(app: str, project_dir: Path | None = None) -> Path | None:
    """First candidate that exists, or ``None`` when the app has no auth set up.

    ``None`` is a real answer and not an error: an app with no auth directory is
    an app nobody has configured yet, which is a state the caller must handle
    deliberately (refuse? run open on loopback?) rather than one this function
    should decide by raising.
    """
    for candidate in auth_dir_candidates(app, project_dir):
        if candidate.is_dir():
            return candidate
    return None


def server_config_path(auth_dir: Path, app: str) -> Path:
    """``<auth_dir>/<app>d_config`` — the sshd_config analogue."""
    return auth_dir / f"{app}d_config"


def client_config_path(auth_dir: Path, app: str) -> Path:
    """``<auth_dir>/<app>_config`` — the ssh_config analogue."""
    return auth_dir / f"{app}_config"


def user_dir(auth_dir: Path, username: str) -> Path:
    """``<auth_dir>/users/<username>/``.

    IDENTITY IS THIS DIRECTORY'S NAME, which is the single most important thing
    copied from ssh. sshd never had to ask "whose key is this line?" because
    authorized_keys lives inside the target user's home — identity is LOCATION,
    not a field to be parsed and trusted. Every scheme that stores identity as a
    column beside the credential eventually reads the wrong column.
    """
    return auth_dir / "users" / username


# EOF
