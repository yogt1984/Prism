"""Tests for 03_03: W_AI TTS integration, CLI commands, and audio cleanup."""

import io
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from pydub import AudioSegment
from sqlmodel import Session, SQLModel, create_engine, select

from prism.models import Briefing, BriefingFormat, User


# ── Helpers ─────────────────────────────────────────────────────────


def _make_mp3_bytes(duration_ms: int = 500) -> bytes:
    seg = AudioSegment.silent(duration=duration_ms)
    buf = io.BytesIO()
    seg.export(buf, format="mp3")
    return buf.getvalue()


SAMPLE_MP3 = _make_mp3_bytes(500)


def _make_tts_result(briefing_id: int, tmp_path: Path):
    """Return a TTSResult-like object for mocking."""
    from prism.tts import TTSResult

    audio_dir = tmp_path / "audio"
    audio_dir.mkdir(exist_ok=True)
    mp3_path = audio_dir / f"{briefing_id}.mp3"
    mp3_path.write_bytes(SAMPLE_MP3)
    return TTSResult(
        path=mp3_path,
        duration_sec=10,
        size_bytes=len(SAMPLE_MP3),
        chunks_processed=1,
        total_chars=100,
    )


# ── Fixtures ────────────────────────────────────────────────────────


@pytest.fixture()
def db_engine(tmp_path):
    url = f"sqlite:///{tmp_path / 'test.db'}"
    engine = create_engine(url, connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    yield engine
    engine.dispose()


@pytest.fixture()
def pro_user(db_engine):
    with Session(db_engine) as session:
        user = User(
            email="pro@test.com",
            is_pro=True,
            preferred_format=BriefingFormat.AUDIO_SCRIPT,
            interests="technology",
        )
        session.add(user)
        session.commit()
        session.refresh(user)
        return user


@pytest.fixture()
def email_user(db_engine):
    with Session(db_engine) as session:
        user = User(
            email="free@test.com",
            is_pro=False,
            preferred_format=BriefingFormat.EMAIL,
            interests="finance",
        )
        session.add(user)
        session.commit()
        session.refresh(user)
        return user


@pytest.fixture()
def mock_claude():
    """Mock Claude API so WriterAgent doesn't need a real key."""
    mock_msg = MagicMock()
    mock_msg.content = [MagicMock(text="<p>Test briefing content</p>")]
    with patch("prism.agents.w_ai.anthropic.Anthropic") as mock_cls:
        mock_client = MagicMock()
        mock_client.messages.create.return_value = mock_msg
        mock_cls.return_value = mock_client
        yield mock_client


@pytest.fixture()
def mock_resend():
    with patch("prism.agents.w_ai.resend") as mock:
        yield mock


@pytest.fixture()
def tts_env(monkeypatch, tmp_path):
    """Configure settings for TTS tests."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-openai-test")
    monkeypatch.setenv("AUDIO_STORAGE_DIR", str(tmp_path / "audio"))
    monkeypatch.setenv("RESEND_API_KEY", "re_test")
    import prism.config as cfg
    cfg._settings = None
    yield tmp_path
    cfg._settings = None


@pytest.fixture()
def no_openai_env(monkeypatch, tmp_path):
    """Configure settings without OpenAI key."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setenv("AUDIO_STORAGE_DIR", str(tmp_path / "audio"))
    monkeypatch.setenv("RESEND_API_KEY", "re_test")
    import prism.config as cfg
    cfg._settings = None
    yield tmp_path
    cfg._settings = None


def _make_clusters(db_engine):
    """Create minimal story clusters for W_AI."""
    from prism.models import Source, StoryCluster

    with Session(db_engine) as session:
        src = Source(name="Reuters", url="https://reuters.com", trust_score=0.9)
        session.add(src)
        session.commit()

        cluster = StoryCluster(
            headline="Test Story",
            summary="A test story summary.",
            categories="technology",
            article_count=1,
        )
        session.add(cluster)
        session.commit()
        session.refresh(cluster)
        return [cluster]


# ── W_AI: audio format triggers TTS ────────────────────────────────


def test_audio_format_triggers_tts(tts_env, db_engine, pro_user, mock_claude, mock_resend):
    """Audio-format briefing calls synthesize_briefing and updates DB."""
    from prism.agents.w_ai import WriterAgent
    from prism.circuit_breaker import openai_tts_breaker

    openai_tts_breaker.reset()
    clusters = _make_clusters(db_engine)

    with patch("prism.tts.synthesize_briefing") as mock_tts:
        mock_tts.return_value = _make_tts_result(1, tts_env)
        agent = WriterAgent()
        briefing = agent.create_and_send(pro_user, clusters, db_engine)

    mock_tts.assert_called_once()
    assert briefing is not None

    # Check audio fields in DB
    with Session(db_engine) as session:
        b = session.get(Briefing, briefing.id)
        assert b.audio_path == f"audio/{briefing.id}.mp3"
        assert b.audio_duration_sec == 10
        assert b.audio_size_bytes > 0

    openai_tts_breaker.reset()


def test_email_format_skips_tts(tts_env, db_engine, email_user, mock_claude, mock_resend):
    """Email-format briefing does NOT call TTS."""
    from prism.agents.w_ai import WriterAgent

    clusters = _make_clusters(db_engine)

    with patch("prism.tts.synthesize_briefing") as mock_tts:
        agent = WriterAgent()
        briefing = agent.create_and_send(email_user, clusters, db_engine)

    mock_tts.assert_not_called()
    assert briefing is not None
    assert briefing.audio_path == ""


def test_json_format_skips_tts(tts_env, db_engine, mock_claude, mock_resend):
    """JSON-format briefing does NOT call TTS."""
    from prism.agents.w_ai import WriterAgent

    with Session(db_engine) as session:
        user = User(
            email="json@test.com",
            is_pro=True,
            preferred_format=BriefingFormat.JSON_FEED,
            interests="finance",
        )
        session.add(user)
        session.commit()
        session.refresh(user)

    clusters = _make_clusters(db_engine)

    with patch("prism.tts.synthesize_briefing") as mock_tts:
        agent = WriterAgent()
        briefing = agent.create_and_send(user, clusters, db_engine)

    mock_tts.assert_not_called()
    assert briefing.audio_path == ""


# ── W_AI: TTS failure doesn't block briefing ───────────────────────


def test_tts_failure_does_not_block_briefing(tts_env, db_engine, pro_user, mock_claude, mock_resend):
    """TTS error does not prevent briefing creation."""
    from prism.agents.w_ai import WriterAgent
    from prism.circuit_breaker import openai_tts_breaker

    openai_tts_breaker.reset()
    clusters = _make_clusters(db_engine)

    with patch("prism.tts.synthesize_briefing", side_effect=Exception("OpenAI down")):
        with patch("prism.agents.w_ai.send_alert") as mock_alert:
            agent = WriterAgent()
            briefing = agent.create_and_send(pro_user, clusters, db_engine)

    assert briefing is not None
    assert briefing.content_text != ""
    assert briefing.audio_path == ""
    mock_alert.assert_called_once()

    openai_tts_breaker.reset()


def test_tts_error_sends_warning_alert(tts_env, db_engine, pro_user, mock_claude, mock_resend):
    """TTSError sends a WARNING-level alert."""
    from prism.agents.w_ai import WriterAgent
    from prism.alerts import AlertLevel
    from prism.circuit_breaker import openai_tts_breaker
    from prism.tts import TTSError

    openai_tts_breaker.reset()
    clusters = _make_clusters(db_engine)

    with patch("prism.tts.synthesize_briefing", side_effect=TTSError("bad input")):
        with patch("prism.agents.w_ai.send_alert") as mock_alert:
            agent = WriterAgent()
            agent.create_and_send(pro_user, clusters, db_engine)

    mock_alert.assert_called_once()
    _, kwargs = mock_alert.call_args
    assert kwargs["level"] == AlertLevel.WARNING

    openai_tts_breaker.reset()


def test_circuit_open_sends_warning_alert(tts_env, db_engine, pro_user, mock_claude, mock_resend):
    """CircuitOpenError sends a WARNING-level alert and doesn't block briefing."""
    from prism.agents.w_ai import WriterAgent
    from prism.alerts import AlertLevel
    from prism.circuit_breaker import CircuitOpenError, openai_tts_breaker

    openai_tts_breaker.reset()
    clusters = _make_clusters(db_engine)

    with patch(
        "prism.tts.synthesize_briefing",
        side_effect=CircuitOpenError("openai_tts", 300.0),
    ):
        with patch("prism.agents.w_ai.send_alert") as mock_alert:
            agent = WriterAgent()
            briefing = agent.create_and_send(pro_user, clusters, db_engine)

    assert briefing is not None
    assert briefing.audio_path == ""
    mock_alert.assert_called_once()
    _, kwargs = mock_alert.call_args
    assert kwargs["level"] == AlertLevel.WARNING

    openai_tts_breaker.reset()


def test_unexpected_error_sends_error_alert(tts_env, db_engine, pro_user, mock_claude, mock_resend):
    """Unexpected exception sends an ERROR-level alert."""
    from prism.agents.w_ai import WriterAgent
    from prism.alerts import AlertLevel
    from prism.circuit_breaker import openai_tts_breaker

    openai_tts_breaker.reset()
    clusters = _make_clusters(db_engine)

    with patch("prism.tts.synthesize_briefing", side_effect=RuntimeError("disk full")):
        with patch("prism.agents.w_ai.send_alert") as mock_alert:
            agent = WriterAgent()
            briefing = agent.create_and_send(pro_user, clusters, db_engine)

    assert briefing is not None
    mock_alert.assert_called_once()
    _, kwargs = mock_alert.call_args
    assert kwargs["level"] == AlertLevel.ERROR

    openai_tts_breaker.reset()


# ── W_AI: missing OpenAI key skips silently ─────────────────────────


def test_missing_openai_key_skips_tts(no_openai_env, db_engine, pro_user, mock_claude, mock_resend):
    """Without OpenAI key, TTS is skipped silently — no error, no audio."""
    from prism.agents.w_ai import WriterAgent

    clusters = _make_clusters(db_engine)

    with patch("prism.tts.synthesize_briefing") as mock_tts:
        agent = WriterAgent()
        briefing = agent.create_and_send(pro_user, clusters, db_engine)

    mock_tts.assert_not_called()
    assert briefing is not None
    assert briefing.audio_path == ""


# ── CLI: prism briefing synthesize ──────────────────────────────────


def test_cli_synthesize_success(tts_env, db_engine, monkeypatch):
    """CLI synthesize command generates audio for a briefing."""
    from typer.testing import CliRunner

    from prism.cli.briefing import app

    # Create a briefing with text content but no audio
    with Session(db_engine) as session:
        user = User(email="cli@test.com", is_pro=True)
        session.add(user)
        session.commit()
        b = Briefing(user_id=user.id, content_text="Some spoken text.", story_count=1)
        session.add(b)
        session.commit()
        bid = b.id

    with patch("prism.cli.briefing._get_engine", return_value=db_engine):
        with patch("prism.tts.synthesize_briefing") as mock_tts:
            mock_tts.return_value = _make_tts_result(bid, tts_env)
            runner = CliRunner()
            result = runner.invoke(app, ["synthesize", str(bid)])

    assert result.exit_code == 0
    assert "Audio generated" in result.output

    # Verify DB updated
    with Session(db_engine) as session:
        loaded = session.get(Briefing, bid)
        assert loaded.audio_path == f"audio/{bid}.mp3"
        assert loaded.audio_duration_sec == 10


def test_cli_synthesize_not_found(tts_env, db_engine):
    """CLI synthesize with nonexistent ID exits with error."""
    from typer.testing import CliRunner

    from prism.cli.briefing import app

    with patch("prism.cli.briefing._get_engine", return_value=db_engine):
        runner = CliRunner()
        result = runner.invoke(app, ["synthesize", "999"])

    assert result.exit_code == 1


def test_cli_synthesize_no_text(tts_env, db_engine):
    """CLI synthesize on briefing without text content exits with error."""
    from typer.testing import CliRunner

    from prism.cli.briefing import app

    with Session(db_engine) as session:
        user = User(email="notext@test.com", is_pro=True)
        session.add(user)
        session.commit()
        b = Briefing(user_id=user.id, content_html="<p>HTML only</p>", story_count=1)
        session.add(b)
        session.commit()
        bid = b.id

    with patch("prism.cli.briefing._get_engine", return_value=db_engine):
        runner = CliRunner()
        result = runner.invoke(app, ["synthesize", str(bid)])

    assert result.exit_code == 1
    assert "no text content" in result.output


def test_cli_synthesize_already_has_audio(tts_env, db_engine):
    """CLI synthesize on briefing with existing audio exits cleanly."""
    from typer.testing import CliRunner

    from prism.cli.briefing import app

    with Session(db_engine) as session:
        user = User(email="hasaudio@test.com", is_pro=True)
        session.add(user)
        session.commit()
        b = Briefing(
            user_id=user.id,
            content_text="Some text.",
            audio_path="audio/1.mp3",
            story_count=1,
        )
        session.add(b)
        session.commit()
        bid = b.id

    with patch("prism.cli.briefing._get_engine", return_value=db_engine):
        runner = CliRunner()
        result = runner.invoke(app, ["synthesize", str(bid)])

    assert result.exit_code == 0
    assert "already exists" in result.output


# ── CLI: prism briefing synthesize-pending ──────────────────────────


def test_cli_synthesize_pending(tts_env, db_engine):
    """CLI synthesize-pending processes all audio briefings without audio."""
    from typer.testing import CliRunner

    from prism.cli.briefing import app

    with Session(db_engine) as session:
        user = User(
            email="pending@test.com",
            is_pro=True,
            preferred_format=BriefingFormat.AUDIO_SCRIPT,
        )
        session.add(user)
        session.commit()
        for i in range(3):
            b = Briefing(
                user_id=user.id,
                content_text=f"Briefing {i} text.",
                story_count=1,
            )
            session.add(b)
        session.commit()

    with patch("prism.cli.briefing._get_engine", return_value=db_engine):
        with patch("prism.tts.synthesize_briefing") as mock_tts:
            mock_tts.side_effect = [
                _make_tts_result(1, tts_env),
                _make_tts_result(2, tts_env),
                _make_tts_result(3, tts_env),
            ]
            runner = CliRunner()
            result = runner.invoke(app, ["synthesize-pending"])

    assert result.exit_code == 0
    assert "3 synthesized" in result.output
    assert "0 failed" in result.output


def test_cli_synthesize_pending_partial_failure(tts_env, db_engine):
    """CLI synthesize-pending continues on individual failures."""
    from typer.testing import CliRunner

    from prism.cli.briefing import app

    with Session(db_engine) as session:
        user = User(
            email="partial@test.com",
            is_pro=True,
            preferred_format=BriefingFormat.AUDIO_SCRIPT,
        )
        session.add(user)
        session.commit()
        for i in range(2):
            b = Briefing(
                user_id=user.id,
                content_text=f"Briefing {i} text.",
                story_count=1,
            )
            session.add(b)
        session.commit()

    with patch("prism.cli.briefing._get_engine", return_value=db_engine):
        with patch("prism.tts.synthesize_briefing") as mock_tts:
            mock_tts.side_effect = [
                _make_tts_result(1, tts_env),
                RuntimeError("API down"),
            ]
            runner = CliRunner()
            result = runner.invoke(app, ["synthesize-pending"])

    assert result.exit_code == 0
    assert "1 synthesized" in result.output
    assert "1 failed" in result.output
