---
name: app-lifecycle
description: App scaffolding, validation, dev-install, and submission API. init_app(), validate(), AppValidator, ValidationResult, and the full end-to-end workflow.
---

# App Lifecycle

Full lifecycle for SciTeX workspace apps: scaffold → validate → dev-install → submit.

## init_app()

```python
from scitex_app.appmaker import init_app

def init_app(
    target_dir: str | Path,
    name: str,
    *,
    label: str = "",
    icon: str = "fas fa-puzzle-piece",
    description: str = "",
    manifest: Optional[dict] = None,
    license_id: str = "AGPL-3.0",
    overwrite: bool = False,
    frontend_type: str = "html",   # "html" or "react"
) -> list[str]
```

Generates complete app boilerplate. Returns list of relative paths created. Skips existing files unless `overwrite=True`.

```python
from scitex_app.appmaker import init_app
from pathlib import Path

created = init_app(
    target_dir=Path("./my_awesome_app"),
    name="my_awesome_app",          # must end with _app or -app
    label="My Awesome App",
    icon="fas fa-flask",
    description="A SciTeX workspace app.",
    frontend_type="html",           # or "react" for React+Vite+Zustand
)
print(f"Created {len(created)} files")
```

### Generated files (HTML frontend, ~17 files)

```
__init__.py
apps.py
views.py
urls.py
tests.py
skill.py
manifest.json
templates/<name>/index.html
templates/<name>/index_partial.html
static/<name>/css/<name>.css
.agents/agents.json
AGENTS.md
docs/PLATFORM.md
README.md
LICENSE
.gitignore
pyproject.toml
_cli.py
```

React frontend (`frontend_type="react"`) adds additional files: `package.json`, `vite.config.js`, `src/bridge/bridge-init.ts`, `src/components/`, `src/store/`.

### manifest.json required fields

```json
{
  "name": "my_awesome_app",
  "slug": "my-awesome-app",
  "label": "My Awesome App",
  "version": "0.1.0",
  "icon": "fas fa-flask",
  "description": "...",
  "privileges": []
}
```

Required fields: `name`, `slug`, `label`, `version`, `icon`.

### Privilege types

```json
"privileges": [
  {"type": "filesystem", "scope": "project"},
  {"type": "network",    "scope": "none"},
  {"type": "api",        "scope": "scitex"}
]
```

| Type | Valid scopes |
|------|-------------|
| `filesystem` | `project`, `readonly`, `none` |
| `network` | `none`, `allowlist` |
| `api` | `scitex`, `llm`, `none` |

## validate()

```python
from scitex_app.appmaker import validate

errors = validate(app_dir)   # list[str], empty = passed
if not errors:
    print("Ready for submission")
else:
    for e in errors:
        print(f"ERROR: {e}")
```

Thin wrapper around `AppValidator` — returns error strings directly.

## AppValidator

Full validation pipeline. Pure Python, no Django dependency.

```python
from scitex_app.validator import AppValidator

validator = AppValidator("/path/to/myapp")
result = validator.validate()

print(result.passed)    # bool
for err in result.errors:
    print(f"ERROR: {err}")
for warn in result.warnings:
    print(f"WARN:  {warn}")
```

```python
class AppValidator:
    def __init__(
        self,
        app_path: str | Path,
        max_bundle_size: int = 50 * 1024 * 1024,  # 50 MB default
    )

    def validate(self) -> ValidationResult
    def validate_manifest(self) -> None
    def validate_structure(self) -> None
    def validate_css(self) -> None
    def validate_js(self) -> None
    def validate_bundle_size(self) -> None
    def validate_privileges(self) -> None
```

### What each check validates

| Check | What it does |
|-------|-------------|
| `validate_manifest` | manifest.json exists, has required fields, valid semver version |
| `validate_structure` | `_django/views.py` and `_django/urls.py` exist |
| `validate_css` | CSS does not target reserved shell selectors |
| `validate_js` | JS/TS/JSX/TSX has no dangerous patterns |
| `validate_bundle_size` | Total file size is under `max_bundle_size` |
| `validate_privileges` | Declared privileges use valid types and scopes |

### ValidationResult

```python
@dataclass
class ValidationResult:
    passed: bool
    errors: List[str]
    warnings: List[str]
    privileges: List[dict]
    manifest: Optional[dict]
```

`result.add_error(msg)` — appends to errors and sets `passed = False`.
`result.add_warning(msg)` — appends to warnings, does not fail.

### Forbidden CSS selectors

Apps must not target: `#scitex-ai-panel`, `#main-content`, `.ws-module-pane`, `.workspace-header`, `.workspace-sidebar`, `.stx-shell-*`, `#workspace-container`, `.ws-app-sidebar`.

### Forbidden JS patterns

`eval(`, `Function(`, `document.cookie`, `window.parent`, `window.top`, `__import__`, `os.system`, `subprocess`, `exec(`.

## End-to-end workflow

```bash
# 1. Scaffold
scitex-app app init . --name my_app

# 2. Develop (edit views.py, templates/, etc.)

# 3. Validate
scitex-app app validate .

# 4. Dev-install on running SciTeX Cloud instance
export SCITEX_API_TOKEN="your-jwt-token"
scitex-app app dev-install . --server http://127.0.0.1:8000

# 5. Test in browser at http://127.0.0.1:8000/

# 6. Submit for public review
scitex-app app submit .
```

## Reference implementation

Study `figrecipe` for a complete working example:

```
~/proj/figrecipe/src/figrecipe/_django/           # Django views + urls
~/proj/figrecipe/src/figrecipe/_django/frontend/  # React + bridge
~/proj/figrecipe/src/figrecipe/_django/manifest.json
```
