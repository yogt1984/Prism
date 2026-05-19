"""T0.1: Database initialization with WAL mode.

Tests written before implementation per ROADMAP TDD approach.
Covers: init_db idempotency, WAL mode, foreign keys, CRUD for all models,
concurrent read+write.
"""

import threading
import time
from pathlib import Path

import pytest
from sqlalchemy import inspect, text
from sqlmodel import Session, select

from prism.db import init_db
from prism.models import (
    Article,
    BiasLabel,
    Briefing,
    BriefingFormat,
    Engagement,
    Perspective,
    Source,
    StoryCluster,
    StoryStatus,
    User,
)


@pytest.fixture()
def db_engine(tmp_path: Path):
    """Create a fresh test database for each test."""
    db_path = tmp_path / "test.db"
    url = f"sqlite:///{db_path}"
    engine = init_db(url)
    yield engine
    engine.dispose()


@pytest.fixture()
def session(db_engine):
    """Provide a session bound to the test engine."""
    with Session(db_engine) as s:
        yield s


# --- init_db ---

def test_init_db_creates_all_tables(db_engine):
    table_names = inspect(db_engine).get_table_names()
    expected = {"source", "storycluster", "article", "perspective",
                "user", "engagement", "briefing"}
    assert expected.issubset(set(table_names))


def test_init_db_idempotent(tmp_path: Path):
    url = f"sqlite:///{tmp_path / 'test.db'}"
    engine1 = init_db(url)
    # Second call should not raise
    engine2 = init_db(url)
    tables = inspect(engine2).get_table_names()
    assert "source" in tables
    engine1.dispose()
    engine2.dispose()


# --- WAL mode ---

def test_wal_mode_enabled(db_engine):
    with db_engine.connect() as conn:
        result = conn.execute(text("PRAGMA journal_mode")).scalar()
        assert result == "wal"


# --- Foreign keys ---

def test_foreign_keys_enabled(db_engine):
    with db_engine.connect() as conn:
        result = conn.execute(text("PRAGMA foreign_keys")).scalar()
        assert result == 1


def test_foreign_key_article_invalid_cluster(session):
    source = Source(name="Test", url="test.com")
    session.add(source)
    session.commit()

    article = Article(
        cluster_id=99999,  # does not exist
        source_id=source.id,
        title="Test",
        url="https://test.com/1",
    )
    session.add(article)
    with pytest.raises(Exception):  # IntegrityError
        session.commit()


def test_foreign_key_article_invalid_source(session):
    cluster = StoryCluster(headline="Test")
    session.add(cluster)
    session.commit()

    article = Article(
        cluster_id=cluster.id,
        source_id=99999,  # does not exist
        title="Test",
        url="https://test.com/1",
    )
    session.add(article)
    with pytest.raises(Exception):
        session.commit()


def test_foreign_key_perspective_invalid_cluster(session):
    source = Source(name="Test", url="test.com")
    session.add(source)
    session.commit()

    perspective = Perspective(
        cluster_id=99999,
        source_id=source.id,
        summary="Test",
    )
    session.add(perspective)
    with pytest.raises(Exception):
        session.commit()


def test_foreign_key_engagement_invalid_user(session):
    cluster = StoryCluster(headline="Test")
    session.add(cluster)
    session.commit()

    engagement = Engagement(
        user_id=99999,
        cluster_id=cluster.id,
        action="read",
    )
    session.add(engagement)
    with pytest.raises(Exception):
        session.commit()


def test_foreign_key_briefing_invalid_user(session):
    briefing = Briefing(user_id=99999)
    session.add(briefing)
    with pytest.raises(Exception):
        session.commit()


# --- CRUD: Source ---

def test_crud_source(session):
    # Create
    source = Source(name="Reuters", url="reuters.com", trust_score=0.9,
                    bias_label=BiasLabel.CENTER)
    session.add(source)
    session.commit()
    assert source.id is not None

    # Read
    fetched = session.exec(select(Source).where(Source.url == "reuters.com")).one()
    assert fetched.name == "Reuters"
    assert fetched.trust_score == 0.9

    # Update
    fetched.trust_score = 0.95
    session.add(fetched)
    session.commit()
    refetched = session.get(Source, source.id)
    assert refetched.trust_score == 0.95

    # Delete
    session.delete(refetched)
    session.commit()
    assert session.get(Source, source.id) is None


# --- CRUD: StoryCluster + Article relationship ---

