# 01_03 — Story Detail & Perspective Viewer

**Parent:** 01 Web Frontend
**Depends on:** 01_01 (auth), 01_08 (design system for bias colors)

---

## Objective

Build the most important page in Prism — the story detail view that shows
multiple perspectives side-by-side with visible bias labels, sentiment
indicators, and source attribution. This is the core product differentiator:
"bias made visible."

---

## Route

`/stories/[id]` — protected. Dynamic route, server-side fetched for SEO.

---

## Component Tree

```
<StoryDetailPage storyId>
  <StoryHeader>
    <Breadcrumb items={["Dashboard", "Stories", headline]} />
    <Headline text={story.headline} />
    <StoryMeta>
      <CategoryPills categories={story.categories.split(",")} />
      <TimeAgo date={story.first_seen} />
      <ArticleCountBadge count={story.article_count} />
      <QualityIndicator score={story.quality_score} />
    </StoryMeta>
  </StoryHeader>

  <NeutralSummary>
    <SectionLabel text="Neutral Summary" />
    <SummaryText text={story.summary} />
  </NeutralSummary>

  <ResonancePanel>
    <ResonanceScore value={resonance.resonance} />
    <MomentumIndicator value={resonance.momentum} />
    <PeakResonance value={resonance.peak_resonance} />
    <SourceCountStat value={resonance.source_count} />
    <BreadthStat value={resonance.breadth} />
    <ComputedAt date={resonance.computed_at} />
  </ResonancePanel>

  <PerspectiveViewer>
    <ViewToggle mode={side-by-side | stacked | tabbed} />
    <PerspectiveGrid>
      <PerspectiveCard perspective>              // repeated per perspective
        <SourceHeader>
          <SourceName sourceId={perspective.source_id} />
          <BiasLabel label={perspective.bias_label} />
          <SentimentBar value={perspective.sentiment} />
        </SourceHeader>
        <PerspectiveSummary text={perspective.summary} />
        <KeyClaimsList>
          <ClaimItem claim>                      // repeated
            <ClaimText text={claim} />
          </ClaimItem>
        </KeyClaimsList>
      </PerspectiveCard>
    </PerspectiveGrid>
  </PerspectiveViewer>

  <ArticleSourcesList>
    <SectionLabel text="Original Sources" />
    <ArticleTable>
      <ArticleRow article>                       // repeated per article
        <SourceBadge sourceId={article.source_id} />
        <ArticleTitle text={article.title} />
        <ExternalLink href={article.url} />
        <PublishedAt date={article.published_at} />
      </ArticleRow>
    </ArticleTable>
  </ArticleSourcesList>

  <EngagementBar>
    <SaveButton onClick={saveStory} />
    <SkipButton onClick={skipStory} />
    <ShareButton onClick={copyLink} />
  </EngagementBar>
</StoryDetailPage>
```

---

## API Calls

### Story with Articles + Perspectives

```
GET /api/bff/stories/{storyId}

Response: StoryDetailOut
{
  id: 123,
  headline: "Fed Holds Rates Steady Amid Inflation Concerns",
  summary: "The Federal Reserve announced...",
  categories: "finance,politics",
  status: "analyzed",
  article_count: 8,
  prompt_version: "v2",
  quality_score: 0.85,
  resonance_score: 4.72,
  first_seen: "2026-06-05T03:15:00Z",
  last_updated: "2026-06-05T04:30:00Z",
  articles: [
    {
      id: 456,
      source_id: 3,
      title: "Fed Keeps Rates at 5.25%...",
      url: "https://reuters.com/...",
      snippet: "The U.S. Federal Reserve...",
      published_at: "2026-06-05T02:30:00Z",
      fetched_at: "2026-06-05T03:15:00Z"
    }
  ],
  perspectives: [
    {
      id: 789,
      source_id: 3,
      summary: "Reuters frames the decision as...",
      sentiment: 0.05,
      bias_label: "center",
      key_claims: "[\"Fed held rates at 5.25%\", \"Inflation remains above target\"]"
    }
  ]
}
```

