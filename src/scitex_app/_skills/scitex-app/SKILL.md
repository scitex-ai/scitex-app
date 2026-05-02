---
description: App-developer SDK for SciTeX workspace apps — write-once for local + cloud, zero-dep stdlib. Python API — `get_files(root)` (returns `FilesBackend` auto-detecting local vs cloud), `files.read / write / exists / delete / rename / copy / list`, `build_tree(files, max_depth=)`, `register_backend(name, factory)` (plug in S3/NAS), lazy submodules `chat`, `paths`, `validator`, and `scitex_app._standalone.run_standalone(app_module=, port=)` (run an app without the Django shell). 11 MCP tools — project-file ops (`app_read_file`, `app_write_file`, `app_list_files`, `app_file_exists`, `app_delete_file`, `app_rename_file`, `app_copy_file`) + app-lifecycle (`app_scaffold`, `app_validate`) + skills meta (`skills_list`, `skills_get`). Further lifecycle — `dev-install`, `submit`, bump/version, slug/icon — live in the CLI (`scitex-app app dev-install / submit`) and appmaker internals, not as MCP tools. Replaces copy-pasting Django starter apps, hand-rolled `manifest.json`, per-app `startproject` scaffolds, and `pathlib`/`boto3` scattered through app code. Use when the user asks to "scaffold a SciTeX app", "init a workspace app", "validate my app manifest", "dev-install" (→ CLI), "submit the app" (→ CLI), "read/write files with auto local/cloud backend", "register an S3 backend", "run this app standalone", "build a file tree", or mentions `manifest.json`, `ModuleConfig`, workspace sidebar registration, scitex-app SDK.
allowed-tools: mcp__scitex__app_*
primary_interface: cli
interfaces:
  python: 2
  cli: 3
  mcp: 2
  skills: 2
  hook: 0
  http: 0
name: scitex-app
tags: [scitex-app, scitex-package]
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

`pip install scitex-app` alone does NOT expose `scitex.app` — also
`pip install scitex` for the umbrella form. See
[../../general/02_interface-python-api.md] for the ecosystem-wide rule.

## Leaves

### Core SDK / interfaces
- [01_files-sdk](01_files-sdk.md)
- [02_backend-sdk](02_backend-sdk.md)
- [03_paths](03_paths.md)
- [04_cli](04_cli.md)
- [05_standalone](05_standalone.md)
- [06_environment-vars](06_environment-vars.md)
- [07_backend-validation](07_backend-validation.md) — App validation pipeline + minimal-app checklist
### Workflows / references
- [10_app-lifecycle](10_app-lifecycle.md) — End-to-end: scaffold → develop → validate → dev-install → test → submit.
- [11_app-registration](11_app-registration.md) — Workspace sidebar registration via manifest.json → ModuleConfig.
- [12_app-develop](12_app-develop.md) — Development patterns: views, urls, templates, CSS scoping, React bridge.
- [13_app-validate-install](13_app-validate-install.md) — Validate, dev-install, browser testing, troubleshooting.
- [14_app-lifecycle-deploy](14_app-lifecycle-deploy.md) — Lifecycle Steps 3-6 (validate/dev-install/test/submit) + figrecipe reference.
- [15_manifest-schema](15_manifest-schema.md) — Complete manifest.json schema reference.
- [16_app-registration-internals](16_app-registration-internals.md) — Sidebar render, partial load, entry points, source files, troubleshooting.
- [17_app-develop-frontend](17_app-develop-frontend.md) — CSS scoping, React frontend, Files SDK in views.
- [18_app-test-troubleshoot](18_app-test-troubleshoot.md) — Browser testing, standalone mode, troubleshooting catalogue, env vars.

## Quick Start

```bash
scitex-app app init . --name my_app
scitex-app app validate .
scitex-app app dev-install . --server http://127.0.0.1:8000
```

Python API examples live in [01_files-sdk.md](01_files-sdk.md).