def test_crud_story_cluster_with_articles(session):
    source = Source(name="AP", url="apnews.com")
    session.add(source)
    session.commit()

    cluster = StoryCluster(headline="Market crash", article_count=2)
    session.add(cluster)
    session.commit()

    a1 = Article(cluster_id=cluster.id, source_id=source.id,
                 title="Markets plunge", url="https://ap.com/1")
    a2 = Article(cluster_id=cluster.id, source_id=source.id,
                 title="Stocks drop sharply", url="https://ap.com/2")
    session.add_all([a1, a2])
    session.commit()

    # Read back with relationship
    fetched = session.get(StoryCluster, cluster.id)
    assert len(fetched.articles) == 2
    assert {a.title for a in fetched.articles} == {"Markets plunge", "Stocks drop sharply"}

    # Update cluster status
    fetched.status = StoryStatus.ANALYZED
    session.add(fetched)
    session.commit()
    assert session.get(StoryCluster, cluster.id).status == StoryStatus.ANALYZED


# --- CRUD: User ---

def test_crud_user(session):
    user = User(email="alice@example.com", interests="finance,technology",
                briefing_depth=15, is_pro=True)
    session.add(user)
    session.commit()
    assert user.id is not None

    fetched = session.exec(select(User).where(User.email == "alice@example.com")).one()
    assert fetched.interests == "finance,technology"
    assert fetched.is_pro is True
    assert fetched.preferred_format == BriefingFormat.EMAIL

    fetched.briefing_depth = 20
    session.add(fetched)
    session.commit()
    assert session.get(User, user.id).briefing_depth == 20

    session.delete(session.get(User, user.id))
    session.commit()
    assert session.get(User, user.id) is None


# --- CRUD: Perspective ---

def test_crud_perspective(session):
    source = Source(name="BBC", url="bbc.co.uk")
    session.add(source)
    session.commit()

    cluster = StoryCluster(headline="Election results")
    session.add(cluster)
    session.commit()

    perspective = Perspective(
        cluster_id=cluster.id, source_id=source.id,
        summary="BBC frames this as a historic shift",
        sentiment=0.3, bias_label=BiasLabel.CENTER,
        key_claims='["Labour wins majority (Source: BBC)"]',
    )
    session.add(perspective)
    session.commit()

    fetched = session.get(StoryCluster, cluster.id)
    assert len(fetched.perspectives) == 1
    assert fetched.perspectives[0].sentiment == 0.3


# --- CRUD: Engagement ---

def test_crud_engagement(session):
    user = User(email="bob@example.com")
    cluster = StoryCluster(headline="Test")
    session.add_all([user, cluster])
    session.commit()

    engagement = Engagement(user_id=user.id, cluster_id=cluster.id,
                            action="read", read_time_sec=45)
    session.add(engagement)
    session.commit()

    fetched = session.exec(
        select(Engagement).where(Engagement.user_id == user.id)
    ).one()
    assert fetched.action == "read"
    assert fetched.read_time_sec == 45
    assert fetched.created_at is not None


# --- CRUD: Briefing ---

def test_crud_briefing(session):
    user = User(email="carol@example.com")
    session.add(user)
    session.commit()

    briefing = Briefing(user_id=user.id, content_html="<h1>News</h1>",
                        story_count=5, sent=True)
    session.add(briefing)
    session.commit()

    fetched = session.get(Briefing, briefing.id)
    assert fetched.content_html == "<h1>News</h1>"
    assert fetched.story_count == 5
    assert fetched.sent is True


# --- Concurrent access ---

def test_concurrent_read_write(db_engine):
    """WAL mode allows a reader thread to not block a writer thread."""
    # Seed a row
    with Session(db_engine) as s:
        s.add(Source(name="Seed", url="seed.com"))
        s.commit()

    errors: list[str] = []

    def writer():
        try:
            with Session(db_engine) as s:
                s.add(Source(name="Writer", url="writer.com"))
                time.sleep(0.1)  # hold the write open briefly
                s.commit()
        except Exception as e:
            errors.append(f"writer: {e}")

    def reader():
        try:
            with Session(db_engine) as s:
                results = s.exec(select(Source)).all()
                assert len(results) >= 1  # at least the seed row
        except Exception as e:
            errors.append(f"reader: {e}")

    t_writer = threading.Thread(target=writer)
    t_reader = threading.Thread(target=reader)

    t_writer.start()
    time.sleep(0.02)  # let writer start its transaction
    t_reader.start()

    t_writer.join(timeout=5)
    t_reader.join(timeout=5)

    assert errors == [], f"Concurrent access failed: {errors}"
