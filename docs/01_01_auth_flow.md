# 01_01 — Authentication Flow

**Parent:** 01 Web Frontend
**Must complete before:** all other 01_xx specs (every page depends on auth)

---

## Objective

Implement passwordless authentication using email magic links. Bridge
browser-based sessions to the backend's `X-API-Key` auth model so the
frontend can call all protected endpoints transparently.

---

## Auth Architecture

```
┌─────────────┐       ┌──────────────────────┐       ┌──────────────────┐
│   Browser    │       │   Next.js (BFF)      │       │   FastAPI API    │
│              │       │                      │       │                  │
│ 1. Enter     │──────>│ 2. POST /users       │──────>│ 3. register_user │
│    email     │       │    (signup only)      │       │    → User row    │
│              │       │                      │       │                  │
│ 4. Click     │──────>│ 5. NextAuth verify   │       │                  │
│    magic     │       │    callback          │       │                  │
│    link      │       │                      │       │                  │
│              │       │ 6. Create session    │       │                  │
│              │       │    (JWT httpOnly)     │       │                  │
│              │<──────│    + store api_key    │       │                  │
│              │       │    in encrypted       │       │                  │
│ 7. App calls │──────>│    session cookie     │       │                  │
│    /api/bff/ │       │                      │       │                  │
│    stories   │       │ 8. Read api_key from │       │                  │
│              │       │    session, attach    │──────>│ 9. X-API-Key     │
│              │       │    X-API-Key header   │       │    auth check    │
│              │<──────│                      │<──────│    → data        │
└─────────────┘       └──────────────────────┘       └──────────────────┘
```

---

## Implementation Tasks

### 1. NextAuth.js Configuration

File: `frontend/app/api/auth/[...nextauth]/route.ts`

```typescript
import NextAuth from "next-auth"
import EmailProvider from "next-auth/providers/email"

export const authOptions = {
  providers: [
    EmailProvider({
      server: {
        host: process.env.EMAIL_SERVER_HOST,   // e.g. smtp.resend.com
        port: 465,
        auth: {
          user: process.env.EMAIL_SERVER_USER,  // "resend"
          pass: process.env.RESEND_API_KEY,
        },
      },
      from: process.env.EMAIL_FROM,            // noreply@yourdomain.com
    }),
  ],
  session: { strategy: "jwt", maxAge: 30 * 24 * 60 * 60 },  // 30 days
  callbacks: { signIn, jwt, session },         // defined below
  pages: {
    signIn: "/login",
    newUser: "/signup",
    verifyRequest: "/check-email",
    error: "/auth-error",
  },
}
```

### 2. Signup Flow

**Route:** `/signup`

**Component tree:**
```
<SignupPage>
  <SignupForm>
    <EmailInput />                    // validated: regex ^[^@\s]+@[^@\s]+\.[^@\s]+$
    <InterestGrid>                    // 8 checkboxes, one per Category
      <InterestChip category />       // toggleable pill for each
    </InterestGrid>
    <SubmitButton />                  // "Create account"
  </SignupForm>
  <LoginLink />                       // "Already have an account? Log in"
</SignupPage>
```

**Sequence:**

1. User enters email + selects interests (at least 1 required)
2. Client validates email format locally
3. Call BFF: `POST /api/bff/signup`
   - BFF calls FastAPI: `POST /users {email, interests: "finance,technology"}`
   - Response: `UserOut {id, email, interests, is_pro: false, ...}`
   - On 422 (duplicate email): show "Account exists — log in instead"
4. BFF triggers NextAuth `signIn("email", {email})` to send magic link
5. Redirect to `/check-email`

**API call — BFF signup handler:**

File: `frontend/app/api/bff/signup/route.ts`
```typescript
// Request from client
{ email: string, interests: string[] }

// BFF transforms to FastAPI format
POST ${FASTAPI_URL}/users
Body: { email, interests: interests.join(","), briefing_depth: 10 }
Headers: { "Content-Type": "application/json" }

// FastAPI response
201: { id, email, name, interests, preferred_format, briefing_depth, is_pro, created_at }
422: { detail: "..." }  // invalid email, bad interest, duplicate
```