React Query key: `["stories", storyId, "detail"]`
Stale time: 5 minutes

### Resonance Breakdown

```
GET /api/bff/stories/{storyId}/resonance

Response: ResonanceOut
{
  cluster_id: 123,
  resonance: 4.72,
  momentum: 0.35,
  peak_resonance: 5.10,
  mention_count: 8,
  source_count: 6,
  authority_weighted_sum: 3.85,
  breadth: 2.58,
  window_hours: 72,
  computed_at: "2026-06-05T04:30:00Z"
}
```

React Query key: `["stories", storyId, "resonance"]`
Stale time: 5 minutes

### Source Lookup (for names)

Perspectives and articles contain `source_id` but not source name/bias.
The sources list is fetched once and cached globally.

```
GET /api/bff/sources?active=true

Response: SourceOut[]
// Cached in React Query with stale time of 30 minutes
```

React Query key: `["sources"]`
Build a lookup map: `Map<number, SourceOut>`

### Record Engagement

```
POST /api/bff/engagements
Body: { user_id: 5, cluster_id: 123, action: "save", read_time_sec: 0 }

Response: EngagementOut (201)
{ id, user_id, cluster_id, action, read_time_sec, created_at }
```

Mutation on success: show toast "Story saved" / "Story skipped"

---

## Key Components Detail

### BiasLabel

Visual badge showing the political leaning of a perspective's source.

| bias_label | Color | Text |
|------------|-------|------|
| `left` | `bg-blue-600 text-white` | Left |
| `center_left` | `bg-blue-300 text-blue-900` | Center-Left |
| `center` | `bg-gray-200 text-gray-800` | Center |
| `center_right` | `bg-red-300 text-red-900` | Center-Right |
| `right` | `bg-red-600 text-white` | Right |
| `unknown` | `bg-gray-100 text-gray-500` | Unknown |

Size: `px-2 py-0.5 text-xs font-medium rounded-full`

### SentimentBar

Horizontal bar visualizing sentiment from -1.0 (negative) to +1.0 (positive).

```
[-1.0 ─────────────|──── 0.0 ────|───────────── +1.0]
                    ████████      ← marker at sentiment value
```

**Implementation:**
- Container: `w-full h-2 bg-gray-100 rounded-full relative`
- Marker: `absolute w-3 h-3 rounded-full` positioned at `(sentiment + 1) / 2 * 100%`
- Color: red (< -0.3), orange (-0.3 to -0.1), gray (-0.1 to 0.1), light-green (0.1 to 0.3), green (> 0.3)
- Center line at 50% as thin gray border

### PerspectiveViewer — View Modes

**Side-by-side** (default on desktop >= 1024px):
- CSS grid: `grid-cols-2` for 2 perspectives, `grid-cols-3` for 3+
- Each card equal width, scrollable if content overflows

**Stacked** (default on mobile < 768px):
- Single column, full width
- Each perspective card separated by subtle divider

**Tabbed** (user toggle, any breakpoint):
- Tab bar with source names + bias label dots
- One perspective visible at a time
- Swipeable on mobile (touch gesture)

### ResonancePanel

Compact stat panel (horizontal on desktop, vertical on mobile).

```
┌──────────────────────────────────────────────────┐
│  4.72 ▲0.35    Peak: 5.10    6 sources    2.58b  │
│  resonance      momentum      coverage    breadth │
└──────────────────────────────────────────────────┘
```

Each stat: large number + small label underneath.
Momentum arrow: green ▲ (> 0.1), red ▼ (< -0.1), gray ─ (flat).

### KeyClaimsList

`key_claims` is stored as a JSON string in the API. Parse it client-side.

```typescript
const claims: string[] = JSON.parse(perspective.key_claims)
```

Render as bulleted list. Each claim is a single factual statement.

### EngagementBar

Sticky bottom bar (mobile) or floating right panel (desktop).

