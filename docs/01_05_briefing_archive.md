# 01_05 — Briefing Archive & Reader

**Parent:** 01 Web Frontend
**Depends on:** 01_01 (auth, BFF proxy)

---

## Objective

Build the briefing list and detail reader. Users view their history of
generated briefings, read full content (rendered HTML), and can trigger
on-demand generation. This is the primary content consumption surface.

---

## Routes

- `/briefings` — paginated list of past briefings
- `/briefings/[id]` — full briefing reader

---

## Component Tree — List Page (`/briefings`)

```
<BriefingsListPage>
  <PageHeader>
    <Heading text="Your Briefings" />
    <TriggerBriefingButton />                    // "Generate new briefing"
  </PageHeader>

  <BriefingList>
    <BriefingListItem briefing>                  // repeated
      <DateColumn>
        <DayOfWeek text="Thu" />
        <DateFull text="Jun 5, 2026" />
        <Time text="7:00 AM" />
      </DateColumn>
      <ContentPreview>
        <StoryCountBadge count={briefing.story_count} />
        <SentBadge sent={briefing.sent} />
        <PromptVersionTag version={briefing.prompt_version} />
      </ContentPreview>
      <ViewButton href={`/briefings/${briefing.id}`} />
    </BriefingListItem>
  </BriefingList>

  <Pagination>
    <PreviousButton disabled={offset === 0} />
    <PageInfo text="Showing 1-20 of {total}" />
    <NextButton disabled={items.length < limit} />
  </Pagination>
</BriefingsListPage>
```

## Component Tree — Reader Page (`/briefings/[id]`)

```
<BriefingReaderPage briefingId>
  <ReaderHeader>
    <BackLink href="/briefings" text="All Briefings" />
    <DateDisplay date={briefing.created_at} />
    <StoryCountBadge count={briefing.story_count} />
    <FormatBadge format="email" | "audio_script" | "json_feed" />
  </ReaderHeader>

  <ReaderContent>
    <HTMLRenderer html={briefing.content_html} />   // sanitized render
  </ReaderContent>

  <TextFallback visible={!briefing.content_html}>
    <PlainTextRenderer text={briefing.content_text} />
  </TextFallback>

  <AudioPlayerSlot visible={false}>
    // Placeholder — wired in Priority 3 (TTS)
    <ProBadge text="Audio briefings available with Pro" />
  </AudioPlayerSlot>

  <BriefingNav>
    <PreviousBriefingLink />
    <NextBriefingLink />
  </BriefingNav>
</BriefingReaderPage>
```

---

## API Calls

### List Briefings

```
GET /api/bff/users/{userId}/briefings?limit=20&offset={offset}

Response: BriefingOut[]
[{
  id: 42,
  user_id: 5,
  story_count: 10,
  prompt_version: "v2",
  sent: true,
  sent_at: "2026-06-05T07:00:12Z",
  created_at: "2026-06-05T06:58:00Z"
}]
```

React Query key: `["briefings", userId, "list", offset]`
Stale time: 5 minutes

**Pagination logic:**
- `limit = 20` (fixed)
- `offset` managed in URL query param: `/briefings?page=2` → offset=20
- "Next" disabled when response length < 20 (no more pages)
- "Previous" disabled when offset === 0

### Get Briefing Detail

```
GET /api/bff/users/{userId}/briefings/{briefingId}

Response: BriefingDetailOut
{
  id: 42,
  user_id: 5,
  story_count: 10,
  prompt_version: "v2",
  sent: true,
  sent_at: "2026-06-05T07:00:12Z",
  created_at: "2026-06-05T06:58:00Z",
  content_html: "<h2>Your Daily Briefing</h2><p>...",
  content_text: "Your Daily Briefing\n\n..."
}
```

React Query key: `["briefings", userId, briefingId]`
Stale time: 30 minutes (briefing content never changes)

### Trigger On-Demand Briefing

```
POST /api/bff/users/{userId}/briefings

Response: BriefingDetailOut (201)

Error 422: { detail: "No stories available for briefing generation" }
```

Mutation on success:
- Invalidate `["briefings", userId, "list", 0]` (first page)
- Navigate to `/briefings/{newId}`
- Toast: "Briefing generated with {story_count} stories"

---

## HTMLRenderer Component

W_AI generates HTML briefings with `<h2>`, `<p>`, `<a>`, `<em>`, `<strong>` tags.
This must be rendered safely.

**Sanitization:** use `DOMPurify` to strip scripts, event handlers, iframes.

```typescript
import DOMPurify from "dompurify"

const ALLOWED_TAGS = ["h1", "h2", "h3", "p", "a", "em", "strong", "ul", "ol", "li", "br", "span"]
const ALLOWED_ATTRS = ["href", "target", "rel"]

function HTMLRenderer({ html }: { html: string }) {
  const clean = DOMPurify.sanitize(html, {
    ALLOWED_TAGS,
    ALLOWED_ATTR: ALLOWED_ATTRS,
  })
  return (
    <article
      className="prose prose-neutral max-w-none"
      dangerouslySetInnerHTML={{ __html: clean }}
    />
  )
}
```

