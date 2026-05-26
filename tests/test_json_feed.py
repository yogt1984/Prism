"""T16.1: JSON feed briefing format tests."""

import json
from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest
from sqlmodel import Session

from prism.agents.w_ai import BRIEFING_PROMPT_VERSION, WriterAgent
from prism.db import init_db
from prism.models import (
    Briefing,
    BriefingFormat,
    Perspective,
    Source,
    StoryCluster,
    StoryStatus,
    User,
)


@pytest.fixture()
def db_engine(tmp_path):
    url = f"sqlite:///{tmp_path / 'test.db'}"
    engine = init_db(url)
    yield engine
    engine.dispose()


def _seed_data(engine, fmt=BriefingFormat.JSON_FEED):
    """Create a pro user, source, cluster with perspectives."""
    with Session(engine) as s:
        user = User(
            email="json@test.com", interests="finance,technology",
            preferred_format=fmt, is_pro=True,
        )
        s.add(user)
        s.commit()
        s.refresh(user)

        source1 = Source(name="Reuters", url="reuters.com", trust_score=0.9)
        source2 = Source(name="Bloomberg", url="bloomberg.com", trust_score=0.85)
        s.add_all([source1, source2])
        s.commit()
        s.refresh(source1)
        s.refresh(source2)

        first_seen = datetime.now(UTC) - timedelta(hours=2)
        cluster = StoryCluster(
            headline="Markets Rally on Fed Decision",
            summary="Stock markets surged after the Federal Reserve held rates steady.",
            categories="finance,technology",
            status=StoryStatus.ANALYZED,
            article_count=3,
            first_seen=first_seen,
        )
        s.add(cluster)
        s.commit()
        s.refresh(cluster)
        cluster_id = cluster.id

        p1 = Perspective(
            cluster_id=cluster_id, source_id=source1.id,
            summary="Reuters frames this as a dovish pivot.",
            sentiment=0.4, bias_label="center",
            key_claims=json.dumps(["Fed held rates (Source: Reuters)"]),
        )
        p2 = Perspective(
            cluster_id=cluster_id, source_id=source2.id,
            summary="Bloomberg emphasizes market reaction.",
            sentiment=0.6, bias_label="center_right",
            key_claims=json.dumps(["S&P 500 up 2% (Source: Bloomberg)"]),
        )
        s.add_all([p1, p2])
        s.commit()

        # Create detached copies to avoid session issues
        user_detached = User(
            id=user.id, email=user.email,
            interests=user.interests, is_pro=True,
            preferred_format=fmt,
        )
        cluster_detached = StoryCluster(
            id=cluster_id,
            headline="Markets Rally on Fed Decision",
            summary="Stock markets surged after the Federal Reserve held rates steady.",
            categories="finance,technology",
            status=StoryStatus.ANALYZED,
            article_count=3,
            first_seen=first_seen,
        )
        return user_detached, [cluster_detached]


class TestJsonFeedFormat:

    def test_json_feed_is_valid_json(self, db_engine):
        user, clusters = _seed_data(db_engine)
        w_ai = WriterAgent()
        result = w_ai._format_json_feed(user, clusters, "raw content", db_engine)
        parsed = json.loads(result)
        assert isinstance(parsed, dict)

    def test_json_feed_has_required_fields(self, db_engine):
        user, clusters = _seed_data(db_engine)
        w_ai = WriterAgent()
        result = w_ai._format_json_feed(user, clusters, "raw content", db_engine)
        feed = json.loads(result)

        assert "version" in feed
        assert feed["version"] == "1.0"
        assert "title" in feed
        assert user.email in feed["title"]
        assert "generated_at" in feed
        assert "items" in feed
        assert isinstance(feed["items"], list)

    def test_json_feed_items_have_required_fields(self, db_engine):
        user, clusters = _seed_data(db_engine)
        w_ai = WriterAgent()
        result = w_ai._format_json_feed(user, clusters, "raw content", db_engine)
        feed = json.loads(result)

        assert len(feed["items"]) == 1
        item = feed["items"][0]

        assert "id" in item
        assert "headline" in item
        assert "summary" in item
        assert "categories" in item
        assert "perspectives" in item
        assert "sources" in item

        assert item["headline"] == "Markets Rally on Fed Decision"
        assert isinstance(item["categories"], list)
        assert "finance" in item["categories"]

    def test_json_feed_includes_perspectives(self, db_engine):
        user, clusters = _seed_data(db_engine)
        w_ai = WriterAgent()
        result = w_ai._format_json_feed(user, clusters, "raw content", db_engine)
        feed = json.loads(result)

        item = feed["items"][0]
        perspectives = item["perspectives"]
        assert len(perspectives) == 2

        # Each perspective has source attribution
        for p in perspectives:
            assert "summary" in p
            assert "sentiment" in p
            assert "bias_label" in p
            assert "key_claims" in p
            assert len(p["key_claims"]) >= 1

    def test_json_feed_includes_sources(self, db_engine):
        user, clusters = _seed_data(db_engine)
        w_ai = WriterAgent()
        result = w_ai._format_json_feed(user, clusters, "raw content", db_engine)
        feed = json.loads(result)

        item = feed["items"][0]
        assert len(item["sources"]) >= 1


