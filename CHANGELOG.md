# Changelog

All notable changes to `scitex-app` are documented here.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/);
versions follow [Semantic Versioning](https://semver.org/).

## [Unreleased]

## [0.5.0] - 2026-07-19

- fix(gui-launcher): `--force` now reclaims an **orphaned** instance of
  our own app — one still holding the port after dying without clearing
  its runtime state, and therefore invisible to `status()`. That is the
  exact case the flag exists for, and it was the one case it refused,
  then printed remedies that ignored `--force` entirely. A flag that
  names the fix and does not perform it is the same bug as an install
  hint that installs nothing. (scitex-writer finding, 2.31.0)

- fix(gui-launcher): ownership is proven from the holder's **argv**, not
  its process name. A `comm` of `python` names nothing and is shared by
  every Python server on the box — terminating on that evidence would
  terminate strangers.

- fix(gui-launcher): `port_holder` no longer reports "a process owned by
  another user" when the truth is "this `/proc` will not let us look".
  Our agent containers deny `/proc/<pid>/fd` even for a same-uid
  process, so the module built to prevent confident wrong answers was
  giving one. It now returns a validated `PortHolder` dataclass whose
  `status` is one of the declared `free` / `identified` / `unreadable`,
  and whose `ours` is three-valued (`True` / `False` / `None` = we could
  not look).

  **Breaking (public API):** `embed.gui_port_holder()` and
  `_gui_runtime.port_holder()` now return a `PortHolder` instead of
  `dict | None`. Callers checking `if holder is None` should use
  `if not holder.in_use`; `holder["pid"]` becomes `holder.pid`. Both
  gain an optional `package` argument that populates `ours`.

  The holder-identification path is proven against real listening
  sockets on a host; inside our containers those tests **skip**, because
  `/proc/<pid>/fd` is unreadable there. Stated rather than papered over
  — claiming a green we did not get is the failure mode this change
  exists to fix.

## [0.4.2] - 2026-07-13

- chore: consolidate optional-dependencies into a single `[all]` extra
  (operator directive, prompted by scitex-writer PR #322). Extras are
  now all-or-nothing — `chat`/`chat-all`/`cli`/`cloud`/`django`/`mcp`
  collapse into one `[all]`; `dev`/`docs` stay separate (those are for
  building the package, not using it). `cli = []` was already empty
  (click/rich moved to base `dependencies` earlier) — an install hint
  that resolves to a no-op looks like a fix but installs nothing, and
  the user believes they already tried it. Every install-this-extra
  hint (formerly naming `mcp` or `cli`) across the CLI, skill docs, and
  sphinx docs now points at `all`. Added `tests/develop/test_extras.py`,
  which reads the real `pyproject.toml` and fails if any extra is
  empty or any referenced extra name is missing/empty.
  (#54)

## [0.4.1] - 2026-07-13

- fix(gui-runtime): `_gui_runtime.state_path(package)` now honors a
  `SCITEX_<PACKAGE>_GUI_STATE` env override before falling back to the
  `scitex_config` resolution, matching scitex-writer's pre-existing
  `SCITEX_WRITER_GUI_STATE` convention (dropped during the 0.4.0
  generalization from writer PR #316). This repo bans mocks/
  monkeypatch, so the env var is the only channel available to a
  subprocess-driven end-to-end CLI test (`gui serve` run as a real
  subprocess) — without it, such a test writes to the developer's
  actual runtime state instead of a temp file. (#51)

## [0.4.0] - 2026-07-13

- feat: add `scitex_app.embed`, a public host-embedding API. 3+ consumers
  (figrecipe, writer, scitex-todo) were reaching into the private
  `scitex_app._django` / `scitex_app._standalone` modules for
  host-embedding, including one hard top-level import. Root cause was
  our own skill docs and app-scaffold templates teaching that private
  import pattern to every consumer; both now reference
  `scitex_app.embed`, so newly scaffolded apps stop reproducing it.
  `scitex_app.chat`'s own docstrings and docs/APP_SDK.md are also fixed
  — `from scitex_app.chat import X` raises `ModuleNotFoundError` because
  `chat` is a lazy `__getattr__` attribute, not a real submodule; the
  working form is `from scitex_app import chat` then `chat.X`. (#48)
- feat: add a shared GUI launcher (`scitex_app.embed.serve_gui` +
  `scitex_app._gui_runtime`), generalized from scitex-writer's `gui
  serve` runtime module (writer PR #316). Binds the exact port or fails
  loud (never drifts to the next free port), refuses a second instance
  via runtime state (self-healing a stale recorded pid), identifies a
  foreign port holder via `/proc` (no `ss`/`lsof` shell-out), and
  `--force` only ever stops the instance recorded in its own runtime
  state — never a process it does not own. Scaffolded apps' `gui
  --force` no longer blind-kills whatever holds the port via `fuser -k`.
  `scitex-config` is now a real (non-dev) dependency. (#49)

## [0.3.0] - 2026-07-12

- feat(validator): forbid a hand-written `version` in `manifest.json`;
  require `pip_package` (the dist name) instead. The app version is now
  the SINGLE SOURCE OF TRUTH of the installed pip package, read at
  runtime via `importlib.metadata`. A manifest `version` inevitably
  drifts from the package (2026-07 incident: manifests stuck at
  `0.14.0` while packages shipped `2.25.0` / `0.29.9` / `1.4.2`, so
  every app tile in scitex-hub showed a wrong version). Both validators
  (`scitex_app.validator.AppValidator` and
  `scitex_app.appmaker._validate`) drop `version` from their
  required-field lists, add `pip_package`, and emit an error when a
  `version` key is present. The scaffold now generates `pip_package`
  instead of `version`, and the manifest schema doc documents the rule.
  **Breaking:** existing manifests that declare `version` must remove it
  and add `pip_package`. (#47)

## [0.2.10] - 2026-06-14

(Version 0.2.9 was claimed by an earlier orphan tag on 2026-06-03 that
never published to PyPI; jumping to 0.2.10 to avoid the conflict.)

- fix(appmaker): emit nested-package layout (`<wrapper>/<name>/`) + add
  `[tool.hatch.build.targets.wheel] packages = ["<name>"]` block to
  generated `pyproject.toml`. Pre-fix the scaffold emitted a FLAT layout
  that hatchling refused to package — every `pip install --no-deps
  --target=<dir> <gitea-archive-url>` from the hub then failed with
  "Unable to determine which files to ship inside the wheel". Port of
  scitex-cloud PR #293 M4 done-gate. New test gate
  (`tests/scitex_app/appmaker/test__scaffold.py`, 36 cases, no mocks,
  incl. real `pip install` into a fresh venv) prevents regression. (#35)

## [0.2.8] - 2026-05-26

- test: de-mock + fix test quality; fix fastmcp call-tool API drift
- ci(docs): make _sphinx_html commit-back step non-fatal
- ci: normalize codecov.yml to canonical shape
- ci(quality): replace broken ecosystem-clone template with single-package audit-all
- ci(codecov): disable PR comments to stop email noise
- tests: PA-307 TQ001/TQ002/TQ003/TQ007 mechanical cleanup
- fix: NL001 PEP 515 underscore separators for integer literals
- fix(docs): suppress Sphinx docstring RST issues and duplicate FilesBackend warning

## [0.2.7] - 2026-05-26

- fix(workflows): resync integrated release pipeline from scitex-dev v0.11.20
- fix(workflows): standardize to scitex-dev canonical set
- ci+docs: normalize workflow filenames + README badges (PS-164)
- quality: subprocess coverage + dev extras + audit gate + flat file-ops API
- docs(readme): recommend uv pip install <pkg>[all] (faster resolver)
- ci(release): sync publish-pypi.yml fix from ecosystem
- release(deps): bump 0.2.6 -> 0.2.7; auto-publish on tag push

## [0.2.6]

- Initial CHANGELOG entry — see git log for prior history.
