"""The manifest's `privileges` declaration.

PORTED from `scitex_app.validator.AppValidator.validate_privileges`, listed in
the shipped docs and never called by the CLI. This is the manifest's own
security declaration — what an app says it needs from the host — so an
unvalidated one means a typo'd `scope` reads as a scope nobody granted.
"""

from __future__ import annotations

import json
from pathlib import Path

VALID_PRIVILEGE_TYPES = {"filesystem", "network", "api"}
VALID_FILESYSTEM_SCOPES = {"project", "readonly", "none"}
VALID_NETWORK_SCOPES = {"none", "allowlist"}
VALID_API_SCOPES = {"scitex", "llm", "none"}

_SCOPES_BY_TYPE = {
    "filesystem": VALID_FILESYSTEM_SCOPES,
    "network": VALID_NETWORK_SCOPES,
    "api": VALID_API_SCOPES,
}


def validate_privileges(app_dir: str | Path) -> list[str]:
    """Check the manifest's declared privileges are well-formed.

    NOT ARMED — `validate()` skips this unless `check_privileges=True`.

    A manifest with NO `privileges` key reports nothing. That is not an
    oversight and it is not "valid": this rule checks the SHAPE of a
    declaration, and it has no opinion on whether one should exist. Whether an
    app must declare its privileges is a platform decision, and asserting it
    here would smuggle in a requirement nobody agreed to under the name of a
    format check.
    """
    errors = []
    root = Path(app_dir)
    manifest_path = root / "manifest.json"

    if not manifest_path.exists():
        return []  # validate_manifest() reports a missing manifest
    try:
        data = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []  # validate_manifest() reports unparseable JSON
    if not isinstance(data, dict):
        return []

    privileges = data.get("privileges", [])
    if not isinstance(privileges, list):
        return ["manifest.json 'privileges' must be a list"]

    for priv in privileges:
        if not isinstance(priv, dict):
            errors.append(f"Invalid privilege entry (not a dict): {priv}")
            continue

        ptype = priv.get("type")
        if ptype not in VALID_PRIVILEGE_TYPES:
            errors.append(
                f"Unknown privilege type '{ptype}'. "
                f"Valid: {', '.join(sorted(VALID_PRIVILEGE_TYPES))}"
            )

        scope = priv.get("scope", "none")
        valid_scopes = _SCOPES_BY_TYPE.get(ptype, set())
        if valid_scopes and scope not in valid_scopes:
            errors.append(
                f"Invalid scope '{scope}' for privilege type '{ptype}'. "
                f"Valid: {', '.join(sorted(valid_scopes))}"
            )

    return errors


# EOF
