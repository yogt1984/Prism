"""prism resonance — query media impact scores by keyword or cluster ID."""

import json as _json
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
    is_json_mode,
    print_json,
    print_table,
)

app = typer.Typer(help="Query Resonance media-impact scores for topics and stories.")


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


def _momentum_str(val: float) -> str:
    if val > 0:
        return f"+{val:.2f}"
    return f"{val:.2f}"


@app.callback(invoke_without_command=True)
def resonance_default(
    ctx: typer.Context,
    keyword: Annotated[str | None, typer.Option("--keyword", "-k", help="Search stories by keyword in headline/summary.")] = None,
    sort: Annotated[str, typer.Option(help="Sort: resonance (default) or momentum.")] = "resonance",
    limit: Annotated[int, typer.Option(help="Max results.")] = 20,
) -> None:
    """Show top stories ranked by Resonance score, optionally filtered by keyword."""
    if ctx.invoked_subcommand is not None:
        return

    from prism.models import StoryCluster, TopicResonance
    engine = _get_engine()
    with Session(engine) as session:
        stmt = (
            select(StoryCluster, TopicResonance)
            .join(TopicResonance, StoryCluster.id == TopicResonance.cluster_id)
        )

        if keyword:
            kw = f"%{keyword}%"
            stmt = stmt.where(
                (StoryCluster.headline.like(kw))  # type: ignore[union-attr]
                | (StoryCluster.summary.like(kw))  # type: ignore[union-attr]
            )

        if sort == "momentum":
            stmt = stmt.order_by(col(TopicResonance.momentum).desc())
        else:
            stmt = stmt.order_by(col(TopicResonance.resonance).desc())

        stmt = stmt.limit(limit)
        results = session.exec(stmt).all()

    if is_json_mode():
        print_json([
            {
                "id": cluster.id,
                "headline": cluster.headline,
                "resonance": tr.resonance,
                "momentum": tr.momentum,
                "peak_resonance": tr.peak_resonance,
                "mention_count": tr.mention_count,
                "source_count": tr.source_count,
                "breadth": tr.breadth,
                "categories": cluster.categories,
                "first_seen": str(cluster.first_seen),
            }
            for cluster, tr in results
        ])
        return

    if not results:
        if keyword:
            console.print(f"  No stories matching '{keyword}' with resonance data.")
        else:
            console.print("  No resonance data yet. Run a discovery + analysis cycle first.")
        return

    rows = [
        [
            str(cluster.id),
            cluster.headline[:50] or "(no headline)",
            f"{tr.resonance:.2f}",
            _momentum_str(tr.momentum),
            str(tr.mention_count),
            str(tr.source_count),
            cluster.categories or "-",
            _age_str(cluster.first_seen),
        ]
        for cluster, tr in results
    ]

    title = f"Resonance — '{keyword}'" if keyword else "Resonance — Top Stories"
    print_table(title, ["ID", "Headline", "Resonance", "Momentum", "Mentions", "Sources", "Categories", "Age"], rows)


@app.command("show")
def resonance_show(
    cluster_id: Annotated[int, typer.Argument(help="Story cluster ID.")],
) -> None:
    """Show full resonance breakdown for a story."""
    from prism.models import StoryCluster, TopicResonance
    engine = _get_engine()
    with Session(engine) as session:
        cluster = session.get(StoryCluster, cluster_id)
        if not cluster:
            err_console.print(f"[red]Cluster not found:[/red] {cluster_id}")
            raise typer.Exit(1)

        tr = session.exec(
            select(TopicResonance).where(TopicResonance.cluster_id == cluster_id)
        ).first()

    if is_json_mode():
        if tr is None:
            print_json({"cluster_id": cluster_id, "resonance": None,
                        "message": "Resonance not yet computed"})
        else:
            print_json({
                "cluster_id": tr.cluster_id,
                "resonance": tr.resonance,
                "momentum": tr.momentum,
                "peak_resonance": tr.peak_resonance,
                "mention_count": tr.mention_count,
                "source_count": tr.source_count,
                "authority_weighted_sum": tr.authority_weighted_sum,
                "breadth": tr.breadth,
                "window_hours": tr.window_hours,
                "computed_at": str(tr.computed_at),
            })
        return

    if tr is None:
        console.print(f"  No resonance data for cluster #{cluster_id}.")
        return

    from rich.panel import Panel
    lines = [
        f"Resonance:             {tr.resonance:.3f}",
        f"Momentum:              {tr.momentum:+.3f}",
        f"Peak Resonance:        {tr.peak_resonance:.3f}",
        f"Mention Count:         {tr.mention_count}",
        f"Source Count:           {tr.source_count}",
        f"Authority Weighted Sum: {tr.authority_weighted_sum:.3f}",
        f"Breadth:               {tr.breadth:.3f}",
        f"Window (hours):        {tr.window_hours}",
        f"Computed At:           {tr.computed_at}",
    ]
    console.print(Panel(
        "\n".join(lines),
        title=f"Resonance — {cluster.headline or f'Cluster #{cluster_id}'}",
    ))
