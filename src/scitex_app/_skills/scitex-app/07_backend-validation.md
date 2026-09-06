---
description: |
  [TOPIC] Backend SDK — App Validation
  [DETAILS] Backend SDK — App validation pipeline (manifest, structure, CSS, JS, bundle size, privileges) and the minimal-app checklist..
tags: [scitex-app-backend-validation]
---

# Backend SDK — App Validation

Companion to [02_backend-sdk.md](02_backend-sdk.md); path helpers are in
[03_paths.md](03_paths.md).

## App Validation

```python
from scitex_app.validator import AppValidator

validator = AppValidator("/path/to/myapp")      # accepts str or Path
result = validator.validate()

result.passed            # bool
result.errors            # List[str] — fail conditions
result.warnings          # List[str] — advisory notices; result.manifest: dict|None
```

**Two entry points, and NEITHER IS A SUPERSET OF THE OTHER.** Read this before
relying on either. `AppValidator` (above) is the class documented here; the CLI
`scitex-app app validate` calls `scitex_app.appmaker.validate`, a separate
implementation.

**THEY DO NOT TAKE THE SAME `app_dir`.** The CLI wants the directory holding
`manifest.json` (`<pkg>/_django`); `AppValidator` resolves it from the package
root. Hand the CLI a package root and it reports `manifest.json not found`
while `AppValidator` reads it fine — measured on scholar, 15 errors vs 3, and
**0 vs 0** once each gets the path it wants. Agreement at the right roots hides
it. Measured coverage, each at its own root:

| check | `scitex-app app validate` | `AppValidator` |
| --- | --- | --- |
| manifest / structure / CSS | yes | yes |
| Python forbidden patterns | yes | **no** (scans no `.py` at all) |
| templates, dependencies | yes | **no** |
| mount-prefix safety | yes (**ARMED** 0.14.0) | **no** |
| JS dangerous patterns | yes (opt-in) | yes |
| bundle size cap | yes (opt-in) | yes |
| privilege types and scopes | yes (opt-in) | yes |

The last three were **ported into the CLI path**, no longer exclusive. Opt-in:

```python
validate(app_dir, check_js_safety=True, check_bundle_size=True,
         check_privileges=True)
```

Off by default, and the default IS the arming switch. The narrowed JS rule
reports **0** on `scholar/_django` and `writer/_django` and fires on planted
hazards — but zero is equally consistent with "the scan did not run", so those
three stay unarmed until a peer reports a finding I did not construct.

**`check_prefix_safety` is the exception: ARMED as of 0.14.0.** Its findings are
errors, so a caller that raises on a non-empty result — including hub's
publication path — refuses an app carrying a root-absolute or document-relative
request URL; pass `check_prefix_safety=False` to opt out. This said "opt-in" for
two releases after it stopped being true, the one stale place that shipped to
app developers.

**Report the denominator.** "0 findings" is not a claim; "0 findings across N
files" is, and N == 0 means NOT SCANNED rather than CLEAN:

```python
from scitex_app.appmaker import scannable_files, validate_prefix_safety

print(len(scannable_files(app_dir)), "files")   # <- the denominator
for row in validate_prefix_safety(app_dir):
    print(row)
```

**To scan a REF, export it — not a detached worktree.**

```bash
git archive <ref> | tar -x -C "$(mktemp -d)"
```

This used to say "use a detached worktree", which cost hub a whole measurement:
before 0.14.4 the `.worktrees/` skip matched the ABSOLUTE path, so a scan rooted
in one had every file excluded by an ancestor — 1,116 files / 0 findings on a
tree holding 262. Fixed in 0.14.4; the export is still the better habit for a
REF, being the ref and nothing else.

A positive control proves the instrument RUNS, not that it is POINTED anywhere.
Both, or neither is evidence. Since 0.14.1 a missing path raises, not "clean".

Still divided on CSS: `#main-content { color: red }` passes the CLI and fails
`AppValidator`; `footer { display: none }` does the reverse.
`validate_css_canonical()` is the one measured answer but is UNARMED, so the
divergence describes what runs today. On MANIFESTS the only divergence is
`license`, required by the CLI alone (6 of the 7 apps already declare it). Card
`app-two-validators-docs-describe-the-uncalled-one-20260822`.

## Errors vs advice (CLI path)

`scitex_app.appmaker` exposes two entry points to the same pipeline:

```python
from scitex_app.appmaker import validate, validate_with_warnings

errors = validate(app_dir)                       # failures only
errors, warnings = validate_with_warnings(app_dir)
```

Only `errors` fails a build; advisory notices print in yellow either way.

Two findings are advisory:

