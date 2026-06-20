"""`scitex-app skills` — list / get / install agent-facing skills.

Self-contained. No scitex-dev runtime dep — walks the package's own
`_skills/scitex-app/` directory directly.
"""

from __future__ import annotations

import os as _os
import shutil as _shutil
from pathlib import Path

import click

PKG = "scitex-app"
_PKG_SHORT = "app"  # scitex-app → app (prefix-stripping rule)


# ---------------------------------------------------------------------------
# Path resolution — always via helper, never hardcoded
# ---------------------------------------------------------------------------


def _scitex_dir() -> Path:
    """Return the ecosystem-wide user-scope root.

    Respects ``$SCITEX_DIR`` for relocation (default ``~/.scitex``).
    """
    return Path(_os.environ.get("SCITEX_DIR", Path.home() / ".scitex"))


def _default_skills_base() -> Path:
    """Resolve the default parent directory for skills installation.

    Returns ``<SCITEX_DIR>/app/runtime/skills/`` — inside the package's
    own namespace (``app``), under the runtime tree, so it honours
    ``$SCITEX_DIR`` and the ecosystem state-directory conventions.
    """
    return _scitex_dir() / _PKG_SHORT / "runtime" / "skills"


def _legacy_skills_dir() -> Path:
    """Return the legacy cross-package skills path for back-compat."""
    return _scitex_dir() / "dev" / "skills" / PKG


def _migrate_legacy_skills(target: Path) -> None:
    """Migrate skills from the legacy ``~/.scitex/dev/skills/scitex-app/`` path.

    If the legacy directory exists, move its contents to *target* and
    emit a one-time deprecation warning.  The legacy read-path is kept
    for one minor version (per local-state-directives §8).
    """
    legacy = _legacy_skills_dir()
    if not legacy.is_dir():
        return
    # target parent already exists (caller ensures it)
    click.echo(
        f"warning: migrating skills from {legacy} to {target} "
        f"(legacy location deprecated — will be removed in a future release).",
        err=True,
    )
    for child in legacy.iterdir():
        dest = target / child.name
        if not dest.exists():
            _shutil.move(str(child), str(dest))
    # remove the now-empty legacy directory
    try:
        legacy.rmdir()
    except OSError:
        pass  # not empty — skip, next install will finish migration


# ---------------------------------------------------------------------------
# Skill source (bundled in the wheel)
# ---------------------------------------------------------------------------


def _skills_root() -> Path:
    """Resolve the bundled ``_skills/scitex-app/`` directory."""
    import scitex_app

    pkg_dir = Path(scitex_app.__file__).parent
    return pkg_dir / "_skills" / PKG


def _list_skill_files(root: Path) -> list[Path]:
    """All ``.md`` files under ``_skills/scitex-app/`` (recursive), excluding SKILL.md."""
    if not root.is_dir():
        return []
    return sorted(p for p in root.rglob("*.md") if p.is_file() and p.name != "SKILL.md")


# ---------------------------------------------------------------------------
# CLI commands
# ---------------------------------------------------------------------------


@click.group(name="skills", invoke_without_command=True)
@click.pass_context
def skills_group(ctx) -> None:
    """Agent-facing skills bundled with scitex-app.

    \b
    Examples:
      $ scitex-app skills list
      $ scitex-app skills get 01_installation
      $ scitex-app skills install                # → ~/.scitex/app/runtime/skills/scitex-app/
      $ scitex-app skills install --claude-symlink
    """
    if ctx.invoked_subcommand is None:
        click.echo(ctx.get_help())


@skills_group.command(name="list")
@click.option("--json", "as_json", is_flag=True, help="Emit machine-readable JSON.")
def skills_list(as_json: bool) -> None:
    """List skill files bundled with this package.

    \b
    Example:
      $ scitex-app skills list
      $ scitex-app skills list --json
    """
    root = _skills_root()
    files = _list_skill_files(root)
    if as_json:
        import json as _json

        click.echo(
            _json.dumps(
                [{"name": p.stem, "path": str(p)} for p in files],
                indent=2,
            )
        )
        return
    if not files:
        click.echo(f"no skills found at {root}", err=True)
        raise SystemExit(1)
    for p in files:
        rel = p.relative_to(root)
        click.echo(f"{p.stem:36s}  {rel}")


