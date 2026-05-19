"""Shared formatting helpers for CLI output."""

import json as _json
from typing import Any

from rich.console import Console
from rich.table import Table

console = Console()
err_console = Console(stderr=True)

_json_mode = False


def set_json_mode(enabled: bool) -> None:
    global _json_mode
    _json_mode = enabled


def is_json_mode() -> bool:
    return _json_mode


def print_json(data: Any) -> None:
    # Use plain print — Rich console adds control characters that break JSON parsing.
    print(_json.dumps(data, indent=2, default=str))


def print_table(title: str, columns: list[str], rows: list[list[str]]) -> None:
    """Print a Rich table, or JSON if --json is active."""
    if _json_mode:
        print_json([dict(zip(columns, row)) for row in rows])
        return
    table = Table(title=title, show_lines=False)
    for col in columns:
        table.add_column(col)
    for row in rows:
        table.add_row(*row)
    console.print(table)


def mask_secret(value: str) -> str:
    """Mask a secret string, showing only last 4 chars."""
    if not value:
        return "(empty)"
    if len(value) <= 8:
        return "****"
    return "****" + value[-4:]
