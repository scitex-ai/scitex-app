#!/usr/bin/env python3
"""Comment strippers shared by every rule that scans source TEXT.

WHY THIS MODULE EXISTS, AND WHY IT IS LATE. `strip_js_comments` was written
2026-09-03 for one rule, and its docstring already carried the whole argument:
a detector keyed on a substring INVERTS ON DOCUMENTATION — the file that best
explains why it removed a bad call looks identical to the file that still has
it. On 2026-09-05 the HTML version was added, for the same one rule.

Nobody asked whether the OTHER text-scanning rules had ever received it. They
had not. Measured against the shipped 0.14.2, each case paired with a control:

    validate_js          live eval() 1   commented 1    false positive
    validate_css         live rule   1   commented 1    false positive
    validate_templates   forbidden block, commented     false positive
    validate_templates   REQUIREMENTS PRESENT ONLY IN A COMMENT -> 0 errors
                                                        FALSE NEGATIVE

The last one runs the other way and is the reason this module is not a tidy-up.
Those checks are PRESENCE tests (`"global_base.html" not in content`), so a page
that does not extend the frame passes as long as the string appears in a
comment. Every other instance was a noisy false positive; that one is silent,
and it sits in a check that runs by default.

scitex-ui named the general shape, about a defect of their own the same day:
the insight already existed, it had simply never been carried across a
boundary — the rule is not missing, its SCOPE is implicit. Putting the three
strippers in one module makes the scope explicit: this is where a rule that
reads source text comes to get its comments removed.

TWO CONTRACTS EVERY STRIPPER HERE KEEPS:

  1. BLANK, NEVER DELETE. Comments become spaces of the SAME LENGTH, so line
     and column numbers in a finding still point at the real file.
  2. DO NOT TRADE A FALSE POSITIVE FOR A FALSE NEGATIVE. Hiding too much is
     worse than reporting too much: the finding disappears and nothing says
     why. Hence the string-awareness below rather than a naive regex.
"""

from __future__ import annotations

import re

__all__ = [
    "strip_css_comments",
    "strip_html_comments",
    "strip_js_comments",    "strip_python_comments",
]


def _blank(source: str, spans) -> str:
    """Replace each span with same-length spaces, preserving newlines."""
    out = list(source)
    for lo, hi in spans:
        for i in range(lo, hi):
            if out[i] != "\n":
                out[i] = " "
    return "".join(out)


def strip_python_comments(source: str) -> str:
    """Blank out `# ...` comments, leaving string literals intact.

    Found by asking the same question of every remaining rule rather than
    stopping at three. `validate_security` regex-scans `.py` files for
    forbidden patterns and never stripped comments; measured on the shipped
    0.14.2:

        live      os.system("ls")                    1 finding
        COMMENTED # removed in 0.9: os.system("ls")  1 finding

    That is a SECURITY rule reporting the file that documents the call it
    removed — the same shape as the other three, in the rule where a spurious
    finding is most likely to be argued with rather than acted on.

    A `#` inside a string is not a comment (`S = "#"`), so this tracks quotes
    rather than matching a pattern — the same reason `strip_js_comments` is not
    a regex.

    DOCSTRINGS ARE DELIBERATELY LEFT ALONE, so a docstring mentioning
    `os.system` still reports. A docstring is a string the module genuinely
    contains, not a comment the parser discards, and deciding which strings are
    prose is a different judgement needing its own calibration. Left reporting
    rather than guessed at — guessing is how the first of these got here. Same
    treatment as a `<pre>` block in HTML.
    """
    quotes = ('"""', "'''", '"', "'")
    spans = []
    i = 0
    n = len(source)
    quote = None
    while i < n:
        if quote:
            if source[i] == "\\":
                i += 2
                continue
            if source.startswith(quote, i):
                i += len(quote)
                quote = None
                continue
            i += 1
            continue
        for q in quotes:
            if source.startswith(q, i):
                quote = q
                i += len(q)
                break
        else:
            if source[i] == "#":
                end = source.find("\n", i)
                end = n if end == -1 else end
                spans.append((i, end))
                i = end
                continue
            i += 1
    return _blank(source, spans)


