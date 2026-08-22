"""App validator — check structure, security, manifest, templates, and CSS."""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path

logger = logging.getLogger(__name__)

REQUIRED_FILES = [
    "apps.py",
    "views.py",
    "urls.py",
    "LICENSE",
    "README.md",
    "manifest.json",
]

FORBIDDEN_PATTERNS = [
    (r"\bsubprocess\b", "subprocess"),
    (r"\bos\.system\b", "os.system"),
    (r"\beval\s*\(", "eval()"),
    (r"\bexec\s*\(", "exec()"),
    (r"\b__import__\b", "__import__"),
]

MANIFEST_REQUIRED_KEYS = ["name", "slug", "label", "pip_package", "icon", "license"]

# Frame selectors that app CSS must not style
PROTECTED_SELECTORS = [
    ".stx-shell-sidebar",
    ".stx-shell-sidebar__title",
    ".panel-resizer",
    "footer",
]

# Forbidden frame block overrides
FORBIDDEN_BLOCK_OVERRIDES = [
    "workspace_worktree_pane",
    "workspace_ai_pane",
    "workspace_viewer_pane",
    "workspace_apps_pane",
]

# ── Mount-prefix safety ──────────────────────────────────────────────────────
# Routes the PLATFORM owns. They live at the server root, are NOT under an app's
# mount, and prefixing them breaks them (see skills 33_mount-prefix.md,
# "Prefix YOUR endpoints. Not the platform's."). Root-absolute is CORRECT here.
PLATFORM_ROUTE_PREFIXES = (
    "/platform/api/",
    "/apps/store/api/",
)

# Schemes and forms that are not app-relative at all, so the mount cannot apply.
_PREFIX_SAFE_LEADERS = ("http://", "https://", "//", "data:", "blob:", "mailto:", "#", "?")

# The identifier the contract prescribes for the mount prefix. stx-mount.js
# declares `const STX_MOUNT`, and 33_mount-prefix.md tells apps to join
# base + "/your/path". A template literal opening `${STX_MOUNT}` is therefore
# the CORRECT fix, not a finding — see _prefix_finding_class.
MOUNT_IDENTIFIERS = ("STX_MOUNT",)

# A literal whose first token is an interpolation: `${something}/api/x`.
_LEADING_INTERPOLATION = re.compile(r"^\$\{\s*([A-Za-z_$][\w$]*)\s*\}")

# Call sites that issue a request and therefore must resolve against the mount.
_REQUEST_CALL = r"(?:fetch|axios(?:\.\w+)?|\.open|new\s+URL|EventSource|WebSocket)"

# A string literal argument: 'x', "x" or `x`.
_LITERAL = r"""['"`]([^'"`\n]*)['"`]"""

PREFIX_REQUEST_LITERAL = re.compile(_REQUEST_CALL + r"\s*\(\s*" + _LITERAL)

# A literal bound to a url-ish name and fetched on a LATER line:
#     const url = `/api/graph/network?doi=${doi}`;
#     const resp = await fetch(url);
# Matching only the direct-argument form above found 1 of scitex-scholar's 3
# known root-absolute sites, because two of them take this shape. Detecting the
# rest properly needs dataflow; binding-by-name is the cheap approximation and
# its limits are documented on validate_prefix_safety.
PREFIX_URL_BINDING = re.compile(
    r"\b(?:const|let|var)\s+\w*(?:url|uri|endpoint|path)\w*\s*=\s*" + _LITERAL,
    re.IGNORECASE,
)

# Reading an implicit base out of the document/location and slicing it. These
# produce a base by INFERENCE, which is what breaks across mounts.
PREFIX_INFERRED_BASE = (
    (re.compile(r"\bdocument\.baseURI\b"), "document.baseURI"),
    (re.compile(r"\bnew\s+URL\s*\([^)]*,\s*location\b"), "new URL(..., location)"),
    (re.compile(r"\blocation\.(?:pathname|href)\b\s*\.\s*(?:split|slice|substring|replace)"),
     "location.pathname/href string-slicing"),
)

