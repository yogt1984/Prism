"""Prism CLI — terminal control plane for the news pipeline."""

from importlib.metadata import version as pkg_version
from typing import Annotated

import typer

from prism.cli._fmt import console, is_json_mode, print_json, set_json_mode
from prism.cli.briefing import app as briefing_app
from prism.cli.config_cmd import app as config_app
from prism.cli.cycle import app as cycle_app
from prism.cli.docs import app as docs_app
from prism.cli.run import app as run_app
from prism.cli.source import app as source_app
from prism.cli.status import app as status_app
from prism.cli.story import app as story_app
from prism.cli.user import app as user_app

app = typer.Typer(
    name="prism",
    help="Prism — AI-curated multi-perspective news briefings.",
    no_args_is_help=True,
    rich_markup_mode="rich",
)

app.add_typer(run_app, name="run")
app.add_typer(status_app, name="status")
app.add_typer(cycle_app, name="cycle")
app.add_typer(config_app, name="config")
app.add_typer(user_app, name="user")
app.add_typer(source_app, name="source")
app.add_typer(story_app, name="story")
app.add_typer(briefing_app, name="briefing")
app.add_typer(docs_app, name="docs")


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