**Styling via Tailwind `@tailwindcss/typography` plugin:**
- `prose` class handles headings, paragraphs, links, lists
- Links get `target="_blank" rel="noopener noreferrer"` via DOMPurify hook
- Source attribution links (parenthetical) styled as subtle gray text

**Link handling:**
All `<a>` tags in briefing HTML point to original source URLs. Force them
to open in new tab via DOMPurify `afterSanitizeAttributes` hook:

```typescript
DOMPurify.addHook("afterSanitizeAttributes", (node) => {
  if (node.tagName === "A") {
    node.setAttribute("target", "_blank")
    node.setAttribute("rel", "noopener noreferrer")
  }
})
```

---

## BriefingNav (Previous/Next Navigation)

Allows navigating between briefings without returning to the list.

**Data source:** Use the list query to know adjacent briefing IDs.

```typescript
// From the list cache, find current briefing's position
const list = queryClient.getQueryData(["briefings", userId, "list", 0])
const currentIdx = list?.findIndex(b => b.id === briefingId)
const prevId = currentIdx > 0 ? list[currentIdx - 1].id : null
const nextId = currentIdx < list.length - 1 ? list[currentIdx + 1].id : null
```

If list not cached (direct URL visit), hide nav arrows.

---

## TriggerBriefingButton Behavior

This button calls `POST /users/{id}/briefings` which runs P_AI + W_AI
synchronously. This can take 10-30 seconds.

**UX flow:**
1. Click button → disable, show spinner + "Generating your briefing..."
2. BFF proxy makes request (long timeout: 60s)
3. On success → navigate to new briefing reader page
4. On 422 → re-enable button, toast "No stories available"
5. On timeout/error → re-enable button, toast "Generation failed — try again"

**Rate guard:** disable button for 60 seconds after successful generation
to prevent spamming. Store last-generated timestamp in `localStorage`.

---

## UI States

### Loading

| Component | Display |
|-----------|---------|
| BriefingList | 5 skeleton rows (pulsing date + badges) |
| BriefingReader content | Full-width pulsing block (h-96) |
| Trigger button active | Spinner + "Generating..." text |

### Empty

| Condition | Display |
|-----------|---------|
| No briefings exist | Centered: "No briefings yet" + "Your first one arrives at 7am UTC" + trigger button |
| Briefing has no HTML content | Fall back to `content_text` in `<pre>` with `whitespace-pre-wrap` |
| Briefing has neither HTML nor text | "This briefing has no content" (should not happen) |

### Error

| Scenario | Display |
|----------|---------|
| List fetch fails | "Could not load briefings" + retry button |
| Detail fetch 404 | "Briefing not found" + back to list link |
| Trigger 422 | Toast: "No stories available for briefing" |
| Trigger timeout | Toast: "Briefing generation timed out — try again" |

---

## Mobile Breakpoints

| Breakpoint | Layout |
|------------|--------|
| >= 768px (md) | List: date column (120px) + content + view button in row. Reader: `max-w-prose` centered with comfortable margins. |
| < 768px (sm) | List: stacked (date on top, badges below, full-width tap target). Reader: full-width with `px-4` padding. BriefingNav as bottom bar. |

---

## Acceptance Criteria

| # | Criterion | Verification |
|---|-----------|--------------|
| 1 | Briefing list shows newest first | Compare order with API response sorted by `created_at` desc |
| 2 | Pagination shows correct page and navigates | Click next, verify offset=20 in URL and new items |
| 3 | Briefing reader renders HTML content correctly | Compare rendered headings/links with `content_html` |
| 4 | Source links open in new tab | Click attribution link, verify `target="_blank"` |
| 5 | DOMPurify strips dangerous HTML | Inject `<script>alert(1)</script>` in test, verify stripped |
| 6 | Plain text fallback works when HTML is empty | Mock briefing with empty `content_html`, verify text renders |
| 7 | Trigger button generates new briefing | Click, wait for response, verify new briefing in list |
| 8 | Trigger button disabled during generation | Click, verify button is disabled with spinner |
| 9 | Trigger rate guard prevents spam | Generate, verify button disabled for 60s |
| 10 | Previous/next navigation works in reader | Open briefing, click next, verify different content |
| 11 | Mobile list items are tappable full-width | Test at 375px, verify each item is a single tap target |

---

## Testing Strategy

- **Unit:** `HTMLRenderer` sanitizes dangerous tags, preserves safe tags
- **Unit:** `HTMLRenderer` adds target="_blank" to all links
- **Unit:** pagination offset calculation from page number
- **Unit:** rate guard timer logic
- **Integration (MSW):** list page with mocked briefings, pagination
- **Integration (MSW):** reader page with mocked HTML content
- **E2E:** trigger briefing → verify appears in list → open reader → navigate
