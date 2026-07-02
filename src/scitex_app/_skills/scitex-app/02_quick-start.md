---
description: |
  [TOPIC] scitex-app Quick Start
  [DETAILS] Smallest example — scaffold an app, validate, dev-install into a local workspace, and test in the browser.
tags: [scitex-app-quick-start]
version: 0.2.6
exported_via: installed
---

# Quick Start

## CLI: scaffold → validate → dev-install

```bash
scitex-app app init . --name my_app
scitex-app app validate .
scitex-app app dev-install . --server http://127.0.0.1:8000
```

`init` lays down the standard app layout (`manifest.json`, views,
templates, urls, static, css). `validate` runs the manifest-schema +
minimal-app checks. `dev-install` registers the app with a running
SciTeX Cloud workspace for live iteration.

## Open the workspace

```bash
xdg-open http://127.0.0.1:8000          # browser
```

The new app appears in the workspace sidebar (see
`11_app-registration.md` for sidebar internals).

## Python: read/write app files

```python
import scitex_app

# Save a CSV inside the active app's data area
scitex_app.put_file("results/today.csv", b"a,b\n1,2\n")

# Stream it back
data = scitex_app.get_file("results/today.csv")
```

The Files SDK auto-routes between local disk and cloud backends based
on the active backend registration. See `19_files-sdk.md` for the
full surface.

## Submit when ready

```bash
scitex-app app submit . --target prod
```

## Next steps

- `04_cli-reference.md` — full CLI subcommand surface
- `03_python-api.md` — Python SDK reference
- `10_app-lifecycle.md` — end-to-end lifecycle walkthrough
- `15_manifest-schema.md` — manifest.json schema
