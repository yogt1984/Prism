"""T10.3: GET /sources, GET /stories, GET /stories/{id} tests."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from prism.api.app import create_app
from prism.api.routes import _get_session
from prism.db import init_db
from prism.models import (
    Article,
    Perspective,
    Source,
    StoryCluster,
    StoryStatus,
    TopicResonance,
)


@pytest.fixture()
def db_engine(tmp_path: Path):
    url = f"sqlite:///{tmp_path / 'test.db'}"
    engine = init_db(url)
    yield engine
    engine.dispose()


@pytest.fixture()
def client(db_engine):
    app = create_app()

    def _override():
        with Session(db_engine) as session:
            yield session

    app.dependency_overrides[_get_session] = _override
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def _seed_sources(engine, count=3):
    sources = []
    with Session(engine, expire_on_commit=False) as s:
        for i in range(count):
            src = Source(
                name=f"Source-{i}",
                url=f"source{i}.com",
                trust_score=round(0.5 + i * 0.1, 1),
                bias_label="center",
                active=(i % 2 == 0),  # 0,2 active; 1 inactive
            )
            s.add(src)
            sources.append(src)
        s.commit()
    return sources


def _seed_story(engine, source, *, status="raw", headline="Test Event",
                n_articles=2, n_perspectives=1):
    with Session(engine, expire_on_commit=False) as s:
        cluster = StoryCluster(
            headline=headline,
            summary="A test summary.",
            categories="politics",
            status=status,
            article_count=n_articles,
        )
        s.add(cluster)
        s.commit()

        for j in range(n_articles):
            art = Article(
                cluster_id=cluster.id,
                source_id=source.id,
                title=f"{headline} — article {j}",
                url=f"https://example.com/{cluster.id}/{j}",
                snippet=f"Snippet {j}",
            )
            s.add(art)

        for k in range(n_perspectives):
            persp = Perspective(
                cluster_id=cluster.id,
                source_id=source.id,
                summary=f"Perspective {k} on {headline}",
                sentiment=0.2,
                bias_label="center",
                key_claims="[]",
            )
            s.add(persp)
        s.commit()
    return cluster


# ── GET /sources ──────────────────────────────────────────────────────


def test_sources_empty_db(client):
    resp = client.get("/sources")
    assert resp.status_code == 200
    assert resp.json() == []


def test_sources_returns_all(client, db_engine):
    _seed_sources(db_engine, count=4)
    resp = client.get("/sources")
    assert resp.status_code == 200
    assert len(resp.json()) == 4


def test_sources_ordered_by_trust_desc(client, db_engine):
    _seed_sources(db_engine, count=5)
    data = client.get("/sources").json()
    scores = [s["trust_score"] for s in data]
    assert scores == sorted(scores, reverse=True)


def test_sources_filter_active_true(client, db_engine):
    _seed_sources(db_engine, count=4)  # indices 0,2 active; 1,3 inactive
    data = client.get("/sources", params={"active": True}).json()
    assert all(s["active"] is True for s in data)
    assert len(data) == 2


def test_sources_filter_active_false(client, db_engine):
    _seed_sources(db_engine, count=4)
    data = client.get("/sources", params={"active": False}).json()
    assert all(s["active"] is False for s in data)
    assert len(data) == 2


def test_sources_no_filter_returns_both(client, db_engine):
    _seed_sources(db_engine, count=3)  # 2 active, 1 inactive
    data = client.get("/sources").json()
    active_flags = {s["active"] for s in data}
    assert active_flags == {True, False}


def test_sources_response_fields(client, db_engine):
    _seed_sources(db_engine, count=1)
    row = client.get("/sources").json()[0]
    required = {"id", "name", "url", "rss_url", "trust_score",
                "bias_label", "categories", "active", "created_at"}
    assert required.issubset(set(row.keys()))


def test_sources_trust_score_is_float(client, db_engine):
    _seed_sources(db_engine, count=1)
    row = client.get("/sources").json()[0]
    assert isinstance(row["trust_score"], float)


def test_sources_id_is_int(client, db_engine):
    _seed_sources(db_engine, count=1)
    row = client.get("/sources").json()[0]
    assert isinstance(row["id"], int)


# ── GET /stories ──────────────────────────────────────────────────────


def test_stories_empty_db(client):
    resp = client.get("/stories")
    assert resp.status_code == 200
    assert resp.json() == []


def test_stories_returns_list(client, db_engine):
    sources = _seed_sources(db_engine, count=1)
    _seed_story(db_engine, sources[0])
    _seed_story(db_engine, sources[0], headline="Second Event")
    data = client.get("/stories").json()
    assert len(data) == 2


def test_stories_default_limit_20(client, db_engine):
    sources = _seed_sources(db_engine, count=1)
    for i in range(25):
        _seed_story(db_engine, sources[0], headline=f"Event {i}")
    data = client.get("/stories").json()
    assert len(data) == 20


def test_stories_custom_limit(client, db_engine):
    sources = _seed_sources(db_engine, count=1)
    for i in range(10):
        _seed_story(db_engine, sources[0], headline=f"Event {i}")
    data = client.get("/stories", params={"limit": 3}).json()
    assert len(data) == 3


def test_stories_limit_max_100(client):
    resp = client.get("/stories", params={"limit": 101})
    assert resp.status_code == 422


def test_stories_limit_min_1(client):
    resp = client.get("/stories", params={"limit": 0})
    assert resp.status_code == 422


def test_stories_offset(client, db_engine):
    sources = _seed_sources(db_engine, count=1)
    for i in range(5):
        _seed_story(db_engine, sources[0], headline=f"Event {i}")
    all_stories = client.get("/stories", params={"limit": 100}).json()
    offset_stories = client.get("/stories", params={"offset": 2, "limit": 100}).json()
    assert len(offset_stories) == len(all_stories) - 2


def test_stories_offset_beyond_total(client, db_engine):
    sources = _seed_sources(db_engine, count=1)
    _seed_story(db_engine, sources[0])
    data = client.get("/stories", params={"offset": 999}).json()
    assert data == []


def test_stories_filter_status_raw(client, db_engine):
    sources = _seed_sources(db_engine, count=1)
    _seed_story(db_engine, sources[0], status="raw")
    _seed_story(db_engine, sources[0], status="analyzed", headline="Analyzed")
    data = client.get("/stories", params={"status": "raw"}).json()
    assert len(data) == 1
    assert data[0]["status"] == "raw"


def test_stories_filter_status_analyzed(client, db_engine):
    sources = _seed_sources(db_engine, count=1)
    _seed_story(db_engine, sources[0], status="raw")
    _seed_story(db_engine, sources[0], status="analyzed", headline="Analyzed")
    data = client.get("/stories", params={"status": "analyzed"}).json()
    assert len(data) == 1
    assert data[0]["status"] == "analyzed"


def test_stories_filter_status_invalid(client):
    resp = client.get("/stories", params={"status": "bogus"})
    assert resp.status_code == 422
    assert "Invalid status" in resp.json()["detail"]


def test_stories_filter_status_case_insensitive(client, db_engine):
    sources = _seed_sources(db_engine, count=1)
    _seed_story(db_engine, sources[0], status="raw")
    data = client.get("/stories", params={"status": "RAW"}).json()
    assert len(data) == 1


def test_stories_ordered_by_first_seen_desc(client, db_engine):
    sources = _seed_sources(db_engine, count=1)
    for i in range(5):
        _seed_story(db_engine, sources[0], headline=f"Event {i}")
    data = client.get("/stories").json()
    dates = [s["first_seen"] for s in data]
    assert dates == sorted(dates, reverse=True)


def test_stories_response_fields(client, db_engine):
    sources = _seed_sources(db_engine, count=1)
    _seed_story(db_engine, sources[0])
    row = client.get("/stories").json()[0]
    required = {"id", "headline", "summary", "categories", "status",
                "article_count", "first_seen", "last_updated"}
    assert required.issubset(set(row.keys()))


def test_stories_list_does_not_include_articles(client, db_engine):
    """List endpoint must NOT embed articles/perspectives (use detail for that)."""
    sources = _seed_sources(db_engine, count=1)
    _seed_story(db_engine, sources[0])
    row = client.get("/stories").json()[0]
    assert "articles" not in row
    assert "perspectives" not in row


# ── GET /stories/{id} ────────────────────────────────────────────────


def test_story_detail_found(client, db_engine):
    sources = _seed_sources(db_engine, count=1)
    cluster = _seed_story(db_engine, sources[0], n_articles=3, n_perspectives=2)
    resp = client.get(f"/stories/{cluster.id}")
    assert resp.status_code == 200


def test_story_detail_not_found(client):
    resp = client.get("/stories/9999")
    assert resp.status_code == 404
    assert "not found" in resp.json()["detail"].lower()


def test_story_detail_includes_articles(client, db_engine):
    sources = _seed_sources(db_engine, count=1)
    cluster = _seed_story(db_engine, sources[0], n_articles=3)
    data = client.get(f"/stories/{cluster.id}").json()
    assert len(data["articles"]) == 3


def test_story_detail_includes_perspectives(client, db_engine):
    sources = _seed_sources(db_engine, count=1)
    cluster = _seed_story(db_engine, sources[0], n_perspectives=2)
    data = client.get(f"/stories/{cluster.id}").json()
    assert len(data["perspectives"]) == 2


def test_story_detail_article_fields(client, db_engine):
    sources = _seed_sources(db_engine, count=1)
    cluster = _seed_story(db_engine, sources[0])
    art = client.get(f"/stories/{cluster.id}").json()["articles"][0]
    required = {"id", "source_id", "title", "url", "snippet",
                "published_at", "fetched_at"}
    assert required.issubset(set(art.keys()))


def test_story_detail_perspective_fields(client, db_engine):
    sources = _seed_sources(db_engine, count=1)
    cluster = _seed_story(db_engine, sources[0])
    persp = client.get(f"/stories/{cluster.id}").json()["perspectives"][0]
    required = {"id", "source_id", "summary", "sentiment",
                "bias_label", "key_claims"}
    assert required.issubset(set(persp.keys()))


def test_story_detail_no_articles_returns_empty_list(client, db_engine):
    """A cluster with 0 articles must return articles: [], not crash."""
    with Session(db_engine, expire_on_commit=False) as s:
        cluster = StoryCluster(headline="Bare", summary="No arts", categories="world")
        s.add(cluster)
        s.commit()
    data = client.get(f"/stories/{cluster.id}").json()
    assert data["articles"] == []
    assert data["perspectives"] == []


def test_story_detail_invalid_id_type(client):
    """Non-integer ID must be rejected."""
    resp = client.get("/stories/abc")
    assert resp.status_code == 422


def test_story_detail_negative_id(client):
    resp = client.get("/stories/-1")
    assert resp.status_code == 404


def test_story_detail_sentiment_is_float(client, db_engine):
    sources = _seed_sources(db_engine, count=1)
    cluster = _seed_story(db_engine, sources[0])
    persp = client.get(f"/stories/{cluster.id}").json()["perspectives"][0]
    assert isinstance(persp["sentiment"], float)


def test_story_detail_cluster_fields_match_list(client, db_engine):
    """Detail endpoint must include the same top-level fields as the list."""
    sources = _seed_sources(db_engine, count=1)
    cluster = _seed_story(db_engine, sources[0])
    list_row = client.get("/stories").json()[0]
    detail = client.get(f"/stories/{cluster.id}").json()
    for key in ("id", "headline", "summary", "categories", "status", "article_count"):
        assert detail[key] == list_row[key], f"Mismatch on {key}"


# ── GET /stories — resonance_score field ────────────────────────────


def test_stories_list_includes_resonance_score(client, db_engine):
    sources = _seed_sources(db_engine, count=1)
    _seed_story(db_engine, sources[0])
    row = client.get("/stories").json()[0]
    assert "resonance_score" in row
    assert row["resonance_score"] == 0.0


def test_stories_no_resonance_returns_zero(client, db_engine):
    """Stories with no resonance data yet return resonance_score: 0.0."""
    sources = _seed_sources(db_engine, count=1)
    _seed_story(db_engine, sources[0])
    row = client.get("/stories").json()[0]
    assert row["resonance_score"] == 0.0


# ── GET /stories?sort=resonance ─────────────────────────────────────


def test_stories_sort_resonance(client, db_engine):
    """GET /stories?sort=resonance returns stories ordered by resonance desc."""
    sources = _seed_sources(db_engine, count=1)
    c1 = _seed_story(db_engine, sources[0], headline="Low resonance")
    c2 = _seed_story(db_engine, sources[0], headline="High resonance")
    # Manually set resonance scores
    with Session(db_engine) as s:
        cl1 = s.get(StoryCluster, c1.id)
        cl1.resonance_score = 1.0
        cl2 = s.get(StoryCluster, c2.id)
        cl2.resonance_score = 10.0
        s.add(cl1)
        s.add(cl2)
        s.commit()

    data = client.get("/stories", params={"sort": "resonance"}).json()
    assert data[0]["headline"] == "High resonance"
    assert data[1]["headline"] == "Low resonance"


def test_stories_sort_invalid(client):
    resp = client.get("/stories", params={"sort": "bogus"})
    assert resp.status_code == 422
    assert "Invalid sort" in resp.json()["detail"]


def test_stories_sort_default_is_first_seen(client, db_engine):
    """Default sort is first_seen desc, not resonance."""
    sources = _seed_sources(db_engine, count=1)
    _seed_story(db_engine, sources[0], headline="Old")
    _seed_story(db_engine, sources[0], headline="New")
    data = client.get("/stories").json()
    dates = [s["first_seen"] for s in data]
    assert dates == sorted(dates, reverse=True)


# ── GET /stories/{id}/resonance ─────────────────────────────────────


def test_story_resonance_found(client, db_engine):
    sources = _seed_sources(db_engine, count=1)
    cluster = _seed_story(db_engine, sources[0])
    with Session(db_engine) as s:
        tr = TopicResonance(
            cluster_id=cluster.id,
            resonance=12.5,
            momentum=3.2,
            peak_resonance=15.0,
            mention_count=8,
            source_count=4,
            authority_weighted_sum=6.1,
            breadth=2.32,
            window_hours=72,
        )
        s.add(tr)
        s.commit()

    resp = client.get(f"/stories/{cluster.id}/resonance")
    assert resp.status_code == 200
    data = resp.json()
    assert data["resonance"] == 12.5
    assert data["momentum"] == 3.2
    assert data["peak_resonance"] == 15.0
    assert data["mention_count"] == 8
    assert data["source_count"] == 4
    assert data["authority_weighted_sum"] == 6.1
    assert data["breadth"] == 2.32
    assert data["window_hours"] == 72
    assert "computed_at" in data


def test_story_resonance_not_found(client):
    resp = client.get("/stories/9999/resonance")
    assert resp.status_code == 404


def test_story_resonance_no_data_yet(client, db_engine):
    """Story exists but resonance not computed → 404."""
    sources = _seed_sources(db_engine, count=1)
    cluster = _seed_story(db_engine, sources[0])
    resp = client.get(f"/stories/{cluster.id}/resonance")
    assert resp.status_code == 404
    assert "not yet computed" in resp.json()["detail"]
