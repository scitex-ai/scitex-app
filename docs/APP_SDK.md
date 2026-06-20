# SciTeX App SDK -- Backend Interface and Validation

scitex-app is the write-once Python SDK that apps use to interact with files, data, and platform services. It works identically in local, cloud, and self-hosted environments.

## Package Overview

```
scitex_app/
  __init__.py          # Public API: get_files, register_backend, build_tree
  paths.py             # Path resolution for app directories and manifests
  sdk/
    _protocol.py       # FilesBackend protocol (structural typing)
    _filesystem.py     # Local pathlib backend
    _cloud_files.py    # Cloud REST API backend
    _client.py         # PlatformClient for cloud API
    _tree.py           # File tree builder
    _cloud_data.py     # Cloud datastore SDK
    _cloud_jobs.py     # Cloud job queue SDK
    _cloud_external.py # Cloud external API proxy
    _cloud_scitex.py   # Cloud scitex-specific operations
  _chat/               # Chat/SSE streaming for app AI features
  _cli/                # CLI tools (introspect, MCP server)
  _mcp/                # MCP server for AI tool integration
```

## FilesBackend Protocol

The core abstraction. Apps code against this interface once, and it works everywhere:

```python
@runtime_checkable
class FilesBackend(Protocol):
    def read(self, path: str, *, binary: bool = False) -> str | bytes: ...
    def write(self, path: str, content: str | bytes) -> None: ...
    def list(self, directory: str = "", *, extensions: list[str] | None = None) -> list[str]: ...
    def exists(self, path: str) -> bool: ...
    def delete(self, path: str) -> None: ...
    def rename(self, old_path: str, new_path: str) -> None: ...
    def copy(self, src_path: str, dest_path: str) -> None: ...
```

### Backend Auto-Detection

```python
from scitex_app import get_files

# Local (default): uses FileSystemBackend + pathlib
files = get_files("./my_project")

# Cloud (auto): detected when SCITEX_API_TOKEN is set
files = get_files()  # routes through cloud REST API

# Explicit backend selection
files = get_files(root="./data", backend="s3")
```

Detection order: explicit `backend=` arg > `SCITEX_API_TOKEN` env var > filesystem default.

## Path Resolution

`scitex_app.paths` provides Django-agnostic path resolution:

```python
from scitex_app.paths import (
    get_base_dir,                # SCITEX_BASE_DIR env or explicit
    resolve_user_project_dir,    # data/users/<owner>/proj/<repo>/
    resolve_published_project_dir,  # data/projects/<slug>/
    resolve_manifest,            # Read manifest.json from project dir
    find_partial_template,       # Locate index_partial.html
    validate_project_structure,  # Check required files exist
)
```

### Directory Conventions

```
base_dir/
  data/
    users/<owner>/proj/<repo>/    # dev (user-installed) apps
      manifest.json
      templates/<app_name>/index_partial.html
      static/<app_name>/...
    projects/<slug>/              # published projects
      manifest.json
      ...
```

## Manifest Schema

Every app must provide a `manifest.json` at its project root:

```json
{
  "$schema": "scitex-app-manifest",
  "$schema_version": "2.0.0",
  "name": "my_app",
  "label": "My App",
  "icon": "fas fa-rocket",
  "version": "1.0.0",
  "description": "What this app does",
  "license": "MIT",
  "privileges": [
    {"type": "filesystem", "scope": "project", "reason": "Read/write data files"},
    {"type": "network", "scope": "outbound", "reason": "Fetch external datasets"}
  ],
  "dependencies": {
    "python": ["numpy", "my-app"],
    "system": [],
    "node": [],
    "r": [],
    "other": []
  },
  "container": null
}
```

### Privilege System

Apps declare what they need; the platform enforces it:

| Type | Scopes | Description |
|------|--------|-------------|
| `filesystem` | `project`, `user`, `system` | File read/write access |
| `network` | `outbound`, `inbound`, `local` | Network connections |
| `api` | `datastore`, `jobs`, `external` | Platform API access |

Each privilege includes a `reason` field shown to users during installation.

## App Discovery via Entry Points

Apps register with pip entry points for automatic discovery:

```toml
# pyproject.toml
[project.entry-points."scitex_modules"]
my_app = "my_app:scitex_module_config"
```

The entry point must return a `ModuleConfig` instance. scitex-hub's `discover_external_modules()` calls `entry_points(group="scitex_modules")` at startup.

## Cloud SDK Services

When running in the cloud, scitex-app provides additional SDK modules:

| Module | Purpose |
|--------|---------|
| `sdk._cloud_data` | Key-value datastore (CRUD + search) |
| `sdk._cloud_files` | File storage via REST API |
| `sdk._cloud_jobs` | Background job submission + polling |
| `sdk._cloud_external` | Proxied external API calls |
| `sdk._cloud_scitex` | scitex-specific operations |

All cloud modules auto-configure from `SCITEX_API_TOKEN` and `SCITEX_API_URL` environment variables.

## Chat/SSE Streaming

`scitex_app._chat` provides Server-Sent Events streaming for app AI features:

```python
from scitex_app.chat import stream_response

# In a Django view
def my_chat_view(request):
    return stream_response(request, backend="openai", model="gpt-4")
```

## App Validation Pipeline

The platform validates apps before approval using checks in both scitex-app (path/structure) and scitex-hub (security):

1. **Structure** -- `validate_project_structure()` checks for `templates/` and `index_partial.html`
2. **Manifest** -- `resolve_manifest()` parses and validates `manifest.json`
3. **Security** -- Platform-side scan for forbidden patterns (subprocess, eval, exec)
4. **Dependencies** -- Declared in manifest, verified against allowed list

## Key Files

| File | Purpose |
|------|---------|
| `sdk/_protocol.py` | `FilesBackend` protocol definition |
| `sdk/__init__.py` | `get_files()`, `register_backend()`, auto-detection |
| `sdk/_filesystem.py` | Local filesystem backend |
| `sdk/_cloud_files.py` | Cloud REST API backend |
| `paths.py` | Path resolution utilities |

## Cross-References

- **scitex-hub** (`docs/ARCHITECTURE/APP_PLATFORM.md`) -- Platform mounting, manifest loading, `ModuleConfig` registry
- **scitex-ui** (`docs/APP_SANDBOX.md`) -- Frontend CSS isolation, shared components, theme contract
- **figrecipe** (`docs/SCITEX_APP_INTEGRATION.md`) -- Reference implementation using `FilesBackend` and `_django` convention
