"""prism user — user management commands."""

from typing import Annotated

import typer
from sqlmodel import Session, select

from prism.cli._fmt import console, err_console, is_json_mode, print_json, print_table

app = typer.Typer(help="User management.")


def _get_engine():  # type: ignore[no-untyped-def]
    from prism.db import get_engine
    return get_engine()


def _find_user(session: Session, email: str):  # type: ignore[no-untyped-def]
    from prism.models import User
    return session.exec(select(User).where(User.email == email.strip().lower())).first()


def _fmt_last_briefing(info: dict) -> str:  # type: ignore[type-arg]
    if not info["last_briefing_id"]:
        return "none"
    bid = info["last_briefing_id"]
    dt = info["last_briefing_date"]
    sent = info["last_briefing_sent"]
    return f"#{bid} ({dt}, sent={sent})"


@app.command("add")
def user_add(
    email: str,
    interests: Annotated[str, typer.Option(help="Comma-separated interests.")] = "",
    depth: Annotated[int, typer.Option(help="Stories per briefing.")] = 10,
) -> None:
    """Register a new user."""
    from prism.onboarding import RegistrationError, register_user
    try:
        user = register_user(email, interests=interests, briefing_depth=depth,
                             engine=_get_engine())
    except RegistrationError as exc:
        err_console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(1)

    if is_json_mode():
        print_json({"id": user.id, "email": user.email, "interests": user.interests})
        return
    console.print(f"  [green]Registered[/green] {user.email} (id={user.id})")


@app.command("ls")
def user_ls(
    pro: Annotated[bool, typer.Option("--pro", help="Show pro users only.")] = False,
) -> None:
    """List all users."""
    from prism.models import User
    engine = _get_engine()
    with Session(engine) as session:
        stmt = select(User)
        if pro:
            stmt = stmt.where(User.is_pro.is_(True))  # type: ignore[union-attr]
        users = session.exec(stmt).all()

    rows = [
        [str(u.id), u.email, u.interests or "-", u.preferred_format,
         str(u.briefing_depth), "yes" if u.is_pro else "no",
         u.created_at.strftime("%Y-%m-%d")]
        for u in users
    ]
    print_table("Users", ["ID", "Email", "Interests", "Format", "Depth", "Pro", "Created"], rows)


@app.command("show")
def user_show(email: str) -> None:
    """Show user details, engagement stats, and last briefing."""
    from prism.models import Briefing, Engagement
    engine = _get_engine()
    with Session(engine) as session:
        user = _find_user(session, email)
        if not user:
            err_console.print(f"[red]User not found:[/red] {email}")
            raise typer.Exit(1)

        engagements = session.exec(
            select(Engagement).where(Engagement.user_id == user.id)
        ).all()
        last_briefing = session.exec(
            select(Briefing).where(Briefing.user_id == user.id)
            .order_by(Briefing.created_at.desc())  # type: ignore[union-attr]
        ).first()

        info = {
            "id": user.id,
            "email": user.email,
            "name": user.name,
            "interests": user.interests,
            "preferred_format": user.preferred_format,
            "briefing_depth": user.briefing_depth,
            "is_pro": user.is_pro,
            "created_at": str(user.created_at),
            "engagement_count": len(engagements),
            "last_briefing_id": last_briefing.id if last_briefing else None,
            "last_briefing_date": str(last_briefing.created_at) if last_briefing else None,
            "last_briefing_sent": last_briefing.sent if last_briefing else None,
        }

    if is_json_mode():
        print_json(info)
        return

    from rich.panel import Panel
    lines = [
        f"Email:    {info['email']}",
        f"Name:     {info['name'] or '-'}",
        f"Interests:{info['interests'] or '-'}",
        f"Format:   {info['preferred_format']}",
        f"Depth:    {info['briefing_depth']}",
        f"Pro:      {'yes' if info['is_pro'] else 'no'}",
        f"Created:  {info['created_at']}",
        "",
        f"Engagements: {info['engagement_count']}",
        f"Last briefing: {_fmt_last_briefing(info)}",
    ]
    console.print(Panel("\n".join(lines), title=f"User #{info['id']}"))


@app.command("edit")
def user_edit(
    email: str,
    interests: Annotated[str | None, typer.Option(help="Comma-separated interests.")] = None,
    depth: Annotated[int | None, typer.Option(help="Stories per briefing.")] = None,
    fmt: Annotated[str | None, typer.Option("--format",
                                            help="email|json_feed|audio_script")] = None,
) -> None:
    """Update user preferences."""
    from prism.models import BriefingFormat
    from prism.onboarding import VALID_INTERESTS
    engine = _get_engine()
    with Session(engine) as session:
        user = _find_user(session, email)
        if not user:
            err_console.print(f"[red]User not found:[/red] {email}")
            raise typer.Exit(1)

        if interests is not None:
            if interests:
                for i in interests.split(","):
                    if i.strip() not in VALID_INTERESTS:
                        err_console.print(f"[red]Invalid interest:[/red] {i.strip()}")
                        raise typer.Exit(1)
            user.interests = interests
        if depth is not None:
            user.briefing_depth = depth
        if fmt is not None:
            try:
                user.preferred_format = BriefingFormat(fmt)
            except ValueError:
                err_console.print(f"[red]Invalid format:[/red] {fmt}")
                raise typer.Exit(1)

        session.add(user)
        session.commit()

    if is_json_mode():
        print_json({"status": "updated", "email": email})
        return
    console.print(f"  [green]Updated[/green] {email}")


@app.command("rm")
def user_rm(
    email: str,
    yes: Annotated[bool, typer.Option("--yes", "-y", help="Skip confirmation.")] = False,
) -> None:
    """Delete a user."""
    engine = _get_engine()
    with Session(engine) as session:
        user = _find_user(session, email)
        if not user:
            err_console.print(f"[red]User not found:[/red] {email}")
            raise typer.Exit(1)

        if not yes:
            confirm = typer.confirm(f"Delete user {user.email}?")
            if not confirm:
                raise typer.Abort()

        session.delete(user)
        session.commit()

    if is_json_mode():
        print_json({"status": "deleted", "email": email})
        return
    console.print(f"  [green]Deleted[/green] {email}")
