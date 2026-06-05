# 03_05 — Frontend Audio Player

**Parent:** 03 TTS Audio Briefings
**Depends on:** 03_04 (streaming endpoint), 01_05 (briefing reader page)

---

## Objective

Add an audio player to the briefing reader page that plays synthesized MP3
briefings for Pro users. Free users see a locked state with an upgrade prompt.

---

## Affected Page

`/briefings/[id]` — the briefing reader from 01_05.

---

## Component Tree

Insert between `<ReaderContent>` and `<BriefingNav>` in the existing
briefing reader (01_05):

```
<BriefingReaderPage>
  <ReaderHeader />
  <ReaderContent />

  ──────── NEW ────────
  <AudioSection briefing={briefing} user={user}>

    <AudioPlayer visible={briefing.hasAudio && user.isPro}>
      <PlayerContainer>
        <PlayPauseButton state={playing | paused} onClick={toggle} />
        <ProgressBar>
          <Elapsed text="01:23" />
          <SeekBar
            value={currentTime}
            max={briefing.audioDurationSec}
            onChange={seek}
          />
          <Duration text="05:47" />
        </ProgressBar>
        <VolumeControl>
          <VolumeIcon muted={isMuted} />
          <VolumeSlider value={volume} onChange={setVolume} />
        </VolumeControl>
        <PlaybackSpeed>
          <SpeedButton text="1x" onClick={cycleSpeed} />
        </PlaybackSpeed>
        <DownloadButton href={audioUrl} download={filename} />
      </PlayerContainer>
    </AudioPlayer>

    <AudioLocked visible={briefing.hasAudio && !user.isPro}>
      <LockIcon />
      <Text text="Audio briefings are a Pro feature" />
      <UpgradeLink href="/settings" text="Upgrade to Pro — $7/month" />
    </AudioLocked>

    <AudioUnavailable visible={!briefing.hasAudio && isAudioFormat}>
      <InfoIcon />
      <Text text="Audio is being generated — check back shortly" />
    </AudioUnavailable>

  </AudioSection>
  ──────── END NEW ────

  <BriefingNav />
</BriefingReaderPage>
```

---

## Audio Source URL

The audio is fetched from the BFF proxy endpoint:

```
/api/bff/users/{userId}/briefings/{briefingId}/audio
```

This routes through the BFF which attaches `X-API-Key` and forwards the
binary stream from FastAPI (03_04).

```typescript
const audioUrl = `/api/bff/users/${session.user.id}/briefings/${briefingId}/audio`
```

The `<audio>` element's `src` attribute points directly to this URL.
The browser handles Range requests natively for seeking.

---

## AudioPlayer Component

File: `frontend/components/audio/AudioPlayer.tsx`

```typescript
interface AudioPlayerProps {
  briefingId: number
  durationSec: number
  sizeBytes: number
}
```

### Implementation with `useRef` + HTMLAudioElement

```typescript
function AudioPlayer({ briefingId, durationSec, sizeBytes }: AudioPlayerProps) {
  const audioRef = useRef<HTMLAudioElement>(null)
  const [isPlaying, setIsPlaying] = useState(false)
  const [currentTime, setCurrentTime] = useState(0)
  const [duration, setDuration] = useState(durationSec)
  const [volume, setVolume] = useState(1)
  const [playbackRate, setPlaybackRate] = useState(1)
  const [isLoading, setIsLoading] = useState(false)

  const audioUrl = `/api/bff/users/${userId}/briefings/${briefingId}/audio`

  // Sync time updates
  useEffect(() => {
    const audio = audioRef.current
    if (!audio) return

    const onTimeUpdate = () => setCurrentTime(audio.currentTime)
    const onLoadedMetadata = () => setDuration(audio.duration)
    const onEnded = () => setIsPlaying(false)
    const onWaiting = () => setIsLoading(true)
    const onCanPlay = () => setIsLoading(false)

    audio.addEventListener("timeupdate", onTimeUpdate)
    audio.addEventListener("loadedmetadata", onLoadedMetadata)
    audio.addEventListener("ended", onEnded)
    audio.addEventListener("waiting", onWaiting)
    audio.addEventListener("canplay", onCanPlay)

    return () => {
      audio.removeEventListener("timeupdate", onTimeUpdate)
      audio.removeEventListener("loadedmetadata", onLoadedMetadata)
      audio.removeEventListener("ended", onEnded)
      audio.removeEventListener("waiting", onWaiting)
      audio.removeEventListener("canplay", onCanPlay)
    }
  }, [])

  function toggle() {
    const audio = audioRef.current
    if (!audio) return
    if (isPlaying) { audio.pause() } else { audio.play() }
    setIsPlaying(!isPlaying)
  }

  function seek(time: number) {
    const audio = audioRef.current
    if (!audio) return
    audio.currentTime = time
    setCurrentTime(time)
  }

  function changeVolume(v: number) {
    const audio = audioRef.current
    if (!audio) return
    audio.volume = v
    setVolume(v)
  }

  function cycleSpeed() {
    const speeds = [0.75, 1, 1.25, 1.5, 2]
    const nextIdx = (speeds.indexOf(playbackRate) + 1) % speeds.length
    const next = speeds[nextIdx]
    if (audioRef.current) audioRef.current.playbackRate = next
    setPlaybackRate(next)
  }

  return (
    <>
      <audio ref={audioRef} src={audioUrl} preload="metadata" />
      {/* ... render UI controls using state above ... */}
    </>
  )
}
```

