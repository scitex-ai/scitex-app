---
description: |
  [TOPIC] Backend SDK — App Validation
  [DETAILS] Backend SDK — App validation pipeline (manifest, structure, CSS, JS, bundle size, privileges) and the minimal-app checklist..
tags: [scitex-app-backend-validation]
---

# Backend SDK — App Validation

Companion to [02_backend-sdk.md](02_backend-sdk.md) (split out for SK401
budget). Path resolution helpers live in [03_paths.md](03_paths.md).

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
implementation. Measured coverage:

| check | `scitex-app app validate` | `AppValidator` |
| --- | --- | --- |
| manifest / structure / CSS | yes | yes |
| Python forbidden patterns | yes | **no** (scans no `.py` at all) |
| templates, dependencies | yes | **no** |
| mount-prefix safety | yes (**ARMED** 0.14.0) | **no** |
| JS dangerous patterns | yes (opt-in) | yes |
| bundle size cap | yes (opt-in) | yes |
| privilege types and scopes | yes (opt-in) | yes |

The last three were **ported into the CLI path** and are no longer exclusive to
`AppValidator`. They are opt-in:

```python
validate(app_dir, check_js_safety=True, check_bundle_size=True,
         check_privileges=True)
```

Off by default, and the default IS the arming switch. The narrowed JS rule
reports **0** on `scholar/_django` and `writer/_django` and still fires on
planted hazards — but zero is consistent both with "the fleet is clean" and
with "the scan did not run", so those three stay unarmed until a peer reports
a finding I did not construct.

**`check_prefix_safety` is the exception: ARMED as of 0.14.0.** `validate()`
runs it unless you pass `check_prefix_safety=False`, and its findings are
errors, so a caller that raises on a non-empty result — including scitex-hub's
publication path — will refuse an app over it. From 0.14.0 an app carrying a
root-absolute or document-relative request URL cannot be published.

This paragraph said "opt-in" until the day it was not — one of three places the
same sentence went false at once, and **the only one that shipped stale to app
developers**, for two releases. A wrong docstring misleads a maintainer reading
the source; a wrong skill doc misleads someone with no reason to check.

**And when you run the rule yourself, report the denominator.** "0 findings" is
not a claim; "0 findings across N files" is, and N == 0 means NOT SCANNED
rather than CLEAN:

```python
from scitex_app.appmaker import scannable_files, validate_prefix_safety

print(len(scannable_files(app_dir)), "files")   # <- the denominator
for row in validate_prefix_safety(app_dir):
    print(row)
```

**To scan a REF rather than a working tree, export it — do not reach for a
detached worktree.**

```bash
git archive <ref> | tar -x -C "$(mktemp -d)"
```

This used to say "use a detached worktree", and that advice cost scitex-hub a
whole measurement on 2026-09-05: `.worktrees/` is a skipped name, and before
0.14.4 the skip matched the ABSOLUTE path, so a scan ROOTED in a worktree had
every file excluded by an ancestor — 1,116 files / 0 findings on a tree holding
262. 0.14.4 matches relative to the scan root, so worktrees scan correctly now;
the export is still the better habit for a REF, being the ref and nothing else.

A positive control (a temp tree with `fetch("/api/thing")`, which must return
exactly 1) proves the instrument RUNS, not that it is POINTED at anything — a
control runs on a tree that exists. Both, or neither is evidence. Since 0.14.1
a path that does not exist raises rather than answering "clean".

What remains genuinely divided is the CSS and manifest half: `#main-content
{ color: red }` passes the CLI and fails `AppValidator`; `footer { display:
none }` does the reverse. Card
`app-two-validators-docs-describe-the-uncalled-one-20260822`. **The CSS half
now has one answer**, measured against the shell rather than argued from either
list: `validate_css_canonical()` (0.15.0, *Workspace CSS* below). It is
UNARMED, so the divergence still describes what runs today; arming collapses
the two. The manifest half is unchanged.

## Errors vs advice (CLI path)

`scitex_app.appmaker` exposes two entry points to the same pipeline:

