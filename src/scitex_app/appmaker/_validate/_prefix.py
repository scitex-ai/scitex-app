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

# A BINDING'S NAME IS NOT EVIDENCE ABOUT ITS VALUE. `ATTR_SIGN_IN_URL` ends in
# _URL because it NAMES THE ATTRIBUTE THAT HOLDS a url -- the opposite of the
# string being one. Measured in scitex-ui's dim/_Dim.ts:43:
#
#     const ATTR_SIGN_IN_URL = "data-stx-dim-sign-in-url";
#     -> inferred-base request URL 'data-stx-dim-sign-in-url'
#
# So the binding pattern additionally requires the VALUE to carry a path
# separator. Tightening the NAME list instead is whack-a-mole: ATTR_*_URL,
# *_URL_PARAM and *_URL_HEADER are all the same shape.
#
# THE COST, stated because an enumeration's exclusions are invisible in its
# output: `const url = "search"` -- a single segment with no separator, fetched
# later -- is no longer reported. That value is genuinely UNDECIDABLE from the
# literal alone, and this rule already refuses to report undecidable cases as
# violations (see the variable-prefixed exclusion on validate_prefix_safety).
# Reporting unknown as a violation is the bug this file was written to avoid.
# The DIRECT form `fetch("search")` is unaffected -- it still reports.
_BINDING_VALUE_IS_PATHLIKE = re.compile(r"[/]|^\$\{")

