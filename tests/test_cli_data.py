"""T7.2: CLI data command tests.

Covers prism user, source, story, briefing subcommands.
"""

import json
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from prism.cli._fmt import set_json_mode
from prism.cli.app import app
from prism.db import init_db
from prism.models import (
    Article,
    BiasLabel,
    Briefing,
    Perspective,
    Source,
    StoryCluster,
    StoryStatus,
    User,
)

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


def _patch_engine(engine):
    """Patch _get_engine across all CLI modules to use test engine."""
    return [
        patch("prism.cli.user._get_engine", return_value=engine),
        patch("prism.cli.source._get_engine", return_value=engine),
        patch("prism.cli.story._get_engine", return_value=engine),
        patch("prism.cli.briefing._get_engine", return_value=engine),
    ]


def _seed_user(engine, email="alice@example.com", interests="finance,technology"):
    from sqlmodel import Session
    with Session(engine) as s:
        user = User(email=email, interests=interests)
        s.add(user)
        s.commit()
        s.refresh(user)
        return user.id


def _seed_source(engine, name="Reuters", url="reuters.com"):
    from sqlmodel import Session
    with Session(engine) as s:
        source = Source(name=name, url=url, trust_score=0.95, bias_label=BiasLabel.CENTER)
        s.add(source)
        s.commit()
        s.refresh(source)
        return source.id


def _seed_cluster(engine, source_id, headline="Test headline",
                  status=StoryStatus.ANALYZED):
    from sqlmodel import Session
    with Session(engine) as s:
        cluster = StoryCluster(headline=headline, summary="Test summary",
                               categories="finance", status=status, article_count=2)
        s.add(cluster)
        s.commit()
        s.refresh(cluster)
        article = Article(cluster_id=cluster.id, source_id=source_id,
                          title="Test article", url=f"https://example.com/{cluster.id}")
        s.add(article)
        perspective = Perspective(cluster_id=cluster.id, source_id=source_id,
                                 summary="Test perspective", sentiment=0.3,
                                 bias_label=BiasLabel.CENTER,
                                 key_claims='["Claim (Source: Reuters)"]')
        s.add(perspective)
        s.commit()
        return cluster.id


def _seed_briefing(engine, user_id, sent=True):
    from sqlmodel import Session
    with Session(engine) as s:
        briefing = Briefing(user_id=user_id, content_html="<p>Test briefing</p>",
                            story_count=3, sent=sent,
                            sent_at=datetime.now(UTC) if sent else None)
        s.add(briefing)
        s.commit()
        s.refresh(briefing)
        return briefing.id


# ─── User commands ────────────────────────────────────────────

class TestUserAdd:
    def test_add_user(self, db_engine):
        patches = _patch_engine(db_engine)
        with patch("prism.onboarding.get_engine", return_value=db_engine):
            for p in patches:
                p.start()
            result = runner.invoke(app, ["user", "add", "bob@example.com",
                                         "--interests", "finance"])
            for p in patches:
                p.stop()
        assert result.exit_code == 0
        assert "Registered" in result.output

    def test_add_user_invalid_email(self, db_engine):
        patches = _patch_engine(db_engine)
        with patch("prism.onboarding.get_engine", return_value=db_engine):
            for p in patches:
                p.start()
            result = runner.invoke(app, ["user", "add", "not-an-email"])
            for p in patches:
                p.stop()
        assert result.exit_code == 1
        assert "Error" in result.output

    def test_add_user_json(self, db_engine):
        patches = _patch_engine(db_engine)
        with patch("prism.onboarding.get_engine", return_value=db_engine):
            for p in patches:
                p.start()
            result = runner.invoke(app, ["--json", "user", "add", "bob@example.com"])
            for p in patches:
                p.stop()
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["email"] == "bob@example.com"


