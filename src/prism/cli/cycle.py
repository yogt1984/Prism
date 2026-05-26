"""prism cycle — manually trigger individual agent cycles."""

from typing import Annotated

import typer

from prism.cli._fmt import (
    cli_get_engine as _get_engine,
)
from prism.cli._fmt import (
    console,
    err_console,
    info,
    is_json_mode,
    print_json,
)

app = typer.Typer(help="Manually trigger discovery, analysis, or briefing cycles.")


@app.command("discover")
def cycle_discover() -> None:
    """Run D_AI discovery cycle once."""
    from prism.main import discovery_cycle

    info("  Running discovery cycle...")
    discovery_cycle(_get_engine())

    if is_json_mode():
        print_json({"cycle": "discovery", "status": "complete"})
        return
    console.print("  [green]Discovery cycle complete.[/green]")


@app.command("analyze")
def cycle_analyze() -> None:
    """Run A_AI analysis cycle once."""
    from prism.main import analysis_cycle

    info("  Running analysis cycle...")
    analysis_cycle(_get_engine())

    if is_json_mode():
        print_json({"cycle": "analysis", "status": "complete"})
        return
    console.print("  [green]Analysis cycle complete.[/green]")


@app.command("brief")
def cycle_brief(
    user: Annotated[
        str | None,
        typer.Option("--user", help="Run briefing for a single user (email)."),
    ] = None,
) -> None:
    """Run P_AI + W_AI briefing cycle once."""
    from sqlmodel import Session, select

    from prism.agents.p_ai import PersonalizationAgent
    from prism.agents.w_ai import WriterAgent
    from prism.models import User

    engine = _get_engine()
    p_ai = PersonalizationAgent()
    w_ai = WriterAgent()

    if user:
        with Session(engine) as session:
            u = session.exec(
                select(User).where(User.email == user.strip().lower())
            ).first()
        if not u:
            err_console.print(f"[red]User not found:[/red] {user}")
            raise typer.Exit(1)
        users = [u]
    else:
        users = p_ai.get_all_users(engine)

    info(f"  Running briefing cycle for {len(users)} user(s)...")
    sent = 0
    for u in users:
        clusters = p_ai.select_stories(u, engine)
        result = w_ai.create_and_send(u, clusters, engine)
        if result and result.sent:
            sent += 1

    if is_json_mode():
        print_json({"cycle": "briefing", "users": len(users), "sent": sent})
        return
    console.print(
        f"  [green]Briefing cycle complete.[/green] {sent}/{len(users)} sent."
    )
