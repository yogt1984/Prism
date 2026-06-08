"""Core TTS module: converts text scripts to MP3 audio files.

Uses OpenAI TTS API with chunking (4096-char limit per request),
retry/circuit-breaker for resilience, and pydub for MP3 concatenation.
"""

import io
import logging
import re
from dataclasses import dataclass
from pathlib import Path

from openai import OpenAI
from pydub import AudioSegment

from prism.circuit_breaker import openai_tts_breaker
from prism.metrics import (
    tts_chars_processed_total,
    tts_duration_seconds,
    tts_failed_total,
    tts_generated_total,
)
from prism.retry import retry_on_transient

logger = logging.getLogger(__name__)

SILENCE_GAP_MS = 200  # milliseconds between chunks


class TTSError(Exception):
    """Raised on TTS validation or synthesis failure."""


@dataclass
class TTSResult:
    path: Path  # absolute path to the MP3 file
    duration_sec: int  # playback duration in seconds
    size_bytes: int  # file size
    chunks_processed: int  # number of API calls made
    total_chars: int  # total characters synthesized


# ── Internal helpers ────────────────────────────────────────────────


def _validate_input(text: str, max_chars: int) -> str:
    """Validate and clean the input text."""
    text = text.strip()

    if not text:
        raise TTSError("Empty text — nothing to synthesize")

    if len(text) > max_chars:
        raise TTSError(
            f"Text too long: {len(text)} chars (max {max_chars})"
        )

    # Strip phonetic hints meant for the script but not for TTS
    # W_AI adds [YEL-en] style hints — OpenAI TTS reads brackets literally
    text = re.sub(r"\[([A-Z]+-[A-Za-z]+(?:-[A-Za-z]+)*)\]", "", text)
    text = re.sub(r"\s{2,}", " ", text)  # collapse double spaces from removal

    return text.strip()


def _chunk_text(text: str, max_chars: int) -> list[str]:
    """Split text into chunks on sentence boundaries.

    Strategy:
    1. Split on paragraph breaks (double newline) first
    2. If a paragraph exceeds max_chars, split on sentence endings
    3. If a sentence exceeds max_chars, split on clause boundaries
    4. Last resort: hard split at max_chars
    """
    chunks: list[str] = []
    current = ""

    paragraphs = text.split("\n\n")

    for para in paragraphs:
        para = para.strip()
        if not para:
            continue

        # If adding this paragraph stays within limit
        if len(current) + len(para) + 2 <= max_chars:
            current = f"{current}\n\n{para}" if current else para
            continue

        # Flush current chunk if non-empty
        if current:
            chunks.append(current.strip())
            current = ""

        # If paragraph itself fits
        if len(para) <= max_chars:
            current = para
            continue

        # Split paragraph into sentences
        sentences = re.split(r"(?<=[.!?])\s+", para)
        for sentence in sentences:
            if len(current) + len(sentence) + 1 <= max_chars:
                current = f"{current} {sentence}" if current else sentence
            else:
                if current:
                    chunks.append(current.strip())
                if len(sentence) <= max_chars:
                    current = sentence
                else:
                    # Sentence too long — split on clauses
                    clauses = re.split(r"(?<=[,;])\s+", sentence)
                    current = ""
                    for clause in clauses:
                        if len(current) + len(clause) + 1 <= max_chars:
                            current = f"{current} {clause}" if current else clause
                        else:
                            if current:
                                chunks.append(current.strip())
                            current = clause[:max_chars]  # hard limit fallback

    if current:
        chunks.append(current.strip())

    return [c for c in chunks if c]


@openai_tts_breaker
@retry_on_transient(max_retries=3, base_delay=2.0)
def _synthesize_chunk(
    client: OpenAI,
    text: str,
    voice: str,
    model: str,
) -> bytes:
    """Call OpenAI TTS API for a single chunk. Returns raw MP3 bytes."""
    response = client.audio.speech.create(
        model=model,
        voice=voice,
        input=text,
        response_format="mp3",
    )
    return response.content


def _concatenate_chunks(chunk_bytes_list: list[bytes]) -> AudioSegment:
    """Join MP3 chunks with silence gaps between them."""
    silence = AudioSegment.silent(duration=SILENCE_GAP_MS)
    combined = AudioSegment.empty()

    for i, chunk_bytes in enumerate(chunk_bytes_list):
        segment = AudioSegment.from_mp3(io.BytesIO(chunk_bytes))
        combined += segment
        if i < len(chunk_bytes_list) - 1:
            combined += silence

    return combined


def _export_and_measure(
    audio: AudioSegment,
    output_path: Path,
) -> tuple[int, int]:
    """Export to MP3 and return (duration_sec, size_bytes)."""
    audio.export(str(output_path), format="mp3", bitrate="128k")
    duration_sec = int(audio.duration_seconds)
    size_bytes = output_path.stat().st_size
    return duration_sec, size_bytes


# ── Public API ──────────────────────────────────────────────────────


def synthesize_briefing(
    briefing_id: int,
    text: str,
    voice: str | None = None,
    model: str | None = None,
) -> TTSResult:
    """Full TTS pipeline: validate -> chunk -> synthesize -> concatenate -> export.

    Args:
        briefing_id: Used to name the output file.
        text: The full audio script text (from W_AI).
        voice: Override config voice (default: settings.tts_voice).
        model: Override config model (default: settings.tts_model).

    Returns:
        TTSResult with file path, duration, and size.

    Raises:
        TTSError: On validation failure or unrecoverable API error.
        CircuitOpenError: If the OpenAI TTS circuit breaker is open.
    """
    import time

    from prism.config import get_settings

    start = time.monotonic()
    s = get_settings()

    if not s.openai_api_key:
        raise TTSError("OpenAI API key not configured")

    voice = voice or s.tts_voice
    model = model or s.tts_model

    # 1. Validate and clean
    clean_text = _validate_input(text, s.tts_max_chars)

    # 2. Chunk
    chunks = _chunk_text(clean_text, s.tts_chunk_size)
    logger.info(
        "TTS: briefing %d split into %d chunks (%d chars total)",
        briefing_id,
        len(chunks),
        len(clean_text),
    )

    # 3. Synthesize each chunk
    client = OpenAI(api_key=s.openai_api_key)
    chunk_audio: list[bytes] = []

    try:
        for i, chunk in enumerate(chunks):
            logger.debug(
                "TTS: synthesizing chunk %d/%d (%d chars)",
                i + 1,
                len(chunks),
                len(chunk),
            )
            audio_bytes = _synthesize_chunk(client, chunk, voice, model)
            chunk_audio.append(audio_bytes)
            tts_chars_processed_total.inc(len(chunk))

        # 4. Concatenate
        combined = _concatenate_chunks(chunk_audio)

        # 5. Export
        output_dir = Path(s.audio_storage_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / f"{briefing_id}.mp3"

        duration_sec, size_bytes = _export_and_measure(combined, output_path)

        elapsed = time.monotonic() - start
        tts_generated_total.inc()
        tts_duration_seconds.observe(elapsed)

        logger.info(
            "TTS: briefing %d complete — %ds, %d bytes, %s",
            briefing_id,
            duration_sec,
            size_bytes,
            output_path,
        )

        return TTSResult(
            path=output_path,
            duration_sec=duration_sec,
            size_bytes=size_bytes,
            chunks_processed=len(chunks),
            total_chars=len(clean_text),
        )
    except Exception:
        tts_failed_total.inc()
        raise
