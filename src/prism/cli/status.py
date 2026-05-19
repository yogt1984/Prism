"""prism status — pipeline health dashboard."""

import os
import time
from datetime import UTC, datetime
from typing import Annotated

import typer
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from sqlmodel import Session, func, select

from prism.cli._fmt import console, is_json_mode, print_json

app = typer.Typer(help="Pipeline status dashboard.")


def _get_engine():  # type: ignore[no-untyped-def]
    from prism.db import get_engine
    return get_engine()


def _collect_stats(engine) -> dict:  # type: ignore[no-untyped-def, type-arg]
    """Gather all dashboard metrics from the database."""
    from prism.models import (
        Article,
        Briefing,
        Perspective,
        Source,
        StoryCluster,
        User,
    )

    with Session(engine) as session:
        # Cluster counts
        total_clusters = session.exec(
            select(func.count(StoryCluster.id))
        ).one()
        by_status = dict(session.exec(
            select(StoryCluster.status, func.count(StoryCluster.id))
            .group_by(StoryCluster.status)
        ).all())

        # Other counts
        total_articles = session.exec(select(func.count(Article.id))).one()
        total_perspectives = session.exec(
            select(func.count(Perspective.id))
        ).one()
        total_sources = session.exec(select(func.count(Source.id))).one()
        active_sources = session.exec(
            select(func.count(Source.id)).where(Source.active.is_(True))  # type: ignore[union-attr]
        ).one()
        total_users = session.exec(select(func.count(User.id))).one()
        pro_users = session.exec(
            select(func.count(User.id)).where(User.is_pro.is_(True))  # type: ignore[union-attr]
        ).one()

        # Recent briefings
        total_briefings = session.exec(select(func.count(Briefing.id))).one()
        sent_briefings = session.exec(
            select(func.count(Briefing.id)).where(Briefing.sent.is_(True))  # type: ignore[union-attr]
        ).one()
        last_briefing = session.exec(
            select(Briefing.created_at)
            .order_by(Briefing.created_at.desc())  # type: ignore[union-attr]
            .limit(1)
        ).first()

        # Category distribution
        cat_rows = session.exec(select(StoryCluster.categories)).all()

        # DB file size
        db_url = str(engine.url)
        db_path = db_url.replace("sqlite:///", "")
        db_size = os.path.getsize(db_path) if os.path.exists(db_path) else 0

    cat_counts: dict[str, int] = {}
    for cats_str in cat_rows:
        if cats_str:
            for cat in cats_str.split(","):
                cat = cat.strip()
                if cat:
                    cat_counts[cat] = cat_counts.get(cat, 0) + 1

    return {
        "total_clusters": total_clusters,
        "by_status": by_status,
        "total_articles": total_articles,
        "total_perspectives": total_perspectives,
        "total_sources": total_sources,
        "active_sources": active_sources,
        "total_users": total_users,
        "pro_users": pro_users,
        "total_briefings": total_briefings,
        "sent_briefings": sent_briefings,
        "last_briefing": str(last_briefing) if last_briefing else None,
        "categories": cat_counts,
        "db_size_mb": round(db_size / (1024 * 1024), 2),
        "timestamp": datetime.now(UTC).isoformat(),
    }


def _render_dashboard(stats: dict) -> Panel:  # type: ignore[type-arg]
    """Build a Rich panel from stats dict."""
    # Pipeline table
    pipeline = Table(show_header=True, show_lines=False, box=None, padding=(0, 2))
    pipeline.add_column("Metric", style="bold")
    pipeline.add_column("Value", justify="right")

    pipeline.add_row("Clusters", str(stats["total_clusters"]))
    for status, count in sorted(stats["by_status"].items()):
        pipeline.add_row(f"  {status}", str(count))
    pipeline.add_row("Articles", str(stats["total_articles"]))
    pipeline.add_row("Perspectives", str(stats["total_perspectives"]))
    pipeline.add_row(
        "Sources",
        f"{stats['active_sources']} active / {stats['total_sources']} total",
    )
    pipeline.add_row(
        "Users",
        f"{stats['total_users']} ({stats['pro_users']} pro)",
    )
    pipeline.add_row(
        "Briefings",
        f"{stats['sent_briefings']} sent / {stats['total_briefings']} total",
    )
    if stats["last_briefing"]:
        pipeline.add_row("Last briefing", stats["last_briefing"][:19])
    pipeline.add_row("DB size", f"{stats['db_size_mb']} MB")

    # Category bars
    cat_lines = []
    if stats["categories"]:
        sorted_cats = sorted(
            stats["categories"].items(), key=lambda x: x[1], reverse=True,
        )
        max_count = sorted_cats[0][1] if sorted_cats else 1
        total = stats["total_clusters"] or 1
        for cat, count in sorted_cats:
            bar_len = int(count / max_count * 20)
            pct = count / total * 100
            cat_lines.append(f"  {cat:<14s} {'#' * bar_len:<20s} {pct:>4.0f}%")

    if cat_lines:
        cat_text = "\n[bold]Categories[/bold]\n" + "\n".join(cat_lines)
    else:
        cat_text = ""


    # Combine into a panel
    content = pipeline
    title = f"Prism Pipeline Status  ({stats['timestamp'][:19]})"
    return Panel(content, title=title, subtitle=cat_text if cat_lines else None)


@app.callback(invoke_without_command=True)
def status(
    watch: Annotated[
        bool, typer.Option("--watch", help="Continuous refresh every 5 seconds.")
    ] = False,
) -> None:
    """Show pipeline health dashboard."""
    engine = _get_engine()

    if is_json_mode():
        print_json(_collect_stats(engine))
        return

    if watch:
        try:
            with Live(
                _render_dashboard(_collect_stats(engine)),
                refresh_per_second=0.2,
                console=console,
            ) as live:
                while True:
                    time.sleep(5)
                    live.update(_render_dashboard(_collect_stats(engine)))
        except KeyboardInterrupt:
            console.print("\n  [yellow]Stopped.[/yellow]")
    else:
        console.print(_render_dashboard(_collect_stats(engine)))
