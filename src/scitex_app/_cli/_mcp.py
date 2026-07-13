#!/usr/bin/env python3
# Timestamp: 2026-03-13
# File: scitex_app/_cli/_mcp.py

"""MCP server commands for scitex-app."""

import click


@click.group(invoke_without_command=True)
@click.option("--help-recursive", is_flag=True, help="Show help for all subcommands.")
@click.pass_context
def mcp(ctx, help_recursive):
    """MCP (Model Context Protocol) server commands."""
    if help_recursive:
        _print_help_recursive(ctx)
        ctx.exit(0)
    elif ctx.invoked_subcommand is None:
        click.echo(ctx.get_help())


def _print_help_recursive(ctx):
    """Print help for mcp and all its subcommands."""
    fake_parent = click.Context(click.Group(), info_name="scitex-app")
    parent_ctx = click.Context(mcp, info_name="mcp", parent=fake_parent)

    click.secho("=== scitex-app mcp ===", fg="cyan", bold=True)
    click.echo(mcp.get_help(parent_ctx))

    for name in sorted(mcp.list_commands(ctx) or []):
        cmd = mcp.get_command(ctx, name)
        if cmd is None:
            continue
        click.echo()
        click.secho(f"=== scitex-app mcp {name} ===", fg="cyan", bold=True)
        with click.Context(cmd, info_name=name, parent=parent_ctx) as sub_ctx:
            click.echo(cmd.get_help(sub_ctx))


@mcp.command("list-tools")
@click.option(
    "-v", "--verbose", count=True, help="Verbosity: -v sig, -vv +desc1, -vvv full."
)
@click.option("--json", "as_json", is_flag=True, help="Output as JSON.")
def list_tools(verbose: int, as_json: bool) -> None:
    """List available MCP tools.

    \b
    Verbosity levels:
      (none)  Tool names only
      -v      Full signatures
      -vv     Signatures + first line of description
      -vvv    Signatures + full description

    \b
    Example:
      $ scitex-app mcp list-tools
      $ scitex-app mcp list-tools -vv
      $ scitex-app mcp list-tools --json
    """
    try:
        from .._mcp.server import mcp as mcp_server
    except ImportError as e:
        raise click.ClickException(
            f"fastmcp not installed. Install with: pip install scitex-app[all]\n{e}"
        ) from e

    import asyncio

    tools = asyncio.run(mcp_server.list_tools())
    total = len(tools)

    if as_json:
        import json

        output = {
            "total": total,
            "tools": [
                {"name": t.name, "description": t.description or ""} for t in tools
            ],
        }
        click.echo(json.dumps(output, indent=2))
        return

    click.secho(f"scitex-app MCP: {total} tools", fg="cyan", bold=True)
    click.echo()

    for tool in sorted(tools, key=lambda t: t.name):
        if verbose == 0:
            click.echo(f"  {tool.name}")
        elif verbose >= 1:
            click.echo(f"  {tool.name}")
            if tool.description:
                if verbose == 1:
                    desc = tool.description.split("\n")[0].strip()
                else:
                    desc = tool.description.strip()
                click.echo(f"    {desc}")
            click.echo()


@mcp.command("start")
@click.option("--dry-run", is_flag=True, help="Print launch plan without starting.")
@click.option(
    "-y", "--yes", is_flag=True, help="Suppress interactive confirmation (assume yes)."
)
def start_server(dry_run: bool, yes: bool) -> None:
    """Start the scitex-app MCP server.

    \b
    Example:
      $ scitex-app mcp start
      $ scitex-app mcp start --dry-run
    """
    if dry_run:
        click.echo("DRY RUN — would start scitex-app MCP server (stdio transport)")
        return
    try:
        from .._mcp.server import mcp as mcp_server
    except ImportError as e:
        raise click.ClickException(
            f"Failed to import MCP server. "
            f"Install fastmcp: pip install scitex-app[all]\n{e}"
        ) from e

    click.echo("Starting scitex-app MCP server...")
    mcp_server.run()


@mcp.command(
    "installation",
    hidden=True,
    context_settings={"ignore_unknown_options": True},
)
@click.pass_context
def installation_deprecated(ctx) -> None:
    """(deprecated) Renamed to `show-installation`."""
    click.echo(
        "error: `scitex-app mcp installation` was renamed to "
        "`scitex-app mcp show-installation`.\n"
        "Re-run with: scitex-app mcp show-installation",
        err=True,
    )
    ctx.exit(2)


@mcp.command("show-installation")
@click.option("--json", "as_json", is_flag=True, help="Output as JSON.")
def show_installation(as_json: bool) -> None:
    """Show installation instructions for MCP server integration.

    \b
    Example:
      $ scitex-app mcp show-installation
      $ scitex-app mcp show-installation --json
    """
    config = {
        "mcpServers": {
            "scitex-app": {
                "command": "scitex-app",
                "args": ["mcp", "start"],
            }
        }
    }
    if as_json:
        import json as _json

        click.echo(
            _json.dumps(
                {
                    "success": True,
                    "install_command": "pip install scitex-app[all]",
                    "config": config,
                },
                indent=2,
            )
        )
        return
    click.echo("Install scitex-app with MCP support:")
    click.echo()
    click.echo("  pip install scitex-app[all]")
    click.echo()
    click.echo("Add to your MCP client configuration:")
    click.echo()
    import json as _json

    for line in _json.dumps(config, indent=2).split("\n"):
        click.echo(f"  {line}")
    click.echo()
    click.echo("Verify with:")
    click.echo("  scitex-app mcp doctor")
    click.echo("  scitex-app mcp list-tools")


@mcp.command("doctor")
def doctor() -> None:
    """Check MCP server dependencies and configuration.

    \b
    Example:
      $ scitex-app mcp doctor
    """
    click.echo("Checking MCP dependencies...")

    try:
        import fastmcp

        click.echo(f"  [OK] fastmcp {fastmcp.__version__}")
    except ImportError:
        click.echo("  [!!] fastmcp not installed")
        click.echo("    Install with: pip install scitex-app[all]")
        return

    try:
        from .._mcp.server import mcp as mcp_server

        import asyncio

        tool_count = len(asyncio.run(mcp_server.list_tools()))
        click.echo(f"  [OK] MCP server loaded ({tool_count} tools)")
    except Exception as e:
        click.echo(f"  [!!] MCP server error: {e}")
        return

    click.echo()
    click.echo("MCP server is ready.")
    click.echo("Run with: scitex-app mcp start")
