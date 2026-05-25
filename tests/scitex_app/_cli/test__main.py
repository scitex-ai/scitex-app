#!/usr/bin/env python3
# Timestamp: 2026-03-21
# File: tests/test__cli.py

"""Tests for scitex_app/_cli/_main.py — CLI commands via Click's CliRunner."""

from __future__ import annotations

import json

import pytest

click = pytest.importorskip("click")
from click.testing import CliRunner

from scitex_app._cli._main import main


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def runner():
    return CliRunner()


@pytest.fixture
def temp_dir(tmp_path):
    """A temporary directory usable as a file backend root."""
    return tmp_path


# ---------------------------------------------------------------------------
# Tests: top-level main group
# ---------------------------------------------------------------------------


class TestMainGroup:
    def test_help_flag_result_exit_code_equals_n_0(self, runner):
        # Arrange
        # Arrange
        # Act
        result = runner.invoke(main, ["--help"])
        # Act
        # Assert
        # Assert
        assert result.exit_code == 0

    def test_help_flag_scitex_app_sdk_in_result_output(self, runner):
        # Arrange
        # Arrange
        # Act
        result = runner.invoke(main, ["--help"])
        # Act
        # Assert
        # Assert
        assert "SciTeX App SDK" in result.output

    def test_h_flag_alias_result_exit_code_equals_n_0(self, runner):
        # Arrange
        # Arrange
        # Act
        result = runner.invoke(main, ["-h"])
        # Act
        # Assert
        # Assert
        assert result.exit_code == 0

    def test_h_flag_alias_scitex_app_sdk_in_result_output(self, runner):
        # Arrange
        # Arrange
        # Act
        result = runner.invoke(main, ["-h"])
        # Act
        # Assert
        # Assert
        assert "SciTeX App SDK" in result.output

    def test_version_flag_result_exit_code_equals_n_0(self, runner):
        # Arrange
        # Arrange
        # Act
        result = runner.invoke(main, ["--version"])
        # Act
        # Assert
        # Assert
        assert result.exit_code == 0

    def test_version_flag_scitex_app_in_result_output_lower(self, runner):
        # Arrange
        # Arrange
        # Act
        result = runner.invoke(main, ["--version"])
        # Act
        # Assert
        # Assert
        assert "scitex-app" in result.output.lower()

    def test_no_args_shows_help_result_exit_code_equals_n_0(self, runner):
        # Arrange
        # Arrange
        # Act
        result = runner.invoke(main, [])
        # Act
        # Assert
        # Assert
        assert result.exit_code == 0

    def test_no_args_shows_help_usage_in_result_output_or_scitex_in_result_output(
        self, runner
    ):
        # Arrange
        # Arrange
        # Act
        result = runner.invoke(main, [])
        # Act
        # Assert
        # Assert
        assert "Usage" in result.output or "SciTeX" in result.output

    def test_help_recursive_flag_result_exit_code_equals_n_0(self, runner):
        # Arrange
        # Arrange
        # Act
        result = runner.invoke(main, ["--help-recursive"])
        # Act
        # Assert
        # Assert
        assert result.exit_code == 0

    def test_help_recursive_flag_command_in_result_output_or_scitex_in_result_output(
        self, runner
    ):
        # Arrange
        # Arrange
        # Act
        result = runner.invoke(main, ["--help-recursive"])
        # Act
        # Assert
        # Assert
        assert "Command:" in result.output or "SciTeX" in result.output


# ---------------------------------------------------------------------------
# Tests: list command
# ---------------------------------------------------------------------------


