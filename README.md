<!-- ---
!-- Timestamp: 2026-03-13
!-- Author: ywatanabe
!-- File: /home/ywatanabe/proj/scitex-app/README.md
!-- --- -->

# SciTeX App (<code>scitex-app</code>)

<p align="center">
  <a href="https://scitex.ai">
    <img src="docs/scitex-logo-blue-cropped.png" alt="SciTeX" width="400">
  </a>
</p>

<p align="center"><b>Write-once interface for local + cloud SciTeX apps</b></p>

<p align="center">
  <a href="https://badge.fury.io/py/scitex-app"><img src="https://badge.fury.io/py/scitex-app.svg" alt="PyPI version"></a>
  <a href="https://scitex-app.readthedocs.io/"><img src="https://readthedocs.org/projects/scitex-app/badge/?version=latest" alt="Documentation"></a>
  <a href="https://github.com/ywatanabe1989/scitex-app/actions/workflows/test.yml"><img src="https://github.com/ywatanabe1989/scitex-app/actions/workflows/test.yml/badge.svg" alt="Tests"></a>
  <a href="https://www.gnu.org/licenses/agpl-3.0"><img src="https://img.shields.io/badge/License-AGPL--3.0-blue.svg" alt="License: AGPL-3.0"></a>
</p>

<p align="center">
  <a href="https://scitex-app.readthedocs.io/">Full Documentation</a> · <code>pip install scitex-app</code>
</p>

---

## Problem

SciTeX apps (like FigRecipe, Writer, Stats) need to work in three environments: standalone local (`pip install`), cloud (scitex.ai), and self-hosted. Today, each environment requires different file I/O code — `pathlib` locally, HTTP REST calls on cloud. This means maintaining two codebases or tightly coupling apps to one deployment mode.

## Solution

SciTeX App provides a **unified file storage SDK** with a single `FilesBackend` protocol. Apps call `get_files()` and get back a backend that works identically regardless of environment. Write your app once — it runs everywhere.

| Environment | Backend | How it works |
|-------------|---------|--------------|
| **Local** | `FileSystemBackend` | pathlib-based, zero dependencies |
| **Cloud** | `CloudFilesBackend` | HTTP REST via `SCITEX_API_TOKEN` (injected at runtime) |
| **Custom** | `register_backend()` | S3, GCS, or any storage you need |

<p align="center"><sub><b>Table 1.</b> Three deployment modes. The SDK auto-detects cloud when <code>SCITEX_API_TOKEN</code> is set; otherwise defaults to local filesystem.</sub></p>

### Seven Operations

Every backend implements the same 7-method protocol:

| Method | Description |
|--------|-------------|
| `read(path)` | Read file content (text or binary) |
| `write(path, content)` | Write content, creating parent dirs |
| `list(directory)` | List files with optional extension filter |
| `exists(path)` | Check if a file exists |
| `delete(path)` | Delete a file |
| `rename(old, new)` | Rename/move a file |
| `copy(src, dest)` | Copy a file |

<p align="center"><sub><b>Table 2.</b> The <code>FilesBackend</code> protocol. Uses <code>typing.Protocol</code> for structural subtyping — backends just implement the methods, no inheritance required.</sub></p>

## Installation

Requires Python >= 3.10. **Zero dependencies** — pure stdlib.

```bash
pip install scitex-app
```

> **SciTeX users**: `pip install scitex` already includes App SDK. Access via `scitex.app`.

## Quickstart

```python
from scitex_app.sdk import get_files

# Local filesystem (default)
files = get_files("./my_project")
content = files.read("config/settings.yaml")
files.write("output/result.csv", csv_text)

# List files with filter
yaml_files = files.list("config", extensions=[".yaml"])

# Cloud mode (auto-detected via SCITEX_API_TOKEN)
import os
os.environ["SCITEX_API_TOKEN"] = "your-token"
cloud_files = get_files()  # routes through cloud REST API
```

## Three Interfaces

<details>
<summary><strong>Python API</strong></summary>

<br>

```python
from scitex_app.sdk import get_files, register_backend, FilesBackend

files = get_files("./project")        # auto-detect backend
files.read("data.csv")                # read file
files.write("out.txt", "hello")       # write file
files.list(extensions=[".yaml"])       # list with filter
files.exists("config.yaml")           # check existence
files.delete("temp.txt")              # delete file
files.rename("old.txt", "new.txt")    # rename/move
files.copy("src.txt", "dst.txt")      # copy file
```

> **[Full API reference](https://scitex-app.readthedocs.io/)**

</details>

<details>
<summary><strong>CLI Commands</strong></summary>

<br>

```bash
scitex-app --help-recursive              # Show all commands
scitex-app read <path>                   # Read a file
scitex-app list [directory]              # List files
scitex-app exists <path>                 # Check existence
scitex-app list-python-apis              # List Python API tree
scitex-app mcp list-tools                # List MCP tools
```

> **[Full CLI reference](https://scitex-app.readthedocs.io/)**

</details>

<details>
<summary><strong>MCP Server — for AI Agents</strong></summary>

<br>

AI agents can read, write, and manage files through the unified SDK.

| Tool | Description |
|------|-------------|
| `app_read_file` | Read a file through the SDK backend |
| `app_write_file` | Write content to a file |
| `app_list_files` | List files in a directory |
| `app_file_exists` | Check if a file exists |
| `app_delete_file` | Delete a file |
| `app_copy_file` | Copy a file |
| `app_rename_file` | Rename/move a file |

<sub><b>Table 3.</b> Seven MCP tools mirroring the FilesBackend protocol. All tools accept JSON parameters and return JSON results.</sub>

```bash
scitex-app mcp start
```

> **[Full MCP specification](https://scitex-app.readthedocs.io/)**

</details>

## Part of SciTeX

App SDK is part of [**SciTeX**](https://scitex.ai). When used inside the SciTeX framework, the SDK is available via `scitex.app`:

```python
import scitex

# Access files through the unified SDK
files = scitex.app.get_files("./project")
content = files.read("recipes/scatter.yaml")
files.write("output/figure.png", png_bytes)
```

Apps built with `scitex-app` work in all three modes:
- **Standalone**: `pip install figrecipe` runs locally with filesystem backend
- **Cloud**: Deploy to scitex.ai — cloud backend injected automatically
- **Self-hosted**: Run your own instance with custom backends

The SciTeX ecosystem follows the Four Freedoms for researchers:

>Four Freedoms for Research
>
>0. The freedom to **run** your research anywhere — your machine, your terms.
>1. The freedom to **study** how every step works — from raw data to final manuscript.
>2. The freedom to **redistribute** your workflows, not just your papers.
>3. The freedom to **modify** any module and share improvements with the community.
>
>AGPL-3.0 — because research infrastructure deserves the same freedoms as the software it runs on.

---

<p align="center">
  <a href="https://scitex.ai" target="_blank"><img src="docs/scitex-icon-navy-inverted.png" alt="SciTeX" width="40"/></a>
</p>

<!-- EOF -->
