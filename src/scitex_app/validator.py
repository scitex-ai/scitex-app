#!/usr/bin/env python3
# Timestamp: 2026-03-17
# File: scitex_app/validator.py

"""scitex_app.validator — App validation pipeline for SciTeX platform.

Validates app directories against the SciTeX app contract before deployment.
Pure Python, no Django dependency.

Usage:
    from scitex_app.validator import AppValidator

    validator = AppValidator("/path/to/myapp")
    result = validator.validate()
    if not result.passed:
        for error in result.errors:
            print(f"ERROR: {error}")
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

logger = logging.getLogger(__name__)

# Required manifest fields — IMPORTED, not declared. NOTE: `version` is
# intentionally NOT required; the app version is the single source of truth of
# the installed `pip_package` (the dist name), read at runtime via
# importlib.metadata, and a hand-written manifest `version` is forbidden (see
# validate_manifest).
#
# This module used to declare its own five-key set against the CLI's six, so
# `license` was required by one entry point and not the other, and the coverage
# table in the skills shipped for weeks comparing them check-by-check without
# saying so. Same defect as the JS pattern list fixed in 0.16.2, same remedy.
from scitex_app.appmaker._validate._manifest import (  # noqa: E402
    MANIFEST_REQUIRED_KEYS as MANIFEST_REQUIRED_FIELDS,
)

# Valid privilege types
VALID_PRIVILEGE_TYPES = {"filesystem", "network", "api"}
VALID_FILESYSTEM_SCOPES = {"project", "readonly", "none"}
VALID_NETWORK_SCOPES = {"none", "allowlist"}
VALID_API_SCOPES = {"scitex", "llm", "none"}

# Shell selectors that apps must NOT target
SHELL_SELECTORS = {
    "#scitex-ai-panel",
    "#main-content",
    ".ws-module-pane",
    ".workspace-header",
    ".workspace-sidebar",
    # `.stx-shell-` REMOVED 2026-09-06. It was a bare PREFIX in a table matched
    # by raw substring, so it flagged every app that styled its own
    # `.stx-shell-sidebar__*` element — scitex-hub measured 42 such legitimate
    # lines across nine apps. `.stx-shell-*` is not blanket no-touch; ownership
    # is by NODE, not by name prefix. The shipped skill has said so since
    # 0.15.0 while this entry kept contradicting it.
    "#workspace-container",
    ".ws-app-sidebar",
}

# Dangerous JS patterns
# ONE DECLARATION, IMPORTED — not a second copy kept in step by hand.
#
# This list used to be nine patterns here and five in `_validate/_js.py`, and
# the difference was not a disagreement: it was a MEASURED NARROWING that
# landed in one implementation only. Four of the original nine —
# `__import__`, `os.system`, `subprocess`, `exec\s*\(` — are the PYTHON
# forbidden list copy-pasted into a JS scanner, and they were removed there
# after measuring the fleet.
#
# scitex-writer hit the survivor on 2026-09-06, through THIS module:
#
#     static/writer/js/editor.js:812
#     while ((match = re.exec(line)) !== null)
#         -> "dangerous pattern matching '\bexec\s*\('"
#
# `RegExp.prototype.exec` in a tokenizer loop. Not code execution, and
# `\bexec\s*\(` cannot tell a member call from the eval-family builtin.
#
# They reported it rather than renaming the variable to dodge the checker,
# which is why it is fixed here instead of hidden in their tree.
#
# The import is the point. Syncing two lists is a promise; importing one is a
# guarantee — and the promise had already been broken once, silently, in the
# direction that failed a peer's correct code.
from scitex_app.appmaker._validate._js import DANGEROUS_JS_PATTERNS

# Default max bundle size (50MB)
DEFAULT_MAX_BUNDLE_SIZE = 50 * 1024 * 1024

# Directories to skip during CSS/JS scanning (build artifacts, docs, etc.)
SKIP_DIRS = {"node_modules", "dist", ".vite", "_docs", "__pycache__", "assets"}


@dataclass
class ValidationResult:
    """Result of app validation."""

    passed: bool = True
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    privileges: List[dict] = field(default_factory=list)
    manifest: Optional[dict] = None

    def add_error(self, msg: str):
        self.errors.append(msg)
        self.passed = False

    def add_warning(self, msg: str):
        self.warnings.append(msg)


class AppValidator:
    """Validates a SciTeX app directory against the platform contract.

    Args:
        app_path: Path to the app's root directory (or _django subdirectory)
        max_bundle_size: Maximum total file size in bytes
    """

    def __init__(
        self,
        app_path: str | Path,
        max_bundle_size: int = DEFAULT_MAX_BUNDLE_SIZE,
    ):
        self.app_path = Path(app_path).resolve()
        self.max_bundle_size = max_bundle_size
        self._result = ValidationResult()

    def validate(self) -> ValidationResult:
        """Run all validation checks. Returns ValidationResult."""
        self._result = ValidationResult()

        # Order matters: manifest first (other checks may depend on it)
        self.validate_manifest()
        self.validate_structure()
        self.validate_css()
        self.validate_js()
        self.validate_bundle_size()
        if self._result.manifest:
            self.validate_privileges()

        return self._result

    def validate_manifest(self) -> None:
        """Check manifest.json exists and has required fields."""
        # Look in app root or _django subdirectory
        for candidate in [
            self.app_path / "manifest.json",
            self.app_path / "_django" / "manifest.json",
        ]:
            if candidate.exists():
                try:
                    manifest = json.loads(candidate.read_text())
                    self._result.manifest = manifest
                except json.JSONDecodeError as exc:
                    self._result.add_error(f"manifest.json is invalid JSON: {exc}")
                    return

                missing = set(MANIFEST_REQUIRED_FIELDS) - set(manifest.keys())
                if missing:
                    self._result.add_error(
                        f"manifest.json missing required fields: "
                        f"{', '.join(sorted(missing))}"
                    )

                # The app version is the SINGLE SOURCE OF TRUTH: the installed
                # package's own version, read at runtime via importlib.metadata
                # from `pip_package`. A hand-written `version` in the manifest is
                # FORBIDDEN — it inevitably drifts from the package (2026-07
                # incident: manifests stuck at "0.14.0" while the packages
                # shipped 2.25.0 / 0.29.9 / 1.4.2, so every app tile showed a
                # wrong version). Declare `pip_package` (the dist name) instead.
                if "version" in manifest:
                    self._result.add_error(
                        "manifest.json must NOT declare 'version' — it drifts "
                        "from the package. The version is derived at runtime "
                        "from the installed 'pip_package' (importlib.metadata). "
                        "Remove the 'version' key."
                    )

                # Validate field types
                if "name" in manifest and not isinstance(manifest["name"], str):
                    self._result.add_error("manifest.name must be a string")

                self._result.privileges = manifest.get("privileges", [])
                return

        self._result.add_error("No manifest.json found in app directory")

    def validate_structure(self) -> None:
        """Check required file structure exists."""
        # Check for _django package (required for platform apps)
        django_dir = self.app_path / "_django"
        if not django_dir.is_dir():
            # Maybe the app_path IS the _django dir
            if (self.app_path / "views.py").exists():
                django_dir = self.app_path
            else:
                self._result.add_warning(
                    "No _django/ directory found. "
                    "App may not integrate with scitex-hub."
                )
                return

        required_files = ["views.py", "urls.py"]
        for fname in required_files:
            if not (django_dir / fname).exists():
                self._result.add_error(f"Missing required file: _django/{fname}")

    @staticmethod
    def _should_skip(path: Path) -> bool:
        """Check if a file should be skipped (build artifacts, docs, etc.)."""
        return bool(SKIP_DIRS & set(path.parts))

    def validate_css(self) -> None:
        """Check CSS source files don't target shell elements."""
        for css_file in self.app_path.rglob("*.css"):
            if self._should_skip(css_file):
                continue
            try:
                content = css_file.read_text(errors="replace")
            except OSError:
                continue

            for selector in SHELL_SELECTORS:
                if selector in content:
                    rel = css_file.relative_to(self.app_path)
                    self._result.add_error(
                        f"{rel}: targets shell selector '{selector}' — "
                        "app CSS must not modify shell elements"
                    )

    def validate_js(self) -> None:
        """Check JS/TS source files for dangerous patterns."""
        for ext in ("*.js", "*.ts", "*.tsx", "*.jsx"):
            for js_file in self.app_path.rglob(ext):
                if self._should_skip(js_file):
                    continue

                try:
                    content = js_file.read_text(errors="replace")
                except OSError:
                    continue

                rel = js_file.relative_to(self.app_path)
                for pattern in DANGEROUS_JS_PATTERNS:
                    if re.search(pattern, content):
                        self._result.add_error(
                            f"{rel}: contains dangerous pattern matching '{pattern}'"
                        )

    def validate_bundle_size(self) -> None:
        """Check total file size is under the limit."""
        total_size = 0
        for f in self.app_path.rglob("*"):
            if f.is_file() and "node_modules" not in f.parts:
                total_size += f.stat().st_size

        if total_size > self.max_bundle_size:
            mb = total_size / (1024 * 1024)
            limit_mb = self.max_bundle_size / (1024 * 1024)
            self._result.add_error(
                f"Bundle size {mb:.1f}MB exceeds limit of {limit_mb:.1f}MB"
            )

    def validate_privileges(self) -> None:
        """Check declared privileges are valid."""
        for priv in self._result.privileges:
            if not isinstance(priv, dict):
                self._result.add_error(f"Invalid privilege entry (not a dict): {priv}")
                continue

            ptype = priv.get("type")
            if ptype not in VALID_PRIVILEGE_TYPES:
                self._result.add_error(
                    f"Unknown privilege type '{ptype}'. "
                    f"Valid: {', '.join(sorted(VALID_PRIVILEGE_TYPES))}"
                )

            scope = priv.get("scope", "none")
            valid_scopes = {
                "filesystem": VALID_FILESYSTEM_SCOPES,
                "network": VALID_NETWORK_SCOPES,
                "api": VALID_API_SCOPES,
            }.get(ptype, set())

            if valid_scopes and scope not in valid_scopes:
                self._result.add_error(
                    f"Invalid scope '{scope}' for privilege type '{ptype}'. "
                    f"Valid: {', '.join(sorted(valid_scopes))}"
                )


# EOF
