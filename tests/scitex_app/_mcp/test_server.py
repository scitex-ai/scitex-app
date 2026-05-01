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


def test_app_write_then_read_roundtrip(tmp_path):
    write_msg = _unwrap(
        _call_tool("app_write_file", path="hello.txt", content="hi", root=str(tmp_path))
    )
    assert "hello.txt" in str(write_msg)

    content = _unwrap(_call_tool("app_read_file", path="hello.txt", root=str(tmp_path)))
    assert content == "hi"


def test_app_list_files_filters_by_extension(tmp_path):
    (tmp_path / "a.txt").write_text("x")
    (tmp_path / "b.yaml").write_text("y: 1")
    files = _unwrap(
        _call_tool(
            "app_list_files", directory="", root=str(tmp_path), extensions=[".yaml"]
        )
    )
    assert "b.yaml" in files
    assert "a.txt" not in files


def test_app_file_exists_true_and_false(tmp_path):
    (tmp_path / "x.txt").write_text("here")
    assert (
        _unwrap(_call_tool("app_file_exists", path="x.txt", root=str(tmp_path))) is True
    )
    assert (
        _unwrap(_call_tool("app_file_exists", path="missing.txt", root=str(tmp_path)))
        is False
    )


def test_app_copy_then_delete(tmp_path):
    (tmp_path / "src.txt").write_text("data")
    _call_tool(
        "app_copy_file", src_path="src.txt", dest_path="dst.txt", root=str(tmp_path)
    )
    assert (tmp_path / "dst.txt").read_text() == "data"
    _call_tool("app_delete_file", path="dst.txt", root=str(tmp_path))
    assert not (tmp_path / "dst.txt").exists()


def test_app_rename_file(tmp_path):
    (tmp_path / "old.txt").write_text("data")
    _call_tool(
        "app_rename_file", old_path="old.txt", new_path="new.txt", root=str(tmp_path)
    )
    assert not (tmp_path / "old.txt").exists()
    assert (tmp_path / "new.txt").read_text() == "data"


def test_app_validate_returns_error_envelope_for_empty_dir(tmp_path):
    raw = _unwrap(_call_tool("app_validate", app_dir=str(tmp_path)))
    payload = json.loads(raw)
    assert payload["success"] is False
    assert payload["errors"]


def test_app_skills_list_returns_envelope():
    raw = _unwrap(_call_tool("app_skills_list"))
    payload = json.loads(raw)
    assert payload["package"] == "scitex-app"
    assert isinstance(payload["skills"], list)


def test_app_skills_get_unknown_skill_reports_error():
    raw = asyncio.run(
        server.mcp.call_tool("app_skills_get", {"name": "__definitely_missing__"})
    )
    payload = json.loads(_unwrap(raw))
    assert payload["success"] is False
    assert "unknown skill" in payload["error"]
