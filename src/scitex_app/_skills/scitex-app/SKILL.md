---
name: scitex-app
description: App developer SDK — scaffold, validate, dev-install, standalone shell, file operations, and cloud SDK for building SciTeX workspace apps. Use when creating, testing, or deploying SciTeX apps.
allowed-tools: mcp__scitex__app_*
---

# scitex-app — App Developer SDK

Toolkit for building SciTeX workspace apps with scaffold, validation, standalone mode, and cloud integration.

## Quick Start

```bash
# Scaffold a new app
scitex-app app init . --name my_app

# Validate structure
scitex-app app validate .

# Dev-install on SciTeX Cloud
scitex-app app dev-install . --server http://127.0.0.1:8000

# Launch standalone with workspace shell
my-app gui
```

```python
from scitex_app import build_tree
from scitex_app.sdk import get_files
from scitex_app._standalone import run_standalone

# File operations via SDK
files = get_files("./my_project")
content = files.read("config/settings.yaml")
files.write("output/result.csv", csv_text)
tree_data = files.list("", extensions=[".yaml"])

# Build file tree for UI
tree = build_tree(files, max_depth=2)

# Launch standalone app
run_standalone(app_module="my_app", port=8050, open_browser=True)
```

## Python API

### Core

| Function | Purpose |
|----------|---------|
| `build_tree(files, max_depth)` | Build nested file tree dict for UI |
| `run_standalone(app_module, port, host, ...)` | Launch standalone Django server with shell |

### scitex_app.paths — Path Resolution

| Function | Purpose |
|----------|---------|
| `get_base_dir(base_dir=None)` | Get base directory for apps |
| `resolve_user_project_dir(owner, repo)` | Resolve user project directory |
| `resolve_published_project_dir(slug)` | Resolve published app directory |
| `resolve_manifest(project_dir)` | Find manifest.json in project |
| `resolve_template_dir(project_dir)` | Get template directory |
| `resolve_static_dir(project_dir)` | Get static files directory |
| `validate_project_structure(project_dir)` | Validate app directory structure |

### scitex_app.validator — App Validation

| Class/Function | Purpose |
|----------------|---------|
| `AppValidator` | Validate manifest, security, structure, bundle size |
| `ValidationResult` | Dataclass with validation results |

### scitex_app.sdk — Cloud SDK

| Function | Purpose |
|----------|---------|
| `get_client()` | Get platform API client |
| `reset_client()` | Reset client instance |
| `CloudFilesBackend` | Cloud-backed file operations |
| `sdk.data` | Cloud data CRUD operations |
| `sdk.files` | Cloud file upload/download |
| `sdk.jobs` | Cloud job submission/status |

## App Lifecycle CLI

| Command | Purpose |
|---------|---------|
| `scitex-app app init . [--frontend react]` | Scaffold app (17-23 files) |
| `scitex-app app validate .` | Check structure, security, manifest |
| `scitex-app app dev-install .` | Install on SciTeX Cloud server |
| `scitex-app app submit .` | Submit for public review |

## File Operations CLI

```bash
scitex-app read <path> [--binary] [--json]
scitex-app write <path> [--stdin] [--json] [--dry-run]
scitex-app list [<dir>] [--ext <ext>] [--json]
scitex-app exists <path> [--json]
scitex-app delete <path> [--dry-run] [--json]
scitex-app rename <old> <new> [--dry-run] [--json]
scitex-app copy <src> <dest> [--dry-run] [--json]
```

## Other CLI Commands

```bash
# Documentation
scitex-app docs --page quickstart
scitex-app docs --list

# MCP server
scitex-app mcp start
scitex-app mcp list-tools [-v]
scitex-app mcp doctor
scitex-app mcp installation

# Introspection
scitex-app list-python-apis [-v] [--json]
```

## Environment Variables

| Variable | Purpose |
|----------|---------|
| `SCITEX_BASE_DIR` | Base directory for app path resolution |
| `SCITEX_API_TOKEN` | JWT token for cloud API authentication |
| `SCITEX_API_URL` | Cloud API base URL (default: http://127.0.0.1:8000) |
| `SCITEX_SERVER_URL` | Server URL for app commands |
| `SCITEX_WORKING_DIR` | Working directory for standalone mode |
| `SCITEX_UI_STATIC` | Path to scitex-ui static files |
| `DJANGO_SECRET_KEY` | Django secret for standalone mode |
| `DJANGO_DEBUG` | Django debug mode (default: true) |
| `ANTHROPIC_API_KEY` | API key for chat backend |
| `LLM_MODEL` | LLM model for chat (default: claude-sonnet-4-20250514) |

## MCP Tools (for AI agents)

| Tool | Parameters | Purpose |
|------|-----------|---------|
| `app_scaffold` | `name`, `frontend` | Scaffold new app |
| `app_validate` | `path` | Validate app structure |
| `app_read_file` | `path`, `root`, `binary` | Read file content |
| `app_write_file` | `path`, `content`, `root` | Write file |
| `app_list_files` | `directory`, `root`, `extensions` | List directory |
| `app_file_exists` | `path`, `root` | Check file existence |
| `app_delete_file` | `path`, `root` | Delete file |
| `app_copy_file` | `src_path`, `dest_path`, `root` | Copy file |
| `app_rename_file` | `old_path`, `new_path`, `root` | Rename/move file |
