"""T7.4: CLI docs viewer tests.

Covers prism docs spec|cli|roadmap|arch|stack|readme|ls|search.
"""

import json

import pytest
from typer.testing import CliRunner

from prism.cli._fmt import set_json_mode
from prism.cli.app import app

runner = CliRunner()


@pytest.fixture(autouse=True)
def _reset_json_mode():
    set_json_mode(False)
    yield
    set_json_mode(False)


# ─── Individual doc commands ──────────────────────────────────

class TestDocView:
    @pytest.mark.parametrize("cmd", ["spec", "cli", "roadmap", "arch", "stack", "readme"])
    def test_view_doc(self, cmd):
        result = runner.invoke(app, ["docs", cmd])
        assert result.exit_code == 0
        # Each doc should have some content
        assert len(result.output) > 100

    @pytest.mark.parametrize("cmd", ["spec", "roadmap"])
    def test_view_doc_json(self, cmd):
        result = runner.invoke(app, ["--json", "docs", cmd])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "file" in data
        assert "content" in data
        assert len(data["content"]) > 100

    def test_spec_contains_key_sections(self):
        result = runner.invoke(app, ["--json", "docs", "spec"])
        data = json.loads(result.output)
        content = data["content"]
        assert "Agent Specifications" in content
        assert "Data Model" in content
        assert "Reliability" in content

    def test_roadmap_contains_milestones(self):
        result = runner.invoke(app, ["--json", "docs", "roadmap"])
        data = json.loads(result.output)
        assert "Milestone" in data["content"]

    def test_arch_contains_design(self):
        result = runner.invoke(app, ["--json", "docs", "arch"])
        data = json.loads(result.output)
        assert "D_AI" in data["content"] or "pipeline" in data["content"].lower()


# ─── List ─────────────────────────────────────────────────────

class TestDocLs:
    def test_ls_shows_all_docs(self):
        result = runner.invoke(app, ["docs", "ls"])
        assert result.exit_code == 0
        for name in ("spec", "cli", "roadmap", "arch", "stack", "readme"):
            assert name in result.output

    def test_ls_shows_exists(self):
        result = runner.invoke(app, ["docs", "ls"])
        assert "yes" in result.output

    def test_ls_json(self):
        result = runner.invoke(app, ["--json", "docs", "ls"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert len(data) == 8
        assert all("Name" in row for row in data)


# ─── Search ───────────────────────────────────────────────────

class TestDocSearch:
    def test_search_finds_matches(self):
        result = runner.invoke(app, ["docs", "search", "retry"])
        assert result.exit_code == 0
        assert "match" in result.output

    def test_search_no_matches(self):
        result = runner.invoke(app, ["docs", "search", "xyzzy_nonexistent_term_42"])
        assert result.exit_code == 0
        assert "No matches" in result.output

    def test_search_json(self):
        result = runner.invoke(app, ["--json", "docs", "search", "Claude"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert isinstance(data, list)
        assert len(data) > 0
        assert "doc" in data[0]
        assert "line" in data[0]
        assert "snippet" in data[0]

    def test_search_case_insensitive(self):
        result = runner.invoke(app, ["--json", "docs", "search", "PRISM"])
        data = json.loads(result.output)
        assert len(data) > 0

    def test_search_context_lines(self):
        result = runner.invoke(app, ["--json", "docs", "search", "retry", "-C", "0"])
        data = json.loads(result.output)
        # With 0 context, snippets should be single lines
        for match in data:
            assert "\n" not in match["snippet"]
