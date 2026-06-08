"""Tests for 03_02: TTS core module."""

import io
import os
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import pytest
from pydub import AudioSegment

from prism.tts import (
    TTSError,
    TTSResult,
    _chunk_text,
    _concatenate_chunks,
    _export_and_measure,
    _validate_input,
    synthesize_briefing,
)


# ── Helpers ─────────────────────────────────────────────────────────


def _make_mp3_bytes(duration_ms: int = 500) -> bytes:
    """Generate minimal valid MP3 bytes using pydub."""
    seg = AudioSegment.silent(duration=duration_ms)
    buf = io.BytesIO()
    seg.export(buf, format="mp3")
    return buf.getvalue()


SAMPLE_MP3 = _make_mp3_bytes(500)


# ── _validate_input ─────────────────────────────────────────────────


def test_validate_empty_raises():
    with pytest.raises(TTSError, match="Empty text"):
        _validate_input("", 50000)


def test_validate_whitespace_only_raises():
    with pytest.raises(TTSError, match="Empty text"):
        _validate_input("   \n  ", 50000)


def test_validate_too_long_raises():
    with pytest.raises(TTSError, match="too long"):
        _validate_input("x" * 100, 50)


def test_validate_strips_phonetic_hints():
    result = _validate_input("Janet Yellen [YEL-en] spoke today.", 50000)
    assert "[" not in result
    assert "YEL-en" not in result
    assert "Janet Yellen spoke today." in result


def test_validate_strips_multi_part_hints():
    result = _validate_input("Xi Jinping [SHEE-jin-PING] met Kim.", 50000)
    assert "[" not in result
    assert "SHEE-jin-PING" not in result


def test_validate_preserves_normal_brackets():
    """Non-phonetic brackets are kept."""
    result = _validate_input("GDP grew [2.5%] last quarter.", 50000)
    assert "[2.5%]" in result


def test_validate_collapses_double_spaces():
    result = _validate_input("word [YEL-en] other", 50000)
    assert "  " not in result


# ── _chunk_text ─────────────────────────────────────────────────────


def test_chunk_single_short():
    chunks = _chunk_text("Hello world.", 4000)
    assert len(chunks) == 1
    assert chunks[0] == "Hello world."


def test_chunk_splits_paragraphs():
    text = "Paragraph one.\n\nParagraph two.\n\nParagraph three."
    chunks = _chunk_text(text, 30)
    assert len(chunks) >= 2
    for c in chunks:
        assert len(c) <= 30


def test_chunk_splits_on_sentences():
    """Long text splits on sentence boundaries."""
    text = ". ".join([f"Sentence {i}" for i in range(100)]) + "."
    chunks = _chunk_text(text, 200)
    assert len(chunks) > 1
    for chunk in chunks:
        assert chunk.endswith(".")
        assert len(chunk) <= 200


def test_chunk_handles_long_paragraph():
    """Single paragraph exceeding limit splits on sentences."""
    text = "A" * 3000 + ". " + "B" * 3000 + "."
    chunks = _chunk_text(text, 4000)
    assert len(chunks) == 2


def test_chunk_clause_fallback():
    """Sentences exceeding limit split on clauses."""
    # Single sentence with commas, no periods
    text = ", ".join([f"clause {i}" for i in range(50)])
    chunks = _chunk_text(text, 100)
    assert len(chunks) > 1
    for c in chunks:
        assert len(c) <= 100


def test_chunk_preserves_all_text():
    """Chunking doesn't lose content."""
    text = "First paragraph.\n\nSecond paragraph.\n\nThird paragraph."
    chunks = _chunk_text(text, 30)
    combined = " ".join(chunks)
    assert "First paragraph." in combined
    assert "Second paragraph." in combined
    assert "Third paragraph." in combined


def test_chunk_empty_input():
    chunks = _chunk_text("", 4000)
    assert chunks == []


def test_chunk_respects_max_chars():
    """No chunk exceeds max_chars."""
    text = " ".join(["word"] * 500)
    chunks = _chunk_text(text, 100)
    for c in chunks:
        assert len(c) <= 100


# ── _concatenate_chunks ────────────────────────────────────────────


def test_concatenate_single_chunk():
    seg = _concatenate_chunks([SAMPLE_MP3])
    assert seg.duration_seconds > 0


