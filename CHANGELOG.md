# Changelog

All notable changes to `scitex-app` are documented here.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/);
versions follow [Semantic Versioning](https://semver.org/).

## [Unreleased]

## [0.15.2] - 2026-09-06

Patch. A longer name is a different name, and one rule is one finding. Both
came out of scitex-hub's second step-2 run, and both were attributed by them to
their own code rather than to this rule.

### Fixed — an exact name matched every name that EXTENDS it

`.stx-shell-sidebar__header` and `.stx-shell-sidebar__header-compact` are
unrelated selectors; a rule on the second cannot touch the first. `name in
selector` said otherwise, so eight `__header-compact` rules in `writer_app`
were reported as `!important on the shared component
'.stx-shell-sidebar__header'` — **a finding naming a class the selector does
not contain**.

hub read the same eight as "writer minted a class inside the shell's BEM
namespace, and the shell renders zero of them, so nothing is reached". That is
true, and worth raising with writer — but it explained the wrong thing. The
rule was not correctly reporting a phantom target; it was matching a different
class.

`-` is a legal class-name character, so the guard is `(?![\w-])`, the same
boundary the footer rule already carried and this one did not. The leading side
needs none: `.foo` cannot occur inside `.my-foo`, because the `.` is part of
the token. `SHELL_INSTANCE_PREFIXES` are exempt and stay substring matches —
they are prefix FAMILIES by construction (`.wft-` is meant to match
`.wft-node`), which is exactly the distinction `in` erased: it made every exact
name behave like a prefix.

Also fixed for `#main-content-2`, `#workspace-layout-old`,
`.workspace-pane-mine`, `.panel-resizer-custom` — measured, all six tiers.

### Fixed — one rule produced two findings

`.stx-shell-sidebar` and `.stx-shell-sidebar__header` are both in
`SHARED_COMPONENT_CLASSES` and both substring-matched the same selector, so a
single declaration reported twice under two names. **hub's eight findings were
four rules.**

A count that inflates is worse than one that is merely incomplete, because it
reads as more evidence than exists — and this one inflated inside a number
being used to decide whether to arm. A matched name that is a proper substring
of another matched name is now dropped; the most specific match describes the
selector. Two genuinely different names (`.panel-resizer, .h-resizer`) still
report twice, because neither contains the other.

### What this does to hub's measurement

Their 0.15.1 run: 428 files, 27 findings, all 27 opened, **9 defects**. Eight
of the 27 were the `__header-compact` group. Those were four rules, and after
this release they are zero — so the number they re-run against 0.15.2 should
fall by eight, and none of the nine defects is among them.

Not restated here as a corrected total: that is hub's number to produce from
their own ref, and predicting it is the thing this changelog keeps saying not
to do.

### Added — every finding now carries `file:line:` and the selector it matched

scitex-hub named the mechanism of their own mistake precisely enough to remove
it:

> "The rule I have been quoting at myself all evening is 'a finding is a claim
> about a string, so open the match'. I opened the FILE. Opening the match
> means reading the string the tool actually emitted and checking it appears
> where the tool says it does. I did not do the last step, and it is the step."

They went to the file, found a class that looked like the reported one, and
wrote a correct paragraph about the wrong object — **arriving at the right
verdict from the wrong evidence, which is worse than being wrong, because a
wrong verdict gets challenged and a right one does not.**

That step was hard for a reason in this code, not in their method: four of the
message forms named a class without quoting the selector, and none carried a
position. So the finding now reads

    static/a.css:177: !important on the shared component '.panel-resizer' in
    'div[class*="editor"]:not(.panel-resizer)' — …

and "does the named thing actually appear in what was matched?" is answerable
from the finding text alone. Put side by side, the substring bug above is
visible on sight. A warning would not have helped; this is the mechanical
form of the rule.

The `display:none` and body-state checks moved inside the rule loop to get a
line, joining the footer check that moved there in 0.15.1.

### What is NOT fixed, and stays declared

Ten of hub's 27 were rules confined by an ancestor to the app's own subtree
(`.writer-workspace .h-resizer`, `body.scholar-page #main-content`). The
`!important` is real and cannot reach a shell instance outside that subtree.
Detecting that is the subject question — the same one the
`:is(header, footer)` trade and tier 3 are already waiting on a parser for —
so it stays in `not_checked` rather than being half-implemented.

hub's own read, which decided it: *"an advisory rule that reports a
scoped-but-`!important` rule is not wrong; it made me go look, and going to
look is what found the resizer bug."* That bug — `.panel-resizer` given
`z-index: 100 !important` in one writer file and `z-index: 1 !important` in
another, both bare, on a class the shell renders 50 times, load order deciding
which wins for every app on the page — is what the rule exists to find.

## [0.15.1] - 2026-09-06

Patch. An EXCLUDED name is not a target — and a MATCHED one still is. The first
run against a real population found this in ten minutes.

### Fixed — `:not()` and `:has()` arguments read as targets

```css
div[class*="editor"]:not(.panel-resizer) { overflow: visible !important }
```

reported `!important on the shared component '.panel-resizer'`. The rule
EXCLUDES resizers from a rule about editors; it does not style one. Same
semantics as the `:not(footer)` case 0.15.0 fixed, in a check that fix did not
reach: 0.15.0 blanked parenthesised arguments in the two FOOTER checks only,
and the name-membership checks — tier 1 ids, tier 1 prefixes, `APP_CONTAINERS`,
`SHARED_COMPONENT_CLASSES`, and the `:root` token check — all still read the
raw selector.

Found by scitex-hub running 0.15.0 against their own tree
(`develop@4ec9c4066`, 428 files scanned via `css_files()`, 29 findings) — real
code, from `writer_app/css/editor/editor.css:177`. That file's OTHER finding is
genuine (`.panel-resizer::before { z-index: 100 !important }`), so it is 1 real
plus 1 false rather than two of either.

### And the half of that report NOT taken — `:is()` still targets

hub proposed `:is(.foo, .h-resizer)` and `:where(.stx-shell-sidebar)` as
must-NOT-fire cases beside the `:not()` finding. **`:is()` and `:where()` are
MATCHING pseudo-classes**: `:is(.foo, .h-resizer) { color: red !important }`
applies `!important` to every `.h-resizer` on the page, the shell's included.
Blanking them for the membership question — the obvious way to reuse the
stripper 0.15.0 already had — would have converted a false positive into a
false NEGATIVE, silently.

So the module now carries two strippers, deliberately, against the usual rule
that a second implementation is a defect. They answer two different questions:

    membership   is this protected name a TARGET of this rule?
                 `:not(.panel-resizer)` excludes it  -> no
                 `:is(.foo, .h-resizer)` matches it  -> YES
    leftmost     does this selector list BEGIN with a bare `footer`?
                 every internal comma is noise, `:is()` included

Only the second wants every comma gone. One stripper cannot serve both.

### Added to `not_checked` — the residual this trade leaves

`:is(header, footer) { …!important }` DOES reach the shell's footer and is not
reported. The leftmost test drops every comma inside `:is()`, because keeping
them would fire on the far commoner `:is(header, footer) .x { … }`, where the
footer is an ANCESTOR and the subject is `.x`. Separating the two means knowing
which compound is the subject — the parser again, same card. Asserted as a
known zero beside the shape it pays for, so the trade is visible rather than
looking like an oversight.

### On the number

hub's 29 is a FINDING count and is not reported here as a defect count: they
opened a sample (3 verified real, 1 verified false, 25 unopened) and will
re-run against this release before saying more. `.panel-resizer` inside
`div[class*="…"]:not(…)` looks like a `writer_app` idiom rather than a one-off,
so the total may move materially.

The denominator did not move: 428 files under `css_files()`'s skip-set walk and
428 under 0.14.4's `.git`-only walk. Expected — hub's app dirs carry no
`node_modules` — and reported anyway, because "no movement" is only evidence
when it was going to be reported either way.

## [0.15.0] - 2026-09-05

Minor. One canonical workspace-CSS rule, measured against the shell instead of
argued from a list. **Unarmed** — `validate()` does not call it.

### Added — `validate_css_canonical()`, tiers 1 and 2 of three

Three implementations of one spec lived across two repositories and disagreed
in both directions on the same input:

```
#main-content { color: red }     passed the CLI rule, failed AppValidator
footer { display: none }         the reverse
```

scitex-hub measured the shell on 2026-09-04 — 30 agents, HEAD pinned, a control
in every loop, `defined_at` per row — and the table did not correct my list, it
**invalidated my instrument**. The rule is ownership **by node**, not by name:

- a node the shell renders, sizes or queries → no-touch
- the container the app renders INTO → no `!important`
- shared design tokens → read with `var()`, never redefine at `:root`
- a **shared component** class (apps render their own resizers, toggle buttons,
  sidebar elements) → free on the app's own nodes, no-`!important` because
  `!important` also reaches the shell's instances

That last line is why "does this stylesheet MENTION the name" is answerable and
is the wrong question. `.stx-shell-*` occurs 842 times across 114 files;
scitex-hub's own apps carry 42 legitimate selector lines on
`stx-shell-sidebar__*`. A mention-ban fails all 42 — correct code.

Tier 1 is therefore restricted to names an app can never legitimately own —
ids (singular by definition) and the shell's own root classes — where "mentions
it" and "selects the shell's node" coincide. Everything an app may own an
INSTANCE of is tier 2, where only the abusive operations error. The tiering is
not a severity ranking; it is the line between where the substring proxy holds
and where it does not.

New public names, all from `scitex_app.appmaker._validate`:

```python
validate_css_canonical(app_dir) -> CssScanReport
css_files(app_dir) -> list[Path]          # the denominator walk
CssScanReport(findings, files_scanned, checked, not_checked)
SHELL_INSTANCE_NAMES, SHELL_INSTANCE_PREFIXES, APP_CONTAINERS,
SHARED_COMPONENT_CLASSES, SHELL_TOKEN_PREFIXES, BODY_STATE_CLASSES
```

`CssScanReport` carries its own denominator and its own blind spot, and a
validator rejects findings against zero files. `files_scanned == 0` reads
NOT SCANNED, never clean — the failure mode that cost two measurements in one
evening (0.14.1, 0.14.4).

### Added — `check_css_canonical=` on `validate()` / `validate_with_warnings()`

Defaults to **False**. The old `validate_css()` is what still runs. This flag
is the arming switch, and arming means REPLACING that call, not adding to it —
running both would report one CSS defect twice under two wordings. Whoever
arms it deletes the `validate_css()` call in the same change.

Arming waits on scitex-hub's sequence, accepted verbatim: *ship canonical
unarmed with the blind spot declared → hub re-measures their five findings
against the shipped rule, from a stated ref, with the denominator from
`css_files()` → then arm.*

### Not checked, and the report says so

**Tier 3** is the structural rule that an app's selectors be scoped under its
own root. A bare `[data-pane]{}` or `.panel-toggle-btn{}` reaches the shell's
frame **without mentioning any protected name**, so no name-based validator —
mine, hub's, or this one — can see it. It needs a parser. Card
`app-css-tier3-structural-scoping-needs-a-parser-20260905`.

Shipping without it was hub's call, and their condition was that the result
must SAY SO in the return value: a validator blind to a whole class is a check
that cannot fail for that class, and its green will be read as "this app's CSS
is properly scoped" by someone with no reason to doubt it.

The second residual: whether a bare `footer { … }` rule actually reaches the
shell's footer. Semantically that is the right question and it is **not
implementable by substring**, so the implementable part ships — `!important` on
an unscoped `footer` and `footer { display: none }` are errors — and the rest
is declared. `.myapp footer { … }`, `.status-footer`, `.site-footer` and
`--footer-height` are calibrated non-findings.

### Three corrections that came from measurement, not from reasoning

- `.panel-resizer` was **tier 1** in the draft. Apps render it 41 times across
  nine apps against the shell's 6, so a mention-ban would have failed correct
  code in nine applications. Moved to tier 2. The error was in hub's one-line
  09-04 *summary*, not in the measured table beside it — the compression is
  where the fact was lost, and the table won.
- The `footer` match fires on the **leftmost position only**. The first
  narrowing still reported `.myapp footer { … }` — an app scoping a footer
  inside its own subtree, exactly what the rule exists to permit. Found by
  running the rule against code that ought to pass, which is the only place a
  false positive is visible.
- **A comma inside `:is()` is not a selector list.** `:is(header, footer) .x`
  puts `footer` after a comma, so the leftmost test read an argument as a
  second selector and fired. `:not(footer)` is the sharpest form of this: the
  rule EXCLUDES a footer and the detector called that targeting one. Both
  footer checks now read the selector with parenthesised arguments blanked,
  and the `display:none` half moved inside the rule loop so the two share one
  definition instead of two that drift.

  scitex-hub found this against 0.14.4 in a real file
  (`body > :first-child:not(header):not(main):not(footer)`) — which the
  canonical already passed, because `(` is not a boundary character. **The
  hole was in the hypothetical they offered beside it**, `:is(header, footer)`.
  Their example was already handled and their generalisation was right anyway;
  only running both separated them.

### One thing this cannot check, added to `not_checked`

`body.myapp-page footer { display: none }` is not leftmost, so this rule passes
it — and unlike `.myapp footer` it DOES reach the shell's footer, which lives
inside `<body>`. The two selectors differ only in whether the scoping element
contains the shell's node: a DOM fact, not a string fact, which is tier 3
wearing another hat.

It must not simply be banned either. scitex-hub does this deliberately and
documents it shell-side, so a ban would fail their design rather than catch a
defect. What the shell permits is the shell's to state; the validator's job
here is to say it did not look.

## [0.14.4] - 2026-09-05

Patch. A scan root that sits inside a skipped directory returned zero instead
of refusing — and the recommended method put callers there.

### Fixed — the walk excluded files by ANCESTOR directory names

`scannable_files` and `validate_prefix_safety` matched `PREFIX_SKIP_DIRS`
against every component of a file's ABSOLUTE path. So a scan root under
`.worktrees/`, `node_modules/`, `.venv/` — any of the nine skip names — had all
of its files excluded by a directory the caller never chose, and returned zero
files and zero findings.

MY OWN ADVICE PUT A PEER THERE. I told scitex-hub to read the REF rather than a
working tree, and to do it with a detached worktree. Worktrees live under
`.worktrees/`, which is in the skip set precisely so a scan of a REPO ROOT does
not descend into sibling worktrees. Both pieces of guidance are individually
correct; together they produce a silent zero.

hub reported "22 app dirs, 1,116 files, 0 findings, control returned 1" and
retracted it: their tree holds **262** prefix findings. The scan had seen
nothing at all.

The fix is one change: the walk matches skip names RELATIVE to the scan root.
Directories inside the app are still skipped; ancestors the caller never chose
no longer count.

MY FIRST VERSION ALSO REFUSED such a root, as belt-and-braces, and that was
wrong. hub said what they would actually do with 0.14.4: their hooks DENY
tracked-file edits outside `<repo>/.worktrees/<name>/`, so scanning a worktree
is their NORMAL path, not an accident — the refusal fired on the mandated
workflow. Once the match is relative, that scan is simply correct and there is
nothing to guard. A guard that removes a capability is not a guard.

They also pre-empted the wrong repair: an `allow_skipped_ancestor=True` escape
hatch would re-open the silent zero. Right — and unnecessary, because there is
now nothing to escape from.

Calibrated:

    1 finding / 1 file   a plain root
    1 finding / 1 file   a root with node_modules INSIDE it (dependency skipped)
    1 file               a root under .worktrees   (was 0 — the silent zero)
    1 file               an exported tree, wherever it sits

### Retraction — the hub evidence cited for arming in 0.14.0

That release cited "scitex-hub 29 app dirs, 1,471 files, 0 findings, control
returned exactly 1" as part of the case for arming `check_prefix_safety`. **That
line should not have been written.** It is annotated as retracted in the 0.14.0
entry above rather than deleted, since it is what the decision was actually made
on.

ARMING STANDS, ON DIFFERENT EVIDENCE. hub measured the shape that actually
matters: `validate()` is called only on USER-SUBMITTED app projects — `_publish`,
`_launcher`, `_scaffold`, `api_dev` — never on hub's own Django apps, which are
not appmaker-shaped. So the gate is unaffected by their 262. The correct
question was never "is hub's tree clean" but "what population does the gate
read", and only the second was ever load-bearing.

### And the denominator did not save it, for a reason worth naming

hub reported 1,116 files beside 0 findings — the healthiest-looking possible
result. The two numbers came from DIFFERENT INSTRUMENTS: the denominator from
their own re-implementation of the walk (which only skips names below its root,
so it never saw the ancestor), the numerator from ours (which did).
`scannable_files` would have returned 0 and the report would have read NOT
SCANNED. A denominator from a second implementation is not a denominator.


## [0.14.3] - 2026-09-05

Patch. Three more rules stop reading comments as code — and one of them stops
letting a comment SATISFY a requirement.

### Fixed — a comment could satisfy a frame requirement (FALSE NEGATIVE)

`validate_templates` checks `"global_base.html" not in content` and
`"block content" not in content`. Those are PRESENCE tests, so a page that
extends nothing and defines no content block PASSED as long as the strings
appeared in an HTML comment. Measured on the shipped 0.14.2 with controls:
zero errors on a page meeting neither requirement.

Every other instance of this blindness found the same day was a false
POSITIVE — documentation read as code, noisy but visible. This one is silent,
and `validate_templates` runs by DEFAULT rather than behind a `check_*` flag,
so it is live in a publication gate.

### Fixed — commented-out violations reported by three more rules

    validate_js        live eval()      1, commented-out ALSO 1
    validate_css       live rule        1, commented-out ALSO 1
    validate_security  live os.system   1, commented-out ALSO 1

The CSS case is the shape scitex-ui reported from their own incident: a path
quoted inside a comment read as a live reference, failing every PR in a peer
repository.

### Added — `_validate/_comments.py`

`strip_js_comments` (2026-09-03) and `strip_html_comments` (0.14.2) moved here
and are joined by `strip_css_comments`; `_prefix` re-exports all three, since
they were public there first. CSS has no line comment — `//` appears inside
every `url(https://...)` — and a `/*` inside a quoted value does not open one.

WHY A MODULE RATHER THAN THREE MORE IMPORTS. `strip_js_comments` had carried
the whole argument in its docstring for two days. What was missing was not the
rule but its SCOPE: nothing declared where it applied, so each new rule had to
rediscover it. scitex-ui named the shape after hitting it themselves the same
day. A module makes the scope explicit — this is where a rule that reads source
text comes to have its comments removed.

### Calibration — twelve cases, both directions per rule

A stripper that hides too much converts each false positive into a false
negative, where the finding disappears and nothing says why. So every fix is
paired with the case that must STILL report:

    js    live eval 1 / commented 0 / live AFTER a comment 1
    css   live 1 / commented 0 / live after comment 1 / "/*" in a string 1
    tpl   conformant 0 / missing both 2 / ONLY IN A COMMENT 2 (was 0)
          forbidden live 1 / forbidden commented 0
    py    live os.system 1 / commented 0 / live after comment 1
          "#" in a string 1 / clean 0 / docstring 1 (deliberate)

Suite 726 passed, 2 skipped.

### The remaining rules are accounted for BY MECHANISM, not by an unread zero

Rather than leaving six unprobed, each was resolved by asking what it reads:

    validate_manifest / _privileges / _dependencies   json.loads — JSON has
                                                      no comments to misread
    validate_structure / _bundle_size                 read no text at all
    validate_security                                 regex-scans .py  <- had it

That last one is why this matters: a SECURITY rule was reporting the file that
documents the call it removed. `strip_python_comments` tracks quotes rather
than matching a pattern, because `S = "#"` is a value.

DOCSTRINGS ARE LEFT REPORTING, deliberately. A docstring is a string the module
genuinely contains, not a comment the parser discards; deciding which strings
are prose is a separate judgement needing its own calibration, and guessing is
how the first of these defects got here. Same treatment as a `<pre>` block.

The first probe of css and templates returned 0/0 and was nearly read as clean
— the LIVE case had also returned 0, so the zero said nothing. Every result
above rests on a case that provably reports.


## [0.14.2] - 2026-09-05

Patch. The armed prefix rule no longer reports documentation as a violation.

### Fixed — a URL inside an HTML comment was an ERROR

`strip_js_comments` has stripped `//` and `/* */` since 2026-09-03, with the
reason in its own docstring: a detector keyed on a substring INVERTS ON
DOCUMENTATION — the file that best explains why it removed a bad call looks
identical to the file that still has it. `.html` never got the same treatment.

Nobody noticed while the rule was a RECORD. It became visible the week the rule
became a GATE, because a false positive stopped being noise in a report and
started refusing to publish an app over text no browser ever requests.

`<script>` bodies are excluded from the HTML pass and left to the JS stripper
that runs over them afterwards: `-->` occurs inside JavaScript strings, and
treating one as a comment terminator would blank everything before it and make
a real finding disappear — trading a false positive for a false negative, which
is the trade `strip_js_comments` explicitly refuses. Comments are blanked to
same-length spaces, never deleted, so reported line numbers still point at the
real source.

A `<pre>` code sample still reports. Distinguishing a teaching block from live
markup needs its own calibration and is not guessed at here.

### Fixed — `{% url %}` was reported as a violation

A Django or Jinja tag is resolved by the server's URLconf, which under a mount
already includes the mount prefix: it is the prescribed idiom. Measured on
scitex-hub's tree, 11 of 339 findings were `{% url %}`, every one correct code.

This is NOT the same judgement as `${...}` interpolation, which is still
reported: there the LEADING SLASH is decidable whatever the expression yields.
For a template tag nothing before the path is ours to read, and an unknown must
not be collapsed into a violation.

### Measured effect on the consumer trees, at their refs

    scitex-hub       1975 files    339 -> 328    (-11, exactly the template tags)
    figrecipe         116 files     19 ->  19
    scitex-writer     144 files      5 ->   5
    scitex-cards       94 files      4 ->   4
    scitex-scholar     74 files      0 ->   0
    scitex-storage     26 files      0 ->   0

Nothing else moved. Both fixes were also calibrated in the direction that
matters more — a live call after a comment, a live call on the same line as
one, a `-->` inside a script string, and an interpolated root-absolute URL all
still report, with correct line numbers.


## [0.14.1] - 2026-09-05

Patch. `validate_prefix_safety` no longer answers "clean" about a directory
that is not there, and the walk behind a files-scanned count is now public.

### Fixed — a missing path returned zero findings instead of refusing

`validate_prefix_safety("/path/that/does/not/exist")` returned `[]`. `rglob`
over a missing directory yields nothing, so a typo, a removed worktree, or a
relative path resolved from the wrong directory read as a passing result. It
now raises `FileNotFoundError` (and `NotADirectoryError` for a file).

THIS IS NOT HYPOTHETICAL — IT IS HOW 0.14.0 WAS ARMED. The scan behind that
decision pointed at `<repo>/.worktrees/prefix-check` in two peer repositories.
Neither path existed. Both reported zero findings and were announced as clean;
measured afterwards on the same refs with the published wheel, figrecipe has 19
findings and scitex-writer 5. **The positive control passed throughout**,
because a control runs on a temp tree that does exist. The instrument was
working and aimed at nothing.

`validate()` and `validate_with_warnings()` are unchanged for a missing app
directory: they still report it as findings rather than raising, because a
publication gate reads that list and must not start receiving an exception.
The refusal is for the direct caller running the rule against their own tree.

### Added — `scannable_files`, `PREFIX_SCAN_SUFFIXES`, `PREFIX_SKIP_DIRS`

Public on `scitex_app.appmaker`. We ask consumers to report files-scanned
beside their findings — "0 findings" is not a claim, "0 findings across N
files" is, and N == 0 means NOT SCANNED rather than CLEAN. scitex-hub found
that everything needed to produce that number was behind an underscore and
imported from `_validate` to comply. A request we make of consumers cannot
depend on a path we tell them not to touch; that is the same defect as
`validate_prefix_safety` in 0.14.0, found the same day by the same peer.

`scannable_files` is exported alongside the constants so a caller uses THIS
walk rather than re-deriving the skip rules — a second implementation is a
second thing to drift.


## [0.14.0] - 2026-09-05

Minor, and BEHAVIOUR-CHANGING for every existing caller of `validate()`:
the mount-prefix safety rule, shipped unarmed in 0.9.0, is now ARMED.

### Changed — `check_prefix_safety` now defaults to True

`validate()` and `validate_with_warnings()` run the prefix rule unless a
caller passes `check_prefix_safety=False`. Its findings are ERRORS, not
warnings, so any caller that raises on a non-empty result now refuses an app
it previously accepted.

WHAT THAT MEANS IN PRACTICE. The rule reports request URLs that do not
resolve under an app mount — `fetch("/api/x")`, which ignores the mount and
404s everywhere, and `fetch("api/x")`, which resolves against the DOCUMENT
url so it works at `/app/` and 404s at `/app`. Those apps were already
broken under a mount; what changes today is that they are caught instead of
shipped.

CONSEQUENCE WORTH STATING PLAINLY, because the first symptom is otherwise a
user hitting an error nobody warned them about: scitex-hub's PUBLICATION
path calls `validate()` with no keywords. From this release, submitting an
app containing a root-absolute request URL fails to publish. hub identified
this themselves and asked that it be announced rather than merely shipped.

In this package the new default reaches `appmaker._publish`,
`appmaker._dev_install`, the `scitex-app app validate` CLI, the
`app_validate` MCP tool, and the public `scitex_app.validate()`.

ARMED ON MEASUREMENT, NOT ON ELAPSED TIME. Every consumer repo was scanned
on its current ref, each against a positive control, so a zero was
distinguishable from a scan that never ran:

    scitex-writer / figrecipe / scholar   clean
    scitex-hub    29 app dirs, 1471 files, 0 findings; control returned 1

**^ BOTH LINES ARE RETRACTED. See 0.14.1 and 0.14.4.** The writer/figrecipe
zeros scanned directories that did not exist (0.14.1); hub's zero scanned a
detached worktree, whose every file this rule excluded by an ancestor directory
name (0.14.4). Their real numbers are 5, 19 and 262. Left in place rather than
edited out: this is what the arming decision was actually made on, and deleting
it would hide that.

hub had asked to be consulted BEFORE arming and gave the go-ahead
2026-09-05T20:16Z, ahead of the 09-07 they had committed to.

### Added — `validate_prefix_safety` is importable from `scitex_app.appmaker`

It was only reachable at `scitex_app.appmaker._validate`, a private path.
scitex-hub scanned their fleet for us, imported it from the obvious public
home, hit an ImportError, and was one step from reporting the symbol as
missing. We ask other packages to run this rule against their own code, so
it cannot live only on a path they are not supposed to touch.

### Note for anyone who needs the old behaviour

Pass `check_prefix_safety=False` explicitly. That is a deliberate opt-out
with a name, which is what it should have been all along — but if you find
yourself adding it to a publication gate, the app is the thing to fix.


## [0.13.0] - 2026-09-05

Minor: `scitex_app.authz` gains a fifth verdict kind, an optional upgrade
route, and the three-valued resolve state that `can()` will be built on. All
additive — nothing existing changes shape.

WHY THE FIFTH KIND EXISTS, since four were declared complete in 0.12.0.
`can()` is committed SYNCHRONOUS AND TOTAL: it answers from state resolved
before it is called. That splits "unresolved" into two situations a
"value, or None" field renders identical — the caller who never resolved
(a contract violation, which must RAISE) and resolution that was attempted
and FAILED (a real operating state, which must still return something the
screen can draw). The second case had no verdict to return. It does now.

COORDINATION. These strings are declared twice, in two languages, in two
repositories — scitex-ui renders what this package builds, and their switch
is exhaustive, so a new kind is a compile error on their side by design. The
fifth kind was added WITH them and ordered TS-FIRST: scitex-ui shipped
`UNRESOLVED` in 0.20.2 first, because this repo's cross-package check reads
the INSTALLED scitex-ui and a Python-first order goes red in a way this side
cannot clear.

### Added

- **`UNRESOLVED` / `unresolved()` — "we do not know", and never a denial.**
  Carries NO payload. Not the failure REASON either: timeout,
  misconfiguration and network do not change what the UI renders, and naming
  one discloses that the service behind a gate is currently down to a reader
  who is not authenticated to it. A server-side log is where that belongs.
  Do NOT use it for a caller who skipped resolution — that is a bug, and
  rendering it as a legitimate "not yet known" UI hides the bug forever.

- **`ResolveState` — NOT_ATTEMPTED / FAILED / RESOLVED.** The prerequisite
  the split above rests on. An `Enum`, deliberately NOT a `str` subclass,
  unlike the verdict kinds in the same module: those are strings because they
  are serialised and read by another language; this one must never survive a
  `json.dumps` or a stray `to_dict()`, for the disclosure reason above. A
  test asserts it is not a `str`.

  Deliberately NOT built: a container pairing the state with the resolved
  VALUE. Nothing resolves anything yet — no resolver, no hub URL
  configuration, no token storage — so its fields would be invented rather
  than observed.

- **`upgrade_url` on `denied-because-not-entitled`, optional.** Confirmed
  with scitex-hub: the destination is their pricing page. `billing_checkout`
  is a POST target and can never be somewhere a denied user is sent. The
  value is supplied BY THE HUB rather than built here, because the hub URL is
  configurable and a self-hosted deployment's answer differs.

  ITS ABSENCE IS MEANINGFUL and is pinned: absent means this hub has no
  upgrade surface configured, so render inert. It NEVER means "not yet
  resolved" — that is the `unresolved` kind, and conflating them would put
  the same three-value collapse back one layer down.

### Unchanged, and worth stating

The validator needed NO new code for the fifth kind. Every payload arm is
written as an EXCLUSION (`kind not in _PERMITS_...` → refuse), so a kind
absent from those tuples lands in the refusing branch by default: the safe
default for a new kind is "carries nothing". Measured before the kind
existed and again after, with a control — the same `upgrade_url` is still
ACCEPTED on `denied-because-not-entitled`, so the refusals mean something.

`can()` itself is still NOT in this release. What remains is hub URL
configuration, token storage, and the function.

## [0.12.1] - 2026-09-03

Patch: the mount-prefix scan was measuring the wrong population, and then
reporting things that are not request URLs. No API change.

WHO IS AFFECTED. The prefix rule is UNARMED — `validate()` skips it unless
`check_prefix_safety=True` — so nothing was failing a build on this. What it
degraded was the RECORD: a report where most rows are unactionable is one
nobody reads, which is how a check stops being read at all.

### Fixed

- **The scan read a project's own dependencies as its violations.**
  `PREFIX_SKIP_DIRS` excluded `node_modules` but had no Python equivalent, so a
  scan pointed at a project ROOT descended into the virtualenv. Measured across
  three real trees: 46, 46 and 48 findings, dominated by playwright's driver
  bundle (a *test* tool), matplotlib's `web_backend` templates, and an installed
  figrecipe — none of which ship under the scanned app's mount, so none can
  break under it. One tree read 46 while its own source was clean. The rule
  already embodied "installed dependencies are not the application"; it applied
  that to JavaScript only.

- **A linked worktree multiplied every finding.** A worktree is another checkout
  of the same repository, so each real finding was reported once more per
  checked-out branch, making the count a function of how many branches happen to
  exist locally.

- **A url-ish NAME was treated as evidence about its VALUE.**
  `const ATTR_SIGN_IN_URL = "data-stx-dim-sign-in-url"` was reported as an
  inferred-base URL. The name ends in `_URL` because it *names the attribute
  that holds* a url — the opposite of the value being one. The binding pattern
  now also requires the value to carry a path separator.

- **The bundler's `new URL(<spec>, import.meta.url)` was reported.** That idiom
  is resolved at build time into a hashed asset and issues no request. It was
  previously excluded by FILE (`vite.config`), which is the wrong
  discriminator — the signature is the second argument, and the idiom is just as
  valid in application source. Root-absolute specifiers are deliberately NOT
  exempt: `new URL("/x", base)` discards the base's path and resolves from the
  origin root, so it still breaks under a mount.

After the above, on the same three trees: 5, 0 and 0 — and the two non-zero
figures are corroborated by a second scan route that never touched `.venv/` or
`.worktrees/`.

### Added

- A cross-package check that the authorization verdict's four `kind` strings
  agree with scitex-ui's TypeScript copy, which is a second declaration of one
  decision in another language and repository. It runs where a rename would
  happen rather than where the breakage would appear.

- The CI step that actually runs the cross-package checks. They had never run in
  CI: the matrix job installs no scitex-ui so every cross-package arm skipped,
  and the job that does install it ran only the example's own tests. The
  `stx-mount` marker check added in 0.12.0 had therefore been reporting skips
  for a week while its docstring claimed otherwise.


## [0.12.0] - 2026-09-03

Minor: `scitex_app.authz` is a new public module. The rest is a validator
correctness fix and three checks that had no mechanical enforcement before.

The one entry with a consumer-visible effect is the prefix-scan fix: the scan
had been reporting commented-out code as a live finding since 0.9.0, so anyone
who ran `app validate` by hand could have been told to fix a call they had
already deleted.

### Added
- **`scitex_app.authz` — the authorization verdict, as a value rather than a
  boolean.** `can()` itself is not here yet; the type ships first because
  scitex-ui is building the display side against a shape agreed in a message
  thread, and a contract that lives only in a thread drifts. Four kinds
  (`allowed`, `denied`, `denied-because-not-signed-in`,
  `denied-because-not-entitled`), `kind` as the discriminant, payload travelling
  with the verdict so nobody reconstructs the reason, and a validator that
  enforces payload ABSENCE as well as presence — a plain denial that offered a
  sign-in URL would tell a user to do something that cannot help. Deliberately
  no `.allowed` boolean: it reads naturally, passes review, and silently treats
  "sign in first" as identical to "never".

### Fixed
- **The mount-prefix scan no longer reads commented-out code as code.** Shipping
  since 0.9.0: a file whose only match sat in a comment produced a finding
  telling the author to fix a call they had already removed. Comments are now
  blanked with string literals PRESERVED — not by a regex, because `//` opens
  every absolute URL and a naive strip would truncate `"https://…"` and lose a
  real finding, trading a false positive for the worse direction. Same-length
  blanks keep reported line numbers pointing at the real source. Measured on the
  three consumer trees before and after: scholar 0/0, writer 5/5, figrecipe 6/6
  — so no previously reported finding was a comment artefact, and none was lost.

### Internal
- **The `stx-mount` marker name is now checked across packages AND languages.**
  It is declared four times — `_django.py` (which renders it), `embed.py`'s
  no-Django fallback, `scitex_ui/mount.py`, and scitex-ui's `mount.ts` (which
  reads it in the browser) — and nothing enforced agreement; scitex_ui's own
  comment said "must match mount.ts" and admitted no mechanism. A rename on one
  side degrades either to a thrown error or, in the other ordering, to a page
  that renders perfectly and 404s its API only under a mount. The check reads
  the TypeScript constant out of scitex-ui's shipped source, so it needs no
  checkout, and SKIPS when scitex-ui is absent — scitex-app does not depend on
  it and must not.
