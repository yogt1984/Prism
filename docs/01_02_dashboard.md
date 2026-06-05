# 01_02 — Dashboard & Story Feed

**Parent:** 01 Web Frontend
**Depends on:** 01_01 (auth session required)

---

## Objective

Build the primary authenticated landing page that shows today's briefing,
top stories ranked by resonance, and tracked keyword sparklines. This is the
first thing users see after login.

---

## Route

`/dashboard` — protected, redirects to `/login` if unauthenticated.

---

## Component Tree

```
<DashboardPage>
  <DashboardLayout>
    <Sidebar>                                      // desktop: left 280px, mobile: hidden
      <UserGreeting name={session.user.name} />
      <KeywordSidebar>
        <SidebarHeading text="Tracked Keywords" />
        <KeywordList>
          <KeywordItem keyword perception momentum> // per keyword
            <KeywordName />
            <Sparkline data={history} />            // last 20 points
            <MomentumArrow direction />             // ▲ ▼ ─
          </KeywordItem>
        </KeywordList>
        <AddKeywordButton />                        // opens modal
      </KeywordSidebar>
      <QuickActions>
        <TriggerBriefingButton />
        <AddKeywordButton />
      </QuickActions>
    </Sidebar>

    <MainContent>                                   // flex-1
      <TodayBriefingCard>
        <CardHeader text="Today's Briefing" date />
        <BriefingPreview html={content_html} />     // truncated to 300 chars
        <StoryCount count={story_count} />
        <ViewFullButton href="/briefings/{id}" />
      </TodayBriefingCard>

      <TopStoriesSection>
        <SectionHeader text="Top Stories" />
        <StoryCardRow>                              // horizontal scroll on mobile
          <StoryCard story>                         // repeated, max 5
            <CategoryPill category />
            <Headline text />
            <ResonanceBadge score momentum />
            <SourceCount count />
            <TimeAgo firstSeen />
          </StoryCard>
        </StoryCardRow>
        <ViewAllLink href="/stories" />
      </TopStoriesSection>

      <RecentStoriesFeed>
        <SectionHeader text="Recent Stories" />
        <StoryList>
          <StoryRow story>                          // compact row format
            <CategoryDot color />
            <Headline />
            <ResonanceScore />
            <TimeAgo />
          </StoryRow>
        </StoryList>
        <LoadMoreButton />                          // offset-based pagination
      </RecentStoriesFeed>
    </MainContent>
  </DashboardLayout>
</DashboardPage>
```

---

## API Calls & Data Fetching

All calls go through BFF proxy (`/api/bff/...`). React Query handles caching.

### Today's Briefing

```
GET /api/bff/users/{userId}/briefings?limit=1

Response: BriefingOut[]
[{
  id: 42,
  user_id: 5,
  story_count: 10,
  prompt_version: "v2",
  sent: true,
  sent_at: "2026-06-05T07:00:00Z",
  created_at: "2026-06-05T06:58:12Z"
}]

// If content needed for preview:
GET /api/bff/users/{userId}/briefings/42

Response: BriefingDetailOut
{ ...BriefingOut, content_html: "<h2>...", content_text: "..." }
```

React Query key: `["briefings", userId, "latest"]`
Stale time: 5 minutes (briefings are daily, no need for frequent refetch)

### Top Stories by Resonance

```
GET /api/bff/stories?sort=resonance&status=analyzed&limit=5

Response: StoryOut[]
[{
  id: 123,
  headline: "Fed Holds Rates Steady...",
  summary: "The Federal Reserve...",
  categories: "finance,politics",
  status: "analyzed",
  article_count: 8,
  prompt_version: "v2",
  quality_score: 0.85,
  resonance_score: 4.72,
  first_seen: "2026-06-05T03:15:00Z",
  last_updated: "2026-06-05T04:30:00Z"
}]
```

React Query key: `["stories", "top-resonance"]`
Stale time: 2 minutes
Refetch on window focus: true

### Recent Stories Feed

```
GET /api/bff/stories?sort=first_seen&status=analyzed&limit=20&offset={offset}

Response: StoryOut[] (same schema as above)
```

React Query key: `["stories", "recent", offset]`
Stale time: 1 minute

### Keyword Sidebar

```
// Step 1: get active keywords
GET /api/bff/keywords?active=true

Response: KeywordOut[]
[{
  id: 7,
  keyword: "tariffs",
  aliases: "trade war,import duties",
  category: "finance",
  is_active: true,
  created_at: "2026-06-01T12:00:00Z"
}]

// Step 2: for each keyword, get perception history (last 20 points)
GET /api/bff/keywords/7/perception/history?limit=20

Response: PerceptionOut[]
[{
  keyword_id: 7,
  perception: -0.35,
  salience: 2.1,
  valence: -0.17,
  momentum: -0.05,
  cluster_count: 4,
  source_count: 12,
  computed_at: "2026-06-05T06:30:00Z"
}]
```

