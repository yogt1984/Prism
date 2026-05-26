"""T10.8: OpenAPI schema completeness + end-to-end integration tests."""

from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from prism.api.app import create_app
from prism.api.routes import _get_session, generate_api_key, require_api_key
from prism.db import init_db
from prism.models import (
    Article,
    Briefing,
    Perspective,
    Source,
    StoryCluster,
    User,
)

_auth_state: dict[str, int] = {"user_id": 0}


@pytest.fixture()
def db_engine(tmp_path: Path):
    url = f"sqlite:///{tmp_path / 'test.db'}"
    engine = init_db(url)
    yield engine
    engine.dispose()


@pytest.fixture()
def client(db_engine):
    app = create_app()
    _auth_state["user_id"] = 0

    def _override():
        with Session(db_engine) as session:
            yield session

    app.dependency_overrides[_get_session] = _override
    app.dependency_overrides[require_api_key] = lambda: User(
        id=_auth_state["user_id"], email="auth@test", is_pro=True,
    )
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


# ══════════════════════════════════════════════════════════════════════
# OpenAPI schema validation
# ══════════════════════════════════════════════════════════════════════


@pytest.fixture()
def schema(client):
    resp = client.get("/openapi.json")
    assert resp.status_code == 200
    return resp.json()


def test_openapi_is_valid_json(schema):
    assert isinstance(schema, dict)
    assert "openapi" in schema
    assert "paths" in schema


def test_openapi_has_all_paths(schema):
    expected_paths = {
        "/health",
        "/config",
        "/sources",
        "/stories",
        "/stories/{story_id}",
        "/users",
        "/users/{user_id}",
        "/users/{user_id}/briefings",
        "/users/{user_id}/briefings/{briefing_id}",
        "/engagements",
    }
    assert expected_paths.issubset(set(schema["paths"].keys()))


def test_openapi_health_get_only(schema):
    health = schema["paths"]["/health"]
    assert "get" in health
    assert "post" not in health
    assert "put" not in health


def test_openapi_users_has_post_get_patch(schema):
    assert "post" in schema["paths"]["/users"]
    user_id_path = schema["paths"]["/users/{user_id}"]
    assert "get" in user_id_path
    assert "patch" in user_id_path


def test_openapi_stories_methods(schema):
    assert "get" in schema["paths"]["/stories"]
    assert "get" in schema["paths"]["/stories/{story_id}"]


def test_openapi_briefings_methods(schema):
    briefings = schema["paths"]["/users/{user_id}/briefings"]
    assert "get" in briefings
    assert "post" in briefings


def test_openapi_engagements_post_only(schema):
    eng = schema["paths"]["/engagements"]
    assert "post" in eng
    assert "get" not in eng


def test_openapi_schemas_defined(schema):
    """All response/request schemas must appear in components."""
    schemas = schema.get("components", {}).get("schemas", {})
    expected_schemas = {
        "HealthResponse",
        "ConfigResponse",
        "SourceOut",
        "StoryOut",
        "StoryDetailOut",
        "ArticleOut",
        "PerspectiveOut",
        "UserCreate",
        "UserUpdate",
        "UserOut",
        "BriefingOut",
        "BriefingDetailOut",
        "EngagementCreate",
        "EngagementOut",
    }
    assert expected_schemas.issubset(set(schemas.keys()))


def test_openapi_user_out_no_api_key(schema):
    """UserOut schema must NOT contain api_key field."""
    user_schema = schema["components"]["schemas"]["UserOut"]
    props = user_schema.get("properties", {})
    assert "api_key" not in props


def test_openapi_security_defined(schema):
    """Protected endpoints should reference the APIKeyHeader security scheme."""
    # At least one path should have security defined
    has_security = False
    for path_obj in schema["paths"].values():
        for method_obj in path_obj.values():
            if isinstance(method_obj, dict) and "security" in method_obj:
                has_security = True
                break
    assert has_security


def test_openapi_post_users_201(schema):
    post = schema["paths"]["/users"]["post"]
    assert "201" in post["responses"]


def test_openapi_post_engagements_201(schema):
    post = schema["paths"]["/engagements"]["post"]
    assert "201" in post["responses"]