# `new URL(<spec>, import.meta.url)` is the BUNDLER'S module-relative asset
# reference. Vite/Rollup resolve it at BUILD time into a hashed asset URL; it
# issues no runtime request and never resolves against the mount.
#
# THIS INDICTS AN EARLIER FIX OF MINE. On 2026-09-03 I removed exactly this
# idiom -- `new URL(".", import.meta.url)` -- by excluding the FILE it appeared
# in (vite.config, via PREFIX_SKIP_FILE_STEMS). That is not the discriminator.
# The signature is the SECOND ARGUMENT, and the idiom is just as valid in
# application source, where no file-based exclusion reaches it. Measured hours
# later in scitex-ui's pdf-viewer/index.ts:110, reported against code that is
# correct. Keying on WHERE a construct appears rather than WHAT it is leaves
# the class intact.
PREFIX_BUILD_TIME_URL = re.compile(
    r"new\s+URL\s*\(\s*" + _LITERAL + r"\s*,\s*import\.meta\.url"
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

#: The subset of the above whose comments are `<!-- -->` rather than `//`.
_HTML_SUFFIXES = frozenset({".html", ".htm"})

# Deliberately NOT validator.py's SKIP_DIRS, which excludes "assets" and "dist".
# The built bundle is what ships and is where these URLs actually live —
# scitex-writer's offending anchor is in a COMMITTED static/writer/assets/
# index.js, and its TS source can disagree with it. Skipping build output would
# hide the population this rule exists to measure.
# INSTALLED DEPENDENCIES ARE NOT THE APPLICATION, and until 2026-09-03 this set
# said so for JavaScript only. "node_modules" was excluded from the first
# version; the Python equivalent never was, so a scan pointed at a project ROOT
# descended into the virtualenv and reported the app's own dependencies as its
# violations. Measured against three peer checkouts, each of which holds a
# .venv/:
#     scitex-writer 46, scitex-scholar 46, scitex-ui 48 findings
# dominated by playwright's driver bundle (a TEST tool), matplotlib's
# web_backend templates, and figrecipe's built assets installed as a package.
# None of those ship under the scanned app's mount, so none can break under it.
# scitex-scholar in particular reads 46 here while its own source is clean.
#
# "site-packages" rather than the venv's NAME is what does the work: it holds
# whatever the directory is called (.venv, venv, env, /opt/venv-sac). The two
# venv names are listed as well so files directly under a venv root are covered.
#
# NOT added, deliberately: "dist" and "assets" - see the note above. Vendored
# code the app SHIPS stays in scope for the same reason; scitex-writer's PDF.js
# reaches the browser under the mount, so its findings are real.
PREFIX_SKIP_DIRS = frozenset(
    {
        "node_modules",
        ".git",
        "__pycache__",
        ".vite",
        "_docs",
        "site-packages",
        ".venv",
        "venv",
        # A LINKED WORKTREE IS ANOTHER CHECKOUT OF THIS SAME REPO, so every
        # finding in the real tree is reported again for each worktree holding
        # that file. Measured the same day, after the dependency fix above:
        #     scitex-writer  10 rows -> 5 distinct, the rest .worktrees/ copies
        #     scitex-ui       6 rows -> 3 distinct, likewise
        # The duplicates name paths that are not the tree the author is fixing,
        # and the count is a function of how many branches happen to be checked
        # out — which is not a property of the application at all.
        ".worktrees",
    }
)

# BUILD CONFIGURATION IS NOT APPLICATION CODE, and this rule's own docstring
# already said so — "Static/asset base paths (a bundler `base` setting) are NOT
# inspected" — while the scan read the file anyway. Measured 2026-09-03 against
# scitex-writer:
#     vite.config.ts:5: inferred-base request URL '.'
# from `fileURLToPath(new URL(".", import.meta.url))`, which is Node's __dirname
# idiom evaluated at BUILD time. It issues no request, reaches no browser, and
# has no mount to resolve against. A documented exclusion that the code does not
# implement is not an exclusion.
# RE-CHECKED 2026-09-03 against the new construct-level rule, and KEPT.
# Disabling this list entirely changes NOTHING on three real trees:
#     writer delta=0   scholar delta=0   ui delta=0
# so it is currently subsumed. It stays anyway, and the reason is the LIMIT of
# that measurement rather than affection for the mechanism: the only build
# config present in those trees is vite.config. Dropping the rollup/webpack/
# esbuild entries on vite-only evidence would extrapolate past what was
# measured. Re-run the comparison when a tree here carries one of the others;
# if it is still zero, this list should go rather than linger as a second
# mechanism for one job.
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


# The strippers moved to `_comments` when the same blindness was found in
# validate_js / validate_css / validate_templates. Re-exported here because
# they were public from this module first.
from ._comments import (  # noqa: F401
    strip_css_comments,
    strip_html_comments,
    strip_js_comments,
)

def _is_build_config(path: Path) -> bool:
    """True for a bundler/tooling config, which runs at build time only."""
    return any(path.name.startswith(stem) for stem in PREFIX_SKIP_FILE_STEMS)


#: The OPENING `{%` of a Django or Jinja tag, anywhere in the literal.
#:
#: DELIBERATELY NOT `\{%.*?%\}`. That was the first version and it matched
#: nothing, because the literal reaching this function is not the source text:
#: the extractor stops at the inner quote, so
#:
#:     fetch("{% url 'api:search' %}")   arrives here as   "{% url "
#:
#: — an opening tag with no closing one. Written against what I assumed the
#: literal looked like rather than what the extractor produces, and found by
#: running the case rather than by reading the pattern.
#:
#: An opening `{%` is sufficient on its own: it has no other meaning inside a
#: request URL. Unanchored so `"/{% ... %}"` and `"{% ... %}?page=1"` are both
#: recognised as server-built.
_TEMPLATE_TAG = re.compile(r"\{%")


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

    # A Django/Jinja tag: the whole path is produced by the server's URLconf,
    # which UNDER A MOUNT ALREADY INCLUDES THE MOUNT PREFIX. So this is not
    # merely undecidable here — it is the prescribed idiom, and 0.14.0 reported
    # it as a violation. Measured on scitex-hub's tree: 11 of 339 findings were
    # `{% url %}`, every one of them correct code.
    #
    # NOT the same judgement as `${...}` below, and the difference is what makes
    # both right: there the LEADING SLASH is decidable whatever the expression
    # yields, so a root-absolute literal is still reported. Here nothing before
    # the path is ours to read, and per this function's own three-valued rule an
    # unknown must not be collapsed into a violation.
    if _TEMPLATE_TAG.search(url):
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


def scannable_files(app_dir: str | Path) -> list[Path]:
    """The files this rule reads, in scan order — the DENOMINATOR of a result.

    "0 findings" is not a claim on its own; "0 findings across N files" is. When
    N is zero the honest report is NOT SCANNED, not CLEAN, and the two are
    indistinguishable in a bare finding count.

    This exists because the distinction was not academic. The measurement the
    2026-09-05 arming decision rested on pointed at `<repo>/.worktrees/
    prefix-check` in two peer repositories. Those paths DID NOT EXIST. rglob
    over a missing directory yields nothing, so the scan reported zero findings
    and was read as clean; the positive control passed throughout, because a
    control runs on a temp tree that does exist. The instrument was working and
    aimed at nothing.

    Exported so a caller reporting a denominator uses THIS walk rather than
    re-deriving it — a second implementation of the skip rules is a second
    thing to drift. `PREFIX_SCAN_SUFFIXES` and `PREFIX_SKIP_DIRS` are public
    for the same reason, at scitex-hub's request: they were asked to report
    files-scanned and the constants needed to do it were behind an underscore.
    """
    root = Path(app_dir)
    _refuse_unscannable(root)
    out = []
    for path in sorted(root.rglob("*")):
        if path.suffix not in PREFIX_SCAN_SUFFIXES or not path.is_file():
            continue
        # RELATIVE to the scan root, deliberately. `path.parts` walks the whole
        # absolute path, so a scan root that merely SITS under a skipped
        # directory had every one of its files excluded by an ANCESTOR name the
        # caller never chose. Measured: a root under `.worktrees/` returned 0
        # files and 0 findings while containing a live violation.
        if any(part in PREFIX_SKIP_DIRS for part in path.relative_to(root).parts):
            continue
        if _is_build_config(path):
            continue
        out.append(path)
    return out


def _refuse_unscannable(root: Path) -> None:
    """Raise rather than answer "clean" about a directory that is not there.

    A wrong path is a CALLER error and the only honest response is to say so.
    Returning an empty list lets a typo, a removed worktree, or a relative path
    resolved from the wrong cwd read as a passing result — and this rule is now
    a gate, so a caller can also "clear" it by pointing it at nothing.

    THE SECOND CASE COST A PEER A WHOLE MEASUREMENT, AND MY OWN ADVICE CAUSED
    IT. I told scitex-hub to scan the REF rather than a working tree, and to do
    that with a detached worktree. Worktrees live under `.worktrees/`, which is
    in PREFIX_SKIP_DIRS so that a scan of a REPO ROOT does not descend into
    sibling worktrees. Both pieces are individually right; together they produce
    a silent zero, because the walk excluded every file by an ANCESTOR name.
    hub reported 1,116 files / 0 findings and their tree in fact holds 262.

    THE FIX IS THE RELATIVE MATCH, AND ONLY THAT. My first version also REFUSED
    a root sitting inside a skipped directory — belt-and-braces, and wrong.
    Once the walk matches relative to the root, such a scan is CORRECT, so the
    refusal removed a capability rather than adding a guard. hub found it by
    saying what they would actually do: their hooks DENY tracked-file edits
    outside `<repo>/.worktrees/<name>/`, so scanning a worktree is their normal
    path, not an accident. A guard that fires on the mandated workflow is a
    guard aimed at the wrong thing.

    They were explicit that an `allow_skipped_ancestor=True` escape hatch would
    be the wrong answer — it re-opens the silent zero — and they are right. The
    answer is that there is nothing to escape from once the match is relative.
    """
    if not root.exists():
        raise FileNotFoundError(
            f"cannot scan {root}: no such path. A prefix-safety result of "
            f"'no findings' would be indistinguishable from 'never scanned', "
            f"so this refuses rather than reporting clean."
        )
    if not root.is_dir():
        raise NotADirectoryError(
            f"cannot scan {root}: not a directory. Pass the APP directory; "
            f"scanning a single file is not what this rule measures."
        )


def validate_prefix_safety(app_dir: str | Path) -> list[str]:
    """Report request URLs that do not resolve correctly under an app mount.

    ARMED 2026-09-05. `validate()` runs this by default, so it is now a GATE:
    callers that raise on a non-empty result — including scitex-hub's
    PUBLICATION path — will refuse an app over it. It said "NOT ARMED … a check
    nobody branches on is not a check" from the day it was written until the day
    that stopped being true.

    ARMED ON MEASUREMENT, NOT ON ELAPSED TIME. Every consumer repo was scanned
    on its current ref, each against a positive control so a zero was
    distinguishable from a scan that never ran: writer / figrecipe / scholar
    clean, and scitex-hub 29 app dirs / 1471 files / 0 findings with a control
    returning exactly 1. hub asked to be consulted before arming and gave the
    go-ahead 2026-09-05T20:16Z.

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
    _refuse_unscannable(root)

    for path in scannable_files(root):
        try:
            raw = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        # Comments are not code. Stripped with string literals preserved, and
        # replaced by same-length blanks so reported line numbers still match
        # the file on disk.
        if path.suffix in _HTML_SUFFIXES:
            # HTML comments first: an .html file is markup AND script, and the
            # JS pass below cannot see `<!-- -->`.
            raw = strip_html_comments(raw)
        content = strip_js_comments(raw)
        relpath = path.relative_to(root)

        seen_lines = set()
        # Spans covering `new URL(<spec>, import.meta.url)`. Collected FIRST so
        # a match landing inside one can be dropped: that literal is a module
        # specifier the bundler resolves at build time, not a request URL.
        # A ROOT-ABSOLUTE specifier is NOT exempt, even here: `new URL("/x", base)`
        # discards the base's path and resolves from the origin root, so
        # import.meta.url does not save it and it still breaks under a mount.
        # Measured -- suppressing the whole construct silently killed a REAL
        # finding in scitex-writer's built bundle:
        #     claims-list.js:1 root-absolute '/static/writer/assets/pdf.worker.min.mjs'
        # Found only by asking WHICH row disappeared rather than trusting a
        # count that had moved in the direction I wanted.
        build_time_spans = [
            m.span()
            for m in PREFIX_BUILD_TIME_URL.finditer(content)
            if not m.group(1).startswith("/")
        ]
        for pattern in (PREFIX_REQUEST_LITERAL, PREFIX_URL_BINDING, _XHR_OPEN_URL):
          for match in pattern.finditer(content):
            if any(lo <= match.start() < hi for lo, hi in build_time_spans):
                continue
            if pattern is PREFIX_URL_BINDING and not _BINDING_VALUE_IS_PATHLIKE.search(
                match.group(1)
            ):
                continue  # a url-ish NAME says nothing about the VALUE
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
