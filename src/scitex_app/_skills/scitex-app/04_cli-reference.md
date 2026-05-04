---
description: |
  [TOPIC] scitex-app CLI Reference
  [DETAILS] Top-level subcommands of `scitex-app` — app (init/validate/dev-install/submit), file, mcp, docs, skills, list-python-apis.
tags: [scitex-app-cli-reference]
---

# CLI Reference

`scitex-app` is the entry point installed by `pip install scitex-app`.

```text
scitex-app [OPTIONS] COMMAND [ARGS]...
```

## Top-level options

| Flag                 | Purpose                                              |
|----------------------|------------------------------------------------------|
| `-V / --version`     | Show the version and exit                            |
| `--help-recursive`   | Show help for all subcommands                        |
| `--json`             | Emit structured JSON output (where supported)        |
| `-h / --help`        | Show this message and exit                           |

## Configuration precedence

```
CLI flags  →  ./config.yaml  →  $SCITEX_APP_CONFIG
           →  ~/.scitex/app/config.yaml  →  built-in defaults
```

## App Development

| Command | Purpose                                                          |
|---------|------------------------------------------------------------------|
| `app`   | Create, validate, dev-install, and submit SciTeX apps            |

Common subcommands of `app`:

```bash
scitex-app app init <DIR> --name <name>      # scaffold layout
scitex-app app validate <DIR>                # manifest + minimal-app checks
scitex-app app dev-install <DIR> --server URL  # register w/ workspace
scitex-app app submit <DIR> --target prod    # ship to a SciTeX Cloud target
```

## File operations

| Command | Purpose                                                          |
|---------|------------------------------------------------------------------|
| `file`  | Read / write / list files via the registered Files SDK backend   |

```bash
scitex-app file put results/today.csv data.csv
scitex-app file get results/today.csv ./local.csv
scitex-app file list results/
```

## Integration

| Command            | Purpose                                              |
|--------------------|------------------------------------------------------|
| `mcp`              | MCP server management (start / stop / status)        |
| `list-python-apis` | List the public Python API tree                      |

## Documentation

| Command  | Purpose                                                    |
|----------|------------------------------------------------------------|
| `docs`   | View package documentation                                 |
| `skills` | View package skills (workflow-oriented guides)             |

## Examples

```bash
scitex-app --help-recursive | head -80
scitex-app app init . --name my_app
scitex-app app validate .
scitex-app app dev-install . --server http://127.0.0.1:8000
scitex-app app submit . --target prod
```

See `19c_cli.md` for the legacy CLI page and `10_app-lifecycle.md` for
the full lifecycle walkthrough.
