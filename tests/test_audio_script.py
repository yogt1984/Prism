"""T19.1: Audio script briefing format tests."""

import json
import re
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


def _seed_data(engine, n_clusters=1, fmt=BriefingFormat.AUDIO_SCRIPT):
    """Create a pro user, source, and cluster(s) with perspectives."""
    with Session(engine) as s:
        user = User(
            email="audio@test.com", interests="finance,technology",
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

        clusters = []
        for i in range(n_clusters):
            first_seen = datetime.now(UTC) - timedelta(hours=2)
            cluster = StoryCluster(
                headline=f"Markets Rally on Fed Decision {i}",
                summary=f"Stock markets surged after event {i}.",
                categories="finance,technology",
                status=StoryStatus.ANALYZED,
                article_count=3,
                first_seen=first_seen,
            )
            s.add(cluster)
            s.commit()
            s.refresh(cluster)

            p1 = Perspective(
                cluster_id=cluster.id, source_id=source1.id,
                summary="Reuters frames this as a dovish pivot.",
                sentiment=0.4, bias_label="center",
                key_claims=json.dumps(["Fed held rates (Source: Reuters)"]),
            )
            p2 = Perspective(
                cluster_id=cluster.id, source_id=source2.id,
                summary="Bloomberg emphasizes market reaction.",
                sentiment=0.6, bias_label="center_right",
                key_claims=json.dumps(["S&P 500 up 2% (Source: Bloomberg)"]),
            )
            s.add_all([p1, p2])
            s.commit()
            clusters.append(cluster)

        # Detached copies
        user_d = User(
            id=user.id, email=user.email,
            interests=user.interests, is_pro=True,
            preferred_format=fmt,
        )
        clusters_d = [
            StoryCluster(
                id=c.id,
                headline=c.headline,
                summary=c.summary,
                categories=c.categories,
                status=StoryStatus.ANALYZED,
                article_count=c.article_count,
                first_seen=c.first_seen,
            )
            for c in clusters
        ]
        return user_d, clusters_d


# Sample audio script for mocking Claude's response
SAMPLE_AUDIO = (
    "Good morning. Here's your briefing for today. "
    "The Federal Reserve held interest rates steady yesterday, "
    "according to Reuters, sending markets sharply higher. "
    "The S&P 500 rose two percent on the news, as reported by Bloomberg. "
    "However, sources disagree on the long-term outlook. "
    "Reuters frames this as a dovish pivot, while Bloomberg emphasizes "
    "the immediate market reaction. "
    "Moving on to technology. "
    "Major tech companies reported strong quarterly earnings, "
    "according to Reuters. Analysts remain divided on forward guidance, "
    "as reported by Bloomberg. "
    "Also worth noting, several emerging market currencies strengthened "
    "against the dollar, according to Reuters. "
    "That's your briefing for today. Stay informed."
)


class TestAudioScriptFormat:

    def test_audio_script_no_html_tags(self, db_engine):
        """Audio script output must not contain HTML tags."""
        user, clusters = _seed_data(db_engine)
        w_ai = WriterAgent()

        mock_response = MagicMock()
        mock_response.content = [MagicMock(text=SAMPLE_AUDIO)]

        with patch.object(w_ai, "_call_claude", return_value=mock_response):
            result = w_ai._format_audio_script(user, clusters, db_engine)

        assert "<" not in result or not re.search(r"<[a-zA-Z/]", result)

    def test_audio_script_has_transitions(self, db_engine):
        """Audio script should include transition phrases between stories."""
        user, clusters = _seed_data(db_engine, n_clusters=3)
        w_ai = WriterAgent()

        mock_response = MagicMock()
        mock_response.content = [MagicMock(text=SAMPLE_AUDIO)]

        with patch.object(w_ai, "_call_claude", return_value=mock_response):
            result = w_ai._format_audio_script(user, clusters, db_engine)

        transition_patterns = [
            r"[Mm]oving on",
            r"[Ii]n related news",
            r"[Aa]lso worth noting",
            r"[Tt]urning to",
            r"[Mm]eanwhile",
        ]
        found = any(re.search(p, result) for p in transition_patterns)
        assert found, f"No transition phrases found in: {result[:200]}..."

    def test_audio_script_spoken_attribution(self, db_engine):
        """Attribution should be spoken-form, not parenthetical."""
        user, clusters = _seed_data(db_engine)
        w_ai = WriterAgent()

        mock_response = MagicMock()
        mock_response.content = [MagicMock(text=SAMPLE_AUDIO)]

        with patch.object(w_ai, "_call_claude", return_value=mock_response):
            result = w_ai._format_audio_script(user, clusters, db_engine)

        # Should use "according to" or "as reported by"
        spoken_attr = re.search(r"(according to|as reported by)", result)
        assert spoken_attr, "No spoken-form attribution found"

    def test_audio_script_no_parenthetical_source(self, db_engine):
        """Audio script must not contain (Source: X) parenthetical attribution."""
        user, clusters = _seed_data(db_engine)
        w_ai = WriterAgent()

        mock_response = MagicMock()
        mock_response.content = [MagicMock(text=SAMPLE_AUDIO)]

        with patch.object(w_ai, "_call_claude", return_value=mock_response):
            result = w_ai._format_audio_script(user, clusters, db_engine)

        assert "(Source:" not in result

    def test_audio_script_prompt_includes_story_data(self, db_engine):
        """The prompt sent to Claude should include story JSON data."""
        user, clusters = _seed_data(db_engine)
        w_ai = WriterAgent()

        mock_response = MagicMock()
        mock_response.content = [MagicMock(text=SAMPLE_AUDIO)]

        with patch.object(w_ai, "_call_claude", return_value=mock_response) as mock_call:
            w_ai._format_audio_script(user, clusters, db_engine)

        prompt_sent = mock_call.call_args[0][0]
        assert "spoken-word" in prompt_sent
        assert "Markets Rally" in prompt_sent
        assert "finance" in prompt_sent

    def test_audio_script_word_target_scales_with_stories(self, db_engine):
        """Word target in prompt should scale with story count."""
        user, clusters = _seed_data(db_engine, n_clusters=5)
        w_ai = WriterAgent()

        mock_response = MagicMock()
        mock_response.content = [MagicMock(text=SAMPLE_AUDIO)]

        with patch.object(w_ai, "_call_claude", return_value=mock_response) as mock_call:
            w_ai._format_audio_script(user, clusters, db_engine)

        prompt_sent = mock_call.call_args[0][0]
        # 5 stories * 90 = 450 words
        assert "450" in prompt_sent


class TestAudioScriptIntegration:

    def test_pro_user_audio_script_stored_correctly(self, db_engine):
        """Pro user with audio_script format gets text in content_text, empty content_html."""
        user, clusters = _seed_data(db_engine)
        w_ai = WriterAgent()

        mock_response = MagicMock()
        mock_response.content = [MagicMock(text=SAMPLE_AUDIO)]

        with patch.object(w_ai, "_call_claude", return_value=mock_response):
            with patch.object(w_ai, "send_email") as mock_send:
                briefing = w_ai.create_and_send(user, clusters, engine=db_engine)
                mock_send.assert_not_called()

        assert briefing is not None
        assert briefing.content_html == ""
        assert briefing.content_text != ""
        assert "according to" in briefing.content_text or "as reported by" in briefing.content_text

    def test_audio_script_no_email_sent(self, db_engine):
        """Audio script briefing should not trigger email delivery."""
        user, clusters = _seed_data(db_engine)
        w_ai = WriterAgent()

        mock_response = MagicMock()
        mock_response.content = [MagicMock(text=SAMPLE_AUDIO)]

        with patch.object(w_ai, "_call_claude", return_value=mock_response):
            with patch.object(w_ai, "send_email") as mock_send:
                briefing = w_ai.create_and_send(user, clusters, engine=db_engine)
                mock_send.assert_not_called()

        assert briefing is not None
        assert briefing.sent is False

    def test_audio_script_has_prompt_version(self, db_engine):
        user, clusters = _seed_data(db_engine)
        w_ai = WriterAgent()

        mock_response = MagicMock()
        mock_response.content = [MagicMock(text=SAMPLE_AUDIO)]

        with patch.object(w_ai, "_call_claude", return_value=mock_response):
            with patch.object(w_ai, "send_email"):
                briefing = w_ai.create_and_send(user, clusters, engine=db_engine)

        assert briefing.prompt_version == BRIEFING_PROMPT_VERSION

    def test_audio_script_persists_in_db(self, db_engine):
        user, clusters = _seed_data(db_engine)
        w_ai = WriterAgent()

        mock_response = MagicMock()
        mock_response.content = [MagicMock(text=SAMPLE_AUDIO)]

        with patch.object(w_ai, "_call_claude", return_value=mock_response):
            with patch.object(w_ai, "send_email"):
                briefing = w_ai.create_and_send(user, clusters, engine=db_engine)
                bid = briefing.id

        with Session(db_engine) as s:
            b = s.get(Briefing, bid)
            assert b is not None
            assert b.content_html == ""
            assert b.content_text != ""

    def test_free_user_audio_falls_back_to_email(self, db_engine):
        """Free user requesting audio_script should fall back to email."""
        with Session(db_engine) as s:
            user = User(
                email="free@test.com", interests="finance",
                preferred_format=BriefingFormat.AUDIO_SCRIPT, is_pro=False,
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

            user_d = User(
                id=user.id, email=user.email,
                interests=user.interests, is_pro=False,
                preferred_format=BriefingFormat.AUDIO_SCRIPT,
            )

        w_ai = WriterAgent()
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text="<h1>Email</h1>")]

        with patch.object(w_ai, "client") as mock_client:
            mock_client.messages.create.return_value = mock_response
            with patch.object(w_ai, "send_email", return_value=False):
                briefing = w_ai.create_and_send(user_d, [cluster], engine=db_engine)

        assert briefing is not None
        assert briefing.content_html == "<h1>Email</h1>"
        assert briefing.content_text == ""

    def test_audio_uses_dedicated_prompt(self, db_engine):
        """Audio script should use AUDIO_SCRIPT_PROMPT, not BRIEFING_PROMPT."""
        user, clusters = _seed_data(db_engine)
        w_ai = WriterAgent()

        mock_response = MagicMock()
        mock_response.content = [MagicMock(text=SAMPLE_AUDIO)]

        with patch.object(w_ai, "_call_claude", return_value=mock_response) as mock_call:
            w_ai._format_audio_script(user, clusters, db_engine)

        prompt_sent = mock_call.call_args[0][0]
        # Audio prompt should have audio-specific instructions
        assert "spoken-word" in prompt_sent
        assert "according to" in prompt_sent.lower() or "transition phrases" in prompt_sent.lower()
        # Should NOT have email-specific instructions
        assert "<h2>" not in prompt_sent
