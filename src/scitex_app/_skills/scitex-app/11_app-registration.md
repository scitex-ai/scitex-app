---
description: How a SciTeX app registers with the workspace sidebar — manifest.json to ModuleConfig to sidebar tab. Covers dev-install path, published app path, ModuleConfig fields, frontend integration points, and troubleshooting.
name: app-registration
tags: [scitex-app, scitex-package]
---

# App Registration — How Apps Appear in the Workspace

When a SciTeX app is installed or published, it appears as a tab in the workspace
sidebar. This document traces the full registration flow from `manifest.json` through
`ModuleConfig` to the rendered tab.

---

## Registration Flow

```
manifest.json → ModuleConfig dataclass → register_module() → workspace sidebar
```

Two paths exist depending on development stage:

---

## Path 1: Dev Install (during development)

```bash
export SCITEX_API_TOKEN="your-jwt-token"
scitex-app app dev-install . --server http://127.0.0.1:8000
```

1. Local validation runs (`scitex-app app validate .`).
2. `POST /apps/store/api/dev/install/` is called with `{"owner": "alice", "repo": "my-awesome-app"}`.
3. A `DevInstallation` database record is created:
   - `source_owner` = your username
   - `source_repo` = repo slug from manifest `slug` field
   - `module_name` = `dev__alice__my-awesome-app` (auto-generated)
4. On each workspace page load, `build_module_config(dev_install)` synthesizes a `ModuleConfig` for that user.
5. The app tab appears **only for you** — no global registry pollution.

Templates are served live from `data/users/<owner>/proj/<repo>/templates/` on the
server filesystem. Edits to `index_partial.html` take effect on the next page load
without reinstall.

### Module name convention

Dev modules always follow: `dev__<owner>__<repo>`

Examples:
- Owner `alice`, repo `my-awesome-app` → `dev__alice__my-awesome-app`
- Owner `bob`, repo `data-viz-app` → `dev__bob__data-viz-app`

The `repo` component comes from the manifest `slug` field (hyphen-separated).

---

## Path 2: Published App (after submission and approval)

```bash
scitex-app app submit .
```

1. A PR is opened on the scitex-apps registry at `gitea.scitex.ai/scitex-apps/registry`.
2. After approval:
   - An `AppsModule` database record is created with `visibility="public"`.
   - `load_approved_apps()` runs at Django startup (or immediately after approval).
   - For each public module, `load_single_app()` reads the manifest and calls `register_module(config)`.
   - The module is added to the global registry.
3. The context processor includes it in `workspace_modules` for all users.
4. Users install it from the app catalog (`default_enabled=False` until they do).

---

## ModuleConfig — What Gets Registered

```python
from apps.infra.workspace_app.registry import ModuleConfig

ModuleConfig(
    # Identity
    name="my-awesome-app",      # URL slug → /apps/my-awesome-app/
    label="My Awesome App",     # Sidebar display label
    app_name="apps_app",        # Always "apps_app" for external apps

    # Icon
    icon_fa="fas fa-flask",     # FontAwesome class from manifest "icon"

    # Template
    partial_template="apps_app/user_apps/my-awesome-app_partial.html",

    # Context
    context_builder="apps.workspace.apps_app.services.app_context.build_user_app_context",

    # Ordering
    order=90,                   # Built-ins use 20–50; external apps use 90+

    # Visibility
    default_enabled=False,      # User must add it from catalog

    # Dev flags (dev-install path only)
    is_dev=True,
    status="wip",

    # LLM / accessibility
    ai_hint="Short description injected into LLM context.",

    # Legal
    license="AGPL-3.0",
)
```

### manifest.json fields → ModuleConfig fields

| `manifest.json` field | `ModuleConfig` field | Notes |
|----------------------|----------------------|-------|
| `slug` | `name` | URL path segment (hyphen-separated) |
| `label` | `label` | Sidebar display name |
| `icon` | `icon_fa` | FontAwesome class |
| `version` | stored in `AppsModule` | Semantic version string |
| `privileges` | `privileges` | Declared capabilities |
| `ai_hint` | `ai_hint` | LLM context injection |
| `order` | `order` | Tab position (default 90) |
| `license` | `license` | License identifier |

### Fields set automatically (not from manifest)

| Field | Value | Why |
|-------|-------|-----|
| `app_name` | `"apps_app"` | All external apps go through apps infrastructure |
| `partial_template` | `"apps_app/user_apps/{name}_partial.html"` | Standard location |
| `context_builder` | `"...build_user_app_context"` | Standard external app context |
| `order` | `90` | External apps appear after built-ins (20–50) |
| `default_enabled` | `False` | Requires user to install from catalog |

---

## See also

- [16_app-registration-internals.md](16_app-registration-internals.md) —
  How the sidebar renders the tab, how the partial gets loaded,
  pyproject entry points, server-side source files, and troubleshooting.
  Split from this file for SK401's 200-line budget.

# EOF