#: `/* ... */`, non-greedy. CSS has no line comment: `//` appears inside every
#: `url(https://...)`, so treating it as one would mangle a live declaration.
_CSS_BLOCK_COMMENT = re.compile(r"/\*.*?\*/", re.DOTALL)


def strip_css_comments(source: str) -> str:
    """Blank out `/* ... */`, leaving quoted strings intact.

    A `/*` inside a quoted value (`content: "/*"`) does not open a comment, and
    a `*/` inside one does not close it. Getting that wrong blanks live
    declarations up to the next quote — the false-negative trade this module
    refuses.

    This is the exact shape of the incident scitex-ui reported: a path quoted
    inside a CSS comment was read as a live reference by a text scanner, and
    took down every PR in a peer repository.
    """
    spans = []
    i = 0
    n = len(source)
    quote = None
    while i < n:
        ch = source[i]
        if quote:
            if ch == "\\":
                i += 2
                continue
            if ch == quote:
                quote = None
            i += 1
            continue
        if ch in "\"'":
            quote = ch
            i += 1
            continue
        if source.startswith("/*", i):
            m = _CSS_BLOCK_COMMENT.match(source, i)
            end = m.end() if m else n  # unterminated: to end of file
            spans.append((i, end))
            i = end
            continue
        i += 1
    return _blank(source, spans)


#: Matches an HTML comment, non-greedy so the FIRST `-->` closes it. Unlike the
#: JS case a regex is safe here: `<!--` has no second meaning inside markup, and
#: `-->` inside a `<script>` string is handled by scanning scripts separately —
#: see strip_html_comments.
_HTML_COMMENT = re.compile(r"<!--.*?-->", re.DOTALL)
_HTML_SCRIPT_BLOCK = re.compile(
    r"<script\b[^>]*>.*?</script\s*>", re.DOTALL | re.IGNORECASE
)


def strip_html_comments(source: str) -> str:
    """Blank out `<!-- ... -->`, leaving `<script>` bodies untouched.

    WHY THIS EXISTS, AND WHY IT IS LATE. `strip_js_comments` below has solved
    exactly this problem for JavaScript since 2026-09-03, with exactly this
    argument in its docstring: "a detector keyed on a substring INVERTS ON
    DOCUMENTATION — the file that best explains why it removed a bad call looks
    identical to the file that still has it." `.html` was never given the same
    treatment. Nobody noticed while the rule was a RECORD; it became visible the
    week the rule became a GATE, because a false positive stopped being noise in
    a report and started refusing someone's app.

    Measured on the shipped 0.14.0 before this existed:

        <!-- fetch("/api/x"); -->        1 finding   <- text no browser requests
        <pre>fetch("/api/x");</pre>      1 finding   <- a teaching block

    SCRIPT BODIES ARE EXCLUDED FROM THIS PASS, not because they are safe, but
    because they are JavaScript and the JS stripper runs over them afterwards.
    Blanking `<!-- -->` inside a script would also eat the legacy
    `<!--` guard idiom and, worse, any `-->` appearing inside a JS string would
    silently terminate a "comment" that never started — turning a false POSITIVE
    into a false NEGATIVE, which is the trade `strip_js_comments` explicitly
    refuses to make. A finding that vanishes tells no one why.

    `<pre>` IS DELIBERATELY NOT HANDLED HERE. A code sample in a `<pre>` block
    is documentation and reports today, but stripping it needs the same
    both-directions calibration and a clear rule for distinguishing a sample
    from live markup. Left reporting rather than guessed at; see the card.

    Comments are replaced by spaces of the SAME LENGTH, never deleted, so
    reported line and column numbers still point at the real source — the same
    contract as the JS stripper, and the reason a file with a comment on line 3
    does not misreport every finding after it.
    """
    spans = [m.span() for m in _HTML_SCRIPT_BLOCK.finditer(source)]

    def _in_script(pos: int) -> bool:
        return any(lo <= pos < hi for lo, hi in spans)

    out = list(source)
    for m in _HTML_COMMENT.finditer(source):
        if _in_script(m.start()):
            continue
        for i in range(m.start(), m.end()):
            if out[i] != "\n":
                out[i] = " "
    return "".join(out)


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


# EOF
