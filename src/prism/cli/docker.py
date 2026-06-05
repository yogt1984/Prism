"""Docker build, run, and deploy commands."""

import os
import subprocess
import sys
import time
from pathlib import Path

import typer
from rich.console import Console

app = typer.Typer(help="Docker build, run & deploy.", no_args_is_help=True)
console = Console()

# ── Paths ────────────────────────────────────────────────────────────────────

ROOT = Path(__file__).resolve().parents[3]  # repo root
COMPOSE = "docker compose"
COMPOSE_PROD = f"{COMPOSE} -f docker-compose.yml -f docker-compose.prod.yml"


def _run(cmd: str, cwd: Path = ROOT) -> int:
    return subprocess.run(cmd, shell=True, cwd=cwd).returncode


def _run_or_exit(cmd: str, msg: str = "Command failed") -> None:
    if _run(cmd) != 0:
        console.print(f"  [red]✗[/red]  {msg}")
        raise typer.Exit(1)


def _require_host() -> str:
    host = os.environ.get("PRISM_DEPLOY_HOST", "")
    if not host:
        console.print("  [red]✗[/red]  Set PRISM_DEPLOY_HOST or pass --host")
        raise typer.Exit(1)
    return host


# ── Dev ──────────────────────────────────────────────────────────────────────

@app.command()
def dev(
    service: str = typer.Argument(
        None, help="Service to start: backend, frontend, or omit for both.",
    ),
) -> None:
    """Start dev stack with hot-reload."""
    svc_map = {"backend": "prism", "frontend": "frontend"}
    target = svc_map.get(service, "") if service else ""
    _run(f"{COMPOSE} up --build {target}".strip())


@app.command()
def down() -> None:
    """Stop all services."""
    _run(f"{COMPOSE} down")
    console.print("  [green]✓[/green]  Stopped")


@app.command()
def logs(
    service: str = typer.Argument(None, help="Service name (backend, frontend)."),
) -> None:
    """Tail container logs."""
    svc_map = {"backend": "prism", "frontend": "frontend"}
    target = svc_map.get(service, service or "")
    _run(f"{COMPOSE} logs -f {target}".strip())


# ── Build ────────────────────────────────────────────────────────────────────

@app.command()
def build(
    service: str = typer.Argument(
        None, help="Service to build: backend, frontend, or omit for all.",
    ),
) -> None:
    """Build Docker images."""
    if service == "backend":
        _run("docker build -t prism:latest .")
    elif service == "frontend":
        _run("docker build -t prism-frontend:latest ./frontend")
    else:
        _run_or_exit(f"{COMPOSE_PROD} build", "Build failed")
        console.print("  [green]✓[/green]  All images built")


# ── Prod (local) ─────────────────────────────────────────────────────────────

@app.command()
def prod(
    stop: bool = typer.Option(False, "--down", help="Stop instead of start."),
    restart: bool = typer.Option(False, "--restart", help="Rebuild and restart."),
) -> None:
    """Start production stack locally."""
    if stop:
        _run(f"{COMPOSE_PROD} down")
        console.print("  [green]✓[/green]  Production stopped")
    elif restart:
        _run(f"{COMPOSE_PROD} up -d --build")
    else:
        _run(f"{COMPOSE_PROD} up -d")
        console.print("  [green]✓[/green]  API → :8000   Frontend → :3000")


@app.command()
def status() -> None:
    """Show running containers and health."""
    _run(f"{COMPOSE_PROD} ps")


@app.command()
def shell(
    service: str = typer.Argument("backend", help="Service: backend or frontend."),
) -> None:
    """Open a shell in a running container."""
    svc_map = {"backend": "prism", "frontend": "frontend"}
    target = svc_map.get(service, service)
    sh = "sh" if target == "frontend" else "bash"
    _run(f"{COMPOSE} exec {target} {sh}")


@app.command()
def migrate() -> None:
    """Run Alembic database migrations."""
    _run(f"{COMPOSE} exec prism alembic upgrade head")


# ── Test ─────────────────────────────────────────────────────────────────────