class TestJsonFeedIntegration:

    def test_pro_user_json_feed_stored_correctly(self, db_engine):
        """Pro user with json_feed format gets JSON in content_text, empty content_html."""
        user, clusters = _seed_data(db_engine)

        w_ai = WriterAgent()
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text="<h1>Briefing</h1><p>Content</p>")]

        with patch.object(w_ai, "client") as mock_client:
            mock_client.messages.create.return_value = mock_response
            with patch.object(w_ai, "send_email") as mock_send:
                briefing = w_ai.create_and_send(user, clusters, engine=db_engine)

                # Email should NOT be called for JSON feed
                mock_send.assert_not_called()

        assert briefing is not None
        assert briefing.content_html == ""
        assert briefing.content_text != ""

        # content_text should be valid JSON
        feed = json.loads(briefing.content_text)
        assert feed["version"] == "1.0"
        assert len(feed["items"]) == 1

    def test_json_feed_no_email_sent(self, db_engine):
        """JSON feed briefing should not trigger email delivery."""
        user, clusters = _seed_data(db_engine)

        w_ai = WriterAgent()
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text="content")]

        with patch.object(w_ai, "client") as mock_client:
            mock_client.messages.create.return_value = mock_response
            with patch.object(w_ai, "send_email") as mock_send:
                briefing = w_ai.create_and_send(user, clusters, engine=db_engine)
                mock_send.assert_not_called()

        assert briefing is not None
        assert briefing.sent is False

    def test_json_feed_has_prompt_version(self, db_engine):
        user, clusters = _seed_data(db_engine)

        w_ai = WriterAgent()
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text="content")]

        with patch.object(w_ai, "client") as mock_client:
            mock_client.messages.create.return_value = mock_response
            with patch.object(w_ai, "send_email"):
                briefing = w_ai.create_and_send(user, clusters, engine=db_engine)

        assert briefing.prompt_version == BRIEFING_PROMPT_VERSION

    def test_json_feed_persists_in_db(self, db_engine):
        user, clusters = _seed_data(db_engine)

        w_ai = WriterAgent()
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text="content")]

        with patch.object(w_ai, "client") as mock_client:
            mock_client.messages.create.return_value = mock_response
            with patch.object(w_ai, "send_email"):
                briefing = w_ai.create_and_send(user, clusters, engine=db_engine)
                bid = briefing.id

        with Session(db_engine) as s:
            b = s.get(Briefing, bid)
            assert b is not None
            assert b.content_html == ""
            feed = json.loads(b.content_text)
            assert "items" in feed

    def test_email_format_still_works(self, db_engine):
        """Email format should still store HTML and send email."""
        user, clusters = _seed_data(db_engine, fmt=BriefingFormat.EMAIL)

        w_ai = WriterAgent()
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text="<h1>Email</h1>")]

        with patch.object(w_ai, "client") as mock_client:
            mock_client.messages.create.return_value = mock_response
            with patch.object(w_ai, "send_email", return_value=True) as mock_send:
                briefing = w_ai.create_and_send(user, clusters, engine=db_engine)
                mock_send.assert_called_once()

        assert briefing is not None
        assert briefing.content_html == "<h1>Email</h1>"
        assert briefing.content_text == ""

    def test_free_user_falls_back_to_email(self, db_engine):
        """Free user requesting json_feed should fall back to email."""
        with Session(db_engine) as s:
            user = User(
                email="free@test.com", interests="finance",
                preferred_format=BriefingFormat.JSON_FEED, is_pro=False,
            )
            s.add(user)
            s.commit()
            s.refresh(user)

            source = Source(name="Src", url="src.com", trust_score=0.8)
            s.add(source)
            s.commit()
            s.refresh(source)

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
                interests=user.interests, is_pro=False,
                preferred_format=BriefingFormat.JSON_FEED,
            )

        w_ai = WriterAgent()
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text="<h1>Email</h1>")]

        with patch.object(w_ai, "client") as mock_client:
            mock_client.messages.create.return_value = mock_response
            with patch.object(w_ai, "send_email", return_value=False):
                briefing = w_ai.create_and_send(user_detached, [cluster], engine=db_engine)

        # Should fall back to email format
        assert briefing is not None
        assert briefing.content_html == "<h1>Email</h1>"
        assert briefing.content_text == ""