def test_concatenate_multiple_adds_silence():
    """Multi-chunk result is longer than sum of parts (silence gaps)."""
    seg1 = AudioSegment.from_mp3(io.BytesIO(SAMPLE_MP3))
    dur1 = seg1.duration_seconds

    combined = _concatenate_chunks([SAMPLE_MP3, SAMPLE_MP3])
    # Should be: 2 * dur1 + 200ms gap
    assert combined.duration_seconds > dur1 * 2 - 0.01  # tolerance
    assert combined.duration_seconds >= dur1 * 2 + 0.15  # at least some gap


def test_concatenate_three_chunks_two_gaps():
    """Three chunks should have two silence gaps."""
    seg1 = AudioSegment.from_mp3(io.BytesIO(SAMPLE_MP3))
    dur1 = seg1.duration_seconds

    combined = _concatenate_chunks([SAMPLE_MP3, SAMPLE_MP3, SAMPLE_MP3])
    # 3 * dur1 + 2 * 0.2s gaps
    expected_min = dur1 * 3 + 0.3  # at least 0.3s of gap
    assert combined.duration_seconds >= expected_min


# ── _export_and_measure ─────────────────────────────────────────────


def test_export_creates_file(tmp_path):
    seg = AudioSegment.silent(duration=2000)
    output = tmp_path / "test.mp3"
    duration, size = _export_and_measure(seg, output)
    assert output.exists()
    assert duration == 2
    assert size == output.stat().st_size
    assert size > 0


def test_export_subdirectory(tmp_path):
    seg = AudioSegment.silent(duration=1000)
    output = tmp_path / "sub" / "test.mp3"
    output.parent.mkdir(parents=True)
    duration, size = _export_and_measure(seg, output)
    assert output.exists()
    assert duration == 1


# ── synthesize_briefing (mocked OpenAI) ────────────────────────────


@pytest.fixture()
def tts_env(monkeypatch, tmp_path):
    """Set up config for TTS tests."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-openai-test")
    monkeypatch.setenv("AUDIO_STORAGE_DIR", str(tmp_path / "audio"))
    import prism.config as cfg
    cfg._settings = None
    yield tmp_path
    cfg._settings = None


@pytest.fixture()
def mock_openai():
    """Mock OpenAI client creation and TTS API call."""
    mock_response = Mock()
    mock_response.content = SAMPLE_MP3

    mock_client = MagicMock()
    mock_client.audio.speech.create.return_value = mock_response

    with patch("prism.tts.OpenAI", return_value=mock_client) as mock_cls:
        mock_cls._client = mock_client
        yield mock_client


def test_synthesize_short_text(tts_env, mock_openai):
    """Short text produces single-chunk MP3."""
    from prism.circuit_breaker import openai_tts_breaker
    openai_tts_breaker.reset()

    result = synthesize_briefing(1, "This is a test briefing.")
    assert isinstance(result, TTSResult)
    assert result.path.exists()
    assert result.chunks_processed == 1
    assert result.duration_sec >= 0
    assert result.size_bytes > 0
    assert result.total_chars > 0

    openai_tts_breaker.reset()


def test_synthesize_multi_chunk(tts_env, mock_openai):
    """Long text produces multi-chunk MP3."""
    from prism.circuit_breaker import openai_tts_breaker
    openai_tts_breaker.reset()

    # ~10000 chars — should be 3+ chunks at 4000 max
    text = ". ".join([f"Sentence number {i} with some padding text" for i in range(250)]) + "."
    result = synthesize_briefing(2, text)
    assert result.chunks_processed >= 3
    assert result.path.exists()
    assert mock_openai.audio.speech.create.call_count == result.chunks_processed

    openai_tts_breaker.reset()


def test_synthesize_output_path(tts_env, mock_openai):
    """Output file is at audio_storage_dir/{briefing_id}.mp3."""
    from prism.circuit_breaker import openai_tts_breaker
    openai_tts_breaker.reset()

    result = synthesize_briefing(42, "Test text.")
    assert result.path.name == "42.mp3"
    assert result.path.parent == tts_env / "audio"

    openai_tts_breaker.reset()


def test_synthesize_empty_text_raises(tts_env):
    with pytest.raises(TTSError, match="Empty text"):
        synthesize_briefing(1, "")


def test_synthesize_over_max_chars_raises(tts_env):
    with pytest.raises(TTSError, match="too long"):
        synthesize_briefing(1, "x" * 51000)


def test_synthesize_no_openai_key(monkeypatch, tmp_path):
    """Missing OpenAI key raises TTSError."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setenv("AUDIO_STORAGE_DIR", str(tmp_path / "audio"))
    import prism.config as cfg
    cfg._settings = None

    with pytest.raises(TTSError, match="not configured"):
        synthesize_briefing(1, "Some text.")

    cfg._settings = None


