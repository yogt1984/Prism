"""prism source — source registry management commands."""

from datetime import UTC, datetime
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

blocklist_app = typer.Typer(help="Manage the domain blocklist.")

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


@app.command("candidates")
def source_candidates(
    limit: Annotated[int, typer.Option(help="Max results.")] = 20,
) -> None:
    """List candidate sources awaiting evaluation."""
    from prism.models import Source, SourceStatus
    engine = _get_engine()
    with Session(engine) as session:
        sources = session.exec(
            select(Source)
            .where(Source.status == SourceStatus.CANDIDATE)
            .order_by(Source.sighting_count.desc())  # type: ignore[union-attr]
            .limit(limit)
        ).all()

    if not sources:
        console.print("No candidate sources.")
        return

    rows = [
        [s.url, str(s.sighting_count), "Yes" if s.rss_url else "No", s.discovered_via or "-"]
        for s in sources
    ]
    print_table("Candidates", ["Domain", "Sightings", "RSS", "Discovered"], rows)


@app.command("probation")
def source_probation() -> None:
    """List sources in probation with validation stats."""
    from prism.models import Source, SourceStatus
    engine = _get_engine()
    with Session(engine) as session:
        sources = session.exec(
            select(Source).where(Source.status == SourceStatus.PROBATION)
        ).all()

    if not sources:
        console.print("No sources in probation.")
        return

    rows = []
    for s in sources:
        total = s.articles_validated + s.articles_failed
        ratio = s.articles_validated / max(total, 1)
        if s.probation_start:
            ps = s.probation_start.replace(tzinfo=UTC) if s.probation_start.tzinfo is None else s.probation_start
            days = (datetime.now(UTC) - ps).days
        else:
            days = 0
        rows.append([
            s.url, f"{s.trust_score:.2f}",
            str(s.articles_validated), str(s.articles_failed),
            f"{ratio:.0%}", str(days),
        ])
    print_table("Probation", ["Domain", "Trust", "Valid", "Fail", "Ratio", "Days"], rows)


@app.command("evaluate")
def source_evaluate() -> None:
    """Manually trigger probation evaluation cycle."""
    from prism.agents.source_lifecycle import evaluate_probation_sources
    engine = _get_engine()
    results = evaluate_probation_sources(engine)
    console.print(
        f"Evaluation complete: "
        f"{results['promoted']} promoted, "
        f"{results['rejected']} rejected, "
        f"{results['reset']} reset"
    )


@app.command("promote")
def source_promote(
    source_id: Annotated[int, typer.Argument(help="Source ID to promote.")],
) -> None:
    """Manually promote a source to trusted status."""
    from prism.models import Source, SourceStatus
    engine = _get_engine()
    with Session(engine) as session:
        source = session.get(Source, source_id)
        if source is None:
            err_console.print(f"[red]Source {source_id} not found.[/red]")
            raise typer.Exit(1)
        if source.status == SourceStatus.SEED:
            err_console.print(f"[red]Source '{source.name}' is a seed — already trusted.[/red]")
            raise typer.Exit(1)

        source.status = SourceStatus.TRUSTED
        source.trust_score = 0.5
        source.active = True
        source.last_evaluated = datetime.now(UTC)
        session.commit()
        name, url = source.name, source.url

    console.print(f"  [green]Promoted[/green] '{name}' ({url}) to trusted.")


@app.command("reject")
def source_reject(
    source_id: Annotated[int, typer.Argument(help="Source ID to reject.")],
    reason: Annotated[str, typer.Option(help="Rejection reason.")] = "",
) -> None:
    """Manually reject a source."""
    from prism.models import Source, SourceStatus
    if not reason:
        err_console.print("[red]--reason is required.[/red]")
        raise typer.Exit(1)

    engine = _get_engine()
    with Session(engine) as session:
        source = session.get(Source, source_id)
        if source is None:
            err_console.print(f"[red]Source {source_id} not found.[/red]")
            raise typer.Exit(1)
        if source.status == SourceStatus.SEED:
            err_console.print(f"[red]Cannot reject seed source '{source.name}'.[/red]")
            raise typer.Exit(1)

        source.status = SourceStatus.REJECTED
        source.active = False
        source.trust_score = 0.0
        source.rejection_reason = reason
        source.last_evaluated = datetime.now(UTC)
        session.commit()
        name = source.name

    console.print(f"  [red]Rejected[/red] '{name}': {reason}")


# ── Blocklist subcommands ──────────────────────────────────────────


@blocklist_app.command("add")
def blocklist_add(
    domain: Annotated[str, typer.Argument(help="Domain to block.")],
) -> None:
    """Add a domain to the discovery blocklist."""
    from pathlib import Path
    path = Path("data/source_blocklist.txt")
    normalized = domain.lower().removeprefix("www.")

    existing: set[str] = set()
    if path.exists():
        existing = {
            line.strip().lower().removeprefix("www.")
            for line in path.read_text().splitlines()
            if line.strip() and not line.startswith("#")
        }

    if normalized in existing:
        console.print(f"{normalized} is already blocked.")
        return

    with path.open("a") as f:
        f.write(f"\n{normalized}")

    from prism.agents.blocklist import reload_blocklist
    reload_blocklist()
    console.print(f"  [green]Added[/green] {normalized} to blocklist.")


@blocklist_app.command("ls")
def blocklist_ls() -> None:
    """List blocked domains."""
    from prism.agents.blocklist import load_blocklist
    domains = sorted(load_blocklist())
    if not domains:
        console.print("Blocklist is empty.")
        return
    for d in domains:
        console.print(f"  {d}")
    console.print(f"\n{len(domains)} domains blocked.")


app.add_typer(blocklist_app, name="blocklist")