React Query key: `["keywords", "active"]` and `["perception", keywordId, "sparkline"]`
Stale time: 5 minutes for keywords, 2 minutes for perception

### Trigger On-Demand Briefing

```
POST /api/bff/users/{userId}/briefings

Response: BriefingDetailOut (201)
{ id, content_html, content_text, story_count, ... }

Error: 422 { detail: "No stories available for briefing generation" }
```

Mutation key: `["briefings", "trigger"]`
On success: invalidate `["briefings", userId, "latest"]`

---

## UI States

### Loading

| Component | Loading display |
|-----------|----------------|
| TodayBriefingCard | Skeleton: gray rectangle (h-32), pulsing |
| StoryCard (x5) | Skeleton: 5 cards with pulsing headline + badge placeholders |
| StoryRow | Skeleton: 10 rows with pulsing bars |
| KeywordItem | Skeleton: 4 items with pulsing name + flat sparkline |

### Empty

| Component | Empty condition | Display |
|-----------|----------------|---------|
| TodayBriefingCard | No briefings returned | "No briefing yet — your first one arrives at 7am UTC" with clock icon |
| TopStoriesSection | No analyzed stories | "Stories are being analyzed — check back soon" |
| RecentStoriesFeed | No stories at all | "No stories discovered yet. The pipeline runs every 2 hours." |
| KeywordSidebar | No keywords tracked | "Track your first keyword to see media pressure" + Add button |

### Error

| Scenario | Display |
|----------|---------|
| BFF returns 401 | Redirect to `/login` (session expired) |
| BFF returns 500 | Toast: "Could not load {section}. Retrying..." + auto-retry 3x |
| Network failure | Banner at top: "Connection lost — data may be stale" |
| Trigger briefing 422 | Toast: "No stories available yet" |

---

## Sparkline Component

Renders in the keyword sidebar. Tiny inline chart (80px x 24px).

**Input:** `PerceptionOut[]` (last 20 points)
**X-axis:** time (hidden, implied by point order)
**Y-axis:** `perception` value, range -1.0 to +1.0
**Color:** green if latest momentum > 0, red if < 0, gray if ~0

Implementation: SVG `<polyline>` — no charting library needed for this.

```typescript
interface SparklineProps {
  data: { perception: number; computed_at: string }[]
  width?: number   // default 80
  height?: number  // default 24
}
```

---

## ResonanceBadge Component

Shows on story cards. Visual indicator of media impact.

**Input:** `resonance_score: number`, `momentum?: number`
**Display:** rounded pill with score, color-coded by magnitude

| Score range | Color | Label |
|-------------|-------|-------|
| 0 - 1.0 | gray | Low |
| 1.0 - 3.0 | blue | Moderate |
| 3.0 - 5.0 | orange | High |
| 5.0+ | red | Viral |

Momentum arrow: `▲` (positive), `▼` (negative), `─` (flat, abs < 0.1)

---

## Mobile Breakpoints

| Breakpoint | Layout change |
|------------|---------------|
| >= 1024px (lg) | Sidebar visible (280px), main content beside it |
| 768-1023px (md) | Sidebar collapses to icon rail, expands on click |
| < 768px (sm) | Sidebar hidden, accessible via hamburger menu. StoryCardRow scrolls horizontally. Bottom nav replaces sidebar. |

**Touch targets:** all interactive elements minimum 44px height on mobile.

---

## Acceptance Criteria

| # | Criterion | Verification |
|---|-----------|--------------|
| 1 | Dashboard loads within 2s showing briefing + stories | Lighthouse audit, network throttled to Fast 3G |
| 2 | Today's briefing card shows correct content_html preview | Compare truncated text with API response |
| 3 | Top 5 stories are sorted by resonance descending | Verify order matches `GET /stories?sort=resonance` |
| 4 | Story cards show headline, category pill, resonance badge | Visual inspection across 5 stories |
| 5 | Category pills use correct colors per category | Each of 8 categories has distinct color |
| 6 | Keyword sparklines render perception history | Add keyword, wait for data, verify chart has points |
| 7 | Momentum arrows match perception momentum sign | Compare arrow direction with API `momentum` value |
| 8 | "Load more" fetches next page of stories | Click, verify 20 more rows appear with correct offset |
| 9 | Trigger briefing button generates new briefing | Click, verify toast + briefing card updates |
| 10 | Empty states display when no data exists | Fresh account, verify all empty messages show |
| 11 | Sidebar collapses on tablet, hides on mobile | Resize browser, verify responsive behavior |
| 12 | Story card click navigates to `/stories/{id}` | Click card, verify URL and page render |

---

## Testing Strategy

- **Unit:** `ResonanceBadge` renders correct color/label for each score range
- **Unit:** `Sparkline` renders correct SVG path from perception data
- **Unit:** `TodayBriefingCard` handles null/empty/loaded states
- **Integration (MSW):** mock BFF endpoints, verify full dashboard renders
- **E2E (Playwright):** login → dashboard loads → click story → navigate