**Key decisions:**
- `preload="metadata"` — loads duration/headers without full download
- Native `<audio>` element handles Range requests for seeking automatically
- No third-party audio library — the native API covers all needs
- `playbackRate` for speed control (0.75x to 2x)

---

## Time Formatting

```typescript
function formatTime(seconds: number): string {
  const mins = Math.floor(seconds / 60)
  const secs = Math.floor(seconds % 60)
  return `${mins.toString().padStart(2, "0")}:${secs.toString().padStart(2, "0")}`
}

// Examples: 0 → "00:00", 83 → "01:23", 347 → "05:47"
```

---

## SeekBar Component

Custom styled range input for seeking.

```typescript
interface SeekBarProps {
  currentTime: number
  duration: number
  onSeek: (time: number) => void
  isLoading: boolean
}
```

**Visual:**
- Track: `h-1.5 bg-gray-200 rounded-full`
- Progress fill: `bg-brand-500` (purple), width = `currentTime / duration * 100%`
- Thumb: `w-3 h-3 bg-brand-600 rounded-full` (hidden until hover/focus)
- Buffered range: `bg-gray-300` (shows how much is downloaded)
- Loading state: pulsing animation on progress bar

**Implementation:** native `<input type="range">` with custom Tailwind styling
via `appearance-none` and pseudo-element selectors.

---

## PlaybackSpeed Component

Cycles through: 0.75x → 1x → 1.25x → 1.5x → 2x

```
<SpeedButton>
  <Text text="1.5x" />
</SpeedButton>
```

- Rounded pill: `px-2 py-1 text-xs font-mono bg-gray-100 rounded`
- Current speed displayed as text
- Click cycles to next speed
- Persist last-used speed in `localStorage` per user

---

## VolumeControl Component

```typescript
interface VolumeControlProps {
  volume: number           // 0 to 1
  onChange: (v: number) => void
}
```

**Desktop:** vertical slider on hover, speaker icon always visible
**Mobile:** hidden (users use device volume instead)

Speaker icon states:
- Full volume (>0.5): speaker with 3 waves
- Low volume (0.01-0.5): speaker with 1 wave
- Muted (0): speaker with X

Click speaker icon: toggle mute (remember previous volume).

---

## DownloadButton Component

```typescript
<a
  href={audioUrl}
  download={`prism-briefing-${briefingId}.mp3`}
  className="..."
>
  <DownloadIcon />
  <span className="sr-only">Download audio</span>
  <FileSizeLabel text={formatBytes(sizeBytes)} />
</a>
```

```typescript
function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1048576) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / 1048576).toFixed(1)} MB`
}

// Examples: 1548276 → "1.5 MB", 524288 → "512.0 KB"
```

The `download` attribute triggers a file save dialog instead of navigation.

---

## AudioLocked Component (Free Users)

```typescript
function AudioLocked() {
  return (
    <div className="flex items-center gap-3 p-4 bg-gray-50 rounded-lg border border-gray-200">
      <LockClosedIcon className="w-5 h-5 text-gray-400" />
      <div>
        <p className="text-sm font-medium text-gray-700">
          Audio briefings are a Pro feature
        </p>
        <Link href="/settings" className="text-sm text-brand-600 hover:underline">
          Upgrade to Pro — $7/month
        </Link>
      </div>
    </div>
  )
}
```

---

## AudioUnavailable Component

Shown when the briefing format is `audio_script` but `has_audio` is false
(TTS synthesis failed or is still processing).

```typescript
function AudioUnavailable() {
  return (
    <div className="flex items-center gap-3 p-4 bg-blue-50 rounded-lg border border-blue-200">
      <ClockIcon className="w-5 h-5 text-blue-400" />
      <p className="text-sm text-blue-700">
        Audio is being generated — check back shortly
      </p>
    </div>
  )
}
```

---

## Engagement Tracking

Track audio listen events to feed P_AI's engagement loop:

```typescript
// Fire "open" engagement when audio starts playing (first play only)
const hasTrackedPlay = useRef(false)

function onFirstPlay() {
  if (hasTrackedPlay.current) return
  hasTrackedPlay.current = true
  mutateEngagement({
    user_id: session.user.id,
    cluster_id: briefingClusterId,  // if available
    action: "read",
    read_time_sec: 0,  // updated on pause/end
  })
}

