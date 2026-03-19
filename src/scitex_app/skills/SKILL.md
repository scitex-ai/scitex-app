---
name: scitex-app
description: App developer SDK — scaffold, validate, dev-install, standalone shell
---

# scitex-app Skills

App developer toolkit for building SciTeX workspace apps.

## Quick Start

```bash
pip install scitex-app[cli]
scitex-app app init . --name my_app
scitex-app app validate .
scitex-app app dev-install . --server http://127.0.0.1:8000
```

## App Lifecycle

| Command | Purpose |
|---------|---------|
| `scitex-app app init .` | Scaffold complete app (17+ files) |
| `scitex-app app init . --frontend react` | React + Vite + Zustand scaffold (23 files) |
| `scitex-app app validate .` | Check structure, security, manifest |
| `scitex-app app dev-install .` | Install on SciTeX Cloud server |
| `scitex-app app submit .` | Submit for public review |
| `my-app gui` | Launch standalone with workspace shell |

## Standalone Mode

Every scaffolded app includes a `gui` CLI command:

```python
from scitex_app._standalone import run_standalone
run_standalone(app_module="my_app", port=8050)
```

This launches a local Django server with the full workspace shell
(Console, FileTree, Viewer, App content) from scitex-ui.

## Key APIs

### FilesBackend — unified file I/O

```python
from scitex_app.sdk import get_files

files = get_files("./my_project")
content = files.read("config/settings.yaml")
files.write("output/result.csv", csv_text)
tree = files.list("", extensions=[".yaml"])
```

### build_tree — file tree for UI

```python
from scitex_app import build_tree

tree = build_tree(files, max_depth=2)
# Returns nested dicts: {path, name, type, children}
```

## Docs

```bash
scitex-app docs --page quickstart    # View quickstart guide
scitex-app docs --list               # List all doc pages
```
