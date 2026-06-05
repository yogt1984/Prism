# 06_05 — CLI Commands & API Endpoints

**Parent:** 06 Source Auto-Discovery
**Depends on:** 06_04 (lifecycle logic exists to call)

---

## Objective

Expose source lifecycle management via CLI commands (for operators)
and API endpoints (for future admin UI). Includes listing candidates,
probation sources, manual promote/reject, and blocklist management.

---

## Part 1: CLI Commands

### Existing CLI Structure

The CLI uses Click (via `src/prism/cli.py` or `pyproject.toml`
entry points). Current source commands:

```
prism source add <name> <url> [--rss-url] [--trust] [--bias]
prism source ls
```

### New Commands

All new commands go under the `prism source` group.

#### `prism source candidates`

```python
@source_group.command("candidates")
@click.option("--limit", default=20, help="Max results")
def source_candidates(limit: int):
    """List candidate sources awaiting evaluation."""
    engine = get_engine()
    with Session(engine) as session:
        sources = session.exec(
            select(Source)
            .where(Source.status == SourceStatus.CANDIDATE)
            .order_by(Source.sighting_count.desc())
            .limit(limit)
        ).all()

    if not sources:
        click.echo("No candidate sources.")
        return

    click.echo(f"{'Domain':<30} {'Sightings':>9} {'RSS':>4} {'Discovered':>12}")
    click.echo("-" * 60)
    for s in sources:
        rss = "Yes" if s.rss_url else "No"
        click.echo(f"{s.url:<30} {s.sighting_count:>9} {rss:>4} {s.discovered_via:>12}")
```

#### `prism source probation`

```python
@source_group.command("probation")
def source_probation():
    """List sources in probation with validation stats."""
    engine = get_engine()
    with Session(engine) as session:
        sources = session.exec(
            select(Source).where(Source.status == SourceStatus.PROBATION)
        ).all()

    if not sources:
        click.echo("No sources in probation.")
        return

    click.echo(f"{'Domain':<25} {'Trust':>5} {'Valid':>5} {'Fail':>5} {'Ratio':>6} {'Days':>4}")
    click.echo("-" * 58)
    for s in sources:
        total = s.articles_validated + s.articles_failed
        ratio = s.articles_validated / max(total, 1)
        days = (datetime.now(UTC) - s.probation_start).days if s.probation_start else 0
        click.echo(
            f"{s.url:<25} {s.trust_score:>5.2f} "
            f"{s.articles_validated:>5} {s.articles_failed:>5} "
            f"{ratio:>5.0%} {days:>4}"
        )
```

#### `prism source evaluate`

```python
@source_group.command("evaluate")
def source_evaluate():
    """Manually trigger probation evaluation cycle."""
    from prism.agents.source_lifecycle import evaluate_probation_sources
    engine = get_engine()
    results = evaluate_probation_sources(engine)
    click.echo(
        f"Evaluation complete: "
        f"{results['promoted']} promoted, "
        f"{results['rejected']} rejected, "
        f"{results['reset']} reset"
    )
```

#### `prism source promote <id>`

```python
@source_group.command("promote")
@click.argument("source_id", type=int)
def source_promote(source_id: int):
    """Manually promote a source to trusted status."""
    engine = get_engine()
    with Session(engine) as session:
        source = session.get(Source, source_id)
        if source is None:
            click.echo(f"Source {source_id} not found.", err=True)
            raise SystemExit(1)
        if source.status == SourceStatus.SEED:
            click.echo(f"Source '{source.name}' is a seed — already trusted.", err=True)
            raise SystemExit(1)

        source.status = SourceStatus.TRUSTED
        source.trust_score = 0.5
        source.active = True
        source.last_evaluated = datetime.now(UTC)
        session.commit()

    click.echo(f"Source '{source.name}' ({source.url}) promoted to trusted.")
```

#### `prism source reject <id>`

```python
@source_group.command("reject")
@click.argument("source_id", type=int)
@click.option("--reason", required=True, help="Rejection reason")
def source_reject(source_id: int, reason: str):
    """Manually reject a source."""
    engine = get_engine()
    with Session(engine) as session:
        source = session.get(Source, source_id)
        if source is None:
            click.echo(f"Source {source_id} not found.", err=True)
            raise SystemExit(1)
        if source.status == SourceStatus.SEED:
            click.echo(f"Cannot reject seed source '{source.name}'.", err=True)
            raise SystemExit(1)

        source.status = SourceStatus.REJECTED
        source.active = False
        source.trust_score = 0.0
        source.rejection_reason = reason
        source.last_evaluated = datetime.now(UTC)
        session.commit()

    click.echo(f"Source '{source.name}' rejected: {reason}")
```

