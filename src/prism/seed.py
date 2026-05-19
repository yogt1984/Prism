"""Seed the source registry with known trusted outlets.

Idempotent — safe to run multiple times. Skips sources that already exist.
"""

import logging

from sqlalchemy import Engine
from sqlmodel import Session, select

from prism.models import BiasLabel, Source

logger = logging.getLogger(__name__)

# fmt: off
SEED_SOURCES = [
    # Wire services — highest trust, minimal bias
    ("Associated Press", "apnews.com", "https://rsshub.app/apnews/topics/apf-topnews", 0.95, BiasLabel.CENTER, "politics,world,finance"),
    ("Reuters", "reuters.com", "https://www.reutersagency.com/feed/", 0.95, BiasLabel.CENTER, "politics,world,finance"),
    ("AFP", "france24.com", "https://www.france24.com/en/rss", 0.90, BiasLabel.CENTER, "world,politics"),

    # Center / Centrist
    ("BBC News", "bbc.co.uk", "https://feeds.bbci.co.uk/news/rss.xml", 0.90, BiasLabel.CENTER, "politics,world,technology,science"),
    ("NPR", "npr.org", "https://feeds.npr.org/1001/rss.xml", 0.85, BiasLabel.CENTER, "politics,culture,science"),
    ("PBS NewsHour", "pbs.org", "https://www.pbs.org/newshour/feeds/rss/headlines", 0.85, BiasLabel.CENTER, "politics,world"),
    ("The Hill", "thehill.com", "https://thehill.com/feed/", 0.75, BiasLabel.CENTER, "politics"),

    # Center-left
    ("The New York Times", "nytimes.com", "https://rss.nytimes.com/services/xml/rss/nyt/HomePage.xml", 0.85, BiasLabel.CENTER_LEFT, "politics,world,culture,technology"),
    ("The Washington Post", "washingtonpost.com", "https://feeds.washingtonpost.com/rss/national", 0.85, BiasLabel.CENTER_LEFT, "politics,world"),
    ("The Guardian", "theguardian.com", "https://www.theguardian.com/world/rss", 0.85, BiasLabel.CENTER_LEFT, "politics,world,culture"),
    ("CNN", "cnn.com", "http://rss.cnn.com/rss/edition.rss", 0.70, BiasLabel.CENTER_LEFT, "politics,world,technology"),
    ("Politico", "politico.com", "https://www.politico.com/rss/politicopicks.xml", 0.80, BiasLabel.CENTER_LEFT, "politics"),

    # Center-right
    ("The Wall Street Journal", "wsj.com", "https://feeds.a.dj.com/rss/RSSWorldNews.xml", 0.85, BiasLabel.CENTER_RIGHT, "finance,politics,world"),
    ("The Economist", "economist.com", "https://www.economist.com/rss", 0.90, BiasLabel.CENTER_RIGHT, "finance,politics,world"),
    ("Financial Times", "ft.com", "https://www.ft.com/rss/home", 0.90, BiasLabel.CENTER_RIGHT, "finance,politics"),

    # Left
    ("The Atlantic", "theatlantic.com", "https://www.theatlantic.com/feed/all/", 0.80, BiasLabel.LEFT, "politics,culture"),
    ("Vox", "vox.com", "https://www.vox.com/rss/index.xml", 0.70, BiasLabel.LEFT, "politics,technology,science"),

    # Right
    ("Fox News", "foxnews.com", "https://moxie.foxnews.com/google-publisher/latest.xml", 0.60, BiasLabel.RIGHT, "politics,world"),
    ("National Review", "nationalreview.com", "https://www.nationalreview.com/feed/", 0.70, BiasLabel.RIGHT, "politics"),

    # Technology
    ("Ars Technica", "arstechnica.com", "https://feeds.arstechnica.com/arstechnica/index", 0.85, BiasLabel.CENTER, "technology,science"),
    ("TechCrunch", "techcrunch.com", "https://techcrunch.com/feed/", 0.75, BiasLabel.CENTER, "technology"),
    ("The Verge", "theverge.com", "https://www.theverge.com/rss/index.xml", 0.75, BiasLabel.CENTER_LEFT, "technology,culture"),
    ("Wired", "wired.com", "https://www.wired.com/feed/rss", 0.75, BiasLabel.CENTER_LEFT, "technology,science"),

    # Science
    ("Nature", "nature.com", "https://www.nature.com/nature.rss", 0.95, BiasLabel.CENTER, "science,health"),
    ("Science", "science.org", "https://www.science.org/rss/news_current.xml", 0.95, BiasLabel.CENTER, "science,health"),

    # Sports
    ("ESPN", "espn.com", "https://www.espn.com/espn/rss/news", 0.80, BiasLabel.CENTER, "sports"),

    # Finance
    ("Bloomberg", "bloomberg.com", "https://feeds.bloomberg.com/markets/news.rss", 0.85, BiasLabel.CENTER, "finance,technology"),
    ("CNBC", "cnbc.com", "https://www.cnbc.com/id/100003114/device/rss/rss.html", 0.75, BiasLabel.CENTER, "finance"),

    # International
    ("Al Jazeera", "aljazeera.com", "https://www.aljazeera.com/xml/rss/all.xml", 0.75, BiasLabel.CENTER_LEFT, "world,politics"),
    ("DW News", "dw.com", "https://rss.dw.com/rdf/rss-en-all", 0.80, BiasLabel.CENTER, "world,politics"),
]
# fmt: on


def seed_sources(engine: Engine) -> int:
    """Insert seed sources. Returns count of newly inserted sources."""
    inserted = 0
    with Session(engine) as session:
        for name, url, rss_url, trust, bias, categories in SEED_SOURCES:
            existing = session.exec(select(Source).where(Source.url == url)).first()
            if existing:
                continue
            source = Source(
                name=name,
                url=url,
                rss_url=rss_url,
                trust_score=trust,
                bias_label=bias,
                categories=categories,
                active=True,
            )
            session.add(source)
            inserted += 1
        session.commit()
    logger.info("Seeded %d new sources (%d already existed)",
                inserted, len(SEED_SOURCES) - inserted)
    return inserted
