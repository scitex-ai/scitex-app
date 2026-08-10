# Changelog

All notable changes to `scitex-app` are documented here.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/);
versions follow [Semantic Versioning](https://semver.org/).

## [Unreleased]

## [0.6.1] - 2026-08-05

- **fix(gui-launcher): `--force` could SIGTERM an unrelated process.**
  `argv_is_ours()` scanned the whole argv including `argv[0]` — the
  *interpreter* path. A project-local venv puts the project name in that path,
  so `/home/x/<project>/.venv/bin/python` claimed **every** process started
  from that venv as ours: a test run, a jupyter kernel, an unrelated dev
  server. Since `serve_gui(--force)` terminates on `holder.ours`, the flag
  could kill a stranger whose only connection to us was the directory its
  interpreter happened to live under — precisely the failure `--force` exists
  to avoid.

  0.5.0's own note claimed ownership "is proven from the holder's argv, not
  its name". The proof was weaker than the sentence: the documented
  counter-example (`myscitex_writerx` does not match) is about **token
  boundaries** and said nothing about **path segments**.

  `argv[0]` now contributes only its last two path components — the program
  and the directory immediately containing it. One level up is what a program
  *is*; three levels up is only where it lives. Everything after `argv[0]` is
  matched whole, so module paths still count:

  | argv[0] | verdict |
  |---|---|
  | `/opt/venv/…/scitex_writer/__main__.py` | ours — parent names it |
  | `/usr/local/bin/scitex-writer-gui` | ours — script names it |
  | `/home/x/<project>/.venv/bin/python` | **not** ours |
  | `/home/x/<project>/.venv/bin/jupyter` | **not** ours |

  All four are pinned by tests, so the boundary cannot drift silently in
  either direction. Reported by scitex-scholar with a deterministic
  reproduction in which only `argv[0]` differed.

  Known residual, documented in the docstring rather than left implied: a
  stranger run as `python /home/x/<package>/run.py` still matches, because a
  script living inside the package tree is real argv evidence.

## [0.6.0] - 2026-08-05

- **security(paths): caller-supplied path components are now validated and
  contained.** `scitex_app.paths` joined `owner` / `repo` / `slug` straight
  onto a filesystem root with no validation and no containment check. On the
  hub these were not exploitable for traversal only because Django's `<str:>`
  URL converter excludes `/` — a property of the **routing layer**, not of
  this module. Every other consumer lost that: a CLI caller, a service
  embedding the package, or a future `<path:>` route on the hub itself, which
  would have silently re-opened it. A guard that holds only because of what
  some caller upstream happens to do is not a guard.

  Measured before the fix: **3 of 14** behaviours safe. Cross-tenant reach was
  real, not theoretical — `owner="alice"`, `repo="../../bob/proj/bobrepo"`
  returned bob's actual project directory. An absolute component escaped the
  base directory entirely, because `Path("/a/b") / "/c"` is `Path("/c")`:
  pathlib silently discards the root. After: **14 of 14**.

  Both checks are required and neither substitutes for the other. Per-segment
  validation alone misses a symlink planted inside the root; containment alone
  misses cross-tenant reach, because `owner="alice/../bob"` lands on a
  directory that is still *inside* the base dir.

  Fixed across the whole family, not just the two functions first reported:
  `resolve_user_project_dir`, `resolve_published_project_dir` (identical
  defect on `slug`), `parse_dev_module_name`, `resolve_manifest`,
  `resolve_template_dir`, `resolve_static_dir`, and `find_partial_template`
  (whose caller-supplied `filename` was never validated — a traversal filename
  read any file on the host).

  **Not a breaking change for correct callers.** A refusal returns `None`,
  which is the module's existing "not found" answer, so a probe stays a 404
  rather than becoming a 500. Refusals are logged with `%r`, so a hostile name
  cannot inject control characters into your logs. Package-side half of
  scitex-hub #527.

- **Breaking (install surface): `dev` and `docs` are PEP 735 dependency
  groups, not extras.** Requesting either as a bracketed extra no longer
  resolves; use `pip install -e . --group dev` (pip ≥ 25.1), or `--group
  docs` to build the documentation. `[all]` is unchanged and remains the only
  public extra.

  This keeps the build toolchain out of the user-facing install: `[all]` must
  give every runtime capability and no pytest, ruff or sphinx. Groups are not
  `[project.optional-dependencies]`, so the closure rule that would otherwise
  force the toolchain into `[all]` no longer applies to them.

  If you install the toolchain with an unknown extra, note that pip **warns
  and still exits 0** — so a `pip install -e ".[dev]" || fallback` chain will
  never reach its fallback and will silently install nothing. Request groups
  with `--group`, which fails loudly on a tool that does not support them.

- deprecate(chat): `LLM_MODEL` is renamed to `SCITEX_APP_LLM_MODEL`. The old
  name still works and logs a deprecation warning; it is aliased rather than
  renamed because it was a published, documented contract. If both are set the
  prefixed one wins **and the conflict is logged** — the pick is never silent.
  The unprefixed name is being retired because it is generic enough to collide
  with another tool in the same environment, which would quietly change which
  model you talk to.

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
