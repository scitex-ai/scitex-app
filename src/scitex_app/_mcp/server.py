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
    """Read a file inside a SciTeX app project via the auto-detecting FilesBackend — same call works for local paths AND cloud-backed workspaces (S3 / NAS / registered custom backends). Drop-in replacement for raw `open(path).read()` or `boto3.get_object` scattered through app code. Use when the user asks to "read this app's config.yaml", "get the contents of path X in my app", "load a file through the SDK", or is writing app code that must work both locally and on the cloud. Set `binary=True` for base64-encoded binary content.

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
    """Write content to a file inside a SciTeX app project via the auto-detecting FilesBackend — routes to local disk OR the active cloud backend automatically. Drop-in replacement for `open(path, 'w').write(...)` or `boto3.put_object`. Use when the user asks to "save this to my app", "write config.yaml in the app folder", "persist this result", or is producing outputs from app code that must work both locally and in the cloud workspace.

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
    """List files inside a SciTeX app project through the FilesBackend — works on local directories AND cloud-backed workspaces. Drop-in replacement for `os.listdir` / `pathlib.Path.glob` / `s3.list_objects_v2`. Use when the user asks to "list files in my app", "show YAML configs", "what's in this app's data/ dir?", or before iterating over app inputs. Filter with `extensions=['.yaml', '.png']`.

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
    """Check whether a file exists inside a SciTeX app project via the FilesBackend. Works identically for local and cloud backends. Drop-in replacement for `pathlib.Path.exists()` / `s3.head_object`. Use when the user asks "does this file exist in the app?", "has the app written its output yet?", "check for X before writing", or guards a read.

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
    """Delete a file inside a SciTeX app project via the FilesBackend — local or cloud. Destructive. Drop-in replacement for `os.remove` / `pathlib.Path.unlink` / `s3.delete_object`. Use when the user asks to "delete this file from my app", "remove stale outputs", "clean up the app's temp/", or is tidying before a fresh run.

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
    """Copy a file inside a SciTeX app project via the FilesBackend — local or cloud, including cross-backend copies (e.g. local → S3) if both are configured. Drop-in replacement for `shutil.copy` / `s3.copy_object`. Use when the user asks to "copy config.yaml to backup.yaml", "duplicate this input as a variant", "snapshot this file before editing", or is preparing a "known-good" baseline.

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
    """Rename or move a file inside a SciTeX app project via the FilesBackend — atomic on local, best-effort on cloud backends. Drop-in replacement for `os.rename` / `pathlib.Path.rename`. Use when the user asks to "rename X to Y in my app", "move this file to a different folder", "fix a typo in a filename", or is reorganizing the app's data layout.

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
    """Generate a brand-new SciTeX workspace app in a directory — full Django starter (manifest.json, urls.py, views.py, templates, CSS, static/, tests/) + optional React bridge. Auto-appends `_app` to the name. Drop-in replacement for `django-admin startapp` + hand-copying boilerplate + writing manifest.json by hand. Use whenever the user asks to "scaffold a SciTeX app", "init a new workspace app", "create a new app called X", "start a new scitex-app module", "make a React-frontend app", or is beginning a fresh workspace module. Set `frontend='react'` for React bridge, `icon='fas fa-chart-bar'` for a Font Awesome icon.

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
    """Audit a SciTeX app for cloud-submission readiness — checks `manifest.json` schema + fields, directory structure, CSS scoping (no global leaks), JS safety (no cross-app DOM access), bundle size limits, and required privileges. Drop-in replacement for running ad-hoc lint scripts before every submission. Use whenever the user asks to "validate my app", "is my app ready to submit?", "check the manifest", "audit CSS safety", or before `scitex-app app submit`. Returns a list of errors or an empty list on pass.

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


# §5 — skills introspection tools (per audit-mcp-tools convention)
@mcp.tool()
def app_skills_list() -> str:
    """List the names of every skill page shipped by scitex-app.

    Returns
    -------
        JSON string with `{"success": true, "package": "scitex-app",
        "skills": ["01_files-sdk", "02_backend-sdk", ...]}`.
    """
    try:
        from pathlib import Path

        skills_dir = Path(__file__).parent.parent / "_skills" / "scitex-app"
        names = sorted(p.stem for p in skills_dir.glob("*.md") if p.name != "SKILL.md")
        return _json_mod.dumps(
            {"success": True, "package": "scitex-app", "skills": names},
            indent=2,
        )
    except Exception as e:
        return _json_mod.dumps({"success": False, "error": str(e)}, indent=2)


@mcp.tool()
def app_skills_get(name: str) -> str:
    """Fetch the full Markdown content of one scitex-app skill page.

    Args:
        name: Skill page name without `.md`, e.g. `01_files-sdk`.

    Returns
    -------
        JSON string with `{"success": true, "package": "scitex-app",
        "name": <name>, "content": <markdown>}`, or an error envelope.
    """
    try:
        from pathlib import Path

        skills_dir = Path(__file__).parent.parent / "_skills" / "scitex-app"
        target = skills_dir / f"{name}.md"
        if not target.exists():
            available = sorted(
                p.stem for p in skills_dir.glob("*.md") if p.name != "SKILL.md"
            )
            return _json_mod.dumps(
                {
                    "success": False,
                    "error": f"unknown skill {name!r}; available: {available}",
                },
                indent=2,
            )
        return _json_mod.dumps(
            {
                "success": True,
                "package": "scitex-app",
                "name": name,
                "content": target.read_text(encoding="utf-8"),
            },
            indent=2,
        )
    except Exception as e:
        return _json_mod.dumps({"success": False, "error": str(e)}, indent=2)


# EOF
