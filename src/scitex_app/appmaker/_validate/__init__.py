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
from ._bundle import DEFAULT_MAX_BUNDLE_SIZE, validate_bundle_size
from ._css import (
    APP_CONTAINERS,
    BODY_STATE_CLASSES,
    SHARED_COMPONENT_CLASSES,
    SHELL_INSTANCE_NAMES,
    SHELL_INSTANCE_PREFIXES,
    SHELL_TOKEN_PREFIXES,
    CssScanReport,
    NotAnAppDirectoryError,
    css_files,
    validate_css_canonical,
)
from ._css_finding import (
    CssFinding,
)
from ._dependencies import validate_dependencies
from ._frame import (
    FORBIDDEN_BLOCK_OVERRIDES,
    PROTECTED_SELECTORS,
    validate_css,
    validate_css_advisory,
    validate_templates,
)
from ._js import DANGEROUS_JS_PATTERNS, JS_SKIP_DIRS, validate_js
from ._manifest import (
    MANIFEST_REQUIRED_KEYS,
    validate_manifest,
    validate_manifest_advisory,
)
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
from ._privileges import (
    VALID_API_SCOPES,
    VALID_FILESYSTEM_SCOPES,
    VALID_NETWORK_SCOPES,
    VALID_PRIVILEGE_TYPES,
    validate_privileges,
)
from ._security import FORBIDDEN_PATTERNS, validate_security

logger = logging.getLogger(__name__)

__all__ = [
    "APP_CONTAINERS",
    "BODY_STATE_CLASSES",
    "CssFinding",
    "CssScanReport",
    "DANGEROUS_JS_PATTERNS",
    "DEFAULT_MAX_BUNDLE_SIZE",
    "FORBIDDEN_BLOCK_OVERRIDES",
    "FORBIDDEN_PATTERNS",
    "JS_SKIP_DIRS",
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
    "SHARED_COMPONENT_CLASSES",
    "SHELL_INSTANCE_NAMES",
    "SHELL_INSTANCE_PREFIXES",
    "NotAnAppDirectoryError",
    "SHELL_TOKEN_PREFIXES",
    "VALID_API_SCOPES",
    "VALID_FILESYSTEM_SCOPES",
    "VALID_NETWORK_SCOPES",
    "VALID_PRIVILEGE_TYPES",
    "css_files",
    "validate",
    "validate_bundle_size",
    "validate_css",
    "validate_css_advisory",
    "validate_css_canonical",
    "validate_dependencies",
    "validate_js",
    "validate_manifest",
    "validate_manifest_advisory",
    "validate_prefix_safety",
    "validate_privileges",
    "validate_security",
    "validate_structure",
    "validate_templates",
    "validate_with_warnings",
]


def validate(
    app_dir: str | Path,
    *,
    check_prefix_safety: bool = True,
    check_js_safety: bool = False,
    check_bundle_size: bool = False,
    check_privileges: bool = False,
    check_css_canonical: bool = False,
) -> list[str]:
    """Run all validations on a local app directory.

    Returns list of error strings (empty = valid). Everything returned here is a
    FAILURE; advisory findings come back separately from
    validate_with_warnings().

    `check_prefix_safety` defaults to True as of 2026-09-05; the rest still
    default to False. A caller that names no keyword therefore gets the prefix
    rule, which is a BEHAVIOUR CHANGE for every existing call site.
    """
    errors, _ = validate_with_warnings(
        app_dir,
        check_prefix_safety=check_prefix_safety,
        check_js_safety=check_js_safety,
        check_bundle_size=check_bundle_size,
        check_privileges=check_privileges,
        check_css_canonical=check_css_canonical,
    )
    return errors


