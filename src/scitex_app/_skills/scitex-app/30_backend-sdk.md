---
description: |
  [TOPIC] scitex_app — AI Agent Developer Guide
  [DETAILS] Backend SDK reference — FilesBackend protocol, Django integration, manifest schema, app validation, path resolution.
tags: [scitex-app-backend-sdk]
---

#!/usr/bin/env python3
# scitex_app — AI Agent Developer Guide
# Timestamp: 2026-03-18
# Audience: AI coding agents building SciTeX apps

---

## 1. Quick Start

```python
from scitex_app.sdk import get_files

# Local: pass a directory path
files = get_files("./my_project")
content = files.read("data/config.yaml")
files.write("output/result.json", '{"ok": true}')

# Cloud: auto-detected when SCITEX_API_TOKEN is set
import os
os.environ["SCITEX_API_TOKEN"] = "your-token"
os.environ["SCITEX_API_URL"] = "https://scitex.ai"
files = get_files()  # routes to cloud REST API
```

Auto-detection order:
1. Explicit `backend=` argument wins
2. `SCITEX_API_TOKEN` env var → cloud backend
3. Fallback → local `FileSystemBackend`

---

## 2. FilesBackend Protocol

`FilesBackend` is a `typing.Protocol` — no inheritance needed, just implement these 7 methods.

```python
from scitex_app.sdk import FilesBackend
from typing import List, Optional, Union

class MyBackend:                                        # no inheritance required
    def read(self, path: str, *, binary: bool = False) -> Union[str, bytes]: ...
    def write(self, path: str, content: Union[str, bytes]) -> None: ...
    def list(self, directory: str = "", *, extensions: Optional[List[str]] = None) -> List[str]: ...
    def exists(self, path: str) -> bool: ...
    def delete(self, path: str) -> None: ...            # raises FileNotFoundError
    def rename(self, old_path: str, new_path: str) -> None: ...  # raises FileNotFoundError / FileExistsError
    def copy(self, src_path: str, dest_path: str) -> None: ...   # raises FileNotFoundError
```

Registering a custom backend:

```python
from scitex_app.sdk import register_backend

def my_s3_factory(root, **kwargs) -> MyBackend:
    return MyBackend(root, **kwargs)

register_backend("s3", my_s3_factory)
files = get_files(backend="s3", bucket="my-bucket")
```

---

## 3. Django Integration

### Application shell

Django-template apps extend the adapter and fill its content block:

```django
{% extends "scitex_app/app_shell.html" %}
{% block scitex_app_content %}<main id="my-app">...</main>{% endblock %}
```

The adapter is a DELEGATE, not a shell — it has no content of its own; it
re-opens `scitex_ui/standalone_shell.html`'s `app_content` as
`scitex_app_content`, and the workspace shell (sidebar, three-col layout,
file tree, AI panel) is supplied by **scitex-ui**. A host may shadow only the
adapter and map `scitex_app_content` into its own shell; app templates must
not name `global_base.html` or extend the standalone shell directly.
`run_standalone()` requires scitex-ui and fails loudly at startup
(`ScitexUiRequiredError`) if absent, not a render-time `TemplateDoesNotExist`
— install alongside: `pip install scitex-app scitex-ui`.

### AppConfig

```python
# myapp/_django/apps.py
from scitex_app.embed import ScitexAppConfig

class MyAppConfig(ScitexAppConfig):
    name = "myapp._django"
    label = "myapp"
    verbose_name = "My App"

# Properties after loading manifest.json (see the sections below for the
# version + scope contracts in full):
# config.manifest -> dict (raw)    config.app_slug -> manifest["slug"]
# config.app_icon -> manifest["icon"]
# config.is_standalone -> bool (default False)
# config.frontend_type -> str (default "django")
# config.app_version -> INSTALLED version of pip_package (importlib.metadata,
#   NEVER a hand-written manifest "version" — see "Version display" below)
# config.app_scope -> "user"|"project" (manifest "scope", default "user" —
#   see "Application shell"; "project" opts in to a per-app selector, never the
#   global header)
# config.validate_manifest() -> List[str] (empty = valid)
```

### Version display (shared contract)

Every leaf app shows its OWN installed version, continuously, never hardcoded
(`importlib.metadata` via the shared accessor; editable checkout / missing dist → labelled `"0.0.0+local"`). Do NOT add a `version` key to `manifest.json` (the validator rejects it — it drifts); `pip_package` is the whole story.

```python
# Continuous: add "scitex_app.context_processors.app_version" (the mounted leaf) or
# ".scitex_app_version" (the SDK) to TEMPLATES OPTIONS context_processors; render
# {{ app_version }} on any page with no view change. Python: package_version("<pip_package>").
```

**Adoption (Hub / Scholar / Writer / FigRecipe / Stats / Cards / SAC):** each package shows its OWN `pip_package` — never scitex-app's number (the SDK is `package_version()`, no arg). Render in the host / scitex-ui footer or badge slot; if scitex-ui adds a version-badge token, consume it, don't fork it.

### View factories + URLs

```python
# views.py
from pathlib import Path
from scitex_app.embed import scitex_editor_page, scitex_api_dispatch

STATIC_DIR = Path(__file__).parent / "static" / "myapp"
editor_page = scitex_editor_page(static_dir=STATIC_DIR)  # 503 if build missing

def _get_editor(request): ...                            # your editor ctx or None

api_dispatch = scitex_api_dispatch(
    handlers={"load": ..., "save": ...},                  # -> JsonResponse
    parameterized=[("file/", ...)],                       # /file/<anything>
    no_editor_endpoints={"health"}, get_editor=_get_editor)

# urls.py
from scitex_app.embed import scitex_urlpatterns
from . import views
urlpatterns = scitex_urlpatterns(views)  # "" -> editor, "<path:ep>" -> api
```

---

## 4. Manifest Schema

```json
{
  "name":    "My App",
  "slug":    "myapp",
  "label":   "myapp",
  "pip_package": "myapp",
  "icon":    "fas fa-flask",
  "license": "MIT",

  "standalone":    false,
  "frontend_type": "react",
  "scope":         "project",

  "privileges": [
    {"type": "filesystem", "scope": "project"},
    {"type": "network",    "scope": "none"},
    {"type": "api",        "scope": "scitex"}
  ],
  "dependencies": ["scitex>=1.0"],
  "bridge": {}
}
```

Required: `name`, `slug`, `label`, `pip_package`, `icon`, `license`. A
hand-written `version` key is FORBIDDEN (it drifts) — the version derives from
the installed `pip_package` at runtime.

Valid privilege combinations:

| type         | valid scopes                    |
|--------------|---------------------------------|
| `filesystem` | `project`, `readonly`, `none`   |
| `network`    | `none`, `allowlist`             |
| `api`        | `scitex`, `llm`, `none`         |

---

## See also

- [03_paths.md](03_paths.md) — Path resolution helpers (existing leaf)
- [07_backend-validation.md](07_backend-validation.md) — App validation
  pipeline + minimal-app checklist (split from this file for SK401's
  200-line budget)
