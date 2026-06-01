"""prism perception — track keywords and query media perception scores."""

from datetime import UTC, datetime
from typing import Annotated

import typer
from sqlmodel import Session, col, select

from prism.cli._fmt import (
    cli_get_engine as _get_engine,
)
from prism.cli._fmt import (
    console,
    err_console,
    info,
    is_json_mode,
    print_json,
    print_table,
)

app = typer.Typer(help="Track keywords and query media perception pressure.")

keyword_app = typer.Typer(help="Manage tracked keywords.")
app.add_typer(keyword_app, name="keyword")


def _age_str(dt: datetime) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    delta = datetime.now(UTC) - dt
    hours = delta.total_seconds() / 3600
    if hours < 1:
        return f"{int(delta.total_seconds() / 60)}m ago"
    if hours < 24:
        return f"{int(hours)}h ago"
    return f"{int(hours / 24)}d ago"


def _sign_str(val: float) -> str:
    if val > 0:
        return f"+{val:.3f}"
    return f"{val:.3f}"


# ── Keyword management ──────────────────────────────────────────────


@keyword_app.command("add")
def keyword_add(
    keyword: Annotated[str, typer.Argument(help="Keyword to track.")],
    aliases: Annotated[str, typer.Option("--aliases", "-a", help="Comma-separated synonyms.")] = "",
    category: Annotated[str, typer.Option("--category", "-c", help="Grouping label.")] = "",
) -> None:
    """Add a keyword to track."""
    from prism.models import KeywordTrack

    engine = _get_engine()
    with Session(engine) as session:
        existing = session.exec(
            select(KeywordTrack).where(KeywordTrack.keyword == keyword)
        ).first()
        if existing:
            err_console.print(f"[red]Keyword already tracked:[/red] '{keyword}' (id={existing.id})")
            raise typer.Exit(1)

        kw = KeywordTrack(keyword=keyword, aliases=aliases, category=category)
        session.add(kw)
        session.commit()
        session.refresh(kw)

    if is_json_mode():
        print_json({"id": kw.id, "keyword": kw.keyword, "aliases": kw.aliases, "category": kw.category})
        return

    console.print(f"  Tracking keyword '{keyword}' (id={kw.id})")


@keyword_app.command("ls")
def keyword_ls(
    active_only: Annotated[bool, typer.Option("--active", help="Show only active keywords.")] = False,
) -> None:
    """List tracked keywords."""
    from prism.models import KeywordTrack

    engine = _get_engine()
    with Session(engine) as session:
        stmt = select(KeywordTrack)
        if active_only:
            stmt = stmt.where(KeywordTrack.is_active == True)  # noqa: E712
        stmt = stmt.order_by(col(KeywordTrack.keyword))
        keywords = session.exec(stmt).all()

    if is_json_mode():
        print_json([
            {"id": kw.id, "keyword": kw.keyword, "aliases": kw.aliases,
             "category": kw.category, "is_active": kw.is_active}
            for kw in keywords
        ])
        return

    if not keywords:
        console.print("  No tracked keywords. Use `prism perception keyword add <word>` to start.")
        return

    rows = [
        [str(kw.id), kw.keyword, kw.aliases or "-", kw.category or "-",
         "yes" if kw.is_active else "no"]
        for kw in keywords
    ]
    print_table("Tracked Keywords", ["ID", "Keyword", "Aliases", "Category", "Active"], rows)


@keyword_app.command("rm")
def keyword_rm(
    keyword_id: Annotated[int, typer.Argument(help="Keyword ID to deactivate.")],
) -> None:
    """Deactivate a tracked keyword (keeps history)."""
    from prism.models import KeywordTrack

    engine = _get_engine()
    with Session(engine) as session:
        kw = session.get(KeywordTrack, keyword_id)
        if not kw:
            err_console.print(f"[red]Keyword not found:[/red] {keyword_id}")
            raise typer.Exit(1)

        kw.is_active = False
        session.add(kw)
        session.commit()

    if is_json_mode():
        print_json({"id": keyword_id, "is_active": False})
        return

    console.print(f"  Deactivated keyword '{kw.keyword}' (id={keyword_id})")


# ── Perception queries ──────────────────────────────────────────────