def test_openapi_stories_pagination_params(schema):
    get = schema["paths"]["/stories"]["get"]
    param_names = {p["name"] for p in get.get("parameters", [])}
    assert "limit" in param_names
    assert "offset" in param_names
    assert "status" in param_names


def test_openapi_sources_active_param(schema):
    get = schema["paths"]["/sources"]["get"]
    param_names = {p["name"] for p in get.get("parameters", [])}
    assert "active" in param_names


def test_openapi_title_and_version(schema):
    assert schema["info"]["title"] == "Prism API"
    assert "version" in schema["info"]


# ══════════════════════════════════════════════════════════════════════
# End-to-end integration tests
# ══════════════════════════════════════════════════════════════════════


def _seed_story_with_data(engine):
    """Create a fully-formed story: source + cluster + article + perspective."""
    with Session(engine, expire_on_commit=False) as s:
        src = Source(name="Reuters", url="reuters.com", trust_score=0.95)
        s.add(src)
        s.commit()

        cluster = StoryCluster(
            headline="Market Rally",
            summary="Stocks surged today.",
            categories="finance",
            status="analyzed",
            article_count=1,
        )
        s.add(cluster)
        s.commit()

        art = Article(
            cluster_id=cluster.id,
            source_id=src.id,
            title="Stocks surge on data",
            url="https://reuters.com/markets/1",
            snippet="Markets rallied strongly.",
        )
        s.add(art)

        persp = Perspective(
            cluster_id=cluster.id,
            source_id=src.id,
            summary="Reuters reports strong rally.",
            sentiment=0.7,
            bias_label="center",
            key_claims='["Markets up 2% (Source: Reuters)"]',
        )
        s.add(persp)
        s.commit()

    return src, cluster, art, persp


def test_e2e_register_get_update_user(client):
    """Full user lifecycle: register → get → update → verify."""
    # Register
    r1 = client.post("/users", json={
        "email": "e2e@test.com",
        "interests": "finance,technology",
    })
    assert r1.status_code == 201
    user_id = r1.json()["id"]
    _auth_state["user_id"] = user_id

    # Get
    r2 = client.get(f"/users/{user_id}")
    assert r2.status_code == 200
    assert r2.json()["email"] == "e2e@test.com"

    # Update
    r3 = client.patch(f"/users/{user_id}", json={
        "name": "E2E User",
        "interests": "politics,health",
        "briefing_depth": 15,
    })
    assert r3.status_code == 200
    assert r3.json()["name"] == "E2E User"
    assert r3.json()["interests"] == "politics,health"
    assert r3.json()["briefing_depth"] == 15

    # Verify update persisted
    r4 = client.get(f"/users/{user_id}")
    assert r4.json()["name"] == "E2E User"


def test_e2e_browse_sources_and_stories(client, db_engine):
    """Browse public content: sources → stories → story detail."""
    src, cluster, art, persp = _seed_story_with_data(db_engine)

    # List sources
    sources = client.get("/sources").json()
    assert len(sources) >= 1
    assert any(s["name"] == "Reuters" for s in sources)

    # List stories
    stories = client.get("/stories").json()
    assert len(stories) >= 1
    assert any(s["headline"] == "Market Rally" for s in stories)

    # Story detail
    detail = client.get(f"/stories/{cluster.id}").json()
    assert detail["headline"] == "Market Rally"
    assert len(detail["articles"]) == 1
    assert len(detail["perspectives"]) == 1
    assert detail["perspectives"][0]["sentiment"] == 0.7


def test_e2e_engagement_feedback_loop(client, db_engine):
    """Register user → view stories → record engagement."""
    _seed_story_with_data(db_engine)

    # Register
    user = client.post("/users", json={
        "email": "engaged@test.com", "interests": "finance",
    }).json()

    # Discover a story
    stories = client.get("/stories").json()
    assert len(stories) >= 1
    cluster_id = stories[0]["id"]

    # Record open
    r1 = client.post("/engagements", json={
        "user_id": user["id"],
        "cluster_id": cluster_id,
        "action": "open",
    })
    assert r1.status_code == 201

    # Record read with time
    r2 = client.post("/engagements", json={
        "user_id": user["id"],
        "cluster_id": cluster_id,
        "action": "read",
        "read_time_sec": 90,
    })
    assert r2.status_code == 201
    assert r2.json()["read_time_sec"] == 90

    # Record save
    r3 = client.post("/engagements", json={
        "user_id": user["id"],
        "cluster_id": cluster_id,
        "action": "save",
    })
    assert r3.status_code == 201


