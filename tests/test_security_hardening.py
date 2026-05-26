"""M11: Security hardening tests — API key hashing, rate limiting, user-scoped access.

Covers T11.1 (hashed API keys), T11.2 (rate limiting), T11.3 (user-scoped access).
"""

import hashlib
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from prism.api.app import create_app
from prism.api.rate_limit import RateLimitMiddleware
from prism.api.routes import _get_session, generate_api_key, hash_api_key
from prism.db import init_db
from prism.models import Briefing, StoryCluster, User


# ── Fixtures ────────────────────────────────────────────────────────────


@pytest.fixture()
def db_engine(tmp_path: Path):
    url = f"sqlite:///{tmp_path / 'test.db'}"
    engine = init_db(url)
    yield engine
    engine.dispose()


@pytest.fixture()
def client(db_engine):
    """Client with real auth (no override) — for testing actual auth flow."""
    app = create_app()

    def _override():
        with Session(db_engine) as session:
            yield session

    app.dependency_overrides[_get_session] = _override
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture()
def rate_limited_client(db_engine):
    """Client with aggressive rate limit for testing."""
    app = create_app()

    # Remove default middleware and add one with low limits
    app.user_middleware.clear()
    app.middleware_stack = None  # force rebuild
    app.add_middleware(RateLimitMiddleware, public_rpm=5, authenticated_rpm=10, window_seconds=60)

    def _override():
        with Session(db_engine) as session:
            yield session

    app.dependency_overrides[_get_session] = _override
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def _make_pro_user(engine, email="pro@test.com"):
    """Create a pro user with hashed API key. Returns (user, raw_key)."""
    raw_key, key_hash = generate_api_key()
    with Session(engine, expire_on_commit=False) as s:
        user = User(
            email=email,
            interests="finance",
            is_pro=True,
            api_key_hash=key_hash,
        )
        s.add(user)
        s.commit()
    return user, raw_key


def _make_free_user(engine, email="free@test.com"):
    """Create a free user with hashed API key. Returns (user, raw_key)."""
    raw_key, key_hash = generate_api_key()
    with Session(engine, expire_on_commit=False) as s:
        user = User(
            email=email,
            interests="finance",
            is_pro=False,
            api_key_hash=key_hash,
        )
        s.add(user)
        s.commit()
    return user, raw_key


def _make_briefing(engine, user_id):
    with Session(engine, expire_on_commit=False) as s:
        b = Briefing(user_id=user_id, content_html="<p>News</p>", story_count=1)
        s.add(b)
        s.commit()
    return b


def _make_cluster(engine, headline="Test Event"):
    with Session(engine, expire_on_commit=False) as s:
        cluster = StoryCluster(headline=headline, article_count=1)
        s.add(cluster)
        s.commit()
    return cluster


# ══════════════════════════════════════════════════════════════════════
# T11.1: API Key Hashing
# ══════════════════════════════════════════════════════════════════════


