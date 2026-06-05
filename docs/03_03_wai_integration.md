# 03_03 — W_AI Integration

**Parent:** 03 TTS Audio Briefings
**Depends on:** 03_01 (schema), 03_02 (TTS module)

---

## Objective

Hook the TTS module into W_AI's existing briefing pipeline so that audio
scripts are automatically synthesized into MP3 files after generation. TTS
failure must never block text briefing delivery.

---

## Current W_AI Flow (`src/prism/agents/w_ai.py:227-293`)

```
create_and_send(user, clusters, engine)
  1. Check: clusters empty? → return None
  2. Tier enforcement: free users → force EMAIL format
  3. Generate content via Claude
  4. Format-specific routing:
     - EMAIL → content_html = Claude output
     - JSON_FEED → content_text = JSON feed
     - AUDIO_SCRIPT → content_text = spoken-prose script
  5. Store Briefing row in DB
  6. Deliver (email only, others are API-only)
  7. Return Briefing
```

**Insert point:** between step 5 (store) and step 6 (deliver), add TTS
synthesis for `AUDIO_SCRIPT` format briefings.

---

## Modified Flow

```
create_and_send(user, clusters, engine)
  1. Check: clusters empty? → return None
  2. Tier enforcement: free users → force EMAIL format
  3. Generate content via Claude
  4. Format-specific routing (unchanged)
  5. Store Briefing row in DB
  ──────── NEW ────────
  6. If format == AUDIO_SCRIPT and openai_api_key configured:
     a. Call synthesize_briefing(briefing.id, content_text)
     b. On success: update briefing with audio_path, duration, size
     c. On failure: log error, send ntfy alert, continue without audio
  ──────── END NEW ────
  7. Deliver (unchanged)
  8. Return Briefing
```

---

## Implementation

### Changes to `src/prism/agents/w_ai.py`

Add the TTS call inside `create_and_send`, after the briefing is committed:

```python
@timed_cycle("briefing")
def create_and_send(
    self, user: User, clusters: list[StoryCluster],
    engine: Engine | None = None,
) -> Briefing | None:
    # ... existing steps 1-5 unchanged ...

    with Session(e) as session:
        briefing = Briefing(
            user_id=user.id,
            content_html=content_html,
            content_text=content_text,
            story_count=len(clusters),
            prompt_version=BRIEFING_PROMPT_VERSION,
        )
        session.add(briefing)
        session.commit()
        session.refresh(briefing)

        # ── NEW: TTS synthesis for audio briefings ──
        if fmt == BriefingFormat.AUDIO_SCRIPT:
            self._try_synthesize_audio(briefing, session)

        # ... existing delivery logic unchanged ...
```

### TTS Wrapper Method

```python
def _try_synthesize_audio(self, briefing: Briefing, session: Session) -> None:
    """Attempt TTS synthesis. Never raises — failures are logged and alerted."""
    from prism.config import get_settings
    s = get_settings()

    if not s.openai_api_key:
        logger.info(
            "Skipping TTS for briefing %d — OpenAI API key not configured",
            briefing.id,
        )
        return

    try:
        from prism.tts import synthesize_briefing, TTSError
        from prism.metrics import tts_generated_total, tts_failed_total

        result = synthesize_briefing(
            briefing_id=briefing.id,
            text=briefing.content_text,
        )

        # Update briefing with audio metadata
        briefing.audio_path = f"audio/{briefing.id}.mp3"
        briefing.audio_duration_sec = result.duration_sec
        briefing.audio_size_bytes = result.size_bytes
        session.add(briefing)
        session.commit()

        tts_generated_total.inc()

        logger.info(
            "TTS complete for briefing %d: %ds, %d bytes",
            briefing.id, result.duration_sec, result.size_bytes,
        )

    except TTSError as exc:
        tts_failed_total.inc()
        logger.error("TTS validation failed for briefing %d: %s",
                     briefing.id, exc)
        send_alert(
            f"TTS failed for briefing {briefing.id}: {exc}",
            level=AlertLevel.WARNING,
        )

    except CircuitOpenError as exc:
        tts_failed_total.inc()
        logger.warning("TTS circuit open for briefing %d: %s",
                       briefing.id, exc)
        send_alert(
            f"TTS circuit breaker open — audio skipped for briefing {briefing.id}",
            level=AlertLevel.WARNING,
        )

    except Exception as exc:
        tts_failed_total.inc()
        logger.exception("Unexpected TTS error for briefing %d", briefing.id)
        send_alert(
            f"TTS unexpected error for briefing {briefing.id}: {exc}",
            level=AlertLevel.ERROR,
        )
```