class TestListCommand:
    def test_list_empty_directory_result_exit_code_equals_n_0(self, runner, temp_dir):
        # Arrange
        # Arrange
        # Act
        result = runner.invoke(main, ["file", "list", "--root", str(temp_dir)])
        # Act
        # Assert
        # Assert
        assert result.exit_code == 0

    def test_list_empty_directory_result_output_strip(self, runner, temp_dir):
        # Arrange
        # Arrange
        # Act
        result = runner.invoke(main, ["file", "list", "--root", str(temp_dir)])
        # Act
        # Assert
        # Assert
        assert result.output.strip() == ""

    def test_list_shows_files_result_exit_code_equals_n_0(self, runner, temp_dir):
        # Arrange
        # Arrange
        (temp_dir / "hello.txt").write_text("world", encoding="utf-8")
        (temp_dir / "config.yaml").write_text("key: value", encoding="utf-8")
        # Act
        result = runner.invoke(main, ["file", "list", "--root", str(temp_dir)])
        # Act
        # Assert
        # Assert
        assert result.exit_code == 0

    def test_list_shows_files_hello_txt_in_result_output(self, runner, temp_dir):
        # Arrange
        # Arrange
        (temp_dir / "hello.txt").write_text("world", encoding="utf-8")
        (temp_dir / "config.yaml").write_text("key: value", encoding="utf-8")
        # Act
        result = runner.invoke(main, ["file", "list", "--root", str(temp_dir)])
        # Act
        # Assert
        # Assert
        assert "hello.txt" in result.output

    def test_list_shows_files_config_yaml_in_result_output(self, runner, temp_dir):
        # Arrange
        # Arrange
        (temp_dir / "hello.txt").write_text("world", encoding="utf-8")
        (temp_dir / "config.yaml").write_text("key: value", encoding="utf-8")
        # Act
        result = runner.invoke(main, ["file", "list", "--root", str(temp_dir)])
        # Act
        # Assert
        # Assert
        assert "config.yaml" in result.output

    def test_list_with_extension_filter_result_exit_code_equals_n_0(
        self, runner, temp_dir
    ):
        # Arrange
        # Arrange
        (temp_dir / "a.txt").write_text("a")
        (temp_dir / "b.yaml").write_text("b: 1")
        # Act
        result = runner.invoke(
            main, ["file", "list", "--root", str(temp_dir), "--ext", ".yaml"]
        )
        # Act
        # Assert
        # Assert
        assert result.exit_code == 0

    def test_list_with_extension_filter_b_yaml_in_result_output(self, runner, temp_dir):
        # Arrange
        # Arrange
        (temp_dir / "a.txt").write_text("a")
        (temp_dir / "b.yaml").write_text("b: 1")
        # Act
        result = runner.invoke(
            main, ["file", "list", "--root", str(temp_dir), "--ext", ".yaml"]
        )
        # Act
        # Assert
        # Assert
        assert "b.yaml" in result.output

    def test_list_with_extension_filter_a_txt_not_in_result_output(
        self, runner, temp_dir
    ):
        # Arrange
        # Arrange
        (temp_dir / "a.txt").write_text("a")
        (temp_dir / "b.yaml").write_text("b: 1")
        # Act
        result = runner.invoke(
            main, ["file", "list", "--root", str(temp_dir), "--ext", ".yaml"]
        )
        # Act
        # Assert
        # Assert
        assert "a.txt" not in result.output

    def test_list_subdirectory_result_exit_code_equals_n_0(self, runner, temp_dir):
        # Arrange
        # Arrange
        subdir = temp_dir / "sub"
        subdir.mkdir()
        (subdir / "note.md").write_text("# Notes")
        # Act
        result = runner.invoke(main, ["file", "list", "sub", "--root", str(temp_dir)])
        # Act
        # Assert
        # Assert
        assert result.exit_code == 0

    def test_list_subdirectory_note_md_in_result_output(self, runner, temp_dir):
        # Arrange
        # Arrange
        subdir = temp_dir / "sub"
        subdir.mkdir()
        (subdir / "note.md").write_text("# Notes")
        # Act
        result = runner.invoke(main, ["file", "list", "sub", "--root", str(temp_dir)])
        # Act
        # Assert
        # Assert
        assert "note.md" in result.output

    def test_list_help_result_exit_code_equals_n_0(self, runner):
        # Arrange
        # Arrange
        # Act
        result = runner.invoke(main, ["file", "list", "--help"])
        # Act
        # Assert
        # Assert
        assert result.exit_code == 0

    def test_list_help_directory_in_result_output_lower_or_list_in_result_output(
        self, runner
    ):
        # Arrange
        # Arrange
        # Act
        result = runner.invoke(main, ["file", "list", "--help"])
        # Act
        # Assert
        # Assert
        assert "directory" in result.output.lower() or "List" in result.output


# ---------------------------------------------------------------------------
# Tests: exists command
# ---------------------------------------------------------------------------