#### `prism source blocklist add <domain>`

```python
@source_group.group("blocklist")
def blocklist_group():
    """Manage the domain blocklist."""
    pass

@blocklist_group.command("add")
@click.argument("domain")
def blocklist_add(domain: str):
    """Add a domain to the discovery blocklist."""
    from pathlib import Path
    path = Path("data/source_blocklist.txt")
    normalized = domain.lower().removeprefix("www.")

    # Check if already blocked
    existing = set()
    if path.exists():
        existing = {
            line.strip() for line in path.read_text().splitlines()
            if line.strip() and not line.startswith("#")
        }

    if normalized in existing:
        click.echo(f"{normalized} is already blocked.")
        return

    with path.open("a") as f:
        f.write(f"\n{normalized}")

    # Reload cached blocklist
    from prism.agents.blocklist import reload_blocklist
    reload_blocklist()

    click.echo(f"Added {normalized} to blocklist.")

@blocklist_group.command("ls")
def blocklist_ls():
    """List blocked domains."""
    from prism.agents.blocklist import load_blocklist
    domains = sorted(load_blocklist())
    if not domains:
        click.echo("Blocklist is empty.")
        return
    for d in domains:
        click.echo(f"  {d}")
    click.echo(f"\n{len(domains)} domains blocked.")
```

---

## Part 2: API Endpoints

Add to `src/prism/api/routes.py`. These are admin-level endpoints
gated behind API key authentication.

### `GET /sources/candidates`

```python
@router.get("/sources/candidates")
def list_candidate_sources(
    limit: int = Query(default=20, le=100),
    session: Session = Depends(_get_session),
) -> list[SourceOut]:
    """List candidate sources ordered by sighting count."""
    result = session.exec(
        select(Source)
        .where(Source.status == "candidate")
        .order_by(col(Source.sighting_count).desc())
        .limit(limit)
    )
    return [SourceOut.model_validate(s) for s in result.all()]
```

### `GET /sources/probation`

```python
@router.get("/sources/probation")
def list_probation_sources(
    session: Session = Depends(_get_session),
) -> list[SourceOut]:
    """List sources currently in probation with validation stats."""
    result = session.exec(
        select(Source).where(Source.status == "probation")
    )
    return [SourceOut.model_validate(s) for s in result.all()]
```

### `POST /sources/{source_id}/promote`

```python
@router.post("/sources/{source_id}/promote")
def promote_source(
    source_id: int,
    user: User = Depends(require_api_key),
    session: Session = Depends(_get_session),
) -> SourceOut:
    """Manually promote a source to trusted (admin)."""
    source = session.get(Source, source_id)
    if source is None:
        raise HTTPException(status_code=404, detail="Source not found")
    if source.status == "seed":
        raise HTTPException(status_code=409, detail="Seed sources cannot be promoted")

    source.status = SourceStatus.TRUSTED
    source.trust_score = 0.5
    source.active = True
    source.last_evaluated = datetime.now(UTC)
    session.commit()
    session.refresh(source)
    return SourceOut.model_validate(source)
```

### `POST /sources/{source_id}/reject`

```python
class RejectBody(BaseModel):
    reason: str

@router.post("/sources/{source_id}/reject")
def reject_source(
    source_id: int,
    body: RejectBody,
    user: User = Depends(require_api_key),
    session: Session = Depends(_get_session),
) -> SourceOut:
    """Manually reject a source (admin)."""
    source = session.get(Source, source_id)
    if source is None:
        raise HTTPException(status_code=404, detail="Source not found")
    if source.status == "seed":
        raise HTTPException(status_code=409, detail="Seed sources cannot be rejected")

    source.status = SourceStatus.REJECTED
    source.active = False
    source.trust_score = 0.0
    source.rejection_reason = body.reason
    source.last_evaluated = datetime.now(UTC)
    session.commit()
    session.refresh(source)
    return SourceOut.model_validate(source)
```

### SourceOut Schema Update

Add lifecycle fields to the existing `SourceOut` response model:

```python
class SourceOut(BaseModel):
    id: int
    name: str
    url: str
    rss_url: str
    trust_score: float
    bias_label: str
    categories: str
    active: bool
    # New lifecycle fields
    status: str
    discovered_via: str
    sighting_count: int
    articles_validated: int
    articles_failed: int
    probation_start: datetime | None
    last_evaluated: datetime | None
    rejection_reason: str
```

