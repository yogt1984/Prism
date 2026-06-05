# 03 — TTS Audio Briefings

**Priority:** 3 (Revenue — Pro differentiator)
**Depends on:** Web Frontend (Priority 1) for playback UI
**Unlocks:** Audio consumption, mobile-first experience

---

## Objective

Convert W_AI's existing audio briefing scripts into playable audio files using
text-to-speech synthesis. W_AI already generates spoken-prose scripts with
phonetic guidance for proper nouns — this task adds the synthesis and delivery
pipeline.

---

## Current State (Already Implemented)

W_AI generates audio scripts when `preferred_format = audio_script`:

- Spoken prose (no HTML tags, no markdown)
- Phonetic hints for proper nouns in parentheses
- Natural transition phrases between stories
- Stored in `Briefing.content_text` field

**What's missing:** Actual audio file generation and a way to listen to it.

---

## TTS Provider Selection

| Provider    | Quality  | Cost         | Latency | Notes                        |
|-------------|----------|--------------|---------|------------------------------|
| OpenAI TTS  | High     | $15/1M chars | ~2s/req | `tts-1-hd` model, 6 voices  |
| ElevenLabs  | Premium  | $5/mo 30k chars | ~3s/req | Cloneable voices, expressive |

**Recommendation:** OpenAI TTS (`tts-1-hd`) for v1.

- Simpler API (single HTTP call, no websocket streaming)
- Predictable pricing (per-character, no plan tiers)
- Good enough quality for news briefings
- Consistent voice across all briefings

---

## Architecture

```
W_AI generates audio script
        |
        v
TTS module (new: src/prism/tts.py)
  - Splits script into chunks if >4096 chars (OpenAI limit)
  - Calls OpenAI TTS API per chunk
  - Concatenates audio segments (pydub)
  - Encodes final MP3
        |
        v
Storage: data/audio/{briefing_id}.mp3
        |
        v
API: GET /users/{user_id}/briefings/{briefing_id}/audio
  - Streams MP3 file
  - Auth required, Pro-only
        |
        v
Frontend: <audio> player on briefing detail page
```

---

## Implementation Tasks

### 1. TTS Module (`src/prism/tts.py`)

```python
synthesize_briefing(briefing_id: int, text: str, voice: str = "alloy") -> Path
```

- **Input validation:** reject empty text, enforce max length (50k chars)
- **Chunking:** split on sentence boundaries at ~4000 char chunks
  - Split on `. ` or `\n\n`, never mid-sentence
  - Each chunk must be a complete thought
- **API call:** `openai.audio.speech.create(model="tts-1-hd", voice=voice, input=chunk)`
  - Retry with exponential backoff (reuse existing `retry.py`)
  - Circuit breaker integration (reuse `circuit_breaker.py`)
- **Concatenation:** use `pydub` to join MP3 segments with 200ms silence gaps
- **Output:** write to `data/audio/{briefing_id}.mp3`
- **Cleanup:** remove chunk files after concatenation
- **Metrics:** increment `tts_generated_total`, track `tts_duration_seconds`

### 2. W_AI Integration

After W_AI generates an `audio_script` format briefing:

- Call `synthesize_briefing(briefing.id, briefing.content_text)`
- Store audio file path in new field: `Briefing.audio_path`
- If TTS fails: briefing still succeeds (text is stored), audio retried later
- Send ntfy alert on TTS failure

### 3. Database Changes

Add to `Briefing` model:

```
audio_path (str | None)      — relative path to MP3 file
audio_duration_sec (int | None) — duration in seconds for UI display
audio_size_bytes (int | None)   — file size for download estimates
```

Alembic migration: `008_add_audio_fields.py`

### 4. API Endpoint

**GET /users/{user_id}/briefings/{briefing_id}/audio**

- Auth: API key required, must be Pro user
- Returns: `StreamingResponse` with `audio/mpeg` content type
- Headers: `Content-Length`, `Accept-Ranges: bytes` (for seeking)
- 404 if audio not generated yet
- 403 if user is not Pro

### 5. Frontend Audio Player

On the briefing detail page (`/briefings/[id]`):

- Show audio player only when `audio_path` is not null
- Standard `<audio>` element with controls
- Display duration and file size
- Download button for offline listening
- Pro badge — grayed out for free users with "Upgrade to Pro" tooltip

### 6. Voice Configuration

Add to `config.py`:

```
tts_voice (str, default "alloy")     — OpenAI voice: alloy, echo, fable, onyx, nova, shimmer
tts_model (str, default "tts-1-hd")  — tts-1 (fast) or tts-1-hd (quality)
```

Add to CLI:

```
prism config show  — include TTS voice and model
```

---

## Audio Quality Requirements

- **Format:** MP3, 128kbps (OpenAI default)
- **Sample rate:** 24kHz (OpenAI default for tts-1-hd)
- **Max duration:** ~15 minutes for a 10-story briefing
- **File size:** ~15MB max for a full briefing
- **Silence between stories:** 200ms gap

---

## Cost Estimate

| Briefing size | Characters | Cost (tts-1-hd) |
|---------------|------------|------------------|
| 5 stories     | ~5,000     | $0.075           |
| 10 stories    | ~10,000    | $0.15            |
| 25 stories    | ~25,000    | $0.375           |

At 100 Pro users generating daily briefings (avg 10 stories): ~$15/day, ~$450/month.

---

## Acceptance Criteria

| # | Criterion | Verification |
|---|-----------|--------------|
| 1 | Audio file is generated for audio_script briefings | Trigger briefing for audio-format Pro user, verify MP3 exists |
| 2 | Audio plays correctly in browser | Open briefing detail, click play, listen for 30s |
| 3 | Chunked scripts produce seamless audio | Generate briefing >4096 chars, verify no audible cuts |
| 4 | Free users cannot access audio endpoint | Call API as free user, verify 403 response |
| 5 | TTS failure does not block briefing delivery | Kill OpenAI mock, verify text briefing still saved |
| 6 | Audio duration matches expected length | Compare `audio_duration_sec` with actual MP3 metadata |
| 7 | Circuit breaker trips after repeated TTS failures | Simulate 5 consecutive failures, verify breaker opens |
| 8 | Audio files are cleaned up for deleted briefings | Delete briefing, verify orphan MP3 removed |
| 9 | Voice config is respected | Set `tts_voice=nova`, verify audio uses nova voice |
| 10 | Retry logic handles transient OpenAI errors | Simulate 429 rate limit, verify retry succeeds |

---

## Testing Strategy

- **Unit tests:** mock OpenAI TTS API, test chunking logic, concatenation
- **Integration:** generate real audio with test OpenAI key (small input)
- **Cost guard:** CI tests use mocked TTS to avoid API charges

---

## Dependencies (New)

```
openai>=1.0        — TTS API client
pydub>=0.25        — MP3 concatenation
```

## Environment Variables (New)

```
OPENAI_API_KEY=sk-...
TTS_VOICE=alloy
TTS_MODEL=tts-1-hd
```