class TestUserLs:
    def test_ls_users(self, db_engine):
        _seed_user(db_engine)
        _seed_user(db_engine, email="bob@example.com")
        patches = _patch_engine(db_engine)
        for p in patches:
            p.start()
        result = runner.invoke(app, ["user", "ls"])
        for p in patches:
            p.stop()
        assert result.exit_code == 0
        # Rich may truncate columns; check partial match
        assert "alice" in result.output
        assert "bob" in result.output

    def test_ls_users_json(self, db_engine):
        _seed_user(db_engine)
        patches = _patch_engine(db_engine)
        for p in patches:
            p.start()
        result = runner.invoke(app, ["--json", "user", "ls"])
        for p in patches:
            p.stop()
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert len(data) == 1


class TestUserShow:
    def test_show_user(self, db_engine):
        _seed_user(db_engine)
        patches = _patch_engine(db_engine)
        for p in patches:
            p.start()
        result = runner.invoke(app, ["user", "show", "alice@example.com"])
        for p in patches:
            p.stop()
        assert result.exit_code == 0
        assert "alice@example.com" in result.output

    def test_show_user_not_found(self, db_engine):
        patches = _patch_engine(db_engine)
        for p in patches:
            p.start()
        result = runner.invoke(app, ["user", "show", "nobody@example.com"])
        for p in patches:
            p.stop()
        assert result.exit_code == 1


class TestUserEdit:
    def test_edit_interests(self, db_engine):
        _seed_user(db_engine)
        patches = _patch_engine(db_engine)
        for p in patches:
            p.start()
        result = runner.invoke(app, ["user", "edit", "alice@example.com",
                                     "--interests", "science,health"])
        for p in patches:
            p.stop()
        assert result.exit_code == 0
        assert "Updated" in result.output

    def test_edit_invalid_interest(self, db_engine):
        _seed_user(db_engine)
        patches = _patch_engine(db_engine)
        for p in patches:
            p.start()
        result = runner.invoke(app, ["user", "edit", "alice@example.com",
                                     "--interests", "gossip"])
        for p in patches:
            p.stop()
        assert result.exit_code == 1

    def test_edit_format(self, db_engine):
        _seed_user(db_engine)
        patches = _patch_engine(db_engine)
        for p in patches:
            p.start()
        result = runner.invoke(app, ["user", "edit", "alice@example.com",
                                     "--format", "json_feed"])
        for p in patches:
            p.stop()
        assert result.exit_code == 0


class TestUserRm:
    def test_rm_user(self, db_engine):
        _seed_user(db_engine)
        patches = _patch_engine(db_engine)
        for p in patches:
            p.start()
        result = runner.invoke(app, ["user", "rm", "alice@example.com", "--yes"])
        for p in patches:
            p.stop()
        assert result.exit_code == 0
        assert "Deleted" in result.output

    def test_rm_user_not_found(self, db_engine):
        patches = _patch_engine(db_engine)
        for p in patches:
            p.start()
        result = runner.invoke(app, ["user", "rm", "nobody@example.com", "--yes"])
        for p in patches:
            p.stop()
        assert result.exit_code == 1


# ─── Source commands ──────────────────────────────────────────

class TestSourceLs:
    def test_ls_sources(self, db_engine):
        _seed_source(db_engine)
        patches = _patch_engine(db_engine)
        for p in patches:
            p.start()
        result = runner.invoke(app, ["source", "ls"])
        for p in patches:
            p.stop()
        assert result.exit_code == 0
        assert "Reuters" in result.output

    def test_ls_sources_json(self, db_engine):
        _seed_source(db_engine)
        patches = _patch_engine(db_engine)
        for p in patches:
            p.start()
        result = runner.invoke(app, ["--json", "source", "ls"])
        for p in patches:
            p.stop()
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert len(data) == 1

    def test_ls_filter_bias(self, db_engine):
        _seed_source(db_engine)
        patches = _patch_engine(db_engine)
        for p in patches:
            p.start()
        result = runner.invoke(app, ["source", "ls", "--bias", "left"])
        for p in patches:
            p.stop()
        assert result.exit_code == 0
        assert "Reuters" not in result.output  # Reuters is center


