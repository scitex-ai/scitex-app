---
description: |
  [TOPIC] CLI Reference
  [DETAILS] scitex-app CLI — file operations, app lifecycle (init/validate/dev-install/submit), MCP server, and Python API introspection..
tags: [scitex-app-cli]
---

# CLI Reference

Entry point: `scitex-app` (installed via `pip install scitex-app`)

`click` and `rich` are base dependencies, always installed. For chat/cloud/django/mcp features: `pip install scitex-app[all]`.

```
Usage: scitex-app [OPTIONS] COMMAND [ARGS]...

  SciTeX App SDK — write-once interface for local + cloud apps.

Options:
  --version          Show version and exit.
  --help-recursive   Show help for all subcommands.
  -h, --help         Show this message and exit.
```

## App Development

### app init

```bash
scitex-app app init [TARGET_DIR] [OPTIONS]
```

Scaffold a complete SciTeX app.

| Option | Default | Purpose |
|--------|---------|---------|
| `--name`, `-n` | directory name | Python module name (must end with `_app`) |
| `--label`, `-l` | derived from name | Human-readable label |
| `--icon`, `-i` | `fas fa-puzzle-piece` | Font Awesome icon class |
| `--description`, `-d` | `""` | Short description |
| `--frontend`, `-f` | `html` | Frontend type: `html` or `react` |
| `--overwrite` | false | Overwrite existing files |

```bash
scitex-app app init .
scitex-app app init /path/to/my_app --name my_awesome_app
scitex-app app init . -n demo_app -l "Demo" -i "fas fa-flask"
scitex-app app init . --frontend react
```

Name is auto-suffixed with `_app` if missing.

### app validate

```bash
scitex-app app validate [APP_DIR]
```

Validate app for submission readiness. Exits 0 on pass, 1 on failure.

```bash
scitex-app app validate .
scitex-app app validate /path/to/my_app
```

### app install-dev

```bash
scitex-app app install-dev [APP_DIR] [OPTIONS]
```

Validate locally, then call the SciTeX Cloud install-dev API. App appears in workspace sidebar immediately.

| Option | Default | Env var | Purpose |
|--------|---------|---------|---------|
| `--server`, `-s` | `http://127.0.0.1:8000` | `SCITEX_SERVER_URL` | Server URL |
| `--token`, `-t` | — | `SCITEX_API_TOKEN` | JWT access token (required) |
| `--owner`, `-o` | auto-detected | — | Gitea username |
| `--repo`, `-r` | from manifest | — | Gitea repo name |

```bash
scitex-app app install-dev .
scitex-app app install-dev . --server http://my-server:8000
```

### app submit

```bash
scitex-app app submit [APP_DIR] [OPTIONS]
```

Submit app for review and public listing. Opens a PR on scitex-apps registry.

| Option | Default | Env var | Purpose |
|--------|---------|---------|---------|
| `--server`, `-s` | `http://127.0.0.1:8000` | `SCITEX_SERVER_URL` | Server URL |
| `--token`, `-t` | — | `SCITEX_API_TOKEN` | JWT token (required) |

```bash
scitex-app app submit .
scitex-app app submit /path/to/my_app --server https://scitex.example.com
```

## File Operations

All file commands are under the `file` subgroup and accept `--root` (default `.`) and `--json` for machine-readable output.

```bash
scitex-app file read <path> [--root DIR] [--binary] [--json]
scitex-app file write <path> [CONTENT] [--root DIR] [--stdin] [--json] [--dry-run]
scitex-app file list [DIRECTORY] [--root DIR] [--ext EXT]... [--json]
scitex-app file exists <path> [--root DIR] [--json]
scitex-app file delete <path> [--root DIR] [--json] [--dry-run]
scitex-app file rename <old-path> <new-path> [--root DIR] [--json] [--dry-run]
scitex-app file copy <src-path> <dest-path> [--root DIR] [--json] [--dry-run]
```

```bash
# Read a file
scitex-app file read config.yaml
scitex-app file read data.bin --binary

# Write content
scitex-app file write output.txt "hello world"
echo "data" | scitex-app file write output.txt --stdin
scitex-app file write output.txt "test" --dry-run

# List files
scitex-app file list
scitex-app file list data --ext .yaml --ext .json
scitex-app file list --json

# Check existence (exit code 0=exists, 1=missing)
scitex-app file exists config.yaml

# Delete, rename, copy with dry-run preview
scitex-app file delete temp.txt --dry-run
scitex-app file rename old.txt new.txt
scitex-app file copy src.txt dst.txt --dry-run
```

## Integration

### MCP Server

```bash
scitex-app mcp start             # Start MCP server (stdio transport)
scitex-app mcp list-tools        # List available MCP tools
scitex-app mcp list-tools -v     # Verbose with parameter descriptions
scitex-app mcp doctor            # Check MCP configuration health
scitex-app mcp installation      # Show installation instructions
```

### Python API Introspection

```bash
scitex-app list-python-apis              # List all public Python APIs
scitex-app list-python-apis -v           # Verbose with signatures
scitex-app list-python-apis --json       # Machine-readable JSON
```

## Documentation and Skills

```bash
scitex-app docs list             # List available documentation pages
scitex-app docs get <page>       # Show a documentation page
scitex-app skills list           # List skill pages
scitex-app skills get <skill>    # Show a skill page
```

Requires `scitex-dev`: `pip install scitex-dev`