- **`import scitex_app` is now asserted not to import Django or `scitex_ui`.**
  0.11.0 made `_standalone` — the module that runs Django servers — import
  eagerly at package root, and nothing checked that it stayed cheap. The
  existing import-smoke leg installs the extras, so Django is present there and
  it would pass whether or not the property held. The new test runs in a
  subprocess so the assertion is independent of what the runner has installed,
  and it is load-bearing for someone else: scitex-scholar made scitex-app a hard
  dependency and retired their "not installed" fallback, so an import-time
  regression here is now an outage there rather than a downgrade.

## [0.11.0] - 2026-09-03

Minor: `hosts_to_allow` becomes public API, and the app validator gains a warn
tier plus the three checks its own documentation had been promising. Released
now because figrecipe and scitex-scholar are each holding a verbatim copy of
`hosts_to_allow` and cannot replace it with an import until the public name
ships.

### Added
- **`scitex_app.hosts_to_allow(host)` is now public** — what a `--host` bind
  implies for Django's `ALLOWED_HOSTS`. It became public because it was about to
  be depended on privately: scitex-scholar and figrecipe each carried a verbatim
  copy, and on 0.10.1 both were replacing it with
  `from scitex_app._standalone import _hosts_to_allow`. Three repositories
  committing to an underscore path is a promise nobody made, and deciding the
  name before the dependency exists is cheaper than deprecating an accidental
  one after. `_hosts_to_allow` survives as a migration alias so the in-flight
  PRs that were told to use it keep working; it is removed once both have
  swapped (card `app-retire-private-hosts-to-allow-alias`).
