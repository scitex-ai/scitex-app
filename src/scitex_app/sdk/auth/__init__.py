#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ssh-shaped authentication, so no SciTeX app author has to build their own.

WHY THIS IS IN THE SDK rather than in each app, in the operator's words:

    "SDK に含めないと、他のユーザが GUI のアプリを書くときに大変になってくる。
     認証の仕組みとか、一般的なユーザさんが自分で組めるかって言うとそうではない"

Authentication is the canonical thing you must not ask every app author to
re-implement. Ship it as a convention and you get N implementations; the weakest
one becomes everyone's security posture, and nobody finds out until it matters.
Ship it as code and everyone gets the same reviewed path.

WHY IT LOOKS LIKE ssh — 守破離, and this package is mostly 守. Earlier attempts
translated ssh's model into something that looked tidier and each translation
reintroduced a problem ssh had already solved. So: keyword-value config files
named after sshd's, permissions enforced by refusal, identity carried by
directory location, LogLevel DEBUG1/2/3 meaning exactly -v/-vv/-vvv.

    <project>/.scitex/<app>/auth/     checked first
    ~/.scitex/<app>/auth/             fallback
      <app>_config                        client side (ssh_config)
      <app>d_config                       server side (sshd_config)
      users/<name>/authorized_keys        public keys, ssh format
      users/<name>/password               one PHC hash

The one deliberate divergence (破) is that there is NO /etc tier. sshd splits
because it is a system daemon serving every OS user; an app board is not, and a
third tier no app writes to is a tier that goes stale and misleads.

Usage, mirroring ``get_files()`` next door::

    from scitex_app.sdk.auth import get_authenticator

    auth = get_authenticator("cards")            # resolves project then home
    result = auth.password("ywatanabe", supplied)
    if result.accepted:
        subject = result.username                # the DIRECTORY name that matched
    else:
        for line in result.trace.rendered(auth.config.log_level):
            log.info(line)                       # ssh's -vvv, when asked for

NOTHING HERE EVER READS ``~/.ssh``. A user may paste a key they already own;
nothing pastes it for them. Granting access belongs to the person granting it.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ._authenticator import (
    AuthResult,
    Method,
    Outcome,
    Trace,
    TraceStep,
    authenticate_password,
    authenticate_publickey,
    fingerprint,
)
from ._config import (
    AuthConfig,
    ConfigError,
    LogLevel,
    Tristate,
    parse_config,
)
from ._password import HashFormatError, hash_password, verify_password
from ._paths import (
    UnsafeAppName,
    UnsafeUsername,
    auth_dir_candidates,
    client_config_path,
    resolve_auth_dir,
    server_config_path,
    user_dir,
    validate_app_name,
    validate_username,
)
from ._strictmodes import StrictModesError
from ._users import Identity, list_identities, load_identity, parse_authorized_keys

__all__ = [
    "AuthConfig",
    "AuthResult",
    "Authenticator",
    "ConfigError",
    "HashFormatError",
    "Identity",
    "LogLevel",
    "Method",
    "Outcome",
    "StrictModesError",
    "UnsafeAppName",
    "UnsafeUsername",
    "Trace",
    "TraceStep",
    "Tristate",
    "auth_dir_candidates",
    "authenticate_password",
    "authenticate_publickey",
    "client_config_path",
    "fingerprint",
    "get_authenticator",
    "hash_password",
    "list_identities",
    "load_identity",
    "parse_authorized_keys",
    "parse_config",
    "resolve_auth_dir",
    "server_config_path",
    "user_dir",
    "validate_app_name",
    "validate_username",
    "verify_password",
]


class AuthNotConfigured(RuntimeError):
    """No auth directory exists for this app, and the caller must decide.

    Deliberately NOT auto-created and NOT silently defaulted to open. Creating
    it would invent a policy the operator never wrote; defaulting to open would
    be worse. The message lists every path that was tried, because "where does
    it expect the file?" is the first question and an error that cannot answer
    it sends the reader guessing — which is precisely the failure this whole
    package exists to correct.
    """


@dataclass(frozen=True)
class Authenticator:
    """One app's resolved auth: where it lives, what it permits, who is in it."""

    app: str
    auth_dir: Path
    config: AuthConfig

    def password(self, username: str, supplied: str) -> AuthResult:
        """Check a password for ``username``."""
        return authenticate_password(self.auth_dir, username, supplied, self.config)

    def publickey(self, username: str, algorithm: str, material: str) -> AuthResult:
        """Check an offered public key for ``username``."""
        return authenticate_publickey(
            self.auth_dir, username, algorithm, material, self.config
        )

    def identities(self) -> tuple[str, ...]:
        """Every configured username — answers "who can get in?" without reads."""
        return list_identities(self.auth_dir)


def get_authenticator(
    app: str,
    *,
    project_dir: Path | None = None,
) -> Authenticator:
    """Resolve ``app``'s auth directory and parse its server config.

    Raises :class:`AuthNotConfigured` when no auth directory exists, naming every
    candidate path. Raises :class:`ConfigError` when one exists but its config
    cannot be honoured — at LOAD time, so a contradiction surfaces before the
    first login rather than during it.
    """
    auth_dir = resolve_auth_dir(app, project_dir)
    if auth_dir is None:
        tried = auth_dir_candidates(app, project_dir)
        listing = "\n".join(f"    {path}" for path in tried)
        raise AuthNotConfigured(
            f"no auth directory for app {app!r}. Looked in:\n{listing}\n"
            f"  fix: mkdir -p {tried[0]}/users/$USER && chmod 700 {tried[0]}"
        )
    return Authenticator(
        app=app,
        auth_dir=auth_dir,
        config=parse_config(server_config_path(auth_dir, app)),
    )


# EOF
