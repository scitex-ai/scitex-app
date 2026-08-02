#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""The decision: does this (username, credential) get in, and why or why not.

THE "WHY NOT" IS HALF THE FEATURE. ssh's real value under ``-vvv`` is not that it
fails — it is that it tells you WHICH key was offered and WHY each one was
rejected. Authentication that fails silently is unfixable by the person it failed
for, which is precisely the state the operator was left in when a board asked for
a password it could not explain and named no username at all.

So every decision here carries a :class:`Trace`: an ordered list of the steps
tried and their outcomes, at ssh's own verbosity levels. The board can render it
at DEBUG1+ and say nothing at INFO, exactly as sshd does.

WHAT IS NEVER IN A TRACE: the credential. Not the password, not the hash, not a
prefix of either. Traces are written to logs and logs are read by people who
should not learn secrets from them, so a trace carries STRUCTURE — which method,
which key by fingerprint, which outcome — and never content.
"""

from __future__ import annotations

import hashlib
import base64
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

from ._config import AuthConfig, LogLevel
from ._password import HashFormatError, verify_password
from ._users import Identity, load_identity

__all__ = [
    "AuthResult",
    "Method",
    "Outcome",
    "Trace",
    "TraceStep",
    "authenticate_password",
    "authenticate_publickey",
    "fingerprint",
]


class Method(str, Enum):
    """The authentication methods, named as ssh names them."""

    PUBLICKEY = "publickey"
    PASSWORD = "password"


class Outcome(str, Enum):
    """Why a step ended as it did — never a bare bool.

    A bool would collapse "wrong password" and "password auth is disabled" and
    "this user has no password set" into one ``False``, and those three want
    three different actions from whoever is reading.
    """

    ACCEPTED = "accepted"
    WRONG_CREDENTIAL = "wrong credential"
    METHOD_DISABLED = "method disabled by config"
    NO_SUCH_USER = "no such user"
    NO_CREDENTIAL_CONFIGURED = "user has no credential of this kind"
    CREDENTIAL_UNREADABLE = "stored credential could not be parsed"


@dataclass(frozen=True)
class TraceStep:
    """One thing tried, and what came of it. Structure only, never content."""

    message: str
    level: LogLevel = LogLevel.DEBUG1


@dataclass(frozen=True)
class Trace:
    """The ordered record of an authentication attempt.

    Rendered at the config's LogLevel, so an operator who wants ssh's ``-vvv``
    experience sets ``LogLevel DEBUG3`` and gets it, and one who does not sees
    nothing.
    """

    steps: tuple[TraceStep, ...] = field(default_factory=tuple)

    def rendered(self, level: LogLevel) -> tuple[str, ...]:
        """The lines visible at ``level``. ``INFO`` shows none of the debug ones."""
        order = list(LogLevel)
        ceiling = order.index(level)
        return tuple(
            step.message for step in self.steps if order.index(step.level) <= ceiling
        )


@dataclass(frozen=True)
class AuthResult:
    """Accepted or not, WHICH identity, and the full reasoning.

    ``username`` is present on success and is the DIRECTORY NAME that matched —
    not a string the client supplied and not one parsed out of a header. That is
    what makes "who did this?" answerable downstream.
    """

    accepted: bool
    method: Method
    outcome: Outcome
    username: str | None = None
    trace: Trace = field(default_factory=Trace)


def fingerprint(algorithm: str, material: str) -> str:
    """``SHA256:...`` over the key blob — ssh's own fingerprint format.

    A fingerprint is what makes a trace useful without making it dangerous: it
    names WHICH key was offered, and it is derived from public material, so
    logging it leaks nothing. ``ssh-keygen -lf`` prints the same string, which
    means an operator can match a log line against a key they hold.
    """
    try:
        blob = base64.b64decode(material.encode("ascii"), validate=True)
    except Exception:  # noqa: BLE001 -- an unparseable key still needs a label
        return f"{algorithm}:<unparseable>"
    digest = hashlib.sha256(blob).digest()
    return "SHA256:" + base64.b64encode(digest).decode("ascii").rstrip("=")


def _resolve(
    auth_dir: Path, username: str, config: AuthConfig, steps: list[TraceStep]
) -> Identity | None:
    identity = load_identity(auth_dir, username, config)
    if identity is None:
        steps.append(
            TraceStep(
                f"no user directory {auth_dir / 'users' / username}",
                LogLevel.DEBUG1,
            )
        )
    return identity


def authenticate_publickey(
    auth_dir: Path,
    username: str,
    offered_algorithm: str,
    offered_material: str,
    config: AuthConfig,
) -> AuthResult:
    """Check an offered public key against ``users/<username>/authorized_keys``."""
    steps: list[TraceStep] = []
    offered_fp = fingerprint(offered_algorithm, offered_material)
    steps.append(
        TraceStep(f"offering {offered_algorithm} {offered_fp}", LogLevel.DEBUG1)
    )

    if not config.pubkey_enabled:
        steps.append(
            TraceStep(
                "PubkeyAuthentication is 'no' in the server config", LogLevel.INFO
            )
        )
        return AuthResult(
            False, Method.PUBLICKEY, Outcome.METHOD_DISABLED, trace=Trace(tuple(steps))
        )

    identity = _resolve(auth_dir, username, config, steps)
    if identity is None:
        return AuthResult(
            False, Method.PUBLICKEY, Outcome.NO_SUCH_USER, trace=Trace(tuple(steps))
        )
    if not identity.has_key:
        steps.append(
            TraceStep(
                f"{identity.directory / config.authorized_keys_file} holds no keys",
                LogLevel.DEBUG1,
            )
        )
        return AuthResult(
            False,
            Method.PUBLICKEY,
            Outcome.NO_CREDENTIAL_CONFIGURED,
            trace=Trace(tuple(steps)),
        )

    for known in identity.keys:
        known_fp = fingerprint(known.algorithm, known.material)
        if known.algorithm == offered_algorithm and known.material == offered_material:
            steps.append(
                TraceStep(
                    f"accepted: matches {known_fp}"
                    + (f" ({known.comment})" if known.comment else ""),
                    LogLevel.INFO,
                )
            )
            return AuthResult(
                True,
                Method.PUBLICKEY,
                Outcome.ACCEPTED,
                username=identity.name,
                trace=Trace(tuple(steps)),
            )
        # DEBUG2 rather than DEBUG1: on a user with many keys this is noisy, and
        # ssh puts exactly this kind of per-candidate detail behind -vv.
        steps.append(TraceStep(f"no match against {known_fp}", LogLevel.DEBUG2))

    steps.append(
        TraceStep(
            f"offered key not in {config.authorized_keys_file} "
            f"({len(identity.keys)} key(s) checked)",
            LogLevel.INFO,
        )
    )
    return AuthResult(
        False, Method.PUBLICKEY, Outcome.WRONG_CREDENTIAL, trace=Trace(tuple(steps))
    )


def authenticate_password(
    auth_dir: Path, username: str, password: str, config: AuthConfig
) -> AuthResult:
    """Check a password against ``users/<username>/password``."""
    steps: list[TraceStep] = []

    if not config.password_enabled:
        steps.append(
            TraceStep(
                "PasswordAuthentication is 'no' in the server config", LogLevel.INFO
            )
        )
        return AuthResult(
            False, Method.PASSWORD, Outcome.METHOD_DISABLED, trace=Trace(tuple(steps))
        )

    identity = _resolve(auth_dir, username, config, steps)
    if identity is None:
        return AuthResult(
            False, Method.PASSWORD, Outcome.NO_SUCH_USER, trace=Trace(tuple(steps))
        )
    if not identity.has_password:
        steps.append(
            TraceStep(f"{identity.directory / 'password'} is absent", LogLevel.DEBUG1)
        )
        return AuthResult(
            False,
            Method.PASSWORD,
            Outcome.NO_CREDENTIAL_CONFIGURED,
            trace=Trace(tuple(steps)),
        )

    try:
        ok = verify_password(identity.password_hash or "", password)
    except HashFormatError as exc:
        # NOT a failed login. A stored credential that cannot be parsed is a
        # broken server, and returning "wrong password" here would hide it
        # forever behind a message that looks like ordinary user error.
        steps.append(TraceStep(f"stored hash unusable: {exc}", LogLevel.INFO))
        return AuthResult(
            False,
            Method.PASSWORD,
            Outcome.CREDENTIAL_UNREADABLE,
            trace=Trace(tuple(steps)),
        )

    if ok:
        steps.append(TraceStep(f"accepted: password for {username}", LogLevel.INFO))
        return AuthResult(
            True,
            Method.PASSWORD,
            Outcome.ACCEPTED,
            username=identity.name,
            trace=Trace(tuple(steps)),
        )
    steps.append(TraceStep(f"password mismatch for {username}", LogLevel.INFO))
    return AuthResult(
        False, Method.PASSWORD, Outcome.WRONG_CREDENTIAL, trace=Trace(tuple(steps))
    )


# EOF
