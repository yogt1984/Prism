# 03_02 — TTS Core Module

**Parent:** 03 TTS Audio Briefings
**Depends on:** 03_01 (config, dependencies, circuit breaker)

---

## Objective

Implement the core text-to-speech module that converts a text script into an
MP3 file. Handles chunking (OpenAI has a 4096-char limit per request),
API calls with retry/circuit-breaker, MP3 concatenation with silence gaps,
and metadata extraction.

---

## Module

File: `src/prism/tts.py`

---

## Public API

```python
def synthesize_briefing(
    briefing_id: int,
    text: str,
    voice: str | None = None,
    model: str | None = None,
) -> TTSResult:
    """Convert a briefing text script to an MP3 audio file.

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
```

```python
@dataclass
class TTSResult:
    path: Path              # absolute path to the MP3 file
    duration_sec: int       # playback duration in seconds
    size_bytes: int         # file size
    chunks_processed: int   # number of API calls made
    total_chars: int        # total characters synthesized
```

```python
class TTSError(Exception):
    """Raised on TTS validation or synthesis failure."""
    pass
```

---

## Implementation Steps

### 1. Input Validation

```python
def _validate_input(text: str) -> str:
    """Validate and clean the input text."""
    text = text.strip()

    if not text:
        raise TTSError("Empty text — nothing to synthesize")

    if len(text) > settings.tts_max_chars:
        raise TTSError(
            f"Text too long: {len(text)} chars (max {settings.tts_max_chars})"
        )

    # Strip phonetic hints meant for the script but not for TTS
    # W_AI adds [YEL-en] style hints — OpenAI TTS reads brackets literally
    text = re.sub(r'\[([A-Z]+-[A-Za-z]+(?:-[A-Za-z]+)*)\]', '', text)
    text = re.sub(r'\s{2,}', ' ', text)  # collapse double spaces from removal

    return text
```

**Why strip phonetic hints:** W_AI's audio scripts include `[YEL-en]` style
brackets for human readers. OpenAI TTS would read these literally as "open
bracket, Y-E-L dash E-N, close bracket." Strip them before synthesis.

### 2. Text Chunking

OpenAI TTS API limit: 4096 characters per request. Briefings can be 5,000-25,000
characters. Split into chunks without breaking mid-sentence.

```python
def _chunk_text(text: str, max_chars: int) -> list[str]:
    """Split text into chunks on sentence boundaries.

    Strategy:
    1. Split on paragraph breaks (double newline) first
    2. If a paragraph exceeds max_chars, split on sentence endings
    3. If a sentence exceeds max_chars, split on clause boundaries (comma/semicolon)
    4. Last resort: hard split at max_chars (should never happen for real text)
    """
    chunks: list[str] = []
    current = ""

    # Split into paragraphs
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
        sentences = re.split(r'(?<=[.!?])\s+', para)
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
                    clauses = re.split(r'(?<=[,;])\s+', sentence)
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

    return [c for c in chunks if c]  # filter empty
```

**Chunk size:** `settings.tts_chunk_size` (default 4000) — leaves 96 chars of
headroom below the 4096 API limit for encoding overhead.

### 3. Per-Chunk Synthesis

```python
from openai import OpenAI

from prism.circuit_breaker import openai_tts_breaker
from prism.retry import retry_on_transient

@openai_tts_breaker
@retry_on_transient(max_retries=3, base_delay=2.0)
def _synthesize_chunk(
    client: OpenAI,
    text: str,
    voice: str,
    model: str,
) -> bytes:
    """Call OpenAI TTS API for a single chunk.

    Returns:
        Raw MP3 bytes.
    """
    response = client.audio.speech.create(
        model=model,
        voice=voice,
        input=text,
        response_format="mp3",
    )
    return response.content
```

**Retry behavior (inherited from `retry.py`):**
- Retries on: `httpx.TimeoutException`, `httpx.ConnectError`, `ConnectionError`,
  rate limit errors (429), server errors (5xx)
- 3 attempts with exponential backoff: 2s, 4s, 8s
- Total max wait: ~14 seconds per chunk