class TestApiKeyHashing:
    """T11.1: API keys must be hashed at rest with SHA-256."""

    def test_hash_api_key_returns_sha256_hex(self):
        result = hash_api_key("prism_test_key_123")
        assert len(result) == 64  # SHA-256 hex digest
        assert all(c in "0123456789abcdef" for c in result)

    def test_hash_api_key_deterministic(self):
        key = "prism_abc123"
        assert hash_api_key(key) == hash_api_key(key)

    def test_hash_api_key_different_inputs_different_hashes(self):
        h1 = hash_api_key("prism_key_a")
        h2 = hash_api_key("prism_key_b")
        assert h1 != h2

    def test_hash_api_key_matches_stdlib_sha256(self):
        key = "prism_verify_hash"
        expected = hashlib.sha256(key.encode()).hexdigest()
        assert hash_api_key(key) == expected

    def test_hash_api_key_empty_string(self):
        """Empty string should still produce a valid hash."""
        result = hash_api_key("")
        assert len(result) == 64

    def test_generate_api_key_returns_raw_and_hash(self):
        raw, hashed = generate_api_key()
        assert raw.startswith("prism_")
        assert len(hashed) == 64
        assert hash_api_key(raw) == hashed

    def test_generate_api_key_raw_differs_from_hash(self):
        raw, hashed = generate_api_key()
        assert raw != hashed

    def test_generate_api_key_100_unique_pairs(self):
        pairs = [generate_api_key() for _ in range(100)]
        raw_keys = {p[0] for p in pairs}
        hashes = {p[1] for p in pairs}
        assert len(raw_keys) == 100
        assert len(hashes) == 100

    def test_auth_succeeds_with_correct_raw_key(self, client, db_engine):
        user, raw_key = _make_pro_user(db_engine)
        resp = client.get(
            f"/users/{user.id}",
            headers={"X-API-Key": raw_key},
        )
        assert resp.status_code == 200
        assert resp.json()["email"] == "pro@test.com"

    def test_auth_fails_with_hash_instead_of_raw_key(self, client, db_engine):
        """Sending the hash as the API key must fail — only raw key works."""
        user, raw_key = _make_pro_user(db_engine)
        key_hash = hash_api_key(raw_key)
        resp = client.get(
            f"/users/{user.id}",
            headers={"X-API-Key": key_hash},
        )
        assert resp.status_code == 401

    def test_auth_fails_with_wrong_key(self, client, db_engine):
        user, _ = _make_pro_user(db_engine)
        resp = client.get(
            f"/users/{user.id}",
            headers={"X-API-Key": "prism_wrong_key_entirely"},
        )
        assert resp.status_code == 401

    def test_stored_hash_not_equal_to_raw_key(self, db_engine):
        user, raw_key = _make_pro_user(db_engine)
        with Session(db_engine) as s:
            stored_user = s.get(User, user.id)
            assert stored_user is not None
            assert stored_user.api_key_hash != raw_key
            assert stored_user.api_key_hash == hash_api_key(raw_key)

    def test_plaintext_api_key_field_is_empty(self, db_engine):
        """Deprecated api_key field should be empty for new users."""
        user, _ = _make_pro_user(db_engine)
        with Session(db_engine) as s:
            stored = s.get(User, user.id)
            assert stored is not None
            assert stored.api_key == ""

    def test_empty_api_key_hash_cannot_auth(self, client, db_engine):
        """User with empty api_key_hash must not be matchable."""
        with Session(db_engine, expire_on_commit=False) as s:
            user = User(email="nohash@test.com", is_pro=True, api_key_hash="")
            s.add(user)
            s.commit()
        resp = client.get(
            f"/users/{user.id}",
            headers={"X-API-Key": ""},
        )
        assert resp.status_code == 401

    def test_two_users_different_keys_both_auth(self, client, db_engine):
        user_a, key_a = _make_pro_user(db_engine, email="a@test.com")
        user_b, key_b = _make_pro_user(db_engine, email="b@test.com")
        assert key_a != key_b

        resp_a = client.get(
            f"/users/{user_a.id}",
            headers={"X-API-Key": key_a},
        )
        assert resp_a.status_code == 200
        assert resp_a.json()["email"] == "a@test.com"

        resp_b = client.get(
            f"/users/{user_b.id}",
            headers={"X-API-Key": key_b},
        )
        assert resp_b.status_code == 200
        assert resp_b.json()["email"] == "b@test.com"

    def test_user_a_key_cannot_auth_as_user_b(self, client, db_engine):
        """Cross-user key must not work."""
        user_a, key_a = _make_pro_user(db_engine, email="a@test.com")
        user_b, key_b = _make_pro_user(db_engine, email="b@test.com")
        # user_a's key should auth as user_a, not user_b
        # accessing user_b with user_a's key should be 403 (user-scoped)
        resp = client.get(
            f"/users/{user_b.id}",
            headers={"X-API-Key": key_a},
        )
        assert resp.status_code == 403

    def test_api_key_never_in_user_response(self, client, db_engine):
        user, raw_key = _make_pro_user(db_engine)
        resp = client.get(
            f"/users/{user.id}",
            headers={"X-API-Key": raw_key},
        )
        body = resp.text
        assert raw_key not in body
        data = resp.json()
        assert "api_key" not in data
        assert "api_key_hash" not in data

    def test_hash_is_case_sensitive(self):
        h1 = hash_api_key("prism_ABC")
        h2 = hash_api_key("prism_abc")
        assert h1 != h2

    def test_hash_unicode_key(self):
        """Unicode in key should hash correctly."""
        result = hash_api_key("prism_tëst_kéy_ünïcödé")
        assert len(result) == 64


