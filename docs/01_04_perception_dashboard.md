# 01_04 — Perception Dashboard & Charts

**Parent:** 01 Web Frontend
**Depends on:** 01_01 (auth), 01_08 (design system, chart library)

---

## Objective

Build an interactive dashboard for tracking keyword perception pressure over
time. Users add keywords (e.g., "tariffs", "AI regulation") and see how media
framing evolves through time-series charts showing salience, valence, and
net perception.

---

## Route

`/perception` — protected.

---

## Component Tree

```
<PerceptionPage>
  <PageHeader>
    <Heading text="Perception Tracker" />
    <Subtext text="Monitor how media frames your tracked topics over time" />
    <AddKeywordButton onClick={openModal} />
  </PageHeader>

  <KeywordOverviewGrid>                          // responsive grid
    <KeywordOverviewCard keyword>                // repeated per active keyword
      <CardHeader>
        <KeywordName text={keyword.keyword} />
        <CategoryBadge text={keyword.category} />
        <RemoveButton onClick={deactivate} />
      </CardHeader>
      <PerceptionValue>
        <LargeNumber value={latest.perception} />
        <MomentumArrow value={latest.momentum} />
        <Label text="perception pressure" />
      </PerceptionValue>
      <StatRow>
        <Stat label="salience" value={latest.salience} />
        <Stat label="valence" value={latest.valence} format="+/-" />
        <Stat label="sources" value={latest.source_count} />
        <Stat label="clusters" value={latest.cluster_count} />
      </StatRow>
      <MiniChart data={history} field="perception" height={80} />
      <ExpandButton onClick={selectKeyword} />
    </KeywordOverviewCard>
  </KeywordOverviewGrid>

  <DetailPanel visible={selectedKeyword !== null}>
    <DetailHeader>
      <KeywordName text={selected.keyword} />
      <AliasesList aliases={selected.aliases} />
      <TimeRangeSelector options={[24h, 7d, 30d]} />
    </DetailHeader>
    <PerceptionChart>                            // full-size Recharts
      <TimeSeriesLine field="perception" color="purple" />
      <TimeSeriesLine field="valence" color="blue" />
      <TimeSeriesBar field="salience" color="gray" opacity={0.3} />
      <ZeroLine />                               // horizontal at y=0
      <Tooltip showing={perception, salience, valence, source_count} />
      <XAxis type="time" />
      <YAxis domain={[-1, 1]} label="perception / valence" />
      <YAxisRight domain="auto" label="salience" />
    </PerceptionChart>
    <MomentumIndicator>
      <TrendLabel text="rising" | "falling" | "stable" />
      <DeltaValue value={latest.momentum} />
      <TrendExplanation />                       // "Perception shifted +0.12 in last scan"
    </MomentumIndicator>
  </DetailPanel>

  <AddKeywordModal visible={isModalOpen}>
    <ModalHeader text="Track a New Keyword" />
    <KeywordInput placeholder="e.g., tariffs" />
    <AliasesInput placeholder="e.g., trade war, import duties" />
    <CategorySelect options={categories} />
    <SubmitButton text="Start Tracking" />
  </AddKeywordModal>
</PerceptionPage>
```

---

## API Calls

### List Active Keywords

```
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
```

React Query key: `["keywords", "active"]`
Stale time: 5 minutes

### Latest Perception per Keyword

```
GET /api/bff/keywords/{keywordId}/perception

Response: PerceptionOut
{
  keyword_id: 7,
  perception: -0.35,
  salience: 2.1,
  valence: -0.17,
  momentum: -0.05,
  cluster_count: 4,
  source_count: 12,
  computed_at: "2026-06-05T06:30:00Z"
}

Error 404: { detail: "No perception data yet for this keyword" }
```

React Query key: `["perception", keywordId, "latest"]`
Stale time: 2 minutes

### Perception History (for charts)

```
GET /api/bff/keywords/{keywordId}/perception/history?limit={limit}

Response: PerceptionOut[] (newest first)

// limit by time range:
//   24h → limit=48  (30-min intervals)
//   7d  → limit=336
//   30d → limit=500 (API max)
```

React Query key: `["perception", keywordId, "history", timeRange]`
Stale time: 2 minutes

**Important:** API returns newest first. Reverse the array for chart display
(charts need chronological order, oldest → newest).

### Add Keyword

```
POST /api/bff/keywords
Body: { keyword: "AI regulation", aliases: "AI safety,AI governance", category: "technology" }

Response: KeywordOut (201)
{ id: 12, keyword: "AI regulation", aliases: "AI safety,AI governance", ... }

Error 409: { detail: "Keyword 'AI regulation' already tracked" }
```

Mutation on success: invalidate `["keywords", "active"]`, close modal, show toast.

### Remove Keyword

```
DELETE /api/bff/keywords/{keywordId}

Response: 204 (no body)
Error 404: { detail: "Keyword not found" }
```

Mutation on success: invalidate `["keywords", "active"]`, show toast.

---

## Chart Specification

Library: **Recharts** (composable, React-native, good TypeScript support).

### PerceptionChart (Detail Panel)

**Data shape** (after reversing API response):

```typescript
interface ChartDataPoint {
  time: number          // Unix timestamp for XAxis
  perception: number    // -1.0 to +1.0
  valence: number       // -1.0 to +1.0
  salience: number      // 0 to ~10+ (unbounded)
  source_count: number
  cluster_count: number
}
```

**Chart config:**