**Circuit breaker behavior:**
- Opens after 5 consecutive failures across all calls
- Stays open for 300 seconds (5 minutes)
- Half-open: allows one test call, reopens on failure

### 4. MP3 Concatenation

```python
from pydub import AudioSegment

SILENCE_GAP_MS = 200  # milliseconds between stories

def _concatenate_chunks(chunk_bytes_list: list[bytes]) -> AudioSegment:
    """Join MP3 chunks with silence gaps between them.

    Args:
        chunk_bytes_list: List of raw MP3 bytes from OpenAI.

    Returns:
        Combined AudioSegment.
    """
    silence = AudioSegment.silent(duration=SILENCE_GAP_MS)
    combined = AudioSegment.empty()

    for i, chunk_bytes in enumerate(chunk_bytes_list):
        segment = AudioSegment.from_mp3(io.BytesIO(chunk_bytes))
        combined += segment
        if i < len(chunk_bytes_list) - 1:
            combined += silence

    return combined
```

### 5. Export and Metadata

```python
def _export_and_measure(
    audio: AudioSegment,
    output_path: Path,
) -> tuple[int, int]:
    """Export to MP3 and return (duration_sec, size_bytes)."""
    audio.export(str(output_path), format="mp3", bitrate="128k")

    duration_sec = int(audio.duration_seconds)
    size_bytes = output_path.stat().st_size

    return duration_sec, size_bytes
```

### 6. Full Pipeline (`synthesize_briefing`)

```python
def synthesize_briefing(
    briefing_id: int,
    text: str,
    voice: str | None = None,
    model: str | None = None,
) -> TTSResult:
    """Full TTS pipeline: validate → chunk → synthesize → concatenate → export."""
    from prism.config import get_settings
    s = get_settings()

    if not s.openai_api_key:
        raise TTSError("OpenAI API key not configured")

    voice = voice or s.tts_voice
    model = model or s.tts_model

    # 1. Validate and clean
    clean_text = _validate_input(text)

    # 2. Chunk
    chunks = _chunk_text(clean_text, s.tts_chunk_size)
    logger.info("TTS: briefing %d split into %d chunks (%d chars total)",
                briefing_id, len(chunks), len(clean_text))

    # 3. Synthesize each chunk
    client = OpenAI(api_key=s.openai_api_key)
    chunk_audio: list[bytes] = []

    for i, chunk in enumerate(chunks):
        logger.debug("TTS: synthesizing chunk %d/%d (%d chars)",
                     i + 1, len(chunks), len(chunk))
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

    logger.info("TTS: briefing %d complete — %ds, %d bytes, %s",
                briefing_id, duration_sec, size_bytes, output_path)

    return TTSResult(
        path=output_path,
        duration_sec=duration_sec,
        size_bytes=size_bytes,
        chunks_processed=len(chunks),
        total_chars=len(clean_text),
    )
```

---

## Error Handling

| Failure point | Behavior | Recovery |
|---------------|----------|----------|
| Empty text | `TTSError` raised immediately | Caller (W_AI) logs and skips audio |
| Text too long | `TTSError` raised immediately | Caller logs, briefing delivered as text-only |
| OpenAI API 429 | Retry 3× with backoff | Succeeds on retry or raises |
| OpenAI API 5xx | Retry 3× with backoff | Succeeds on retry or raises |
| OpenAI API auth error | Raises immediately (not transient) | Caller catches, sends ntfy alert |
| Circuit breaker open | `CircuitOpenError` raised | Caller logs, briefing delivered as text-only |
| pydub/ffmpeg failure | Raises `Exception` | Caller catches, sends ntfy alert |
| Disk full | `OSError` on export | Caller catches, sends ntfy alert |
| Partial synthesis (3 of 5 chunks fail) | Raises after retry exhaustion | No partial audio written — all or nothing |

---

## Temporary File Cleanup

No temporary files are written. Chunk audio bytes are held in memory
(`list[bytes]`) and only written to disk as the final concatenated MP3.
Intermediate pydub `AudioSegment` objects are garbage collected normally.