| Button | Action | Icon | API call |
|--------|--------|------|----------|
| Save | Bookmark story | Bookmark icon | `POST /engagements {action: "save"}` |
| Skip | Mark as not interesting | X icon | `POST /engagements {action: "skip"}` |
| Share | Copy story URL to clipboard | Share icon | No API call, `navigator.clipboard` |

After save/skip: disable both buttons, show confirmation. Track `read_time_sec`
from page load to engagement action.

---

## Read Time Tracking

Measure time spent on the story page to feed back to P_AI.

```typescript
const pageLoadTime = useRef(Date.now())

function handleEngagement(action: "save" | "skip") {
  const readTimeSec = Math.floor((Date.now() - pageLoadTime.current) / 1000)
  mutate({ user_id: session.user.id, cluster_id: storyId, action, read_time_sec: readTimeSec })
}
```

Also fire an `"open"` engagement on page mount (once per session per story):
```typescript
useEffect(() => {
  mutate({ action: "open", read_time_sec: 0 })
}, [storyId])
```

---

## UI States

### Loading
- `StoryHeader`: pulsing headline (h-8 w-3/4) + meta skeletons
- `NeutralSummary`: 3 pulsing lines
- `PerspectiveCard` x3: pulsing header + 4 pulsing lines each
- `ResonancePanel`: 4 pulsing stat boxes

### Empty / Edge Cases

| Condition | Display |
|-----------|---------|
| Story not found (404) | "Story not found" message + back to dashboard link |
| No perspectives yet (status=raw) | "This story is being analyzed — perspectives coming soon" |
| No resonance data (404) | ResonancePanel shows "—" for all stats |
| Single perspective only | Show single card full-width with note: "Only one source covered this story" |
| key_claims is empty `"[]"` | Hide KeyClaimsList section |

### Error
| Scenario | Display |
|----------|---------|
| Story fetch fails | Full-page error: "Could not load story" + retry button |
| Resonance fetch fails | Panel shows "—" values, no error toast (non-critical) |
| Engagement POST fails | Toast: "Could not save — try again" + re-enable buttons |

---

## Mobile Breakpoints

| Breakpoint | Changes |
|------------|---------|
| >= 1024px (lg) | Side-by-side perspectives (grid), ResonancePanel horizontal, EngagementBar as right panel |
| 768-1023px (md) | Perspectives stacked or 2-col grid, ResonancePanel horizontal |
| < 768px (sm) | Single-column everything, tabbed perspectives with swipe, EngagementBar sticky bottom, ResonancePanel vertical stack |

---

## Acceptance Criteria

| # | Criterion | Verification |
|---|-----------|--------------|
| 1 | Story headline and summary render from API data | Compare text with `GET /stories/{id}` response |
| 2 | All perspectives display with correct bias labels | Count cards, verify bias_label matches API |
| 3 | Bias labels are color-coded per spec | Left=blue, right=red, center=gray across 5+ stories |
| 4 | Sentiment bars position marker correctly | Verify marker at 75% for sentiment=0.5 |
| 5 | Key claims parse from JSON and render as list | Verify bullet count matches parsed array length |
| 6 | Resonance panel shows all 6 stats | Compare values with `/stories/{id}/resonance` |
| 7 | Article source links open original URLs | Click 3 links, verify external navigation |
| 8 | Save button fires engagement with correct read_time | Save after 10s, verify `read_time_sec >= 10` in API |
| 9 | Open engagement fires on page load | Load page, verify `action: "open"` in DB |
| 10 | Side-by-side mode works with 2-5 perspectives | Test stories with varying perspective counts |
| 11 | Tabbed mode works on mobile with swipe | Test on 375px viewport, swipe between tabs |
| 12 | 404 story shows not-found message | Visit `/stories/99999`, verify error page |

---

## Testing Strategy

- **Unit:** `BiasLabel` renders correct color for each of 6 labels
- **Unit:** `SentimentBar` positions marker at correct percentage
- **Unit:** `KeyClaimsList` parses JSON string and renders items
- **Unit:** `PerspectiveViewer` switches between view modes
- **Integration (MSW):** full page render with mocked story detail response
- **E2E:** navigate from dashboard → story detail → save → verify engagement