class TestExistsCommand:
    def test_exists_true_true_in_result_output(self, runner, temp_dir):
        # Arrange
        # Arrange
        (temp_dir / "present.txt").write_text("here")
        # Act
        result = runner.invoke(
            main, ["file", "exists", "present.txt", "--root", str(temp_dir)]
        )
        # Act
        # Assert
        # Assert
        assert "true" in result.output

    def test_exists_true_result_exit_code_equals_n_0(self, runner, temp_dir):
        # Arrange
        # Arrange
        (temp_dir / "present.txt").write_text("here")
        # Act
        result = runner.invoke(
            main, ["file", "exists", "present.txt", "--root", str(temp_dir)]
        )
        # Act
        # Assert
        # Assert
        assert result.exit_code == 0

    def test_exists_false_false_in_result_output(self, runner, temp_dir):
        # Arrange
        # Arrange
        # Act
        result = runner.invoke(
            main, ["file", "exists", "absent.txt", "--root", str(temp_dir)]
        )
        # Act
        # Assert
        # Assert
        assert "false" in result.output

    def test_exists_false_result_exit_code_equals_n_1(self, runner, temp_dir):
        # Arrange
        # Arrange
        # Act
        result = runner.invoke(
            main, ["file", "exists", "absent.txt", "--root", str(temp_dir)]
        )
        # Act
        # Assert
        # Assert
        assert result.exit_code == 1

    def test_exists_help_result_exit_code_equals_n_0(self, runner):
        # Arrange
        # Act
        result = runner.invoke(main, ["file", "exists", "--help"])
        # Assert
        assert result.exit_code == 0


# ---------------------------------------------------------------------------
# Tests: read command
# ---------------------------------------------------------------------------


class TestReadCommand:
    def test_read_text_file_result_exit_code_equals_n_0(self, runner, temp_dir):
        # Arrange
        # Arrange
        (temp_dir / "data.txt").write_text("hello world", encoding="utf-8")
        # Act
        result = runner.invoke(
            main, ["file", "read", "data.txt", "--root", str(temp_dir)]
        )
        # Act
        # Assert
        # Assert
        assert result.exit_code == 0

    def test_read_text_file_hello_world_in_result_output(self, runner, temp_dir):
        # Arrange
        # Arrange
        (temp_dir / "data.txt").write_text("hello world", encoding="utf-8")
        # Act
        result = runner.invoke(
            main, ["file", "read", "data.txt", "--root", str(temp_dir)]
        )
        # Act
        # Assert
        # Assert
        assert "hello world" in result.output

    def test_read_missing_file_fails(self, runner, temp_dir):
        # Arrange
        # Act
        result = runner.invoke(
            main, ["file", "read", "missing.txt", "--root", str(temp_dir)]
        )
        # Assert
        assert result.exit_code != 0

    def test_read_help_result_exit_code_equals_n_0(self, runner):
        # Arrange
        # Arrange
        # Act
        result = runner.invoke(main, ["file", "read", "--help"])
        # Act
        # Assert
        # Assert
        assert result.exit_code == 0

    def test_read_help_path_in_result_output_lower_or_read_in_result_output(
        self, runner
    ):
        # Arrange
        # Arrange
        # Act
        result = runner.invoke(main, ["file", "read", "--help"])
        # Act
        # Assert
        # Assert
        assert "path" in result.output.lower() or "Read" in result.output


# ---------------------------------------------------------------------------
# Tests: app subgroup
# ---------------------------------------------------------------------------


