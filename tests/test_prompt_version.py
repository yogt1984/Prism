"""T17.1: Prompt version tracking tests."""

from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from alembic import command
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, inspect, text
from sqlmodel import Session, select

from prism.agents.a_ai import ANALYSIS_PROMPT_VERSION, AnalysisAgent
from prism.agents.w_ai import BRIEFING_PROMPT_VERSION, WriterAgent
from prism.db import init_db
from prism.models import Briefing, Source, StoryCluster, StoryStatus, User


# ══════════════════════════════════════════════════════════════════════
# Migration tests
# ══════════════════════════════════════════════════════════════════════


def _alembic_cfg(db_url: str):
    from alembic.config import Config
    project_root = Path(__file__).resolve().parent.parent
    cfg = Config(str(project_root / "alembic.ini"))
    cfg.set_main_option("sqlalchemy.url", db_url)
    return cfg


def _make_engine(tmp_path, name="test.db"):
    url = f"sqlite:///{tmp_path / name}"
    return create_engine(url, connect_args={"check_same_thread": False}), url


class TestPromptVersionMigration:

    def test_upgrade_003_adds_storycluster_column(self, tmp_path):
        _, url = _make_engine(tmp_path)
        command.upgrade(_alembic_cfg(url), "003")
        eng = create_engine(url, connect_args={"check_same_thread": False})
        cols = {c["name"] for c in inspect(eng).get_columns("storycluster")}
        assert "prompt_version" in cols
        eng.dispose()

    def test_upgrade_003_adds_briefing_column(self, tmp_path):
        _, url = _make_engine(tmp_path)
        command.upgrade(_alembic_cfg(url), "003")
        eng = create_engine(url, connect_args={"check_same_thread": False})
        cols = {c["name"] for c in inspect(eng).get_columns("briefing")}
        assert "prompt_version" in cols
        eng.dispose()

    def test_upgrade_003_default_empty_string(self, tmp_path):
        _, url = _make_engine(tmp_path)
        cfg = _alembic_cfg(url)
        # Upgrade to 002, insert data, then upgrade to 003
        command.upgrade(cfg, "002")
        eng = create_engine(url, connect_args={"check_same_thread": False})
        with eng.connect() as conn:
            conn.execute(text(
                "INSERT INTO storycluster (headline, first_seen, last_updated) "
                "VALUES ('Test', '2026-01-01', '2026-01-01')"
            ))
            conn.commit()
        command.upgrade(cfg, "003")
        with eng.connect() as conn:
            row = conn.execute(text("SELECT prompt_version FROM storycluster")).fetchone()
            assert row[0] == ""
        eng.dispose()

    def test_downgrade_003_removes_columns(self, tmp_path):
        _, url = _make_engine(tmp_path)
        cfg = _alembic_cfg(url)
        command.upgrade(cfg, "003")
        command.downgrade(cfg, "002")
        eng = create_engine(url, connect_args={"check_same_thread": False})
        sc_cols = {c["name"] for c in inspect(eng).get_columns("storycluster")}
        br_cols = {c["name"] for c in inspect(eng).get_columns("briefing")}
        assert "prompt_version" not in sc_cols
        assert "prompt_version" not in br_cols
        eng.dispose()

    def test_stepwise_001_002_003(self, tmp_path):
        _, url = _make_engine(tmp_path)
        cfg = _alembic_cfg(url)
        command.upgrade(cfg, "001")
        command.upgrade(cfg, "002")
        command.upgrade(cfg, "003")
        eng = create_engine(url, connect_args={"check_same_thread": False})
        with eng.connect() as conn:
            row = conn.execute(text("SELECT version_num FROM alembic_version")).fetchone()
            assert row[0] == "003"
        eng.dispose()

    def test_roundtrip_no_data_loss(self, tmp_path):
        _, url = _make_engine(tmp_path)
        cfg = _alembic_cfg(url)
        command.upgrade(cfg, "003")
        eng = create_engine(url, connect_args={"check_same_thread": False})
        with eng.connect() as conn:
            conn.execute(text(
                "INSERT INTO storycluster (headline, prompt_version, first_seen, last_updated) "
                "VALUES ('Versioned', 'v2', '2026-01-01', '2026-01-01')"
            ))
            conn.commit()
        command.downgrade(cfg, "002")
        command.upgrade(cfg, "003")
        with eng.connect() as conn:
            row = conn.execute(text(
                "SELECT headline FROM storycluster WHERE headline='Versioned'"
            )).fetchone()
            assert row is not None
        eng.dispose()


# ══════════════════════════════════════════════════════════════════════
# A_AI sets prompt_version
# ══════════════════════════════════════════════════════════════════════


@pytest.fixture()
def db_engine(tmp_path):
    url = f"sqlite:///{tmp_path / 'test.db'}"
    engine = init_db(url)
    yield engine
    engine.dispose()


