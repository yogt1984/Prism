"""T1.5: Seed trusted sources."""

from pathlib import Path

import pytest
from sqlmodel import Session, select

from prism.db import init_db
from prism.models import BiasLabel, Source
from prism.seed import SEED_SOURCES, seed_sources


@pytest.fixture()
def db_engine(tmp_path: Path):
    url = f"sqlite:///{tmp_path / 'test.db'}"
    engine = init_db(url)
    yield engine
    engine.dispose()


def test_seed_sources_creates_rows(db_engine):
    count = seed_sources(db_engine)
    assert count >= 20

    with Session(db_engine) as s:
        sources = s.exec(select(Source)).all()
        assert len(sources) >= 20


def test_seed_sources_idempotent(db_engine):
    first = seed_sources(db_engine)
    second = seed_sources(db_engine)
    assert first >= 20
    assert second == 0  # no new inserts

    with Session(db_engine) as s:
        sources = s.exec(select(Source)).all()
        assert len(sources) == first


def test_seeded_sources_have_rss(db_engine):
    seed_sources(db_engine)
    with Session(db_engine) as s:
        sources = s.exec(select(Source)).all()
        for source in sources:
            assert source.rss_url != "", f"{source.name} missing rss_url"


def test_seed_covers_bias_spectrum(db_engine):
    seed_sources(db_engine)
    with Session(db_engine) as s:
        sources = s.exec(select(Source)).all()
        labels = {source.bias_label for source in sources}
        # Must have at least left, center, right representation
        assert BiasLabel.LEFT in labels
        assert BiasLabel.CENTER in labels
        assert BiasLabel.RIGHT in labels
        assert BiasLabel.CENTER_LEFT in labels
        assert BiasLabel.CENTER_RIGHT in labels


def test_seed_data_integrity():
    """Verify the seed data list itself is well-formed."""
    urls = set()
    for name, url, rss_url, trust, bias, categories in SEED_SOURCES:
        assert name, "Empty source name"
        assert url, "Empty URL"
        assert rss_url, f"{name} missing RSS URL"
        assert 0.0 <= trust <= 1.0, f"{name} trust {trust} out of range"
        assert url not in urls, f"Duplicate URL: {url}"
        urls.add(url)
        # Categories should be valid
        for cat in categories.split(","):
            assert cat in {
                "finance", "politics", "technology", "sports",
                "culture", "science", "health", "world",
            }, f"{name} has invalid category: {cat}"
