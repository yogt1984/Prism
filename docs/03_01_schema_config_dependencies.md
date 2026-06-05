# 03_01 — Database Schema, Config & Dependencies

**Parent:** 03 TTS Audio Briefings
**Must complete before:** all other 03_xx specs

---

## Objective

Add audio metadata fields to the `Briefing` model, wire TTS configuration
into `config.py`, create the audio storage directory, add a circuit breaker
instance for OpenAI, and install the new dependencies.

---

## Current Briefing Model (`src/prism/models.py:186-196`)

```python
class Briefing(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id")
    content_html: str = ""
    content_text: str = ""
    story_count: int = 0
    prompt_version: str = ""
    sent: bool = False
    sent_at: datetime | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
```

---

## Schema Changes

### New Fields on `Briefing`

Add after the existing `created_at` field:

```python
# TTS audio
audio_path: str = ""                  # relative path: "audio/42.mp3", empty if no audio
audio_duration_sec: int = 0           # playback duration in seconds, 0 if no audio
audio_size_bytes: int = 0             # file size for download estimate, 0 if no audio
```

**Field semantics:**

| Field | Set when | Value |
|-------|----------|-------|
| `audio_path` | TTS synthesis completes successfully | `"audio/{briefing_id}.mp3"` |
| `audio_duration_sec` | TTS synthesis completes | Extracted from MP3 metadata via pydub |
| `audio_size_bytes` | TTS synthesis completes | `os.path.getsize()` of the MP3 |

All default to empty/zero. A briefing with `audio_path == ""` has no audio.

---

## Alembic Migration

File: `alembic/versions/008_add_audio_fields.py`

```python
"""Add TTS audio fields to Briefing.

Revision ID: 008
Revises: 007
"""

from alembic import op
import sqlalchemy as sa

revision = "008"
down_revision = "007"


def upgrade() -> None:
    op.add_column("briefing", sa.Column(
        "audio_path", sa.String(), server_default="", nullable=False))
    op.add_column("briefing", sa.Column(
        "audio_duration_sec", sa.Integer(), server_default="0", nullable=False))
    op.add_column("briefing", sa.Column(
        "audio_size_bytes", sa.Integer(), server_default="0", nullable=False))


def downgrade() -> None:
    op.drop_column("briefing", "audio_size_bytes")
    op.drop_column("briefing", "audio_duration_sec")
    op.drop_column("briefing", "audio_path")
```

**Migration safety:**
- All columns have server defaults — existing Briefing rows unaffected
- No data transformation needed

---

## Config Changes (`src/prism/config.py`)

Add to `Settings` class after the perception tracking section:

```python
# TTS (required for audio briefings, optional otherwise)
openai_api_key: str = ""              # OpenAI API key for TTS
tts_voice: str = "alloy"             # alloy, echo, fable, onyx, nova, shimmer
tts_model: str = "tts-1-hd"          # tts-1 (fast, lower quality) or tts-1-hd (high quality)
tts_max_chars: int = 50000            # reject scripts longer than this
tts_chunk_size: int = 4000            # chars per API call (OpenAI limit: 4096)
audio_storage_dir: str = "data/audio" # directory for MP3 files
```

**Available voices (OpenAI):**

| Voice | Character |
|-------|-----------|
| `alloy` | Neutral, balanced (recommended default) |
| `echo` | Male, warm |
| `fable` | British, storytelling |
| `onyx` | Deep male, authoritative |
| `nova` | Female, friendly |
| `shimmer` | Female, expressive |

**Model comparison:**

| Model | Latency | Quality | Cost |
|-------|---------|---------|------|
| `tts-1` | ~1s/req | Good | $15/1M chars |
| `tts-1-hd` | ~2s/req | High | $30/1M chars |

---

## Circuit Breaker Instance

Add to `src/prism/circuit_breaker.py` alongside existing breakers:

```python
openai_tts_breaker = CircuitBreaker(
    "openai_tts",
    failure_threshold=5,
    recovery_timeout=300.0,  # 5 minutes
)
```

This is separate from the Claude breaker. An OpenAI outage should not
affect Claude-powered analysis, and vice versa.

---

## Audio Storage Directory

Path: `data/audio/` (relative to project root, matching `database_url`
convention of using `data/` for persistent state).

**Creation:** ensure directory exists at startup and before each write.

Add to `src/prism/db.py` `init_db()`:

```python
import os
from prism.config import settings

def init_db() -> None:
    # ... existing DB init ...
    os.makedirs(settings.audio_storage_dir, exist_ok=True)
```