@app.callback(invoke_without_command=True)
def perception_default(
    ctx: typer.Context,
    limit: Annotated[int, typer.Option(help="Max results.")] = 20,
) -> None:
    """Show latest perception scores for all tracked keywords."""
    if ctx.invoked_subcommand is not None:
        return

    from prism.models import KeywordTrack, PerceptionSnapshot

    engine = _get_engine()
    with Session(engine) as session:
        keywords = session.exec(
            select(KeywordTrack).where(KeywordTrack.is_active == True)  # noqa: E712
        ).all()

        if not keywords:
            console.print("  No tracked keywords. Use `prism perception keyword add <word>` to start.")
            return

        results = []
        for kw in keywords:
            snap = session.exec(
                select(PerceptionSnapshot)
                .where(PerceptionSnapshot.keyword_id == kw.id)
                .order_by(PerceptionSnapshot.computed_at.desc())  # type: ignore[union-attr]
            ).first()
            results.append((kw, snap))

    # Sort by |perception| descending
    results.sort(key=lambda x: abs(x[1].perception) if x[1] else 0.0, reverse=True)
    results = results[:limit]

    if is_json_mode():
        print_json([
            {
                "keyword_id": kw.id,
                "keyword": kw.keyword,
                "perception": snap.perception if snap else None,
                "salience": snap.salience if snap else None,
                "valence": snap.valence if snap else None,
                "momentum": snap.momentum if snap else None,
                "cluster_count": snap.cluster_count if snap else 0,
                "source_count": snap.source_count if snap else 0,
                "computed_at": str(snap.computed_at) if snap else None,
            }
            for kw, snap in results
        ])
        return

    rows = [
        [
            str(kw.id),
            kw.keyword,
            _sign_str(snap.perception) if snap else "-",
            f"{snap.salience:.2f}" if snap else "-",
            _sign_str(snap.valence) if snap else "-",
            _sign_str(snap.momentum) if snap else "-",
            str(snap.cluster_count) if snap else "0",
            _age_str(snap.computed_at) if snap else "-",
        ]
        for kw, snap in results
    ]
    print_table(
        "Perception Pressure",
        ["ID", "Keyword", "P(K,t)", "Salience", "Valence", "Momentum", "Clusters", "Updated"],
        rows,
    )


@app.command("show")
def perception_show(
    keyword_id: Annotated[int, typer.Argument(help="Keyword ID.")],
    history: Annotated[int, typer.Option("--history", "-n", help="Number of snapshots to show.")] = 10,
) -> None:
    """Show perception detail and history for a keyword."""
    from prism.models import KeywordTrack, PerceptionSnapshot

    engine = _get_engine()
    with Session(engine) as session:
        kw = session.get(KeywordTrack, keyword_id)
        if not kw:
            err_console.print(f"[red]Keyword not found:[/red] {keyword_id}")
            raise typer.Exit(1)

        snapshots = session.exec(
            select(PerceptionSnapshot)
            .where(PerceptionSnapshot.keyword_id == keyword_id)
            .order_by(PerceptionSnapshot.computed_at.desc())  # type: ignore[union-attr]
            .limit(history)
        ).all()

    if is_json_mode():
        print_json({
            "keyword_id": kw.id,
            "keyword": kw.keyword,
            "aliases": kw.aliases,
            "category": kw.category,
            "snapshots": [
                {
                    "perception": s.perception,
                    "salience": s.salience,
                    "valence": s.valence,
                    "momentum": s.momentum,
                    "cluster_count": s.cluster_count,
                    "source_count": s.source_count,
                    "computed_at": str(s.computed_at),
                }
                for s in snapshots
            ],
        })
        return

    if not snapshots:
        console.print(f"  No perception data yet for '{kw.keyword}'. Run a perception cycle first.")
        return

    latest = snapshots[0]
    from rich.panel import Panel

    lines = [
        f"Perception P(K,t):  {latest.perception:+.4f}",
        f"Salience A(K,t):    {latest.salience:.4f}",
        f"Valence V(K,t):     {latest.valence:+.4f}",
        f"Momentum dP/dt:     {latest.momentum:+.4f}",
        f"Clusters:           {latest.cluster_count}",
        f"Sources:            {latest.source_count}",
        f"Computed:           {latest.computed_at}",
    ]
    console.print(Panel(
        "\n".join(lines),
        title=f"Perception — '{kw.keyword}'" + (f" ({kw.aliases})" if kw.aliases else ""),
    ))

    if len(snapshots) > 1:
        console.print("\n  [bold]History[/bold]")
        rows = [
            [
                _age_str(s.computed_at),
                _sign_str(s.perception),
                f"{s.salience:.2f}",
                _sign_str(s.valence),
                _sign_str(s.momentum),
                str(s.cluster_count),
            ]
            for s in snapshots
        ]
        print_table(
            f"'{kw.keyword}' History",
            ["When", "P(K,t)", "Salience", "Valence", "Momentum", "Clusters"],
            rows,
        )


@app.command("scan")
def perception_scan() -> None:
    """Manually trigger a perception scan cycle."""
    from prism.agents.r_ai import ResonanceTracker

    engine = _get_engine()
    info("  Running perception scan...")
    r_ai = ResonanceTracker()
    r_ai.process_keywords(engine)
    info("  Perception scan complete.")
