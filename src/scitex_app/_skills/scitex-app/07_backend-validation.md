---
description: Backend SDK — App validation pipeline (manifest, structure, CSS, JS, bundle size, privileges) and the minimal-app checklist.
name: backend-validation
tags: [scitex-app, scitex-package]
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

Validation pipeline (runs in order):
1. `validate_manifest()` — required fields, valid JSON, semver version
2. `validate_structure()` — `_django/views.py` and `_django/urls.py` present
3. `validate_css()` — no CSS targeting shell selectors (see below)
4. `validate_js()` — no dangerous JS patterns
5. `validate_bundle_size()` — total size < 50 MB (configurable via `max_bundle_size`)
6. `validate_privileges()` — privilege types and scopes must be valid

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
  `_django/frontend/src/` in their source tree. scitex-cloud discovers
  bridges by scanning sibling directories. Use an `[app]` optional extra
  for platform Python deps. In CI, clone the repo as a sibling.
