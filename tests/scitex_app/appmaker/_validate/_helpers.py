"""Fixtures shared by the split _validate test modules (moved verbatim)."""

from __future__ import annotations

import json
from pathlib import Path


def write_manifest(path: Path, data: dict) -> None:
    (path / "manifest.json").write_text(json.dumps(data), encoding="utf-8")


def make_minimal_embedded_app(root: Path) -> None:
    """Create a minimal embedded app (passes validate() without template/CSS checks)."""
    write_manifest(
        root,
        {
            "name": "test_app",
            "slug": "test-app",
            "label": "Test App",
            "pip_package": "test-app",
            "icon": "fas fa-flask",
            "license": "MIT",
            "embedded_package": True,
            "dependencies": {"python": []},
        },
    )
    (root / "views.py").touch()
    (root / "urls.py").touch()


def make_full_standalone_app(root: Path, app_name: str = "myapp") -> None:
    """Create a standalone app with all required files."""
    write_manifest(
        root,
        {
            "name": app_name,
            "slug": app_name.replace("_", "-"),
            "label": "My App",
            "pip_package": app_name.replace("_", "-"),
            "icon": "fas fa-star",
            "license": "MIT",
            "dependencies": {"python": ["django"]},
        },
    )
    (root / "apps.py").touch()
    (root / "views.py").touch()
    (root / "urls.py").touch()
    (root / "LICENSE").write_text("MIT License", encoding="utf-8")
    (root / "README.md").write_text("# My App", encoding="utf-8")

    # Template for standalone app
    templates_dir = root / "templates" / app_name
    templates_dir.mkdir(parents=True)
    (templates_dir / "index_partial.html").write_text("<div>content</div>")

    # Agents config
    agents_dir = root / ".agents"
    agents_dir.mkdir()
    (agents_dir / "agents.json").write_text(json.dumps({"agents": []}))


# EOF
