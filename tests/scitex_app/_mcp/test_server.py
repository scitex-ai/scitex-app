#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tests for scitex_app/_mcp/server.py — FastMCP tool registration + dispatch.

Covers the file-ops tool wrappers (read/write/list/exists/delete/copy/rename)
and the lifecycle/skills introspection tools without standing up an actual
MCP transport — we invoke each `@mcp.tool()`-decorated callable directly
via FastMCP's tool registry.
"""

from __future__ import annotations

import asyncio
import json

import pytest

pytest.importorskip("fastmcp")

from scitex_app._mcp import server


def _call_tool(_tool_name: str, **kwargs):
    """Invoke a registered MCP tool by name and return its raw value."""
    return asyncio.run(server.mcp.call_tool(_tool_name, kwargs))


def _unwrap(result):
    """FastMCP wraps tool returns in ToolResult — unwrap to the python value."""
    if hasattr(result, "structured_content"):
        sc = result.structured_content
        if isinstance(sc, dict) and "result" in sc:
            return sc["result"]
        return sc
    return result


def test_app_write_then_read_roundtrip_hello_txt_in_str_write_msg(tmp_path):
    # Arrange
    # Arrange
    # Act
    write_msg = _unwrap(
        _call_tool("app_write_file", path="hello.txt", content="hi", root=str(tmp_path))
    )
    # Act
    # Assert
    # Assert
    assert "hello.txt" in str(write_msg)


def test_app_write_then_read_roundtrip_content_equals_hi(tmp_path):
    # Arrange
    # Arrange
    # Act
    write_msg = _unwrap(
        _call_tool("app_write_file", path="hello.txt", content="hi", root=str(tmp_path))
    )
    # Assert
    assert "hello.txt" in str(write_msg)
    content = _unwrap(_call_tool("app_read_file", path="hello.txt", root=str(tmp_path)))
    # Act
    # Assert
    assert content == "hi"




def test_app_list_files_filters_by_extension_b_yaml_in_files(tmp_path):
    # Arrange
    # Arrange
    (tmp_path / "a.txt").write_text("x")
    (tmp_path / "b.yaml").write_text("y: 1")
    # Act
    files = _unwrap(
        _call_tool(
            "app_list_files", directory="", root=str(tmp_path), extensions=[".yaml"]
        )
    )
    # Act
    # Assert
    # Assert
    assert "b.yaml" in files


def test_app_list_files_filters_by_extension_a_txt_not_in_files(tmp_path):
    # Arrange
    # Arrange
    (tmp_path / "a.txt").write_text("x")
    (tmp_path / "b.yaml").write_text("y: 1")
    # Act
    files = _unwrap(
        _call_tool(
            "app_list_files", directory="", root=str(tmp_path), extensions=[".yaml"]
        )
    )
    # Act
    # Assert
    # Assert
    assert "a.txt" not in files




def test_app_file_exists_true_and_false_unwrap_call_tool_app_file_exists_path_x_txt_root_str_tmp_pat(tmp_path):
    # Arrange
    # Arrange
    # Act
    (tmp_path / "x.txt").write_text("here")
    # Act
    # Assert
    # Assert
    assert (
        _unwrap(_call_tool("app_file_exists", path="x.txt", root=str(tmp_path))) is True
    )


def test_app_file_exists_true_and_false_unwrap_call_tool_app_file_exists_path_missing_txt_root_str_t(tmp_path):
    # Arrange
    # Arrange
    # Act
    (tmp_path / "x.txt").write_text("here")
    # Act
    # Assert
    # Assert
    assert (
        _unwrap(_call_tool("app_file_exists", path="missing.txt", root=str(tmp_path)))
        is False
    )




def test_app_copy_then_delete_tmp_path_dst_txt_read_text_data(tmp_path):
    # Arrange
    # Arrange
    (tmp_path / "src.txt").write_text("data")
    # Act
    _call_tool(
        "app_copy_file", src_path="src.txt", dest_path="dst.txt", root=str(tmp_path)
    )
    # Act
    # Assert
    # Assert
    assert (tmp_path / "dst.txt").read_text() == "data"


def test_app_copy_then_delete_not_tmp_path_dst_txt_exists(tmp_path):
    # Arrange
    # Arrange
    (tmp_path / "src.txt").write_text("data")
    # Act
    _call_tool(
        "app_copy_file", src_path="src.txt", dest_path="dst.txt", root=str(tmp_path)
    )
    # Assert
    assert (tmp_path / "dst.txt").read_text() == "data"
    _call_tool("app_delete_file", path="dst.txt", root=str(tmp_path))
    # Act
    # Assert
    assert not (tmp_path / "dst.txt").exists()




def test_app_rename_file_not_tmp_path_old_txt_exists(tmp_path):
    # Arrange
    # Arrange
    (tmp_path / "old.txt").write_text("data")
    # Act
    _call_tool(
        "app_rename_file", old_path="old.txt", new_path="new.txt", root=str(tmp_path)
    )
    # Act
    # Assert
    # Assert
    assert not (tmp_path / "old.txt").exists()


def test_app_rename_file_tmp_path_new_txt_read_text_data(tmp_path):
    # Arrange
    # Arrange
    (tmp_path / "old.txt").write_text("data")
    # Act
    _call_tool(
        "app_rename_file", old_path="old.txt", new_path="new.txt", root=str(tmp_path)
    )
    # Act
    # Assert
    # Assert
    assert (tmp_path / "new.txt").read_text() == "data"




def test_app_validate_returns_error_envelope_for_empty_dir_payload_success_is_false(tmp_path):
    # Arrange
    # Arrange
    raw = _unwrap(_call_tool("app_validate", app_dir=str(tmp_path)))
    # Act
    payload = json.loads(raw)
    # Act
    # Assert
    # Assert
    assert payload["success"] is False


def test_app_validate_returns_error_envelope_for_empty_dir_payload_errors(tmp_path):
    # Arrange
    # Arrange
    raw = _unwrap(_call_tool("app_validate", app_dir=str(tmp_path)))
    # Act
    payload = json.loads(raw)
    # Act
    # Assert
    # Assert
    assert payload["errors"]




def test_app_skills_list_returns_envelope_payload_package_scitex_app():
    # Arrange
    # Arrange
    raw = _unwrap(_call_tool("app_skills_list"))
    # Act
    payload = json.loads(raw)
    # Act
    # Assert
    # Assert
    assert payload["package"] == "scitex-app"


def test_app_skills_list_returns_envelope_isinstance_payload_skills_list():
    # Arrange
    # Arrange
    raw = _unwrap(_call_tool("app_skills_list"))
    # Act
    payload = json.loads(raw)
    # Act
    # Assert
    # Assert
    assert isinstance(payload["skills"], list)




def test_app_skills_get_unknown_skill_reports_error_payload_success_is_false():
    # Arrange
    # Arrange
    raw = asyncio.run(
        server.mcp.call_tool("app_skills_get", {"name": "__definitely_missing__"})
    )
    # Act
    payload = json.loads(_unwrap(raw))
    # Act
    # Assert
    # Assert
    assert payload["success"] is False


def test_app_skills_get_unknown_skill_reports_error_unknown_skill_in_payload_error():
    # Arrange
    # Arrange
    raw = asyncio.run(
        server.mcp.call_tool("app_skills_get", {"name": "__definitely_missing__"})
    )
    # Act
    payload = json.loads(_unwrap(raw))
    # Act
    # Assert
    # Assert
    assert "unknown skill" in payload["error"]