---

## Metrics (New)

Add to `src/prism/metrics.py` (from 05_02):

```python
source_candidates_discovered_total = Counter(
    "prism_source_candidates_discovered_total",
    "New candidate sources discovered",
)
source_promoted_total = Counter(
    "prism_source_promoted_total",
    "Sources promoted to trusted",
)
source_rejected_total = Counter(
    "prism_source_rejected_total",
    "Sources rejected after probation",
)
source_probation_active = Gauge(
    "prism_source_probation_active",
    "Sources currently in probation",
)
```

Increment in `source_lifecycle.py` promote/reject functions, and
update the gauge in the gauge refresh job (05_03).

---

## Acceptance Criteria

| # | Criterion | Verification |
|---|-----------|--------------|
| 1 | `prism source candidates` lists candidates | Create candidates, run, verify output |
| 2 | `prism source probation` shows stats | Create probation source, verify columns |
| 3 | `prism source evaluate` triggers evaluation | Run with eligible sources, verify output |
| 4 | `prism source promote 5` promotes source | Verify status change in DB |
| 5 | `prism source reject 5 --reason "..."` rejects | Verify status + reason in DB |
| 6 | Promoting seed source fails with error | Attempt, verify error message |
| 7 | `prism source blocklist add x.com` appends | Verify file updated |
| 8 | `prism source blocklist ls` lists all | Verify output matches file |
| 9 | `GET /sources/candidates` returns JSON | curl, verify response schema |
| 10 | `GET /sources/probation` returns probation sources | curl, verify |
| 11 | `POST /sources/{id}/promote` requires auth | Call without API key, verify 401 |
| 12 | `POST /sources/{id}/reject` stores reason | Call with body, verify rejection_reason |
| 13 | Reject seed via API returns 409 | Attempt, verify error response |
| 14 | SourceOut includes lifecycle fields | Verify response has `status`, `sighting_count` etc. |

---

## Testing Strategy

### CLI Tests

```python
def test_source_candidates_command(runner, populated_db):
    """CLI lists candidate sources."""
    result = runner.invoke(cli, ["source", "candidates"])
    assert result.exit_code == 0
    assert "Domain" in result.output

def test_source_promote_command(runner, engine):
    """CLI promotes a source."""
    # Create candidate source
    result = runner.invoke(cli, ["source", "promote", "1"])
    assert "promoted to trusted" in result.output

def test_source_reject_seed_fails(runner, populated_db):
    """CLI rejects promoting seed source."""
    result = runner.invoke(cli, ["source", "promote", "1"])  # seed source
    assert result.exit_code != 0
    assert "seed" in result.output.lower()

def test_blocklist_add(runner, tmp_path):
    """CLI adds domain to blocklist."""
    result = runner.invoke(cli, ["source", "blocklist", "add", "spam.com"])
    assert "Added spam.com" in result.output
```

### API Tests

```python
def test_get_candidates(client):
    """GET /sources/candidates returns candidates."""
    res = client.get("/sources/candidates")
    assert res.status_code == 200
    assert isinstance(res.json(), list)

def test_promote_source_api(client, api_key):
    """POST /sources/{id}/promote promotes source."""
    res = client.post("/sources/1/promote", headers={"X-API-Key": api_key})
    assert res.status_code == 200
    assert res.json()["status"] == "trusted"

def test_reject_source_api(client, api_key):
    """POST /sources/{id}/reject stores reason."""
    res = client.post(
        "/sources/1/reject",
        headers={"X-API-Key": api_key},
        json={"reason": "Unreliable content"},
    )
    assert res.status_code == 200
    assert res.json()["rejection_reason"] == "Unreliable content"

def test_reject_seed_api_returns_409(client, api_key, populated_db):
    """Cannot reject seed source via API."""
    # Get a seed source ID
    res = client.post(
        "/sources/1/reject",
        headers={"X-API-Key": api_key},
        json={"reason": "test"},
    )
    assert res.status_code == 409
```

---

## Files Changed

| File | Change |
|------|--------|
| `src/prism/cli.py` | Add 6 new source subcommands + blocklist group |
| `src/prism/api/routes.py` | Add 4 new endpoints, update SourceOut |
| `src/prism/metrics.py` | Add 4 source lifecycle metrics |
| `tests/test_cli_source.py` | New: CLI command tests |
| `tests/test_api_sources.py` | New: API endpoint tests |
