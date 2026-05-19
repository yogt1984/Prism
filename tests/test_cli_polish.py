"""T7.5: CLI polish tests — --quiet, --db global flags."""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from prism.cli._fmt import set_db_override, set_json_mode, set_quiet_mode
from prism.cli.app import app
from prism.db import init_db

runner = CliRunner()


@pytest.fixture(autouse=True)
def _reset_modes():
    """Reset all global mode flags between tests."""
    set_json_mode(False)
    set_quiet_mode(False)
    set_db_override(None)
    yield
    set_json_mode(False)
    set_quiet_mode(False)
    set_db_override(None)


@pytest.fixture()
def db_engine(tmp_path: Path):
    url = f"sqlite:///{tmp_path / 'test.db'}"
    engine = init_db(url)
    yield engine
    engine.dispose()


# ─── --quiet flag ────────────────────────────────────────────

class TestQuietFlag:
    def test_quiet_suppresses_run_progress(self):
        """--quiet suppresses info() messages but keeps final output."""
        with (
            patch("prism.db.init_db") as mock_init,
            patch("prism.main.discovery_cycle"),
            patch("prism.main.analysis_cycle"),
            patch("prism.main.briefing_cycle"),
        ):
            mock_init.return_value = MagicMock()
            result = runner.invoke(app, ["--quiet", "run", "--once"])
        assert result.exit_code == 0
        # Progress messages suppressed
        assert "Initializing" not in result.output
        assert "Running single cycle" not in result.output
        # Final result still shown
        assert "Cycle complete" in result.output

    def test_quiet_suppresses_cycle_progress(self):
        """--quiet suppresses cycle info() messages."""
        with (
            patch("prism.cli.cycle._get_engine", return_value=MagicMock()),
            patch("prism.main.discovery_cycle"),
        ):
            result = runner.invoke(app, ["--quiet", "cycle", "discover"])
        assert result.exit_code == 0
        assert "Running discovery" not in result.output
        assert "complete" in result.output

    def test_quiet_version_still_shows(self):
        """--quiet doesn't affect version output (no info() calls there)."""
        result = runner.invoke(app, ["--quiet", "version"])
        assert result.exit_code == 0
        assert "Prism" in result.output

    def test_quiet_help_flag_visible(self):
        """--quiet/-q appears in help text."""
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        assert "--quiet" in result.output

    def test_quiet_short_flag(self):
        """Short -q flag works the same as --quiet."""
        with (
            patch("prism.db.init_db") as mock_init,
            patch("prism.main.discovery_cycle"),
            patch("prism.main.analysis_cycle"),
            patch("prism.main.briefing_cycle"),
        ):
            mock_init.return_value = MagicMock()
            result = runner.invoke(app, ["-q", "run", "--once"])
        assert result.exit_code == 0
        assert "Initializing" not in result.output


# ─── --db flag ───────────────────────────────────────────────

class TestDbFlag:
    def test_db_override_passed_to_engine(self, tmp_path):
        """--db flag causes get_engine to receive the custom URL."""
        custom_url = f"sqlite:///{tmp_path / 'custom.db'}"
        engine = init_db(custom_url)

        with patch("prism.db.get_engine", return_value=engine) as mock_ge:
            result = runner.invoke(app, ["--db", custom_url, "--json", "status"])

        assert result.exit_code == 0
        mock_ge.assert_called_with(custom_url)

    def test_db_help_flag_visible(self):
        """--db appears in help text."""
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        assert "--db" in result.output

    def test_db_override_with_status(self, tmp_path):
        """--db works end-to-end with status command."""
        custom_url = f"sqlite:///{tmp_path / 'alt.db'}"
        engine = init_db(custom_url)
        try:
            with patch("prism.db.get_engine", return_value=engine):
                result = runner.invoke(
                    app, ["--db", custom_url, "--json", "status"]
                )
            assert result.exit_code == 0
            data = json.loads(result.output)
            assert "total_clusters" in data
        finally:
            engine.dispose()


# ─── Combined flags ──────────────────────────────────────────

class TestCombinedFlags:
    def test_json_implies_quiet(self):
        """--json mode also suppresses info() messages."""
        with (
            patch("prism.db.init_db") as mock_init,
            patch("prism.main.discovery_cycle"),
            patch("prism.main.analysis_cycle"),
            patch("prism.main.briefing_cycle"),
        ):
            mock_init.return_value = MagicMock()
            result = runner.invoke(app, ["--json", "run", "--once"])
        # No progress messages in JSON mode
        assert "Initializing" not in result.output
        assert "Running single cycle" not in result.output

    def test_quiet_and_json_together(self):
        """--quiet --json doesn't break anything."""
        result = runner.invoke(app, ["--quiet", "--json", "version"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "prism" in data

    def test_all_flags_together(self, tmp_path):
        """--quiet --json --db all at once."""
        custom_url = f"sqlite:///{tmp_path / 'combo.db'}"
        engine = init_db(custom_url)
        try:
            with patch("prism.db.get_engine", return_value=engine):
                result = runner.invoke(
                    app,
                    ["--quiet", "--json", "--db", custom_url, "status"],
                )
            assert result.exit_code == 0
            data = json.loads(result.output)
            assert "total_clusters" in data
        finally:
            engine.dispose()
