---
description: |
  [TOPIC] scitex-app Installation
  [DETAILS] pip install scitex-app; small base deps (click/rich/scitex-config); pip install scitex-app[all] for chat/cloud/django/mcp; smoke verify with scitex-app version + app init.
tags: [scitex-app-installation]
---

# Installation

## Standard

```bash
pip install scitex-app
```

Base dependencies (`click`, `rich`, `scitex-config`) are small and
runtime-agnostic — the file-ops SDK core still runs anywhere.

## Optional extras

Extras are all-or-nothing — one `[all]` extra covers chat (anthropic/
litellm), cloud (requests), Django integration, and MCP tools
(fastmcp):

```bash
pip install 'scitex-app[all]'
```

## Umbrella

```bash
pip install scitex            # also exposes import scitex.app
```

`pip install scitex-app` alone does NOT make `import scitex.app` work —
install the umbrella for that form. See
`../../general/02_interface-python-api.md`.

## Verify

```bash
python -c "import scitex_app; print(scitex_app.__version__)"
scitex-app --help
scitex-app app init /tmp/demo_app --name demo
scitex-app app validate /tmp/demo_app
```

Expected: a version string, the CLI help, then a scaffolded app at
`/tmp/demo_app/` that passes validation.

## Cloud companion (optional)

To **dev-install** an app into a running SciTeX Hub workspace, also
install:

```bash
pip install scitex-hub           # provides the workspace endpoint
```

Used as:

```bash
scitex-app app dev-install /tmp/demo_app --server http://127.0.0.1:8000
```