### 3. Login Flow

**Route:** `/login`

**Component tree:**
```
<LoginPage>
  <LoginForm>
    <EmailInput />
    <SubmitButton />                  // "Send magic link"
  </LoginForm>
  <SignupLink />                      // "New here? Create account"
</LoginPage>
```

**Sequence:**

1. User enters email
2. Call NextAuth: `signIn("email", {email, callbackUrl: "/dashboard"})`
3. NextAuth sends magic link via Resend SMTP
4. Redirect to `/check-email`
5. User clicks link → NextAuth verifies token → `signIn` callback fires

### 4. Check-Email Confirmation

**Route:** `/check-email`

**Component tree:**
```
<CheckEmailPage>
  <MailIcon />
  <Heading text="Check your inbox" />
  <Text text="We sent a magic link to {email}. Click it to sign in." />
  <ResendButton />                    // "Didn't get it? Resend" (60s cooldown)
</CheckEmailPage>
```

No API calls. Static page. Email passed via URL query param from NextAuth.

### 5. NextAuth Callbacks

**`signIn` callback** — maps email to Prism user:

```typescript
async signIn({ user, account }) {
  // Look up user in FastAPI by email
  const res = await fetch(`${FASTAPI_URL}/users?email=${user.email}`)
  if (res.status === 404) return false  // unknown email → block sign-in
  return true
}
```

**`jwt` callback** — embed Prism user data in JWT:

```typescript
async jwt({ token, user, trigger }) {
  if (trigger === "signIn") {
    // Fetch user from FastAPI
    const prismUser = await fetchUserByEmail(token.email)
    token.userId = prismUser.id
    token.apiKey = prismUser.api_key     // stored encrypted in JWT
    token.isPro = prismUser.is_pro
    token.interests = prismUser.interests
  }
  return token
}
```

**`session` callback** — expose safe fields to client:

```typescript
async session({ session, token }) {
  session.user.id = token.userId
  session.user.isPro = token.isPro
  session.user.interests = token.interests
  // api_key stays in token only — NEVER exposed to browser
  return session
}
```

### 6. BFF Proxy Layer

All authenticated frontend API calls go through BFF routes that inject
the API key from the server-side session.

File: `frontend/app/api/bff/[...path]/route.ts`

```typescript
async function proxyToFastAPI(request: NextRequest) {
  const session = await getServerSession(authOptions)
  if (!session) return NextResponse.json({ error: "Unauthorized" }, { status: 401 })

  const token = await getToken({ req: request })
  const apiKey = token.apiKey  // from JWT, never sent to browser

  const path = request.nextUrl.pathname.replace("/api/bff/", "")
  const res = await fetch(`${FASTAPI_URL}/${path}`, {
    method: request.method,
    headers: {
      "Content-Type": "application/json",
      "X-API-Key": apiKey,
    },
    body: ["GET", "HEAD"].includes(request.method) ? undefined : await request.text(),
  })

  return NextResponse.json(await res.json(), { status: res.status })
}

export { proxyToFastAPI as GET, proxyToFastAPI as POST, proxyToFastAPI as PATCH }
```

**URL mapping:**
| Frontend calls | BFF proxies to |
|----------------|----------------|
| `GET /api/bff/stories` | `GET /stories` with X-API-Key |
| `GET /api/bff/users/5/briefings` | `GET /users/5/briefings` with X-API-Key |
| `POST /api/bff/engagements` | `POST /engagements` with X-API-Key |
| `PATCH /api/bff/users/5` | `PATCH /users/5` with X-API-Key |

### 7. Route Protection (Middleware)

File: `frontend/middleware.ts`

```typescript
import { withAuth } from "next-auth/middleware"

export default withAuth({
  pages: { signIn: "/login" },
})

export const config = {
  // Protect all routes except public ones
  matcher: [
    "/dashboard/:path*",
    "/stories/:path*",
    "/briefings/:path*",
    "/perception/:path*",
    "/settings/:path*",
    "/sources/:path*",
    "/api/bff/:path*",
  ],
}
```

**Public routes (no auth):** `/`, `/login`, `/signup`, `/check-email`, `/auth-error`

