---
description: App developer SDK — scaffold, validate, dev-install, standalone shell, file operations, and cloud SDK for building SciTeX workspace apps. Use when creating, testing, or deploying SciTeX apps.
allowed-tools: mcp__scitex__app_*
---

# scitex-app — App Developer SDK

Toolkit for building SciTeX workspace apps with scaffold, validation,
standalone mode, and cloud integration.

## Installation & import (two equivalent paths)

The same module is reachable via two install paths. Both forms work at
runtime; which one a user has depends on their install choice.

```python
# Standalone — pip install scitex-app
import scitex_app
scitex_app.get_files(...)

# Umbrella — pip install scitex
import scitex.app
scitex.app.get_files(...)
```

`pip install scitex-app` alone does NOT expose the `scitex` namespace;
`import scitex.app` raises `ModuleNotFoundError`. To use the
`scitex.app` form, also `pip install scitex`.

See [../../general/02_interface-python-api.md] for the ecosystem-wide
rule and empirical verification table.

## Leaves

### Core SDK / interfaces
- [01_files-sdk](01_files-sdk.md)
- [02_backend-sdk](02_backend-sdk.md)
- [03_paths](03_paths.md)
- [04_cli](04_cli.md)
- [05_standalone](05_standalone.md)
- [06_environment-vars](06_environment-vars.md)

### Workflows / references
- [10_app-lifecycle](10_app-lifecycle.md) — End-to-end: scaffold → develop → validate → dev-install → test → submit.
- [11_app-registration](11_app-registration.md) — Workspace sidebar registration via manifest.json → ModuleConfig.
- [12_app-develop](12_app-develop.md) — Development patterns: views, urls, templates, CSS scoping, React bridge.
- [13_app-validate-install](13_app-validate-install.md) — Validate, dev-install, browser testing, troubleshooting.

## Quick Start

```bash
scitex-app app init . --name my_app
scitex-app app validate .
scitex-app app dev-install . --server http://127.0.0.1:8000
```

```python
from scitex_app.sdk import get_files, build_tree
from scitex_app._standalone import run_standalone

files = get_files("./my_project")
content = files.read("config/settings.yaml")
files.write("output/result.csv", csv_text)
tree = build_tree(files, max_depth=2)
run_standalone(app_module="my_app", port=8050)
```

<!-- EOF -->
