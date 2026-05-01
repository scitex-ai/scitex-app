---
description: Backend SDK reference — FilesBackend protocol, Django integration, manifest schema, app validation, path resolution
name: backend-sdk
tags: [scitex-app, scitex-package]
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

### AppConfig

```python
# myapp/_django/apps.py
from scitex_app._django import ScitexAppConfig

class MyAppConfig(ScitexAppConfig):
    name = "myapp._django"
    label = "myapp"
    verbose_name = "My App"

# Properties available after loading manifest.json:
# config.manifest        -> dict (raw manifest)
# config.app_slug        -> str  (manifest["slug"])
# config.app_version     -> str  (manifest["version"])
# config.app_icon        -> str  (manifest["icon"])
# config.is_standalone   -> bool (manifest["standalone"], default False)
# config.frontend_type   -> str  (manifest["frontend_type"], default "django")
# config.validate_manifest() -> List[str]  (empty = valid)
```

### View factories

```python
# myapp/_django/views.py
from pathlib import Path
from scitex_app._django import scitex_editor_page, scitex_api_dispatch

STATIC_DIR = Path(__file__).parent / "static" / "myapp"

# Serves React SPA index.html; returns 503 if build missing
editor_page = scitex_editor_page(
    static_dir=STATIC_DIR,
    index_file="index.html",                    # default
    fallback_message="Run: npm run build",      # default
)

def _get_editor(request):
    """Return your app's editor/context object, or None."""
    ...

api_dispatch = scitex_api_dispatch(
    handlers={
        "load":   lambda req, editor: ...,      # JsonResponse
        "save":   lambda req, editor: ...,
    },
    parameterized=[
        ("file/", lambda req, editor, param: ...),  # /file/<anything>
    ],
    no_editor_endpoints={"health"},             # endpoints that skip editor check
    get_editor=_get_editor,
)
```

### URL patterns

```python
# myapp/_django/urls.py
from scitex_app._django import scitex_urlpatterns
from . import views

urlpatterns = scitex_urlpatterns(views)
# Generates:
#   ""                  -> views.editor_page  (name="editor")
#   "<path:endpoint>"   -> views.api_dispatch (name="api")
```

---

## 4. Manifest Schema

```json
{
  "name":    "My App",
  "slug":    "myapp",
  "label":   "myapp",
  "version": "0.1.0",
  "icon":    "fas fa-flask",

  "standalone":    false,
  "frontend_type": "react",

  "privileges": [
    {"type": "filesystem", "scope": "project"},
    {"type": "network",    "scope": "none"},
    {"type": "api",        "scope": "scitex"}
  ],
  "dependencies": ["scitex>=1.0"],
  "bridge": {}
}
```

Required fields: `name`, `slug`, `label`, `version`, `icon`

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
