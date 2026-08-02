#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""``<app>d_config`` — sshd_config's grammar, copied rather than translated.

守破離, and this file is 守. Every earlier pass at this design TRANSLATED ssh's
model into something tidier — a YAML schema, a flat key file, a server-only
config — and each translation reintroduced a problem ssh had already solved. So
the rule is: where ssh has an answer, take ssh's answer, including the parts
that look like incidental detail.

WHAT IS COPIED
    keyword-value lines, whitespace separated, case-insensitive keywords
    ``#`` comments, blank lines ignored
    the keyword names themselves (``PubkeyAuthentication``, ``StrictModes``, …)
    ``LogLevel``, which is ssh's ``-v`` / ``-vv`` / ``-vvv``
    FIRST occurrence wins, as sshd does — a later line cannot silently override

The payoff is concrete rather than aesthetic: an example from ``man sshd_config``
pastes in unchanged, and knowing one config transfers to the other. That matters
most for the person who is not a security engineer, which is exactly who this
SDK exists to serve.

WHY NOT YAML, since every other config in this ecosystem is YAML. Two reasons,
and the second is the real one. First, ssh's own documentation and every answer
on the internet is in this grammar, so YAML would mean translating every example
before use. Second, ``Match User alice`` has no clean YAML form — you end up with
a list of dicts each holding a condition and a body, which is a worse spelling of
the same thing and one nobody can write from memory.

WHY UNKNOWN KEYWORDS ARE FATAL. sshd refuses to start on one, and the reason is
the whole point of a gate: a silently-ignored ``PasswordAuthetication`` typo
leaves password auth ENABLED while the file says it is off, so the operator has
written down a belief the system does not share. A warning would not do — nobody
reads a warning on a daemon that started successfully.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

__all__ = [
    "KNOWN_KEYWORDS",
    "AuthConfig",
    "ConfigError",
    "LogLevel",
    "Tristate",
    "parse_config",
]


class Tristate(str, Enum):
    """yes / no / **unset** — because collapsing unset into a pole is the bug.

    Here it decides whether a default may still apply, which a bare bool cannot
    express: ``False`` cannot say whether the operator wrote ``no`` or wrote
    nothing, and those two must behave differently the moment a default changes.
    """

    YES = "yes"
    NO = "no"
    UNSET = "unset"

    @property
    def enabled(self) -> bool:
        """True only for an explicit ``yes``. ``UNSET`` is NOT a value."""
        return self is Tristate.YES


class LogLevel(str, Enum):
    """ssh's own ladder. ``DEBUG1/2/3`` are exactly ``-v`` / ``-vv`` / ``-vvv``.

    Kept verbatim, including ``DEBUG`` as a synonym for ``DEBUG1``, because the
    single most useful property of ssh auth debugging is that ``ssh -vvv`` tells
    you WHICH key was offered and WHY each one was rejected. Authentication that
    fails silently is unfixable by the person it failed for — which is the state
    the operator was left in when a board asked for a password it could not
    explain.
    """

    QUIET = "QUIET"
    FATAL = "FATAL"
    ERROR = "ERROR"
    INFO = "INFO"
    VERBOSE = "VERBOSE"
    DEBUG1 = "DEBUG1"
    DEBUG2 = "DEBUG2"
    DEBUG3 = "DEBUG3"

    @classmethod
    def from_verbosity(cls, count: int) -> "LogLevel":
        """``-v`` → DEBUG1, ``-vv`` → DEBUG2, ``-vvv`` (or more) → DEBUG3."""
        return {0: cls.INFO, 1: cls.DEBUG1, 2: cls.DEBUG2}.get(count, cls.DEBUG3)


class ConfigError(ValueError):
    """A config that cannot be trusted, reported where it is BUILT.

    Carries the file, the line number and the remedy, so the message is
    actionable on its own. An error that states only what broke is half-written:
    the reader still has to work out what to type.
    """

    def __init__(self, path: Path, lineno: int, problem: str, remedy: str) -> None:
        self.path, self.lineno = path, lineno
        self.problem, self.remedy = problem, remedy
        where = f"{path}:{lineno}" if lineno else str(path)
        super().__init__(f"{where}: {problem}\n  fix: {remedy}")