**Key design decisions:**

1. **Never raises:** all exceptions are caught. The briefing text is already
   saved — audio is a best-effort enhancement.
2. **Separate try/except blocks** for `TTSError` (validation) vs
   `CircuitOpenError` (service down) vs generic `Exception` — each gets
   different log level and alert severity.
3. **Metrics tracked** regardless of error type: `tts_generated_total` on
   success, `tts_failed_total` on any failure.
4. **Import inside method:** `tts.py` imports `openai` which is an optional
   dependency. Keeping the import inside the method prevents ImportError
   when OpenAI is not installed (e.g., in test environments without TTS).

---

## Audio Retry on Failure

When TTS fails, the text briefing is delivered without audio. Users see
`has_audio: false` in the API response.

### Manual Retry via CLI

Add to the existing CLI:

```
prism briefing synthesize <briefing_id>   — retry TTS for a specific briefing
prism briefing synthesize-pending         — retry all audio briefings without audio
```

File: add to existing `src/prism/cli/` commands

```python
@briefing_app.command()
def synthesize(briefing_id: int):
    """Retry TTS synthesis for a specific briefing."""
    from prism.db import get_engine
    from prism.models import Briefing
    from prism.tts import synthesize_briefing
    from sqlmodel import Session

    with Session(get_engine()) as session:
        briefing = session.get(Briefing, briefing_id)
        if not briefing:
            console.print(f"Briefing {briefing_id} not found.", style="red")
            raise typer.Exit(1)
        if not briefing.content_text:
            console.print("Briefing has no text content (not an audio briefing).", style="red")
            raise typer.Exit(1)
        if briefing.audio_path:
            console.print(f"Audio already exists: {briefing.audio_path}")
            raise typer.Exit(0)

        result = synthesize_briefing(briefing.id, briefing.content_text)
        briefing.audio_path = f"audio/{briefing.id}.mp3"
        briefing.audio_duration_sec = result.duration_sec
        briefing.audio_size_bytes = result.size_bytes
        session.add(briefing)
        session.commit()

        console.print(f"Audio generated: {result.duration_sec}s, {result.size_bytes} bytes")


@briefing_app.command()
def synthesize_pending():
    """Retry TTS for all audio-format briefings missing audio."""
    from prism.db import get_engine
    from prism.models import Briefing, BriefingFormat, User
    from prism.tts import synthesize_briefing
    from sqlmodel import Session, select

    with Session(get_engine()) as session:
        # Find audio-format briefings without audio
        stmt = (
            select(Briefing)
            .join(User)
            .where(
                Briefing.audio_path == "",
                Briefing.content_text != "",
                User.preferred_format == BriefingFormat.AUDIO_SCRIPT.value,
            )
        )
        pending = session.exec(stmt).all()

    console.print(f"Found {len(pending)} briefings pending TTS.")

    for briefing in pending:
        try:
            result = synthesize_briefing(briefing.id, briefing.content_text)
            with Session(get_engine()) as session:
                b = session.get(Briefing, briefing.id)
                b.audio_path = f"audio/{briefing.id}.mp3"
                b.audio_duration_sec = result.duration_sec
                b.audio_size_bytes = result.size_bytes
                session.add(b)
                session.commit()
            console.print(f"  Briefing {briefing.id}: OK ({result.duration_sec}s)")
        except Exception as exc:
            console.print(f"  Briefing {briefing.id}: FAILED ({exc})", style="red")
```

---

## Audio Cleanup on Briefing Deletion

If a briefing is deleted (future feature), the orphan MP3 should be removed.

Add a utility function:

```python
def cleanup_orphan_audio(briefing: Briefing) -> None:
    """Remove the MP3 file associated with a briefing."""
    if not briefing.audio_path:
        return
    audio_file = Path(settings.audio_storage_dir) / f"{briefing.id}.mp3"
    if audio_file.exists():
        audio_file.unlink()
        logger.info("Removed orphan audio: %s", audio_file)
```

This is called before deleting the briefing row from the database.

---

## Impact on Briefing Cycle Timing

