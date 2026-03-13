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
        ("Files", ["read", "write", "list", "exists"]),
        ("Integration", ["mcp", "list-python-apis"]),
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
    def read(path, root, binary):
        """Read a file through the SDK backend."""
        from scitex_app.sdk import get_files

        files = get_files(root)
        content = files.read(path, binary=binary)
        if binary:
            import sys

            sys.stdout.buffer.write(content)
        else:
            click.echo(content)

    @main.command("list")
    @click.argument("directory", default="")
    @click.option("--root", default=".", help="Root directory for file backend.")
    @click.option("--ext", multiple=True, help="Filter by extension (e.g., .yaml).")
    def list_files(directory, root, ext):
        """List files in a directory through the SDK backend."""
        from scitex_app.sdk import get_files

        files = get_files(root)
        extensions = list(ext) if ext else None
        for path in files.list(directory, extensions=extensions):
            click.echo(path)

    @main.command()
    @click.argument("path")
    @click.option("--root", default=".", help="Root directory for file backend.")
    def exists(path, root):
        """Check if a file exists through the SDK backend."""
        from scitex_app.sdk import get_files

        files = get_files(root)
        result = files.exists(path)
        click.echo("true" if result else "false")
        raise SystemExit(0 if result else 1)

    # -- Integration ---------------------------------------------------------
    main.add_command(mcp)
    main.add_command(list_python_apis)
