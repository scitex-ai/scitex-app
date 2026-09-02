"""manifest.json — schema and content."""

from __future__ import annotations

import json
from pathlib import Path

MANIFEST_REQUIRED_KEYS = ["name", "slug", "label", "pip_package", "icon", "license"]


def validate_manifest(app_dir: str | Path) -> list[str]:
    """Check manifest.json schema and content."""
    errors = []
    root = Path(app_dir)
    manifest_path = root / "manifest.json"

    if not manifest_path.exists():
        return ["manifest.json not found"]

    try:
        data = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as e:
        return [f"manifest.json is not valid JSON: {e}"]

    if not isinstance(data, dict):
        return ["manifest.json must be a JSON object"]

    for key in MANIFEST_REQUIRED_KEYS:
        if key not in data:
            errors.append(f"manifest.json missing required key: '{key}'")

    # The app version is the SINGLE SOURCE OF TRUTH: the installed package's own
    # version, read at runtime via importlib.metadata from `pip_package`. A
    # hand-written `version` in the manifest is FORBIDDEN — it inevitably drifts
    # from the package (2026-07 incident: manifests stuck at "0.14.0" while the
    # packages shipped 2.25.0 / 0.29.9 / 1.4.2, so every app tile showed a wrong
    # version). Declare `pip_package` (the dist name) and let the version derive.
    if "version" in data:
        errors.append(
            "manifest.json must NOT declare 'version' — it drifts from the "
            "package. The version is derived at runtime from the installed "
            "'pip_package' (importlib.metadata). Remove the 'version' key."
        )

    # Validate name matches directory convention
    name = data.get("name", "")
    if name and not (name.endswith("_app") or name.endswith("-app")):
        errors.append(
            f"manifest.json 'name' should end with '_app' or '-app' (got: '{name}')"
        )

    return errors


# EOF
