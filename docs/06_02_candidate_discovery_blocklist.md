# 06_02 — Candidate Discovery & Domain Blocklist

**Parent:** 06 Source Auto-Discovery
**Depends on:** 06_01 (Source lifecycle fields exist)

---

## Objective

Extend D_AI's `run_discovery()` cycle to extract unknown domains from
Brave Search results, filter them against a blocklist, and create
`Source` rows with `status="candidate"`. Also implement the domain
blocklist file and its loading logic.

---

## Domain Blocklist

### File: `data/source_blocklist.txt`

```
# Domains excluded from auto-discovery (one per line)
# Social media and user-generated content
reddit.com
twitter.com
x.com
facebook.com
instagram.com
youtube.com
tiktok.com
linkedin.com
threads.net

# Blog platforms (too heterogeneous for source-level trust)
medium.com
substack.com
wordpress.com
blogspot.com
tumblr.com

# Reference / not news
wikipedia.org
wikimedia.org

# Aggregators (would create circular discovery)
news.google.com
news.bing.com
news.yahoo.com
flipboard.com
apple.news
```

### Loader: `src/prism/agents/blocklist.py` (new)

```python
"""Domain blocklist for source auto-discovery."""

import logging
from pathlib import Path

logger = logging.getLogger(__name__)

_BLOCKLIST_PATH = Path("data/source_blocklist.txt")
_blocklist: set[str] | None = None


def load_blocklist(path: Path | None = None) -> set[str]:
    """Load blocked domains from file. Cached after first load."""
    global _blocklist
    if _blocklist is not None and path is None:
        return _blocklist

    p = path or _BLOCKLIST_PATH
    domains: set[str] = set()

    if not p.exists():
        logger.warning("Blocklist file not found: %s", p)
        _blocklist = domains
        return domains

    for line in p.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        # Normalize: remove www. prefix, lowercase
        domain = line.lower().removeprefix("www.")
        domains.add(domain)

    _blocklist = domains
    logger.info("Loaded %d blocked domains", len(domains))
    return domains


def is_blocked(domain: str) -> bool:
    """Check if a domain is in the blocklist."""
    blocklist = load_blocklist()
    normalized = domain.lower().removeprefix("www.")
    # Check exact match and parent domain
    # e.g. "sports.yahoo.com" should match if "yahoo.com" is blocked
    parts = normalized.split(".")
    for i in range(len(parts) - 1):
        candidate = ".".join(parts[i:])
        if candidate in blocklist:
            return True
    return False


def reload_blocklist() -> set[str]:
    """Force reload from disk (after CLI edits)."""
    global _blocklist
    _blocklist = None
    return load_blocklist()
```

**Subdomain matching:** `sports.yahoo.com` matches `yahoo.com` in the
blocklist. This prevents discovery of subdomains of blocked platforms.

---

## D_AI Extension: Candidate Extraction

### Changes to `src/prism/agents/d_ai.py`

Add a new method `_extract_candidates()` called at the end of
`run_discovery()`:

```python
from prism.agents.blocklist import is_blocked
from prism.config import settings
from prism.models import SourceStatus


def _extract_candidates(
    self,
    brave_results: list[dict],
    engine: Engine | None = None,
) -> int:
    """Extract unknown domains from Brave results and create candidates.

    Returns count of new candidates created.
    """
    e = engine or get_engine()
    created = 0
    max_per_cycle = settings.source_candidate_max_per_cycle

    # Collect unique domains from results
    seen_domains: set[str] = set()
    for result in brave_results:
        url = result.get("url", "")
        if not url:
            continue
        domain = urlparse(url).netloc.removeprefix("www.").lower()
        if not domain or domain in seen_domains:
            continue
        seen_domains.add(domain)

    with Session(e) as session:
        # Load existing source domains for dedup
        existing_urls = {
            row for row in session.exec(select(Source.url)).all()
        }

        for domain in seen_domains:
            if created >= max_per_cycle:
                break

            # Skip if already registered
            if domain in existing_urls:
                # Increment sighting_count for existing candidates
                existing = session.exec(
                    select(Source).where(Source.url == domain)
                ).first()
                if existing and existing.status == SourceStatus.CANDIDATE:
                    existing.sighting_count += 1
                continue

            # Skip blocked domains
            if is_blocked(domain):
                continue

            # Infer category from the search query context
            categories = self._infer_categories(domain, brave_results)

            source = Source(
                name=domain,  # placeholder name, refined later
                url=domain,
                status=SourceStatus.CANDIDATE,
                trust_score=0.0,
                active=False,
                discovered_via="brave_search",
                sighting_count=1,
                categories=categories,
            )
            session.add(source)
            existing_urls.add(domain)
            created += 1

        session.commit()

    if created > 0:
        logger.info("Created %d candidate sources", created)
    return created


def _infer_categories(
    self, domain: str, results: list[dict],
) -> str:
    """Infer categories from the search queries that surfaced this domain.

    If domain appeared in results for "finance news" query, tag "finance".
    """
    categories: set[str] = set()
    category_keywords = {
        "finance": "finance",
        "technology": "technology",
        "politics": "politics",
        "sports": "sports",
        "science": "science",
        "health": "health",
        "culture": "culture",
        "world": "world",
    }
    for result in results:
        result_domain = urlparse(result.get("url", "")).netloc
        result_domain = result_domain.removeprefix("www.").lower()
        if result_domain != domain:
            continue
        title = result.get("title", "").lower()
        desc = result.get("description", "").lower()
        text = f"{title} {desc}"
        for keyword, cat in category_keywords.items():
            if keyword in text:
                categories.add(cat)
    return ",".join(sorted(categories)) if categories else ""
```