- **The three checks the docs promised and nothing ran.** JS dangerous-pattern
  scanning, a bundle-size cap and manifest privilege validation existed in
  `scitex_app.validator.AppValidator`, worked, were covered by tests, were
  described to app developers by the shipped skill doc — and were called by
  nothing; the CLI read no `.js` file at all. Ported into the live path as
  `validate_js` / `validate_bundle_size` / `validate_privileges`, each behind a
  `check_*` keyword defaulting to `False`, so no caller's results change today.
  The JS pattern list was narrowed from nine to five on measurement: the four
  dropped were the Python forbidden list copy-pasted into a JS scanner, and
  `exec\s*\(` produced the only finding either peer repo had — `re.exec(line)`
  in a `while` loop, i.e. correct JavaScript.

### Changed
- **Advisory validator findings no longer fail a build.** `appmaker.validate()`
  returned one flat list and the CLI does `raise SystemExit(1)` on any entry, so
  "should" and "must" were indistinguishable to the only thing acting on them.
  Two findings were worded as advice and enforced as failures — the
  `name` must end in `_app`/`-app` convention, and the deprecated `--color-*`
  CSS variables — and the first was UNCLEARABLE: an app whose correct name would
  COLLIDE with an existing registry entry could satisfy the rule only by
  creating the collision. New `appmaker.validate_with_warnings(app_dir)` returns
  `(errors, warnings)`; `validate()` keeps its signature and now returns errors
  only. `scitex-app app validate` prints advisory notices in yellow and exits
  non-zero only on errors. The remaining error-tier findings are unchanged.