TTS adds latency to the briefing cycle for audio-format users:

| Briefing size | Chunks | TTS time (est.) | Total added |
|---------------|--------|-----------------|-------------|
| 5 stories | 1-2 | 2-4s | ~5s |
| 10 stories | 2-3 | 4-6s | ~8s |
| 25 stories | 5-7 | 10-14s | ~18s |

The briefing cycle already takes 5-15s for Claude generation. TTS adds
comparable time. For the daily scheduled cycle, this is acceptable.

For on-demand briefings (`POST /users/{id}/briefings`), the user waits
for both Claude + TTS. Total: 15-30s. The frontend already handles this
with a loading spinner (01_05).

---

## Acceptance Criteria

| # | Criterion | Verification |
|---|-----------|--------------|
| 1 | Audio-format briefing triggers TTS after text storage | Set user to audio_script, trigger briefing, verify MP3 exists |
| 2 | Email-format briefing does NOT trigger TTS | Set user to email, trigger, verify no audio_path |
| 3 | JSON-format briefing does NOT trigger TTS | Set user to json_feed, trigger, verify no audio_path |
| 4 | TTS failure does not prevent briefing creation | Mock TTS error, trigger, verify Briefing row exists with content_text |
| 5 | TTS failure sends ntfy alert | Mock TTS error, verify `send_alert` called |
| 6 | Briefing `audio_path` set after successful TTS | Verify `audio/{id}.mp3` in DB |
| 7 | Briefing `audio_duration_sec` matches actual MP3 | Compare DB value with ffprobe |
| 8 | Circuit breaker open skips TTS gracefully | Trip breaker, trigger briefing, verify text-only |
| 9 | Missing OpenAI key skips TTS silently | Clear key, trigger, verify no error, no audio |
| 10 | `prism briefing synthesize 42` retries TTS | Create audio briefing without audio, run command, verify MP3 |
| 11 | `prism briefing synthesize-pending` processes all | Create 3 pending, run command, verify all 3 have audio |
| 12 | Metrics increment on success and failure | Check `tts_generated_total`, `tts_failed_total` |

---

## Testing Strategy

### Unit Tests

```python
def test_create_and_send_audio_triggers_tts(mock_tts, mock_claude, pro_user):
    """Audio-format briefing calls synthesize_briefing."""
    pro_user.preferred_format = BriefingFormat.AUDIO_SCRIPT
    w_ai = WriterAgent()
    briefing = w_ai.create_and_send(pro_user, clusters, engine)
    mock_tts.assert_called_once_with(
        briefing_id=briefing.id, text=briefing.content_text
    )

def test_create_and_send_email_skips_tts(mock_tts, mock_claude, pro_user):
    """Email-format briefing does not call TTS."""
    pro_user.preferred_format = BriefingFormat.EMAIL
    w_ai = WriterAgent()
    w_ai.create_and_send(pro_user, clusters, engine)
    mock_tts.assert_not_called()

def test_tts_failure_does_not_block_briefing(mock_tts, mock_claude, pro_user):
    """TTS error does not prevent briefing creation."""
    mock_tts.side_effect = Exception("OpenAI down")
    pro_user.preferred_format = BriefingFormat.AUDIO_SCRIPT
    w_ai = WriterAgent()
    briefing = w_ai.create_and_send(pro_user, clusters, engine)
    assert briefing is not None
    assert briefing.content_text != ""
    assert briefing.audio_path == ""

def test_tts_failure_sends_alert(mock_tts, mock_alerts, mock_claude, pro_user):
    """TTS error triggers ntfy alert."""
    mock_tts.side_effect = Exception("fail")
    pro_user.preferred_format = BriefingFormat.AUDIO_SCRIPT
    w_ai = WriterAgent()
    w_ai.create_and_send(pro_user, clusters, engine)
    mock_alerts.assert_called_once()
```

### Regression

All existing W_AI tests must pass unchanged — TTS is additive and
only triggers for `AUDIO_SCRIPT` format.

---

## Files Changed

| File | Change |
|------|--------|
| `src/prism/agents/w_ai.py` | Add `_try_synthesize_audio()`, call in `create_and_send` |
| `src/prism/cli/` (briefing commands) | Add `synthesize` and `synthesize-pending` |
| `tests/test_w_ai_tts.py` | New test file for TTS integration |
