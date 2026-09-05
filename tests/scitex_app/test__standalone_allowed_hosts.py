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


# ── the 0.0.0.0 bind: what it IMPLIES, not the string ─────────────────────────
#
# "0.0.0.0" was already in the base list, so `--host 0.0.0.0` contributed
# nothing and a request carrying the real interface address in its Host header
# was refused with 400 (scholar on 1.9.0, figrecipe on 0.34.6, 2026-09-02).
# Tests VERBATIM from scitex-scholar's test__server.py (PR #137), pointed at
# the shared function.


def test_hosts_to_allow_loopback_contributes_nothing():
    # Arrange
    from scitex_app import hosts_to_allow

    # Act
    contributed = hosts_to_allow("127.0.0.1")
    # Assert
    assert contributed == []


def test_hosts_to_allow_specific_address_contributes_itself():
    # Arrange
    from scitex_app import hosts_to_allow

    # Act
    contributed = hosts_to_allow("100.64.0.4")
    # Assert
    assert contributed == ["100.64.0.4"]


def test_hosts_to_allow_bind_all_contributes_this_machines_hostname():
    # Arrange
    import socket

    from scitex_app import hosts_to_allow

    # Act
    contributed = hosts_to_allow("0.0.0.0")
    # Assert
    assert socket.gethostname() in contributed


def test_hosts_to_allow_bind_all_never_contributes_the_literal_wildcard():
    """Control: bind-all must widen to THIS machine, never to everything."""
    # Arrange
    from scitex_app import hosts_to_allow

    # Act
    contributed = hosts_to_allow("0.0.0.0")
    # Assert
    assert "*" not in contributed and "0.0.0.0" not in contributed


def test_hosts_to_allow_bind_all_contributes_a_real_interface_address():
    """The test that the first implementation could NOT fail.

    It used getaddrinfo(gethostname()), passed the hostname assertion above,
    and still answered 400 to the real LAN address in a live check. Derive the
    expected address by an INDEPENDENT method -- the UDP-connect trick reads
    the kernel's chosen source address without sending a packet -- so the
    assertion is not the implementation checking itself.
    """
    # Arrange
    import socket

    from scitex_app import hosts_to_allow

    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        s.connect(("10.255.255.255", 1))  # no packet is sent for UDP connect
        expected = s.getsockname()[0]
    # Act
    contributed = hosts_to_allow("0.0.0.0")
    # Assert
    assert expected in contributed, f"{expected!r} not in {contributed!r}"


def test_bind_all_reaches_allowed_hosts_with_a_real_interface_address():
    """End to end through the public helper: the 0.0.0.0 row of the table."""
    # Arrange
    import socket

    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        s.connect(("10.255.255.255", 1))
        expected = s.getsockname()[0]
    # Act
    hosts = _allowed_hosts("0.0.0.0")
    # Assert
    assert expected in hosts, f"{expected!r} not in {hosts!r}"


# ─── the public name, and the alias that must outlive it exactly once ───────


def test_the_public_name_is_importable_from_the_package_root():
    """What scholar and figrecipe swap to. If this breaks, their build breaks."""
    # Arrange
    import scitex_app

    # Act
    exported = getattr(scitex_app, "hosts_to_allow", None)
    # Assert
    assert exported is not None


def test_the_public_name_is_declared_in_all():
    """Importable-but-undeclared is a promise nobody made."""
    # Arrange
    import scitex_app

    # Act
    declared = "hosts_to_allow" in scitex_app.__all__
    # Assert
    assert declared is True


# EOF
