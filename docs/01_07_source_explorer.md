# 01_07 — Source Explorer

**Parent:** 01 Web Frontend
**Depends on:** 01_01 (auth), 01_08 (design system for bias colors)

---

## Objective

Build a page that shows all news sources Prism aggregates from, with their
trust scores and bias labels. This is a transparency feature — users can see
exactly where their news comes from and how each source is rated.

---

## Route

`/sources` — protected.

---

## Component Tree

```
<SourcesPage>
  <PageHeader>
    <Heading text="News Sources" />
    <Subtext text="Every source Prism aggregates from, with trust and bias ratings" />
    <SourceCount text="{count} active sources" />
  </PageHeader>

  <FilterBar>
    <SearchInput
      placeholder="Search sources..."
      value={search}
      onChange={setSearch}
    />
    <BiasFilter>
      <FilterChip label="All" active={bias === null} />
      <FilterChip label="Left" active={bias === "left"} color="blue-600" />
      <FilterChip label="Center-Left" active={bias === "center_left"} color="blue-300" />
      <FilterChip label="Center" active={bias === "center"} color="gray-400" />
      <FilterChip label="Center-Right" active={bias === "center_right"} color="red-300" />
      <FilterChip label="Right" active={bias === "right"} color="red-600" />
    </BiasFilter>
    <SortSelect value={sortBy} onChange={setSortBy}>
      <option value="trust_desc">Trust: High → Low</option>
      <option value="trust_asc">Trust: Low → High</option>
      <option value="name_asc">Name: A → Z</option>
      <option value="bias">Bias: Left → Right</option>
    </SortSelect>
  </FilterBar>

  <SourceTable>
    <TableHeader>
      <Column text="Source" sortable />
      <Column text="Trust Score" sortable />
      <Column text="Bias" sortable />
      <Column text="Categories" />
      <Column text="Stories" />                  // link to filtered story list
    </TableHeader>
    <TableBody>
      <SourceRow source>                         // repeated per source
        <SourceNameCell>
          <FaviconImg src={`https://www.google.com/s2/favicons?domain=${domain}`} />
          <SourceName text={source.name} />
          <SourceUrl text={domain} muted />
        </SourceNameCell>
        <TrustScoreCell>
          <TrustBar value={source.trust_score} />
          <TrustValue text={source.trust_score.toFixed(2)} />
        </TrustScoreCell>
        <BiasCell>
          <BiasLabel label={source.bias_label} />
        </BiasCell>
        <CategoriesCell>
          <CategoryPill category />              // repeated, from source.categories
        </CategoriesCell>
        <StoriesCell>
          <StoriesLink href={`/stories?source=${source.id}`} text="View" />
        </StoriesCell>
      </SourceRow>
    </TableBody>
  </SourceTable>

  <SourceStats>
    <StatCard label="Average Trust" value={avgTrust.toFixed(2)} />
    <StatCard label="Bias Distribution" chart={biasDistribution} />
    <StatCard label="Total Active" value={count} />
  </SourceStats>
</SourcesPage>
```

---

## API Calls

### List All Active Sources

```
GET /api/bff/sources?active=true

Response: SourceOut[]
[{
  id: 1,
  name: "Reuters",
  url: "https://www.reuters.com",
  rss_url: "https://www.reuters.com/rssFeed/worldNews",
  trust_score: 0.92,
  bias_label: "center",
  categories: "world,finance,politics",
  active: true,
  created_at: "2026-05-01T00:00:00Z"
}]
```

React Query key: `["sources", "active"]`
Stale time: 30 minutes (source list changes very rarely)

**Note:** The API returns sources sorted by trust_score descending. All
filtering, searching, and sorting happens client-side since the full list
is small (~30-100 sources, easily fits in memory).

---

## Client-Side Operations

All filtering and sorting is done in the browser — no additional API calls.

### Search Filter

```typescript
const filtered = sources.filter(s =>
  s.name.toLowerCase().includes(search.toLowerCase()) ||
  s.url.toLowerCase().includes(search.toLowerCase())
)
```

Debounced by 200ms via `useDeferredValue` or manual debounce.

### Bias Filter

```typescript
const biasFiltered = bias === null
  ? filtered
  : filtered.filter(s => s.bias_label === bias)
```

### Sort

```typescript
const sorted = [...biasFiltered].sort((a, b) => {
  switch (sortBy) {
    case "trust_desc": return b.trust_score - a.trust_score
    case "trust_asc": return a.trust_score - b.trust_score
    case "name_asc": return a.name.localeCompare(b.name)
    case "bias": return BIAS_ORDER[a.bias_label] - BIAS_ORDER[b.bias_label]
  }
})

