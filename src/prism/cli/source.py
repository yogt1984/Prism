"""prism source — source registry management commands."""

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

app = typer.Typer(help="Manage the news source registry — trust scores, bias labels, and RSS feeds.")


def _find_source(session: Session, url: str):  # type: ignore[no-untyped-def]
    from prism.models import Source
    return session.exec(select(Source).where(Source.url == url)).first()


@app.command("ls")
def source_ls(
    bias: Annotated[str | None, typer.Option(help="Filter by bias label.")] = None,
    min_trust: Annotated[float | None, typer.Option(help="Minimum trust score.")] = None,
    inactive: Annotated[bool, typer.Option("--inactive",
                                           help="Include deactivated sources.")] = False,
) -> None:
    """List sources with trust scores and bias labels."""
    from prism.models import Source
    engine = _get_engine()
    with Session(engine) as session:
        stmt = select(Source)
        if not inactive:
            stmt = stmt.where(Source.active.is_(True))  # type: ignore[union-attr]
        if bias:
            stmt = stmt.where(Source.bias_label == bias)
        if min_trust is not None:
            stmt = stmt.where(Source.trust_score >= min_trust)
        sources = session.exec(stmt.order_by(Source.trust_score.desc())).all()  # type: ignore[union-attr]

    rows = [
        [str(s.id), s.name, s.url, f"{s.trust_score:.2f}", s.bias_label,
         s.categories or "-", "yes" if s.active else "no"]
        for s in sources
    ]
    print_table("Sources", ["ID", "Name", "URL", "Trust", "Bias", "Categories", "Active"], rows)


@app.command("add")
def source_add(
    url: Annotated[str, typer.Argument(help="Source domain URL (e.g. reuters.com).")],
    name: Annotated[str | None, typer.Option(help="Source display name.")] = None,
    trust: Annotated[float, typer.Option(help="Trust score 0.0-1.0.")] = 0.5,
    bias: Annotated[str, typer.Option(help="Bias label.")] = "unknown",
    rss: Annotated[str, typer.Option(help="RSS feed URL.")] = "",
    categories: Annotated[str, typer.Option(help="Comma-separated categories.")] = "",
) -> None:
    """Add a new source to the registry."""
    from prism.models import BiasLabel, Source
    engine = _get_engine()

    try:
        bias_label = BiasLabel(bias)
    except ValueError:
        err_console.print(f"[red]Invalid bias label:[/red] {bias}")
        raise typer.Exit(1)

    if not 0.0 <= trust <= 1.0:
        err_console.print("[red]Trust score must be between 0.0 and 1.0[/red]")
        raise typer.Exit(1)

    with Session(engine) as session:
        existing = _find_source(session, url)
        if existing:
            err_console.print(f"[red]Source already exists:[/red] {url} (id={existing.id})")
            raise typer.Exit(1)

        source = Source(
            name=name or url,
            url=url,
            rss_url=rss,
            trust_score=trust,
            bias_label=bias_label,
            categories=categories,
        )
        session.add(source)
        session.commit()
        session.refresh(source)

    if is_json_mode():
        print_json({"id": source.id, "name": source.name, "url": source.url})
        return
    console.print(f"  [green]Added[/green] {source.name} ({source.url}, id={source.id})")


@app.command("seed")
def source_seed() -> None:
    """Seed the registry with 30 curated sources (idempotent)."""
    from prism.seed import seed_sources
    engine = _get_engine()
    count = seed_sources(engine)

    if is_json_mode():
        print_json({"seeded": count})
        return
    console.print(f"  [green]Seeded[/green] {count} new source(s)")


@app.command("trust")
def source_trust(
    url: Annotated[str, typer.Argument(help="Source domain URL.")],
    score: Annotated[float, typer.Argument(help="New trust score (0.0-1.0).")],
) -> None:
    """Update a source's trust score."""
    if not 0.0 <= score <= 1.0:
        err_console.print("[red]Trust score must be between 0.0 and 1.0[/red]")
        raise typer.Exit(1)

    engine = _get_engine()
    with Session(engine) as session:
        source = _find_source(session, url)
        if not source:
            err_console.print(f"[red]Source not found:[/red] {url}")
            raise typer.Exit(1)

        old = source.trust_score
        source.trust_score = score
        session.add(source)
        session.commit()

    if is_json_mode():
        print_json({"url": url, "old_trust": old, "new_trust": score})
        return
    console.print(f"  [green]Updated[/green] {url}: trust {old:.2f} -> {score:.2f}")


@app.command("bias")
def source_bias(
    url: Annotated[str, typer.Argument(help="Source domain URL.")],
    label: Annotated[str, typer.Argument(help="Bias label (left, center_left, center, center_right, right, unknown).")],
) -> None:
    """Update a source's bias label."""
    from prism.models import BiasLabel
    try:
        bias_label = BiasLabel(label)
    except ValueError:
        valid = ", ".join(b.value for b in BiasLabel)
        err_console.print(f"[red]Invalid bias label:[/red] {label}. Must be one of: {valid}")
        raise typer.Exit(1)

    engine = _get_engine()
    with Session(engine) as session:
        source = _find_source(session, url)
        if not source:
            err_console.print(f"[red]Source not found:[/red] {url}")
            raise typer.Exit(1)

        old = source.bias_label
        source.bias_label = bias_label
        session.add(source)
        session.commit()

    if is_json_mode():
        print_json({"url": url, "old_bias": old, "new_bias": label})
        return
    console.print(f"  [green]Updated[/green] {url}: bias {old} -> {label}")


@app.command("toggle")
def source_toggle(url: Annotated[str, typer.Argument(help="Source domain URL.")]) -> None:
    """Activate or deactivate a source."""
    engine = _get_engine()
    with Session(engine) as session:
        source = _find_source(session, url)
        if not source:
            err_console.print(f"[red]Source not found:[/red] {url}")
            raise typer.Exit(1)

        source.active = not source.active
        session.add(source)
        session.commit()
        state = "active" if source.active else "inactive"

    if is_json_mode():
        print_json({"url": url, "active": source.active})
        return
    console.print(f"  [green]Toggled[/green] {url} -> {state}")