### Fixed
- **Two false-positive classes in the mount-prefix scan**, both found by running
  it against real app packages rather than fixtures. `xhr.open("GET", url)` was
  reported as `inferred-base request URL 'GET'` — XHR's first argument is the
  METHOD, so the remediation told the author to join a verb to the mount; XHR
  URLs are now read from the second argument. And bundler configs were scanned
  despite the rule's own docstring excluding them, reporting
  `new URL(".", import.meta.url)` in `vite.config.ts` — Node's `__dirname`
  idiom, evaluated at build time, reaching no browser. Measured on
  scitex-writer: 8 findings before, 5 after, with the 3 removed being exactly
  these; scitex-scholar (known-clean) stays at 0 and figrecipe's published
  0.34.6 stays at 6, so no true positive was lost.

### Internal
- `appmaker/_validate.py` (537 lines) split into a package of one module per
  concern — app layout, security, manifest, frame rules, dependencies, prefix
  safety — with the full re-export surface preserved on `_validate`, so
  `from scitex_app.appmaker._validate import <anything>` is unaffected. Tests
  moved to the mirror directory the project-structure audit requires; the test
  NAME set is identical before and after.

## [0.10.1] - 2026-09-02

Patch: a server bound to `0.0.0.0` now answers on the addresses it is
actually reachable at. Released immediately — scitex-scholar 1.9.0 and
figrecipe 0.34.6 are both hitting the 400 in the field, and both carry a
local copy of the fix that they replace with an import from this wheel.