PREFIX_SCAN_SUFFIXES = (".js", ".mjs", ".jsx", ".ts", ".tsx", ".html")

# Deliberately NOT validator.py's SKIP_DIRS, which excludes "assets" and "dist".
# The built bundle is what ships and is where these URLs actually live —
# scitex-writer's offending anchor is in a COMMITTED static/writer/assets/
# index.js, and its TS source can disagree with it. Skipping build output would
# hide the population this rule exists to measure.
PREFIX_SKIP_DIRS = frozenset({"node_modules", ".git", "__pycache__", ".vite", "_docs"})


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


def validate_security(app_dir: str | Path) -> list[str]:
    """Scan Python files for forbidden patterns."""
    errors = []
    root = Path(app_dir)

    excluded_dirs = {"__pycache__", ".git", "scitex", "node_modules", ".venv", "venv"}
    for py_file in root.rglob("*.py"):
        if excluded_dirs & set(py_file.relative_to(root).parts):
            continue
        try:
            content = py_file.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        relpath = py_file.relative_to(root)
        for pattern, name in FORBIDDEN_PATTERNS:
            if re.search(pattern, content):
                errors.append(f"Forbidden pattern '{name}' found in {relpath}")

    return errors


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


def validate_templates(app_dir: str | Path) -> list[str]:
    """Check template compliance with workspace frame rules."""
    errors = []
    root = Path(app_dir)
    app_name = _get_app_name(root)
    if not app_name:
        return errors

    index_html = root / "templates" / app_name / "index.html"
    if not index_html.exists():
        return errors

    try:
        content = index_html.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return errors

    # Must extend global_base.html
    if "global_base.html" not in content:
        errors.append("index.html must extend 'global_base.html'")

    # Must have {% block content %}
    if "block content" not in content:
        errors.append("index.html must define {% block content %}")

    # Must NOT override frame blocks
    for block_name in FORBIDDEN_BLOCK_OVERRIDES:
        if f"block {block_name}" in content:
            errors.append(f"index.html must not override '{{% block {block_name} %}}'")

    return errors


def validate_css(app_dir: str | Path) -> list[str]:
    """Check CSS compliance with workspace frame rules."""
    errors = []
    root = Path(app_dir)

    for css_file in root.rglob("*.css"):
        if ".git" in str(css_file):
            continue
        try:
            content = css_file.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        relpath = css_file.relative_to(root)

        # Warn about deprecated --color-* variables
        if re.search(r"var\(--color-", content):
            errors.append(
                f"{relpath}: use --workspace-* or --text-* CSS variables "
                f"instead of --color-* (see workspace template spec)"
            )

        # Check for !important on protected selectors
        for selector in PROTECTED_SELECTORS:
            pattern = re.escape(selector) + r"[^{]*\{[^}]*!important"
            if re.search(pattern, content, re.DOTALL):
                errors.append(f"{relpath}: must not use !important on '{selector}'")

        # Check for footer hiding
        if re.search(r"footer\s*\{[^}]*display\s*:\s*none", content, re.DOTALL):
            errors.append(f"{relpath}: must not hide the footer")

    return errors


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


def _prefix_finding_class(url: str) -> str | None:
    """Classify one request-call URL literal. None = nothing to report.

    Returns the PREDICATE that matched, not a guess at intent — the finding text
    is built from this, so a reader can always reproduce the verdict.

    THIS SIGNAL IS THREE-VALUED and 0.9.0 shipped it as two. A literal opening
    with an interpolation — `${SOMETHING}/api/x` — is VARIABLE-PREFIXED: neither
    root-absolute nor document-relative, because what precedes the path is a
    value this scanner cannot see. 0.9.0 collapsed that unknown into
    "inferred-base", so it flagged `${STX_MOUNT}/api/search` — which is exactly
    the fix its own remediation text prescribes. Reported by scitex-scholar
    against their CORRECTED tree, and reproduced here against the shipped wheel.
    """
    if not url or url.startswith(_PREFIX_SAFE_LEADERS):
        return None

    leading = _LEADING_INTERPOLATION.match(url)
    if leading:
        # Prefixed by the contract's own mount identifier -> this IS the fix.
        if leading.group(1) in MOUNT_IDENTIFIERS:
            return None
        # Prefixed by some OTHER variable. Genuinely UNKNOWN: it may be a
        # correct base under a different name, or a wrong one. Deciding needs
        # the value, which a scanner does not have, so it is not reported —
        # collapsing unknown into "violation" is what produced the 0.9.0 bug,
        # and flagging correct code is worse than missing an incorrect base.
        # Recorded as an explicit exclusion on validate_prefix_safety.
        return None

    if url.startswith("/"):
        if url.startswith(PLATFORM_ROUTE_PREFIXES):
            return None  # platform-owned, correctly at the server root
        return "root-absolute"
    # No leading slash, no scheme, no interpolation: resolves against the
    # DOCUMENT's URL, so it depends on whether the mount happened to be
    # requested with a trailing slash. Works at /app/ and 404s at /app.
    return "inferred-base"