def test_synthesize_voice_override(tts_env, mock_openai):
    """Voice parameter overrides config default."""
    from prism.circuit_breaker import openai_tts_breaker
    openai_tts_breaker.reset()

    synthesize_briefing(1, "Test.", voice="nova")
    call_kwargs = mock_openai.audio.speech.create.call_args.kwargs
    assert call_kwargs["voice"] == "nova"

    openai_tts_breaker.reset()


def test_synthesize_model_override(tts_env, mock_openai):
    """Model parameter overrides config default."""
    from prism.circuit_breaker import openai_tts_breaker
    openai_tts_breaker.reset()

    synthesize_briefing(1, "Test.", model="tts-1")
    call_kwargs = mock_openai.audio.speech.create.call_args.kwargs
    assert call_kwargs["model"] == "tts-1"

    openai_tts_breaker.reset()


def test_synthesize_strips_phonetic_before_api(tts_env, mock_openai):
    """Phonetic hints are stripped before sending to OpenAI."""
    from prism.circuit_breaker import openai_tts_breaker
    openai_tts_breaker.reset()

    synthesize_briefing(1, "Janet Yellen [YEL-en] spoke today.")
    call_kwargs = mock_openai.audio.speech.create.call_args.kwargs
    assert "[YEL-en]" not in call_kwargs["input"]
    assert "Janet Yellen" in call_kwargs["input"]

    openai_tts_breaker.reset()


def test_synthesize_updates_metrics(tts_env, mock_openai):
    """Successful synthesis increments metrics."""
    from prism.circuit_breaker import openai_tts_breaker
    from prism.metrics import tts_chars_processed_total, tts_generated_total

    openai_tts_breaker.reset()
    before_gen = tts_generated_total.value
    before_chars = tts_chars_processed_total.value

    synthesize_briefing(1, "Some text for metrics test.")

    assert tts_generated_total.value == before_gen + 1
    assert tts_chars_processed_total.value > before_chars

    openai_tts_breaker.reset()


def test_synthesize_failure_increments_failed_metric(tts_env, mock_openai):
    """API failure increments tts_failed_total."""
    from prism.circuit_breaker import openai_tts_breaker
    from prism.metrics import tts_failed_total

    openai_tts_breaker.reset()
    mock_openai.audio.speech.create.side_effect = RuntimeError("boom")
    before = tts_failed_total.value

    with pytest.raises(RuntimeError):
        synthesize_briefing(1, "Test.")

    assert tts_failed_total.value == before + 1

    openai_tts_breaker.reset()


def test_synthesize_circuit_breaker_opens(tts_env, mock_openai):
    """After 5 failures, circuit breaker blocks further calls."""
    from prism.circuit_breaker import CircuitOpenError, CircuitState, openai_tts_breaker

    openai_tts_breaker.reset()
    mock_openai.audio.speech.create.side_effect = RuntimeError("fail")

    for _ in range(5):
        with pytest.raises(RuntimeError):
            synthesize_briefing(1, "Test.")

    assert openai_tts_breaker.state == CircuitState.OPEN

    with pytest.raises(CircuitOpenError):
        synthesize_briefing(1, "Test.")

    openai_tts_breaker.reset()


# ── Integration test (real OpenAI, guarded) ─────────────────────────


@pytest.mark.skipif(not os.getenv("OPENAI_API_KEY"), reason="No OpenAI key")
def test_real_tts_small_input(tmp_path, monkeypatch):
    """Smoke test with real API — tiny input to minimize cost."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
    monkeypatch.setenv("AUDIO_STORAGE_DIR", str(tmp_path / "audio"))
    import prism.config as cfg
    cfg._settings = None

    from prism.circuit_breaker import openai_tts_breaker
    openai_tts_breaker.reset()

    result = synthesize_briefing(999, "This is a test.")
    assert result.path.exists()
    assert result.duration_sec >= 1
    result.path.unlink()

    openai_tts_breaker.reset()
    cfg._settings = None
