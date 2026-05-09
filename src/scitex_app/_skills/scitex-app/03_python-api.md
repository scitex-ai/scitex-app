---
description: |
  [TOPIC] scitex-app Python API
  [DETAILS] Top-level public surface — FilesBackend, get_files, register_backend, build_tree, chat, paths, validator.
tags: [scitex-app-python-api]
---

# Python API

Top-level public surface re-exported from `scitex_app`. Detailed
per-area docs live in companion leaves (19* and 10–18).

## Public symbols

| Name                | Kind     | Purpose                                              |
|---------------------|----------|------------------------------------------------------|
| `__version__`       | str      | Installed package version                            |
| `FilesBackend`      | class    | Abstract base — implement to register a new backend  |
| `get_files()`       | function | Retrieve the active Files SDK handle                 |
| `register_backend()`| function | Register a `FilesBackend` impl (e.g. local, S3, cloud) |
| `build_tree()`      | function | Build a hierarchical file-tree dict for a directory  |
| `chat`              | submod   | Chat / AI assistant integration (lazy)               |
| `paths`             | submod   | Standard SciTeX path resolution helpers (lazy)       |
| `validator`         | submod   | App manifest + minimal-app validation (lazy)         |

## Files SDK: example

```python
import scitex_app

files = scitex_app.get_files()
files.put("results/today.csv", b"a,b\n1,2\n")
data = files.get("results/today.csv")
files.list("results/")
```

## Backend registration

```python
from scitex_app import FilesBackend, register_backend

class S3Backend(FilesBackend):
    def get(self, path): ...
    def put(self, path, data): ...
    def list(self, prefix): ...

register_backend("s3", S3Backend(bucket="my-bucket"))
```

## File tree

```python
import scitex_app
tree = scitex_app.build_tree("/path/to/app/data")
# nested dict suitable for the workspace ShellFileTree
```

## Lazy submodules

```python
import scitex_app
scitex_app.paths.app_data_dir("my_app")
scitex_app.validator.validate_manifest("./manifest.json")
scitex_app.chat.send("hello")
```

These are imported on first attribute access via `__getattr__` —
no penalty for users who never touch them.

## Detailed per-area references

- `19_files-sdk.md` — Files SDK surface
- `19a_backend-sdk.md` — backend developer SDK
- `19b_paths.md` — `paths` submodule
- `19c_cli.md` — CLI internals (legacy)
- `15_manifest-schema.md` — manifest.json schema
- `07_backend-validation.md` — validation pipeline
