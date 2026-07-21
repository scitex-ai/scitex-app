#!/usr/bin/env python3
# Timestamp: 2026-06-14
# File: tests/scitex_app/appmaker/test__scaffold.py

"""Tests for scitex_app/appmaker/_scaffold.py — nested-layout + pip-install gate.

Mirrors scitex-hub PR #293 (M4 done-gate). Without these checks the scaffold
silently emits a FLAT layout that hatchling refuses to package — every
`pip install --target=<dir> <gitea-archive-url>` call from the hub then
errors with "Unable to determine which files to ship inside the wheel".

No mocks: the pip-install test actually builds + installs the emitted
scaffold into a throwaway venv and imports the package back out.

STX-TQ002 (AAA markers) + STX-TQ007 (one assert per test) compliant.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import venv
from pathlib import Path

import pytest
from scitex_app.appmaker._scaffold import _pyproject_toml, init_app

# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------


SCAFFOLD_NAME = "demo_nested_app"


@pytest.fixture(scope="module")
def scaffolded_wrapper(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Scaffold once per test module — every layout test reads this tree."""
    wrapper = tmp_path_factory.mktemp("wrapper") / "wrapper_root"
    init_app(target_dir=wrapper, name=SCAFFOLD_NAME, label="Demo Nested")
    return wrapper


@pytest.fixture(scope="module")
def emitted_pyproject() -> str:
    """Render the pyproject template once per test module."""
    return _pyproject_toml("demo_app", "Demo", "test desc", "AGPL-3.0")


# ---------------------------------------------------------------------------
# Layout — wrapper-root files (one assert each)
# ---------------------------------------------------------------------------


WRAPPER_ROOT_FILES = (
    "pyproject.toml",
    "README.md",
    "LICENSE",
    "AGENTS.md",
    ".gitignore",
)


@pytest.mark.parametrize("relpath", WRAPPER_ROOT_FILES)
def test_wrapper_root_file_exists(scaffolded_wrapper: Path, relpath: str) -> None:
    # Arrange
    candidate = scaffolded_wrapper / relpath
    # Act
    exists = candidate.is_file()
    # Assert
    assert exists


# ---------------------------------------------------------------------------
# Layout — nested-package files (one assert each)
# ---------------------------------------------------------------------------


NESTED_PACKAGE_FILES = (
    "__init__.py",
    "apps.py",
    "views.py",
    "urls.py",
    "tests.py",
    "skill.py",
    "_cli.py",
    "manifest.json",
)


@pytest.mark.parametrize("relpath", NESTED_PACKAGE_FILES)
def test_nested_package_file_exists(scaffolded_wrapper: Path, relpath: str) -> None:
    # Arrange
    candidate = scaffolded_wrapper / SCAFFOLD_NAME / relpath
    # Act
    exists = candidate.is_file()
    # Assert
    assert exists


# ---------------------------------------------------------------------------
# Layout — nested templates / static / .agents / docs (one assert each)
# ---------------------------------------------------------------------------


def test_nested_template_index_html_exists(scaffolded_wrapper: Path) -> None:
    # Arrange
    candidate = (
        scaffolded_wrapper / SCAFFOLD_NAME / "templates" / SCAFFOLD_NAME / "index.html"
    )
    # Act
    exists = candidate.is_file()
    # Assert
    assert exists


def test_nested_template_index_partial_html_exists(
    scaffolded_wrapper: Path,
) -> None:
    # Arrange
    candidate = (
        scaffolded_wrapper
        / SCAFFOLD_NAME
        / "templates"
        / SCAFFOLD_NAME
        / "index_partial.html"
    )
    # Act
    exists = candidate.is_file()
    # Assert
    assert exists


def test_nested_static_css_exists(scaffolded_wrapper: Path) -> None:
    # Arrange
    candidate = (
        scaffolded_wrapper
        / SCAFFOLD_NAME
        / "static"
        / SCAFFOLD_NAME
        / "css"
        / f"{SCAFFOLD_NAME}.css"
    )
    # Act
    exists = candidate.is_file()
    # Assert
    assert exists


def test_nested_agents_json_exists(scaffolded_wrapper: Path) -> None:
    # Arrange
    candidate = scaffolded_wrapper / SCAFFOLD_NAME / ".agents" / "agents.json"
    # Act
    exists = candidate.is_file()
    # Assert
    assert exists


def test_nested_platform_docs_exists(scaffolded_wrapper: Path) -> None:
    # Arrange
    candidate = scaffolded_wrapper / SCAFFOLD_NAME / "docs" / "PLATFORM.md"
    # Act
    exists = candidate.is_file()
    # Assert
    assert exists


# ---------------------------------------------------------------------------
# Flat-layout regression guards (one assert each)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "flat_relpath",
    [
        "apps.py",
        "views.py",
        "urls.py",
        "__init__.py",
        "tests.py",
        "skill.py",
        "_cli.py",
        "manifest.json",
        "templates",
        "static",
        ".agents",
        "docs",
    ],
)
def test_flat_layout_path_does_not_exist(
    scaffolded_wrapper: Path, flat_relpath: str
) -> None:
    """Wrapper-root must NOT contain the python-package files — that
    would be the FLAT-layout regression the #293 fix targets."""
    # Arrange
    candidate = scaffolded_wrapper / flat_relpath
    # Act
    exists = candidate.exists()
    # Assert
    assert not exists


