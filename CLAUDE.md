# Prism — AI-Curated Multi-Perspective News Briefings

## Mission

Deliver personalized, multi-perspective news briefings that make bias visible rather than hiding it.

**Motto:** "Humans cannot be objective — neither can AI. We make the bias transparent."

## What This Is

A **news curation platform** (not a journalism company) powered entirely by AI agents.
We aggregate from verified sources, summarize with full attribution, and present
multiple perspectives on every story. We never present AI-written text as original reporting.

## Architecture — Agent Roles

### D_AI (Discovery Agent)
- Uses Brave Search API to discover and monitor trusted news sources
- Maintains a curated source registry with trust scores and bias labels
- Crawls source feeds on schedule, deduplicates stories across outlets
- Outputs: raw story clusters (same event covered by multiple sources)

### A_AI (Analysis Agent)
- Takes story clusters from D_AI
- Uses Claude to: summarize each story, extract key facts, identify perspective/framing differences
- Tags stories by category: finance, politics, sports, technology, culture, etc.
- Detects sentiment and political leaning per source on each story
- Outputs: structured story objects with multi-perspective summaries

### P_AI (Personalization Agent)
- Manages user profiles (interests, depth preferences, reading history)
- Ranks and filters stories per user based on their interest vector
- Controls briefing length and format (quick digest vs deep dive)
- Learns from engagement signals (opens, read-time, saves, skips)
- Outputs: personalized briefing per user

### W_AI (Writer Agent)
- Takes personalized story selections from P_AI
- Generates the final briefing in the user's preferred format:
  - Email newsletter (HTML)
  - Web feed (API/JSON)
  - Audio briefing script (for TTS delivery)
- Every claim links back to its original source — no orphaned statements
- Applies consistent editorial voice without editorializing facts

## Key Constraints

- **Always attribute.** Every fact, quote, or claim must link to its source. No exceptions.
- **Never fabricate.** If Claude can't verify a claim from the source material, it doesn't appear in the briefing.
- **Bias is shown, not hidden.** When sources disagree, present both framings explicitly.
- **No original reporting.** We curate and summarize — we don't break news.
- **Source trust is earned.** New sources start with low trust scores and must be validated before inclusion.

## Data Flow

```
D_AI (discovery) --> raw story clusters --> A_AI (analysis) --> structured stories
                                                                      |
                                                              P_AI (personalization)
                                                                      |
                                                              W_AI (writer) --> briefings
                                                                      |
                                                              user engagement --> P_AI (feedback loop)
```

## Revenue Model

- **Freemium subscription:**
  - Free tier: 1 daily briefing, 3 topics, email only
  - Pro ($7/mo): unlimited topics, audio briefings, deep dives, API access
- **No ads.** Ad-funded news creates perverse incentives. Subscriptions align us with readers.

## Development Principles

- Conventional commits: feat:, fix:, docs:, refactor:
- Never implement directly on main — use task branches
- Minimal diffs, existing code style
- Each agent is an independent module communicating via message queue
- Prefer running single tests over full suite
- Include verification steps for every behavior change
