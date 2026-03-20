#!/usr/bin/env python3
# Timestamp: 2026-03-13
# File: scitex_app/_mcp/server.py

"""MCP server for scitex-app — file operations via Model Context Protocol."""

from __future__ import annotations

import json as _json_mod
from typing import Optional

from fastmcp import FastMCP

mcp = FastMCP("scitex-app")


def _json(obj):
    """Serialize to JSON string."""
    return _json_mod.dumps(obj, indent=2, default=str)


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


# =============================================================================
# App Lifecycle Tools
# =============================================================================


@mcp.tool()
def app_scaffold(
    target_dir: str = ".",
    name: Optional[str] = None,
    label: Optional[str] = None,
    icon: str = "fas fa-puzzle-piece",
    description: str = "",
    frontend: str = "html",
    overwrite: bool = False,
) -> str:
    """Scaffold a complete SciTeX app in a directory.

    Parameters
    ----------
    target_dir : str
        Directory to scaffold in (default: current directory).
    name : str, optional
        App module name (must end with _app). Auto-detected from dir name.
    label : str, optional
        Human-readable label.
    icon : str
        Font Awesome icon class (default: fas fa-puzzle-piece).
    description : str
        Short description of the app.
    frontend : str
        Frontend type: 'html' (default) or 'react'.
    overwrite : bool
        Whether to overwrite existing files (default: False).

    Examples
    --------
    CLI equivalent: scitex-app app init /path/to/my_app --name my_app -f react
    """
    from pathlib import Path
    from scitex_app.appmaker import init_app

    target = Path(target_dir).resolve()
    app_name = name or target.name

    if not (app_name.endswith("_app") or app_name.endswith("-app")):
        sep = "-" if "-" in app_name else "_"
        app_name = f"{app_name}{sep}app"

    created = init_app(
        target_dir=target,
        name=app_name,
        label=label or "",
        icon=icon,
        description=description,
        overwrite=overwrite,
        frontend_type=frontend,
    )

    return _json(
        {
            "success": True,
            "app_name": app_name,
            "target_dir": str(target),
            "files_created": [str(f) for f in created],
            "count": len(created),
        }
    )


@mcp.tool()
def app_validate(app_dir: str = ".") -> str:
    """Validate a SciTeX app for submission readiness.

    Checks manifest, structure, CSS safety, JS safety, bundle size, privileges.

    Parameters
    ----------
    app_dir : str
        Path to the app directory (default: current directory).

    Examples
    --------
    CLI equivalent: scitex-app app validate /path/to/my_app
    """
    from scitex_app.appmaker import validate

    errors = validate(app_dir)

    return _json(
        {
            "success": len(errors) == 0,
            "errors": errors,
            "message": "All checks passed"
            if not errors
            else f"{len(errors)} issue(s) found",
        }
    )


# =============================================================================
# Skills Tools
# =============================================================================


@mcp.tool()
def skills_list() -> str:
    """List available skill pages for scitex-app.

    Examples
    --------
    CLI equivalent: scitex-app skills list
    """
    try:
        from scitex_dev.skills import list_skills

        result = list_skills(package="scitex-app")
        return _json({"success": True, "skills": result.get("scitex-app", [])})
    except ImportError:
        return _json({"success": False, "error": "scitex-dev not installed"})


@mcp.tool()
def skills_get(name: Optional[str] = None) -> str:
    """Get a skill page for scitex-app. Without name, returns main SKILL.md.

    Parameters
    ----------
    name : str, optional
        Reference name (e.g., 'backend-sdk'). If None, returns SKILL.md.

    Examples
    --------
    CLI equivalent: scitex-app skills get backend-sdk
    """
    try:
        from scitex_dev.skills import get_skill

        content = get_skill(package="scitex-app", name=name)
        if content:
            return _json({"success": True, "name": name, "content": content})
        target = f"'{name}'" if name else "SKILL.md"
        return _json({"success": False, "error": f"Skill {target} not found"})
    except ImportError:
        return _json({"success": False, "error": "scitex-dev not installed"})


# EOF
