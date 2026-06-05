# 01_08 — Project Scaffolding, Design System & CI

**Parent:** 01 Web Frontend
**Must complete before:** all other 01_xx specs (provides shared foundation)

---

## Objective

Set up the Next.js project structure, Tailwind design tokens, shared component
library, Docker integration, and CI pipeline. Every other frontend spec builds
on this foundation.

---

## Project Structure

```
frontend/
├── app/
│   ├── layout.tsx                  // root layout: providers, nav, metadata
│   ├── page.tsx                    // landing page (/)
│   ├── login/page.tsx              // 01_01
│   ├── signup/page.tsx             // 01_01
│   ├── check-email/page.tsx        // 01_01
│   ├── auth-error/page.tsx         // 01_01
│   ├── dashboard/page.tsx          // 01_02
│   ├── stories/[id]/page.tsx       // 01_03
│   ├── briefings/
│   │   ├── page.tsx                // 01_05 list
│   │   └── [id]/page.tsx           // 01_05 reader
│   ├── perception/page.tsx         // 01_04
│   ├── settings/page.tsx           // 01_06
│   ├── sources/page.tsx            // 01_07
│   └── api/
│       ├── auth/[...nextauth]/route.ts  // 01_01
│       └── bff/[...path]/route.ts       // 01_01 BFF proxy
├── components/
│   ├── layout/
│   │   ├── AppShell.tsx            // sidebar + main content wrapper
│   │   ├── Sidebar.tsx             // nav links, keyword sidebar
│   │   ├── BottomNav.tsx           // mobile navigation
│   │   └── PageHeader.tsx          // consistent page title + actions
│   ├── ui/                         // atomic design system components
│   │   ├── Badge.tsx
│   │   ├── Button.tsx
│   │   ├── Card.tsx
│   │   ├── Input.tsx
│   │   ├── Modal.tsx
│   │   ├── RadioGroup.tsx
│   │   ├── Select.tsx
│   │   ├── Skeleton.tsx
│   │   ├── Slider.tsx
│   │   ├── Toast.tsx
│   │   └── Tooltip.tsx
│   ├── data-display/               // domain-specific display components
│   │   ├── BiasLabel.tsx
│   │   ├── CategoryPill.tsx
│   │   ├── MomentumArrow.tsx
│   │   ├── ResonanceBadge.tsx
│   │   ├── SentimentBar.tsx
│   │   ├── Sparkline.tsx
│   │   └── TrustBar.tsx
│   └── providers/
│       ├── AuthProvider.tsx        // NextAuth SessionProvider
│       ├── QueryProvider.tsx       // React Query QueryClientProvider
│       └── ToastProvider.tsx       // toast notification context
├── lib/
│   ├── api.ts                      // typed fetch helpers for BFF
│   ├── hooks/
│   │   ├── useStories.ts           // React Query: stories
│   │   ├── useBriefings.ts         // React Query: briefings
│   │   ├── useKeywords.ts          // React Query: keywords + perception
│   │   ├── useSources.ts           // React Query: sources
│   │   └── useUser.ts              // React Query: user profile
│   ├── types.ts                    // TypeScript types matching API schemas
│   └── constants.ts                // category colors, bias colors, etc.
├── public/
│   ├── icons/
│   │   └── globe.svg               // fallback favicon
│   └── og-image.png                // social share image
├── __tests__/
│   ├── components/                 // React Testing Library unit tests
│   └── e2e/                        // Playwright E2E tests
├── tailwind.config.ts
├── next.config.ts
├── tsconfig.json
├── package.json
├── Dockerfile
├── .env.local.example
└── playwright.config.ts
```

---

## TypeScript Types (`lib/types.ts`)

Mirror the FastAPI response schemas exactly:

```typescript
// Matches SourceOut
export interface Source {
  id: number
  name: string
  url: string
  rss_url: string
  trust_score: number
  bias_label: BiasLabel
  categories: string       // comma-separated
  active: boolean
  created_at: string       // ISO datetime
}

// Matches StoryOut
export interface Story {
  id: number
  headline: string
  summary: string
  categories: string
  status: "raw" | "analyzed"
  article_count: number
  prompt_version: string
  quality_score: number
  resonance_score: number
  first_seen: string
  last_updated: string
}

// Matches StoryDetailOut
export interface StoryDetail extends Story {
  articles: Article[]
  perspectives: Perspective[]
}

export interface Article {
  id: number
  source_id: number
  title: string
  url: string
  snippet: string
  published_at: string | null
  fetched_at: string
}

export interface Perspective {
  id: number
  source_id: number
  summary: string
  sentiment: number        // -1.0 to 1.0
  bias_label: BiasLabel
  key_claims: string       // JSON string of string[]
}

export interface Resonance {
  cluster_id: number
  resonance: number
  momentum: number
  peak_resonance: number
  mention_count: number
  source_count: number
  authority_weighted_sum: number
  breadth: number
  window_hours: number
  computed_at: string
}

export interface User {
  id: number
  email: string
  name: string
  interests: string
  preferred_format: BriefingFormat
  briefing_depth: number
  is_pro: boolean
  created_at: string
}

export interface Briefing {
  id: number
  user_id: number
  story_count: number
  prompt_version: string
  sent: boolean
  sent_at: string | null
  created_at: string
}

export interface BriefingDetail extends Briefing {
  content_html: string
  content_text: string
}

export interface Engagement {
  id: number
  user_id: number
  cluster_id: number
  action: "open" | "read" | "save" | "skip"
  read_time_sec: number
  created_at: string
}

export interface Keyword {
  id: number
  keyword: string
  aliases: string
  category: string
  is_active: boolean
  created_at: string
}

export interface PerceptionSnapshot {
  keyword_id: number
  perception: number
  salience: number
  valence: number
  momentum: number
  cluster_count: number
  source_count: number
  computed_at: string
}

export type BiasLabel = "left" | "center_left" | "center" | "center_right" | "right" | "unknown"
export type BriefingFormat = "email" | "json_feed" | "audio_script"
export type Category = "finance" | "politics" | "technology" | "sports" | "culture" | "science" | "health" | "world"
```

---

## Design Tokens (`tailwind.config.ts`)

### Color Palette

```typescript
const config = {
  theme: {
    extend: {
      colors: {
        // Brand
        brand: { 50: "#F5F3FF", 500: "#8B5CF6", 700: "#6D28D9", 900: "#4C1D95" },

        // Bias spectrum
        bias: {
          left: "#2563EB",           // blue-600
          "center-left": "#93C5FD",  // blue-300
          center: "#9CA3AF",         // gray-400
          "center-right": "#FCA5A5", // red-300
          right: "#DC2626",          // red-600
        },

        // Sentiment
        sentiment: {
          negative: "#EF4444",       // red-500
          neutral: "#9CA3AF",        // gray-400
          positive: "#22C55E",       // green-500
        },

        // Trust score
        trust: {
          low: "#F87171",            // red-400
          medium: "#FACC15",         // yellow-400
          good: "#4ADE80",           // green-400
          high: "#16A34A",           // green-600
        },

        // Category (for pills and dots)
        category: {
          finance: "#F59E0B",        // amber-500
          politics: "#8B5CF6",       // violet-500
          technology: "#3B82F6",     // blue-500
          sports: "#22C55E",         // green-500
          culture: "#EC4899",        // pink-500
          science: "#06B6D4",        // cyan-500
          health: "#EF4444",         // red-500
          world: "#6366F1",          // indigo-500
        },
      },
    },
  },
}
```

### Typography

- Body: system font stack (`font-sans` default)
- Headings: same stack, `font-semibold`
- Monospace: for API keys, scores (`font-mono`)
- Briefing content: `@tailwindcss/typography` prose classes

### Spacing / Layout Constants

```typescript
// constants.ts
export const SIDEBAR_WIDTH = 280         // px, desktop sidebar
export const MOBILE_BREAKPOINT = 768     // px
export const TABLET_BREAKPOINT = 1024    // px
export const MAX_CONTENT_WIDTH = 1280    // px
export const TOAST_DURATION = 4000       // ms
```