### 8. Auth Error Page

**Route:** `/auth-error`

**Error states:**

| Error code | Message | Action |
|------------|---------|--------|
| `EmailSignin` | "Could not send magic link" | "Try again" button |
| `Verification` | "Link expired or already used" | "Request new link" button |
| `AccessDenied` | "No account found for this email" | "Create account" link |
| `Default` | "Something went wrong" | "Back to login" link |

---

## State Management

**Session state** via `useSession()` hook (NextAuth):
```typescript
const { data: session, status } = useSession()
// status: "loading" | "authenticated" | "unauthenticated"
// session.user: { id, email, isPro, interests }
```

**No global auth store needed.** NextAuth manages JWT refresh automatically.

---

## UI States

### Loading State
- Skeleton placeholders on all protected pages while `status === "loading"`
- Login/signup buttons disabled during submission with spinner

### Error States
| Scenario | Display |
|----------|---------|
| Invalid email format | Inline red text below input: "Enter a valid email" |
| Duplicate email (signup) | Inline: "Account exists — log in instead" + link |
| Magic link expired | `/auth-error` page with "Request new link" button |
| API unreachable | Toast: "Service temporarily unavailable" |
| Session expired | Auto-redirect to `/login` via middleware |

### Empty States
- N/A for auth flow (no data listing)

---

## Mobile Breakpoints

| Breakpoint | Layout |
|------------|--------|
| >= 768px (md) | Centered card (max-w-md), interest grid 4 columns |
| < 768px | Full-width form, interest grid 2 columns, larger touch targets (48px) |

---

## Security Requirements

- **JWT in httpOnly cookie only** — never `localStorage`
- **API key never reaches the browser** — stays in server-side JWT token
- **CSRF protection** — NextAuth includes CSRF token by default
- **Magic link tokens** — single-use, expire in 24 hours
- **Rate limit** on magic link sends: max 3 per email per hour (NextAuth config)
- **Email normalization** — lowercase + trim before lookup

---

## Environment Variables (Frontend)

```env
NEXTAUTH_URL=http://localhost:3000
NEXTAUTH_SECRET=<random-32-bytes>      # openssl rand -base64 32
EMAIL_SERVER_HOST=smtp.resend.com
EMAIL_SERVER_USER=resend
EMAIL_FROM=noreply@yourdomain.com
RESEND_API_KEY=re_...                  # shared with backend
FASTAPI_URL=http://localhost:8000      # backend, internal only
```

---

## Acceptance Criteria

| # | Criterion | Verification |
|---|-----------|--------------|
| 1 | Signup creates user in FastAPI and sends magic link | Submit form, check DB for new User row, check inbox |
| 2 | Magic link click establishes authenticated session | Click link, verify `useSession()` returns `authenticated` |
| 3 | Session persists across page reloads | Reload `/dashboard`, verify no redirect to `/login` |
| 4 | Session expires after 30 days | Set short maxAge (60s) in test, wait, verify redirect |
| 5 | Protected routes redirect unauthenticated users to /login | Visit `/dashboard` logged out, verify redirect |
| 6 | BFF proxy attaches X-API-Key from session | Inspect FastAPI access log, verify header present |
| 7 | API key never appears in browser DevTools | Check Network tab, cookies, localStorage — absent |
| 8 | Duplicate signup shows helpful error | Try same email twice, verify inline message |
| 9 | Expired magic link shows error page with retry | Use link after 24h, verify `/auth-error` renders |
| 10 | Login with unknown email is rejected | Enter non-existent email, verify error message |
| 11 | Interest selection persists after signup + login | Signup with 3 interests, login, check `/settings` |
| 12 | CSRF token is included in auth requests | Inspect form submission headers |

---

## Testing Strategy

- **Unit:** test NextAuth callbacks (signIn, jwt, session) with mocked FastAPI
- **Unit:** test BFF proxy route with mocked session and mocked fetch
- **E2E (Playwright):** full signup → check-email → magic-link → dashboard flow
  - Use Mailhog or similar for local email capture in CI
- **Security:** verify httpOnly flag on session cookie, no api_key in response