class TestSourceAdd:
    def test_add_source(self, db_engine):
        patches = _patch_engine(db_engine)
        for p in patches:
            p.start()
        result = runner.invoke(app, ["source", "add", "bbc.co.uk",
                                     "--name", "BBC", "--trust", "0.9"])
        for p in patches:
            p.stop()
        assert result.exit_code == 0
        assert "Added" in result.output

    def test_add_duplicate(self, db_engine):
        _seed_source(db_engine)
        patches = _patch_engine(db_engine)
        for p in patches:
            p.start()
        result = runner.invoke(app, ["source", "add", "reuters.com"])
        for p in patches:
            p.stop()
        assert result.exit_code == 1

    def test_add_invalid_trust(self, db_engine):
        patches = _patch_engine(db_engine)
        for p in patches:
            p.start()
        result = runner.invoke(app, ["source", "add", "test.com", "--trust", "1.5"])
        for p in patches:
            p.stop()
        assert result.exit_code == 1


class TestSourceSeed:
    def test_seed(self, db_engine):
        patches = _patch_engine(db_engine)
        with patch("prism.seed.seed_sources", return_value=30):
            for p in patches:
                p.start()
            result = runner.invoke(app, ["source", "seed"])
            for p in patches:
                p.stop()
        assert result.exit_code == 0
        assert "30" in result.output


class TestSourceTrust:
    def test_update_trust(self, db_engine):
        _seed_source(db_engine)
        patches = _patch_engine(db_engine)
        for p in patches:
            p.start()
        result = runner.invoke(app, ["source", "trust", "reuters.com", "0.99"])
        for p in patches:
            p.stop()
        assert result.exit_code == 0
        assert "0.99" in result.output


class TestSourceBias:
    def test_update_bias(self, db_engine):
        _seed_source(db_engine)
        patches = _patch_engine(db_engine)
        for p in patches:
            p.start()
        result = runner.invoke(app, ["source", "bias", "reuters.com", "center_left"])
        for p in patches:
            p.stop()
        assert result.exit_code == 0
        assert "center_left" in result.output

    def test_invalid_bias(self, db_engine):
        _seed_source(db_engine)
        patches = _patch_engine(db_engine)
        for p in patches:
            p.start()
        result = runner.invoke(app, ["source", "bias", "reuters.com", "extreme_left"])
        for p in patches:
            p.stop()
        assert result.exit_code == 1


class TestSourceToggle:
    def test_toggle_source(self, db_engine):
        _seed_source(db_engine)
        patches = _patch_engine(db_engine)
        for p in patches:
            p.start()
        result = runner.invoke(app, ["source", "toggle", "reuters.com"])
        for p in patches:
            p.stop()
        assert result.exit_code == 0
        assert "inactive" in result.output


# ─── Story commands ───────────────────────────────────────────

class TestStoryLs:
    def test_ls_stories(self, db_engine):
        sid = _seed_source(db_engine)
        _seed_cluster(db_engine, sid)
        patches = _patch_engine(db_engine)
        for p in patches:
            p.start()
        result = runner.invoke(app, ["story", "ls"])
        for p in patches:
            p.stop()
        assert result.exit_code == 0
        assert "Test headline" in result.output

    def test_ls_filter_status(self, db_engine):
        sid = _seed_source(db_engine)
        _seed_cluster(db_engine, sid, status=StoryStatus.RAW)
        _seed_cluster(db_engine, sid, headline="Analyzed story")
        patches = _patch_engine(db_engine)
        for p in patches:
            p.start()
        result = runner.invoke(app, ["story", "ls", "--status", "raw"])
        for p in patches:
            p.stop()
        assert result.exit_code == 0
        assert "Analyzed story" not in result.output

    def test_ls_json(self, db_engine):
        sid = _seed_source(db_engine)
        _seed_cluster(db_engine, sid)
        patches = _patch_engine(db_engine)
        for p in patches:
            p.start()
        result = runner.invoke(app, ["--json", "story", "ls"])
        for p in patches:
            p.stop()
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert len(data) == 1


