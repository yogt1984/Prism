"""D_AI — Discovery Agent.

Uses Brave Search API and RSS feeds to discover news stories,
clusters them by event, and maintains a source trust registry.
"""

import logging
import re
from calendar import timegm
from datetime import UTC, datetime, timedelta
from time import struct_time
from urllib.parse import urlparse

import feedparser
import httpx
from sqlalchemy import Engine
from sqlmodel import Session, select

from prism.alerts import AlertLevel, send_alert
from prism.config import settings
from prism.db import get_engine, get_session
from prism.metrics import timed_cycle
from prism.models import Article, Source, StoryCluster, StoryStatus
from prism.retry import retry_on_transient

logger = logging.getLogger(__name__)

BRAVE_NEWS_URL = "https://api.search.brave.com/res/v1/news/search"


class DiscoveryAgent:
    def __init__(self) -> None:
        self.http = httpx.Client(
            headers={"X-Subscription-Token": settings.brave_api_key},
            timeout=30.0,
        )

    @retry_on_transient(max_retries=3, base_delay=2.0)
    def search_brave(self, query: str, count: int = 20) -> list[dict]:
        """Search Brave News API for recent articles on a topic."""
        resp = self.http.get(
            BRAVE_NEWS_URL,
            params={"q": query, "count": count, "freshness": "pd"},
        )
        resp.raise_for_status()
        data = resp.json()
        return data.get("results", [])

    def fetch_rss_sources(self, engine: Engine | None = None) -> list[dict]:
        """Fetch latest articles from RSS feeds of active, trusted sources."""
        e = engine or get_engine()
        articles: list[dict] = []

        with Session(e) as session:
            sources = session.exec(
                select(Source).where(
                    Source.active == True,  # noqa: E712
                    Source.rss_url != "",
                )
            ).all()

            # Collect existing article URLs for dedup
            existing_urls: set[str] = set()
            for row in session.exec(select(Article.url)).all():
                existing_urls.add(row)

            for source in sources:
                try:
                    feed = feedparser.parse(source.rss_url)
                    if feed.bozo:
                        logger.warning(
                            "Malformed/bozo RSS feed for %s (%s)", source.name, source.rss_url
                        )
                        continue

                    for entry in feed.entries:
                        url = getattr(entry, "link", "")
                        if url in existing_urls:
                            continue

                        published_at = None
                        pp = getattr(entry, "published_parsed", None)
                        if isinstance(pp, struct_time):
                            published_at = datetime.fromtimestamp(timegm(pp), tz=UTC).isoformat()

                        articles.append({
                            "title": getattr(entry, "title", ""),
                            "url": url,
                            "description": entry.get("summary", ""),
                            "source": source.name,
                            "published_at": published_at,
                        })
                        existing_urls.add(url)

                except Exception:
                    logger.exception("Failed to fetch RSS for %s", source.name)

        logger.info("RSS fetch complete: %d new articles from %d sources",
                     len(articles), len(sources) if sources else 0)
        return articles

    # --- Deduplication ---

    @staticmethod
    def _jaccard(a: str, b: str) -> float:
        """Word-set Jaccard similarity between two strings."""
        words_a = set(a.lower().split())
        words_b = set(b.lower().split())
        if not words_a or not words_b:
            return 0.0
        return len(words_a & words_b) / len(words_a | words_b)

    @staticmethod
    def _tfidf_similarity(a: str, b: str) -> float:
        """TF-IDF cosine similarity between two strings.

        Returns 0.0 if sklearn is unavailable or inputs are empty.
        """
        if not a or not b:
            return 0.0
        try:
            from sklearn.feature_extraction.text import TfidfVectorizer
            from sklearn.metrics.pairwise import cosine_similarity
        except ImportError:
            return 0.0
        try:
            vectorizer = TfidfVectorizer()
            matrix = vectorizer.fit_transform([a, b])
            return float(cosine_similarity(matrix[0:1], matrix[1:2])[0, 0])
        except ValueError:
            # e.g. empty vocabulary after stop-word removal
            return 0.0

    # Regex for capitalized multi-word entities (e.g. "Federal Reserve", "Elon Musk")
    _ENTITY_RE = re.compile(r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\b")

    @staticmethod
    def _entity_overlap(a: str, b: str) -> float:
        """Jaccard similarity on extracted named entities.

        Extracts capitalized word sequences (e.g. "Federal Reserve",
        "Elon Musk") via regex — no spaCy dependency.
        """
        if not a or not b:
            return 0.0
        entities_a = set(DiscoveryAgent._ENTITY_RE.findall(a))
        entities_b = set(DiscoveryAgent._ENTITY_RE.findall(b))
        if not entities_a or not entities_b:
            return 0.0
        return len(entities_a & entities_b) / len(entities_a | entities_b)

    def _combined_similarity(self, a: str, b: str) -> float:
        """Weighted combination of Jaccard, TF-IDF, and entity overlap."""
        jaccard = self._jaccard(a, b)
        tfidf = self._tfidf_similarity(a, b)
        entity = self._entity_overlap(a, b)
        return 0.5 * jaccard + 0.3 * tfidf + 0.2 * entity

    def deduplicate_articles(
        self, articles: list[dict], threshold: float = 0.6,
    ) -> list[list[dict]]:
        """Group articles covering the same story.

        Primary: Jaccard similarity >= threshold.
        Fallback: when Jaccard is in [0.4, threshold), use combined score
        (0.5*jaccard + 0.3*tfidf + 0.2*entity) with threshold 0.4.
        """
        combined_threshold = 0.4
        clusters: list[list[dict]] = []
        for article in articles:
            title = article.get("title", "")
            placed = False
            for cluster in clusters:
                rep_title = cluster[0].get("title", "")
                jaccard = self._jaccard(title, rep_title)
                if jaccard >= threshold:
                    cluster.append(article)
                    placed = True
                    break
                if jaccard >= 0.4:
                    combined = self._combined_similarity(title, rep_title)
                    if combined >= combined_threshold:
                        cluster.append(article)
                        placed = True
                        break
            if not placed:
                clusters.append([article])
        return clusters

    # --- Storage ---

    def _find_existing_cluster(
        self, session: Session, title: str,
    ) -> StoryCluster | None:
        """Check if a matching cluster from the last 24h already exists.

        Compares against both cluster headlines AND article titles so that
        merges still work after A_AI rewrites the headline.
        """
        cutoff = datetime.now(UTC) - timedelta(hours=24)
        recent = session.exec(
            select(StoryCluster).where(StoryCluster.first_seen >= cutoff)
        ).all()
        if not recent:
            return None

        # Bulk-load article titles for all recent clusters
        cluster_ids = [c.id for c in recent]
        art_rows = session.exec(
            select(Article.cluster_id, Article.title).where(
                Article.cluster_id.in_(cluster_ids),  # type: ignore[union-attr]
            )
        ).all()
        titles_by_cluster: dict[int, list[str]] = {}
        for cid, art_title in art_rows:
            titles_by_cluster.setdefault(cid, []).append(art_title)

        for cluster in recent:
            if self._jaccard(title, cluster.headline) >= 0.6:
                return cluster
            for art_title in titles_by_cluster.get(cluster.id, []):
                if self._jaccard(title, art_title) >= 0.6:
                    return cluster
        return None

    def store_cluster(
        self, articles: list[dict], engine: Engine | None = None,
    ) -> StoryCluster | None:
        """Store a story cluster and its articles, merging into existing clusters."""
        if not articles:
            return None

        e = engine or get_engine()
        with Session(e) as session:
            title = articles[0].get("title", "")
            cluster = self._find_existing_cluster(session, title)

            if cluster:
                cluster.article_count += len(articles)
                cluster.last_updated = datetime.now(UTC)
            else:
                cluster = StoryCluster(
                    headline=title,
                    article_count=len(articles),
                    status=StoryStatus.RAW,
                )
                session.add(cluster)
                session.commit()
                session.refresh(cluster)

            for raw in articles:
                url = raw.get("url", "")
                existing = session.exec(select(Article).where(Article.url == url)).first()
                if existing:
                    continue

                source = self._get_or_create_source(session, raw, e)

                pub_raw = raw.get("published_at")
                if isinstance(pub_raw, str):
                    pub_at = datetime.fromisoformat(pub_raw)
                elif isinstance(pub_raw, datetime):
                    pub_at = pub_raw
                else:
                    pub_at = None

                article = Article(
                    cluster_id=cluster.id,
                    source_id=source.id,  # type: ignore[arg-type]
                    title=raw.get("title", ""),
                    url=url,
                    snippet=raw.get("description", ""),
                    published_at=pub_at,
                )
                session.add(article)

            session.commit()
            session.refresh(cluster)
            return cluster

    def _get_or_create_source(
        self, session: Session, raw: dict, engine: Engine | None = None,
    ) -> Source:
        """Find or create a source entry from article metadata."""
        url = raw.get("url", "")
        domain = urlparse(url).netloc.removeprefix("www.")

        existing = session.exec(select(Source).where(Source.url == domain)).first()
        if existing:
            return existing

        source = Source(
            name=raw.get("source", domain),
            url=domain,
        )
        session.add(source)
        session.commit()
        session.refresh(source)
        return source

    # --- Brave date parsing ---

    @staticmethod
    def _parse_brave_age(age_str: str) -> datetime | None:
        """Parse Brave API 'age' field (e.g. '5 hours ago') to a UTC datetime."""
        import re

        m = re.match(r"(\d+)\s+(minute|hour|day|week|month)s?\s+ago", age_str.strip())
        if not m:
            return None
        value, unit = int(m.group(1)), m.group(2)
        deltas = {
            "minute": timedelta(minutes=value),
            "hour": timedelta(hours=value),
            "day": timedelta(days=value),
            "week": timedelta(weeks=value),
            "month": timedelta(days=value * 30),
        }
        return datetime.now(UTC) - deltas[unit]

    def _normalize_brave_results(self, results: list[dict]) -> list[dict]:
        """Normalize Brave results: extract source from meta_url, parse age."""
        for r in results:
            # Map source name from meta_url.hostname when missing
            if not r.get("source"):
                hostname = (r.get("meta_url") or {}).get("hostname", "")
                if hostname:
                    r["source"] = hostname.removeprefix("www.")

            if "published_at" not in r or r["published_at"] is None:
                age = r.get("age", "")
                if age:
                    dt = self._parse_brave_age(age)
                    if dt:
                        r["published_at"] = dt.isoformat()
        return results

    # --- Full Cycle ---

    @timed_cycle("discovery")
    def run_discovery(
        self,
        queries: list[str] | None = None,
        engine: Engine | None = None,
    ) -> None:
        """Run one discovery cycle across configured topics."""
        if queries is None:
            queries = [
                "latest news", "finance news", "technology news",
                "politics news", "sports news", "science news",
            ]

        all_articles: list[dict] = []
        for query in queries:
            try:
                results = self._normalize_brave_results(self.search_brave(query, count=10))
                all_articles.extend(results)
                logger.info("Brave search '%s': %d results", query, len(results))
            except Exception:
                logger.exception("Failed to search Brave for '%s'", query)

        rss_articles = self.fetch_rss_sources(engine)
        all_articles.extend(rss_articles)

        clusters = self.deduplicate_articles(all_articles)
        clusters.sort(key=len, reverse=True)
        max_stories = settings.max_stories_per_cycle
        if len(clusters) > max_stories:
            logger.info("Capping clusters from %d to %d", len(clusters), max_stories)
            clusters = clusters[:max_stories]

        stored = 0
        for cluster_articles in clusters:
            cluster = self.store_cluster(cluster_articles, engine)
            if cluster:
                stored += 1

        if not all_articles:
            send_alert(
                "Discovery cycle returned zero articles from all sources",
                level=AlertLevel.WARNING,
            )
        elif stored == 0:
            send_alert(
                f"Discovery cycle found {len(all_articles)} articles but stored 0 new clusters",
                level=AlertLevel.WARNING,
            )

        logger.info(
            "Discovery cycle complete. Stored %d clusters from %d articles.",
            stored, len(all_articles),
        )

    def get_trusted_sources(self, min_trust: float | None = None) -> list[Source]:
        """Retrieve sources above the trust threshold."""
        threshold = min_trust or settings.min_source_trust_score
        with get_session() as session:
            stmt = select(Source).where(
                Source.active == True,  # noqa: E712
                Source.trust_score >= threshold,
            )
            return list(session.exec(stmt).all())
