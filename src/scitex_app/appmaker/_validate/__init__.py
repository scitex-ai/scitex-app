"""App validator — check structure, security, manifest, templates, and CSS.

Split from a single 537-line module. This file is the ORCHESTRATOR and the
import surface: every name the old module exposed is re-exported here, so
`from scitex_app.appmaker._validate import <anything>` keeps working. The checks
themselves live one concern per module:

    _app_layout    required files, and the manifest reads the others depend on
    _security      forbidden patterns in the app's own Python
    _manifest      manifest.json schema and content
    _frame         workspace frame rules for templates and CSS
    _dependencies  the manifest's `dependencies` shape
    _prefix        mount-prefix safety for request URLs
"""

from __future__ import annotations

import logging
from pathlib import Path

from ._app_layout import (
    REQUIRED_FILES,
    _get_app_name,
    _get_frontend_type,
    _is_embedded_package,
    validate_structure,
)
from ._dependencies import validate_dependencies
from ._frame import (
    FORBIDDEN_BLOCK_OVERRIDES,
    PROTECTED_SELECTORS,
    validate_css,
    validate_templates,
)
from ._manifest import MANIFEST_REQUIRED_KEYS, validate_manifest
from ._prefix import (
    MOUNT_IDENTIFIERS,
    PLATFORM_ROUTE_PREFIXES,
    PREFIX_INFERRED_BASE,
    PREFIX_REQUEST_LITERAL,
    PREFIX_SCAN_SUFFIXES,
    PREFIX_SKIP_DIRS,
    PREFIX_URL_BINDING,
    _prefix_finding_class,
    validate_prefix_safety,
)
from ._security import FORBIDDEN_PATTERNS, validate_security

logger = logging.getLogger(__name__)

__all__ = [
    "FORBIDDEN_BLOCK_OVERRIDES",
    "FORBIDDEN_PATTERNS",
    "MANIFEST_REQUIRED_KEYS",
    "MOUNT_IDENTIFIERS",
    "PLATFORM_ROUTE_PREFIXES",
    "PREFIX_INFERRED_BASE",
    "PREFIX_REQUEST_LITERAL",
    "PREFIX_SCAN_SUFFIXES",
    "PREFIX_SKIP_DIRS",
    "PREFIX_URL_BINDING",
    "PROTECTED_SELECTORS",
    "REQUIRED_FILES",
    "validate",
    "validate_css",
    "validate_dependencies",
    "validate_manifest",
    "validate_prefix_safety",
    "validate_security",
    "validate_structure",
    "validate_templates",
]


def validate(app_dir: str | Path, *, check_prefix_safety: bool = False) -> list[str]:
    """Run all validations on a local app directory.

    Returns list of error strings (empty = valid).

    `check_prefix_safety` is OFF by default, and that default IS the arming
    switch — flipping it to True is the whole of "arm the validator". It is a
    named keyword rather than a silencing flag so it stays greppable and
    individually revisitable; see validate_prefix_safety for why it is not yet
    armed and what has to be true first.
    """
    errors = []
    root = Path(app_dir)
    is_embedded = _is_embedded_package(root)
    frontend_type = _get_frontend_type(root)

    errors.extend(validate_structure(app_dir))
    errors.extend(validate_security(app_dir))
    errors.extend(validate_manifest(app_dir))
    if not is_embedded or (frontend_type and frontend_type != "react"):
        # SKIP ONLY COMPILED-REACT FRONTENDS, which is what the old comment here
        # actually claimed ("embedded packages use compiled React builds") — but
        # the condition tested `not is_embedded`, and _is_embedded_package()
        # returns True from the DIRECTORY NAME alone (any `_`-prefixed dir).
        #
        # So every app living in `_django/` had template and CSS validation
        # unconditionally off, compiled React or not. scitex-scholar found this
        # in their own package: manifest declares frontend_type "vanilla" with
        # no React build anywhere, hand-written Django templates and CSS — i.e.
        # exactly what these two validators check — and neither ever ran. Two
        # checks listed, invoked, and structurally unreachable.
        #
        # The file already knew how to ask: the index_partial check below reads
        # frontend_type. This pair did not.
        #
        # The predicate is deliberately NOT the simpler `frontend_type !=
        # "react"`. frontend_type is inconsistent in the wild — "html",
        # "django", "vanilla" all appear, and the default differs by module
        # ("" here, "django" in _django.py) — so only "react" reliably means
        # compiled. Written this way the change is STRICTLY ADDITIVE:
        #   non-embedded, any type   -> runs (unchanged)
        #   embedded + "react"       -> skipped (unchanged)
        #   embedded + declared other-> RUNS (the fix)
        #   embedded + undeclared    -> skipped (unchanged; an undeclared app
        #                               may well be a React build, and guessing
        #                               would invent findings on compiled output)
        # No app loses a check it has today.
        errors.extend(validate_templates(app_dir))
        errors.extend(validate_css(app_dir))
    errors.extend(validate_dependencies(app_dir))
    if check_prefix_safety:
        # DELIBERATELY OUTSIDE the `if not is_embedded` branch above. Every app
        # carrying this defect today (scholar, writer, figrecipe) IS an embedded
        # `_django` package, so gating this on `not is_embedded` would skip
        # precisely the population it exists to measure — and pass, forever.
        errors.extend(validate_prefix_safety(app_dir))
    return errors


# EOF