@skills_group.command(name="get")
@click.argument("name")
@click.option("--json", "as_json", is_flag=True, help="Emit machine-readable JSON.")
def skills_get(name: str, as_json: bool) -> None:
    """Print the contents of a skill file by NAME (e.g. ``01_installation``).

    \b
    Example:
      $ scitex-app skills get 01_installation
      $ scitex-app skills get 02_quick-start --json
    """
    root = _skills_root()
    target_stem = name[:-3] if name.endswith(".md") else name
    match = next((p for p in _list_skill_files(root) if p.stem == target_stem), None)
    if match is None:
        click.echo(f"skill not found: {name}", err=True)
        available = ", ".join(p.stem for p in _list_skill_files(root)[:8])
        click.echo(f"available: {available}…", err=True)
        raise SystemExit(1)
    if as_json:
        import json as _json

        click.echo(
            _json.dumps(
                {
                    "name": match.stem,
                    "path": str(match),
                    "content": match.read_text(encoding="utf-8"),
                },
                indent=2,
            )
        )
        return
    click.echo(match.read_text(encoding="utf-8"))


@skills_group.command(name="install")
@click.option(
    "--dest",
    type=click.Path(),
    default=None,
    help=(
        "Destination parent dir (default: ~/.scitex/app/runtime/skills/scitex-app/)."
    ),
)
@click.option(
    "--no-link",
    "no_link",
    is_flag=True,
    help="Copy files instead of symlinking. Default is symlink.",
)
@click.option(
    "--claude-symlink",
    is_flag=True,
    help="Also expose at ~/.claude/skills/scitex/ for Claude Code consumers.",
)
@click.option("--dry-run", is_flag=True, help="Preview without copying/linking.")
@click.option("--yes", "-y", is_flag=True, help="Skip confirmation prompt.")
def skills_install(
    dest: str | None,
    no_link: bool,
    claude_symlink: bool,
    dry_run: bool,
    yes: bool,
) -> None:
    """Install this package's skills into a target directory.

    \b
    Default: symlink the entire ``_skills/scitex-app/`` dir to
    ``~/.scitex/app/runtime/skills/scitex-app/`` so add/rename/delete
    in source propagates immediately.  Respects ``$SCITEX_DIR`` for
    ecosystem-wide relocation.

    \b
    Example:
      $ scitex-app skills install
      $ scitex-app skills install --claude-symlink
      $ scitex-app skills install --no-link --dest /tmp/scitex-app-skills
    """
    del yes  # accepted for §2 compliance; install is non-interactive
    src = _skills_root().resolve()
    if not src.is_dir():
        click.echo(f"no skills directory at {src}", err=True)
        raise SystemExit(1)

    base = Path(dest).expanduser() if dest else _default_skills_base()
    target = base / PKG

    if dry_run:
        action = "copy" if no_link else "symlink"
        click.echo(f"would {action} {src} -> {target}")
        if claude_symlink:
            claude_link = Path.home() / ".claude" / "skills" / "scitex"
            click.echo(f"would symlink {claude_link} -> {base}")
        return

    base.mkdir(parents=True, exist_ok=True)

    # Back-compat: migrate from legacy ~/.scitex/dev/skills/scitex-app/
    if dest is None:
        _migrate_legacy_skills(target.parent)

    if target.is_symlink() or target.is_file():
        target.unlink()
    elif target.is_dir():
        _shutil.rmtree(target)

    if no_link:
        _shutil.copytree(src, target)
        click.echo(f"copied {src} -> {target}")
    else:
        _os.symlink(src, target, target_is_directory=True)
        click.echo(f"linked {target} -> {src}")

    if claude_symlink:
        claude_link = Path.home() / ".claude" / "skills" / "scitex"
        claude_link.parent.mkdir(parents=True, exist_ok=True)
        if claude_link.is_symlink():
            claude_link.unlink()
        if not claude_link.exists():
            _os.symlink(base.resolve(), claude_link, target_is_directory=True)
            click.echo(f"linked {claude_link} -> {base}")
        else:
            click.echo(
                f"warning: {claude_link} exists and is not a symlink - skipping",
                err=True,
            )