const BIAS_ORDER = { left: 0, center_left: 1, center: 2, center_right: 3, right: 4, unknown: 5 }
```

---

## Key Components

### TrustBar

Horizontal progress bar showing trust score (0.0 to 1.0).

```typescript
interface TrustBarProps {
  value: number  // 0.0 to 1.0
}
```

**Visual:**
- Container: `w-24 h-2 bg-gray-100 rounded-full`
- Fill: width = `value * 100%`, color varies by range:

| Score | Color | Label |
|-------|-------|-------|
| 0.0 - 0.3 | `bg-red-400` | Low |
| 0.3 - 0.6 | `bg-yellow-400` | Medium |
| 0.6 - 0.8 | `bg-green-400` | Good |
| 0.8 - 1.0 | `bg-green-600` | High |

Numeric value shown beside the bar: `0.92`.

### BiasLabel

Same component as defined in `01_03`. Reused here.

### Bias Distribution Chart

Mini donut/pie chart in the stats section showing count per bias label.

```typescript
const distribution = sources.reduce((acc, s) => {
  acc[s.bias_label] = (acc[s.bias_label] || 0) + 1
  return acc
}, {} as Record<string, number>)
```

Implementation: simple SVG donut (no charting library needed for 6 segments).
Colors match BiasLabel badge colors. Legend shows count per label.

### Favicon

Google's favicon service for source icons:
```
https://www.google.com/s2/favicons?domain=${new URL(source.url).hostname}&sz=32
```

Fallback: generic globe icon if favicon fails to load.

```typescript
<img
  src={faviconUrl}
  onError={(e) => { e.currentTarget.src = "/icons/globe.svg" }}
  alt=""
  className="w-5 h-5 rounded"
/>
```

---

## UI States

### Loading
- Table skeleton: 10 rows with pulsing cells
- Stats: 3 pulsing stat cards

### Empty

| Condition | Display |
|-----------|---------|
| No sources match search | "No sources match '{search}'" + clear button |
| No sources match bias filter | "No {bias} sources found" + reset button |

### Error
| Scenario | Display |
|----------|---------|
| Source fetch fails | "Could not load sources" + retry button |

---

## Mobile Breakpoints

| Breakpoint | Layout |
|------------|--------|
| >= 1024px (lg) | Full table with all 5 columns. Stats row below. |
| 768-1023px (md) | Table hides Categories column. Filter chips wrap to 2 rows. |
| < 768px (sm) | Card layout instead of table. Each source as a card: name + favicon on top, trust bar + bias badge below, categories as pills. Search input full-width. Sort as dropdown. Stats stacked vertically. |

**Mobile card layout:**
```
┌─────────────────────────┐
│ 🌐 Reuters              │
│ reuters.com             │
│ ████████████░░ 0.92     │
│ [Center]  finance world │
│ View stories →          │
└─────────────────────────┘
```

---

## Acceptance Criteria

| # | Criterion | Verification |
|---|-----------|--------------|
| 1 | All active sources display in table | Compare row count with `GET /sources?active=true` length |
| 2 | Trust score bars are proportional to value | Source with 0.92 has ~92% fill width |
| 3 | Trust bar colors match score ranges | 0.2 = red, 0.5 = yellow, 0.7 = green, 0.9 = dark green |
| 4 | Bias labels match API values with correct colors | Spot-check 5 sources against API response |
| 5 | Search filters by name and URL | Type "reuters", verify only Reuters visible |
| 6 | Bias filter shows only selected label | Click "Left", verify only left-bias sources |
| 7 | Sort by trust descending shows highest first | Click sort, verify first row has highest score |
| 8 | Sort by bias groups left → right | Click sort, verify order matches bias spectrum |
| 9 | Favicons load for known domains | Verify Reuters, BBC, NPR show favicons |
| 10 | Stats show correct average trust | Calculate manually, compare with displayed value |
| 11 | Bias distribution chart shows correct proportions | Compare segment sizes with counted labels |
| 12 | Mobile card layout renders at 375px | Resize, verify cards replace table |

---

## Testing Strategy

- **Unit:** `TrustBar` renders correct width and color for each range
- **Unit:** search filter matches name and URL
- **Unit:** bias filter isolates correct sources
- **Unit:** sort functions produce correct order
- **Unit:** favicon fallback triggers on load error
- **Integration (MSW):** full page with mocked 30 sources, test filter combos
- **E2E:** load sources → search → filter by bias → sort → verify display
