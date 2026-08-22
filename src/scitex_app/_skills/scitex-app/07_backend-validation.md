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
| mount-prefix safety | yes (opt-in) | **no** |
| JS dangerous patterns | **no** | yes |
| bundle size cap | **no** | yes |
| privilege types and scopes | **no** | yes |

So switching wholesale to either one loses checks. Reconciling them is tracked
on card `app-two-validators-docs-describe-the-uncalled-one-20260822`; until
then, run BOTH if you want full coverage.

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
