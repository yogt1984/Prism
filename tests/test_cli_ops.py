"""T7.3: CLI operations command tests.

Covers prism run, cycle, and status subcommands.
"""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from prism.cli._fmt import set_json_mode
from prism.cli.app import app
from prism.db import init_db
from prism.models import Source, StoryCluster, User

runner = CliRunner()


@pytest.fixture(autouse=True)
def _reset_json_mode():
    set_json_mode(False)
    yield
    set_json_mode(False)


@pytest.fixture()
def db_engine(tmp_path: Path):
    url = f"sqlite:///{tmp_path / 'test.db'}"
    engine = init_db(url)
    yield engine
    engine.dispose()


# ─── Run ──────────────────────────────────────────────────────

class TestRun:
    def test_run_once(self):
        """--once calls all three cycles and exits."""
        with (
            patch("prism.db.init_db") as mock_init,
            patch("prism.main.discovery_cycle") as mock_d,
            patch("prism.main.analysis_cycle") as mock_a,
            patch("prism.main.briefing_cycle") as mock_b,
        ):
            mock_init.return_value = MagicMock()
            result = runner.invoke(app, ["run", "--once"])
        assert result.exit_code == 0
        assert "Cycle complete" in result.output
        mock_d.assert_called_once()
        mock_a.assert_called_once()
        mock_b.assert_called_once()

    def test_run_scheduler_starts(self):
        """Without --once, scheduler.start() is called."""
        mock_scheduler = MagicMock()
        mock_scheduler.start.side_effect = KeyboardInterrupt
        with (
            patch("prism.db.init_db") as mock_init,
            patch("prism.main.build_scheduler", return_value=mock_scheduler),
            patch("prism.main.install_signal_handlers"),
        ):
            mock_init.return_value = MagicMock()
            result = runner.invoke(app, ["run"])
        assert result.exit_code == 0
        mock_scheduler.start.assert_called_once()

    def test_run_help(self):
        result = runner.invoke(app, ["run", "--help"])
        assert result.exit_code == 0
        assert "--once" in result.output


# ─── Cycle ────────────────────────────────────────────────────

class TestCycleDiscover:
    def test_discover(self):
        with (
            patch("prism.cli.cycle._get_engine", return_value=MagicMock()),
            patch("prism.main.discovery_cycle") as mock_dc,
        ):
            result = runner.invoke(app, ["cycle", "discover"])
        assert result.exit_code == 0
        assert "complete" in result.output
        mock_dc.assert_called_once()

    def test_discover_json(self):
        with (
            patch("prism.cli.cycle._get_engine", return_value=MagicMock()),
            patch("prism.main.discovery_cycle"),
        ):
            result = runner.invoke(app, ["--json", "cycle", "discover"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["cycle"] == "discovery"


class TestCycleAnalyze:
    def test_analyze(self):
        with (
            patch("prism.cli.cycle._get_engine", return_value=MagicMock()),
            patch("prism.main.analysis_cycle") as mock_ac,
        ):
            result = runner.invoke(app, ["cycle", "analyze"])
        assert result.exit_code == 0
        mock_ac.assert_called_once()


class TestCycleBrief:
    def test_brief_all_users(self, db_engine):
        from sqlmodel import Session
        with Session(db_engine) as s:
            s.add(User(email="a@test.com"))
            s.add(User(email="b@test.com"))
            s.commit()

        mock_p_ai = MagicMock()
        mock_p_ai.get_all_users.return_value = [
            MagicMock(email="a@test.com"),
            MagicMock(email="b@test.com"),
        ]
        mock_p_ai.select_stories.return_value = []

        mock_w_ai = MagicMock()
        mock_w_ai.create_and_send.return_value = None

        with (
            patch("prism.cli.cycle._get_engine", return_value=db_engine),
            patch("prism.agents.p_ai.PersonalizationAgent",
                  return_value=mock_p_ai),
            patch("prism.agents.w_ai.WriterAgent", return_value=mock_w_ai),
        ):
            result = runner.invoke(app, ["cycle", "brief"])
        assert result.exit_code == 0
        assert "2 user(s)" in result.output

    def test_brief_single_user(self, db_engine):
        from sqlmodel import Session
        with Session(db_engine) as s:
            s.add(User(email="solo@test.com"))
            s.commit()

        mock_p_ai = MagicMock()
        mock_p_ai.select_stories.return_value = []
        mock_w_ai = MagicMock()
        mock_w_ai.create_and_send.return_value = None

        with (
            patch("prism.cli.cycle._get_engine", return_value=db_engine),
            patch("prism.agents.p_ai.PersonalizationAgent",
                  return_value=mock_p_ai),
            patch("prism.agents.w_ai.WriterAgent", return_value=mock_w_ai),
        ):
            result = runner.invoke(app, ["cycle", "brief",
                                         "--user", "solo@test.com"])
        assert result.exit_code == 0
        assert "1 user(s)" in result.output

    def test_brief_user_not_found(self, db_engine):
        with patch("prism.cli.cycle._get_engine", return_value=db_engine):
            result = runner.invoke(app, ["cycle", "brief",
                                         "--user", "nobody@test.com"])
        assert result.exit_code == 1

    def test_brief_json(self, db_engine):
        mock_p_ai = MagicMock()
        mock_p_ai.get_all_users.return_value = []
        mock_w_ai = MagicMock()

        with (
            patch("prism.cli.cycle._get_engine", return_value=db_engine),
            patch("prism.agents.p_ai.PersonalizationAgent",
                  return_value=mock_p_ai),
            patch("prism.agents.w_ai.WriterAgent", return_value=mock_w_ai),
        ):
            result = runner.invoke(app, ["--json", "cycle", "brief"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["cycle"] == "briefing"
        assert data["users"] == 0


# ─── Status ───────────────────────────────────────────────────

class TestStatus:
    def test_status_dashboard(self, db_engine):
        with patch("prism.cli.status._get_engine", return_value=db_engine):
            result = runner.invoke(app, ["status"])
        assert result.exit_code == 0
        assert "Prism Pipeline Status" in result.output

    def test_status_json(self, db_engine):
        with patch("prism.cli.status._get_engine", return_value=db_engine):
            result = runner.invoke(app, ["--json", "status"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "total_clusters" in data
        assert "total_users" in data
        assert "categories" in data
        assert "db_size_mb" in data

    def test_status_with_data(self, db_engine):
        from sqlmodel import Session
        with Session(db_engine) as s:
            source = Source(name="Test", url="test.com")
            s.add(source)
            s.commit()
            s.refresh(source)
            s.add(StoryCluster(headline="Story", categories="finance",
                               article_count=2))
            s.add(User(email="u@test.com"))
            s.commit()

        with patch("prism.cli.status._get_engine", return_value=db_engine):
            result = runner.invoke(app, ["--json", "status"])
        data = json.loads(result.output)
        assert data["total_clusters"] == 1
        assert data["total_users"] == 1
        assert data["active_sources"] == 1

    def test_status_help(self):
        result = runner.invoke(app, ["status", "--help"])
        assert result.exit_code == 0
        assert "--watch" in result.output
