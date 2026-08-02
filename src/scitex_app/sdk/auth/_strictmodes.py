#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""StrictModes — refuse credentials whose file permissions make them worthless.

ssh's rule, and it is a REFUSAL rather than a warning. That choice is the whole
value of the feature: a warning on a daemon that started successfully is read by
nobody, and a credential file left group-readable is silently exploitable for as
long as it takes anyone to notice. A refusal is loud, and it is fixed by one
chmod. The asymmetry is entirely one-sided, which is why ssh defaults it on and
why this does too.

TWO RULES, NOT ONE, and the difference is not an oversight in ssh — it follows
from what the file holds:

    SECRET   (a private key; here, ``password``)
             must not be group/other READABLE or writable.
             ssh: "Permissions 0644 for 'id_rsa' are too open."
             Reading it is the attack. 0600.

    PUBLIC   (``authorized_keys``, which holds public keys)
             must not be group/other WRITABLE. Reading it harms nobody —
             the keys in it are public by construction. WRITING it is the
             attack, because appending one line grants access.
             ssh permits 0644 here, and so does this.

Copying that distinction rather than flattening both to 0600 is the difference
between imitating ssh and imitating a screenshot of ssh. Flattening would also
teach app authors a rule that is wrong (that public keys are secret), and a
security primitive that teaches a wrong model does damage past its own scope.

OWNERSHIP is checked too, for the reason sshd checks it: permission bits on a
file someone else owns are theirs to change at any moment, so a 0600 file owned
by another uid offers no guarantee at all.
"""

from __future__ import annotations

import os
import stat
from dataclasses import dataclass
from pathlib import Path

__all__ = [
    "GROUP_OTHER_READ",
    "GROUP_OTHER_WRITE",
    "StrictModesError",
    "check_public_file",
    "check_secret_file",
    "check_directory",
]

#: The bits each rule forbids. Named, because ``0o077`` at a call site is a
#: number the next reader has to decode, and decoding it wrongly is silent.
GROUP_OTHER_READ = stat.S_IRGRP | stat.S_IROTH
GROUP_OTHER_WRITE = stat.S_IWGRP | stat.S_IWOTH


@dataclass(frozen=True)
class StrictModesError(PermissionError):
    """A credential this process refuses to use, and the one command that fixes it.

    Subclasses PermissionError so a caller that only wants "auth material was
    unusable" can catch the stdlib type, while a caller that wants to render the
    remedy gets the fields.
    """

    path: Path
    mode: int
    problem: str
    remedy: str

    def __str__(self) -> str:  # pragma: no cover - formatting only
        return (
            f"Permissions {self.mode:04o} for {str(self.path)!r} are too open.\n"
            f"  {self.problem}\n"
            f"  fix: {self.remedy}"
        )


def _mode_of(path: Path) -> int:
    return stat.S_IMODE(path.lstat().st_mode)


def _refuse_if_not_ours(path: Path) -> None:
    """Ownership first: bits on someone else's file are theirs to change."""
    owner = path.lstat().st_uid
    if owner != os.getuid():
        raise StrictModesError(
            path=path,
            mode=_mode_of(path),
            problem=(
                f"owned by uid {owner}, but this process runs as uid {os.getuid()}. "
                "Its permission bits can be changed by that owner at any time, so "
                "they guarantee nothing here"
            ),
            remedy=f"chown {os.getuid()} {path}",
        )


def check_secret_file(path: Path) -> None:
    """Refuse a secret readable or writable by anyone but its owner.

    The password-hash file. A hash is not a plaintext password, but it is an
    offline-cracking target, so the rule is a private key's rule.
    """
    _refuse_if_not_ours(path)
    mode = _mode_of(path)
    offending = mode & (GROUP_OTHER_READ | GROUP_OTHER_WRITE)
    if offending:
        raise StrictModesError(
            path=path,
            mode=mode,
            problem=("this file holds a secret and must not be accessible by others"),
            remedy=f"chmod 600 {path}",
        )


def check_public_file(path: Path) -> None:
    """Refuse a public file that others can WRITE. Readable is fine, by design.

    ``authorized_keys`` holds public keys. Reading them grants nothing. Appending
    one line grants access, so writability is the whole risk and readability is
    none of it.
    """
    _refuse_if_not_ours(path)
    mode = _mode_of(path)
    if mode & GROUP_OTHER_WRITE:
        raise StrictModesError(
            path=path,
            mode=mode,
            problem=(
                "others can write to it, and appending one line to this file "
                "grants access"
            ),
            remedy=f"chmod go-w {path}",
        )


def check_directory(path: Path) -> None:
    """Refuse a directory others can write into.

    A writable directory defeats every check on the files inside it: whoever can
    write the directory can replace ``authorized_keys`` wholesale, whatever its
    own mode says. sshd walks the whole chain for this reason.
    """
    if path.is_symlink():
        # A SYMLINK, DIAGNOSED AS ONE. Without this branch the outcome was still
        # SAFE but the message was unusable: _mode_of uses lstat(), a symlink's
        # own mode is 0777, so it tripped the group/other-writable test and the
        # remedy read "chmod 700 <path>" — and chmod on a symlink does nothing on
        # Linux. An operator following that exactly would watch it fail and have
        # no next step.
        #
        # Found by scitex-app, who noted the outcome was safe for an INCIDENTAL
        # reason. That is worth fixing on its own terms: a refusal whose stated
        # remedy cannot work is a refusal the reader cannot act on, and this
        # package's whole position on error text is that naming the fix is half
        # the message.
        raise StrictModesError(
            path=path,
            mode=_mode_of(path),
            problem=(
                "this is a SYMLINK, not a directory. Its own permission bits are "
                "0777 by construction and cannot be changed, so no chmod here "
                "can satisfy StrictModes"
            ),
            remedy=(
                f"rm {path} and make it a real directory (mkdir -p {path} && "
                f"chmod 700 {path}), or point the user at the real location by "
                "name instead of aliasing it"
            ),
        )
    _refuse_if_not_ours(path)
    mode = _mode_of(path)
    if mode & GROUP_OTHER_WRITE:
        raise StrictModesError(
            path=path,
            mode=mode,
            problem=(
                "others can write into this directory, so they can replace the "
                "credential files inside it regardless of those files' own modes"
            ),
            remedy=f"chmod 700 {path}",
        )


# EOF
