# 03_04 — Audio Streaming API Endpoint

**Parent:** 03 TTS Audio Briefings
**Depends on:** 03_01 (schema + audio_path field), 03_02 (MP3 files on disk)

---

## Objective

Implement the API endpoint that serves MP3 audio files to authenticated Pro
users. Supports full file download and HTTP Range requests for seeking in
browser audio players.

---

## Endpoint Specification

### GET /users/{user_id}/briefings/{briefing_id}/audio

**Authentication:** `X-API-Key` header (existing `require_api_key` dependency)
**Authorization:** own account only, must be Pro

**Success Response (200):**

```
HTTP/1.1 200 OK
Content-Type: audio/mpeg
Content-Length: 1548276
Accept-Ranges: bytes
Content-Disposition: inline; filename="briefing-42.mp3"
Cache-Control: private, max-age=86400

<MP3 binary data>
```

**Range Response (206):**

```
HTTP/1.1 206 Partial Content
Content-Type: audio/mpeg
Content-Range: bytes 0-65535/1548276
Content-Length: 65536

<partial MP3 binary data>
```

**Error responses:**

| Status | Condition | Body |
|--------|-----------|------|
| 401 | Missing or invalid API key | `{"detail": "Missing API key"}` |
| 403 | User is not Pro | `{"detail": "API access requires a Pro subscription"}` |
| 403 | Accessing another user's briefing | `{"detail": "Access denied: you can only access your own resources"}` |
| 404 | Briefing not found | `{"detail": "Briefing not found"}` |
| 404 | Audio not yet generated | `{"detail": "Audio not available for this briefing"}` |
| 416 | Invalid range request | `{"detail": "Requested range not satisfiable"}` |

---

## Implementation

Add to `src/prism/api/routes.py`:

```python
from pathlib import Path

from fastapi import Request
from fastapi.responses import Response, StreamingResponse


@router.get("/users/{user_id}/briefings/{briefing_id}/audio")
def stream_audio(
    user_id: int,
    briefing_id: int,
    request: Request,
    auth_user: User = Depends(require_api_key),
    session: Session = Depends(_get_session),
) -> Response:
    """Stream the audio MP3 for a briefing."""
    # 1. Authorization
    if auth_user.id != user_id:
        raise HTTPException(status_code=403,
            detail="Access denied: you can only access your own resources")

    # 2. Load briefing
    briefing = session.get(Briefing, briefing_id)
    if briefing is None or briefing.user_id != user_id:
        raise HTTPException(status_code=404, detail="Briefing not found")

    # 3. Check audio exists
    if not briefing.audio_path:
        raise HTTPException(status_code=404,
            detail="Audio not available for this briefing")

    from prism.config import get_settings
    audio_file = Path(get_settings().audio_storage_dir) / f"{briefing.id}.mp3"

    if not audio_file.exists():
        raise HTTPException(status_code=404,
            detail="Audio file missing from storage")

    file_size = audio_file.stat().st_size

    # 4. Handle Range requests (for seeking)
    range_header = request.headers.get("range")

    if range_header:
        return _serve_range(audio_file, file_size, range_header, briefing.id)
    else:
        return _serve_full(audio_file, file_size, briefing.id)
```

### Full File Response

```python
def _serve_full(
    audio_file: Path,
    file_size: int,
    briefing_id: int,
) -> StreamingResponse:
    """Serve the complete MP3 file."""

    def file_iterator():
        with open(audio_file, "rb") as f:
            while chunk := f.read(65536):  # 64KB chunks
                yield chunk

    return StreamingResponse(
        content=file_iterator(),
        media_type="audio/mpeg",
        headers={
            "Content-Length": str(file_size),
            "Accept-Ranges": "bytes",
            "Content-Disposition": f'inline; filename="briefing-{briefing_id}.mp3"',
            "Cache-Control": "private, max-age=86400",
        },
    )
```

### Range Request Response

Range requests are essential for seeking in `<audio>` players. Without
them, the browser must download the entire file before seeking.