// Update read_time_sec when audio ends or user navigates away
useEffect(() => {
  return () => {
    if (hasTrackedPlay.current && audioRef.current) {
      mutateEngagement({
        action: "read",
        read_time_sec: Math.floor(audioRef.current.currentTime),
      })
    }
  }
}, [])
```

---

## UI States

### Loading

| State | Display |
|-------|---------|
| Audio metadata loading (`preload="metadata"`) | SeekBar disabled, duration shows "—:—" |
| Audio buffering (network) | Pulsing progress bar, play button shows spinner |

### Error

| Scenario | Display |
|----------|---------|
| Audio fetch 404 | Show `AudioUnavailable` component |
| Audio fetch 403 | Show `AudioLocked` component |
| Network error during playback | Toast: "Audio playback interrupted" + auto-retry |
| Browser doesn't support `<audio>` | Show download link as fallback |

### Edge Cases

| Scenario | Behavior |
|----------|----------|
| User navigates away during playback | Audio stops, engagement tracked |
| User opens same briefing in new tab | Independent player instance |
| Audio file deleted from server | 404 → show `AudioUnavailable` |
| Browser tab backgrounded | Audio continues playing (standard browser behavior) |

---

## Mobile Breakpoints

| Breakpoint | Layout |
|------------|--------|
| >= 768px (md) | Player as horizontal bar below briefing content. Volume slider visible. Download button with file size text. |
| < 768px (sm) | Player as sticky bottom bar (above BriefingNav). Volume control hidden. Speed and download as icon-only buttons. Full-width seek bar. Play/pause button larger (48px touch target). |

**Mobile sticky player:**
```
┌─────────────────────────────────────┐
│ ▶ 01:23 ████████░░░░░░░░░░░ 05:47  │
│         1.5x                  ⬇     │
└─────────────────────────────────────┘
```

---

## Acceptance Criteria

| # | Criterion | Verification |
|---|-----------|--------------|
| 1 | Audio player appears for briefings with `has_audio=true` | Verify player component in DOM |
| 2 | Play button starts audio playback | Click play, verify audio is audible |
| 3 | Pause button stops playback | Click pause mid-playback, verify silence |
| 4 | Seek bar allows jumping to position | Drag to 50%, verify `currentTime` updates |
| 5 | Time display shows elapsed and total | Verify "01:23 / 05:47" format |
| 6 | Playback speed cycles through 5 options | Click speed button 5 times, verify 0.75→1→1.25→1.5→2 |
| 7 | Speed persists in localStorage | Set 1.5x, reload page, verify 1.5x |
| 8 | Volume slider changes audio volume | Set to 50%, verify reduced volume |
| 9 | Download button triggers file save | Click download, verify save dialog |
| 10 | Free user sees locked state | Login as free, verify lock icon + upgrade link |
| 11 | Missing audio shows "being generated" | Mock briefing with `has_audio=false`, verify message |
| 12 | Mobile sticky player renders at 375px | Resize, verify bottom bar layout |
| 13 | Audio continues when tab is backgrounded | Play, switch tabs, switch back, verify still playing |
| 14 | Engagement tracked on first play | Play audio, check engagement API call |

---

## Testing Strategy

### Unit Tests

- `AudioPlayer` renders play button and seek bar
- `AudioPlayer` toggles play/pause state on click
- `formatTime` produces correct strings for edge cases (0, 59, 3600)
- `formatBytes` produces correct strings (0, 1023, 1MB, 15MB)
- `AudioLocked` renders upgrade link
- `AudioUnavailable` renders info message
- Speed cycling wraps from 2x back to 0.75x
- Volume mute toggle preserves previous volume

### Integration Tests (MSW)

- Mock audio endpoint returning binary data, verify player loads metadata
- Mock 403 response, verify locked state renders
- Mock 404 response, verify unavailable state renders

### E2E (Playwright)

- Login as Pro → open audio briefing → play → seek → pause → verify time
  (requires a real MP3 fixture served by MSW)

---

## Files Changed

| File | Change |
|------|--------|
| `frontend/components/audio/AudioPlayer.tsx` | New: main player component |
| `frontend/components/audio/SeekBar.tsx` | New: custom styled range input |
| `frontend/components/audio/PlaybackSpeed.tsx` | New: speed toggle button |
| `frontend/components/audio/VolumeControl.tsx` | New: volume slider + mute |
| `frontend/components/audio/AudioLocked.tsx` | New: free-tier locked state |
| `frontend/components/audio/AudioUnavailable.tsx` | New: audio pending state |
| `frontend/app/briefings/[id]/page.tsx` | Add `<AudioSection>` to reader |
| `frontend/lib/types.ts` | Update `Briefing` with `has_audio`, `audio_duration_sec`, `audio_size_bytes` |
| `frontend/__tests__/components/audio/` | New test files |
