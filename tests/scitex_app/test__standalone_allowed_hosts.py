#!/usr/bin/env python3
"""ALLOWED_HOSTS must include the address the server was told to bind.

Reported by scitex-scholar 2026-08-23: `serve --host <addr>` started cleanly,
printed "serving at http://<addr>:<port>", and then answered 400 to every
caller. The startup banner asserted the opposite of the truth, which is why the
first minutes went into looking at the network.

No fixtures reach into process state: `_allowed_hosts` takes the extra-hosts
string as an argument and the caller reads the env. The first draft used
`monkeypatch` and PA-306 rejected it — correctly, because needing to patch the
environment was a symptom of the function being impure, not of the rule being
strict.

One assertion each — these are rows of a truth table, and a compound assert
would report "the table is wrong" instead of naming the row.
"""

from scitex_app._standalone import _allowed_hosts


def test_the_bound_host_is_allowed():
    # Arrange — the reported defect. Binding to an address IS the statement
    # that you intend to be reached on it.
    bound = "100.64.0.4"
    # Act
    hosts = _allowed_hosts(bound)
    # Assert
    assert bound in hosts


def test_loopback_is_still_allowed_when_bound_elsewhere():
    # Arrange — the arm that stops the fix becoming a swap. Local access must
    # keep working when the server is bound to an external address.
    expected = "127.0.0.1"
    # Act
    hosts = _allowed_hosts("100.64.0.4")
    # Assert
    assert expected in hosts


def test_the_default_bind_does_not_duplicate_loopback():
    # Arrange — the default host is already in the base list, so appending
    # blindly would produce a duplicate entry.
    # Act
    hosts = _allowed_hosts("127.0.0.1")
    # Assert
    assert hosts.count("127.0.0.1") == 1


def test_extra_hosts_are_contributed():
    # Arrange — the proxy/tunnel case, where the reachable name is not the
    # bound address.
    expected = "app.example.org"
    # Act
    hosts = _allowed_hosts("127.0.0.1", "app.example.org, other.local")
    # Assert
    assert expected in hosts


def test_extra_host_entries_are_stripped():
    # Arrange — a comma-separated list written by a human has spaces in it, and
    # Django matches Host headers exactly, so " other.local" would never match.
    expected = "other.local"
    # Act
    hosts = _allowed_hosts("127.0.0.1", "app.example.org, other.local")
    # Assert
    assert expected in hosts


def test_no_wildcard_is_introduced():
    # Arrange — deliberate limit. These apps ship no authentication and
    # DJANGO_DEBUG defaults to "true", so a "*" would make every reachable
    # address an unauthenticated reader. Fixing the silent 400 must not widen
    # exposure; this arm fails if someone later reaches for the easy answer.
    forbidden = "*"
    # Act
    hosts = _allowed_hosts("100.64.0.4", "app.example.org")
    # Assert
    assert forbidden not in hosts
