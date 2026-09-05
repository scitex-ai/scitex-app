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

print(result.passed)     # bool
print(result.errors)     # List[str] — fail conditions
print(result.warnings)   # List[str] — advisory notices
print(result.manifest)   # dict | None
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

Off by default, and the default IS the arming switch. Measured against the
fleet's app packages before shipping: the narrowed JS rule reports **0** on
`scholar/_django` and `writer/_django`, and still fires on planted hazards.
Zero findings is consistent both with "the fleet is clean" and with "the scan
did not run", so those three stay unarmed until a peer reports a finding I did
not construct.

**`check_prefix_safety` is the exception: ARMED as of 0.14.0.** `validate()`
runs it unless you pass `check_prefix_safety=False`, and its findings are
errors, so a caller that raises on a non-empty result — including scitex-hub's
publication path — will refuse an app over it. From 0.14.0 an app carrying a
root-absolute or document-relative request URL cannot be published.

This paragraph said the prefix rule was opt-in until the day it was not. Worth
naming, because it is the third place the same sentence went false at once: the
rule's own docstring said "NOT ARMED", `validate_with_warnings` said "EVERY
`check_*` KEYWORD IS OFF BY DEFAULT", and this file said opt-in. The first two
were corrected in the arming change; **this one shipped stale to app developers
for two releases**, which is the worst of the three — a docstring misleads a
maintainer reading the source, a skill doc misleads someone who has no reason
to check.

**And when you run the rule yourself, report the denominator.** "0 findings" is
not a claim; "0 findings across N files" is, and N == 0 means NOT SCANNED
rather than CLEAN:

```python
from scitex_app.appmaker import scannable_files, validate_prefix_safety

print(len(scannable_files(app_dir)), "files")   # <- the denominator
for row in validate_prefix_safety(app_dir):
    print(row)
```

A positive control (a temp tree with `fetch("/api/thing")`, which must return
exactly 1) proves the instrument RUNS. It does not prove it is pointed at
anything — a control runs on a tree that exists. Both, or neither is evidence.
Since 0.14.1 a path that does not exist raises rather than answering "clean".

What remains genuinely divided is the CSS and manifest half, where the two
modules answer the SAME question differently — `#main-content { color: red }`
passes the CLI and fails `AppValidator`; `footer { display: none }` does the
reverse. Tracked on card
`app-two-validators-docs-describe-the-uncalled-one-20260822`, waiting on the
authoritative shell-selector list from scitex-hub.

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

`AppValidator` validation pipeline (runs in order):
1. `validate_manifest()` — required fields, valid JSON, and **no `version` key**
2. `validate_structure()` — `_django/views.py` and `_django/urls.py` present
3. `validate_css()` — no CSS targeting shell selectors (see below)
4. `validate_js()` — no dangerous JS patterns
5. `validate_bundle_size()` — total size < 50 MB (configurable via `max_bundle_size`)
6. `validate_privileges()` — privilege types and scopes must be valid

`version` in `manifest.json` is REJECTED by both implementations. The app
version is derived at runtime from the installed `pip_package` via
`importlib.metadata`; a hand-written one drifts, and did — every hub app tile
once showed a wrong version from exactly this. Declare `pip_package` instead.

Shell selectors apps must NOT target:
`#scitex-ai-panel`, `#main-content`, `.ws-module-pane`, `.workspace-header`,
`.workspace-sidebar`, `.stx-shell-*`, `#workspace-container`, `.ws-app-sidebar`

Dangerous JS patterns blocked:
`eval(`, `Function(`, `document.cookie`, `window.parent`, `window.top`,
`__import__`, `os.system`, `subprocess`, `exec(`

Skipped directories during scanning: `node_modules`, `dist`, `.vite`,
`_docs`, `__pycache__`, `assets`

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
- No CSS targeting shell selectors
- No dangerous JS patterns
- `_django/views.py` and `_django/urls.py` required for platform integration
- Use `get_files()` for all file I/O — never `open()` directly in app logic
- **Packaging**: Apps with a `bridge` key in manifest.json must keep
  `_django/frontend/src/` in their source tree. scitex-hub discovers
  bridges by scanning sibling directories. Use an `[app]` optional extra
  for platform Python deps. In CI, clone the repo as a sibling.
