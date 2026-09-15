---
description: |
  [TOPIC] Hub Plugin Install — One Line
  [DETAILS] How a SciTeX app package becomes a scitex-hub app with `pip install <pkg>` and no hub code edits — the `scitex.apps` entry point it must declare, what the hub derives from it (INSTALLED_APPS, URL mount, launcher tile), and the helpers in `scitex_app.plugins`.
tags: [scitex-app-hub-plugin-install]
---

# Hub Plugin Install — One Line

```bash
pip install my-awesome-app      # then restart the hub
```

That is the whole install. Pre-installed apps (figrecipe, writer, ...) use the
same path — the hub's dependency list pins them, the entry point does the rest.

## What the package must declare

1. A Django app whose AppConfig subclasses `ScitexAppConfig`, with
   `manifest.json` beside `apps.py` (`name`, `slug`, `label`, `pip_package`,
   `icon` — see [15_manifest-schema](15_manifest-schema.md)).
2. A `urls.py` in that app with RELATIVE routes (see
   [33_mount-prefix](33_mount-prefix.md)).
3. ONE entry point pointing at the AppConfig:

```toml
[project.entry-points."scitex.apps"]
my_awesome_app = "my_awesome_app.apps:MyAwesomeAppConfig"
```

## What the hub does with it

| Step | When | Result |
|------|------|--------|
| `installed_app_paths(INSTALLED_APPS)` | settings | AppConfig added (templates, static, locale, models found) |
| `include("<config.name>.urls")` at `mount_route(config)` | urls | served at manifest `url`, else `/apps/<slug>/` |
| `ModuleConfig` from `config.manifest` | ready | launcher tile (label, icon, category, order) |

The hub skips a mount or tile whose route/slug it already serves itself, so a
plugin can never shadow a hub page. An app already listed by hand (e.g.
`figrecipe._django`) is REPLACED in place by the discovered AppConfig.

## Helpers (`scitex_app.plugins`, stdlib-only at settings time)

```python
from scitex_app.plugins import (
    discover_plugin_apps,   # -> [PluginApp(name, app_config, distribution)]
    installed_app_paths,    # merge into INSTALLED_APPS, no imports
    loaded_plugin_configs,  # ready AppConfig instances (after django.setup)
    mount_route,            # "apps/<slug>/" or manifest "url"
)
```

Try it: `pip install -e examples/hello_world_app` on a hub, restart, open
`/apps/hello-world/`.

## Not this

- `scitex_modules` (returns a hub `ModuleConfig`) and `scitex_hub.apps`
  (urlpatterns for store-published `/apps/u/<module>/`) are older, narrower
  hooks; a new app needs only `scitex.apps`.
- Dev-install (`scitex-app app dev-install`) is per-user preview, not install.