**Docker volume mapping:** in `docker-compose.prod.yml`, the `data/` directory
is already mounted as a volume. Audio files persist across container restarts.

**.gitignore:** add `data/audio/` to `.gitignore` (binary MP3 files should
not be committed).

---

## API Response Schema Updates

Update `BriefingOut` and `BriefingDetailOut` in `routes.py`:

```python
class BriefingOut(BaseModel):
    id: int
    user_id: int
    story_count: int
    prompt_version: str
    sent: bool
    sent_at: datetime | None
    created_at: datetime
    # New fields
    has_audio: bool              # derived: audio_path != ""
    audio_duration_sec: int
    audio_size_bytes: int

    model_config = {"from_attributes": True}

    @model_validator(mode="before")
    @classmethod
    def derive_has_audio(cls, data):
        if hasattr(data, "audio_path"):
            data.has_audio = bool(data.audio_path)
        return data
```

**Important:** `audio_path` is NOT exposed in the API. The client uses the
streaming endpoint (`GET /users/{id}/briefings/{id}/audio`) to access audio.
Only `has_audio`, `audio_duration_sec`, and `audio_size_bytes` are public.

---

## Dependencies

Add to `pyproject.toml` under `[project.dependencies]`:

```toml
openai = ">=1.0"
pydub = ">=0.25"
```

**System dependency:** `pydub` requires `ffmpeg` for MP3 manipulation.

Add to `Dockerfile`:

```dockerfile
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*
```

---

## Environment Variables

Added to `.env` / `.env.local.example`:

```env
# TTS (leave empty to disable audio briefings)
OPENAI_API_KEY=sk-...
TTS_VOICE=alloy
TTS_MODEL=tts-1-hd
AUDIO_STORAGE_DIR=data/audio
```

---

## Metrics

Add to `src/prism/metrics.py`:

```python
tts_generated_total = Counter("tts_generated_total")
tts_failed_total = Counter("tts_failed_total")
tts_duration_seconds = Histogram("tts_duration_seconds")
tts_chars_processed_total = Counter("tts_chars_processed_total")
```

---

## Acceptance Criteria

| # | Criterion | Verification |
|---|-----------|--------------|
| 1 | Alembic migration applies cleanly | `alembic upgrade head` exits 0 |
| 2 | Existing briefings retain all data | Query briefings, verify content unchanged |
| 3 | New briefings default to empty audio fields | Create briefing, verify `audio_path=""`, durations=0 |
| 4 | Config loads TTS settings from env | Set `TTS_VOICE=nova`, verify `settings.tts_voice == "nova"` |
| 5 | Config defaults work when TTS env vars unset | Unset all, verify no crash, `tts_voice="alloy"` |
| 6 | `openai_tts_breaker` is independent from `claude_breaker` | Trip one, verify other still closed |
| 7 | `data/audio/` directory created at startup | Run `init_db()`, verify directory exists |
| 8 | BriefingOut includes `has_audio`, `audio_duration_sec`, `audio_size_bytes` | GET briefing, verify fields in JSON |
| 9 | BriefingOut does NOT expose `audio_path` | Verify field absent from response |
| 10 | `ffmpeg` available in Docker image | `docker run prism ffmpeg -version` exits 0 |
| 11 | `pydub` can import and detect ffmpeg | `python -c "from pydub import AudioSegment"` exits 0 |
| 12 | Metrics `tts_generated_total` and `tts_failed_total` exist | Verify in metrics snapshot |

---

## Testing Strategy

- **Migration test:** apply 008, verify schema, downgrade, verify clean
- **Model test:** create Briefing with audio fields, verify defaults
- **Config test:** TTS settings load from env, validate voice/model values
- **Circuit breaker test:** `openai_tts_breaker` trips independently
- **API test:** BriefingOut serialization includes derived `has_audio`
- **Regression:** all existing Briefing tests pass unchanged

---

## Files Changed

| File | Change |
|------|--------|
| `src/prism/models.py` | Add 3 fields to Briefing |
| `src/prism/config.py` | Add 6 TTS settings |
| `src/prism/circuit_breaker.py` | Add `openai_tts_breaker` |
| `src/prism/db.py` | Create audio directory in `init_db()` |
| `src/prism/metrics.py` | Add 4 TTS metrics |
| `src/prism/api/routes.py` | Update BriefingOut with audio fields |
| `alembic/versions/008_add_audio_fields.py` | New migration |
| `Dockerfile` | Install ffmpeg |
| `pyproject.toml` | Add openai, pydub |
| `.gitignore` | Add `data/audio/` |