```python
import re

def _serve_range(
    audio_file: Path,
    file_size: int,
    range_header: str,
    briefing_id: int,
) -> Response:
    """Serve a byte range of the MP3 file (HTTP 206)."""
    # Parse "bytes=START-END" or "bytes=START-"
    match = re.match(r"bytes=(\d+)-(\d*)", range_header)
    if not match:
        raise HTTPException(status_code=416,
            detail="Requested range not satisfiable")

    start = int(match.group(1))
    end = int(match.group(2)) if match.group(2) else file_size - 1

    # Validate range
    if start >= file_size or end >= file_size or start > end:
        raise HTTPException(
            status_code=416,
            detail="Requested range not satisfiable",
            headers={"Content-Range": f"bytes */{file_size}"},
        )

    content_length = end - start + 1

    def range_iterator():
        with open(audio_file, "rb") as f:
            f.seek(start)
            remaining = content_length
            while remaining > 0:
                chunk_size = min(65536, remaining)
                data = f.read(chunk_size)
                if not data:
                    break
                remaining -= len(data)
                yield data

    return StreamingResponse(
        content=range_iterator(),
        status_code=206,
        media_type="audio/mpeg",
        headers={
            "Content-Range": f"bytes {start}-{end}/{file_size}",
            "Content-Length": str(content_length),
            "Accept-Ranges": "bytes",
            "Content-Disposition": f'inline; filename="briefing-{briefing_id}.mp3"',
            "Cache-Control": "private, max-age=86400",
        },
    )
```

---

## Streaming vs Loading Entire File

The endpoint uses `StreamingResponse` with 64KB chunks rather than loading
the entire MP3 into memory. For a typical 10-story briefing (~2MB MP3),
this avoids a 2MB allocation per request.

**Memory per concurrent request:** ~64KB (one chunk buffer)
**Max file size served:** no limit (streaming), but briefings are capped at
~15MB by the 50k char TTS input limit.

---

## Caching Strategy

```
Cache-Control: private, max-age=86400
```

- `private`: only browser cache, not CDN/proxy (audio is user-specific)
- `max-age=86400`: 24 hours (briefing audio never changes after generation)

The browser caches the audio after first play. Subsequent plays are instant.

---

## BFF Proxy Considerations

The frontend BFF proxy (`01_01`) must handle binary streaming for this endpoint:

```typescript
// In frontend/app/api/bff/[...path]/route.ts
async function proxyToFastAPI(request: NextRequest) {
  // ... existing auth logic ...

  const res = await fetch(`${FASTAPI_URL}/${path}`, { /* ... */ })

  // For audio, stream the binary response directly
  if (res.headers.get("content-type")?.includes("audio/")) {
    return new NextResponse(res.body, {
      status: res.status,
      headers: {
        "Content-Type": res.headers.get("content-type") || "audio/mpeg",
        "Content-Length": res.headers.get("content-length") || "",
        "Content-Range": res.headers.get("content-range") || "",
        "Accept-Ranges": "bytes",
        "Cache-Control": "private, max-age=86400",
      },
    })
  }

  // ... existing JSON handling ...
}
```

**Important:** forward the `Range` header from the browser to FastAPI:

```typescript
const headers: HeadersInit = {
  "X-API-Key": apiKey,
}
const rangeHeader = request.headers.get("range")
if (rangeHeader) {
  headers["Range"] = rangeHeader
}
```

---

## Acceptance Criteria

