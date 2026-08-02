#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Identities, and the credentials filed under each one.

    auth/users/<name>/authorized_keys      public keys, ssh format, one per line
    auth/users/<name>/password             one PHC hash

IDENTITY IS THE DIRECTORY NAME. This is the single most important thing taken
from ssh, and it is worth stating why rather than treating it as filing.

A board that authenticates with one shared password cannot answer "who did
this?" — it only knows that SOMEBODY knew the secret. The fix people reach for
is to add a username field beside the credential, and that is where the bugs
start: now there are two things (the claimed name, the credential) and a
question about whether they agree, and every such scheme eventually trusts the
claim without checking the pairing. The board this SDK was extracted from had
exactly that bug — it split the Basic-auth header on the colon and compared only
the password half, discarding the username entirely.

sshd never had that problem, and not because it was more careful: because
``authorized_keys`` lives INSIDE the target user's home. The credential's
LOCATION is the identity claim. There is no second field to disagree with, and
no pairing to get wrong. Copying that is not stylistic fidelity; it deletes a
category of bug rather than defending against it.

WHAT IS DELIBERATELY ABSENT: any code that reads ``~/.ssh``. The operator ruled
on this before it could be built — "貼れるのはよくても勝手に貼らないでくださいね、
ユーザがびっくりしますから". A user may certainly paste a key they already have;
nothing may paste it FOR them. Granting access is an act that belongs to the
person granting it, and a tool that performs it silently has taken that act
away from them. There is no flag for this and there should not be one.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from ._config import AuthConfig
from ._paths import user_dir
from ._strictmodes import check_directory, check_public_file, check_secret_file

__all__ = [
    "PASSWORD_FILE",
    "Identity",
    "list_identities",
    "load_identity",
    "parse_authorized_keys",
]

#: Named rather than inlined so the one place it is spelled is greppable. The
#: authorized-keys filename is configurable (``AuthorizedKeysFile``); this is
#: not, because a password file whose name varies is a password file somebody
#: eventually fails to find.
PASSWORD_FILE = "password"


@dataclass(frozen=True)
class PublicKey:
    """One line of an ``authorized_keys`` file, in ssh's own shape.

    ``comment`` is the trailing free text — usually ``user@host`` — and it is
    kept because it is how a human tells two of their own keys apart when
    deciding which to revoke. Dropping it would make the file unreadable to the
    person who has to maintain it.
    """

    algorithm: str
    material: str
    comment: str = ""

    @property
    def line(self) -> str:
        """Re-render as ssh would write it."""
        return " ".join(x for x in (self.algorithm, self.material, self.comment) if x)


@dataclass(frozen=True)
class Identity:
    """One subject: the directory name, plus whatever credentials it holds.

    Both credential kinds are OPTIONAL and independently so. A user with only a
    key cannot use a password, and vice versa — which is ssh's behaviour and
    also the honest model, since the two are separate grants.
    """

    name: str
    directory: Path
    keys: tuple[PublicKey, ...] = field(default_factory=tuple)
    password_hash: str | None = None

    @property
    def has_key(self) -> bool:
        return bool(self.keys)

    @property
    def has_password(self) -> bool:
        return self.password_hash is not None


def _decodes_as_key_blob(material: str) -> bool:
    """True when ``material`` is the base64 of an SSH key blob.

    ``validate=True`` matters: without it base64 silently DISCARDS characters
    outside the alphabet, so a corrupted line would decode to something shorter
    and pass. The point of this check is to reject, so a decoder that quietly
    repairs its input defeats it.
    """
    import base64  # noqa: PLC0415 -- only needed while parsing

    try:
        blob = base64.b64decode(material.encode("ascii"), validate=True)
    except Exception:  # noqa: BLE001 -- every decode failure means the same thing
        return False
    # An SSH blob starts with a 4-byte big-endian length followed by the
    # algorithm name, so anything shorter than that header cannot be one.
    return len(blob) > 4


