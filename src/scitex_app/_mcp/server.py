#!/usr/bin/env python3
# Timestamp: 2026-03-13
# File: scitex_app/_mcp/server.py

"""MCP server for scitex-app — file operations via Model Context Protocol."""

from __future__ import annotations

from fastmcp import FastMCP

mcp = FastMCP("scitex-app")


@mcp.tool()
def app_read_file(path: str, root: str = ".", binary: bool = False) -> str:
    """Read a file through the SDK backend.

    Parameters
    ----------
    path : str
        Relative file path within the project.
    root : str
        Root directory for file operations (default: current directory).
    binary : bool
        If True, read as binary and return base64-encoded content.
    """
    from scitex_app.sdk import get_files

    files = get_files(root)
    content = files.read(path, binary=binary)
    if binary:
        import base64

        return base64.b64encode(content).decode("ascii")
    return content


@mcp.tool()
def app_write_file(path: str, content: str, root: str = ".") -> str:
    """Write content to a file through the SDK backend.

    Parameters
    ----------
    path : str
        Relative file path within the project.
    content : str
        Text content to write.
    root : str
        Root directory for file operations (default: current directory).
    """
    from scitex_app.sdk import get_files

    files = get_files(root)
    files.write(path, content)
    return f"Written: {path}"


@mcp.tool()
def app_list_files(
    directory: str = "",
    root: str = ".",
    extensions: list[str] | None = None,
) -> list[str]:
    """List files in a directory through the SDK backend.

    Parameters
    ----------
    directory : str
        Relative directory path (empty string = root).
    root : str
        Root directory for file operations (default: current directory).
    extensions : list of str, optional
        Filter by file extensions (e.g., [".yaml", ".png"]).
    """
    from scitex_app.sdk import get_files

    files = get_files(root)
    return files.list(directory, extensions=extensions)


@mcp.tool()
def app_file_exists(path: str, root: str = ".") -> bool:
    """Check if a file exists through the SDK backend.

    Parameters
    ----------
    path : str
        Relative file path within the project.
    root : str
        Root directory for file operations (default: current directory).
    """
    from scitex_app.sdk import get_files

    files = get_files(root)
    return files.exists(path)


@mcp.tool()
def app_delete_file(path: str, root: str = ".") -> str:
    """Delete a file through the SDK backend.

    Parameters
    ----------
    path : str
        Relative file path within the project.
    root : str
        Root directory for file operations (default: current directory).
    """
    from scitex_app.sdk import get_files

    files = get_files(root)
    files.delete(path)
    return f"Deleted: {path}"


@mcp.tool()
def app_copy_file(src_path: str, dest_path: str, root: str = ".") -> str:
    """Copy a file through the SDK backend.

    Parameters
    ----------
    src_path : str
        Source file path.
    dest_path : str
        Destination file path.
    root : str
        Root directory for file operations (default: current directory).
    """
    from scitex_app.sdk import get_files

    files = get_files(root)
    files.copy(src_path, dest_path)
    return f"Copied: {src_path} -> {dest_path}"


@mcp.tool()
def app_rename_file(old_path: str, new_path: str, root: str = ".") -> str:
    """Rename/move a file through the SDK backend.

    Parameters
    ----------
    old_path : str
        Current file path.
    new_path : str
        New file path.
    root : str
        Root directory for file operations (default: current directory).
    """
    from scitex_app.sdk import get_files

    files = get_files(root)
    files.rename(old_path, new_path)
    return f"Renamed: {old_path} -> {new_path}"


# EOF
