---
description: |
  [TOPIC] scitex-app Installation
  [DETAILS] pip install scitex-app; zero runtime deps (stdlib SDK); smoke verify with scitex-app version + app init.
tags: [scitex-app-installation]
---

# Installation

## Standard

```bash
pip install scitex-app
```

Pure Python, **zero runtime dependencies**. The SDK uses only the
standard library so it can run inside locked-down workspace
environments.

## Optional MCP extra

```bash
pip install 'scitex-app[mcp]'         # AI-agent MCP tools
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

To **dev-install** an app into a running SciTeX Cloud workspace, also
install:

```bash
pip install scitex-cloud         # provides the workspace endpoint
```

Used as:

```bash
scitex-app app dev-install /tmp/demo_app --server http://127.0.0.1:8000
```
