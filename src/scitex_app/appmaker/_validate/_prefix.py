"""Mount-prefix safety — request URLs that do not survive being mounted."""

from __future__ import annotations

import re
from pathlib import Path

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
#
# `.open` is NOT here, deliberately. XMLHttpRequest's signature is
# `open(method, url)`, so a pattern that captures the FIRST string literal after
# the call reports the METHOD as the URL. Measured 2026-09-03 against
# scitex-writer's shipped bundle: two findings reading
#     inferred-base request URL 'GET'
# from `xhr.open("GET", url)`. 'GET' is not a URL, cannot be prefixed, and the
# remediation text told the author to join it to the mount. XHR is handled by
# _XHR_OPEN_URL below, which skips the method argument.
_REQUEST_CALL = r"(?:fetch|axios(?:\.\w+)?|new\s+URL|EventSource|WebSocket)"

# `xhr.open(METHOD, URL)` — capture the SECOND argument.
_XHR_OPEN_URL = re.compile(
    r"\.open\s*\(\s*['\"`][A-Za-z]+['\"`]\s*,\s*" + r"""['"`]([^'"`\n]*)['"`]"""
)

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

# BUILD CONFIGURATION IS NOT APPLICATION CODE, and this rule's own docstring
# already said so — "Static/asset base paths (a bundler `base` setting) are NOT
# inspected" — while the scan read the file anyway. Measured 2026-09-03 against
# scitex-writer:
#     vite.config.ts:5: inferred-base request URL '.'
# from `fileURLToPath(new URL(".", import.meta.url))`, which is Node's __dirname
# idiom evaluated at BUILD time. It issues no request, reaches no browser, and
# has no mount to resolve against. A documented exclusion that the code does not
# implement is not an exclusion.
PREFIX_SKIP_FILE_STEMS = (
    "vite.config",
    "rollup.config",
    "webpack.config",
    "esbuild.config",
    "vitest.config",
    "jest.config",
    "tailwind.config",
    "postcss.config",
    "babel.config",
    "next.config",
    "svelte.config",
    "astro.config",
)


def _is_build_config(path: Path) -> bool:
    """True for a bundler/tooling config, which runs at build time only."""
    return any(path.name.startswith(stem) for stem in PREFIX_SKIP_FILE_STEMS)


def strip_js_comments(source: str) -> str:
    """Blank out // and /* */ comments, PRESERVING STRING LITERALS.

    WHY THIS EXISTS. Without it the scan reads commented-out code as code.
    Measured 2026-09-03 on a file whose only match was inside a comment:

        // legacy, replaced in 0.9: fetch("/api/old");
        -> 1 finding, reported as a root-absolute request URL

    A detector keyed on a substring INVERTS ON DOCUMENTATION: the file that
    best explains why it removed a bad call looks identical to the file that
    still has it. This is the third instance of that shape found in one night
    -- scitex-ui hit it in a guard of theirs, I hit it in the mount-marker
    reader, and this one had been shipping since 0.9.0.

    WHY IT IS NOT A REGEX. `//` appears inside every absolute URL, so a naive
    `//.*$` turns `fetch("https://api.example.com/x")` into `fetch("https:` --
    mangling a string the scanner then misreads. That would trade a false
    POSITIVE for a false NEGATIVE, which is worse: the finding disappears and
    nothing says why. So this walks the source tracking whether it is inside a
    quote, and only treats `//` and `/*` as comment starts outside one.

    Comments are replaced by spaces of the SAME LENGTH, not deleted, so line
    numbers and column offsets in findings still point at the real source.
    """
    out = []
    i = 0
    n = len(source)
    quote = None  # the quote character currently open, or None
    while i < n:
        ch = source[i]
        if quote is not None:
            out.append(ch)
            if ch == "\\" and i + 1 < n:  # escaped char inside a string
                out.append(source[i + 1])
                i += 2
                continue
            if ch == quote:
                quote = None
            i += 1
            continue
        if ch in "\"'`":
            quote = ch
            out.append(ch)
            i += 1
            continue
        if ch == "/" and i + 1 < n and source[i + 1] == "/":
            while i < n and source[i] != "\n":
                out.append(" ")
                i += 1
            continue
        if ch == "/" and i + 1 < n and source[i + 1] == "*":
            while i < n and not (source[i] == "*" and i + 1 < n and source[i + 1] == "/"):
                out.append("\n" if source[i] == "\n" else " ")
                i += 1
            out.append("  ")
            i += 2
            continue
        out.append(ch)
        i += 1
    return "".join(out)


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
        concern with a different fix and different correct answers, and folding
        them in here would produce findings this rule cannot advise on. That
        exclusion is now ENFORCED by PREFIX_SKIP_FILE_STEMS rather than merely
        stated — until 2026-09-03 the scan read `vite.config.ts` and reported
        from it, so the sentence above was true of the intent and false of the
        code.
      - THIRD-PARTY VENDORED CODE IS STILL SCANNED, and its findings are real
        but usually not actionable by the app author. scitex-writer ships
        PDF.js, whose `document.baseURI` use is genuine inferred-base behaviour
        in code they did not write. Reported rather than skipped, because it
        DOES break under a mount — but the fix there is a library option or a
        vendor upgrade, not an edit to their source.
    """
    errors = []
    root = Path(app_dir)

    for path in sorted(root.rglob("*")):
        if path.suffix not in PREFIX_SCAN_SUFFIXES or not path.is_file():
            continue
        if any(part in PREFIX_SKIP_DIRS for part in path.parts):
            continue
        if _is_build_config(path):
            continue
        try:
            raw = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        # Comments are not code. Stripped with string literals preserved, and
        # replaced by same-length blanks so reported line numbers still match
        # the file on disk.
        content = strip_js_comments(raw)
        relpath = path.relative_to(root)

        seen_lines = set()
        for pattern in (PREFIX_REQUEST_LITERAL, PREFIX_URL_BINDING, _XHR_OPEN_URL):
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


# EOF
