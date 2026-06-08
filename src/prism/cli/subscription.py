"""CLI commands for subscription lifecycle management."""

import typer
from rich.table import Table

from prism.cli._fmt import console, is_json_mode, print_json

app = typer.Typer(help="Subscription lifecycle management.")


@app.command()
def expire() -> None:
    """Run grace period expiry check."""
    from prism.db import get_engine
    from prism.subscription import expire_grace_periods

    count = expire_grace_periods(get_engine())

    if is_json_mode():
        print_json({"downgraded": count})
        return

    console.print(f"Downgraded {count} user(s).")


@app.command()
def status() -> None:
    """Show users with active or expired grace periods."""
    from datetime import UTC, datetime

    from sqlmodel import Session, select

    from prism.db import get_engine
    from prism.models import User

    with Session(get_engine()) as session:
        users = session.exec(
            select(User).where(User.pro_until != None)  # noqa: E711
        ).all()

    if not users:
        if is_json_mode():
            print_json({"users": []})
        else:
            console.print("No users with grace periods.")
        return

    now = datetime.now(UTC)

    if is_json_mode():
        rows = []
        for u in users:
            expired = u.pro_until < now if u.pro_until else False
            rows.append({
                "id": u.id,
                "email": u.email,
                "is_pro": u.is_pro,
                "pro_until": str(u.pro_until),
                "status": "EXPIRED" if expired else "ACTIVE",
            })
        print_json({"users": rows})
        return

    table = Table(title="Grace Period Status")
    table.add_column("ID")
    table.add_column("Email")
    table.add_column("Pro?")
    table.add_column("Grace Until")
    table.add_column("Status")

    for u in users:
        expired = u.pro_until < now if u.pro_until else False
        table.add_row(
            str(u.id), u.email, str(u.is_pro),
            str(u.pro_until), "EXPIRED" if expired else "ACTIVE",
        )
    console.print(table)