#: Membership in these tuples IS the allow-list, so an unrecognised keyword is
#: caught by construction rather than by a separate list someone must remember
#: to keep in step.
_TRISTATE_KEYWORDS = (
    "pubkeyauthentication",
    "passwordauthentication",
    "strictmodes",
)
_PATH_KEYWORDS = ("authorizedkeysfile",)
_LEVEL_KEYWORDS = ("loglevel",)

KNOWN_KEYWORDS: tuple[str, ...] = _TRISTATE_KEYWORDS + _PATH_KEYWORDS + _LEVEL_KEYWORDS

#: Canonical spellings, so an error suggests the REAL keyword rather than
#: echoing the reader's typo back at them.
_CANONICAL = {
    "pubkeyauthentication": "PubkeyAuthentication",
    "passwordauthentication": "PasswordAuthentication",
    "strictmodes": "StrictModes",
    "authorizedkeysfile": "AuthorizedKeysFile",
    "loglevel": "LogLevel",
}

_COMMENT = re.compile(r"^\s*(#.*)?$")


@dataclass(frozen=True)
class AuthConfig:
    """The parsed server config. One named field per setting, never a dict.

    Frozen because a config that can change under a running server is a config
    whose current value nobody can state.
    """

    pubkey_authentication: Tristate = Tristate.UNSET
    password_authentication: Tristate = Tristate.UNSET
    strict_modes: Tristate = Tristate.UNSET
    authorized_keys_file: str = "authorized_keys"
    log_level: LogLevel = LogLevel.INFO
    source: Path | None = None
    #: Keywords in the order seen, so "why did my second line do nothing?" has an
    #: answer that does not require re-reading the parser.
    seen: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        self.validate()

    # -- defaults ---------------------------------------------------------
    # Applied at READ time rather than baked into the field defaults, so `unset`
    # stays distinguishable from an explicit `no` for anything that needs to know
    # whether the operator actually said something.

    @property
    def pubkey_enabled(self) -> bool:
        """Public-key auth is ON unless explicitly disabled — sshd's default."""
        return self.pubkey_authentication is not Tristate.NO

    @property
    def password_enabled(self) -> bool:
        """Password auth is ON unless explicitly disabled — sshd's default."""
        return self.password_authentication is not Tristate.NO

    @property
    def strict_modes_enabled(self) -> bool:
        """Permission checking is ON unless explicitly disabled — sshd's default.

        Defaulting to ON is the point. A credential left group-readable is
        silently exploitable; a refusal is loud and one chmod fixes it. The
        asymmetry is entirely one-sided.
        """
        return self.strict_modes is not Tristate.NO

    def validate(self) -> None:
        """Reject a config that parses but cannot be honoured.

        Runs where the object is BUILT, so a contradiction surfaces at load
        rather than three layers downstream at the first login attempt — by
        which time the person who could fix it has stopped looking.
        """
        where = self.source or Path("<config>")
        if (
            self.pubkey_authentication is Tristate.NO
            and self.password_authentication is Tristate.NO
        ):
            raise ConfigError(
                where,
                0,
                "PubkeyAuthentication and PasswordAuthentication are both 'no', "
                "so nobody could ever authenticate",
                "set at least one to 'yes', or delete the line to take the "
                "default (both enabled)",
            )
        if not self.authorized_keys_file:
            raise ConfigError(
                where,
                0,
                "AuthorizedKeysFile is empty",
                "name a file relative to the user directory, e.g. 'authorized_keys'",
            )
        if Path(self.authorized_keys_file).is_absolute():
            raise ConfigError(
                where,
                0,
                f"AuthorizedKeysFile {self.authorized_keys_file!r} is absolute",
                "make it relative to auth/users/<name>/, e.g. 'authorized_keys' "
                "— an absolute path would point every user at one shared file",
            )
        if os.pardir in Path(self.authorized_keys_file).parts:
            # THE GUARD ABOVE DID NOT ACHIEVE ITS OWN STATED GOAL. Its message
            # says an absolute path "would point every user at one shared file"
            # — and '../../../../.ssh/authorized_keys' points every user at one
            # shared file just as completely, while satisfying the remedy text
            # ("make it relative...") on a literal reading. Measured by
            # scitex-app: absolute was REFUSED, '../' was ACCEPTED.
            #
            # Much lower severity than the username hole, because this value is
            # OPERATOR-supplied and nobody hostile writes it. It is fixed anyway
            # because a check whose message names a property it does not enforce
            # teaches the reader something false about what is guaranteed.
            raise ConfigError(
                where,
                0,
                f"AuthorizedKeysFile {self.authorized_keys_file!r} climbs out of "
                "the user directory with '..'",
                "keep it inside auth/users/<name>/, e.g. 'authorized_keys' — "
                "climbing out points every user at one shared file, which is "
                "the same failure an absolute path would cause",
            )