| finding | why it is advice |
| --- | --- |
| `manifest.json 'name' should end with '_app' / '-app'` | an app can have a real reason not to — a name that would COLLIDE with an existing registry entry — and there is no exemption mechanism |
| `use --workspace-* / --text-* instead of --color-*` | the deprecated variables still render; this is drift from the spec, not a broken app |

Both were once **enforced as failures despite being worded as advice** — one
flat list, and the CLI exits 1 on any entry — which made the first unclearable:
its only prescribed escape was the collision the name avoids. Everything else
is a hard error whose wording matches its enforcement; not a precedent.

`AppValidator` runs, in order: `validate_manifest()` (required fields, valid
JSON, **no `version` key**), `validate_structure()` (`_django/views.py` and
`urls.py`), `validate_css()` (see *Workspace CSS*), `validate_js()`,
`validate_bundle_size()` (50 MB, `max_bundle_size`), `validate_privileges()`.

`version` in `manifest.json` is REJECTED by both — derived at runtime from
`pip_package`. A hand-written one drifts, and did: every hub app tile once showed
a wrong version. The shipped example carried one until 0.15.3.

### Workspace CSS — what your app may and may not style

This was a flat list of eight names describing **a validator nothing called**,
wrong both ways: `.stx-shell-*` is not blanket no-touch (hub's apps carry 42
legitimate `stx-shell-sidebar__*` lines) and it omitted names that are. The
rule is **ownership by NODE, not by name**; tables live in
`scitex_app.appmaker._validate`, deliberately not copied here:

| tier | what | rule |
|---|---|---|
| 1 | `SHELL_INSTANCE_NAMES` / `SHELL_INSTANCE_PREFIXES` — ids and shell root classes an app can never own | any mention is an error |
| 2 | `APP_CONTAINERS` (the box you render INTO), `SHARED_COMPONENT_CLASSES` (you render your own instance), `SHELL_TOKEN_PREFIXES`, `BODY_STATE_CLASSES` | your own instance is yours; **no `!important`**, never redefine a token at `:root`/`html` |
| 3 | selectors reaching the shell **without naming anything** — a bare `[data-pane]{}` | scope under your app's root — **NOT CHECKED, needs a parser** |

```python
from scitex_app.appmaker._validate import validate_css_canonical

report = validate_css_canonical("path/to/app")   # RAISES on a non-app root
print(report.summary())   # findings, denominator, blind spot
report.files_scanned      # 0 means NOT SCANNED, not clean
report.not_checked        # tier 3, and the bare-`footer` residual
for f in report.details:  # BRANCH ON f.rule, never on the message text
    f.rule, f.tier, f.path, f.line, f.selector, f.subject
```

**One app, not a tree — it REFUSES rather than warns.** A root without
`manifest.json` raises `NotAnAppDirectoryError`; to sweep a tree loop your app
dirs, calling this per app (`css_files()` is the walk, ungated). Until 0.20.0
it returned the count beside a caveat: hub read 346 findings on their root —
app population 15 — as a 12.8x regression, with a floor asserted and a control
firing. Both passed: one asks if the walk found files, the other if the rule
can fire; **neither asks if the tree is in scope.**

**Branch on `rule`, never the message.** Findings were strings, so the only
consumer keyword-matched them and mis-bucketed 316. `findings`/`str(f)` unchanged.

**UNARMED** — `validate()` still runs the older four-name `validate_css()`;
pass `check_css_canonical=True`. Arming replaces that call, not adds to it.
Second declared residual: a substring test cannot tell whether a bare
`footer { … }` reaches the shell's, so `!important` on an unscoped `footer` and
`footer { display: none }` are errors and every other bare-`footer` passes.

Blocked JS patterns and skipped scan dirs are `DANGEROUS_JS_PATTERNS` and
`PREFIX_SKIP_DIRS` in the same module. The hand-copied lists that stood here
had both drifted; a stale list is worse than a pointer — nobody re-checks it.

## Minimal App Checklist

```
myapp/
  _django/
    __init__.py
    apps.py      # class MyAppConfig(ScitexAppConfig)
    views.py     # editor_page = scitex_editor_page(...); api_dispatch = scitex_api_dispatch(...)
    urls.py      # urlpatterns = scitex_urlpatterns(views)
    manifest.json
  src/           # Python core logic (no Django)
```

- manifest.json must have all 5 required fields
- CSS scoped to your own nodes (*Workspace CSS*); no dangerous JS patterns
- `_django/views.py` and `_django/urls.py` required for platform integration
- Use `get_files()` for all file I/O — never `open()` directly in app logic
- **Packaging**: apps with a `bridge` key must keep `_django/frontend/src/` in
  their source tree — hub discovers bridges by scanning sibling directories.
  Use an `[app]` optional extra for platform Python deps; in CI, clone the repo
  as a sibling.