### Fixed
- **`_allowed_hosts` now honours a `0.0.0.0` bind.** It appended the bound
  host *string*, and `"0.0.0.0"` was already in the base list, so `--host
  0.0.0.0` contributed nothing and a request carrying the real interface
  address in its Host header was refused with 400 `DisallowedHost` (measured
  2026-09-02 by scitex-scholar on 1.9.0 and by figrecipe on 0.34.6; this
  function's own docstring had recorded the figrecipe symptom on 08-23). The
  bind now contributes what it implies: loopback nothing, a concrete address
  itself, `0.0.0.0` the hostname plus every interface's IPv4 read from the
  interfaces (`SIOCGIFADDR`) — not from name resolution, which inside a
  container returns addresses that are not the LAN interface. Never widened
  to `"*"`. The derivation is scitex-scholar's `_hosts_to_allow` (PR #137)
  verbatim, so scholar and figrecipe can replace their copies with an import.

## [0.10.0] - 2026-08-23

Minor: `run_standalone()` gains language activation. Released now rather than
batched because scitex-hub is building against the i18n contract today and
cannot, while it exists only on `develop`.

### Added — standalone can actually render a non-English language

Catalog *discovery* was already free: Django auto-discovers
`<app>/locale/<lang>/LC_MESSAGES/django.mo` for anything in `INSTALLED_APPS`,
with no `LOCALE_PATHS` and no cooperation from the host. **Activation** was
missing. Nothing ever called `activate()` and `LANGUAGE_CODE` sat at Django's
`en-us` default, so a standalone app could ship a complete, working Japanese
catalog, load it, and render English forever.

`_configure_django()` now sets:

- `LocaleMiddleware`, before `CommonMiddleware` per Django's ordering requirement
- `USE_I18N` explicitly, rather than inheriting a default that could move
- `LANGUAGE_CODE` from `SCITEX_LANGUAGE_CODE` (default `en-us`)
- `LANGUAGES` from `SCITEX_LANGUAGES` (comma-separated), **omitted entirely when
  unset** — passing `[]` would assert "this app supports no languages", the
  opposite of "the app did not say"

### Added — a declared language with no compiled catalog now says so

A language in `LANGUAGES` with no `.mo` does not error: gettext falls back to the
source string, so it reads as *"nobody has translated it yet"* rather than *"the
mechanism is broken"*. Startup now names the language, states that its strings
will render as source, and names the likely cause.

It **prints rather than raises** — a missing translation must not stop a server
starting, and refusing to serve English because Japanese is absent would be worse
than the bug. It checks for the **compiled** `.mo` only, because a `.po` without
its `.mo` is exactly the shape that ships green.

**`msgfmt` is absent** from this container, from scitex-hub's container, and from
`scitex-hub-prod-django:latest` — the image serving production. Three
environments, three absences. `django-admin compilemessages` shells out to it, so
compile at build time via a pure-Python path and ship the `.mo` inside the
distribution.

### Fixed — `serve --host <addr>` bound correctly and then 400'd every caller

`ALLOWED_HOSTS` was a hardcoded loopback-only literal while `--host` accepted any
address, so the server printed `serving at http://<addr>:<port>` and rejected
every request. The banner asserted the opposite of the truth.

The bound host is now always allowed — binding to an address is the statement
that you intend to be reached on it — plus `SCITEX_ALLOWED_HOSTS`
(comma-separated) for the proxy/tunnel case.

Deliberately **not** widened to `["*"]` under `DEBUG`. These apps ship no
authentication and `DJANGO_DEBUG` defaults to `"true"`, so a wildcard would make
every reachable address an unauthenticated reader by default.

**This does not fix embedded leaf apps** that set `DJANGO_SETTINGS_MODULE` and
call `django.setup()` before `run_standalone()` — `_configure_django()` returns
early when settings are already configured, so their own `settings.py` supplies
`ALLOWED_HOSTS` and this change never executes for them. Verified by
scitex-scholar against their running process.

### Documentation

- `35_i18n.md` — the locale convention for mounted apps, leading with the silent
  fallback rather than the layout.
- `05_standalone.md` — states that `run_standalone()`'s settings apply **only if
  Django is not already configured**, with the one-line check to confirm which
  settings you actually got. It previously caveated only re-entrancy.
- `07_backend-validation.md` — the CLI runs `appmaker.validate`, not
  `AppValidator`; neither is a superset of the other, and the doc now carries the
  measured coverage table. It also told developers to add a `version` key that
  both implementations reject.

## [0.9.1] - 2026-08-20

### Fixed — the prefix check flagged the fix it prescribes

0.9.0's `validate_prefix_safety` reported this as `inferred-base`:

```js
`${STX_MOUNT}/api/search?${params}`
```

which is exactly what the finding's own remediation text tells an app to write.
The rule condemned its own prescribed fix. Found by scitex-scholar within
minutes of 0.9.0 publishing, by running the check against a tree they knew to
be **correct** — the only configuration in which a false positive is
distinguishable from a true one.

The discriminator was syntax, not semantics. Same variable, same correct code:

| form | 0.9.0 |
| --- | --- |
| `fetch(STX_MOUNT + "/api/x")` | passed (concatenation) |
| `` `${STX_MOUNT}/api/x` `` | **flagged** (template literal) |

Interpolation is precisely when a URL stops being a bare literal, so a
correctly-fixed site that needs a query string is *forced* into the flagged
form.

**Root cause: a three-valued signal collapsed into two.** A literal opening with
`${…}` is *variable-prefixed* — neither root-absolute nor document-relative,
because what precedes the path is a value the scanner cannot see. 0.9.0 folded
that unknown into "inferred-base".

The fix is deliberately narrow: a leading `${STX_MOUNT}` (see
`MOUNT_IDENTIFIERS`) is satisfied; a leading `${anythingElse}` is *unknown* and
is not reported, recorded as an explicit exclusion. Deciding whether an
arbitrary variable holds the mount requires its value, and inferring it is what
produced the bug.

**Not blunted.** The known-answer control was re-run: scholar's shipped wheel
still reports exactly its three root-absolute sites. Two further test arms exist
solely to prevent this becoming a blanket amnesty — a genuinely root-absolute
and a genuinely relative URL must still be flagged.

No behaviour change for anyone who did not opt in: the check remains **unarmed**
(`validate()` skips it unless `check_prefix_safety=True`), so 0.9.0 could not
have failed a build on this.

## [0.9.0] - 2026-08-20

### Added — mount-prefix safety check, SHIPPED UNARMED

`scitex_app.appmaker.validate_prefix_safety()` reports request URLs that do not
resolve under an app mount. **It is a record, not a gate.** `validate()` skips it
unless `check_prefix_safety=True`, so nothing fails on it — flipping that default
is the arming action, and it has not been taken. Arming today would fail apps
whose fixes are not yet released.

Two classes are reported, and the second is why the check exists:

| class | example | behaviour |
| --- | --- | --- |
| root-absolute | `fetch("/api/x")` | ignores the mount; 404s everywhere, so it gets found |
| inferred-base | `fetch("api/x")` | resolves against the *document* URL — works at `/app/`, 404s at `/app` |

The second passes a smoke test and breaks on a redirect. A root-absolute-only
rule would miss it. Platform routes (`/platform/api/`, `/apps/store/api/`) are
exempt — hub owns them, they live at the server root, and prefixing them breaks
them.

Known limits, stated because an enumeration's exclusions are invisible in its
output: no dataflow, so a URL built across statements or bound to a name that
does not look url-ish is missed; static/asset base paths (a bundler `base`
setting) are out of scope as a build-config concern with different correct
answers.

### Fixed — template and CSS validation were unreachable for every `_`-prefixed app

`validate()` skipped `validate_templates` and `validate_css` whenever
`_is_embedded_package()` was true, and that returns true from the **directory
name alone** (`root.name.startswith("_")`), before any manifest is read. So every
app living in `_django/` had both checks unconditionally off — listed, invoked,
and structurally unreachable.

The comment gave it away: *"embedded packages use compiled React builds"* is a
claim about the FRONTEND, while the condition tested the PACKAGING. An embedded
app declaring `frontend_type: "vanilla"`, with hand-written Django templates and
CSS and no React build anywhere, was skipped regardless.

The skip is now keyed on the property the comment always claimed:

```python
if not is_embedded or (frontend_type and frontend_type != "react"):
```

**Strictly additive — no app loses a check it had:**

| case | before | after |
| --- | --- | --- |
| non-embedded, any type | runs | runs |
| embedded + `"react"` | skipped | skipped |
| embedded + declared other | **skipped** | **runs** |
| embedded + undeclared | skipped | skipped |

`frontend_type` is deliberately not tested as `!= "react"` alone: the field is
inconsistent in the wild (`"html"`, `"django"`, `"vanilla"` all appear, and the
default differs by module), so only `"react"` reliably means compiled. An
undeclared app is left alone rather than guessed at, since guessing would invent
findings on compiled output.

**Upgrade note.** If your app is an embedded package that declares a non-React
`frontend_type`, template and CSS validation will run against it for the first
time and may report findings you have not seen before. That is the fix working.

## [0.8.1] - 2026-08-18

No code change. `scitex_app` behaves identically to 0.8.0.

### Documented — 0.8.0's root prefix is `""`, which is FALSY

**If you are migrating from 0.7.x, delete any `|default`, `||` or `or` around
the mount prefix before you do anything else.** Under 0.7.x those were correct
and harmless: `"/"` was the right root, so writing a default was sensible.
0.8.0 made the root the empty string, and every "use this when empty" idiom
now silently restores the withdrawn value:

```django
{{ stx_mount|default:'/' }}    ← renders "/" at root
```

which makes the documented join produce `//api/x` — protocol-relative, which
the browser resolves to a **different host**. That is the exact failure 0.8.0
was cut to prevent, reintroduced by a line that was correct when it was
written. Django `|default:`, Jinja `|default()`, JS `||` and Python `or` all
fire on `""`; use `??` or an explicit `is None` if you need a fallback.

**Migrating is ONE coordinated change; the half-fix is worse than not
starting.** Two things inverted together — the root value became falsy, and the
slash moved from the base to the endpoint. Drop the default but keep
`base + "api/x"` and you get `<prefix>api/x`; flip the join but keep the default
and you get `//api/x`; fix the template but not the bundle and a `||` restores
the old value anyway. Grep template default, base read and every fetch site
before changing one. *(scitex-writer found this — all three faces are present
in their app at once.)*

Found by **scitex-scholar** while migrating, before it shipped. Their tell is
worth repeating: a guard test that should have flipped after the migration kept
passing. A test that survives a breaking change unchanged is evidence about the
test.

This is the server-template twin of the `?? "/"` removed from the client half
in 0.8.0 — that instance was fixed and documented for JS, and the same warning
was not carried to the side where the idiom was *more* likely, because the old
convention rewarded writing it.

### Changed — the contract page is split

`33_mount-prefix.md` (162 lines) is now the contract; `34_mount-prefix-rationale.md`
holds the reasoning. The decisive argument — the failure-mode table showing
`//api/x` resolving off-origin — stays **inline in the contract**, because it is
what must not be undone; only secondary material moved, with the contract
pointing at it.

Both ship in the wheel, which is why a documentation-only change gets a
release: the page a consumer reads is the one in the artifact they installed,
and the misleading version was the one on PyPI.

## [0.8.0] - 2026-08-18

### BREAKING — `stx-mount` carries no trailing slash

Root is now `""` (was `"/"`); embedded is `"/apps/u/x"` (was `"/apps/u/x/"`).
**The slash moved to the endpoint**: write `base + "/api/x"`, not
`base + "api/x"`. 0.7.0–0.7.1's convention is withdrawn two days after it
shipped.

**Why, and it is not a preference.** scitex-ui ships its own `mount_prefix`
with the opposite convention on the *same* meta tag name, in the same venv.
Two SDKs, one tag, incompatible semantics — that had to collapse to one, and
both conventions produce **identical correct output**, so testing correct
usage cannot choose between them. Running each one's *likeliest mistake*
through a real URL resolver can:

| convention | likely mistake | result |
|---|---|---|
| 0.7.x `"/"` + `"/api/x"` | endpoint written with a leading slash | `//api/x` → **`https://api/x` — a different host** |
| 0.8.0 `""` + `"api/x"` | endpoint missing its slash | `https://site/api/x` (root, accidentally fine) |
| 0.8.0 `"/apps/u/f"` + `"api/x"` | same | `/apps/u/fapi/x` — 404, right host |

`//api/x` is protocol-relative: the browser sends the request, **and whatever
it carries, off-origin**. The withdrawn convention's most natural error leaves
the site; this one's 404s on the right host. scitex-hub confirmed this was
their surface too, since hub is what embeds apps.

### BREAKING — the reader throws instead of defaulting to root

`?? "/"` is gone from the contract. A default is indistinguishable from a
correct read, which is exactly how scitex-scholar's prefix fix nearly shipped
as a silent no-op: nothing emitted a marker, the fallback returned root, and
the diff looked complete.

### Fixed — the 0.7.1 derivation was wrong for any non-root view

0.7.1 handed template-rendered apps a copyable one-liner that assumed the view
sits at the app root. Measured: correct at the root, **wrong in 3 of 5 cases,
every wrong one a non-root view, and wrong silently**.

`request.path` is the whole path — the mount prefix *plus* the route the view
occupies — so only the view can subtract it, because only the view knows it.
New `mount_prefix(request, view_path=...)` does, and raises
`MountPrefixMismatch` rather than returning a best guess. `scitex_editor_page`
takes `view_path` too; its default `""` remains correct for `scitex_urlpatterns`,
which registers it at the mount root.

### Migrating

```js
// before (0.7.x)
const base = document.querySelector('meta[name="stx-mount"]')?.content ?? "/";
fetch(base + "api/x");

// after (0.8.0)
const el = document.querySelector('meta[name="stx-mount"]');
if (!el) throw new Error("stx-mount marker missing");
fetch(el.content + "/api/x");
```

Template apps: replace any hand-copied derivation with
`from scitex_app.embed import mount_prefix`, passing your view's own route.

### Credit

The implementation properties are **scitex-ui's** — throw rather than guess,
subtract `view_path` rather than assume root. They argued *against their own
scope*, separating "which code survives" from "which package owns the
contract", and that argument is why the contract stayed here while their design
won. Their `mount.py` also reasoned out the `SCRIPT_NAME` double-prefix trap
and the `resolver_match.route` dead end first. The compare-failure-modes rule
is **scitex-scholar's** generalisation.

## [0.7.1] - 2026-08-18

- **docs(mount-prefix): the SDK does not inject into templates you render
  yourself.** 0.7.0's contract page said "if you serve your shell through
  `scitex_editor_page`, the marker is present" and never stated the other case.

  scitex-scholar nearly shipped through the gap. Their view does
  `render_to_string(...)` — a Django template, not a built SPA shell — so
  nothing injected the marker. Their four client-side changes would have read no
  marker, hit the `?? "/"` fallback, and reproduced the previous behaviour
  exactly, while looking correct in the diff. The page still renders; only the
  API calls 404, and only under a prefix. It was five sites, not four, and the
  fifth would have made the other four useless.

  The page now carries a second "does not" beside the asset-rewriting one, with
  the two-line derivation to copy so a leaf's copy cannot drift from the SDK's,
  and explains why this is **not** an SDK gap: a template-rendered app is
  *writer-shaped*, not *SPA-shaped* — the case `data-api-base` was invented for,
  where the server already owns the HTML. `scitex_editor_page` exists only
  because a built SPA's `index.html` is opaque bytes the server did not author.
  Same contract, two shapes; automatic injection covers one.

  Also records a foot-gun the page's own example invites: two classic `<script>`
  tags each declaring `const STX_MOUNT` share one global scope, so the second is
  a `SyntaxError` that breaks the **whole page**, not just that file.

- **Why a patch release for a documentation change.** The contract page ships
  *inside the wheel* (`scitex_app/_skills/scitex-app/33_mount-prefix.md`), so a
  doc fix that is not released does not exist for the people it is written for —
  and the misleading version is the one currently on PyPI. That is the same
  failure 0.7.0 was cut to end, one level down: 0.7.0 existed only because a
  working contract had been sitting unreleased on `develop` while three
  consumer apps each invented their own answer to a question the SDK had already
  answered. Shipping the correction immediately is the consistent move.

  No code changed. `scitex_app` behaves identically to 0.7.0.

## [0.7.0] - 2026-08-18

- **feat(django): the SDK now tells the browser where the app is mounted.**
  `scitex_urlpatterns` was already prefix-agnostic on the server — its patterns
  are relative, so `include()` works under any root — but nothing told the
  *browser*. Client code had no supported way to learn its mount point, so
  leaves hardcoded `/`: correct standalone, silently broken the moment the app
  is embedded under a prefix.

  `scitex_editor_page` now injects a marker into the served shell:

      <meta name="stx-mount" content="/apps/u/figrecipe/">

  The value is derived server-side from `request.path`. That is exact rather
  than a guess: the view is registered at `path("", ...)`, so its request path
  *is* the mount prefix. Never compute it client-side.

  **Prior art, and it is not ours.** scitex-writer hit this first and solved it
  in its own templates — `data-api-base="{{ api_base|default:'/' }}"` read back
  as `root.dataset.apiBase`, with relative endpoint names joined onto it. That
  pattern *is* the contract; `stx-mount` is simply the SDK's supported way to
  obtain the base, so every app gets it without inventing a third mechanism.
  Read the marker, join relative endpoint names onto it, and the same build
  works at `/` and under any prefix.

  **Why a `<meta>` and not `<base href>` or a template render.** A built SPA's
  `index.html` routinely contains `{{` and `{%` inside inlined JS. Running it
  through Django's template engine would try to interpret those and corrupt the
  bundle for reasons unrelated to mounting. The injection is therefore a plain
  string insertion that adds exactly one tag and touches nothing else. It is
  matched against `<head>` / `<head ...>` specifically — a substring search for
  `<head` also matches `<header`, which placed the marker inside a `<header>`
  element on documents that had one and no real head. Where there is no head at
  all the tag is prepended, which is still correct (the parser hoists a leading
  `<meta>`), so the prefix is never silently dropped.

- **Why this is a minor bump, stated plainly because the omission is the
  lesson.** The feature above landed on `develop` while `pyproject.toml` still
  read `0.6.1` — the same string already published to PyPI and already
  installed across the fleet. Two different builds wore one version number, so
  "am I on 0.6.1?" answered *yes* for a build that lacked the feature and *yes*
  for a build that had it. A version string that cannot distinguish them has
  stopped being an identifier. The practical cost was real: three consumer apps
  looked as though they had ignored a contract that, from where they sat, did
  not exist.

- **test(django): one assertion per test**, and the mount marker is pinned
  against both real mounts it exists to span — `/` standalone and
  `/apps/u/<module>/` as a scitex-hub built-in app.

- **fix(ci): auto-merge counted QUEUED checks as green.** A check still sitting
  in the queue is not a passing check; treating it as one made the gate report
  success before the evidence existed.

- **chore(audit-config): retire 8 PS-224 exemptions measured inert**, and
  relocate the security reasoning into the workflows themselves, so the reason
  lives next to the thing it justifies.

## [0.6.1] - 2026-08-05

- **fix(gui-launcher): `--force` could SIGTERM an unrelated process.**
  `argv_is_ours()` scanned the whole argv including `argv[0]` — the
  *interpreter* path. A project-local venv puts the project name in that path,
  so `/home/x/<project>/.venv/bin/python` claimed **every** process started
  from that venv as ours: a test run, a jupyter kernel, an unrelated dev
  server. Since `serve_gui(--force)` terminates on `holder.ours`, the flag
  could kill a stranger whose only connection to us was the directory its
  interpreter happened to live under — precisely the failure `--force` exists
  to avoid.

  0.5.0's own note claimed ownership "is proven from the holder's argv, not
  its name". The proof was weaker than the sentence: the documented
  counter-example (`myscitex_writerx` does not match) is about **token
  boundaries** and said nothing about **path segments**.

  `argv[0]` now contributes only its last two path components — the program
  and the directory immediately containing it. One level up is what a program
  *is*; three levels up is only where it lives. Everything after `argv[0]` is
  matched whole, so module paths still count:

  | argv[0] | verdict |
  |---|---|
  | `/opt/venv/…/scitex_writer/__main__.py` | ours — parent names it |
  | `/usr/local/bin/scitex-writer-gui` | ours — script names it |
  | `/home/x/<project>/.venv/bin/python` | **not** ours |
  | `/home/x/<project>/.venv/bin/jupyter` | **not** ours |

  All four are pinned by tests, so the boundary cannot drift silently in
  either direction. Reported by scitex-scholar with a deterministic
  reproduction in which only `argv[0]` differed.

  Known residual, documented in the docstring rather than left implied: a
  stranger run as `python /home/x/<package>/run.py` still matches, because a
  script living inside the package tree is real argv evidence.

## [0.6.0] - 2026-08-05

- **security(paths): caller-supplied path components are now validated and
  contained.** `scitex_app.paths` joined `owner` / `repo` / `slug` straight
  onto a filesystem root with no validation and no containment check. On the
  hub these were not exploitable for traversal only because Django's `<str:>`
  URL converter excludes `/` — a property of the **routing layer**, not of
  this module. Every other consumer lost that: a CLI caller, a service
  embedding the package, or a future `<path:>` route on the hub itself, which
  would have silently re-opened it. A guard that holds only because of what
  some caller upstream happens to do is not a guard.

  Measured before the fix: **3 of 14** behaviours safe. Cross-tenant reach was
  real, not theoretical — `owner="alice"`, `repo="../../bob/proj/bobrepo"`
  returned bob's actual project directory. An absolute component escaped the
  base directory entirely, because `Path("/a/b") / "/c"` is `Path("/c")`:
  pathlib silently discards the root. After: **14 of 14**.

  Both checks are required and neither substitutes for the other. Per-segment
  validation alone misses a symlink planted inside the root; containment alone
  misses cross-tenant reach, because `owner="alice/../bob"` lands on a
  directory that is still *inside* the base dir.

  Fixed across the whole family, not just the two functions first reported:
  `resolve_user_project_dir`, `resolve_published_project_dir` (identical
  defect on `slug`), `parse_dev_module_name`, `resolve_manifest`,
  `resolve_template_dir`, `resolve_static_dir`, and `find_partial_template`
  (whose caller-supplied `filename` was never validated — a traversal filename
  read any file on the host).

  **Not a breaking change for correct callers.** A refusal returns `None`,
  which is the module's existing "not found" answer, so a probe stays a 404
  rather than becoming a 500. Refusals are logged with `%r`, so a hostile name
  cannot inject control characters into your logs. Package-side half of
  scitex-hub #527.

- **Breaking (install surface): `dev` and `docs` are PEP 735 dependency
  groups, not extras.** Requesting either as a bracketed extra no longer
  resolves; use `pip install -e . --group dev` (pip ≥ 25.1), or `--group
  docs` to build the documentation. `[all]` is unchanged and remains the only
  public extra.

  This keeps the build toolchain out of the user-facing install: `[all]` must
  give every runtime capability and no pytest, ruff or sphinx. Groups are not
  `[project.optional-dependencies]`, so the closure rule that would otherwise
  force the toolchain into `[all]` no longer applies to them.

  If you install the toolchain with an unknown extra, note that pip **warns
  and still exits 0** — so a `pip install -e ".[dev]" || fallback` chain will
  never reach its fallback and will silently install nothing. Request groups
  with `--group`, which fails loudly on a tool that does not support them.

- deprecate(chat): `LLM_MODEL` is renamed to `SCITEX_APP_LLM_MODEL`. The old
  name still works and logs a deprecation warning; it is aliased rather than
  renamed because it was a published, documented contract. If both are set the
  prefixed one wins **and the conflict is logged** — the pick is never silent.
  The unprefixed name is being retired because it is generic enough to collide
  with another tool in the same environment, which would quietly change which
  model you talk to.

## [0.5.0] - 2026-07-19

- fix(gui-launcher): `--force` now reclaims an **orphaned** instance of
  our own app — one still holding the port after dying without clearing
  its runtime state, and therefore invisible to `status()`. That is the
  exact case the flag exists for, and it was the one case it refused,
  then printed remedies that ignored `--force` entirely. A flag that
  names the fix and does not perform it is the same bug as an install
  hint that installs nothing. (scitex-writer finding, 2.31.0)

- fix(gui-launcher): ownership is proven from the holder's **argv**, not
  its process name. A `comm` of `python` names nothing and is shared by
  every Python server on the box — terminating on that evidence would
  terminate strangers.

- fix(gui-launcher): `port_holder` no longer reports "a process owned by
  another user" when the truth is "this `/proc` will not let us look".
  Our agent containers deny `/proc/<pid>/fd` even for a same-uid
  process, so the module built to prevent confident wrong answers was
  giving one. It now returns a validated `PortHolder` dataclass whose
  `status` is one of the declared `free` / `identified` / `unreadable`,
  and whose `ours` is three-valued (`True` / `False` / `None` = we could
  not look).

  **Breaking (public API):** `embed.gui_port_holder()` and
  `_gui_runtime.port_holder()` now return a `PortHolder` instead of
  `dict | None`. Callers checking `if holder is None` should use
  `if not holder.in_use`; `holder["pid"]` becomes `holder.pid`. Both
  gain an optional `package` argument that populates `ours`.

  The holder-identification path is proven against real listening
  sockets on a host; inside our containers those tests **skip**, because
  `/proc/<pid>/fd` is unreadable there. Stated rather than papered over
  — claiming a green we did not get is the failure mode this change
  exists to fix.

## [0.4.2] - 2026-07-13

- chore: consolidate optional-dependencies into a single `[all]` extra
  (operator directive, prompted by scitex-writer PR #322). Extras are
  now all-or-nothing — `chat`/`chat-all`/`cli`/`cloud`/`django`/`mcp`
  collapse into one `[all]`; `dev`/`docs` stay separate (those are for
  building the package, not using it). `cli = []` was already empty
  (click/rich moved to base `dependencies` earlier) — an install hint
  that resolves to a no-op looks like a fix but installs nothing, and
  the user believes they already tried it. Every install-this-extra
  hint (formerly naming `mcp` or `cli`) across the CLI, skill docs, and
  sphinx docs now points at `all`. Added `tests/develop/test_extras.py`,
  which reads the real `pyproject.toml` and fails if any extra is
  empty or any referenced extra name is missing/empty.
  (#54)

## [0.4.1] - 2026-07-13

- fix(gui-runtime): `_gui_runtime.state_path(package)` now honors a
  `SCITEX_<PACKAGE>_GUI_STATE` env override before falling back to the
  `scitex_config` resolution, matching scitex-writer's pre-existing
  `SCITEX_WRITER_GUI_STATE` convention (dropped during the 0.4.0
  generalization from writer PR #316). This repo bans mocks/
  monkeypatch, so the env var is the only channel available to a
  subprocess-driven end-to-end CLI test (`gui serve` run as a real
  subprocess) — without it, such a test writes to the developer's
  actual runtime state instead of a temp file. (#51)

## [0.4.0] - 2026-07-13

- feat: add `scitex_app.embed`, a public host-embedding API. 3+ consumers
  (figrecipe, writer, scitex-todo) were reaching into the private
  `scitex_app._django` / `scitex_app._standalone` modules for
  host-embedding, including one hard top-level import. Root cause was
  our own skill docs and app-scaffold templates teaching that private
  import pattern to every consumer; both now reference
  `scitex_app.embed`, so newly scaffolded apps stop reproducing it.
  `scitex_app.chat`'s own docstrings and docs/APP_SDK.md are also fixed
  — `from scitex_app.chat import X` raises `ModuleNotFoundError` because
  `chat` is a lazy `__getattr__` attribute, not a real submodule; the
  working form is `from scitex_app import chat` then `chat.X`. (#48)
- feat: add a shared GUI launcher (`scitex_app.embed.serve_gui` +
  `scitex_app._gui_runtime`), generalized from scitex-writer's `gui
  serve` runtime module (writer PR #316). Binds the exact port or fails
  loud (never drifts to the next free port), refuses a second instance
  via runtime state (self-healing a stale recorded pid), identifies a
  foreign port holder via `/proc` (no `ss`/`lsof` shell-out), and
  `--force` only ever stops the instance recorded in its own runtime
  state — never a process it does not own. Scaffolded apps' `gui
  --force` no longer blind-kills whatever holds the port via `fuser -k`.
  `scitex-config` is now a real (non-dev) dependency. (#49)

## [0.3.0] - 2026-07-12

- feat(validator): forbid a hand-written `version` in `manifest.json`;
  require `pip_package` (the dist name) instead. The app version is now
  the SINGLE SOURCE OF TRUTH of the installed pip package, read at
  runtime via `importlib.metadata`. A manifest `version` inevitably
  drifts from the package (2026-07 incident: manifests stuck at
  `0.14.0` while packages shipped `2.25.0` / `0.29.9` / `1.4.2`, so
  every app tile in scitex-hub showed a wrong version). Both validators
  (`scitex_app.validator.AppValidator` and
  `scitex_app.appmaker._validate`) drop `version` from their
  required-field lists, add `pip_package`, and emit an error when a
  `version` key is present. The scaffold now generates `pip_package`
  instead of `version`, and the manifest schema doc documents the rule.
  **Breaking:** existing manifests that declare `version` must remove it
  and add `pip_package`. (#47)

## [0.2.10] - 2026-06-14

(Version 0.2.9 was claimed by an earlier orphan tag on 2026-06-03 that
never published to PyPI; jumping to 0.2.10 to avoid the conflict.)

- fix(appmaker): emit nested-package layout (`<wrapper>/<name>/`) + add
  `[tool.hatch.build.targets.wheel] packages = ["<name>"]` block to
  generated `pyproject.toml`. Pre-fix the scaffold emitted a FLAT layout
  that hatchling refused to package — every `pip install --no-deps
  --target=<dir> <gitea-archive-url>` from the hub then failed with
  "Unable to determine which files to ship inside the wheel". Port of
  scitex-cloud PR #293 M4 done-gate. New test gate
  (`tests/scitex_app/appmaker/test__scaffold.py`, 36 cases, no mocks,
  incl. real `pip install` into a fresh venv) prevents regression. (#35)

## [0.2.8] - 2026-05-26

- test: de-mock + fix test quality; fix fastmcp call-tool API drift
- ci(docs): make _sphinx_html commit-back step non-fatal
- ci: normalize codecov.yml to canonical shape
- ci(quality): replace broken ecosystem-clone template with single-package audit-all
- ci(codecov): disable PR comments to stop email noise
- tests: PA-307 TQ001/TQ002/TQ003/TQ007 mechanical cleanup
- fix: NL001 PEP 515 underscore separators for integer literals
- fix(docs): suppress Sphinx docstring RST issues and duplicate FilesBackend warning

## [0.2.7] - 2026-05-26

- fix(workflows): resync integrated release pipeline from scitex-dev v0.11.20
- fix(workflows): standardize to scitex-dev canonical set
- ci+docs: normalize workflow filenames + README badges (PS-164)
- quality: subprocess coverage + dev extras + audit gate + flat file-ops API
- docs(readme): recommend uv pip install <pkg>[all] (faster resolver)
- ci(release): sync publish-pypi.yml fix from ecosystem
- release(deps): bump 0.2.6 -> 0.2.7; auto-publish on tag push

## [0.2.6]

- Initial CHANGELOG entry — see git log for prior history.
