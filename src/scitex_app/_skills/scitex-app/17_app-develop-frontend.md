---
description: App frontend patterns — CSS scoping rule (forbidden shell selectors), React frontend scaffold (bridge, store, vite config), and Files SDK usage in views.
name: app-develop-frontend
tags: [scitex-app, scitex-package]
---

# App Development — Frontend & Files SDK

Companion to [12_app-develop.md](12_app-develop.md) (which covers
views.py / urls.py / apps.py / index_partial.html). Split out for SK401
budget.

## CSS Scoping Rule

All CSS must be scoped to the app's own prefix. Never target reserved
shell selectors — validation rejects them.

```css
/* my_awesome_app/static/my_awesome_app/css/my_awesome_app.css */

/* Correct — scoped to app prefix */
.my-awesome-app-container { padding: 1rem; }
.my-awesome-app-header    { font-size: 1.2rem; font-weight: bold; }
.my-awesome-app-btn       { background: #0066cc; color: white; padding: 0.5rem 1rem; }
.my-awesome-app-output    { font-family: monospace; margin-top: 1rem; }

/* Forbidden — validation error (these target workspace shell) */
/* #scitex-ai-panel { ... }         */
/* .workspace-sidebar { ... }       */
/* #main-content { ... }            */
/* .ws-module-pane { ... }          */
/* .workspace-header { ... }        */
/* .stx-shell-anything { ... }      */
/* #workspace-container { ... }     */
/* .ws-app-sidebar { ... }          */
```

## React Frontend Pattern

If scaffolded with `--frontend react`, additional files are generated:

```
src/
    bridge/
        bridge-init.ts       # Connects React app to workspace AJAX machinery
    components/
        App.tsx              # Root React component
    store/
        index.ts             # Zustand state store
package.json
vite.config.js
```

### Build before dev-install

```bash
npm install
npm run build   # outputs to static/my_awesome_app/dist/
```

### Partial template for React apps

```html
<!-- templates/my_awesome_app/index_partial.html -->
{% load static %}
<div id="my-awesome-app-root"></div>
<script type="module" src="{% static 'my_awesome_app/dist/index.js' %}"></script>
```

### Bridge init pattern

```typescript
// src/bridge/bridge-init.ts
// Initializes communication between React app and workspace shell
import { useStore } from '../store';

window.__scitex_bridge = {
    onProjectChange: (project) => {
        useStore.getState().setProject(project);
    },
};
```

### vite.config.js output path

```javascript
// vite.config.js
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
    plugins: [react()],
    build: {
        outDir: 'static/my_awesome_app/dist',
        emptyOutDir: true,
    },
});
```

## Using the Files SDK in Views

For file operations, use the SDK instead of `open()` directly:

```python
from scitex_app.sdk import get_files

def api_view(request):
    files = get_files(request.user.project_dir)   # or get_files() for cloud
    content = files.read("data/config.yaml")
    files.write("output/result.json", '{"ok": true}')
    tree = files.list("", extensions=[".py", ".yaml"])
    return JsonResponse({"files": tree})
```

`get_files()` auto-selects backend:
1. Explicit `backend=` argument
2. `SCITEX_API_TOKEN` env var → cloud backend
3. Fallback → local `FileSystemBackend`