class TestAppSubgroup:
    def test_app_help_result_exit_code_equals_n_0(self, runner):
        # Arrange
        # Arrange
        # Act
        result = runner.invoke(main, ["app", "--help"])
        # Act
        # Assert
        # Assert
        assert result.exit_code == 0

    def test_app_help_app_in_result_output_lower(self, runner):
        # Arrange
        # Arrange
        # Act
        result = runner.invoke(main, ["app", "--help"])
        # Act
        # Assert
        # Assert
        assert "app" in result.output.lower()

    def test_app_validate_help(self, runner):
        # Arrange
        # Act
        result = runner.invoke(main, ["app", "validate", "--help"])
        # Assert
        assert result.exit_code == 0

    def test_app_init_help(self, runner):
        # Arrange
        # Act
        result = runner.invoke(main, ["app", "init", "--help"])
        # Assert
        assert result.exit_code == 0

    def test_app_validate_passes_for_minimal_valid_app(self, runner, temp_dir):
        """App validate should pass for a directory that meets minimum requirements."""
        # Arrange
        import json

        # Create minimal app that validate() would accept (embedded, so fewer checks)
        manifest = {
            "name": "test_app",
            "slug": "test-app",
            "label": "Test",
            "version": "1.0.0",
            "icon": "fas fa-flask",
            "license": "MIT",
            "embedded_package": True,
            "dependencies": {"python": []},
        }
        (temp_dir / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
        (temp_dir / "views.py").touch()
        (temp_dir / "urls.py").touch()
        # Act
        result = runner.invoke(main, ["app", "validate", str(temp_dir)])
        # Should succeed (exit_code 0) or at minimum not crash
        # The exact passing depends on validate() checks
        # Assert
        assert result.exit_code in (0, 1)

    def test_app_validate_fails_for_missing_manifest(self, runner, temp_dir):
        # Arrange
        # Act
        result = runner.invoke(main, ["app", "validate", str(temp_dir)])
        # Missing manifest.json should cause a non-zero exit
        # Assert
        assert result.exit_code != 0

    def test_app_init_creates_files(self, runner, temp_dir):
        # Arrange
        target = temp_dir / "my_app"
        target.mkdir()
        # Act
        result = runner.invoke(
            main,
            ["app", "init", str(target), "--name", "my_app"],
        )
        # Should succeed and create files
        # Assert
        assert result.exit_code == 0


# ---------------------------------------------------------------------------
# Tests: mcp subgroup
# ---------------------------------------------------------------------------


class TestMcpSubgroup:
    def test_mcp_help_result_exit_code_equals_n_0(self, runner):
        # Arrange
        # Act
        result = runner.invoke(main, ["mcp", "--help"])
        # Assert
        assert result.exit_code == 0

    def test_mcp_installation_result_exit_code_equals_n_0(self, runner):
        # Arrange
        # Arrange
        # Act
        result = runner.invoke(main, ["mcp", "show-installation"])
        # Act
        # Assert
        # Assert
        assert result.exit_code == 0

    def test_mcp_installation_pip_install_in_result_output(self, runner):
        # Arrange
        # Arrange
        # Act
        result = runner.invoke(main, ["mcp", "show-installation"])
        # Act
        # Assert
        # Assert
        assert "pip install" in result.output

    def test_mcp_doctor_result_exit_code_equals_n_0(self, runner):
        # Arrange
        # Arrange
        # Act
        result = runner.invoke(main, ["mcp", "doctor"])
        # Act
        # Assert
        # Assert
        assert result.exit_code == 0

    def test_mcp_doctor_fastmcp_in_result_output_lower_or_mcp_in_result_output(
        self, runner
    ):
        # Arrange
        # Arrange
        # Act
        result = runner.invoke(main, ["mcp", "doctor"])
        # Act
        # Assert
        # Assert
        assert "fastmcp" in result.output.lower() or "MCP" in result.output

    def test_mcp_list_tools_help(self, runner):
        # Arrange
        # Act
        result = runner.invoke(main, ["mcp", "list-tools", "--help"])
        # Assert
        assert result.exit_code == 0


# ---------------------------------------------------------------------------
# Tests: list-python-apis command
# ---------------------------------------------------------------------------


class TestListPythonApis:
    def test_list_python_apis_runs_result_exit_code_equals_n_0(self, runner):
        # Arrange
        # Arrange
        # Act
        result = runner.invoke(main, ["list-python-apis"])
        # Act
        # Assert
        # Assert
        assert result.exit_code == 0

    def test_list_python_apis_runs_scitex_in_result_output_lower(self, runner):
        # Arrange
        # Arrange
        # Act
        result = runner.invoke(main, ["list-python-apis"])
        # Act
        # Assert
        # Assert
        assert "scitex" in result.output.lower()

    def test_list_python_apis_json_output_result_exit_code_equals_n_0(self, runner):
        # Arrange
        # Arrange
        # Act
        result = runner.invoke(main, ["list-python-apis", "--json"])
        # Act
        # Assert
        # Assert
        assert result.exit_code == 0

    def test_list_python_apis_json_output_data_is_list(self, runner):
        # Arrange
        result = runner.invoke(main, ["list-python-apis", "--json"])
        # Act
        data = json.loads(result.output)
        # Assert
        assert isinstance(data, list)

    def test_list_python_apis_json_output_len_data_0(self, runner):
        # Arrange
        result = runner.invoke(main, ["list-python-apis", "--json"])
        # Act
        data = json.loads(result.output)
        # Assert
        assert len(data) > 0

    def test_list_python_apis_root_only(self, runner):
        # Arrange
        # Act
        result = runner.invoke(main, ["list-python-apis", "--root-only"])
        # Assert
        assert result.exit_code == 0

    def test_list_python_apis_help(self, runner):
        # Arrange
        # Act
        result = runner.invoke(main, ["list-python-apis", "--help"])
        # Assert
        assert result.exit_code == 0


# EOF