---

## Shared Components (`components/ui/`)

### Button

```typescript
interface ButtonProps {
  variant: "primary" | "secondary" | "ghost" | "danger"
  size: "sm" | "md" | "lg"
  disabled?: boolean
  loading?: boolean    // shows spinner, disables click
  children: ReactNode
  onClick?: () => void
}
```

### Skeleton

```typescript
interface SkeletonProps {
  className?: string   // width, height via Tailwind
  variant: "text" | "rect" | "circle"
}
// Usage: <Skeleton variant="text" className="h-6 w-3/4" />
```

### Toast

Context-based toast system.

```typescript
const { toast } = useToast()
toast({ title: "Settings saved", variant: "success" })
toast({ title: "Could not save", variant: "error", description: "Try again" })
```

Auto-dismiss after `TOAST_DURATION`. Stack up to 3 visible. Bottom-right on
desktop, bottom-center on mobile.

### Modal

```typescript
interface ModalProps {
  open: boolean
  onClose: () => void
  title: string
  children: ReactNode
  footer?: ReactNode
}
```

Backdrop click closes. Escape key closes. Focus trapped inside.
Mobile: slides up from bottom (sheet style).

---

## API Fetch Layer (`lib/api.ts`)

Typed wrapper for BFF calls:

```typescript
const API_BASE = "/api/bff"

async function apiFetch<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers: { "Content-Type": "application/json", ...options?.headers },
  })
  if (!res.ok) {
    const body = await res.json().catch(() => ({}))
    throw new ApiError(res.status, body.detail || "Request failed")
  }
  return res.json()
}

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message)
  }
}

// Typed helpers
export const api = {
  stories: {
    list: (params: StoryListParams) => apiFetch<Story[]>(`/stories?${qs(params)}`),
    get: (id: number) => apiFetch<StoryDetail>(`/stories/${id}`),
    resonance: (id: number) => apiFetch<Resonance>(`/stories/${id}/resonance`),
  },
  // ... same pattern for users, briefings, keywords, sources, engagements
}
```

---

## React Query Configuration

```typescript
const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 2 * 60 * 1000,         // 2 min default
      retry: 2,
      refetchOnWindowFocus: true,
    },
    mutations: {
      onError: (err) => {
        if (err instanceof ApiError && err.status === 401) {
          signOut({ callbackUrl: "/login" })
        }
      },
    },
  },
})
```

---

## Navigation (AppShell)

**Desktop (>= 1024px):** left sidebar (280px) with nav links:
```
Dashboard
Stories
Briefings
Perception
Sources
Settings
```

Active link highlighted with `bg-brand-50 text-brand-700 border-l-2 border-brand-500`.

**Mobile (< 768px):** bottom nav bar with 5 icons:
```
[Dashboard] [Stories] [Briefings] [Perception] [Settings]
```

Sources accessible from Settings or hamburger menu.

---

## Docker Integration

`frontend/Dockerfile`:
```dockerfile
FROM node:20-alpine AS deps
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci

FROM node:20-alpine AS builder
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY . .
RUN npm run build

FROM node:20-alpine AS runner
WORKDIR /app
ENV NODE_ENV=production
RUN addgroup -g 1001 -S prism && adduser -S prism -u 1001
COPY --from=builder /app/.next/standalone ./
COPY --from=builder /app/.next/static ./.next/static
COPY --from=builder /app/public ./public
USER prism
EXPOSE 3000
CMD ["node", "server.js"]
```

Add to root `docker-compose.yml`:
```yaml
frontend:
  build: ./frontend
  ports:
    - "3000:3000"
  environment:
    - FASTAPI_URL=http://api:8000
    - NEXTAUTH_URL=http://localhost:3000
    - NEXTAUTH_SECRET=${NEXTAUTH_SECRET}
  depends_on:
    - api
```

Add to `docker-compose.prod.yml` with same pattern + health check on port 3000.

---

## CI Pipeline Updates

Add to `.github/workflows/ci.yml`:

