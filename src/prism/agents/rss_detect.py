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