# ══════════════════════════════════════════════════════════════════════
# T11.2: Rate Limiting
# ══════════════════════════════════════════════════════════════════════


class TestRateLimiting:
    """T11.2: In-memory sliding-window rate limiter."""

    def test_requests_under_limit_succeed(self, rate_limited_client):
        """5 requests under the public limit of 5 should all succeed."""
        for i in range(5):
            resp = rate_limited_client.get("/health")
            assert resp.status_code == 200, f"Request {i+1} failed"

    def test_request_over_limit_returns_429(self, rate_limited_client):
        """6th request exceeding public limit of 5 should return 429."""
        for _ in range(5):
            rate_limited_client.get("/health")
        resp = rate_limited_client.get("/health")
        assert resp.status_code == 429

    def test_429_response_has_retry_after_header(self, rate_limited_client):
        for _ in range(5):
            rate_limited_client.get("/health")
        resp = rate_limited_client.get("/health")
        assert resp.status_code == 429
        assert "Retry-After" in resp.headers
        retry_after = int(resp.headers["Retry-After"])
        assert retry_after > 0
        assert retry_after <= 61

    def test_429_response_body(self, rate_limited_client):
        for _ in range(5):
            rate_limited_client.get("/health")
        resp = rate_limited_client.get("/health")
        assert resp.status_code == 429
        assert "Too many requests" in resp.json()["detail"]

    def test_different_endpoints_share_ip_limit(self, rate_limited_client):
        """Rate limit is per IP, not per endpoint."""
        rate_limited_client.get("/health")
        rate_limited_client.get("/health")
        rate_limited_client.get("/sources")
        rate_limited_client.get("/stories")
        rate_limited_client.get("/health")
        # 6th request should be blocked regardless of endpoint
        resp = rate_limited_client.get("/sources")
        assert resp.status_code == 429

    def test_authenticated_gets_higher_limit(self, rate_limited_client, db_engine):
        """Authenticated requests get 10 rpm (vs 5 for public)."""
        user, raw_key = _make_pro_user(db_engine)
        headers = {"X-API-Key": raw_key}
        for i in range(10):
            resp = rate_limited_client.get(
                f"/users/{user.id}",
                headers=headers,
            )
            assert resp.status_code == 200, f"Auth request {i+1} failed"
        # 11th should be rate limited
        resp = rate_limited_client.get(
            f"/users/{user.id}",
            headers=headers,
        )
        assert resp.status_code == 429

    def test_rate_limit_middleware_instantiation(self):
        """Verify middleware can be instantiated with custom params."""
        from fastapi import FastAPI
        app = FastAPI()
        app.add_middleware(
            RateLimitMiddleware,
            public_rpm=30,
            authenticated_rpm=60,
            window_seconds=120,
        )
        assert app.user_middleware  # middleware was registered

    def test_rate_limit_allows_after_window_expires(self):
        """After the window passes, requests should be allowed again."""
        from fastapi import FastAPI
        from prism.api.routes import router

        app = FastAPI()
        app.add_middleware(
            RateLimitMiddleware,
            public_rpm=2,
            authenticated_rpm=4,
            window_seconds=1,  # 1-second window for fast test
        )
        app.include_router(router)

        with TestClient(app) as c:
            c.get("/health")
            c.get("/health")
            # Should be blocked
            assert c.get("/health").status_code == 429
            # Wait for window to expire
            time.sleep(1.1)
            # Should be allowed again
            assert c.get("/health").status_code == 200

    def test_multiple_429_does_not_crash(self, rate_limited_client):
        """Hitting rate limit multiple times should not cause errors."""
        for _ in range(5):
            rate_limited_client.get("/health")
        for _ in range(10):
            resp = rate_limited_client.get("/health")
            assert resp.status_code == 429

    def test_post_requests_also_rate_limited(self, rate_limited_client):
        """POST requests count toward the rate limit."""
        for _ in range(4):
            rate_limited_client.get("/health")
        rate_limited_client.post("/users", json={
            "email": "rl@test.com", "interests": "finance",
        })
        # 6th request total
        resp = rate_limited_client.get("/health")
        assert resp.status_code == 429


