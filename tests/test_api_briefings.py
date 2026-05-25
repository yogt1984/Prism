"""T10.5: GET/POST /users/{id}/briefings endpoint tests."""

from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from prism.api.app import create_app
from prism.api.routes import _get_session, require_api_key
from prism.db import init_db
from prism.models import Briefing, Source, StoryCluster, User

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


def _make_user(engine, email="test@example.com"):
    with Session(engine, expire_on_commit=False) as s:
        user = User(email=email, interests="finance", briefing_depth=10)
        s.add(user)
        s.commit()
    return user


def _make_briefing(engine, user_id, *, sent=True, story_count=3,
                   content_html="<h1>News</h1>", content_text="News text"):
    with Session(engine, expire_on_commit=False) as s:
        b = Briefing(
            user_id=user_id,
            content_html=content_html,
            content_text=content_text,
            story_count=story_count,
            sent=sent,
            sent_at=datetime.now(UTC) if sent else None,
        )
        s.add(b)
        s.commit()
    return b


# ── GET /users/{id}/briefings ────────────────────────────────────────


def test_list_briefings_empty(client, db_engine):
    user = _make_user(db_engine)
    _auth_state["user_id"] = user.id
    resp = client.get(f"/users/{user.id}/briefings")
    assert resp.status_code == 200
    assert resp.json() == []


def test_list_briefings_returns_items(client, db_engine):
    user = _make_user(db_engine)
    _auth_state["user_id"] = user.id
    _make_briefing(db_engine, user.id)
    _make_briefing(db_engine, user.id, story_count=5)
    data = client.get(f"/users/{user.id}/briefings").json()
    assert len(data) == 2


def test_list_briefings_user_not_found(client):
    _auth_state["user_id"] = 9999
    resp = client.get("/users/9999/briefings")
    assert resp.status_code == 404
    assert "not found" in resp.json()["detail"].lower()


def test_list_briefings_only_own_user(client, db_engine):
    """User A must not see user B's briefings — enforced by user-scoped access."""
    user_a = _make_user(db_engine, email="a@test.com")
    user_b = _make_user(db_engine, email="b@test.com")
    _make_briefing(db_engine, user_a.id)
    _make_briefing(db_engine, user_b.id)
    _auth_state["user_id"] = user_a.id
    data = client.get(f"/users/{user_a.id}/briefings").json()
    assert len(data) == 1
    assert all(b["user_id"] == user_a.id for b in data)


def test_list_briefings_ordered_newest_first(client, db_engine):
    user = _make_user(db_engine)
    _auth_state["user_id"] = user.id
    for _ in range(5):
        _make_briefing(db_engine, user.id)
    data = client.get(f"/users/{user.id}/briefings").json()
    dates = [b["created_at"] for b in data]
    assert dates == sorted(dates, reverse=True)


def test_list_briefings_pagination_limit(client, db_engine):
    user = _make_user(db_engine)
    _auth_state["user_id"] = user.id
    for _ in range(10):
        _make_briefing(db_engine, user.id)
    data = client.get(f"/users/{user.id}/briefings", params={"limit": 3}).json()
    assert len(data) == 3


def test_list_briefings_pagination_offset(client, db_engine):
    user = _make_user(db_engine)
    _auth_state["user_id"] = user.id
    for _ in range(5):
        _make_briefing(db_engine, user.id)
    all_b = client.get(f"/users/{user.id}/briefings", params={"limit": 100}).json()
    offset_b = client.get(
        f"/users/{user.id}/briefings", params={"offset": 2, "limit": 100}
    ).json()
    assert len(offset_b) == len(all_b) - 2


def test_list_briefings_limit_bounds(client, db_engine):
    user = _make_user(db_engine)
    _auth_state["user_id"] = user.id
    assert client.get(f"/users/{user.id}/briefings", params={"limit": 0}).status_code == 422
    assert client.get(f"/users/{user.id}/briefings", params={"limit": 101}).status_code == 422


def test_list_briefings_response_fields(client, db_engine):
    user = _make_user(db_engine)
    _auth_state["user_id"] = user.id
    _make_briefing(db_engine, user.id)
    row = client.get(f"/users/{user.id}/briefings").json()[0]
    required = {"id", "user_id", "story_count", "sent", "sent_at", "created_at"}
    assert required.issubset(set(row.keys()))


def test_list_briefings_no_content_in_list(client, db_engine):
    """List endpoint must NOT include content_html/content_text (use detail)."""
    user = _make_user(db_engine)
    _auth_state["user_id"] = user.id
    _make_briefing(db_engine, user.id)
    row = client.get(f"/users/{user.id}/briefings").json()[0]
    assert "content_html" not in row
    assert "content_text" not in row


def test_list_briefings_sent_is_bool(client, db_engine):
    user = _make_user(db_engine)
    _auth_state["user_id"] = user.id
    _make_briefing(db_engine, user.id, sent=True)
    _make_briefing(db_engine, user.id, sent=False)
    data = client.get(f"/users/{user.id}/briefings").json()
    for b in data:
        assert isinstance(b["sent"], bool)


def test_list_briefings_sent_at_null_when_unsent(client, db_engine):
    user = _make_user(db_engine)
    _auth_state["user_id"] = user.id
    _make_briefing(db_engine, user.id, sent=False)
    row = client.get(f"/users/{user.id}/briefings").json()[0]
    assert row["sent_at"] is None
    assert row["sent"] is False


