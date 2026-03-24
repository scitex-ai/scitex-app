---
name: app-lifecycle
description: End-to-end guide for creating a SciTeX app — scaffold, develop, validate, dev-install, test, submit. Use when creating a new app from scratch.
---

# App Lifecycle — From Scaffold to Published

Complete walkthrough for creating a SciTeX workspace app.

## Prerequisites

```bash
pip install scitex-app scitex-ui
```

## Step 1: Scaffold

```bash
mkdir my-app && cd my-app
scitex-app app init . --name my_app --frontend react
```

This creates ~20 files:
```
my_app/
  _django/
    __init__.py
    apps.py          # MyAppConfig(ScitexAppConfig)
    views.py         # editor_page + api_dispatch
    urls.py          # scitex_urlpatterns(views)
    manifest.json    # App metadata
    frontend/
      src/
        bridge/
          bridge-init.ts    # Entry point (auto-discovered)
          MountPoint.ts     # React root mount
        components/         # Your React components
        store/              # Zustand state
        api/                # Fetch wrappers
  src/                      # Python core logic (no Django)
  tests/
  pyproject.toml
  README.md
```

## Step 2: Edit manifest.json

```json
{
  "name": "My App",
  "slug": "my_app",
  "label": "My App",
  "version": "0.1.0",
  "icon": "fas fa-flask",
  "standalone": false,
  "frontend_type": "react",
  "privileges": [
    {"type": "filesystem", "scope": "project"},
    {"type": "network", "scope": "none"},
    {"type": "api", "scope": "scitex"}
  ],
  "dependencies": ["scitex>=1.0"],
  "bridge": {
    "entry": "src/bridge/bridge-init.ts",
    "source_root": "src"
  }
}
```

Required: `name`, `slug`, `label`, `version`, `icon`

## Step 3: Implement

### Backend (views.py)

```python
from scitex_app._django import scitex_editor_page, scitex_api_dispatch

editor_page = scitex_editor_page(static_dir=STATIC_DIR)

def _get_editor(request):
    # Return your app's context object
    return {"project": request.project}

api_dispatch = scitex_api_dispatch(
    handlers={
        "load": lambda req, editor: JsonResponse({"data": "..."}),
        "save": lambda req, editor: JsonResponse({"ok": True}),
    },
    get_editor=_get_editor,
)
```

### Frontend (bridge-init.ts)

```typescript
import "scitex-ui/css/app.css";
import { mountMyApp } from "./MountPoint";

function init(): void {
  const mount = document.getElementById("app-mount");
  if (!mount) return;
  mountMyApp(mount);
}

// Auto-init
if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", init);
} else {
  init();
}
```

### Use scitex-ui components

```typescript
import { DataTable } from "scitex-ui/react/app";
import { usePanelResize } from "scitex-ui/react/app";
import { FileBrowser } from "scitex-ui/react/app";
```

### Use scitex-app file SDK

```python
from scitex_app.sdk import get_files

files = get_files("./project")
content = files.read("data/config.yaml")
files.write("output/result.csv", csv_text)
```

## Step 4: Validate

```bash
scitex-app app validate .
```

Checks:
- manifest.json has required fields
- `_django/views.py` and `_django/urls.py` exist
- No CSS targeting shell selectors (`#scitex-ai-panel`, `.stx-shell-*`, etc.)
- No dangerous JS (`eval(`, `document.cookie`, etc.)
- Bundle size < 50 MB
- Privilege types and scopes are valid

## Step 5: Dev-Install

```bash
scitex-app app dev-install . --server http://127.0.0.1:8000
```

This:
1. Creates a `DevInstallation` record in the database
2. Copies your app to the server's dev apps directory
3. Registers it in the workspace sidebar (for your user only)

## Step 6: Test in Browser

1. Navigate to `http://127.0.0.1:8000/`
2. Your app should appear in the sidebar
3. Click it — the module pane loads your app's content
4. Test all functionality: API calls, file operations, UI components

## Step 7: Submit for Publication

```bash
scitex-app app submit .
```

This creates a PR to the SciTeX app registry. After review + approval:
- App appears in the public catalog
- Users can install it from the Apps page
- It gets its own sidebar tab when installed

## Reference Implementation

Study figrecipe for a complete working example:

```
~/proj/figrecipe/src/figrecipe/_django/          # Django patterns
~/proj/figrecipe/src/figrecipe/_django/frontend/  # React + bridge
~/proj/figrecipe/src/figrecipe/_django/manifest.json  # Manifest example
```

## Common Patterns

### Embedded vs Standalone

```typescript
// bridge-init.ts
const isEmbedded = !!document.getElementById("workspace-content");
if (isEmbedded) {
  // Running inside scitex-cloud workspace
  mountApp(document.getElementById("app-mount"));
} else {
  // Running standalone (scitex-app serve)
  mountApp(document.getElementById("root"));
}
```

### Panel Resize (scitex-ui)

```typescript
import { usePanelResize } from "scitex-ui/react/app";

function MyEditor() {
  const { leftWidth, rightWidth, resizerProps } = usePanelResize({
    storageKey: "myapp-panel",
    defaultLeftPercent: 30,
  });
  return (
    <div style={{ display: "flex" }}>
      <div style={{ width: leftWidth }}>Sidebar</div>
      <div {...resizerProps} />
      <div style={{ width: rightWidth }}>Main</div>
    </div>
  );
}
```

### Bridge Events (cross-component communication)

```typescript
import { emitBridgeEvent, onBridgeEvent } from "scitex-ui";

// Send
emitBridgeEvent("myapp", "file-opened", { path: "/data/config.yaml" });

// Listen
onBridgeEvent("myapp", "file-opened", (detail) => {
  console.log("Opened:", detail.path);
});
```

# EOF