# ---------------------------------------------------------------------------
# pyproject.toml — hatchling wheel-packages block (one assert each)
# ---------------------------------------------------------------------------


def test_pyproject_has_hatchling_wheel_targets_section(
    emitted_pyproject: str,
) -> None:
    """Without this section hatchling can't detect the nested package
    directory and the wheel build fails with 'Unable to determine which
    files to ship inside the wheel'."""
    # Arrange
    needle = "[tool.hatch.build.targets.wheel]"
    # Act
    has_section = needle in emitted_pyproject
    # Assert
    assert has_section


def test_pyproject_declares_packages_list() -> None:
    """The packages list must reference the python module name (with
    underscores) — the package directory hatchling will ship."""
    # Arrange
    pyproject = _pyproject_toml("demo_app", "Demo", "test desc", "AGPL-3.0")
    # Act
    has_packages_decl = 'packages = ["demo_app"]' in pyproject
    # Assert
    assert has_packages_decl


# ---------------------------------------------------------------------------
# Manifest in nested location (one assert each)
# ---------------------------------------------------------------------------


def test_manifest_lands_inside_nested_package_dir(
    scaffolded_wrapper: Path,
) -> None:
    """manifest.json must be inside <name>/ so hatchling ships it with
    the wheel — and the runtime registry can find it at install-target."""
    # Arrange
    candidate = scaffolded_wrapper / SCAFFOLD_NAME / "manifest.json"
    # Act
    exists = candidate.is_file()
    # Assert
    assert exists


def test_manifest_name_field_matches_module(scaffolded_wrapper: Path) -> None:
    # Arrange
    manifest_path = scaffolded_wrapper / SCAFFOLD_NAME / "manifest.json"
    # Act
    data = json.loads(manifest_path.read_text())
    # Assert
    assert data["name"] == SCAFFOLD_NAME


# ---------------------------------------------------------------------------
# Real pip-install gate (no mocks)
# ---------------------------------------------------------------------------


def _venv_bin(venv_dir: Path) -> Path:
    return venv_dir / ("Scripts" if sys.platform == "win32" else "bin")


@pytest.fixture(scope="module")
def installed_app(tmp_path_factory: pytest.TempPathFactory) -> dict:
    """Scaffold → fresh venv → pip install → record outcomes for assertion.

    Shared across the two pip-install gate tests so the (slow) install
    only happens once per module. Returns the CompletedProcess for the
    install + the import-check CompletedProcess.
    """
    name = "demo_install_app"
    wrapper_root = tmp_path_factory.mktemp("install") / "wrapper"
    init_app(target_dir=wrapper_root, name=name, label="Demo Install")

    venv_dir = tmp_path_factory.mktemp("install") / "v"
    try:
        builder = venv.EnvBuilder(with_pip=True, clear=True)
        builder.create(str(venv_dir))
    except subprocess.CalledProcessError:
        # uv-managed CPython distributions (e.g. the self-hosted CI pool)
        # ship without a working `ensurepip`, so EnvBuilder(with_pip=True)
        # dies bootstrapping pip. Seed the venv via uv instead — same
        # result: a fresh venv whose own pip installs the scaffolded app.
        uv = shutil.which("uv")
        if uv is None:
            raise
        subprocess.run(
            [uv, "venv", "--seed", "--python", sys.executable, str(venv_dir)],
            check=True,
            capture_output=True,
        )

    pip = _venv_bin(venv_dir) / "pip"
    install_proc = subprocess.run(
        [
            str(pip),
            "install",
            "--no-deps",
            str(wrapper_root),
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    py = _venv_bin(venv_dir) / "python"
    import_proc = subprocess.run(
        [str(py), "-c", f"import {name}; print({name}.__file__)"],
        capture_output=True,
        text=True,
        check=False,
    )

    return {
        "name": name,
        "install": install_proc,
        "import_check": import_proc,
    }


@pytest.mark.slow
def test_pip_install_returncode_zero(installed_app: dict) -> None:
    """The flat-layout regression manifests as hatchling refusing to
    build the wheel — pip install then exits non-zero."""
    # Arrange
    install = installed_app["install"]
    # Act
    rc = install.returncode
    # Assert
    assert rc == 0, (
        f"pip install failed:\nstdout:\n{install.stdout}\nstderr:\n{install.stderr}"
    )


@pytest.mark.slow
def test_installed_package_importable(installed_app: dict) -> None:
    """After install, the python module must be importable from the
    installed venv — the contract `pip install --target=<dir> <pkg>`
    relies on (the hub's pip_install_user_app workflow)."""
    # Arrange
    import_check = installed_app["import_check"]
    # Act
    rc = import_check.returncode
    # Assert
    assert rc == 0, f"post-install import failed:\nstderr:\n{import_check.stderr}"
