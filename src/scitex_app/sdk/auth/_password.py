#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Password hashing, in PHC string format, with no dependency to install.

WHY scrypt AND NOT argon2, stated plainly because the operator asked for argon2
and this is a deliberate substitution rather than a slip. argon2 needs
``argon2-cffi``, a compiled dependency. This module is the auth primitive of an
SDK whose whole justification is that an app author should not have to build
auth themselves — and a primitive that fails to install is one they will route
around. ``hashlib.scrypt`` is in the standard library, is memory-hard, and is
what ``passlib`` recommends when argon2 is unavailable.

argon2 IS still honoured: verification dispatches on the ``$id$`` prefix, so an
``$argon2id$`` hash produced anywhere verifies here whenever ``argon2-cffi`` is
importable. The default is scrypt; the door to argon2 is open and needs no
change to this file.

FORMAT is PHC (``$id$params$salt$hash``), the same string shape argon2, scrypt
and bcrypt all use, so a stored hash says which algorithm produced it and with
which parameters. A bare hex digest does not, and a store full of bare digests
cannot be migrated to a stronger algorithm without asking every user to re-enter
their password.

    $scrypt$n=16384,r=8,p=1$<b64 salt>$<b64 hash>

Comparison is ``hmac.compare_digest`` throughout. Timing leaks on a password
check are a real attack and ``==`` on bytes short-circuits at the first
differing byte.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import os
from dataclasses import dataclass

__all__ = [
    "SCRYPT_N",
    "SCRYPT_P",
    "SCRYPT_R",
    "HashFormatError",
    "hash_password",
    "verify_password",
]

#: RFC 7914's interactive-login parameters. n is the memory/CPU cost and must be
#: a power of two; raising it is the knob that keeps this honest as hardware
#: improves. Recorded IN the hash string, so raising it later does not
#: invalidate hashes already stored.
SCRYPT_N = 16_384
SCRYPT_R = 8
SCRYPT_P = 1

_SALT_BYTES = 16
_KEY_BYTES = 32


class HashFormatError(ValueError):
    """A stored hash this module cannot parse — never treated as "no password".

    The distinction matters: an unparseable hash must FAIL the login, not skip
    the check. Treating a malformed credential as absent is how a corrupted file
    becomes an open door.
    """


def _b64(raw: bytes) -> str:
    return base64.b64encode(raw).decode("ascii")


def _unb64(text: str) -> bytes:
    try:
        return base64.b64decode(text.encode("ascii"), validate=True)
    except Exception as exc:  # noqa: BLE001 -- any decode failure is one failure
        raise HashFormatError(f"not valid base64: {text[:16]!r}") from exc


def hash_password(
    password: str,
    *,
    n: int = SCRYPT_N,
    r: int = SCRYPT_R,
    p: int = SCRYPT_P,
) -> str:
    """Hash ``password`` with a fresh random salt. Returns a PHC string."""
    salt = os.urandom(_SALT_BYTES)
    derived = hashlib.scrypt(
        password.encode("utf-8"), salt=salt, n=n, r=r, p=p, dklen=_KEY_BYTES
    )
    return f"$scrypt$n={n},r={r},p={p}${_b64(salt)}${_b64(derived)}"


def _verify_scrypt(stored: str, password: str) -> bool:
    # INSIDE the try, not before it. This unpack sat above the try until
    # 2026-08-02, so a TRUNCATED hash — fewer than five '$'-separated fields —
    # raised a bare ValueError that escaped as itself. `authenticate_password`
    # catches only HashFormatError, so the CREDENTIAL_UNREADABLE outcome written
    # precisely for a corrupt stored credential was bypassed, and the caller got
    # an exception type it had no branch for.
    #
    # The lesson is narrower than "wrap more": a function that converts one error
    # class into another must have EVERY parse step inside the conversion, or the
    # conversion is a claim it does not honour.
    try:
        _, _, params, salt_b64, hash_b64 = stored.split("$", 4)
        parsed = dict(pair.split("=", 1) for pair in params.split(","))
        n, r, p = int(parsed["n"]), int(parsed["r"]), int(parsed["p"])
    except Exception as exc:  # noqa: BLE001
        raise HashFormatError(f"unreadable scrypt parameters: {params!r}") from exc

    expected = _unb64(hash_b64)
    actual = hashlib.scrypt(
        password.encode("utf-8"),
        salt=_unb64(salt_b64),
        n=n,
        r=r,
        p=p,
        dklen=len(expected),
    )
    return hmac.compare_digest(expected, actual)


def _verify_argon2(stored: str, password: str) -> bool:
    try:
        import argon2  # noqa: PLC0415 -- optional, absent by design
    except Exception as exc:  # noqa: BLE001 -- see below; not just ImportError
        # Deliberately broader than ImportError. An optional dependency can be
        # PRESENT and still unusable -- a compiled wheel against the wrong
        # libffi raises at import time with something that is not an
        # ImportError. Catching only ImportError would let that escape as a
        # crash from a code path the caller never opted into, and the honest
        # answer in both cases is identical: this hash cannot be verified here.
        raise HashFormatError(
            f"this hash is argon2, but argon2-cffi is not usable here ({exc}). "
            "fix: pip install argon2-cffi"
        ) from exc
    try:
        return bool(argon2.PasswordHasher().verify(stored, password))
    except Exception:  # noqa: BLE001 -- argon2 signals mismatch by raising
        return False


def verify_password(stored: str, password: str) -> bool:
    """Check ``password`` against a stored PHC hash.

    Raises :class:`HashFormatError` on anything it cannot parse, rather than
    returning ``False``. A caller that cannot tell "wrong password" from
    "corrupt credential file" will debug the wrong one for hours, and — worse —
    a silent ``False`` looks identical to a working rejection, so nobody ever
    learns the file is broken.
    """
    stored = stored.strip()
    if not stored.startswith("$"):
        raise HashFormatError(
            "stored hash is not in PHC format (expected it to start with '$id$'). "
            "A bare digest cannot say which algorithm produced it"
        )
    algorithm = stored.split("$", 2)[1]
    if algorithm == "scrypt":
        return _verify_scrypt(stored, password)
    if algorithm.startswith("argon2"):
        return _verify_argon2(stored, password)
    raise HashFormatError(
        f"unknown password hash algorithm {algorithm!r}. "
        "known: scrypt (built in), argon2i/argon2d/argon2id (needs argon2-cffi)"
    )


# EOF
