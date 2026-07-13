#!/usr/bin/env python3
# Timestamp: 2026-07-13
# File: tests/scitex_app/test_embed_gui.py

"""Tests for scitex_app.embed's shared GUI launcher (serve_gui + friends)."""

from __future__ import annotations

import socket

import pytest

from scitex_app import embed


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


def test_port_taken_message_includes_kill_command_for_known_holder():
    # Arrange
    sock = socket.socket()
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind(("127.0.0.1", 0))
    sock.listen(1)
    port = sock.getsockname()[1]
    # Act
    message = embed._port_taken_message("testpkg", "127.0.0.1", port)
    sock.close()
    # Assert
    assert "kill" in message


def test_gui_status_reports_not_running_by_default(state_file):
    # Arrange
    # Act
    result = embed.gui_status("testpkg", state_path=state_file)
    # Assert
    assert result == {"running": False}


def test_gui_port_holder_returns_none_for_free_port(free_port):
    # Arrange
    # Act
    holder = embed.gui_port_holder(free_port)
    # Assert
    assert holder is None


def test_gui_stop_is_idempotent_when_not_running(state_file):
    # Arrange
    # Act
    result = embed.gui_stop("testpkg", state_path=state_file)
    # Assert
    assert result == {"stopped": False, "running": False}