| Element | Type | Axis | Color | Notes |
|---------|------|------|-------|-------|
| Perception | `<Line>` | left Y | `#8B5CF6` (purple-500) | `strokeWidth={2}`, primary signal |
| Valence | `<Line>` | left Y | `#3B82F6` (blue-500) | `strokeWidth={1}`, dashed |
| Salience | `<Bar>` | right Y | `#9CA3AF` (gray-400) | `opacity={0.3}`, background context |
| Zero line | `<ReferenceLine>` | left Y | `#D1D5DB` (gray-300) | `y={0}`, dashed |

**Left Y-axis:** fixed domain `[-1, 1]`, label "Perception / Valence"
**Right Y-axis:** auto domain, label "Salience (attention volume)"
**X-axis:** time, formatted as "Jun 5 06:00" (or "Jun 1" for 30d view)
**Tooltip:** shows all values on hover, formatted to 2 decimal places

### MiniChart (Overview Cards)

Simplified version: single `<Line>` for perception only.
No axes, no tooltip, no legend. Just the trend line.

```typescript
<ResponsiveContainer width="100%" height={80}>
  <LineChart data={history}>
    <Line
      dataKey="perception"
      stroke={momentum > 0 ? "#22C55E" : momentum < 0 ? "#EF4444" : "#9CA3AF"}
      dot={false}
      strokeWidth={1.5}
    />
    <ReferenceLine y={0} stroke="#E5E7EB" />
  </LineChart>
</ResponsiveContainer>
```

### Time Range Selector

| Option | API limit | X-axis format | Granularity |
|--------|-----------|---------------|-------------|
| 24h | 48 | "HH:mm" | ~30 min per point |
| 7d | 336 | "ddd HH:mm" | ~30 min per point |
| 30d | 500 | "MMM DD" | ~87 min per point |

Default: 7d. Persisted in `localStorage` per keyword.

---

## AddKeywordModal Detail

**Fields:**

| Field | Type | Validation | Required |
|-------|------|------------|----------|
| keyword | text input | 1-100 chars, no commas | Yes |
| aliases | text input | comma-separated, each 1-100 chars | No |
| category | select dropdown | 8 categories from `GET /config` | No |

**Submit flow:**
1. Validate locally (keyword not empty, no commas in keyword)
2. Disable button, show spinner
3. `POST /keywords` via BFF
4. On 201: close modal, toast "Now tracking '{keyword}'", refetch keyword list
5. On 409: show inline error "Already tracking this keyword"
6. On error: toast "Could not add keyword — try again"

---

## UI States

### Loading

| Component | Display |
|-----------|---------|
| KeywordOverviewGrid | 3 skeleton cards (pulsing stat boxes + flat line) |
| DetailPanel chart | Pulsing rectangle (h-64) |
| Latest perception | Pulsing number placeholder |

### Empty

| Condition | Display |
|-----------|---------|
| No keywords tracked | Full-page empty: illustration + "Start tracking a topic" + Add button |
| Keyword has no perception data yet | Overview card shows "Waiting for first scan..." instead of stats, flat gray MiniChart |
| History returns empty array | Detail chart shows "No data for this time range" centered |

### Error

| Scenario | Display |
|----------|---------|
| Keywords list fails | "Could not load keywords" + retry button |
| Perception fetch fails | Card shows "—" values, no chart |
| History fetch fails | Chart area shows "Could not load history" + retry |
| Delete fails | Toast: "Could not remove keyword" |

---

## Mobile Breakpoints

| Breakpoint | Layout |
|------------|--------|
| >= 1024px (lg) | Overview grid 3 columns, detail panel beside grid (60/40 split) |
| 768-1023px (md) | Overview grid 2 columns, detail panel below grid (full width) |
| < 768px (sm) | Overview grid 1 column, detail panel full-screen overlay (slide up). Chart height reduced to 200px. Time range as pill row. |

---

## Acceptance Criteria

| # | Criterion | Verification |
|---|-----------|--------------|
| 1 | All active keywords display as overview cards | Compare card count with `GET /keywords?active=true` length |
| 2 | Latest perception values match API response | Compare displayed number with `GET /keywords/{id}/perception` |
| 3 | MiniChart renders perception trend line | Verify SVG path has correct number of points |
| 4 | Detail chart shows 3 data series (perception, valence, salience) | Select keyword, verify 3 lines/bars render |
| 5 | Time range selector changes chart data | Switch 24h → 7d, verify different point count |
| 6 | Chart data is chronological (oldest left) | Verify first point timestamp < last point timestamp |
| 7 | Tooltip shows all values on hover | Hover chart, verify perception + valence + salience shown |
| 8 | Zero line visible at y=0 | Visual inspection |
| 9 | Add keyword creates new tracking entry | Fill modal, submit, verify new card appears |
| 10 | Duplicate keyword shows 409 error | Try adding same keyword, verify inline error |
| 11 | Remove keyword hides card and preserves history | Click remove, verify card gone, re-add shows old data |
| 12 | Mobile overlay chart is usable at 375px | Tap keyword card, verify chart renders in overlay |

---

## Testing Strategy

- **Unit:** `PerceptionChart` renders correct number of data points
- **Unit:** `MiniChart` color matches momentum sign
- **Unit:** `AddKeywordModal` validates input and handles 409
- **Unit:** time range selector computes correct API limit
- **Integration (MSW):** full page with mocked keywords + perception history
- **E2E:** add keyword → wait for perception data → verify chart → remove keyword
