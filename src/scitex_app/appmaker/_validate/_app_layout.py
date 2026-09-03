"""App layout — required files, and the manifest reads every check depends on."""

from __future__ import annotations

import json
from pathlib import Path

REQUIRED_FILES = [
    "apps.py",
    "views.py",
    "urls.py",
    "LICENSE",
    "README.md",
    "manifest.json",
]


def validate_structure(app_dir: str | Path) -> list[str]:
    """Check that required files exist."""
    errors = []
    root = Path(app_dir)

    if not root.exists():
        return [f"App directory does not exist: {root}"]

    is_embedded = _is_embedded_package(root)
    frontend_type = _get_frontend_type(root)

    # Core files always required
    always_required = ["views.py", "urls.py", "manifest.json"]
    # Standalone-only files (embedded packages have these at package root)
    standalone_required = ["apps.py", "LICENSE", "README.md"]

    for required in always_required:
        if not (root / required).exists():
            errors.append(f"Missing required file: {required}")

    if not is_embedded:
        for required in standalone_required:
            if not (root / required).exists():
                errors.append(f"Missing required file: {required}")

    # Check template pattern (skip for React/bridge apps and embedded packages)
    app_name = _get_app_name(root)
    if app_name and not is_embedded and frontend_type != "react":
        partial = root / "templates" / app_name / "index_partial.html"
        if not partial.exists():
            errors.append(f"Missing template: templates/{app_name}/index_partial.html")

    # Check agents config (skip for embedded packages)
    if not is_embedded:
        agents_paths = [
            root / ".agents" / "agents.json",
            root / ".agents" / "README.md",
        ]
        if not any(p.exists() for p in agents_paths):
            errors.append(
                "Missing agents config: .agents/agents.json or .agents/README.md"
            )

    return errors


def _is_embedded_package(root: Path) -> bool:
    """Return True if the app is embedded inside a Python package.

    Detection: manifest declares ``embedded_package: true``, OR the
    directory name starts with ``_`` (e.g. ``_django``).
    """
    # Convention: _django/ is a private package directory
    if root.name.startswith("_"):
        return True
    manifest_path = root / "manifest.json"
    if manifest_path.exists():
        try:
            data = json.loads(manifest_path.read_text(encoding="utf-8"))
            return bool(data.get("embedded_package", False))
        except (json.JSONDecodeError, OSError):
            pass
    return False


def _get_frontend_type(root: Path) -> str:
    """Return frontend_type from manifest, or empty string."""
    manifest_path = root / "manifest.json"
    if manifest_path.exists():
        try:
            data = json.loads(manifest_path.read_text(encoding="utf-8"))
            return data.get("frontend_type", "")
        except (json.JSONDecodeError, OSError):
            pass
    return ""


def _get_app_name(root: Path) -> str:
    """Derive app name from manifest or directory name."""
    manifest_path = root / "manifest.json"
    if manifest_path.exists():
        try:
            data = json.loads(manifest_path.read_text(encoding="utf-8"))
            return data.get("name", "")
        except (json.JSONDecodeError, OSError):
            pass
    return root.name


# EOF
