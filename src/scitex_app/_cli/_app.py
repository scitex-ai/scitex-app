"""CLI commands for SciTeX app development — scaffold, validate, dev-install, submit."""

from __future__ import annotations

from pathlib import Path

import click
from rich.console import Console

console = Console()


@click.group()
def app():
    """Create, validate, and install SciTeX apps."""


@app.command("init")
@click.argument("target_dir", default=".", type=click.Path())
@click.option("--name", "-n", default=None, help="App module name (must end with _app)")
@click.option("--label", "-l", default=None, help="Human-readable label")
@click.option(
    "--icon", "-i", default="fas fa-puzzle-piece", help="Font Awesome icon class"
)
@click.option("--description", "-d", default="", help="Short description")
@click.option(
    "--frontend",
    "-f",
    type=click.Choice(["html", "react"]),
    default="html",
    help="Frontend type: html (default) or react",
)
@click.option("--overwrite", is_flag=True, help="Overwrite existing files")
def app_init(target_dir, name, label, icon, description, frontend, overwrite):
    """Scaffold a complete SciTeX app in a directory.

    \b
    Examples:
        scitex-app app init .
        scitex-app app init /path/to/my_app --name my_awesome_app
        scitex-app app init . -n demo_app -l "Demo" -i "fas fa-flask"
    """
    from scitex_app.appmaker import init_app

    target = Path(target_dir).resolve()
    app_name = name or target.name

    if not (app_name.endswith("_app") or app_name.endswith("-app")):
        sep = "-" if "-" in app_name else "_"
        suffixed = f"{app_name}{sep}app"
        console.print(
            f"[yellow]Warning:[/yellow] App name '{app_name}' does not end with "
            f"'_app' or '-app'. Adding suffix: '{suffixed}'"
        )
        app_name = suffixed

    console.print(f"[cyan]Scaffolding app:[/cyan] {app_name} in {target}")

    created = init_app(
        target_dir=target,
        name=app_name,
        label=label or "",
        icon=icon,
        description=description,
        overwrite=overwrite,
        frontend_type=frontend,
    )

    for filepath in created:
        console.print(f"  [green]+[/green] {filepath}")

    if not created:
        console.print("  [yellow]No new files created (all already exist).[/yellow]")
    else:
        console.print(f"\n[green]Done![/green] Created {len(created)} files.")


@app.command("validate")
@click.argument("app_dir", default=".", type=click.Path(exists=True))
def app_validate(app_dir):
    """Validate a SciTeX app for submission readiness.

    \b
    Examples:
        scitex-app app validate .
        scitex-app app validate /path/to/my_app
    """
    from scitex_app.appmaker import validate

    errors = validate(app_dir)

    if not errors:
        console.print("[green]All checks passed![/green] App is ready for submission.")
    else:
        console.print(f"[red]Found {len(errors)} issue(s):[/red]")
        for err in errors:
            console.print(f"  [red]✗[/red] {err}")
        raise SystemExit(1)


@app.command("dev-install")
@click.argument("app_dir", default=".", type=click.Path(exists=True))
@click.option(
    "--server",
    "-s",
    default="http://127.0.0.1:8000",
    envvar="SCITEX_SERVER_URL",
    help="SciTeX Cloud server URL",
)
@click.option("--token", "-t", envvar="SCITEX_API_TOKEN", help="JWT access token")
@click.option("--owner", "-o", default=None, help="Gitea username (auto-detected)")
@click.option("--repo", "-r", default=None, help="Gitea repo name (from manifest)")
def app_dev_install(app_dir, server, token, owner, repo):
    """Dev-install an app on SciTeX Cloud server.

    Validates locally, then calls the dev install API.
    The app appears as a workspace tab immediately.

    \b
    Examples:
        scitex-app app dev-install .
        scitex-app app dev-install . --server http://my-server:8000
    """
    if not token:
        console.print(
            "[red]Error:[/red] No API token. Set SCITEX_API_TOKEN or use --token."
        )
        raise SystemExit(1)

    from scitex_app.appmaker._dev_install import dev_install

    console.print(f"[cyan]Dev-installing from:[/cyan] {Path(app_dir).resolve()}")
    console.print(f"[cyan]Server:[/cyan] {server}")

    result = dev_install(
        app_dir, server_url=server, token=token, owner=owner, repo=repo
    )

    if result.get("success"):
        console.print("[green]Dev install successful![/green]")
        if result.get("module_name"):
            console.print(f"  Module: {result['module_name']}")
        console.print("  Your app should appear in the workspace sidebar.")
    else:
        errors = result.get("errors", [result.get("error", "Unknown error")])
        console.print("[red]Dev install failed:[/red]")
        for err in errors:
            console.print(f"  [red]✗[/red] {err}")
        raise SystemExit(1)


@app.command("submit")
@click.argument("app_dir", default=".", type=click.Path(exists=True))
@click.option(
    "--server",
    "-s",
    default="http://127.0.0.1:8000",
    envvar="SCITEX_SERVER_URL",
    help="SciTeX Cloud server URL",
)
@click.option("--token", "-t", envvar="SCITEX_API_TOKEN", help="JWT access token")
def app_submit(app_dir, server, token):
    """Submit an app for review and publication.

    Validates locally, then submits via the server API.
    A PR is opened on the scitex-apps registry for review.

    \b
    Examples:
        scitex-app app submit .
        scitex-app app submit /path/to/my_app --server https://scitex.example.com
    """
    if not token:
        console.print(
            "[red]Error:[/red] No API token. Set SCITEX_API_TOKEN or use --token."
        )
        raise SystemExit(1)

    from scitex_app.appmaker._publish import publish

    console.print(f"[cyan]Submitting app from:[/cyan] {Path(app_dir).resolve()}")

    result = publish(app_dir, server_url=server, token=token)

    if result.get("success"):
        console.print("[green]Submission successful![/green]")
        if result.get("pr_url"):
            console.print(f"  PR: {result['pr_url']}")
    else:
        errors = result.get("errors", [result.get("error", "Unknown error")])
        console.print("[red]Submission failed:[/red]")
        for err in errors:
            console.print(f"  [red]✗[/red] {err}")
        raise SystemExit(1)


# EOF
