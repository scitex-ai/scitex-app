#!/usr/bin/env python3
# Timestamp: 2026-07-13
# File: tests/scitex_app/test_embed_gui.py

"""Tests for scitex_app.embed's shared GUI launcher (serve_gui + friends)."""

from __future__ import annotations

import socket

import pytest

from scitex_app import _gui_runtime, embed


@pytest.fixture
def state_file(tmp_path):
    return tmp_path / "gui.json"


@pytest.fixture
def free_port():
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()
    yield port


def test_serve_gui_binds_and_runs_server(state_file, free_port):
    # Arrange
    calls = []
    # Act
    code = embed.serve_gui(
        "testpkg",
        "/proj",
        free_port,
        "127.0.0.1",
        False,
        lambda: calls.append(1),
        state_path=state_file,
    )
    # Assert
    assert code == 0


def test_serve_gui_invokes_run_server(state_file, free_port):
    # Arrange
    calls = []
    # Act
    embed.serve_gui(
        "testpkg",
        "/proj",
        free_port,
        "127.0.0.1",
        False,
        lambda: calls.append(1),
        state_path=state_file,
    )
    # Assert
    assert calls == [1]


def test_serve_gui_clears_state_after_run(state_file, free_port):
    # Arrange
    # Act
    embed.serve_gui(
        "testpkg",
        "/proj",
        free_port,
        "127.0.0.1",
        False,
        lambda: None,
        state_path=state_file,
    )
    # Assert
    assert not state_file.exists()


def test_serve_gui_refuses_second_instance_without_force(state_file, free_port):
    # Arrange
    import os

    embed._gr.write_state(os.getpid(), free_port, "127.0.0.1", "/proj", state_file)
    # Act
    code = embed.serve_gui(
        "testpkg",
        "/proj",
        free_port,
        "127.0.0.1",
        False,
        lambda: None,
        state_path=state_file,
    )
    # Assert
    assert code == 1


def test_serve_gui_force_stops_own_recorded_instance(state_file, free_port):
    # Arrange
    import os
    import subprocess
    import sys

    child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"])
    embed._gr.write_state(child.pid, free_port, "127.0.0.1", "/proj", state_file)
    calls = []
    # Act
    code = embed.serve_gui(
        "testpkg",
        "/proj",
        free_port,
        "127.0.0.1",
        True,
        lambda: calls.append(1),
        state_path=state_file,
    )
    child.wait(timeout=5)
    # Assert
    assert code == 0 and calls == [1]


def test_serve_gui_refuses_when_port_bound_by_foreign_process(state_file):
    # Arrange
    sock = socket.socket()
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind(("127.0.0.1", 0))
    sock.listen(1)
    port = sock.getsockname()[1]
    # Act
    code = embed.serve_gui(
        "testpkg",
        "/proj",
        port,
        "127.0.0.1",
        False,
        lambda: None,
        state_path=state_file,
    )
    sock.close()
    # Assert
    assert code == 1


def test_serve_gui_never_offers_force_hint_for_foreign_holder(state_file, capsys):
    # Arrange
    sock = socket.socket()
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind(("127.0.0.1", 0))
    sock.listen(1)
    port = sock.getsockname()[1]
    # Act
    embed.serve_gui(
        "testpkg",
        "/proj",
        port,
        "127.0.0.1",
        False,
        lambda: None,
        state_path=state_file,
    )
    sock.close()
    # Assert
    assert "--force" not in capsys.readouterr().err


def test_port_taken_message_includes_kill_command_for_a_foreign_holder():
    # Arrange
    holder = _gui_runtime.PortHolder(
        port=31298,
        status=_gui_runtime.HOLDER_IDENTIFIED,
        pid=4242,
        name="nginx",
        argv=("nginx", "-g", "daemon off;"),
        ours=False,
    )
    # Act
    message = embed._port_taken_message("testpkg", "127.0.0.1", holder)
    # Assert
    assert "kill 4242" in message


def test_port_taken_message_never_offers_force_for_a_foreign_holder():
    # Arrange
    holder = _gui_runtime.PortHolder(
        port=31298,
        status=_gui_runtime.HOLDER_IDENTIFIED,
        pid=4242,
        name="nginx",
        argv=("nginx",),
        ours=False,
    )
    # Act
    message = embed._port_taken_message("testpkg", "127.0.0.1", holder)
    # Assert
    assert "--force" not in message


def test_port_taken_message_offers_force_for_our_own_orphan():
    # Arrange
    holder = _gui_runtime.PortHolder(
        port=31298,
        status=_gui_runtime.HOLDER_IDENTIFIED,
        pid=4242,
        name="python3",
        argv=("python3", "-m", "testpkg", "gui"),
        ours=True,
    )
    # Act
    message = embed._port_taken_message("testpkg", "127.0.0.1", holder)
    # Assert
    assert "--force" in message


def test_port_taken_message_admits_it_could_not_look_rather_than_blaming_a_user():
    # Arrange
    holder = _gui_runtime.PortHolder(port=31298, status=_gui_runtime.HOLDER_UNREADABLE)
    # Act
    message = embed._port_taken_message("testpkg", "127.0.0.1", holder)
    # Assert
    assert "another user" not in message


def test_gui_status_reports_not_running_by_default(state_file):
    # Arrange
    # Act
    result = embed.gui_status("testpkg", state_path=state_file)
    # Assert
    assert result == {"running": False}


def test_gui_port_holder_reports_free_for_an_unused_port(free_port):
    # Arrange
    # Act
    #
    # A just-released ephemeral port can be immediately re-bound by an
    # unrelated concurrently-running test worker before this line runs
    # (pytest-xdist parallelism) -- a TOCTOU race in the fixture's own
    # setup, not a defect in gui_port_holder(). Poll briefly rather than
    # asserting on a single racy sample.
    import time as _time

    holder = embed.gui_port_holder(free_port)
    attempts = 1
    while holder.in_use and attempts < 20:
        _time.sleep(0.05)
        holder = embed.gui_port_holder(free_port)
        attempts += 1
    # Assert
    assert holder.status == _gui_runtime.HOLDER_FREE


def test_gui_stop_is_idempotent_when_not_running(state_file):
    # Arrange
    # Act
    result = embed.gui_stop("testpkg", state_path=state_file)
    # Assert
    assert result == {"stopped": False, "running": False}