```yaml
frontend:
  runs-on: ubuntu-latest
  defaults:
    run:
      working-directory: frontend
  steps:
    - uses: actions/checkout@v4
    - uses: actions/setup-node@v4
      with:
        node-version: 20
        cache: npm
        cache-dependency-path: frontend/package-lock.json
    - run: npm ci
    - run: npm run lint              # ESLint
    - run: npm run type-check        # tsc --noEmit
    - run: npm test                  # React Testing Library
    - run: npm run build             # Next.js build
    - run: npx playwright install --with-deps
    - run: npx playwright test       # E2E (against mocked API)
```

---

## Dependencies (`package.json`)

```json
{
  "dependencies": {
    "next": "^14.2",
    "react": "^18.3",
    "react-dom": "^18.3",
    "next-auth": "^4.24",
    "@tanstack/react-query": "^5.50",
    "recharts": "^2.12",
    "dompurify": "^3.1",
    "@tailwindcss/typography": "^0.5"
  },
  "devDependencies": {
    "typescript": "^5.5",
    "@types/react": "^18.3",
    "@types/dompurify": "^3.0",
    "tailwindcss": "^3.4",
    "postcss": "^8.4",
    "autoprefixer": "^10.4",
    "eslint": "^8.57",
    "eslint-config-next": "^14.2",
    "@testing-library/react": "^16.0",
    "@testing-library/jest-dom": "^6.4",
    "vitest": "^2.0",
    "jsdom": "^24.1",
    "msw": "^2.3",
    "playwright": "^1.45"
  }
}
```

---

## Environment Variables (`.env.local.example`)

```env
# NextAuth
NEXTAUTH_URL=http://localhost:3000
NEXTAUTH_SECRET=                       # openssl rand -base64 32

# Email (Resend SMTP for magic links)
EMAIL_SERVER_HOST=smtp.resend.com
EMAIL_SERVER_USER=resend
EMAIL_FROM=noreply@yourdomain.com
RESEND_API_KEY=re_...

# Backend
FASTAPI_URL=http://localhost:8000
```

---

## Acceptance Criteria

| # | Criterion | Verification |
|---|-----------|--------------|
| 1 | `npm run dev` starts Next.js on port 3000 | Visit http://localhost:3000, verify page loads |
| 2 | `npm run build` completes without errors | Run in CI, verify exit code 0 |
| 3 | TypeScript types compile with strict mode | `tsc --noEmit` exits 0 |
| 4 | ESLint passes with no warnings | `npm run lint` exits 0 |
| 5 | Docker build produces working image | `docker build`, `docker run`, verify port 3000 responds |
| 6 | Docker compose starts frontend + API together | `docker compose up`, verify both services healthy |
| 7 | Design tokens render correct colors | Visual test: render all bias labels, category pills, trust bars |
| 8 | Shared components render in all variants | Unit tests for Button, Modal, Toast, Skeleton |
| 9 | BFF proxy forwards requests with auth | Start both services, login, verify stories load |
| 10 | CI pipeline runs all checks | Push branch, verify GitHub Actions passes all steps |
| 11 | Mobile bottom nav renders at 375px | Resize viewport, verify 5 nav icons visible |
| 12 | Toast stacks and auto-dismisses | Trigger 3 toasts, verify stack + 4s dismiss |

---

## Implementation Order

This spec should be implemented first among all 01_xx specs:

1. `npm create next-app` with TypeScript + Tailwind + App Router
2. Add `tailwind.config.ts` with design tokens
3. Create `lib/types.ts` with all API types
4. Create `lib/api.ts` with fetch helpers
5. Create `components/ui/` (Button, Card, Skeleton, Toast, Modal)
6. Create `components/data-display/` (BiasLabel, CategoryPill, etc.)
7. Create `components/layout/` (AppShell, Sidebar, BottomNav)
8. Set up providers (Auth, Query, Toast)
9. Create Dockerfile and update docker-compose
10. Update CI pipeline
11. Verify end-to-end: `docker compose up` → login → dashboard skeleton renders
