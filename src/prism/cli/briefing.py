"""prism briefing — briefing management commands."""

from typing import Annotated

import typer
from sqlmodel import Session, select

from prism.cli._fmt import (
    cli_get_engine as _get_engine,
)
from prism.cli._fmt import (
    console,
    err_console,
    is_json_mode,
    print_json,
    print_table,
)

app = typer.Typer(help="List, preview, and resend generated briefings.")


@app.command("ls")
def briefing_ls(
    user: Annotated[str | None, typer.Option(help="Filter by user email.")] = None,
    unsent: Annotated[bool, typer.Option("--unsent", help="Show unsent only.")] = False,
    limit: Annotated[int, typer.Option(help="Max rows to show.")] = 20,
) -> None:
    """List recent briefings."""
    from prism.models import Briefing, User
    engine = _get_engine()
    with Session(engine) as session:
        stmt = select(Briefing)
        if unsent:
            stmt = stmt.where(Briefing.sent.is_(False))  # type: ignore[union-attr]
        if user:
            u = session.exec(
                select(User).where(User.email == user.strip().lower())
            ).first()
            if not u:
                err_console.print(f"[red]User not found:[/red] {user}")
                raise typer.Exit(1)
            stmt = stmt.where(Briefing.user_id == u.id)

        briefings = session.exec(
            stmt.order_by(Briefing.created_at.desc()).limit(limit)  # type: ignore[union-attr]
        ).all()

        # Resolve user emails
        user_ids = {b.user_id for b in briefings}
        users = {u.id: u.email for u in session.exec(
            select(User).where(User.id.in_(user_ids))  # type: ignore[union-attr]
        ).all()} if user_ids else {}

    rows = [
        [str(b.id), users.get(b.user_id, "?"), str(b.story_count),
         "yes" if b.sent else "no",
         str(b.sent_at.strftime("%Y-%m-%d %H:%M") if b.sent_at else "-"),
         b.created_at.strftime("%Y-%m-%d %H:%M")]
        for b in briefings
    ]
    print_table("Briefings", ["ID", "User", "Stories", "Sent", "Sent At", "Created"], rows)


@app.command("show")
def briefing_show(briefing_id: Annotated[int, typer.Argument(help="Briefing ID.")]) -> None:
    """Show briefing content."""
    from prism.models import Briefing, User
    engine = _get_engine()
    with Session(engine) as session:
        briefing = session.get(Briefing, briefing_id)
        if not briefing:
            err_console.print(f"[red]Briefing not found:[/red] {briefing_id}")
            raise typer.Exit(1)

        user = session.get(User, briefing.user_id)
        email = user.email if user else "?"
        content = briefing.content_html or briefing.content_text or "(empty)"

    if is_json_mode():
        print_json({
            "id": briefing.id, "user": email,
            "story_count": briefing.story_count, "sent": briefing.sent,
            "sent_at": str(briefing.sent_at), "created_at": str(briefing.created_at),
            "content": content,
        })
        return

    from rich.panel import Panel
    console.print(Panel(
        f"User: {email} | Stories: {briefing.story_count} | "
        f"Sent: {'yes' if briefing.sent else 'no'}\n"
        f"Created: {briefing.created_at}",
        title=f"Briefing #{briefing.id}",
    ))
    # Strip HTML tags for terminal display
    import re
    text = re.sub(r"<[^>]+>", "", content)
    text = re.sub(r"\n{3,}", "\n\n", text)
    console.print(text.strip())
    console.print()


@app.command("preview")
def briefing_preview(email: Annotated[str, typer.Argument(help="User email address.")]) -> None:
    """Generate a briefing preview without sending (dry run)."""
    from prism.agents.p_ai import PersonalizationAgent
    from prism.agents.w_ai import WriterAgent
    from prism.models import User
    engine = _get_engine()

    with Session(engine) as session:
        user = session.exec(
            select(User).where(User.email == email.strip().lower())
        ).first()
        if not user:
            err_console.print(f"[red]User not found:[/red] {email}")
            raise typer.Exit(1)

    p_ai = PersonalizationAgent()
    stories = p_ai.select_stories(user, engine)
    if not stories:
        err_console.print("[yellow]No stories available for this user.[/yellow]")
        raise typer.Exit(0)

    w_ai = WriterAgent()
    content = w_ai.generate_briefing(user, stories, engine)

    if is_json_mode():
        print_json({"user": email, "story_count": len(stories), "content": content})
        return

    from rich.panel import Panel
    console.print(Panel(
        f"User: {email} | Stories: {len(stories)} | [yellow]DRY RUN — not sent[/yellow]",
        title="Briefing Preview",
    ))
    import re
    text = re.sub(r"<[^>]+>", "", content)
    text = re.sub(r"\n{3,}", "\n\n", text)
    console.print(text.strip())
    console.print()


@app.command("resend")
def briefing_resend(briefing_id: Annotated[int, typer.Argument(help="Briefing ID.")]) -> None:
    """Resend a previously generated briefing."""
    from prism.agents.w_ai import WriterAgent
    from prism.models import Briefing, User
    engine = _get_engine()

    with Session(engine) as session:
        briefing = session.get(Briefing, briefing_id)
        if not briefing:
            err_console.print(f"[red]Briefing not found:[/red] {briefing_id}")
            raise typer.Exit(1)

        user = session.get(User, briefing.user_id)
        if not user:
            err_console.print(f"[red]User not found for briefing:[/red] {briefing_id}")
            raise typer.Exit(1)

        content = briefing.content_html or briefing.content_text
        if not content:
            err_console.print("[red]Briefing has no content.[/red]")
            raise typer.Exit(1)

    w_ai = WriterAgent()
    sent = w_ai.send_email(user, content)

    if is_json_mode():
        print_json({"briefing_id": briefing_id, "sent": sent})
        return

    if sent:
        console.print(f"  [green]Resent[/green] briefing #{briefing_id} to {user.email}")
    else:
        err_console.print(f"  [red]Failed[/red] to resend briefing #{briefing_id}")
        raise typer.Exit(1)