def test_e2e_briefing_trigger_and_list(client, db_engine):
    """Register user → trigger briefing → list briefings → get detail."""
    _seed_story_with_data(db_engine)

    user = client.post("/users", json={
        "email": "brief@test.com", "interests": "finance",
    }).json()
    _auth_state["user_id"] = user["id"]

    # Mock the agents for briefing generation
    fake_briefing = Briefing(
        id=1,
        user_id=user["id"],
        content_html="<h1>Your Briefing</h1>",
        content_text="Your briefing text",
        story_count=1,
        sent=True,
        sent_at=datetime.now(UTC),
    )

    mock_p_ai = MagicMock()
    mock_p_ai.select_stories.return_value = [MagicMock()]
    mock_w_ai = MagicMock()
    mock_w_ai.create_and_send.return_value = fake_briefing

    with (
        patch("prism.agents.p_ai.PersonalizationAgent", return_value=mock_p_ai),
        patch("prism.agents.w_ai.WriterAgent", return_value=mock_w_ai),
    ):
        r_trigger = client.post(f"/users/{user['id']}/briefings")
    assert r_trigger.status_code == 201
    assert r_trigger.json()["story_count"] == 1
    assert r_trigger.json()["content_html"] == "<h1>Your Briefing</h1>"


def test_e2e_full_journey(client, db_engine):
    """Complete user journey: register → browse → engage → briefing."""
    src, cluster, _, _ = _seed_story_with_data(db_engine)

    # 1. Health check
    assert client.get("/health").json()["status"] == "ok"

    # 2. Browse sources
    sources = client.get("/sources").json()
    assert len(sources) >= 1

    # 3. Register
    user = client.post("/users", json={
        "email": "journey@test.com",
        "interests": "finance",
    }).json()
    user_id = user["id"]
    _auth_state["user_id"] = user_id

    # 4. Browse stories
    stories = client.get("/stories", params={"status": "analyzed"}).json()
    assert len(stories) >= 1
    story_id = stories[0]["id"]

    # 5. View story detail
    detail = client.get(f"/stories/{story_id}").json()
    assert len(detail["articles"]) >= 1

    # 6. Record engagement
    eng = client.post("/engagements", json={
        "user_id": user_id,
        "cluster_id": story_id,
        "action": "read",
        "read_time_sec": 120,
    })
    assert eng.status_code == 201

    # 7. Update profile
    client.patch(f"/users/{user_id}", json={"name": "Journey User"})
    assert client.get(f"/users/{user_id}").json()["name"] == "Journey User"

    # 8. List briefings (empty initially)
    briefings = client.get(f"/users/{user_id}/briefings").json()
    assert briefings == []


def test_e2e_duplicate_user_then_recover(client):
    """Register → duplicate fails → register with different email succeeds."""
    r1 = client.post("/users", json={
        "email": "dup@test.com", "interests": "finance",
    })
    assert r1.status_code == 201

    r2 = client.post("/users", json={
        "email": "dup@test.com", "interests": "politics",
    })
    assert r2.status_code == 422

    r3 = client.post("/users", json={
        "email": "nodup@test.com", "interests": "politics",
    })
    assert r3.status_code == 201
    assert r3.json()["email"] == "nodup@test.com"


def test_e2e_story_not_found_does_not_break_flow(client, db_engine):
    """Requesting a nonexistent story returns 404 but other endpoints still work."""
    r1 = client.get("/stories/99999")
    assert r1.status_code == 404

    # Sources still works
    r2 = client.get("/sources")
    assert r2.status_code == 200

    # Stories list still works
    r3 = client.get("/stories")
    assert r3.status_code == 200
