---
description: |
  [TOPIC] App Registration — Internals
  [DETAILS] App registration internals — how the sidebar renders the tab, how the partial gets loaded, pyproject entry points, server-side source files, and troubleshooting. Companion to 11_app-registration.md..
tags: [scitex-app-app-registration-internals]
---

# App Registration — Internals

Companion to [11_app-registration.md](11_app-registration.md) (which
covers Registration Flow + dev-install vs published paths +
ModuleConfig). Split out for SK401 budget.

## How the Sidebar Renders the Tab

The workspace context processor (`context_processors.py`) calls
`get_all_modules()` which returns all registered `ModuleConfig` objects.
The sidebar template iterates them:

```html
{% for mod in workspace_modules %}
    <a href="{{ mod.get_url }}" class="sidebar-item" data-module="{{ mod.name }}">
        <i class="{{ mod.icon_fa }}"></i>
        <span>{{ mod.label }}</span>
    </a>
{% endfor %}
```

`mod.get_url()` returns `/apps/{name}/` unless `url` is overridden in the
config. Tab order matches the `order` field — lower numbers appear first.
Built-in SciTeX apps use 20–50; external apps should use 90+ to appear
after them.

## How the Partial Gets Loaded

When the user clicks the tab, the workspace AJAX machinery calls:

```
GET /apps/{name}/partial/
```

This calls `build_user_app_context(request)` and renders the template at
`apps_app/user_apps/{name}_partial.html`.

For dev apps, the template is read live from:
```
data/users/<owner>/proj/<repo>/templates/
```

The partial template is your `templates/my_awesome_app/index_partial.html`.

### AJAX load sequence

1. User clicks sidebar tab
2. Workspace JS: `fetch('/apps/my-awesome-app/partial/')`
3. Server resolves `ModuleConfig` for `"my-awesome-app"`
4. For dev apps: reads template from user's source directory
5. Calls `build_user_app_context(request)` to get context dict
6. Renders template with context
7. Returns HTML fragment
8. Workspace JS injects fragment into `#ws-module-pane`

## pyproject.toml Entry Point

For the app to be discoverable as a local extension (standalone mode +
testing):

```toml
[project.entry-points."scitex_modules"]
my_awesome_app = "my_awesome_app:get_module_config"
```

The `get_module_config()` function returns a `ModuleConfig` object and
is defined in the scaffolded `__init__.py`.

In deployed mode, the server uses the `AppsModule` database record +
filesystem path directly — the entry point is used for local discovery
only.

## Key Source Files (server-side)

| File | Role |
|------|------|
| `scitex-hub/apps/infra/workspace_app/registry.py` | `ModuleConfig` dataclass, `register_module()`, `get_all_modules()` |
| `scitex-hub/apps/workspace/apps_app/services/app_loader.py` | `load_approved_apps()` — published app registration at startup |
| `scitex-hub/apps/workspace/apps_app/services/dev_app_loader.py` | `build_module_config()` — per-request dev app config synthesis |
| `scitex-hub/apps/infra/workspace_app/context_processors.py` | Injects `workspace_modules` into template context |

## Troubleshooting Registration

### App tab not visible after dev-install

The module was registered but may not show for your user:
- Hard-refresh (`Ctrl+Shift+R`) — context processor output is cached in session
- Log out and log back in to clear the session
- Verify the dev-install API returned the module name `dev__<owner>__<app>`
- Confirm you are logged in as the same user whose token was used for dev-install

### App tab shows but partial fails to load (500 error)

The template loaded but `build_user_app_context` raised an exception:
- Check server logs for the Python traceback
- Common cause: `import` error in `views.py` — a missing dependency
- Test your view in isolation: `python -c "from my_awesome_app.views import partial_view"`

### App tab shows but partial returns blank content

The template rendered but produced no visible output:
- Ensure `index_partial.html` is not empty
- Check that the template is a fragment (no `<html>/<head>/<body>` tags needed but allowed)
- Verify `partial_template` in `manifest.json` points to the right path

### Order of tabs is wrong

Set `"order"` in `manifest.json` to control position. Lower = earlier.
External apps default to `90` if not set. Built-in apps use `20`–`50`.
