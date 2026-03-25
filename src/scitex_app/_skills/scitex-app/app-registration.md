---
description: How a SciTeX app registers with the workspace sidebar — manifest.json to ModuleConfig to sidebar tab. Use when building apps that need to appear in the workspace.
---

# App Registration — How Apps Appear in the Workspace

When a SciTeX app is installed, it appears as a tab in the workspace sidebar.
This document explains the registration flow.

## Registration Flow

```
manifest.json → ModuleConfig dataclass → register_module() → workspace sidebar
```

There are two paths:

### Path 1: Dev Install (during development)

```bash
scitex-app app dev-install . --server http://127.0.0.1:8000
```

This creates a `DevInstallation` record in the database:
- `source_owner`: your username
- `source_repo`: repo name
- `module_name`: `dev__<owner>__<repo>` (auto-generated)

At startup, `build_module_config(dev_install)` creates a `ModuleConfig` and
registers it. The app appears in the sidebar for that user only.

### Path 2: Published App (after submission + approval)

```bash
scitex-app app submit .
```

This creates a PR to the app registry. After approval:
1. An `AppsModule` record is created with `visibility="public"`
2. At Django startup, `load_approved_apps()` iterates all public modules
3. For each, `load_single_app()` reads manifest.json and builds `ModuleConfig`
4. `register_module(config)` adds it to the global registry
5. The context processor includes it in `workspace_modules` for templates

## ModuleConfig Fields (what matters for apps)

```python
ModuleConfig(
    name="myapp",               # URL slug → /apps/myapp/
    label="My App",             # Display name in sidebar
    app_name="apps_app",        # Always "apps_app" for external apps
    icon_fa="fas fa-flask",     # FontAwesome icon class
    partial_template="apps_app/user_apps/myapp_partial.html",
    context_builder="apps.workspace.apps_app.services.app_context.build_user_app_context",
    order=90,                   # After built-in modules (20-50)
    default_enabled=False,      # User must install from catalog
    ai_hint="Short description for LLM context",
    license="AGPL-3.0",        # SPDX identifier
)
```

### Fields you control via manifest.json

| manifest.json field | → ModuleConfig field | Purpose |
|---------------------|---------------------|---------|
| `slug` | `name` | URL path segment |
| `name` | `label` | Sidebar display name |
| `icon` | `icon_fa` | FontAwesome icon class |
| `version` | (stored in AppsModule) | Semantic version |
| `privileges` | `privileges` | Declared capabilities |

### Fields set automatically

| ModuleConfig field | Value | Why |
|-------------------|-------|-----|
| `app_name` | `"apps_app"` | All external apps use the apps infrastructure |
| `partial_template` | `"apps_app/user_apps/{name}_partial.html"` | Standard partial location |
| `context_builder` | `"...build_user_app_context"` | Standard context for external apps |
| `order` | `90` | External apps appear after built-ins |

## How the Sidebar Renders It

The workspace context processor (`context_processors.py`) calls `get_all_modules()`
which returns all registered `ModuleConfig` objects. The template iterates:

```html
{% for mod in workspace_modules %}
    <a href="{{ mod.get_url }}" class="sidebar-item" data-module="{{ mod.name }}">
        <i class="{{ mod.icon_fa }}"></i>
        <span>{{ mod.label }}</span>
    </a>
{% endfor %}
```

`get_url()` returns `/apps/{name}/` by default.

## Key Source Files

- `scitex-cloud/apps/infra/workspace_app/registry.py` — ModuleConfig + register_module()
- `scitex-cloud/apps/workspace/apps_app/services/app_loader.py` — load_approved_apps()
- `scitex-cloud/apps/workspace/apps_app/services/dev_app_loader.py` — build_module_config()
- `scitex-cloud/apps/infra/workspace_app/context_processors.py` — injects into templates

# EOF