**Memory estimate:**
- 10-story briefing ≈ 10,000 chars ≈ 3 chunks
- Each chunk ≈ 500KB of MP3 audio
- Peak memory: ~1.5MB for chunks + ~1.5MB for concatenated segment = ~3MB
- Well within reasonable limits even for 25-story briefings (~8MB peak)

---

## Acceptance Criteria

| # | Criterion | Verification |
|---|-----------|--------------|
| 1 | Short text (<4000 chars) produces single-chunk MP3 | Pass 2000-char text, verify `chunks_processed=1` |
| 2 | Long text (>4000 chars) produces multi-chunk MP3 | Pass 10,000-char text, verify `chunks_processed>=3` |
| 3 | Chunks split on sentence boundaries | Inspect chunk contents, verify no mid-sentence splits |
| 4 | Phonetic hints are stripped | Pass text with `[YEL-en]`, verify brackets not in chunks |
| 5 | Empty text raises TTSError | Pass `""`, verify exception |
| 6 | Text over 50k chars raises TTSError | Pass 51k chars, verify exception |
| 7 | Silence gaps between chunks | Load output MP3, verify 200ms silence at expected positions |
| 8 | Output file exists at expected path | Verify `data/audio/{id}.mp3` exists |
| 9 | Duration matches actual audio length | Compare `duration_sec` with ffprobe metadata |
| 10 | Size matches actual file size | Compare `size_bytes` with `os.stat()` |
| 11 | Retry handles OpenAI 429 | Mock 429 on first call, success on second, verify result |
| 12 | Circuit breaker opens after 5 failures | Fail 5 calls, verify `CircuitOpenError` on 6th |
| 13 | Unconfigured OpenAI key raises TTSError | Clear key, verify error message |

---

## Testing Strategy

### Unit Tests (mock OpenAI)

```python
def test_chunk_text_single():
    """Short text produces one chunk."""
    chunks = _chunk_text("Hello world.", 4000)
    assert len(chunks) == 1

def test_chunk_text_splits_on_sentences():
    """Long text splits on sentence boundaries."""
    text = ". ".join([f"Sentence {i}" for i in range(100)]) + "."
    chunks = _chunk_text(text, 200)
    for chunk in chunks:
        assert chunk.endswith(".")

def test_chunk_text_handles_long_paragraph():
    """Single paragraph exceeding limit splits on sentences."""
    text = "A" * 3000 + ". " + "B" * 3000 + "."
    chunks = _chunk_text(text, 4000)
    assert len(chunks) == 2

def test_validate_strips_phonetic_hints():
    """Phonetic brackets are removed."""
    result = _validate_input("Janet Yellen [YEL-en] spoke today.")
    assert "[" not in result
    assert "YEL-en" not in result
    assert "Janet Yellen spoke today." in result

def test_synthesize_briefing_produces_mp3(mock_openai, tmp_path):
    """Full pipeline produces a valid MP3."""
    mock_openai.audio.speech.create.return_value = Mock(
        content=SAMPLE_MP3_BYTES
    )
    result = synthesize_briefing(1, "Test briefing text.", voice="alloy")
    assert result.path.exists()
    assert result.duration_sec > 0
    assert result.size_bytes > 0

def test_synthesize_empty_text_raises():
    with pytest.raises(TTSError, match="Empty text"):
        synthesize_briefing(1, "")

def test_synthesize_over_max_chars_raises():
    with pytest.raises(TTSError, match="too long"):
        synthesize_briefing(1, "x" * 51000)
```

### Integration Test (real OpenAI, guarded)

```python
@pytest.mark.skipif(not os.getenv("OPENAI_API_KEY"), reason="No OpenAI key")
def test_real_tts_small_input():
    """Smoke test with real API — tiny input to minimize cost."""
    result = synthesize_briefing(999, "This is a test.")
    assert result.path.exists()
    assert result.duration_sec >= 1
    # Cleanup
    result.path.unlink()
```

---

## Files Changed

| File | Change |
|------|--------|
| `src/prism/tts.py` | New: full TTS module |
| `tests/test_tts.py` | New: chunking, validation, pipeline tests |