### Integration into `run_discovery()`

Add call after `store_cluster` loop, before the final log:

```python
def run_discovery(self, queries=None, engine=None):
    # ... existing code: search, fetch RSS, deduplicate, store ...

    # Extract candidate sources from Brave results
    brave_articles = [a for a in all_articles if a not in rss_articles]
    self._extract_candidates(brave_articles, engine)

    logger.info("Discovery cycle complete. ...")
```

Only Brave results are passed (not RSS), since RSS articles come from
already-registered sources.

---

## Sighting Count Tracking

Each discovery cycle increments `sighting_count` for existing candidates.
When a candidate reaches `sighting_count >= 3`, the probation pipeline
(06_03) picks it up. This prevents one-off domains from entering
probation.

---

## Acceptance Criteria

| # | Criterion | Verification |
|---|-----------|--------------|
| 1 | New domains create `Source(status="candidate")` | Run discovery, verify new rows |
| 2 | Max 5 candidates per cycle enforced | Feed 20 new domains, verify exactly 5 created |
| 3 | Blocked domains never create candidates | Include reddit.com in results, verify no Source |
| 4 | Subdomain matching works | Include `sports.yahoo.com`, verify blocked |
| 5 | Existing sources not duplicated | Run cycle twice with same results, verify no dups |
| 6 | `sighting_count` incremented for re-seen candidates | See domain in 2 cycles, verify count=2 |
| 7 | Candidate `trust_score=0.0`, `active=False` | Verify defaults on new candidate |
| 8 | `discovered_via="brave_search"` set | Verify field on new candidate |
| 9 | Blocklist loads from file | Verify `load_blocklist()` returns expected set |
| 10 | Blocklist comments and blank lines ignored | Add comments, verify not in set |
| 11 | Categories inferred from search context | Domain in "finance news" results tagged "finance" |

---

## Testing Strategy

### Blocklist Tests

```python
def test_load_blocklist(tmp_path):
    """Loads domains from file, ignoring comments."""
    f = tmp_path / "blocklist.txt"
    f.write_text("# comment\nreddit.com\n\ntwitter.com\n")
    domains = load_blocklist(f)
    assert domains == {"reddit.com", "twitter.com"}

def test_is_blocked_subdomain():
    """Subdomain of blocked domain is blocked."""
    assert is_blocked("sports.yahoo.com") == True
    assert is_blocked("bbc.co.uk") == False  # not in default list

def test_is_blocked_www_prefix():
    """www prefix is stripped."""
    assert is_blocked("www.reddit.com") == True
```

### Candidate Extraction Tests

```python
def test_extract_candidates_creates_sources(engine, populated_db):
    """New domains from Brave results create candidate sources."""
    d_ai = DiscoveryAgent()
    results = [{"url": "https://newsite.com/article/1", "title": "News"}]
    count = d_ai._extract_candidates(results, engine)
    assert count == 1
    with Session(engine) as session:
        src = session.exec(select(Source).where(Source.url == "newsite.com")).first()
        assert src is not None
        assert src.status == SourceStatus.CANDIDATE
        assert src.trust_score == 0.0
        assert src.active == False

def test_extract_candidates_respects_cap(engine, populated_db):
    """At most source_candidate_max_per_cycle candidates created."""
    d_ai = DiscoveryAgent()
    results = [{"url": f"https://site{i}.com/a", "title": "x"} for i in range(20)]
    count = d_ai._extract_candidates(results, engine)
    assert count == 5  # default cap

def test_extract_candidates_increments_sighting(engine, populated_db):
    """Existing candidate sighting_count incremented."""
    d_ai = DiscoveryAgent()
    results = [{"url": "https://newsite.com/a", "title": "x"}]
    d_ai._extract_candidates(results, engine)  # sighting_count=1
    d_ai._extract_candidates(results, engine)  # sighting_count=2
    with Session(engine) as session:
        src = session.exec(select(Source).where(Source.url == "newsite.com")).first()
        assert src.sighting_count == 2
```

---

## Files Changed

| File | Change |
|------|--------|
| `data/source_blocklist.txt` | New: domain blocklist |
| `src/prism/agents/blocklist.py` | New: blocklist loader + is_blocked |
| `src/prism/agents/d_ai.py` | Add _extract_candidates, _infer_categories |
| `tests/test_blocklist.py` | New: blocklist tests |
| `tests/test_discovery.py` | Add candidate extraction tests |
