---
description: App-developer SDK for SciTeX workspace apps — write-once for local + cloud, zero-dep stdlib. Python API — `get_files(root)` (returns `FilesBackend` that auto-detects local vs cloud), `files.read / write / exists / delete / rename / copy / list`, `build_tree(files, max_depth=)`, `register_backend(name, factory)` (plug in S3/NAS), lazy submodules `chat`, `paths`, `validator`, and `scitex_app._standalone.run_standalone(app_module=, port=)` (run an app without the Django workspace shell). 11 MCP tools — project-file ops (`app_read_file`, `app_write_file`, `app_list_files`, `app_file_exists`, `app_delete_file`, `app_rename_file`, `app_copy_file`) + app-lifecycle (`app_scaffold`, `app_validate`) + skills meta (`skills_list`, `skills_get`). Further lifecycle steps — `dev-install`, `submit`, bump/version, slug/icon — live in the CLI (`scitex-app app dev-install / submit`) and Python appmaker internals, not as standalone MCP tools. Drop-in replacement for copy-pasting Django starter apps, hand-rolled `manifest.json`, per-app `startproject` scaffolds, and direct `pathlib`/`boto3` scattered through app code. Use whenever the user asks to "scaffold a SciTeX app", "init a new workspace app", "validate my app manifest", "dev-install this app" (→ CLI), "submit the app to the cloud" (→ CLI), "read/write files in an app with auto local/cloud backend", "register an S3 file backend", "run this app standalone without the shell", "build a file tree", or mentions `manifest.json`, `ModuleConfig`, workspace sidebar registration, scitex-app SDK.
allowed-tools: mcp__scitex__app_*
primary_interface: cli
---

# scitex-app — App Developer SDK

> **Primary interface: CLI.** Reach for `scitex-app scaffold` first. Python API + MCP wrap the same commands for scripting / agent use.

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
