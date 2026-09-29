"""CLI commands for SciTeX app development — scaffold, validate, dev-install, submit."""

from __future__ import annotations

from pathlib import Path

import click

import scitex_logging as slogging

log = slogging.getLogger(__name__)


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
@click.option("--dry-run", is_flag=True, help="Print plan without writing files.")
@click.option(
    "-y", "--yes", is_flag=True, help="Suppress interactive confirmation (assume yes)."
)
def app_init(
    target_dir, name, label, icon, description, frontend, overwrite, dry_run, yes
):
    """Scaffold a complete SciTeX app in a directory.

    \b
    Examples:
        scitex-app app init .
        scitex-app app init /path/to/my_app --name my_awesome_app
        scitex-app app init . -n demo_app -l "Demo" -i "fas fa-flask"
        scitex-app app init . --dry-run
    """
    if dry_run:
        click.echo(
            f"DRY RUN — would scaffold app at {Path(target_dir).resolve()} "
            f"(name={name or '(auto)'}, frontend={frontend}, overwrite={overwrite})"
        )
        return
    from scitex_app.appmaker import init_app

    target = Path(target_dir).resolve()
    app_name = name or target.name

    if not (app_name.endswith("_app") or app_name.endswith("-app")):
        sep = "-" if "-" in app_name else "_"
        suffixed = f"{app_name}{sep}app"
        log.warning(
            f"App name '{app_name}' does not end with "
            f"'_app' or '-app'. Adding suffix: '{suffixed}'"
        )
        app_name = suffixed

    log.info(f"Scaffolding app: {app_name} in {target}")

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
        log.info(f"  + {filepath}")

    if not created:
        log.warning("No new files created (all already exist).")
    else:
        log.success(f"Done! Created {len(created)} files.")


@app.command("validate")
@click.argument("app_dir", default=".", type=click.Path(exists=True))
def app_validate(app_dir):
    """Validate a SciTeX app for submission readiness.

    \b
    Examples:
        scitex-app app validate .
        scitex-app app validate /path/to/my_app
    """
    from scitex_app.appmaker import validate_with_warnings

    errors, warnings = validate_with_warnings(app_dir)

    # Advisory notices print whether or not the app passes, and never change the
    # exit code. Printing them only on failure would deliver advice exactly when
    # nobody is reading it, and exiting 1 on them is the defect this tier fixed.
    if warnings:
        log.warning(f"{len(warnings)} advisory notice(s):")
        for warn in warnings:
            log.warning(f"  ! {warn}")

    if not errors:
        log.success("All checks passed! App is ready for submission.")
    else:
        log.error(f"Found {len(errors)} issue(s):")
        for err in errors:
            log.error(f"  ✗ {err}")
        raise SystemExit(1)


@app.command(
    "dev-install",
    hidden=True,
    context_settings={"ignore_unknown_options": True, "allow_extra_args": True},
)
@click.pass_context
def app_dev_install_deprecated(ctx):
    """(deprecated) Renamed to `install-dev`."""
    click.echo(
        "error: `scitex-app app dev-install` was renamed to "
        "`scitex-app app install-dev`.\n"
        "Re-run with: scitex-app app install-dev [...]",
        err=True,
    )
    ctx.exit(2)


@app.command("install-dev")
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
@click.option(
    "--dry-run", is_flag=True, help="Print install plan without contacting server."
)
@click.option(
    "-y", "--yes", is_flag=True, help="Suppress interactive confirmation (assume yes)."
)
def app_install_dev(app_dir, server, token, owner, repo, dry_run, yes):
    """Dev-install an app on SciTeX Cloud server.

    Validates locally, then calls the dev install API.
    The app appears as a workspace tab immediately.

    \b
    Examples:
        scitex-app app install-dev .
        scitex-app app install-dev . --server http://my-server:8000
        scitex-app app install-dev . --dry-run
    """
    if dry_run:
        click.echo(
            f"DRY RUN — would dev-install app at {Path(app_dir).resolve()} to {server}"
        )
        return
    if not token:
        log.error("No API token. Set SCITEX_API_TOKEN or use --token.")
        raise SystemExit(1)

    from scitex_app.appmaker._dev_install import dev_install

    log.info(f"Dev-installing from: {Path(app_dir).resolve()}")
    log.info(f"Server: {server}")

    result = dev_install(
        app_dir, server_url=server, token=token, owner=owner, repo=repo
    )

    if result.get("success"):
        log.success("Dev install successful!")
        if result.get("module_name"):
            log.info(f"  Module: {result['module_name']}")
        log.info("  Your app should appear in the workspace sidebar.")
    else:
        errors = result.get("errors", [result.get("error", "Unknown error")])
        log.error("Dev install failed:")
        for err in errors:
            log.error(f"  ✗ {err}")
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
        log.error("No API token. Set SCITEX_API_TOKEN or use --token.")
        raise SystemExit(1)

    from scitex_app.appmaker._publish import publish

    log.info(f"Submitting app from: {Path(app_dir).resolve()}")

    result = publish(app_dir, server_url=server, token=token)

    if result.get("success"):
        log.success("Submission successful!")
        if result.get("pr_url"):
            log.info(f"  PR: {result['pr_url']}")
    else:
        errors = result.get("errors", [result.get("error", "Unknown error")])
        log.error("Submission failed:")
        for err in errors:
            log.error(f"  ✗ {err}")
        raise SystemExit(1)


# EOF
