# 06_03 — RSS Detection & Probation Pipeline

**Parent:** 06 Source Auto-Discovery
**Depends on:** 06_02 (candidates exist with sighting_count)

---

## Objective

Two mechanisms that advance candidates through the lifecycle:

1. **RSS detection** — for each candidate, attempt to discover an RSS
   feed URL. Sources with RSS feeds are more valuable (reliable polling).
2. **Probation promotion** — when a candidate reaches `sighting_count >= 3`,
   promote it to `status="probation"` so its articles participate in
   clustering and cross-validation.

---

## Part 1: RSS Feed Detection

### File: `src/prism/agents/rss_detect.py` (new)

```python
"""Attempt to discover RSS feed URLs for candidate sources."""

import logging
import re
from urllib.parse import urljoin

import httpx

from prism.config import settings

logger = logging.getLogger(__name__)

# Common RSS feed paths to probe
_COMMON_PATHS = [
    "/rss",
    "/feed",
    "/feed.xml",
    "/rss.xml",
    "/atom.xml",
    "/feeds/posts/default",
    "/index.xml",
]

_RSS_LINK_RE = re.compile(
    r'<link[^>]+type=["\']application/(rss|atom)\+xml["\'][^>]*href=["\']([^"\']+)["\']',
    re.IGNORECASE,
)


def detect_rss_feed(domain: str) -> str | None:
    """Try to find an RSS feed URL for a domain.

    Strategy:
    1. Fetch homepage HTML, parse <link rel="alternate"> tags
    2. Probe common feed paths (/rss, /feed, /feed.xml, etc.)

    Returns the feed URL or None if no feed found.
    """
    base_url = f"https://{domain}"
    timeout = settings.source_rss_detect_timeout

    client = httpx.Client(
        timeout=timeout,
        follow_redirects=True,
        headers={"User-Agent": "Prism/1.0 RSS Discovery"},
    )

    try:
        # Strategy 1: Parse homepage for <link> tags
        feed_url = _parse_homepage_links(client, base_url)
        if feed_url:
            return feed_url

        # Strategy 2: Probe common paths
        feed_url = _probe_common_paths(client, base_url)
        if feed_url:
            return feed_url

    except httpx.HTTPError:
        logger.debug("HTTP error detecting RSS for %s", domain)
    except Exception:
        logger.debug("Unexpected error detecting RSS for %s", domain, exc_info=True)
    finally:
        client.close()

    return None


def _parse_homepage_links(client: httpx.Client, base_url: str) -> str | None:
    """Fetch homepage and extract RSS/Atom link tags."""
    try:
        resp = client.get(base_url)
        if resp.status_code != 200:
            return None

        # Only parse first 50KB to avoid downloading huge pages
        html = resp.text[:50_000]
        matches = _RSS_LINK_RE.findall(html)
        if matches:
            href = matches[0][1]  # first match, href group
            return urljoin(base_url, href)
    except httpx.HTTPError:
        pass
    return None


def _probe_common_paths(client: httpx.Client, base_url: str) -> str | None:
    """Try common RSS paths and check for valid XML content."""
    for path in _COMMON_PATHS:
        url = urljoin(base_url, path)
        try:
            resp = client.get(url)
            if resp.status_code == 200 and _looks_like_feed(resp.text[:2000]):
                return url
        except httpx.HTTPError:
            continue
    return None


def _looks_like_feed(content: str) -> bool:
    """Quick heuristic: does this look like RSS/Atom XML?"""
    content_lower = content.lower().strip()
    return any(tag in content_lower for tag in [
        "<rss",
        "<feed",
        "<rdf:rdf",
        "<?xml",
    ]) and any(tag in content_lower for tag in [
        "<channel>",
        "<entry>",
        "<item>",
    ])
```

### Integration: Run RSS Detection for New Candidates

Add to D_AI's `_extract_candidates()`, after creating each candidate:

```python
from prism.agents.rss_detect import detect_rss_feed

# After session.add(source):
rss_url = detect_rss_feed(domain)
if rss_url:
    source.rss_url = rss_url
    logger.info("RSS feed found for %s: %s", domain, rss_url)
```

RSS detection is best-effort — if it times out or fails, the source
is still created (Brave Search can find articles without RSS).

---

## Part 2: Probation Promotion

### File: `src/prism/agents/source_lifecycle.py` (new)

```python
"""Source lifecycle management — probation promotion and evaluation."""

import logging
from datetime import UTC, datetime

from sqlalchemy import Engine
from sqlmodel import Session, select

from prism.config import settings
from prism.models import Source, SourceStatus

logger = logging.getLogger(__name__)


def promote_to_probation(engine: Engine) -> int:
    """Promote candidates with sufficient sightings to probation.

    Criteria: sighting_count >= 3 AND status == "candidate"

    Returns count of promoted sources.
    """
    promoted = 0
    with Session(engine) as session:
        candidates = session.exec(
            select(Source).where(
                Source.status == SourceStatus.CANDIDATE,
                Source.sighting_count >= 3,
            )
        ).all()

        for source in candidates:
            source.status = SourceStatus.PROBATION
            source.trust_score = 0.1
            source.active = True
            source.probation_start = datetime.now(UTC)
            promoted += 1
            logger.info(
                "Source '%s' (%s) promoted to probation",
                source.name, source.url,
            )

        session.commit()

    if promoted:
        logger.info("Promoted %d candidates to probation", promoted)
    return promoted
```