class TestAnalysisPromptVersion:

    def test_analyzed_cluster_has_prompt_version(self, db_engine):
        """After analysis, cluster.prompt_version == ANALYSIS_PROMPT_VERSION."""
        # Seed a raw cluster with articles
        with Session(db_engine) as s:
            source = Source(name="TestSrc", url="test.com")
            s.add(source)
            s.commit()
            s.refresh(source)

            from prism.models import Article
            cluster = StoryCluster(
                headline="Test story", article_count=1,
                status=StoryStatus.RAW,
            )
            s.add(cluster)
            s.commit()
            s.refresh(cluster)

            article = Article(
                cluster_id=cluster.id, source_id=source.id,
                title="Test article", url="test.com/1",
                snippet="Some content about finance.",
            )
            s.add(article)
            s.commit()
            cid = cluster.id

        # Mock Claude API
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text='{"summary": "Test summary", "categories": ["finance"], "perspectives": []}')]

        a_ai = AnalysisAgent()
        with patch.object(a_ai, "client") as mock_client:
            mock_client.messages.create.return_value = mock_response
            a_ai.analyze_cluster(cid, db_engine)

        with Session(db_engine) as s:
            cluster = s.get(StoryCluster, cid)
            assert cluster.prompt_version == ANALYSIS_PROMPT_VERSION

    def test_raw_cluster_has_empty_prompt_version(self, db_engine):
        """Unanalyzed clusters have empty prompt_version."""
        with Session(db_engine) as s:
            cluster = StoryCluster(headline="Raw", status=StoryStatus.RAW)
            s.add(cluster)
            s.commit()
            s.refresh(cluster)
            assert cluster.prompt_version == ""


# ══════════════════════════════════════════════════════════════════════
# W_AI sets prompt_version
# ══════════════════════════════════════════════════════════════════════


class TestBriefingPromptVersion:

    def test_briefing_has_prompt_version(self, db_engine):
        """Generated briefing.prompt_version == BRIEFING_PROMPT_VERSION."""
        with Session(db_engine) as s:
            user = User(email="t@t.com", interests="finance", is_pro=True)
            s.add(user)
            s.commit()
            s.refresh(user)

            cluster = StoryCluster(
                headline="News", categories="finance",
                status=StoryStatus.ANALYZED, article_count=1,
                first_seen=datetime.now(UTC) - timedelta(hours=1),
            )
            s.add(cluster)
            s.commit()
            s.refresh(cluster)
            user_detached = User(
                id=user.id, email=user.email,
                interests=user.interests, is_pro=True,
            )
            clusters = [cluster]

        w_ai = WriterAgent()
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text="<h1>Briefing</h1><p>Content</p>")]

        with patch.object(w_ai, "client") as mock_client:
            mock_client.messages.create.return_value = mock_response
            with patch.object(w_ai, "send_email", return_value=False):
                briefing = w_ai.create_and_send(user_detached, clusters, engine=db_engine)

        assert briefing is not None
        assert briefing.prompt_version == BRIEFING_PROMPT_VERSION

    def test_briefing_prompt_version_stored_in_db(self, db_engine):
        """prompt_version persists after commit."""
        with Session(db_engine) as s:
            user = User(email="store@t.com", interests="finance")
            s.add(user)
            s.commit()
            s.refresh(user)

            briefing = Briefing(
                user_id=user.id, story_count=0,
                prompt_version="test_v1",
            )
            s.add(briefing)
            s.commit()
            s.refresh(briefing)
            bid = briefing.id

        with Session(db_engine) as s:
            b = s.get(Briefing, bid)
            assert b.prompt_version == "test_v1"


# ══════════════════════════════════════════════════════════════════════
# API response includes prompt_version
# ══════════════════════════════════════════════════════════════════════


class TestApiPromptVersion:

    @pytest.fixture()
    def client(self, db_engine):
        from prism.api.app import create_app
        app = create_app()

        def _override_session():
            with Session(db_engine) as s:
                yield s

        from prism.api.routes import _get_session
        app.dependency_overrides[_get_session] = _override_session
        return TestClient(app)

    def test_story_list_includes_prompt_version(self, client, db_engine):
        with Session(db_engine) as s:
            c = StoryCluster(
                headline="Test", categories="finance",
                status=StoryStatus.ANALYZED, article_count=1,
                prompt_version="2",
            )
            s.add(c)
            s.commit()

        resp = client.get("/stories")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) >= 1
        assert "prompt_version" in data[0]
        assert data[0]["prompt_version"] == "2"

    def test_story_detail_includes_prompt_version(self, client, db_engine):
        with Session(db_engine) as s:
            c = StoryCluster(
                headline="Detail", categories="finance",
                status=StoryStatus.ANALYZED, article_count=1,
                prompt_version="2",
            )
            s.add(c)
            s.commit()
            s.refresh(c)
            cid = c.id

        resp = client.get(f"/stories/{cid}")
        assert resp.status_code == 200
        assert resp.json()["prompt_version"] == "2"

    def test_story_empty_prompt_version(self, client, db_engine):
        """Raw clusters have empty prompt_version in API."""
        with Session(db_engine) as s:
            c = StoryCluster(
                headline="Raw", status=StoryStatus.RAW, article_count=0,
            )
            s.add(c)
            s.commit()

        resp = client.get("/stories")
        data = resp.json()
        raw_stories = [s for s in data if s["headline"] == "Raw"]
        assert raw_stories[0]["prompt_version"] == ""
