"""prism config — configuration inspection commands."""

import os

import typer
from rich.panel import Panel

from prism.cli._fmt import console, err_console, is_json_mode, print_json, print_table

app = typer.Typer(help="Configuration inspection.")

# Fields that contain secrets and should be masked in output.
_SECRET_FIELDS = {"anthropic_api_key", "brave_api_key", "resend_api_key"}

_ENV_TEMPLATE = """\
# Prism configuration — copy to .env and fill in values

# Required
ANTHROPIC_API_KEY=

# Optional API keys
BRAVE_API_KEY=
RESEND_API_KEY=

# Database
DATABASE_URL=sqlite:///data/newsgen.db
BRIEFING_FROM_EMAIL=briefing@yourdomain.com

# D_AI
DISCOVERY_INTERVAL_HOURS=2
MAX_STORIES_PER_CYCLE=50
MIN_SOURCE_TRUST_SCORE=0.5

# A_AI
MAX_PERSPECTIVES_PER_STORY=5
MAX_INPUT_TOKENS=8000

# P_AI
DEFAULT_BRIEFING_STORIES=10
MAX_BRIEFING_STORIES=25

# W_AI
BRIEFING_SCHEDULE_CRON=0 7 * * *

# Monitoring (empty = disabled)
NTFY_TOPIC=
"""


def _load_settings():  # type: ignore[no-untyped-def]
    """Load settings, returning (settings, error_msg)."""
    try:
        from prism.config import get_settings
        return get_settings(), None
    except Exception as exc:
        return None, str(exc)


def _mask(field: str, value: str) -> str:
    if field in _SECRET_FIELDS:
        from prism.cli._fmt import mask_secret
        return mask_secret(value)
    return value


@app.command("show")
def config_show() -> None:
    """Display current configuration (secrets masked)."""
    settings, err = _load_settings()
    if err:
        err_console.print(f"[red]Failed to load settings:[/red] {err}")
        raise typer.Exit(1)

    fields = settings.model_fields  # type: ignore[union-attr]
    if is_json_mode():
        data = {}
        for name in fields:
            val = str(getattr(settings, name))
            data[name] = _mask(name, val) if name in _SECRET_FIELDS else val
        print_json(data)
        return

    rows = []
    for name in fields:
        val = str(getattr(settings, name))
        display = _mask(name, val)
        rows.append([name, display])
    print_table("Prism Configuration", ["Setting", "Value"], rows)


@app.command("check")
def config_check() -> None:
    """Validate configuration and test API connectivity."""
    settings, err = _load_settings()
    if err:
        err_console.print(f"[red]Failed to load settings:[/red] {err}")
        raise typer.Exit(1)

    results: list[dict] = []

    def _record(name: str, ok: bool, detail: str) -> None:
        results.append({"name": name, "ok": ok, "detail": detail})

    # --- Anthropic API key ---
    api_key = settings.anthropic_api_key  # type: ignore[union-attr]
    if not api_key:
        _record("anthropic_api_key", False, "missing")
    else:
        try:
            import anthropic
            client = anthropic.Anthropic(api_key=api_key)
            client.models.retrieve("claude-sonnet-4-6")
            _record("anthropic_api_key", True, "valid (claude-sonnet-4-6 reachable)")
        except Exception as exc:
            _record("anthropic_api_key", False, str(exc)[:80])

    # --- Brave API key ---
    brave_key = settings.brave_api_key  # type: ignore[union-attr]
    if not brave_key:
        _record("brave_api_key", False, "missing — discovery will skip Brave search")
    else:
        try:
            import httpx
            r = httpx.get(
                "https://api.search.brave.com/res/v1/news/search",
                params={"q": "test", "count": "1"},
                headers={"X-Subscription-Token": brave_key},
                timeout=10,
            )
            r.raise_for_status()
            _record("brave_api_key", True, "valid")
        except Exception as exc:
            _record("brave_api_key", False, str(exc)[:80])

    # --- Resend API key ---
    resend_key = settings.resend_api_key  # type: ignore[union-attr]
    if not resend_key:
        _record("resend_api_key", False, "missing — email delivery disabled")
    else:
        _record("resend_api_key", True, "configured")

    # --- Database ---
    db_url = settings.database_url  # type: ignore[union-attr]
    try:
        from sqlmodel import text

        from prism.db import get_engine
        engine = get_engine(db_url)
        with engine.connect() as conn:
            mode = conn.execute(text("PRAGMA journal_mode")).scalar()
            tables_raw = conn.execute(
                text("SELECT name FROM sqlite_master WHERE type='table'")
            ).fetchall()
            tables = [t[0] for t in tables_raw if not t[0].startswith("sqlite_")]
        db_path = db_url.replace("sqlite:///", "")
        size_str = ""
        if os.path.exists(db_path):
            size_mb = os.path.getsize(db_path) / (1024 * 1024)
            size_str = f", {size_mb:.1f} MB"
        _record("database", True, f"writable, {mode} mode, {len(tables)} tables{size_str}")
    except Exception as exc:
        _record("database", False, str(exc)[:80])

    # --- ntfy ---
    ntfy = settings.ntfy_topic  # type: ignore[union-attr]
    if not ntfy:
        _record("ntfy_topic", True, "disabled (empty topic)")
    else:
        _record("ntfy_topic", True, f'topic "{ntfy}" configured')

    # --- briefing_from_email ---
    from_email = settings.briefing_from_email  # type: ignore[union-attr]
    if from_email == "briefing@yourdomain.com":
        results.append({"name": "briefing_from_email", "ok": True,
                        "detail": f"{from_email} (default — update before sending)",
                        "warn": True})
    else:
        _record("briefing_from_email", True, from_email)

    # --- Output ---
    if is_json_mode():
        print_json(results)
        return

    console.print()
    console.print("  Checking Prism configuration...\n")
    ok_count = 0
    warn_count = 0
    fail_count = 0
    for r in results:
        is_warn = r.get("warn", False)
        if r["ok"] and not is_warn:
            console.print(f"  [green]✓[/green] {r['name']:<24s} {r['detail']}")
            ok_count += 1
        elif is_warn:
            console.print(f"  [yellow]⚠[/yellow] {r['name']:<24s} {r['detail']}")
            warn_count += 1
        else:
            console.print(f"  [red]✗[/red] {r['name']:<24s} {r['detail']}")
            fail_count += 1
    console.print()
    parts = [f"{ok_count} ok"]
    if warn_count:
        parts.append(f"{warn_count} warning{'s' if warn_count > 1 else ''}")
    if fail_count:
        parts.append(f"{fail_count} failed")
    console.print(f"  {', '.join(parts)}.")
    console.print()


@app.command("env")
def config_env() -> None:
    """Print .env template with comments."""
    if is_json_mode():
        print_json({"template": _ENV_TEMPLATE})
        return
    console.print(Panel(_ENV_TEMPLATE.strip(), title=".env template", border_style="dim"))