### Call from Discovery Cycle

Add to `run_discovery()` in `d_ai.py`, after `_extract_candidates()`:

```python
from prism.agents.source_lifecycle import promote_to_probation

# After _extract_candidates:
promote_to_probation(e)
```

This runs at the end of every discovery cycle, checking if any
candidates have accumulated enough sightings.

---

## Probation Behavior

Once a source is in probation (`status="probation"`, `active=True`,
`trust_score=0.1`):

1. **RSS polling:** if `rss_url` is set, D_AI's `fetch_rss_sources()`
   already picks it up (it queries `Source.active == True`).
2. **Brave results:** articles from this domain are stored normally by
   `_get_or_create_source()` and clustered.
3. **Low trust weight:** `trust_score=0.1` means this source has minimal
   influence on cluster quality scores and resonance calculations.
4. **Cross-validation:** handled in 06_04.

---

## Discovery Cycle Updated Flow

```
run_discovery()
  │
  ├── Search Brave (existing)
  ├── Fetch RSS (existing)
  ├── Deduplicate & store clusters (existing)
  │
  ├── _extract_candidates()      ← NEW (06_02)
  │     └── detect_rss_feed()    ← NEW (this spec)
  │
  └── promote_to_probation()     ← NEW (this spec)
```

---

## Acceptance Criteria

| # | Criterion | Verification |
|---|-----------|--------------|
| 1 | RSS detected for known news sites | `detect_rss_feed("bbc.co.uk")` returns feed URL |
| 2 | RSS detection respects timeout | Slow server → returns None within 5s |
| 3 | Homepage `<link>` tags parsed correctly | HTML with RSS link → URL extracted |
| 4 | Common path probing works | Site with `/feed.xml` → detected |
| 5 | Non-feed XML not matched | Site returning HTML at `/feed` → not matched |
| 6 | Candidate with 3 sightings promoted | Set sighting_count=3, run promote, verify status |
| 7 | Promoted source: `active=True`, `trust_score=0.1` | Verify fields |
| 8 | `probation_start` timestamp set | Verify not None after promotion |
| 9 | Candidate with <3 sightings not promoted | sighting_count=2, verify still candidate |
| 10 | Already-probation sources not re-promoted | Run promote twice, verify no change |
| 11 | RSS URL stored on candidate Source | New candidate with feed → rss_url populated |

---

## Testing Strategy

### RSS Detection Tests (with mocked HTTP)

```python
def test_detect_rss_from_link_tag(httpx_mock):
    """Detects RSS from homepage <link> tag."""
    httpx_mock.add_response(
        url="https://example.com",
        html='<html><head><link rel="alternate" type="application/rss+xml" href="/feed.xml"></head></html>',
    )
    assert detect_rss_feed("example.com") == "https://example.com/feed.xml"

def test_detect_rss_from_common_path(httpx_mock):
    """Detects RSS from common /rss path."""
    httpx_mock.add_response(url="https://example.com", status_code=404)
    httpx_mock.add_response(
        url="https://example.com/rss",
        text='<?xml version="1.0"?><rss><channel><item></item></channel></rss>',
    )
    assert detect_rss_feed("example.com") == "https://example.com/rss"

def test_detect_rss_none_when_not_found(httpx_mock):
    """Returns None when no RSS feed found."""
    httpx_mock.add_response(url="https://nofeed.com", text="<html>No feed</html>")
    for path in _COMMON_PATHS:
        httpx_mock.add_response(url=f"https://nofeed.com{path}", status_code=404)
    assert detect_rss_feed("nofeed.com") is None

def test_looks_like_feed():
    """Heuristic correctly identifies feed XML."""
    assert _looks_like_feed('<?xml version="1.0"?><rss><channel><item>')
    assert _looks_like_feed('<feed xmlns="..."><entry>')
    assert not _looks_like_feed('<html><body>Not a feed</body></html>')
```

### Probation Promotion Tests

```python
def test_promote_to_probation(engine):
    """Candidate with 3 sightings is promoted."""
    with Session(engine) as session:
        src = Source(name="Test", url="test.com", status=SourceStatus.CANDIDATE, sighting_count=3)
        session.add(src)
        session.commit()
    count = promote_to_probation(engine)
    assert count == 1
    with Session(engine) as session:
        src = session.exec(select(Source).where(Source.url == "test.com")).first()
        assert src.status == SourceStatus.PROBATION
        assert src.active == True
        assert src.trust_score == 0.1
        assert src.probation_start is not None

def test_promote_skips_low_sighting(engine):
    """Candidate with <3 sightings not promoted."""
    with Session(engine) as session:
        src = Source(name="Test", url="test.com", status=SourceStatus.CANDIDATE, sighting_count=2)
        session.add(src)
        session.commit()
    count = promote_to_probation(engine)
    assert count == 0
```

---

## Files Changed

| File | Change |
|------|--------|
| `src/prism/agents/rss_detect.py` | New: RSS feed detection |
| `src/prism/agents/source_lifecycle.py` | New: promote_to_probation |
| `src/prism/agents/d_ai.py` | Call RSS detection + probation promotion in run_discovery |
| `tests/test_rss_detect.py` | New: RSS detection tests |
| `tests/test_source_lifecycle.py` | New: probation promotion tests |
