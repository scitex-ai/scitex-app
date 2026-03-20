#!/usr/bin/env python3
# Timestamp: 2026-03-13
# File: scitex_app/_cli/_main.py

"""Main CLI entry point for scitex-app."""

import sys

try:
    import click
except ImportError:

    def main(argv=None):
        print(
            "ERROR: click is not installed. Install with: pip install scitex-app[cli]",
            file=sys.stderr,
        )
        raise SystemExit(1)

else:
    from ._introspect import list_python_apis
    from ._mcp import mcp

    CONTEXT_SETTINGS = {"help_option_names": ["-h", "--help"]}

    COMMAND_CATEGORIES = [
        ("App Development", ["app"]),
        ("Files", ["read", "write", "list", "exists", "delete", "rename", "copy"]),
        ("Integration", ["mcp", "list-python-apis"]),
        ("Documentation", ["docs", "skills"]),
    ]

    class CategorizedGroup(click.Group):
        """Custom Click group that displays commands organized by category."""

        def format_commands(self, ctx, formatter):
            commands = {}
            for subcommand in self.list_commands(ctx):
                cmd = self.get_command(ctx, subcommand)
                if cmd is not None and not cmd.hidden:
                    commands[subcommand] = cmd

            if not commands:
                return

            displayed = set()

            for category_name, category_commands in COMMAND_CATEGORIES:
                category_items = []
                for name in category_commands:
                    if name in commands and name not in displayed:
                        cmd = commands[name]
                        help_text = cmd.get_short_help_str(limit=formatter.width)
                        category_items.append((name, help_text))
                        displayed.add(name)

                if category_items:
                    with formatter.section(category_name):
                        formatter.write_dl(category_items)

            uncategorized = [
                (name, commands[name].get_short_help_str(limit=formatter.width))
                for name in sorted(commands.keys())
                if name not in displayed
            ]
            if uncategorized:
                with formatter.section("Other"):
                    formatter.write_dl(uncategorized)

    def _show_recursive_help(ctx: click.Context) -> None:
        """Recursively show help for all commands."""
        click.echo(ctx.get_help())
        click.echo()
        group = ctx.command
        if isinstance(group, click.Group):
            for name in sorted(group.list_commands(ctx)):
                cmd = group.get_command(ctx, name)
                sub_ctx = click.Context(cmd, parent=ctx, info_name=name)
                click.echo(f"{'=' * 60}")
                click.echo(f"Command: {name}")
                click.echo(f"{'=' * 60}")
                click.echo(sub_ctx.get_help())
                click.echo()
                if isinstance(cmd, click.Group):
                    for sub_name in sorted(cmd.list_commands(sub_ctx)):
                        sub_cmd = cmd.get_command(sub_ctx, sub_name)
                        sub_sub_ctx = click.Context(
                            sub_cmd, parent=sub_ctx, info_name=sub_name
                        )
                        click.echo(f"  {'─' * 56}")
                        click.echo(f"  Subcommand: {name} {sub_name}")
                        click.echo(f"  {'─' * 56}")
                        click.echo(sub_sub_ctx.get_help())
                        click.echo()

    def _get_version() -> str:
        """Read version from importlib.metadata."""
        try:
            from importlib.metadata import version

            return version("scitex-app")
        except Exception:
            return "0.0.0"

    @click.group(
        cls=CategorizedGroup,
        context_settings=CONTEXT_SETTINGS,
        invoke_without_command=True,
    )
    @click.version_option(version=_get_version(), prog_name="scitex-app")
    @click.option(
        "--help-recursive", is_flag=True, help="Show help for all subcommands."
    )
    @click.pass_context
    def main(ctx, help_recursive):
        """SciTeX App SDK — write-once interface for local + cloud apps."""
        if help_recursive:
            _show_recursive_help(ctx)
            ctx.exit(0)
        elif ctx.invoked_subcommand is None:
            click.echo(ctx.get_help())

    # -- File commands -------------------------------------------------------
    @main.command()
    @click.argument("path")
    @click.option("--root", default=".", help="Root directory for file backend.")
    @click.option("--binary", is_flag=True, help="Read as binary.")
    @click.option("--json", "as_json", is_flag=True, help="Output as JSON.")
    def read(path, root, binary, as_json):
        """Read a file through the SDK backend.

        Examples:
            scitex-app read config.yaml
            scitex-app read data.bin --binary
            scitex-app read config.yaml --json
        """
        import json as json_mod

        from scitex_app.sdk import get_files

        files = get_files(root)
        content = files.read(path, binary=binary)
        if as_json:
            import base64

            val = base64.b64encode(content).decode("ascii") if binary else content
            click.echo(json_mod.dumps({"path": path, "content": val, "binary": binary}))
        elif binary:
            sys.stdout.buffer.write(content)
        else:
            click.echo(content)

    @main.command()
    @click.argument("path")
    @click.argument("content", required=False, default=None)
    @click.option("--root", default=".", help="Root directory for file backend.")
    @click.option(
        "--stdin", "from_stdin", is_flag=True, help="Read content from stdin."
    )
    @click.option("--json", "as_json", is_flag=True, help="Output as JSON.")
    @click.option(
        "--dry-run", is_flag=True, help="Show what would be written without writing."
    )
    def write(path, content, root, from_stdin, as_json, dry_run):
        """Write content to a file through the SDK backend.

        Examples:
            scitex-app write output.txt "hello world"
            echo "data" | scitex-app write output.txt --stdin
            scitex-app write output.txt "test" --dry-run
        """
        import json as json_mod

        from scitex_app.sdk import get_files

        if from_stdin:
            content = sys.stdin.read()
        if content is None:
            raise click.UsageError("Provide CONTENT argument or use --stdin.")
        if dry_run:
            result = {
                "action": "write",
                "path": path,
                "size": len(content),
                "dry_run": True,
            }
            if as_json:
                click.echo(json_mod.dumps(result))
            else:
                click.echo(f"[dry-run] Would write {len(content)} bytes to {path}")
            return
        files = get_files(root)
        files.write(path, content)
        if as_json:
            click.echo(
                json_mod.dumps({"path": path, "size": len(content), "written": True})
            )
        else:
            click.echo(f"Written {len(content)} bytes to {path}")

    @main.command("list")
    @click.argument("directory", default="")
    @click.option("--root", default=".", help="Root directory for file backend.")
    @click.option("--ext", multiple=True, help="Filter by extension (e.g., .yaml).")
    @click.option("--json", "as_json", is_flag=True, help="Output as JSON.")
    def list_files(directory, root, ext, as_json):
        """List files in a directory through the SDK backend.

        Examples:
            scitex-app list
            scitex-app list data --ext .yaml
            scitex-app list --json
        """
        import json as json_mod

        from scitex_app.sdk import get_files

        files = get_files(root)
        extensions = list(ext) if ext else None
        result = files.list(directory, extensions=extensions)
        if as_json:
            click.echo(json_mod.dumps({"directory": directory, "files": result}))
        else:
            for p in result:
                click.echo(p)

    @main.command()
    @click.argument("path")
    @click.option("--root", default=".", help="Root directory for file backend.")
    @click.option("--json", "as_json", is_flag=True, help="Output as JSON.")
    def exists(path, root, as_json):
        """Check if a file exists through the SDK backend.

        Examples:
            scitex-app exists config.yaml
            scitex-app exists config.yaml --json
        """
        import json as json_mod

        from scitex_app.sdk import get_files

        files = get_files(root)
        result = files.exists(path)
        if as_json:
            click.echo(json_mod.dumps({"path": path, "exists": result}))
        else:
            click.echo("true" if result else "false")
        raise SystemExit(0 if result else 1)

    @main.command()
    @click.argument("path")
    @click.option("--root", default=".", help="Root directory for file backend.")
    @click.option("--json", "as_json", is_flag=True, help="Output as JSON.")
    @click.option(
        "--dry-run", is_flag=True, help="Show what would be deleted without deleting."
    )
    def delete(path, root, as_json, dry_run):
        """Delete a file through the SDK backend.

        Examples:
            scitex-app delete temp.txt
            scitex-app delete temp.txt --dry-run
        """
        import json as json_mod

        from scitex_app.sdk import get_files

        if dry_run:
            if as_json:
                click.echo(
                    json_mod.dumps({"action": "delete", "path": path, "dry_run": True})
                )
            else:
                click.echo(f"[dry-run] Would delete {path}")
            return
        files = get_files(root)
        files.delete(path)
        if as_json:
            click.echo(json_mod.dumps({"path": path, "deleted": True}))
        else:
            click.echo(f"Deleted {path}")

    @main.command()
    @click.argument("old_path")
    @click.argument("new_path")
    @click.option("--root", default=".", help="Root directory for file backend.")
    @click.option("--json", "as_json", is_flag=True, help="Output as JSON.")
    @click.option(
        "--dry-run", is_flag=True, help="Show what would be renamed without renaming."
    )
    def rename(old_path, new_path, root, as_json, dry_run):
        """Rename/move a file through the SDK backend.

        Examples:
            scitex-app rename old.txt new.txt
            scitex-app rename old.txt new.txt --dry-run
        """
        import json as json_mod

        from scitex_app.sdk import get_files

        if dry_run:
            if as_json:
                click.echo(
                    json_mod.dumps(
                        {
                            "action": "rename",
                            "old": old_path,
                            "new": new_path,
                            "dry_run": True,
                        }
                    )
                )
            else:
                click.echo(f"[dry-run] Would rename {old_path} -> {new_path}")
            return
        files = get_files(root)
        files.rename(old_path, new_path)
        if as_json:
            click.echo(
                json_mod.dumps({"old": old_path, "new": new_path, "renamed": True})
            )
        else:
            click.echo(f"Renamed {old_path} -> {new_path}")

    @main.command()
    @click.argument("src_path")
    @click.argument("dest_path")
    @click.option("--root", default=".", help="Root directory for file backend.")
    @click.option("--json", "as_json", is_flag=True, help="Output as JSON.")
    @click.option(
        "--dry-run", is_flag=True, help="Show what would be copied without copying."
    )
    def copy(src_path, dest_path, root, as_json, dry_run):
        """Copy a file through the SDK backend.

        Examples:
            scitex-app copy src.txt dst.txt
            scitex-app copy src.txt dst.txt --dry-run
        """
        import json as json_mod

        from scitex_app.sdk import get_files

        if dry_run:
            if as_json:
                click.echo(
                    json_mod.dumps(
                        {
                            "action": "copy",
                            "src": src_path,
                            "dest": dest_path,
                            "dry_run": True,
                        }
                    )
                )
            else:
                click.echo(f"[dry-run] Would copy {src_path} -> {dest_path}")
            return
        files = get_files(root)
        files.copy(src_path, dest_path)
        if as_json:
            click.echo(
                json_mod.dumps({"src": src_path, "dest": dest_path, "copied": True})
            )
        else:
            click.echo(f"Copied {src_path} -> {dest_path}")

    # -- App Development ----------------------------------------------------
    from ._app import app

    main.add_command(app)

    # -- Integration ---------------------------------------------------------
    main.add_command(mcp)
    main.add_command(list_python_apis)

    try:
        from scitex_dev.cli import docs_click_group, skills_click_group

        main.add_command(docs_click_group(package="scitex-app"))
        main.add_command(skills_click_group(package="scitex-app"))
    except ImportError:

        @main.group()
        def docs():
            """Documentation (requires scitex-dev)."""

        @docs.command("list")
        def docs_list():
            """List available documentation pages."""
            click.echo(
                "ERROR: scitex-dev is required for docs. "
                "Install with: pip install scitex-dev",
                err=True,
            )
            raise SystemExit(1)

        @docs.command("get")
        @click.argument("page_name", required=False)
        def docs_get(page_name):
            """Show documentation."""
            click.echo(
                "ERROR: scitex-dev is required for docs. "
                "Install with: pip install scitex-dev",
                err=True,
            )
            raise SystemExit(1)

        @main.group()
        def skills():
            """View package skills (requires scitex-dev)."""

        @skills.command("list")
        def skills_list():
            """List available skill pages."""
            click.echo(
                "ERROR: scitex-dev is required for skills. "
                "Install with: pip install scitex-dev",
                err=True,
            )
            raise SystemExit(1)

        @skills.command("get")
        @click.argument("skill_name", required=False)
        def skills_get(skill_name):
            """Show a specific skill page."""
            click.echo(
                "ERROR: scitex-dev is required for skills. "
                "Install with: pip install scitex-dev",
                err=True,
            )
            raise SystemExit(1)