# ══════════════════════════════════════════════════════════════════════
# T11.3: User-Scoped Access
# ══════════════════════════════════════════════════════════════════════


class TestUserScopedAccess:
    """T11.3: Authenticated users can only access their own resources."""

    # ── GET /users/{id} ─────────────────────────────────────────────

    def test_user_can_read_own_profile(self, client, db_engine):
        user, key = _make_pro_user(db_engine)
        resp = client.get(
            f"/users/{user.id}",
            headers={"X-API-Key": key},
        )
        assert resp.status_code == 200
        assert resp.json()["email"] == "pro@test.com"

    def test_user_cannot_read_other_profile(self, client, db_engine):
        user_a, key_a = _make_pro_user(db_engine, email="a@test.com")
        user_b, key_b = _make_pro_user(db_engine, email="b@test.com")
        resp = client.get(
            f"/users/{user_b.id}",
            headers={"X-API-Key": key_a},
        )
        assert resp.status_code == 403
        assert "Access denied" in resp.json()["detail"]

    def test_access_denied_message_is_clear(self, client, db_engine):
        user_a, key_a = _make_pro_user(db_engine, email="a@test.com")
        user_b, _ = _make_pro_user(db_engine, email="b@test.com")
        resp = client.get(
            f"/users/{user_b.id}",
            headers={"X-API-Key": key_a},
        )
        assert resp.status_code == 403
        detail = resp.json()["detail"]
        assert "own resources" in detail.lower()

    # ── PATCH /users/{id} ───────────────────────────────────────────

    def test_user_can_update_own_profile(self, client, db_engine):
        user, key = _make_pro_user(db_engine)
        resp = client.patch(
            f"/users/{user.id}",
            json={"name": "Updated"},
            headers={"X-API-Key": key},
        )
        assert resp.status_code == 200
        assert resp.json()["name"] == "Updated"

    def test_user_cannot_update_other_profile(self, client, db_engine):
        user_a, key_a = _make_pro_user(db_engine, email="a@test.com")
        user_b, _ = _make_pro_user(db_engine, email="b@test.com")
        resp = client.patch(
            f"/users/{user_b.id}",
            json={"name": "Hacked"},
            headers={"X-API-Key": key_a},
        )
        assert resp.status_code == 403

    def test_patch_denied_does_not_modify_target(self, client, db_engine):
        """Ensure the target user's data is unchanged after denied PATCH."""
        user_a, key_a = _make_pro_user(db_engine, email="a@test.com")
        user_b, key_b = _make_pro_user(db_engine, email="b@test.com")

        # Attempt to modify user_b with user_a's key
        client.patch(
            f"/users/{user_b.id}",
            json={"name": "Hacked"},
            headers={"X-API-Key": key_a},
        )

        # Verify user_b's name unchanged
        resp = client.get(
            f"/users/{user_b.id}",
            headers={"X-API-Key": key_b},
        )
        assert resp.status_code == 200
        assert resp.json()["name"] == ""  # default, not "Hacked"

    # ── GET /users/{id}/briefings ───────────────────────────────────

    def test_user_can_list_own_briefings(self, client, db_engine):
        user, key = _make_pro_user(db_engine)
        _make_briefing(db_engine, user.id)
        resp = client.get(
            f"/users/{user.id}/briefings",
            headers={"X-API-Key": key},
        )
        assert resp.status_code == 200
        assert len(resp.json()) == 1

    def test_user_cannot_list_other_briefings(self, client, db_engine):
        user_a, key_a = _make_pro_user(db_engine, email="a@test.com")
        user_b, _ = _make_pro_user(db_engine, email="b@test.com")
        _make_briefing(db_engine, user_b.id)
        resp = client.get(
            f"/users/{user_b.id}/briefings",
            headers={"X-API-Key": key_a},
        )
        assert resp.status_code == 403

    # ── GET /users/{id}/briefings/{bid} ─────────────────────────────

    def test_user_can_read_own_briefing_detail(self, client, db_engine):
        user, key = _make_pro_user(db_engine)
        b = _make_briefing(db_engine, user.id)
        resp = client.get(
            f"/users/{user.id}/briefings/{b.id}",
            headers={"X-API-Key": key},
        )
        assert resp.status_code == 200
        assert resp.json()["content_html"] == "<p>News</p>"

    def test_user_cannot_read_other_briefing_detail(self, client, db_engine):
        user_a, key_a = _make_pro_user(db_engine, email="a@test.com")
        user_b, _ = _make_pro_user(db_engine, email="b@test.com")
        b = _make_briefing(db_engine, user_b.id)
        resp = client.get(
            f"/users/{user_b.id}/briefings/{b.id}",
            headers={"X-API-Key": key_a},
        )
        assert resp.status_code == 403

    # ── POST /users/{id}/briefings ──────────────────────────────────

    def test_user_cannot_trigger_other_briefing(self, client, db_engine):
        user_a, key_a = _make_pro_user(db_engine, email="a@test.com")
        user_b, _ = _make_pro_user(db_engine, email="b@test.com")
        resp = client.post(
            f"/users/{user_b.id}/briefings",
            headers={"X-API-Key": key_a},
        )
        assert resp.status_code == 403

    # ── Public endpoints remain unscoped ────────────────────────────

    def test_public_endpoints_no_scoping(self, client):
        """Public endpoints must not require auth or scoping."""
        assert client.get("/health").status_code == 200
        assert client.get("/sources").status_code == 200
        assert client.get("/stories").status_code == 200

    def test_user_registration_is_public(self, client):
        resp = client.post("/users", json={
            "email": "newuser@test.com",
            "interests": "finance",
        })
        assert resp.status_code == 201

    # ── Engagement endpoint ─────────────────────────────────────────

    def test_engagement_requires_auth_but_not_path_scoping(self, client, db_engine):
        """POST /engagements checks auth but user_id is in body, not path."""
        user, key = _make_pro_user(db_engine)
        cluster = _make_cluster(db_engine)
        resp = client.post(
            "/engagements",
            json={
                "user_id": user.id,
                "cluster_id": cluster.id,
                "action": "read",
            },
            headers={"X-API-Key": key},
        )
        assert resp.status_code == 201

    # ── Edge cases ──────────────────────────────────────────────────

    def test_nonexistent_user_id_returns_403_not_404(self, client, db_engine):
        """If auth user exists but target user_id doesn't, 403 before 404."""
        user, key = _make_pro_user(db_engine)
        resp = client.get(
            "/users/99999",
            headers={"X-API-Key": key},
        )
        # auth_user.id != 99999 → 403
        assert resp.status_code == 403

    def test_free_user_gets_403_pro_required_before_scoping(self, client, db_engine):
        """Free user should get 403 (not pro) before scoping check."""
        user, key = _make_free_user(db_engine)
        resp = client.get(
            f"/users/{user.id}",
            headers={"X-API-Key": key},
        )
        assert resp.status_code == 403
        assert "Pro subscription" in resp.json()["detail"]

    def test_scoping_check_uses_auth_user_id(self, client, db_engine):
        """Verify the scoping uses the authenticated user's ID, not key lookup."""
        user_a, key_a = _make_pro_user(db_engine, email="a@test.com")
        user_b, key_b = _make_pro_user(db_engine, email="b@test.com")

        # user_a with own key → own profile → 200
        r1 = client.get(f"/users/{user_a.id}", headers={"X-API-Key": key_a})
        assert r1.status_code == 200

        # user_a with own key → user_b profile → 403
        r2 = client.get(f"/users/{user_b.id}", headers={"X-API-Key": key_a})
        assert r2.status_code == 403

        # user_b with own key → own profile → 200
        r3 = client.get(f"/users/{user_b.id}", headers={"X-API-Key": key_b})
        assert r3.status_code == 200

        # user_b with own key → user_a profile → 403
        r4 = client.get(f"/users/{user_a.id}", headers={"X-API-Key": key_b})
        assert r4.status_code == 403

    def test_all_protected_endpoints_enforce_scoping(self, client, db_engine):
        """Verify every user-scoped endpoint returns 403 for cross-user access."""
        user_a, key_a = _make_pro_user(db_engine, email="a@test.com")
        user_b, _ = _make_pro_user(db_engine, email="b@test.com")
        headers = {"X-API-Key": key_a}
        target = user_b.id

        endpoints = [
            ("GET", f"/users/{target}"),
            ("PATCH", f"/users/{target}"),
            ("GET", f"/users/{target}/briefings"),
            ("GET", f"/users/{target}/briefings/1"),
            ("POST", f"/users/{target}/briefings"),
        ]
        for method, path in endpoints:
            if method == "GET":
                resp = client.get(path, headers=headers)
            elif method == "PATCH":
                resp = client.patch(path, json={"name": "X"}, headers=headers)
            else:
                resp = client.post(path, headers=headers)
            assert resp.status_code == 403, f"{method} {path} returned {resp.status_code}"