def validate_with_warnings(
    app_dir: str | Path,
    *,
    check_prefix_safety: bool = True,
    check_js_safety: bool = False,
    check_bundle_size: bool = False,
    check_privileges: bool = False,
    check_css_canonical: bool = False,
) -> tuple[list[str], list[str]]:
    """Run all validations, separating FAILURES from ADVICE.

    Returns `(errors, warnings)`. Errors fail a build; warnings are reported and
    change nothing.

    WHY THE TIER EXISTS. `validate()` returned one flat list and its only
    consumer does `raise SystemExit(1)` on any entry, so "should" and "must"
    were indistinguishable to the thing acting on them. Two findings were worded
    as advice and enforced as failures, and one of them was UNCLEARABLE: an app
    could not satisfy it without introducing the collision the rule's own
    remediation would cause. A rule nobody can clear does not raise quality — it
    teaches people to stop running the validator.

    NOT an argument for softening the other error-tier findings. Their wording
    matches their enforcement, including the forbidden `version` key, whose
    message cites the incident where every hub app tile showed a wrong version.

    THE `check_*` DEFAULT IS THE ARMING SWITCH — flipping one to True is the
    whole of "arm that rule". They are named keywords rather than one blanket
    flag so each stays greppable and individually revisitable; each rule's own
    docstring says whether it is armed, and if not, what has to be true first.

        check_prefix_safety   request URLs that break under a mount   ARMED
        check_js_safety       dangerous patterns in the app's JS      not armed
        check_bundle_size     total shipped size against a threshold  not armed
        check_privileges      shape of the privilege declaration      not armed
        check_css_canonical   the canonical workspace-CSS rule        not armed

    `check_css_canonical` is the ONE that supersedes rather than adds: it is
    the same spec `validate_css` enforces, measured properly. It is off, and it
    does not turn `validate_css` off, so today the two coexist and only the old
    one runs. That is deliberate and temporary — arming it means replacing the
    call above, not adding to it, and the replacement waits on scitex-hub
    re-measuring their five findings against THIS implementation. Whoever arms
    it must delete the `validate_css` call in the same change; leaving both
    would report one CSS defect twice under two wordings.

    This paragraph read "EVERY `check_*` KEYWORD IS OFF BY DEFAULT" until the
    day one was not. It is listed per-rule now because a sentence quantified
    over all of them goes false the first time any single one is armed, and a
    docstring that is false about the arming state of a GATE is worse than no
    docstring — the reader has no reason to doubt it.

    The last three were PORTED from `scitex_app.validator.AppValidator`, where
    they worked, were tested, were described to app developers by the shipped
    skill doc — and were called by nothing. The CLI read no `.js` file at all.
    Bringing them into the live path is additive: none of them has a counterpart
    here, so none can contradict a verdict this module already gives.
    """
    errors: list[str] = []
    warnings: list[str] = []
    root = Path(app_dir)
    is_embedded = _is_embedded_package(root)
    frontend_type = _get_frontend_type(root)

    errors.extend(validate_structure(app_dir))
    errors.extend(validate_security(app_dir))
    errors.extend(validate_manifest(app_dir))
    warnings.extend(validate_manifest_advisory(app_dir))
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
        # Gated identically to validate_css above, deliberately: an app whose
        # CSS is not being checked must not start receiving CSS advice about
        # files nothing else read.
        warnings.extend(validate_css_advisory(app_dir))
    errors.extend(validate_dependencies(app_dir))
    if check_prefix_safety:
        # DELIBERATELY OUTSIDE the `if not is_embedded` branch above. Every app
        # carrying this defect today (scholar, writer, figrecipe) IS an embedded
        # `_django` package, so gating this on `not is_embedded` would skip
        # precisely the population it exists to measure — and pass, forever.
        # GUARDED because validate_prefix_safety now REFUSES a path that is not
        # there rather than answering "clean" about it. That refusal is right
        # for a direct caller and wrong here: validate() already reports a
        # missing app directory as findings, and a gate reading those findings
        # must not start receiving an exception instead. The refusal is for the
        # peer running the rule against their own tree by hand; the findings
        # list is for the publication path.
        if Path(app_dir).is_dir():
            errors.extend(validate_prefix_safety(app_dir))
    # The three ported checks sit OUTSIDE the embedded/react gate above, like
    # the prefix rule and for the same reason: every app that would exercise
    # them today (scholar, writer, figrecipe) is an embedded `_django` package,
    # so gating on `not is_embedded` would skip exactly the population they
    # exist to measure — and pass, forever.
    if check_js_safety:
        errors.extend(validate_js(app_dir))
    if check_bundle_size:
        errors.extend(validate_bundle_size(app_dir))
    if check_privileges:
        errors.extend(validate_privileges(app_dir))
    if check_css_canonical:
        # GUARDED like the prefix rule, and for the same reason: `css_files()`
        # REFUSES a path that is not there rather than answering "clean" about
        # it, which is right for a peer running the rule by hand and wrong for
        # a gate that already reports a missing app directory as findings.
        #
        # The DENOMINATOR is dropped here on purpose. `validate()` returns a
        # flat list of error strings and cannot carry `files_scanned` or
        # `not_checked` without changing that contract — so a caller who needs
        # to know WHAT WAS SCANNED must call `validate_css_canonical()` and read
        # the report. This is exactly the loss that made "0 findings" mean two
        # different things twice in one evening, and it is accepted here only
        # because this path's zero is not published as a measurement.
        if Path(app_dir).is_dir():
            errors.extend(validate_css_canonical(app_dir).findings)
    return errors, warnings


# EOF
