#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Test file for: scitex_app/_gui_runtime.py

"""Tests for the shared GUI runtime-state module."""

from __future__ import annotations

import os
import socket
import subprocess
import sys

import pytest

from scitex_app import _gui_runtime


@pytest.fixture
def state_file(tmp_path):
    return tmp_path / "gui.json"


@pytest.fixture
def gui_state_env():
    """Set/restore a package's GUI-state override env var around a test.

    Real env-var manipulation (not a mock): yields a setter; whatever
    was there before is restored on teardown so tests don't leak state.
    """
    touched: list[str] = []
    saved: dict[str, str | None] = {}

    def _set(package, value):
        env_name = _gui_runtime.state_path_env_var(package)
        if env_name not in saved:
            saved[env_name] = os.environ.get(env_name)
            touched.append(env_name)
        if value is None:
            os.environ.pop(env_name, None)
        else:
            os.environ[env_name] = str(value)

    try:
        yield _set
    finally:
        for env_name in touched:
            if saved[env_name] is None:
                os.environ.pop(env_name, None)
            else:
                os.environ[env_name] = saved[env_name]


def test_state_path_includes_package_name():
    # Arrange
    # Act
    path = _gui_runtime.state_path("scitex-app-test-pkg")
    # Assert
    assert "scitex-app-test-pkg" in str(path)


def test_state_path_env_var_matches_writer_convention():
    # Arrange
    # Act
    env_name = _gui_runtime.state_path_env_var("writer")
    # Assert
    assert env_name == "SCITEX_WRITER_GUI_STATE"


def test_state_path_honours_env_override(tmp_path, gui_state_env):
    # Arrange
    override = tmp_path / "custom.json"
    gui_state_env("scitex-app-test-pkg", override)
    # Act
    path = _gui_runtime.state_path("scitex-app-test-pkg")
    # Assert
    assert path == override


def test_state_path_falls_back_when_env_unset(gui_state_env):
    # Arrange
    gui_state_env("scitex-app-test-pkg", None)
    # Act
    path = _gui_runtime.state_path("scitex-app-test-pkg")
    # Assert
    assert "scitex-app-test-pkg" in str(path)


def test_read_state_missing_returns_none(state_file):
    # Arrange
    # (state_file is never created)
    # Act
    result = _gui_runtime.read_state(state_file)
    # Assert
    assert result is None


def test_read_state_corrupt_returns_none(state_file):
    # Arrange
    state_file.write_text("{not json")
    # Act
    result = _gui_runtime.read_state(state_file)
    # Assert
    assert result is None


def test_write_state_roundtrips_fields(state_file):
    # Arrange
    _gui_runtime.write_state(123, 31298, "127.0.0.1", "/proj", state_file)
    # Act
    state = _gui_runtime.read_state(state_file)
    # Assert
    assert (state["pid"], state["port"], state["host"], state["project"]) == (
        123,
        31298,
        "127.0.0.1",
        "/proj",
    )


def test_write_state_records_started_at(state_file):
    # Arrange
    _gui_runtime.write_state(123, 31298, "127.0.0.1", "/proj", state_file)
    # Act
    state = _gui_runtime.read_state(state_file)
    # Assert
    assert state["started_at"]


def test_clear_state_is_idempotent(state_file):
    # Arrange
    _gui_runtime.clear_state(state_file)
    # Act
    _gui_runtime.clear_state(state_file)
    # Assert
    assert not state_file.exists()


def test_pid_alive_true_for_own_process():
    # Arrange
    pid = os.getpid()
    # Act
    alive = _gui_runtime.pid_alive(pid)
    # Assert
    assert alive


def test_pid_alive_false_for_invalid_pid():
    # Arrange
    pid = -1
    # Act
    alive = _gui_runtime.pid_alive(pid)
    # Assert
    assert not alive


def test_pid_alive_false_for_exited_child():
    # Arrange
    child = subprocess.Popen([sys.executable, "-c", ""])
    child.wait()
    # Act
    alive = _gui_runtime.pid_alive(child.pid)
    # Assert
    assert not alive


def test_status_missing_state_reports_not_running(state_file):
    # Arrange
    # (state_file is never created)
    # Act
    result = _gui_runtime.status(state_file)
    # Assert
    assert result == {"running": False}


def test_status_live_pid_reports_running_url(state_file):
    # Arrange
    _gui_runtime.write_state(os.getpid(), 31298, "127.0.0.1", "/proj", state_file)
    # Act
    result = _gui_runtime.status(state_file)
    # Assert
    assert result["url"] == "http://127.0.0.1:31298"


def test_status_dead_pid_self_heals_state(state_file):
    # Arrange
    child = subprocess.Popen([sys.executable, "-c", ""])
    child.wait()
    _gui_runtime.write_state(child.pid, 31298, "127.0.0.1", "/proj", state_file)
    # Act
    result = _gui_runtime.status(state_file)
    # Assert
    assert result["stale_state_cleared"] and not state_file.exists()


def test_stop_without_state_is_idempotent(state_file):
    # Arrange
    # (state_file is never created)
    # Act
    result = _gui_runtime.stop(state_file)
    # Assert
    assert result == {"stopped": False, "running": False}


def test_stop_terminates_recorded_process(state_file):
    # Arrange
    child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"])
    _gui_runtime.write_state(child.pid, 31298, "127.0.0.1", "/proj", state_file)
    # Act
    result = _gui_runtime.stop(state_file, timeout=5.0)
    child.wait(timeout=5)
    # Assert
    assert result["stopped"] and result["terminated"]


def test_stop_clears_state_file(state_file):
    # Arrange
    child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"])
    _gui_runtime.write_state(child.pid, 31298, "127.0.0.1", "/proj", state_file)
    # Act
    _gui_runtime.stop(state_file, timeout=5.0)
    child.wait(timeout=5)
    # Assert
    assert not state_file.exists()


# =============================================================================
# port_holder -- reads /proc, so the "who has my port" hint survives in a
# container with no `ss` and no `lsof`.
# =============================================================================


@pytest.fixture
def listening_socket():
    """A real LISTEN socket on an OS-assigned port, held by THIS process."""
    sock = socket.socket()
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind(("127.0.0.1", 0))
    sock.listen(1)
    yield sock
    sock.close()


def test_port_holder_finds_our_own_listening_pid(listening_socket):
    # Arrange
    port = listening_socket.getsockname()[1]
    # Act
    holder = _gui_runtime.port_holder(port)
    # Assert
    assert holder["pid"] == os.getpid()


def test_port_holder_reports_the_process_name(listening_socket):
    # Arrange
    port = listening_socket.getsockname()[1]
    # Act
    holder = _gui_runtime.port_holder(port)
    # Assert
    assert holder["name"]


def test_port_holder_returns_none_when_port_is_free():
    # Arrange
    probe = socket.socket()
    probe.bind(("127.0.0.1", 0))
    free_port = probe.getsockname()[1]
    probe.close()
    # Act
    holder = _gui_runtime.port_holder(free_port)
    # Assert
    assert holder is None
