"""prism story — story cluster inspection commands."""

import json as _json
from datetime import UTC, datetime
from typing import Annotated

import typer
from sqlmodel import Session, func, select

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

app = typer.Typer(help="Inspect discovered story clusters, articles, and perspectives.")


def _age_str(dt: datetime) -> str:
    """Human-readable age string."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    delta = datetime.now(UTC) - dt
    hours = delta.total_seconds() / 3600
    if hours < 1:
        return f"{int(delta.total_seconds() / 60)}m ago"
    if hours < 24:
        return f"{int(hours)}h ago"
    return f"{int(hours / 24)}d ago"


@app.command("ls")
def story_ls(
    status: Annotated[str | None, typer.Option(help="Filter by status (raw|analyzed).")] = None,
    category: Annotated[str | None, typer.Option(help="Filter by category.")] = None,
    sort: Annotated[str, typer.Option(help="Sort field: first_seen (default) or resonance.")] = "first_seen",
    limit: Annotated[int, typer.Option(help="Max rows to show.")] = 20,
) -> None:
    """List recent story clusters."""
    from prism.models import StoryCluster
    engine = _get_engine()
    with Session(engine) as session:
        stmt = select(StoryCluster)
        if status:
            stmt = stmt.where(StoryCluster.status == status)
        if category:
            stmt = stmt.where(StoryCluster.categories.contains(category))  # type: ignore[union-attr]
        if sort == "resonance":
            stmt = stmt.order_by(StoryCluster.resonance_score.desc())  # type: ignore[union-attr]
        else:
            stmt = stmt.order_by(StoryCluster.first_seen.desc())  # type: ignore[union-attr]
        clusters = session.exec(stmt.limit(limit)).all()

    rows = [
        [str(c.id), c.headline[:60] or "(no headline)", c.status,
         str(c.article_count), f"{c.resonance_score:.1f}",
         c.categories or "-", _age_str(c.first_seen)]
        for c in clusters
    ]
    print_table("Stories", ["ID", "Headline", "Status", "Articles", "Resonance", "Categories", "Age"], rows)


@app.command("show")
def story_show(cluster_id: Annotated[int, typer.Argument(help="Story cluster ID.")]) -> None:
    """Show full cluster details with perspectives."""
    from prism.models import Article, Perspective, Source, StoryCluster
    engine = _get_engine()
    with Session(engine) as session:
        cluster = session.get(StoryCluster, cluster_id)
        if not cluster:
            err_console.print(f"[red]Cluster not found:[/red] {cluster_id}")
            raise typer.Exit(1)

        articles = session.exec(
            select(Article).where(Article.cluster_id == cluster_id)
        ).all()
        perspectives = session.exec(
            select(Perspective).where(Perspective.cluster_id == cluster_id)
        ).all()

        # Resolve source names for perspectives
        source_ids = {p.source_id for p in perspectives} | {a.source_id for a in articles}
        sources = {s.id: s for s in session.exec(
            select(Source).where(Source.id.in_(source_ids))  # type: ignore[union-attr]
        ).all()} if source_ids else {}

    if is_json_mode():
        print_json({
            "id": cluster.id,
            "headline": cluster.headline,
            "summary": cluster.summary,
            "status": cluster.status,
            "categories": cluster.categories,
            "article_count": cluster.article_count,
            "first_seen": str(cluster.first_seen),
            "articles": [{"id": a.id, "title": a.title, "url": a.url,
                          "source": sources.get(a.source_id, None)
                          and sources[a.source_id].name}
                         for a in articles],
            "perspectives": [
                {"source": sources.get(p.source_id, None) and sources[p.source_id].name,
                 "bias": p.bias_label, "sentiment": p.sentiment,
                 "summary": p.summary,
                 "claims": _json.loads(p.key_claims) if p.key_claims else []}
                for p in perspectives
            ],
        })
        return

    from rich.panel import Panel
    # Header
    console.print(Panel(
        f"{cluster.headline or '(no headline)'}\n"
        f"Status: {cluster.status} | Categories: {cluster.categories or '-'} | "
        f"Articles: {cluster.article_count}\n"
        f"First seen: {cluster.first_seen} ({_age_str(cluster.first_seen)})",
        title=f"Cluster #{cluster.id}",
    ))

    # Summary
    if cluster.summary:
        console.print(f"\n  [bold]Summary[/bold]\n  {cluster.summary}\n")

    # Articles
    if articles:
        console.print("  [bold]Articles[/bold]")
        for a in articles:
            src_name = sources[a.source_id].name if a.source_id in sources else "?"
            console.print(f"    - {a.title} [dim]({src_name})[/dim]")
        console.print()

    # Perspectives
    if perspectives:
        lines = []
        for p in perspectives:
            src_name = sources[p.source_id].name if p.source_id in sources else "?"
            bias = p.bias_label
            sent_bar = _sentiment_bar(p.sentiment)
            hdr = f"  [bold]{src_name}[/bold] [{bias}]"
            lines.append(f"{hdr}  sentiment: {sent_bar} {p.sentiment:.1f}")
            lines.append(f"  {p.summary}")
            claims = _json.loads(p.key_claims) if p.key_claims else []
            for claim in claims:
                lines.append(f"  [dim]- {claim}[/dim]")
            lines.append("")
        console.print(Panel("\n".join(lines), title="Perspectives"))


def _sentiment_bar(value: float) -> str:
    """Render a small ASCII sentiment bar from -1 to 1."""
    # Map -1..1 to 0..10
    pos = int((value + 1) * 5)
    pos = max(0, min(10, pos))
    return "-" * pos + "*" + "-" * (10 - pos)


@app.command("stats")
def story_stats() -> None:
    """Show aggregate story statistics."""
    from prism.models import Article, Perspective, StoryCluster
    engine = _get_engine()
    with Session(engine) as session:
        total = session.exec(select(func.count(StoryCluster.id))).one()
        by_status = session.exec(
            select(StoryCluster.status, func.count(StoryCluster.id))
            .group_by(StoryCluster.status)
        ).all()
        article_count = session.exec(select(func.count(Article.id))).one()
        perspective_count = session.exec(select(func.count(Perspective.id))).one()

        # Category distribution — categories is comma-separated, so split and count
        clusters = session.exec(select(StoryCluster.categories)).all()

    cat_counts: dict[str, int] = {}
    for cats_str in clusters:
        if cats_str:
            for cat in cats_str.split(","):
                cat = cat.strip()
                if cat:
                    cat_counts[cat] = cat_counts.get(cat, 0) + 1

    status_dict = {s: c for s, c in by_status}
    stats = {
        "total_clusters": total,
        "by_status": status_dict,
        "total_articles": article_count,
        "total_perspectives": perspective_count,
        "categories": cat_counts,
    }

    if is_json_mode():
        print_json(stats)
        return

    console.print("\n  [bold]Story Statistics[/bold]\n")
    console.print(f"  Clusters: {total}")
    for s, c in sorted(status_dict.items()):
        console.print(f"    {s}: {c}")
    console.print(f"  Articles: {article_count}")
    console.print(f"  Perspectives: {perspective_count}")

    if cat_counts:
        console.print("\n  [bold]Categories[/bold]")
        sorted_cats = sorted(cat_counts.items(), key=lambda x: x[1], reverse=True)
        max_count = sorted_cats[0][1] if sorted_cats else 1
        for cat, count in sorted_cats:
            bar_len = int(count / max_count * 20)
            pct = count / total * 100 if total else 0
            console.print(f"    {cat:<14s} {'#' * bar_len} {pct:.0f}%")
    console.print()


@app.command("resonance")
def story_resonance(
    cluster_id: Annotated[int, typer.Argument(help="Story cluster ID.")],
) -> None:
    """Show full resonance breakdown for a story cluster."""
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
