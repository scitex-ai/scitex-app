---
description: |
  [TOPIC] App Lifecycle — End-to-End Guide
  [DETAILS] End-to-end guide for building a SciTeX app — scaffold, develop, validate, dev-install, test, and submit. Includes actual CLI commands with expected outputs, complete manifest schema, and file structure..
tags: [scitex-app-app-lifecycle]
---

# App Lifecycle — End-to-End Guide

Full workflow for building and shipping a SciTeX workspace app from scratch.

```
scaffold → develop → validate → dev-install → test in browser → submit
```

Prerequisites:
- `pip install scitex-app[cli]` — installs the `scitex-app` CLI
- A running SciTeX Cloud instance (for dev-install) at `http://127.0.0.1:8000`
- A JWT token from your profile settings on the server

**Detailed sub-guides:**
- [app-develop](app-develop.md) — views.py, urls.py, templates, CSS, React patterns
- [app-validate-install](app-validate-install.md) — validate, dev-install, test, troubleshoot

---

## Step 1: Scaffold

```bash
# Scaffold into a new directory (HTML frontend, default)
scitex-app app init . --name my_awesome_app --label "My Awesome App" \
    --icon "fas fa-flask" --description "Does something useful."

# React+Vite+Zustand frontend
scitex-app app init . --name my_awesome_app --frontend react

# Overwrite existing files
scitex-app app init . --name my_awesome_app --overwrite
```

**Expected output:**
```
Scaffolding app: my_awesome_app in /path/to/my_awesome_app
  + __init__.py
  + apps.py
  + views.py
  + urls.py
  + tests.py
  + skill.py
  + manifest.json
  + templates/my_awesome_app/index.html
  + templates/my_awesome_app/index_partial.html
  + static/my_awesome_app/css/my_awesome_app.css
  + .agents/agents.json
  + AGENTS.md
  + docs/PLATFORM.md
  + README.md
  + LICENSE
  + .gitignore
  + pyproject.toml
  + _cli.py

Done! Created 18 files.
```

App name **must** end with `_app` or `-app`. The CLI auto-appends the suffix if missing.

React frontend adds: `package.json`, `vite.config.js`, `src/bridge/bridge-init.ts`, `src/components/`, `src/store/`.

### Python API

```python
from scitex_app.appmaker import init_app
from pathlib import Path

created = init_app(
    target_dir=Path("./my_awesome_app"),
    name="my_awesome_app",       # must end with _app or -app
    label="My Awesome App",
    icon="fas fa-flask",
    description="Does something useful.",
    frontend_type="html",        # or "react"
    license_id="AGPL-3.0",
    overwrite=False,
)
print(f"Created {len(created)} files")
```

### Resulting file structure

```
my_awesome_app/
    __init__.py
    apps.py                                  # Django AppConfig
    views.py                                 # HTTP views
    urls.py                                  # URL routing
    tests.py
    skill.py
    manifest.json                            # App metadata (required)
    _cli.py                                  # Standalone CLI entry point
    templates/
        my_awesome_app/
            index.html                       # Full-page view (standalone)
            index_partial.html               # AJAX partial (workspace tab)
    static/
        my_awesome_app/
            css/
                my_awesome_app.css
    .agents/agents.json
    AGENTS.md
    docs/PLATFORM.md
    README.md
    LICENSE
    .gitignore
    pyproject.toml
```

---

## Step 2: Develop

Edit `views.py`, `urls.py`, `templates/`, `static/`, and `manifest.json`.
See [app-develop.md](app-develop.md) for full patterns.

**Key files:**

| File | Purpose |
|------|---------|
| `views.py` | Django views + context builder |
| `urls.py` | URL routing |
| `templates/<name>/index_partial.html` | App HTML (AJAX-loaded into workspace pane) |
| `static/<name>/css/<name>.css` | Scoped CSS — use `.my-awesome-app-*` prefixes |
| `manifest.json` | App metadata, privileges, frontend config |

---

## See also

- [14_app-lifecycle-deploy.md](14_app-lifecycle-deploy.md) — Steps 3–6
  (validate, dev-install, test, submit) + canonical reference
  implementation. Split from this file for SK401's 200-line budget.
- [15_manifest-schema.md](15_manifest-schema.md) — Complete manifest.json
  schema (required fields, optional metadata, privileges, dependencies).

# EOF
