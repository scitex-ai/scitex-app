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


class UnsafeUsername(ValueError):
    """A username that is not a single literal directory name.

    NOT a failed login. A login outcome says something about the credential; this
    says the request was malformed before any credential was consulted. Raising
    is safe here precisely because it leaks nothing: a rejected separator tells
    an attacker only that separators are rejected, never which users exist. The
    user-enumeration caution that makes :func:`load_identity` return ``None`` for
    an unknown user does not apply.
    """


def validate_username(username: str) -> str:
    """Return ``username`` iff it is ONE literal path component. Else raise.

    THE WHOLE SECURITY PROPERTY OF THIS PACKAGE RESTS ON THIS FUNCTION, and it
    was missing until 2026-08-02. Identity-as-location only deletes a bug class
    while the LOCATION is one the server chose. Without this, the client chose
    it, and the design's central claim inverted into its central hole.

    MEASURED against the unfixed code, StrictModes ON (the default)::

        CONTROL   'alice'                     -> accepted=True  user='alice'
        TRAVERSAL '../../../../../outside'    -> accepted=True  user='../../../../../outside'
        ABSOLUTE  '/tmp/…/outside'            -> accepted=True  user='/tmp/…/outside'
        KEY AUTH  via the same escape         -> accepted=True

    TWO SEPARATE ESCAPES, and the second is the one people forget::

        Path('/a/users') / '../../x'  ->  climbs out
        Path('/a/users') / '/tmp/x'   ->  Path('/tmp/x')

    pathlib DISCARDS the left operand when the right is absolute. No ``..`` is
    needed and no string inspection of the joined path would reveal it.

    WHY StrictModes CANNOT CATCH THIS, which is the part worth sitting with: it
    checks the owner and mode of whatever directory it is handed. A target owned
    by this uid at 0700 holding a 0600 credential passes every check — because
    those are the CORRECT permissions. The guard is not broken; it is being
    asked about the wrong directory, so it will never alert.

    AND IT INVERTS THIS PACKAGE'S OWN PROMISE. ``_users`` states that nothing
    reads ``~/.ssh`` and that "there is no flag for this and there should not be
    one". A username of ``../../../../.ssh`` reaches ``~/.ssh/authorized_keys``
    and passes StrictModes CLEANLY — ~/.ssh is 0700 and authorized_keys is 0600,
    exactly the permissions ssh itself demands. The promise was not merely
    unenforced; the username field was the flag that should not exist.

    Found by scitex-app on review, with a working exploit; reproduced here
    before fixing. Every fixture in the original 87 tests used a well-formed
    username, so nothing exercised the one input an attacker controls — the same
    failure mode as the hand-typed key fixture that hid the undecodable-key bug.
    """
    if not isinstance(username, str) or not username:
        raise UnsafeUsername("username must be a non-empty string")
    # Built rather than written literally: a NUL in source is itself a hazard,
    # and tooling that scans for one should not find it here.
    if chr(0) in username:
        raise UnsafeUsername("username must not contain a NUL byte")
    if username in (os.curdir, os.pardir):
        raise UnsafeUsername(
            f"username {username!r} is a directory-navigation name, not a user"
        )
    separators = {os.sep, os.altsep, "/", "\\"} - {None}
    for sep in separators:
        if sep in username:
            raise UnsafeUsername(
                f"username {username!r} contains a path separator {sep!r}; "
                "a username is ONE directory name, never a path"
            )
    if Path(username).is_absolute():
        # Belt to the separator braces: on some platforms an absolute form can
        # exist without a separator this loop matched (e.g. a drive-relative
        # 'C:name'). Cheap, and the failure it guards is total.
        raise UnsafeUsername(f"username {username!r} is an absolute path")
    return username


def user_dir(auth_dir: Path, username: str) -> Path:
    """``<auth_dir>/users/<username>/``, or raise :class:`UnsafeUsername`.

    IDENTITY IS THIS DIRECTORY'S NAME, which is the single most important thing
    copied from ssh. sshd never had to ask "whose key is this line?" because
    authorized_keys lives inside the target user's home — identity is LOCATION,
    not a field to be parsed and trusted. Every scheme that stores identity as a
    column beside the credential eventually reads the wrong column.

    That argument holds ONLY while the server chooses the location, which is why
    :func:`validate_username` runs first and why containment is re-checked after
    resolution: a validated name can still be a SYMLINK pointing anywhere, and
    ``..``-freedom is a property of the resolved path, not of the string.
    """
    validate_username(username)
    users_root = auth_dir / "users"
    candidate = users_root / username

    # CONTAINMENT AFTER RESOLUTION, because the string check alone cannot see a
    # symlink. Only resolve when the path exists: resolve() on a missing path is
    # fine, but comparing a non-existent resolved path against a resolved root
    # is still the correct test, so this runs unconditionally with strict=False.
    resolved = candidate.resolve()
    root = users_root.resolve()
    if resolved != root and root not in resolved.parents:
        raise UnsafeUsername(
            f"username {username!r} resolves to {resolved}, which is outside "
            f"{root} — a user directory must live under users/"
        )
    return candidate


# EOF