def _parse_tristate(path: Path, lineno: int, keyword: str, value: str) -> Tristate:
    lowered = value.strip().lower()
    if lowered in ("yes", "no"):
        return Tristate(lowered)
    raise ConfigError(
        path,
        lineno,
        f"{_CANONICAL[keyword]} value {value!r} is not 'yes' or 'no'",
        "write 'yes' or 'no' — sshd accepts nothing else here",
    )


def _parse_level(path: Path, lineno: int, value: str) -> LogLevel:
    upper = value.strip().upper()
    if upper == "DEBUG":  # ssh's own synonym for DEBUG1
        upper = "DEBUG1"
    try:
        return LogLevel(upper)
    except ValueError:
        raise ConfigError(
            path,
            lineno,
            f"LogLevel {value!r} is not a known level",
            "use one of "
            + ", ".join(level.value for level in LogLevel)
            + " (DEBUG1/2/3 correspond to -v / -vv / -vvv)",
        ) from None


def _suggest(keyword: str) -> str:
    """Nearest known keyword, so a typo's remedy names the real spelling."""
    import difflib  # noqa: PLC0415 -- only needed on the error path

    close = difflib.get_close_matches(keyword, KNOWN_KEYWORDS, n=1, cutoff=0.6)
    if close:
        return f"did you mean {_CANONICAL[close[0]]}?"
    return "known keywords: " + ", ".join(_CANONICAL[k] for k in KNOWN_KEYWORDS)


def parse_config(path: Path) -> AuthConfig:
    """Read an ``<app>d_config``. Unknown keywords and bad values are FATAL.

    A MISSING file is not an error — it means "take the defaults", exactly as a
    host with no sshd_config would. An UNREADABLE file is a different thing and
    does raise, because silently falling back to defaults when the operator
    wrote a policy is how a gate stops gating.
    """
    if not path.exists():
        return AuthConfig(source=path)

    values: dict[str, object] = {}
    seen: list[str] = []
    for lineno, raw in enumerate(path.read_text().splitlines(), start=1):
        if _COMMENT.match(raw):
            continue
        parts = raw.strip().split(None, 1)
        keyword = parts[0].lower()
        value = parts[1].strip() if len(parts) > 1 else ""

        if keyword not in KNOWN_KEYWORDS:
            raise ConfigError(
                path, lineno, f"unknown keyword {parts[0]!r}", _suggest(keyword)
            )
        if not value:
            raise ConfigError(
                path,
                lineno,
                f"{_CANONICAL[keyword]} has no value",
                f"write '{_CANONICAL[keyword]} <value>' on one line",
            )
        seen.append(_CANONICAL[keyword])
        if keyword in values:
            # sshd: the FIRST obtained value wins. Keeping that means a config
            # copied from a man page behaves the way the man page says it does.
            continue

        if keyword in _TRISTATE_KEYWORDS:
            values[keyword] = _parse_tristate(path, lineno, keyword, value)
        elif keyword in _LEVEL_KEYWORDS:
            values[keyword] = _parse_level(path, lineno, value)
        else:
            values[keyword] = value

    return AuthConfig(
        pubkey_authentication=values.get("pubkeyauthentication", Tristate.UNSET),
        password_authentication=values.get("passwordauthentication", Tristate.UNSET),
        strict_modes=values.get("strictmodes", Tristate.UNSET),
        authorized_keys_file=values.get("authorizedkeysfile", "authorized_keys"),
        log_level=values.get("loglevel", LogLevel.INFO),
        source=path,
        seen=tuple(seen),
    )


# EOF
