#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Test file for: scitex_app/_gui_runtime.py

"""Tests for the shared GUI runtime-state module."""

from __future__ import annotations

import functools
import os
import socket
import subprocess
import sys
from pathlib import Path

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


def _proc_fd_is_readable() -> bool:
    """True when this process may read its OWN /proc/<pid>/fd.

    Not a mock and not a guess -- a real capability probe. Our agent
    containers deny this directory even for a same-uid process, which
    is precisely why `port_holder` must distinguish "we could not
    look" from "someone else's process".
    """
    try:
        list(Path(f"/proc/{os.getpid()}/fd").iterdir())
    except OSError:
        return False
    return True


needs_proc_fd = pytest.mark.skipif(
    not _proc_fd_is_readable(),
    reason="/proc/<pid>/fd unreadable here (agent container); holder identification "
    "is provable only where the kernel lets us map socket inodes to pids",
)
needs_denied_proc_fd = pytest.mark.skipif(
    _proc_fd_is_readable(),
    reason="/proc/<pid>/fd is readable here, so the denied-lookup path cannot occur",
)


@needs_proc_fd
def test_port_holder_identifies_our_own_listening_pid(listening_socket):
    # Arrange
    port = listening_socket.getsockname()[1]
    # Act
    holder = _gui_runtime.port_holder(port)
    # Assert
    assert holder.pid == os.getpid()


@needs_proc_fd
def test_port_holder_reports_the_holder_argv(listening_socket):
    # Arrange
    port = listening_socket.getsockname()[1]
    # Act
    holder = _gui_runtime.port_holder(port)
    # Assert
    assert holder.argv


@needs_denied_proc_fd
def test_port_holder_reports_unreadable_rather_than_blaming_another_user(listening_socket):
    # Arrange
    port = listening_socket.getsockname()[1]
    # Act
    holder = _gui_runtime.port_holder(port)
    # Assert
    assert holder.status == _gui_runtime.HOLDER_UNREADABLE


@needs_denied_proc_fd
def test_unreadable_holder_never_claims_to_know_whose_it_is(listening_socket):
    # Arrange
    port = listening_socket.getsockname()[1]
    # Act
    holder = _gui_runtime.port_holder(port, "scitex_app")
    # Assert
    assert holder.ours is None


def test_port_holder_reports_free_when_nothing_listens():
    # Arrange
    probe = socket.socket()
    probe.bind(("127.0.0.1", 0))
    free_port = probe.getsockname()[1]
    probe.close()
    # Act
    #
    # A just-released ephemeral port can be immediately re-bound by an
    # unrelated concurrently-running test worker before this line runs
    # (pytest-xdist parallelism on a low-core CI runner) -- a real TOCTOU
    # race in the test's own setup, not a defect in port_holder(). Poll
    # briefly rather than asserting on a single racy sample.
    import time as _time

    holder = _gui_runtime.port_holder(free_port)
    attempts = 1
    while holder.in_use and attempts < 20:
        _time.sleep(0.05)
        holder = _gui_runtime.port_holder(free_port)
        attempts += 1
    # Assert
    assert holder.status == _gui_runtime.HOLDER_FREE


# =============================================================================
# Ownership is proven from ARGV, never from the process NAME -- a `comm` of
# "python" is shared by every Python server on the box, so killing on that
# basis would kill strangers.
# =============================================================================


def test_argv_proves_ownership_for_a_module_run():
    # Arrange
    argv = ("/usr/bin/python3", "-m", "scitex_writer", "gui")
    # Act
    ours = _gui_runtime.argv_is_ours(argv, "scitex-writer")
    # Assert
    assert ours is True


def test_argv_proves_ownership_from_an_installed_script_path():
    # Arrange
    argv = ("/opt/venv/lib/python3.12/site-packages/scitex_writer/__main__.py",)
    # Act
    ours = _gui_runtime.argv_is_ours(argv, "scitex_writer")
    # Assert
    assert ours is True


def test_argv_does_not_claim_a_merely_similar_name():
    # Arrange
    argv = ("/usr/bin/python3", "-m", "myscitex_writerx")
    # Act
    ours = _gui_runtime.argv_is_ours(argv, "scitex-writer")
    # Assert
    assert ours is False


