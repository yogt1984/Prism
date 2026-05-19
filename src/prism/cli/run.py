"""prism run — start the scheduler or run a single full cycle."""

from typing import Annotated

import typer

from prism.cli._fmt import console

app = typer.Typer(help="Run the pipeline scheduler.")


@app.callback(invoke_without_command=True)
def run(
    once: Annotated[
        bool, typer.Option("--once", help="Run one full cycle and exit.")
    ] = False,
) -> None:
    """Start the Prism pipeline scheduler."""
    import logging

    from prism.db import init_db
    from prism.main import (
        analysis_cycle,
        briefing_cycle,
        build_scheduler,
        discovery_cycle,
        install_signal_handlers,
    )

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    )

    console.print("  Initializing Prism pipeline...")
    engine = init_db()

    if once:
        console.print("  Running single cycle: discover -> analyze -> brief")
        discovery_cycle(engine)
        analysis_cycle(engine)
        briefing_cycle(engine)
        console.print("  [green]Cycle complete.[/green]")
        return

    scheduler = build_scheduler()
    install_signal_handlers(scheduler)
    console.print("  Pipeline started. Press Ctrl+C to stop.")
    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        console.print("\n  [yellow]Shutting down.[/yellow]")