def validate_prefix_safety(app_dir: str | Path) -> list[str]:
    """Report request URLs that do not resolve correctly under an app mount.

    NOT ARMED. `validate()` skips this unless `check_prefix_safety=True`, so
    today this produces a RECORD, not a gate — no caller fails a build on it.
    Saying so explicitly because calling it a "validator" implies the stronger
    claim, and a check nobody branches on is not a check.

    TWO CLASSES, and the second is the reason this rule exists:

      root-absolute   `fetch("/api/x")` — ignores the mount outright. The LOUD
                      failure: it 404s identically everywhere, so it gets found.

      inferred-base   `fetch("api/x")` — no leading slash, so it resolves against
                      the document URL. The QUIET one: it works at "/app/" and
                      404s at "/app", i.e. it passes a smoke test and breaks on a
                      redirect or a differently-typed link. scitex-scholar
                      measured exactly this (search.js:125). A root-absolute-only
                      rule would have caught 3 of their 4 sites and left this one.

    WHAT THIS DOES NOT COVER, stated because an enumeration's exclusions are
    invisible in its output:

      - A URL prefixed by a variable OTHER than the contract's own identifier
        (see MOUNT_IDENTIFIERS). `${someBase}/api/x` is not reported, because
        whether that variable holds the mount is undecidable without its value.
        This is an UNKNOWN deliberately not reported as a violation.
      - Static/asset base paths (a bundler `base` setting,
        e.g. vite's "/static/<app>/") are NOT inspected. They are a build-config
    concern with a different fix and different correct answers, and folding them
    in here would produce findings this rule cannot advise on.
    """
    errors = []
    root = Path(app_dir)

    for path in sorted(root.rglob("*")):
        if path.suffix not in PREFIX_SCAN_SUFFIXES or not path.is_file():
            continue
        if any(part in PREFIX_SKIP_DIRS for part in path.parts):
            continue
        try:
            content = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        relpath = path.relative_to(root)

        seen_lines = set()
        for pattern in (PREFIX_REQUEST_LITERAL, PREFIX_URL_BINDING):
          for match in pattern.finditer(content):
            kind = _prefix_finding_class(match.group(1))
            if kind is None:
                continue
            line = content.count("\n", 0, match.start()) + 1
            if (line, match.group(1)) in seen_lines:
                continue  # same literal caught by both patterns
            seen_lines.add((line, match.group(1)))
            errors.append(
                f"{relpath}:{line}: {kind} request URL {match.group(1)!r} — "
                f"does not resolve under an app mount. Read the mount prefix from "
                f'<meta name="stx-mount"> and join it as base + "/your/path". '
                f"Platform routes ({', '.join(PLATFORM_ROUTE_PREFIXES)}) are exempt."
            )

        for pattern, what in PREFIX_INFERRED_BASE:
            for match in pattern.finditer(content):
                line = content.count("\n", 0, match.start()) + 1
                errors.append(
                    f"{relpath}:{line}: inferred-base via {what} — derives the "
                    f"mount from the current document instead of reading it from "
                    f'<meta name="stx-mount">. Correct at one mount depth by luck.'
                )

    return errors