| # | Criterion | Verification |
|---|-----------|--------------|
| 1 | Full download returns complete MP3 | Download, verify file size matches `audio_size_bytes` |
| 2 | Content-Type is `audio/mpeg` | Inspect response header |
| 3 | Accept-Ranges header is present | Inspect response header |
| 4 | Range request returns 206 with correct Content-Range | `curl -H "Range: bytes=0-1023"`, verify headers |
| 5 | Range request returns correct byte slice | Compare downloaded range with file slice |
| 6 | Invalid range returns 416 | `curl -H "Range: bytes=99999999-"`, verify 416 |
| 7 | Browser `<audio>` player can seek | Play audio in Chrome, drag seek bar, verify no reload |
| 8 | Non-Pro user gets 403 | Call as free user, verify 403 |
| 9 | Wrong user gets 403 | Call with different user's key, verify 403 |
| 10 | Briefing without audio returns 404 | Call for email-format briefing, verify 404 |
| 11 | Missing file on disk returns 404 | Delete MP3, call endpoint, verify 404 |
| 12 | Streaming does not load full file in memory | Profile memory during 10MB file serving |
| 13 | Cache-Control header is set | Verify `private, max-age=86400` |
| 14 | BFF proxy streams audio without buffering | Play via frontend, verify no initial delay |

---

## Testing Strategy

### Unit Tests

```python
def test_audio_full_download(client, pro_user, audio_briefing):
    """Pro user downloads complete MP3."""
    res = client.get(
        f"/users/{pro_user.id}/briefings/{audio_briefing.id}/audio",
        headers={"X-API-Key": pro_user_key},
    )
    assert res.status_code == 200
    assert res.headers["content-type"] == "audio/mpeg"
    assert int(res.headers["content-length"]) == audio_briefing.audio_size_bytes

def test_audio_range_request(client, pro_user, audio_briefing):
    """Range request returns 206 with correct slice."""
    res = client.get(
        f"/users/{pro_user.id}/briefings/{audio_briefing.id}/audio",
        headers={
            "X-API-Key": pro_user_key,
            "Range": "bytes=0-1023",
        },
    )
    assert res.status_code == 206
    assert "bytes 0-1023/" in res.headers["content-range"]
    assert len(res.content) == 1024

def test_audio_range_invalid(client, pro_user, audio_briefing):
    """Invalid range returns 416."""
    res = client.get(
        f"/users/{pro_user.id}/briefings/{audio_briefing.id}/audio",
        headers={
            "X-API-Key": pro_user_key,
            "Range": "bytes=99999999-",
        },
    )
    assert res.status_code == 416

def test_audio_no_audio_returns_404(client, pro_user, text_briefing):
    """Briefing without audio returns 404."""
    res = client.get(
        f"/users/{pro_user.id}/briefings/{text_briefing.id}/audio",
        headers={"X-API-Key": pro_user_key},
    )
    assert res.status_code == 404

def test_audio_free_user_403(client, free_user, audio_briefing):
    """Free user cannot access audio."""
    res = client.get(
        f"/users/{free_user.id}/briefings/{audio_briefing.id}/audio",
        headers={"X-API-Key": free_user_key},
    )
    assert res.status_code == 403

def test_audio_wrong_user_403(client, pro_user, other_pro_user, audio_briefing):
    """Cannot access another user's audio."""
    res = client.get(
        f"/users/{pro_user.id}/briefings/{audio_briefing.id}/audio",
        headers={"X-API-Key": other_pro_key},
    )
    assert res.status_code == 403
```

### Test Fixtures

```python
@pytest.fixture
def audio_briefing(session, pro_user, tmp_path):
    """Create a briefing with a real MP3 file on disk."""
    mp3_data = generate_silence_mp3(duration_ms=1000)  # 1s silence
    audio_dir = tmp_path / "audio"
    audio_dir.mkdir()
    mp3_path = audio_dir / "42.mp3"
    mp3_path.write_bytes(mp3_data)

    briefing = Briefing(
        id=42, user_id=pro_user.id,
        content_text="test", story_count=1,
        audio_path="audio/42.mp3",
        audio_duration_sec=1,
        audio_size_bytes=len(mp3_data),
    )
    session.add(briefing)
    session.commit()
    return briefing
```

---

## Files Changed

| File | Change |
|------|--------|
| `src/prism/api/routes.py` | Add `GET /users/{id}/briefings/{id}/audio` + range helpers |
| `tests/test_api_audio.py` | New test file |
| `frontend/app/api/bff/[...path]/route.ts` | Handle binary streaming for audio |
