"""T17.2: Output quality validation tests for A_AI."""

from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, inspect, text
from sqlmodel import Session

from prism.agents.a_ai import ANALYSIS_PROMPT_VERSION, AnalysisAgent
from prism.db import init_db
from prism.models import Article, Source, StoryCluster, StoryStatus, User


# ══════════════════════════════════════════════════════════════════════
# Migration tests
# ══════════════════════════════════════════════════════════════════════


def _alembic_cfg(db_url: str):
    project_root = Path(__file__).resolve().parent.parent
    cfg = Config(str(project_root / "alembic.ini"))
    cfg.set_main_option("sqlalchemy.url", db_url)
    return cfg


class TestQualityScoreMigration:

    def test_upgrade_004_adds_quality_score_column(self, tmp_path):
        url = f"sqlite:///{tmp_path / 'test.db'}"
        command.upgrade(_alembic_cfg(url), "004")
        eng = create_engine(url, connect_args={"check_same_thread": False})
        cols = {c["name"] for c in inspect(eng).get_columns("storycluster")}
        assert "quality_score" in cols
        eng.dispose()

    def test_upgrade_004_default_zero(self, tmp_path):
        url = f"sqlite:///{tmp_path / 'test.db'}"
        cfg = _alembic_cfg(url)
        command.upgrade(cfg, "003")
        eng = create_engine(url, connect_args={"check_same_thread": False})
        with eng.connect() as conn:
            conn.execute(text(
                "INSERT INTO storycluster (headline, first_seen, last_updated) "
                "VALUES ('Test', '2026-01-01', '2026-01-01')"
            ))
            conn.commit()
        command.upgrade(cfg, "004")
        with eng.connect() as conn:
            row = conn.execute(text("SELECT quality_score FROM storycluster")).fetchone()
            assert float(row[0]) == 0.0
        eng.dispose()

    def test_downgrade_004_removes_column(self, tmp_path):
        url = f"sqlite:///{tmp_path / 'test.db'}"
        cfg = _alembic_cfg(url)
        command.upgrade(cfg, "004")
        command.downgrade(cfg, "003")
        eng = create_engine(url, connect_args={"check_same_thread": False})
        cols = {c["name"] for c in inspect(eng).get_columns("storycluster")}
        assert "quality_score" not in cols
        eng.dispose()

    def test_stepwise_001_through_004(self, tmp_path):
        url = f"sqlite:///{tmp_path / 'test.db'}"
        cfg = _alembic_cfg(url)
        for rev in ["001", "002", "003", "004"]:
            command.upgrade(cfg, rev)
        eng = create_engine(url, connect_args={"check_same_thread": False})
        with eng.connect() as conn:
            row = conn.execute(text("SELECT version_num FROM alembic_version")).fetchone()
            assert row[0] == "004"
        eng.dispose()


# ══════════════════════════════════════════════════════════════════════
# _validate_analysis unit tests
# ══════════════════════════════════════════════════════════════════════


class TestValidateAnalysis:

    def _perfect_result(self):
        return {
            "summary": "A" * 100,  # 100 chars, within [50, 500]
            "perspectives": [
                {
                    "source_id": 1,
                    "summary": "Perspective 1",
                    "sentiment": 0.5,
                    "key_claims": ["claim 1 (Source: Outlet A)"],
                },
                {
                    "source_id": 2,
                    "summary": "Perspective 2",
                    "sentiment": -0.3,
                    "key_claims": ["claim 2 (Source: Outlet B)"],
                },
            ],
        }

    def test_perfect_analysis_no_issues(self):
        issues = AnalysisAgent._validate_analysis(self._perfect_result())
        assert issues == []

    def test_perfect_analysis_quality_score_1(self):
        result = self._perfect_result()
        issues = AnalysisAgent._validate_analysis(result)
        n_persp = len(result["perspectives"])
        total = 2 + n_persp * 3
        score = AnalysisAgent._compute_quality_score(issues, total)
        assert score == 1.0

    def test_short_summary_flagged(self):
        result = self._perfect_result()
        result["summary"] = "Short"
        issues = AnalysisAgent._validate_analysis(result)
        assert any("too short" in i.lower() for i in issues)

    def test_empty_summary_flagged(self):
        result = self._perfect_result()
        result["summary"] = ""
        issues = AnalysisAgent._validate_analysis(result)
        assert any("too short" in i.lower() for i in issues)

    def test_long_summary_flagged(self):
        result = self._perfect_result()
        result["summary"] = "A" * 501
        issues = AnalysisAgent._validate_analysis(result)
        assert any("too long" in i.lower() for i in issues)

    def test_too_few_perspectives_flagged(self):
        result = self._perfect_result()
        result["perspectives"] = [result["perspectives"][0]]
        issues = AnalysisAgent._validate_analysis(result)
        assert any("too few perspectives" in i.lower() for i in issues)

    def test_zero_perspectives_flagged(self):
        result = self._perfect_result()
        result["perspectives"] = []
        issues = AnalysisAgent._validate_analysis(result)
        assert any("too few perspectives" in i.lower() for i in issues)

    def test_empty_key_claims_flagged(self):
        result = self._perfect_result()
        result["perspectives"][0]["key_claims"] = []
        issues = AnalysisAgent._validate_analysis(result)
        assert any("empty key_claims" in i.lower() for i in issues)

    def test_sentiment_out_of_range_high(self):
        result = self._perfect_result()
        result["perspectives"][0]["sentiment"] = 1.5
        issues = AnalysisAgent._validate_analysis(result)
        assert any("out of range" in i.lower() for i in issues)

    def test_sentiment_out_of_range_low(self):
        result = self._perfect_result()
        result["perspectives"][1]["sentiment"] = -2.0
        issues = AnalysisAgent._validate_analysis(result)
        assert any("out of range" in i.lower() for i in issues)

    def test_duplicate_source_ids_flagged(self):
        result = self._perfect_result()
        result["perspectives"][1]["source_id"] = 1  # same as perspective 0
        issues = AnalysisAgent._validate_analysis(result)
        assert any("duplicate source_id" in i.lower() for i in issues)

    def test_multiple_issues_all_reported(self):
        result = {
            "summary": "Short",
            "perspectives": [
                {"source_id": 1, "sentiment": 5.0, "key_claims": []},
            ],
        }
        issues = AnalysisAgent._validate_analysis(result)
        # Should have: short summary, too few perspectives, empty key_claims, sentiment out of range
        assert len(issues) >= 3

    def test_quality_score_partial(self):
        result = self._perfect_result()
        result["summary"] = "Short"  # 1 issue
        issues = AnalysisAgent._validate_analysis(result)
        n_persp = len(result["perspectives"])
        total = 2 + n_persp * 3  # 2 + 6 = 8
        score = AnalysisAgent._compute_quality_score(issues, total)
        assert 0.0 < score < 1.0
        assert score == round(7 / 8, 2)  # 7 passed out of 8