```python
from scitex_app.appmaker import validate, validate_with_warnings

errors = validate(app_dir)                       # failures only
errors, warnings = validate_with_warnings(app_dir)
```

Only `errors` fails a build. `scitex-app app validate` prints advisory notices
in yellow, whether or not the app passes, and exits non-zero **only** on errors.

Two findings are advisory:

| finding | why it is advice |
| --- | --- |
| `manifest.json 'name' should end with '_app' / '-app'` | an app can have a real reason not to — a name that would COLLIDE with an existing registry entry — and there is no exemption mechanism |
| `use --workspace-* / --text-* instead of --color-*` | the deprecated variables still render; this is drift from the spec, not a broken app |

Both used to be **enforced as failures despite being worded as advice**, because
`validate()` returned one flat list and the CLI exits 1 on any entry. That made
the first one unclearable: the only escape it prescribed was to introduce the
collision the name avoids. Everything else `validate()` reports is a hard error
whose wording matches its enforcement, and this is not a precedent for softening
those.

`AppValidator` runs, in order: `validate_manifest()` (required fields, valid
JSON, **no `version` key**), `validate_structure()` (`_django/views.py` and
`urls.py`), `validate_css()` (see *Workspace CSS*), `validate_js()`,
`validate_bundle_size()` (50 MB, `max_bundle_size`), `validate_privileges()`.

`version` in `manifest.json` is REJECTED by both implementations — it is
derived at runtime from `pip_package` via `importlib.metadata`. A hand-written
one drifts, and did: every hub app tile once showed a wrong version from this.

### Workspace CSS — what your app may and may not style

This was a flat list of eight names, "shell selectors apps must NOT target".
**It described a validator nothing called**, and was wrong in both directions:
`.stx-shell-*` is not blanket no-touch (hub's own apps carry 42 legitimate
selector lines on `stx-shell-sidebar__*`), and it omitted names that are. The
rule is **ownership by NODE, not by name**; the tables live in
`scitex_app.appmaker._validate` and are deliberately not copied here:

| tier | what | rule |
|---|---|---|
| 1 | `SHELL_INSTANCE_NAMES` / `SHELL_INSTANCE_PREFIXES` — ids and shell root classes an app can never own | any mention is an error |
| 2 | `APP_CONTAINERS` (the box you render INTO), `SHARED_COMPONENT_CLASSES` (you render your own instance), `SHELL_TOKEN_PREFIXES`, `BODY_STATE_CLASSES` | your own instance is yours; **no `!important`**, never redefine a token at `:root`/`html` |
| 3 | selectors reaching the shell **without naming anything** — a bare `[data-pane]{}` | scope under your app's root — **NOT CHECKED, needs a parser** |

```python
from scitex_app.appmaker._validate import validate_css_canonical

report = validate_css_canonical("path/to/app")
print(report.summary())   # findings AND denominator AND blind spot
report.files_scanned      # 0 means NOT SCANNED, not clean
report.not_checked        # tier 3, and the bare-`footer` residual
```

**UNARMED** — `validate()` still runs the older four-name `validate_css()`;
pass `check_css_canonical=True` for this one. Arming replaces that call rather
than adding to it. Second declared residual: whether a bare `footer { … }`
reaches the shell's footer. A substring test cannot tell, so `!important` on an
unscoped `footer` and `footer { display: none }` are errors and every other
bare-`footer` rule passes.

Blocked JS patterns and skipped scan directories are `DANGEROUS_JS_PATTERNS`
and `PREFIX_SKIP_DIRS` in the same module — read them from there. The two
hand-copied lists that stood here had both drifted (the skip list omitted five
names and invented one), and a stale list is worse than a pointer: nobody
re-checks it.

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
- **Packaging**: Apps with a `bridge` key in manifest.json must keep
  `_django/frontend/src/` in their source tree. scitex-hub discovers
  bridges by scanning sibling directories. Use an `[app]` optional extra
  for platform Python deps. In CI, clone the repo as a sibling.
