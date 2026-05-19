"""Prism CLI — terminal control plane for the news pipeline."""

from importlib.metadata import version as pkg_version
from typing import Annotated

import typer

from prism.cli._fmt import console, is_json_mode, print_json, set_json_mode
from prism.cli.config_cmd import app as config_app

app = typer.Typer(
    name="prism",
    help="Prism — AI-curated multi-perspective news briefings.",
    no_args_is_help=True,
    rich_markup_mode="rich",
)

app.add_typer(config_app, name="config")


def _json_callback(value: bool) -> None:
    if value:
        set_json_mode(True)


@app.callback()
def main_callback(
    json_output: Annotated[
        bool,
        typer.Option("--json", help="Machine-readable JSON output.", callback=_json_callback,
                     is_eager=True),
    ] = False,
) -> None:
    """Global options applied before any subcommand."""


@app.command()
def version() -> None:
    """Show Prism version and environment info."""
    import platform

    try:
        prism_ver = pkg_version("prism")
    except Exception:
        prism_ver = "0.1.0 (dev)"

    info = {
        "prism": prism_ver,
        "python": platform.python_version(),
        "platform": platform.platform(),
    }

    # Gather dependency versions
    for dep in ("anthropic", "httpx", "sqlmodel", "typer", "rich", "apscheduler"):
        try:
            info[dep] = pkg_version(dep)
        except Exception:
            info[dep] = "not installed"

    if is_json_mode():
        print_json(info)
        return

    console.print(f"\n  [bold]Prism[/bold] {info['prism']}")
    console.print(f"  Python {info['python']} on {info['platform']}\n")
    console.print("  Dependencies:")
    for dep in ("anthropic", "httpx", "sqlmodel", "typer", "rich", "apscheduler"):
        console.print(f"    {dep:<16s} {info[dep]}")
    console.print()


def main() -> None:
    app()