@app.command()
def test(
    service: str = typer.Argument(
        None, help="Run tests for: frontend, backend, or omit for both.",
    ),
) -> None:
    """Run test suites."""
    ok = True
    if service in (None, "frontend"):
        console.print("  [blue]1[/blue]  Frontend tests...")
        if _run("npm test", cwd=ROOT / "frontend") != 0:
            ok = False
    if service in (None, "backend"):
        console.print("  [blue]2[/blue]  Backend tests...")
        if _run("pytest tests/", cwd=ROOT) != 0:
            ok = False
    if ok:
        console.print("  [green]✓[/green]  All tests passed")
    else:
        console.print("  [red]✗[/red]  Some tests failed")
        raise typer.Exit(1)


# ── Cloud ────────────────────────────────────────────────────────────────────

@app.command()
def deploy(
    host: str = typer.Option(None, help="Remote host (or set PRISM_DEPLOY_HOST)."),
    remote_dir: str = typer.Option("~/prism", "--dir", help="Remote directory."),
) -> None:
    """Full cloud deploy: build → push → load → start."""
    host = host or _require_host()

    console.print(f"\n  [bold]Deploying to {host}[/bold]\n")

    console.print("  [blue]1[/blue]  Building images...")
    _run_or_exit(f"{COMPOSE_PROD} build", "Build failed")

    console.print("  [blue]2[/blue]  Saving images...")
    _run_or_exit(
        "docker save prism:latest prism-frontend:latest | gzip > /tmp/prism-images.tar.gz",
        "Save failed",
    )

    console.print(f"  [blue]3[/blue]  Pushing to {host}...")
    _run_or_exit(f"rsync -azP /tmp/prism-images.tar.gz {host}:{remote_dir}/")
    _run(f"rsync -az {ROOT}/docker-compose.yml {ROOT}/docker-compose.prod.yml {host}:{remote_dir}/")
    os.remove("/tmp/prism-images.tar.gz")

    console.print("  [blue]4[/blue]  Loading images on remote...")
    _run_or_exit(
        f"ssh {host} 'cd {remote_dir} && gunzip -c prism-images.tar.gz | docker load'",
        "Remote load failed",
    )

    console.print("  [blue]5[/blue]  Starting services...")
    _run(f"ssh {host} 'cd {remote_dir} && {COMPOSE_PROD} up -d'")

    console.print("  [blue]6[/blue]  Health check (15s)...")
    time.sleep(15)
    _run(f"ssh {host} 'cd {remote_dir} && {COMPOSE_PROD} ps'")

    console.print("\n  [green]✓[/green]  Deploy complete\n")


@app.command("cloud-status")
def cloud_status(
    host: str = typer.Option(None, help="Remote host."),
    remote_dir: str = typer.Option("~/prism", "--dir"),
) -> None:
    """Show remote container status."""
    host = host or _require_host()
    _run(f"ssh {host} 'cd {remote_dir} && {COMPOSE_PROD} ps'")


@app.command("cloud-logs")
def cloud_logs(
    host: str = typer.Option(None, help="Remote host."),
    remote_dir: str = typer.Option("~/prism", "--dir"),
) -> None:
    """Tail remote container logs."""
    host = host or _require_host()
    _run(f"ssh {host} 'cd {remote_dir} && {COMPOSE_PROD} logs -f'")


@app.command("cloud-down")
def cloud_down(
    host: str = typer.Option(None, help="Remote host."),
    remote_dir: str = typer.Option("~/prism", "--dir"),
) -> None:
    """Stop remote services."""
    host = host or _require_host()
    _run(f"ssh {host} 'cd {remote_dir} && {COMPOSE_PROD} down'")
    console.print(f"  [green]✓[/green]  Stopped on {host}")


# ── Clean ────────────────────────────────────────────────────────────────────

@app.command()
def clean() -> None:
    """Remove build artifacts and stopped containers."""
    _run(f"{COMPOSE} down --rmi local --volumes --remove-orphans 2>/dev/null || true")
    _run("rm -rf frontend/.next frontend/node_modules/.cache")
    _run("find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true")
    console.print("  [green]✓[/green]  Cleaned")
