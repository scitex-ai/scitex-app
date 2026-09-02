"""manifest.json `dependencies` — shape of what the app declares it needs."""

from __future__ import annotations

import json
from pathlib import Path


def validate_dependencies(app_dir: str | Path) -> list[str]:
    """Check that manifest.json dependencies field is well-formed."""
    errors = []
    root = Path(app_dir)
    manifest_path = root / "manifest.json"

    if not manifest_path.exists():
        return errors

    try:
        data = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return errors

    deps = data.get("dependencies")
    if deps is None:
        errors.append("manifest.json missing 'dependencies' field")
        return errors

    if not isinstance(deps, dict):
        errors.append("manifest.json 'dependencies' must be a JSON object")
        return errors

    valid_types = {"python", "system", "node", "r", "other"}
    for key, val in deps.items():
        if key not in valid_types:
            errors.append(f"manifest.json unknown dependency type: '{key}'")
        if not isinstance(val, list):
            errors.append(f"manifest.json dependencies.{key} must be a list")
        elif not all(isinstance(item, str) for item in val):
            errors.append(f"manifest.json dependencies.{key} items must be strings")

    return errors


# EOF