# ══════════════════════════════════════════════════════════════════════
# Integration: analyze_cluster sets quality_score
# ══════════════════════════════════════════════════════════════════════


@pytest.fixture()
def db_engine(tmp_path):
    url = f"sqlite:///{tmp_path / 'test.db'}"
    engine = init_db(url)
    yield engine
    engine.dispose()


class TestAnalyzeClusterQualityScore:

    def _seed_cluster(self, engine):
        with Session(engine) as s:
            source = Source(name="TestSrc", url="test.com")
            s.add(source)
            s.commit()
            s.refresh(source)

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
                snippet="Some content about finance and economy.",
            )
            s.add(article)
            s.commit()
            return cluster.id, source.id

    def test_good_analysis_high_quality_score(self, db_engine):
        cid, sid = self._seed_cluster(db_engine)

        good_result = {
            "headline": "Test headline",
            "summary": "A detailed summary of the story covering multiple aspects of the event and its implications for the broader context.",
            "categories": ["finance"],
            "perspectives": [
                {"source_id": sid, "summary": "Perspective A", "sentiment": 0.3, "bias_label": "center", "key_claims": ["claim 1"]},
                {"source_id": sid + 100, "summary": "Perspective B", "sentiment": -0.2, "bias_label": "left", "key_claims": ["claim 2"]},
            ],
        }

        mock_response = MagicMock()
        import json
        mock_response.content = [MagicMock(text=json.dumps(good_result))]

        a_ai = AnalysisAgent()
        with patch.object(a_ai, "client") as mock_client:
            mock_client.messages.create.return_value = mock_response
            a_ai.analyze_cluster(cid, db_engine)

        with Session(db_engine) as s:
            cluster = s.get(StoryCluster, cid)
            assert cluster.quality_score == 1.0
            assert cluster.status == StoryStatus.ANALYZED

    def test_poor_analysis_low_quality_score(self, db_engine):
        cid, sid = self._seed_cluster(db_engine)

        poor_result = {
            "headline": "Test",
            "summary": "Short",  # too short
            "categories": ["finance"],
            "perspectives": [
                # only 1 perspective (need 2), empty claims, bad sentiment
                {"source_id": sid, "summary": "Only one", "sentiment": 5.0, "bias_label": "center", "key_claims": []},
            ],
        }

        mock_response = MagicMock()
        import json
        mock_response.content = [MagicMock(text=json.dumps(poor_result))]

        a_ai = AnalysisAgent()
        with patch.object(a_ai, "client") as mock_client:
            mock_client.messages.create.return_value = mock_response
            a_ai.analyze_cluster(cid, db_engine)

        with Session(db_engine) as s:
            cluster = s.get(StoryCluster, cid)
            assert cluster.quality_score < 1.0
            assert cluster.quality_score >= 0.0

    def test_raw_cluster_has_zero_quality_score(self, db_engine):
        with Session(db_engine) as s:
            cluster = StoryCluster(headline="Raw", status=StoryStatus.RAW)
            s.add(cluster)
            s.commit()
            s.refresh(cluster)
            assert cluster.quality_score == 0.0


# ══════════════════════════════════════════════════════════════════════
# API includes quality_score
# ══════════════════════════════════════════════════════════════════════


class TestApiQualityScore:

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

    def test_story_list_includes_quality_score(self, client, db_engine):
        with Session(db_engine) as s:
            c = StoryCluster(
                headline="Quality", categories="finance",
                status=StoryStatus.ANALYZED, article_count=1,
                quality_score=0.85,
            )
            s.add(c)
            s.commit()

        resp = client.get("/stories")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) >= 1
        quality_stories = [s for s in data if s["headline"] == "Quality"]
        assert quality_stories[0]["quality_score"] == 0.85

    def test_story_detail_includes_quality_score(self, client, db_engine):
        with Session(db_engine) as s:
            c = StoryCluster(
                headline="Detail", categories="finance",
                status=StoryStatus.ANALYZED, article_count=1,
                quality_score=0.92,
            )
            s.add(c)
            s.commit()
            s.refresh(c)
            cid = c.id

        resp = client.get(f"/stories/{cid}")
        assert resp.status_code == 200
        assert resp.json()["quality_score"] == 0.92