def parse_authorized_keys(text: str) -> tuple[PublicKey, ...]:
    """Parse ssh's ``authorized_keys`` format: ``<algorithm> <base64> [comment]``.

    Blank lines and ``#`` comments are skipped, as ssh does. A line that cannot
    be parsed is SKIPPED rather than fatal — deliberately unlike the config
    parser, and the asymmetry is the point:

      - a malformed CONFIG line means the operator's stated policy is not the
        running policy, so refusing is the only honest response;
      - a malformed KEY line grants nothing. Refusing the whole file would let
        one bad line revoke every other user's working key, turning a typo into
        an outage. ssh skips, and ``-vvv`` is how you find out why.

    Option prefixes (``command=""``, ``from=""``) are not supported yet. They are
    silently absent rather than silently ignored: such a line does not parse as
    ``<algorithm> <base64>`` and is skipped, so a restriction someone wrote can
    never be quietly dropped while the key it guards stays live.
    """
    keys: list[PublicKey] = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split(None, 2)
        if len(parts) < 2:
            continue
        algorithm, material = parts[0], parts[1]
        if not algorithm.startswith(("ssh-", "ecdsa-", "sk-")):
            # Not a bare key line — most likely an options prefix. Skipping is
            # what keeps an unsupported restriction from being dropped.
            continue
        if not _decodes_as_key_blob(material):
            # A key whose material is not valid base64 is not a key, and letting
            # it through is worse than useless in two ways. It would still MATCH,
            # because matching compares strings — so a corrupted line keeps
            # granting access. And its fingerprint degrades to "<unparseable>",
            # so the trace can no longer say WHICH key was used, which is the
            # one thing the trace exists for. Found by my own end-to-end run,
            # where a malformed test fixture authenticated successfully and
            # logged a fingerprint naming nothing.
            continue
        keys.append(
            PublicKey(
                algorithm=algorithm,
                material=material,
                comment=parts[2] if len(parts) > 2 else "",
            )
        )
    return tuple(keys)


def load_identity(auth_dir: Path, username: str, config: AuthConfig) -> Identity | None:
    """Load one identity, refusing anything whose permissions make it worthless.

    Returns ``None`` when no such user directory exists. That is NOT an error:
    an unknown username is an ordinary failed login, and raising would let a
    caller distinguish "no such user" from "wrong password" by exception type —
    which is a user-enumeration oracle handed out for free.

    A StrictModesError, by contrast, DOES propagate. It is not a failed login;
    it is a misconfigured server, and the person who can fix it needs to see it.
    """
    directory = user_dir(auth_dir, username)
    if not directory.is_dir():
        return None

    if config.strict_modes_enabled:
        check_directory(directory)

    keys: tuple[PublicKey, ...] = ()
    keys_path = directory / config.authorized_keys_file
    if keys_path.is_file():
        if config.strict_modes_enabled:
            check_public_file(keys_path)
        keys = parse_authorized_keys(keys_path.read_text())

    password_hash: str | None = None
    password_path = directory / PASSWORD_FILE
    if password_path.is_file():
        if config.strict_modes_enabled:
            check_secret_file(password_path)
        password_hash = password_path.read_text().strip() or None

    return Identity(
        # THE DIRECTORY'S NAME, never the client's string. This was
        # `name=username` until 2026-08-02, which quietly reintroduced the exact
        # thing this design claims to delete: a second field that can DISAGREE
        # with the location. AuthResult's docstring already promised "the
        # DIRECTORY NAME that matched — not a string the client supplied", and
        # the code returned the supplied string.
        #
        # It mattered twice. Under the traversal bug it echoed the attacker's
        # path back as the authenticated identity, which is what an audit log
        # records as "who did this?". And even with that fixed, on a
        # case-insensitive filesystem "Alice" opens alice/ — so the credential
        # checked and the identity reported would drift apart with no attack at
        # all. Reading it off the resolved directory makes the docstring true by
        # construction rather than by convention.
        name=directory.name,
        directory=directory,
        keys=keys,
        password_hash=password_hash,
    )


def list_identities(auth_dir: Path) -> tuple[str, ...]:
    """Every configured username, sorted. Directory names only — no file reads.

    For an operator asking "who can get in?", which is a question the board
    should be able to answer without touching a single credential.
    """
    users_root = auth_dir / "users"
    if not users_root.is_dir():
        return ()
    return tuple(sorted(p.name for p in users_root.iterdir() if p.is_dir()))


# EOF