# ══════════════════════════════════════════════════════════════════════
# Integration: combined security features
# ══════════════════════════════════════════════════════════════════════


class TestSecurityIntegration:
    """Integration tests combining hashing + scoping + rate limiting."""

    def test_full_auth_flow_with_hashed_key(self, client, db_engine):
        """Create user with hash → auth with raw key → access own data."""
        user, raw_key = _make_pro_user(db_engine)
        _make_briefing(db_engine, user.id)

        # Access own profile
        r1 = client.get(f"/users/{user.id}", headers={"X-API-Key": raw_key})
        assert r1.status_code == 200

        # Access own briefings
        r2 = client.get(f"/users/{user.id}/briefings", headers={"X-API-Key": raw_key})
        assert r2.status_code == 200
        assert len(r2.json()) == 1

    def test_no_auth_on_public_endpoints(self, client):
        """Public endpoints work without any auth header."""
        assert client.get("/health").status_code == 200
        assert client.get("/sources").status_code == 200
        assert client.get("/stories").status_code == 200
        resp = client.post("/users", json={
            "email": "pub@test.com", "interests": "finance",
        })
        assert resp.status_code == 201

    def test_rate_limit_does_not_block_different_auth_states(self, rate_limited_client, db_engine):
        """Rate limit is per IP — both authed and unauthed share the same counter."""
        user, key = _make_pro_user(db_engine)
        # 5 public requests use up the public limit
        for _ in range(5):
            rate_limited_client.get("/health")
        # Even authed request is blocked since IP limit is shared
        resp = rate_limited_client.get(
            f"/users/{user.id}",
            headers={"X-API-Key": key},
        )
        # With auth header, limit is 10, but we already have 5 hits
        # The 6th request (authed) should still be under 10
        assert resp.status_code == 200

    def test_multiple_users_isolated_access(self, client, db_engine):
        """Three users, each can only see their own data."""
        users = []
        for i in range(3):
            u, k = _make_pro_user(db_engine, email=f"user{i}@test.com")
            _make_briefing(db_engine, u.id)
            users.append((u, k))

        for i, (user, key) in enumerate(users):
            # Can access own
            r = client.get(f"/users/{user.id}", headers={"X-API-Key": key})
            assert r.status_code == 200

            # Cannot access others
            for j, (other, _) in enumerate(users):
                if i != j:
                    r = client.get(
                        f"/users/{other.id}",
                        headers={"X-API-Key": key},
                    )
                    assert r.status_code == 403
