"""prism docs — in-terminal documentation viewer with search."""

from pathlib import Path
from typing import Annotated

import typer
from rich.markdown import Markdown
from rich.panel import Panel

from prism.cli._fmt import console, err_console, is_json_mode, print_json

app = typer.Typer(help="Browse and search project documentation in the terminal.")

# Resolve project root (three levels up from this file: cli -> prism -> src -> root)
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent

_DOC_MAP: dict[str, str] = {
    "spec": "docs/specifications.md",
    "cli": "docs/cli-specification.md",
    "roadmap": "ROADMAP.md",
    "arch": "CLAUDE.md",
    "stack": "TECH_STACK.md",
    "readme": "README.md",
    "deploy": "docs/deployment.md",
    "tasks": "docs/tasks.md",
}


def _resolve_doc(name: str) -> Path | None:
    rel = _DOC_MAP.get(name)
    if not rel:
        return None
    path = _PROJECT_ROOT / rel
    return path if path.exists() else None


def _render_doc(path: Path, pager: bool) -> None:
    """Read and render a markdown file."""
    content = path.read_text()

    if is_json_mode():
        print_json({"file": str(path.relative_to(_PROJECT_ROOT)),
                     "content": content})
        return

    md = Markdown(content)
    if pager:
        with console.pager(styles=True):
            console.print(md)
    else:
        console.print(md)


def _doc_command(name: str, description: str):  # type: ignore[no-untyped-def]
    """Factory for individual doc subcommands."""
    @app.command(name, help=f"View {description}.")
    def _cmd(
        pager: Annotated[
            bool, typer.Option("--pager", help="Pipe through pager."),
        ] = False,
    ) -> None:
        path = _resolve_doc(name)
        if not path:
            err_console.print(f"[red]Document not found:[/red] {name}")
            raise typer.Exit(1)
        _render_doc(path, pager)
    return _cmd


# Register one subcommand per document
_doc_command("spec", "system specifications")
_doc_command("cli", "CLI specification")
_doc_command("roadmap", "implementation roadmap")
_doc_command("arch", "architecture & constraints (CLAUDE.md)")
_doc_command("stack", "technology stack")
_doc_command("readme", "project README")
_doc_command("deploy", "deployment guide")
_doc_command("tasks", "task plan")


@app.command("ls")
def docs_ls() -> None:
    """List available documents."""
    from prism.cli._fmt import print_table

    rows = []
    for name, rel in _DOC_MAP.items():
        path = _PROJECT_ROOT / rel
        exists = path.exists()
        size = f"{path.stat().st_size:,} bytes" if exists else "-"
        rows.append([name, rel, "yes" if exists else "no", size])
    print_table("Documents", ["Name", "Path", "Exists", "Size"], rows)


@app.command("search")
def docs_search(
    query: Annotated[str, typer.Argument(help="Search term.")],
    context: Annotated[
        int, typer.Option("-C", help="Lines of context around matches."),
    ] = 2,
) -> None:
    """Search across all documentation for a keyword."""
    query_lower = query.lower()
    results: list[dict] = []

    for name, rel in _DOC_MAP.items():
        path = _PROJECT_ROOT / rel
        if not path.exists():
            continue
        lines = path.read_text().splitlines()
        for i, line in enumerate(lines):
            if query_lower in line.lower():
                start = max(0, i - context)
                end = min(len(lines), i + context + 1)
                snippet = "\n".join(lines[start:end])
                results.append({
                    "doc": name,
                    "file": rel,
                    "line": i + 1,
                    "snippet": snippet,
                })

    if is_json_mode():
        print_json(results)
        return

    if not results:
        console.print(f"  No matches for [bold]{query}[/bold]")
        return

    console.print(f"\n  Found [bold]{len(results)}[/bold] match(es) "
                  f"for [bold]{query}[/bold]:\n")
    for r in results:
        console.print(Panel(
            r["snippet"],
            title=f"{r['doc']} ({r['file']}:{r['line']})",
            border_style="dim",
        ))