def test_a_bare_interpreter_name_proves_nothing():
    # Arrange
    argv = ("python",)
    # Act
    ours = _gui_runtime.argv_is_ours(argv, "scitex-writer")
    # Assert
    assert ours is False


def test_empty_argv_proves_nothing():
    # Arrange
    argv = ()
    # Act
    ours = _gui_runtime.argv_is_ours(argv, "scitex-writer")
    # Assert
    assert ours is False


# -----------------------------------------------------------------------------
# argv[0] is the INTERPRETER, not the program. A project-local venv puts the
# project name in that path, so scanning it whole claimed every process started
# from that venv as ours -- and `terminate` fires on `ours`, so --force could
# SIGTERM a stranger. Reported by scitex-scholar 2026-08-04, reproduced with
# only argv[0] differing. These pin the boundary from BOTH sides: a distant
# ancestor is not evidence, the immediate parent still is.
# -----------------------------------------------------------------------------


def test_a_venv_interpreter_under_a_package_named_directory_is_not_ours():
    # Arrange
    argv = ("/home/x/scitex-scholar/.venv/bin/python", "/tmp/bind_and_sleep.py")
    # Act
    ours = _gui_runtime.argv_is_ours(argv, "scitex-scholar")
    # Assert
    assert ours is False


def test_pytest_run_from_a_package_named_venv_is_not_ours():
    # Arrange
    argv = ("/home/x/scitex-scholar/.venv/bin/python", "-m", "pytest")
    # Act
    ours = _gui_runtime.argv_is_ours(argv, "scitex-scholar")
    # Assert
    assert ours is False


def test_a_foreign_console_script_in_a_package_named_venv_is_not_ours():
    """The same defect wearing a console script instead of `python`."""
    # Arrange
    argv = ("/home/x/scitex-scholar/.venv/bin/jupyter",)
    # Act
    ours = _gui_runtime.argv_is_ours(argv, "scitex-scholar")
    # Assert
    assert ours is False


def test_the_immediate_parent_directory_still_proves_ownership():
    """The other side of the boundary: one level up is what the program IS."""
    # Arrange
    argv = ("/opt/venv/lib/python3.12/site-packages/scitex_writer/__main__.py",)
    # Act
    ours = _gui_runtime.argv_is_ours(argv, "scitex-writer")
    # Assert
    assert ours is True


def test_our_own_console_script_is_still_ours_from_any_bin_directory():
    # Arrange
    argv = ("/usr/local/bin/scitex-writer-gui", "--port", "7777")
    # Act
    ours = _gui_runtime.argv_is_ours(argv, "scitex-writer")
    # Assert
    assert ours is True


# =============================================================================
# PortHolder validates its own shape, so a malformed answer fails where it is
# built rather than three layers downstream.
# =============================================================================


def test_identified_holder_without_a_pid_is_rejected():
    # Arrange
    build = functools.partial(
        _gui_runtime.PortHolder, port=31298, status=_gui_runtime.HOLDER_IDENTIFIED
    )
    # Act
    raised = pytest.raises(ValueError)
    # Assert
    with raised:
        build()


def test_unreadable_holder_carrying_an_ownership_verdict_is_rejected():
    # Arrange
    build = functools.partial(
        _gui_runtime.PortHolder,
        port=31298,
        status=_gui_runtime.HOLDER_UNREADABLE,
        ours=False,
    )
    # Act
    raised = pytest.raises(ValueError)
    # Assert
    with raised:
        build()


def test_an_undeclared_status_is_rejected():
    # Arrange
    build = functools.partial(_gui_runtime.PortHolder, port=31298, status="probably-fine")
    # Act
    raised = pytest.raises(ValueError)
    # Assert
    with raised:
        build()


# =============================================================================
# terminate -- the primitive --force uses to reclaim an orphan of our own.
# =============================================================================


def test_terminate_stops_a_live_process():
    # Arrange
    child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"])
    # Act
    result = _gui_runtime.terminate(child.pid, timeout=5.0)
    child.wait(timeout=5)
    # Assert
    assert result["terminated"] is True


def test_terminate_is_idempotent_on_an_already_dead_process():
    # Arrange
    child = subprocess.Popen([sys.executable, "-c", ""])
    child.wait(timeout=5)
    # Act
    result = _gui_runtime.terminate(child.pid, timeout=5.0)
    # Assert
    assert result["signalled"] is False
