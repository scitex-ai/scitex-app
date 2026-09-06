"""manifest.json — schema and content."""

from __future__ import annotations

import json
from pathlib import Path

# THE ONE REQUIRED-KEY LIST. scitex_app.validator imports this rather than
# declaring a second one — it declared its own for months, five keys against
# these six, so `license` was required by the CLI and not by AppValidator and
# nothing said so. Syncing two lists is a promise; importing one is a guarantee,
# and that promise had already been broken once here and once in the JS pattern
# list (0.16.2), both silently, both in the direction that disagrees about a
# peer's app.
#
# A TUPLE, not a list: this object is imported, so a list would be mutable
# shared state that any importer could `.append()` to, changing validation for
# every caller in the interpreter. (scitex-writer, 2026-09-06.)
MANIFEST_REQUIRED_KEYS = ("name", "slug", "label", "pip_package", "icon", "license")


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

    # The 'name' suffix convention is ADVISORY and lives in
    # validate_manifest_advisory(), not here. See that function for why.

    return errors


def validate_manifest_advisory(app_dir: str | Path) -> list[str]:
    """Manifest findings that are ADVICE, not failures.

    A separate function rather than a severity argument on the one above, so the
    tier is STRUCTURAL: a finding is advisory because of where it is raised, not
    because of how its message happens to be worded. The name convention was
    worded "should" and enforced as a failure, which is how it became
    unclearable — scitex-scholar's manifest is `scholar_editor` because
    `scholar_app` would COLLIDE with hub's existing registry entry, so the only
    escape the rule offered was to create the bug the name avoids.
    """
    warnings = []
    root = Path(app_dir)
    manifest_path = root / "manifest.json"

    if not manifest_path.exists():
        return []
    try:
        data = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []  # validate_manifest() already reports this, as an error
    if not isinstance(data, dict):
        return []

    name = data.get("name", "")
    if name and not (name.endswith("_app") or name.endswith("-app")):
        warnings.append(
            f"manifest.json 'name' should end with '_app' or '-app' (got: '{name}')"
        )

    return warnings


# EOF