class TestStoryShow:
    def test_show_cluster(self, db_engine):
        sid = _seed_source(db_engine)
        cid = _seed_cluster(db_engine, sid)
        patches = _patch_engine(db_engine)
        for p in patches:
            p.start()
        result = runner.invoke(app, ["story", "show", str(cid)])
        for p in patches:
            p.stop()
        assert result.exit_code == 0
        assert "Test headline" in result.output
        assert "Test perspective" in result.output

    def test_show_not_found(self, db_engine):
        patches = _patch_engine(db_engine)
        for p in patches:
            p.start()
        result = runner.invoke(app, ["story", "show", "9999"])
        for p in patches:
            p.stop()
        assert result.exit_code == 1

    def test_show_json(self, db_engine):
        sid = _seed_source(db_engine)
        cid = _seed_cluster(db_engine, sid)
        patches = _patch_engine(db_engine)
        for p in patches:
            p.start()
        result = runner.invoke(app, ["--json", "story", "show", str(cid)])
        for p in patches:
            p.stop()
        data = json.loads(result.output)
        assert data["headline"] == "Test headline"
        assert len(data["perspectives"]) == 1


class TestStoryStats:
    def test_stats(self, db_engine):
        sid = _seed_source(db_engine)
        _seed_cluster(db_engine, sid)
        _seed_cluster(db_engine, sid, headline="Another")
        patches = _patch_engine(db_engine)
        for p in patches:
            p.start()
        result = runner.invoke(app, ["story", "stats"])
        for p in patches:
            p.stop()
        assert result.exit_code == 0
        assert "Clusters" in result.output

    def test_stats_json(self, db_engine):
        sid = _seed_source(db_engine)
        _seed_cluster(db_engine, sid)
        patches = _patch_engine(db_engine)
        for p in patches:
            p.start()
        result = runner.invoke(app, ["--json", "story", "stats"])
        for p in patches:
            p.stop()
        data = json.loads(result.output)
        assert data["total_clusters"] == 1


# ─── Briefing commands ────────────────────────────────────────

class TestBriefingLs:
    def test_ls_briefings(self, db_engine):
        uid = _seed_user(db_engine)
        _seed_briefing(db_engine, uid)
        patches = _patch_engine(db_engine)
        for p in patches:
            p.start()
        result = runner.invoke(app, ["briefing", "ls"])
        for p in patches:
            p.stop()
        assert result.exit_code == 0
        # Rich may truncate columns; check partial match
        assert "alice" in result.output

    def test_ls_unsent(self, db_engine):
        uid = _seed_user(db_engine)
        _seed_briefing(db_engine, uid, sent=False)
        _seed_briefing(db_engine, uid, sent=True)
        patches = _patch_engine(db_engine)
        for p in patches:
            p.start()
        result = runner.invoke(app, ["briefing", "ls", "--unsent"])
        for p in patches:
            p.stop()
        assert result.exit_code == 0
        # Should show the unsent one
        assert "no" in result.output

    def test_ls_json(self, db_engine):
        uid = _seed_user(db_engine)
        _seed_briefing(db_engine, uid)
        patches = _patch_engine(db_engine)
        for p in patches:
            p.start()
        result = runner.invoke(app, ["--json", "briefing", "ls"])
        for p in patches:
            p.stop()
        data = json.loads(result.output)
        assert len(data) == 1


class TestBriefingShow:
    def test_show_briefing(self, db_engine):
        uid = _seed_user(db_engine)
        bid = _seed_briefing(db_engine, uid)
        patches = _patch_engine(db_engine)
        for p in patches:
            p.start()
        result = runner.invoke(app, ["briefing", "show", str(bid)])
        for p in patches:
            p.stop()
        assert result.exit_code == 0
        assert "Test briefing" in result.output

    def test_show_not_found(self, db_engine):
        patches = _patch_engine(db_engine)
        for p in patches:
            p.start()
        result = runner.invoke(app, ["briefing", "show", "9999"])
        for p in patches:
            p.stop()
        assert result.exit_code == 1

    def test_show_json(self, db_engine):
        uid = _seed_user(db_engine)
        bid = _seed_briefing(db_engine, uid)
        patches = _patch_engine(db_engine)
        for p in patches:
            p.start()
        result = runner.invoke(app, ["--json", "briefing", "show", str(bid)])
        for p in patches:
            p.stop()
        data = json.loads(result.output)
        assert data["story_count"] == 3