# ── GET /users/{id}/briefings/{briefing_id} ──────────────────────────


def test_get_briefing_detail(client, db_engine):
    user = _make_user(db_engine)
    _auth_state["user_id"] = user.id
    b = _make_briefing(db_engine, user.id, content_html="<p>Hello</p>")
    resp = client.get(f"/users/{user.id}/briefings/{b.id}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["content_html"] == "<p>Hello</p>"
    assert "content_text" in data


def test_get_briefing_detail_not_found(client, db_engine):
    user = _make_user(db_engine)
    _auth_state["user_id"] = user.id
    resp = client.get(f"/users/{user.id}/briefings/9999")
    assert resp.status_code == 404


def test_get_briefing_detail_wrong_user(client, db_engine):
    """Briefing belongs to user A — requesting via user B's path returns 403."""
    user_a = _make_user(db_engine, email="a@t.com")
    user_b = _make_user(db_engine, email="b@t.com")
    b = _make_briefing(db_engine, user_a.id)
    _auth_state["user_id"] = user_a.id
    resp = client.get(f"/users/{user_b.id}/briefings/{b.id}")
    assert resp.status_code == 403


def test_get_briefing_detail_user_not_found(client):
    _auth_state["user_id"] = 9999
    resp = client.get("/users/9999/briefings/1")
    assert resp.status_code == 404
    assert "User not found" in resp.json()["detail"]


def test_get_briefing_detail_fields_superset_of_list(client, db_engine):
    """Detail must include all list fields plus content."""
    user = _make_user(db_engine)
    _auth_state["user_id"] = user.id
    b = _make_briefing(db_engine, user.id)
    list_row = client.get(f"/users/{user.id}/briefings").json()[0]
    detail = client.get(f"/users/{user.id}/briefings/{b.id}").json()
    for key in list_row:
        assert key in detail, f"List field '{key}' missing from detail"
    assert "content_html" in detail
    assert "content_text" in detail


# ── POST /users/{id}/briefings ───────────────────────────────────────


def test_trigger_briefing_user_not_found(client):
    _auth_state["user_id"] = 9999
    resp = client.post("/users/9999/briefings")
    assert resp.status_code == 404


def test_trigger_briefing_no_stories(client, db_engine):
    """When no stories are available, must return 422."""
    user = _make_user(db_engine)
    _auth_state["user_id"] = user.id

    mock_p_ai = MagicMock()
    mock_p_ai.select_stories.return_value = []
    mock_w_ai = MagicMock()
    mock_w_ai.create_and_send.return_value = None

    with (
        patch("prism.agents.p_ai.PersonalizationAgent", return_value=mock_p_ai),
        patch("prism.agents.w_ai.WriterAgent", return_value=mock_w_ai),
    ):
        resp = client.post(f"/users/{user.id}/briefings")
    assert resp.status_code == 422
    assert "No stories" in resp.json()["detail"]


def test_trigger_briefing_success(client, db_engine):
    """Mocked pipeline returns a briefing — must get 201 with content."""
    user = _make_user(db_engine)
    _auth_state["user_id"] = user.id

    fake_briefing = Briefing(
        id=1,
        user_id=user.id,
        content_html="<h1>Briefing</h1>",
        content_text="Briefing text",
        story_count=3,
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
        resp = client.post(f"/users/{user.id}/briefings")
    assert resp.status_code == 201
    data = resp.json()
    assert data["story_count"] == 3
    assert data["content_html"] == "<h1>Briefing</h1>"


def test_trigger_briefing_calls_agents_with_user(client, db_engine):
    """Verify P_AI and W_AI are called with the correct user."""
    user = _make_user(db_engine)
    _auth_state["user_id"] = user.id

    mock_p_ai = MagicMock()
    mock_p_ai.select_stories.return_value = []
    mock_w_ai = MagicMock()
    mock_w_ai.create_and_send.return_value = None

    with (
        patch("prism.agents.p_ai.PersonalizationAgent", return_value=mock_p_ai),
        patch("prism.agents.w_ai.WriterAgent", return_value=mock_w_ai),
    ):
        client.post(f"/users/{user.id}/briefings")

    # P_AI must have been called with a user whose id matches
    call_args = mock_p_ai.select_stories.call_args
    called_user = call_args[0][0] if call_args[0] else call_args[1].get("user")
    assert called_user.id == user.id


def test_trigger_briefing_response_is_detail_schema(client, db_engine):
    """POST response must include content fields (detail schema, not list)."""
    user = _make_user(db_engine)
    _auth_state["user_id"] = user.id

    fake_briefing = Briefing(
        id=1,
        user_id=user.id,
        content_html="<p>Content</p>",
        content_text="Content",
        story_count=1,
        sent=False,
    )

    mock_p_ai = MagicMock()
    mock_p_ai.select_stories.return_value = [MagicMock()]
    mock_w_ai = MagicMock()
    mock_w_ai.create_and_send.return_value = fake_briefing

    with (
        patch("prism.agents.p_ai.PersonalizationAgent", return_value=mock_p_ai),
        patch("prism.agents.w_ai.WriterAgent", return_value=mock_w_ai),
    ):
        data = client.post(f"/users/{user.id}/briefings").json()
    assert "content_html" in data
    assert "content_text" in data
    assert "story_count" in data
