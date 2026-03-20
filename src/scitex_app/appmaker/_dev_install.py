"""Dev-install a SciTeX app to the cloud server."""

from __future__ import annotations

import json
from pathlib import Path


def dev_install(
    app_dir: str | Path,
    server_url: str,
    token: str,
    owner: str | None = None,
    repo: str | None = None,
) -> dict:
    """Install an app on the SciTeX Cloud server via the dev install API.

    Parameters
    ----------
    app_dir : path
        Directory containing the app with manifest.json.
    server_url : str
        Base URL of the SciTeX Cloud server (e.g. http://127.0.0.1:8000).
    token : str
        JWT access token (Bearer auth).
    owner : str, optional
        Gitea username. Derived from token if not provided.
    repo : str, optional
        Gitea repo name. Derived from manifest.json name if not provided.

    Returns
    -------
    dict
        Server response with 'success' key.
    """
    import requests

    from ._validate import validate

    app_path = Path(app_dir).resolve()

    # Local validation first
    errors = validate(str(app_path))
    if errors:
        return {"success": False, "errors": errors}

    # Read manifest for app name
    manifest_path = app_path / "manifest.json"
    if not manifest_path.is_file():
        return {"success": False, "errors": ["manifest.json not found"]}

    with open(manifest_path, encoding="utf-8") as f:
        manifest = json.load(f)

    repo_name = repo or manifest.get("slug") or manifest.get("name", app_path.name)

    # Resolve owner from token if not provided
    if not owner:
        owner = _get_username_from_token(server_url, token)
        if not owner:
            return {
                "success": False,
                "errors": ["Could not determine owner. Pass --owner explicitly."],
            }

    # Call dev install API
    url = f"{server_url.rstrip('/')}/apps/store/api/dev/install/"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    payload = {"owner": owner, "repo": repo_name}

    resp = requests.post(url, headers=headers, json=payload, timeout=30)

    try:
        return resp.json()
    except (json.JSONDecodeError, ValueError):
        return {
            "success": False,
            "errors": [f"Server returned {resp.status_code}: {resp.text[:200]}"],
        }


def _get_username_from_token(server_url: str, token: str) -> str | None:
    """Resolve the current user's username from the server."""
    import requests

    try:
        url = f"{server_url.rstrip('/')}/platform/api/context/"
        headers = {"Authorization": f"Bearer {token}"}
        resp = requests.get(url, headers=headers, timeout=10)
        if resp.ok:
            data = resp.json()
            return data.get("context", {}).get("user", {}).get("username")
    except Exception:
        pass
    return None


# EOF
