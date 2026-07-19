---
description: |
  [TOPIC] Standalone Mode
  [DETAILS] run_standalone() — launch a SciTeX app locally with the full workspace shell (Django + sidebar + file tree + AI panel) without scitex-hub..
tags: [scitex-app-standalone]
---

# Standalone Mode

`scitex_app.embed.run_standalone()` launches any SciTeX app locally with the full workspace shell — same UX as scitex-hub, no server required.

`embed` is the public host-embedding surface (`scitex_app.embed`) — import from there, not from the private `scitex_app._standalone` / `scitex_app._django` implementation modules.

## run_standalone()

```python
def run_standalone(
    app_module: str,
    port: int = 8050,
    host: str = "127.0.0.1",
    open_browser: bool = True,
    hot_reload: bool = False,
    working_dir: Optional[str] = None,
    desktop: bool = False,
    extra_installed_apps: Optional[list[str]] = None,
    extra_staticfiles_dirs: Optional[list[str]] = None,
    extra_env: Optional[dict[str, str]] = None,
) -> None
```

### Parameters

| Parameter | Default | Purpose |
|-----------|---------|---------|
| `app_module` | required | Dotted path to the app's Django module (e.g. `"my_app"`) |
| `port` | `8050` | TCP port for the Django server |
| `host` | `"127.0.0.1"` | Host to bind (use `"0.0.0.0"` for LAN access) |
| `open_browser` | `True` | Open browser tab automatically after 1.5 s |
| `hot_reload` | `False` | Enable Django `--reload` (file watching) |
| `working_dir` | `None` | Sets `SCITEX_WORKING_DIR`; defaults to `cwd` |
| `desktop` | `False` | Launch as native window via `pywebview` if installed |
| `extra_installed_apps` | `None` | Additional Django app strings to add to `INSTALLED_APPS` |
| `extra_staticfiles_dirs` | `None` | Additional static file directories |
| `extra_env` | `None` | Extra env vars to set before Django configures |

### Basic usage

```python
from scitex_app.embed import run_standalone

# Minimal — app at my_app/urls.py, my_app/views.py, etc.
run_standalone(app_module="my_app")

# Custom port, no browser
run_standalone(app_module="my_app", port=8051, open_browser=False)

# Native desktop window (requires: pip install pywebview)
run_standalone(app_module="my_app", desktop=True)
```

### From a scaffolded app's CLI

Apps created with `scitex-app app init` get a `_cli.py` with a `gui` command:

```bash
my-app gui                           # default port 8050
my-app gui --port 8051 --no-browser
my-app gui --force                   # stop THIS app's own previous instance, then serve
```

The `gui` command uses `scitex_app.embed.serve_gui`: it binds exactly
`--port` or fails loud (never drifts to the next free port), and refuses
a second instance of this app's own GUI unless `--force` is given.

`--force` stops this app's own GUI whether it is *recorded* in the
runtime state or *orphaned* — still holding the port after dying without
clearing that state, which is exactly the case the flag exists for.
It never touches a process it cannot prove is ours, and ownership is
proven from the holder's **argv**, not its name: a `comm` of `python`
is shared by every Python server on the box.

For a foreign holder it prints the name, pid and argv with a `kill`
command, and never offers `--force` — a remedy that would refuse.
When the port is held but the holder cannot be identified (our agent
containers deny `/proc/<pid>/fd` even for our own processes), it says
so plainly rather than blaming another user. The three outcomes are
declared on `PortHolder.status`: `free`, `identified`, `unreadable`;
`ours` is three-valued — `True`, `False`, or `None` for "we could not
look".

### Django settings configured

`run_standalone()` calls `django.conf.settings.configure()` with:

- `INSTALLED_APPS`: `django.contrib.staticfiles`, `<app_module>`, `scitex_ui` (if installed)
- `ROOT_URLCONF`: `<app_module>.urls`
- `STATIC_URL`: `/static/`
- `STATICFILES_DIRS`: app's own `static/` + `_standalone_static/` shell assets
- `DATABASES`: `{}` (no DB required for read-only apps)
- `SECRET_KEY`: from `DJANGO_SECRET_KEY` env or `"scitex-standalone-dev-key"`
- `DEBUG`: from `DJANGO_DEBUG` env (default `"true"`)

Settings configure only once — calling `run_standalone()` a second time is a no-op if Django is already configured.

### Requirements

- `django` (always required)
- `scitex_ui` (optional, provides the workspace shell sidebar/panel)
- `pywebview` (optional, only for `desktop=True`)

### Testing the `gui` command's real CLI path

`serve_gui`'s state-file location can be redirected with an env var --
the only channel available to a subprocess-driven end-to-end test
(`python -m my_app gui serve` run as a real subprocess), which cannot
inject a path via function arguments across a process boundary. Set
`SCITEX_<PACKAGE>_GUI_STATE` (package name uppercased, non-alnum chars
-> `_`, e.g. `SCITEX_MY_APP_GUI_STATE` for `"my-app"`) before spawning
the subprocess to point state at a tmp path instead of the developer's
real runtime state -- keeps end-to-end CLI tests mock-free.
