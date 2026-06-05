# 04_04 — WebSocket Infrastructure & Channels

**Parent:** 04 Async FastAPI + WebSocket
**Depends on:** 04_01 (async engine), 04_02 (async endpoints)

---

## Objective

Implement WebSocket support with three channels: stories (public), briefings
(per-user, authenticated), and perception (authenticated). Includes a
connection manager, authentication, heartbeat, and message schemas.

---

## Architecture

```
                    ┌─────────────────────────┐
                    │   ConnectionManager      │
                    │                         │
                    │  channels:              │
                    │    "stories" → [ws,ws]  │
                    │    "briefings:5" → [ws] │
                    │    "perception" → [ws]  │
                    └─────────┬───────────────┘
                              │
              ┌───────────────┼───────────────┐
              │               │               │
        WS /ws/stories  WS /ws/briefings  WS /ws/perception
        (public)        /{user_id}        (authenticated)
                        (authenticated)
```

---

## File: `src/prism/api/websocket.py`

### ConnectionManager

```python
import asyncio
import logging
import time
from dataclasses import dataclass, field

from fastapi import WebSocket, WebSocketDisconnect

logger = logging.getLogger(__name__)


@dataclass
class _Connection:
    """A tracked WebSocket connection."""
    websocket: WebSocket
    connected_at: float = field(default_factory=time.monotonic)
    last_ping: float = field(default_factory=time.monotonic)
    user_id: int | None = None


class ConnectionManager:
    """Manages WebSocket connections across named channels."""

    def __init__(self) -> None:
        self._channels: dict[str, list[_Connection]] = {}
        self._lock = asyncio.Lock()

    async def connect(
        self,
        channel: str,
        websocket: WebSocket,
        user_id: int | None = None,
    ) -> _Connection:
        """Accept a WebSocket and add it to a channel."""
        await websocket.accept()
        conn = _Connection(websocket=websocket, user_id=user_id)
        async with self._lock:
            self._channels.setdefault(channel, []).append(conn)
        logger.info("WS connected: channel=%s user=%s (total=%d)",
                     channel, user_id, self.connection_count)
        return conn

    async def disconnect(self, channel: str, conn: _Connection) -> None:
        """Remove a connection from a channel."""
        async with self._lock:
            conns = self._channels.get(channel, [])
            if conn in conns:
                conns.remove(conn)
                if not conns:
                    del self._channels[channel]
        logger.info("WS disconnected: channel=%s user=%s", channel, conn.user_id)

    async def broadcast(self, channel: str, data: dict) -> None:
        """Send a message to all connections on a channel."""
        async with self._lock:
            conns = list(self._channels.get(channel, []))

        dead: list[_Connection] = []
        for conn in conns:
            try:
                await conn.websocket.send_json(data)
            except (WebSocketDisconnect, RuntimeError):
                dead.append(conn)

        # Clean up dead connections
        if dead:
            async with self._lock:
                for conn in dead:
                    conns_list = self._channels.get(channel, [])
                    if conn in conns_list:
                        conns_list.remove(conn)

    async def send_to_user(self, channel: str, user_id: int, data: dict) -> None:
        """Send a message to a specific user's connections on a channel."""
        async with self._lock:
            conns = list(self._channels.get(channel, []))

        for conn in conns:
            if conn.user_id == user_id:
                try:
                    await conn.websocket.send_json(data)
                except (WebSocketDisconnect, RuntimeError):
                    pass

    @property
    def connection_count(self) -> int:
        """Total active connections across all channels."""
        return sum(len(c) for c in self._channels.values())

    async def close_all(self, code: int = 1001, reason: str = "Server shutdown") -> None:
        """Close all connections (called on shutdown)."""
        async with self._lock:
            all_conns = [
                (ch, conn)
                for ch, conns in self._channels.items()
                for conn in conns
            ]
            self._channels.clear()

        for channel, conn in all_conns:
            try:
                await conn.websocket.close(code=code, reason=reason)
            except Exception:
                pass

        logger.info("All WebSocket connections closed (%d total)", len(all_conns))


# Module-level singleton
manager = ConnectionManager()
```

---

## WebSocket Authentication

Authenticated channels require an API key. Since WebSocket connections don't
support custom headers in the browser, the key is sent as a query parameter.

```python
from prism.api.routes import hash_api_key
from prism.models import User
from sqlmodel import select


async def authenticate_ws(
    websocket: WebSocket,
    session,  # AsyncSession from dependency
) -> User | None:
    """Authenticate a WebSocket connection via query parameter.

    Usage: ws://host/ws/briefings/5?api_key=prism_xxx
    """
    api_key = websocket.query_params.get("api_key")
    if not api_key:
        await websocket.close(code=4001, reason="Missing api_key parameter")
        return None

    key_hash = hash_api_key(api_key)
    result = await session.exec(
        select(User).where(User.api_key_hash == key_hash)
    )
    user = result.first()

    if user is None:
        await websocket.close(code=4003, reason="Invalid API key")
        return None

    return user
```

**Close codes:**
| Code | Meaning |
|------|---------|
| 4001 | Missing api_key query parameter |
| 4003 | Invalid API key (mirrors HTTP 403) |
| 1001 | Server going away (shutdown) |
| 1000 | Normal closure |

---

## Channel Endpoints

### WS /ws/stories (Public)

No authentication required. Broadcasts new analyzed stories to all connected clients.

```python
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from prism.api.websocket import manager

ws_router = APIRouter()

@ws_router.websocket("/ws/stories")
async def ws_stories(websocket: WebSocket):
    """Public channel: new analyzed stories."""
    conn = await manager.connect("stories", websocket)
    try:
        while True:
            # Keep connection alive — wait for client messages (pings)
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_json({"type": "pong"})
    except WebSocketDisconnect:
        pass
    finally:
        await manager.disconnect("stories", conn)
```

**Message schema (server → client):**

```json
{
  "type": "story",
  "cluster_id": 123,
  "headline": "Fed Holds Rates Steady...",
  "resonance_score": 4.72,
  "categories": "finance,politics",
  "article_count": 8,
  "first_seen": "2026-06-05T03:15:00Z"
}
```

### WS /ws/briefings/{user_id} (Authenticated)

Per-user channel. Notifies when a new briefing is generated.

```python
@ws_router.websocket("/ws/briefings/{user_id}")
async def ws_briefings(websocket: WebSocket, user_id: int):
    """Authenticated channel: new briefing notifications for a user."""
    from prism.db import get_async_session

    async with get_async_session() as session:
        user = await authenticate_ws(websocket, session)
        if user is None:
            return
        if user.id != user_id:
            await websocket.close(code=4003, reason="User ID mismatch")
            return

    channel = f"briefings:{user_id}"
    conn = await manager.connect(channel, websocket, user_id=user_id)
    try:
        while True:
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_json({"type": "pong"})
    except WebSocketDisconnect:
        pass
    finally:
        await manager.disconnect(channel, conn)
```

**Message schema (server → client):**

```json
{
  "type": "briefing",
  "briefing_id": 42,
  "story_count": 10,
  "has_audio": true,
  "created_at": "2026-06-05T06:58:00Z"
}
```

### WS /ws/perception (Authenticated)

Shared channel for all authenticated users. Broadcasts perception updates.

```python
@ws_router.websocket("/ws/perception")
async def ws_perception(websocket: WebSocket):
    """Authenticated channel: perception snapshot updates."""
    from prism.db import get_async_session

    async with get_async_session() as session:
        user = await authenticate_ws(websocket, session)
        if user is None:
            return

    conn = await manager.connect("perception", websocket, user_id=user.id)
    try:
        while True:
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_json({"type": "pong"})
    except WebSocketDisconnect:
        pass
    finally:
        await manager.disconnect("perception", conn)
```

**Message schema (server → client):**

```json
{
  "type": "perception",
  "keyword_id": 7,
  "keyword": "tariffs",
  "perception": -0.35,
  "salience": 2.1,
  "valence": -0.17,
  "momentum": -0.05,
  "cluster_count": 4,
  "source_count": 12,
  "computed_at": "2026-06-05T06:30:00Z"
}
```

---

## Heartbeat

The connection-keeping loop in each endpoint waits for client messages.
Clients should send `"ping"` periodically to keep the connection alive.

**Server-side heartbeat (optional, config-driven):**

```python
from prism.config import settings

HEARTBEAT_SEC = settings.websocket_heartbeat_sec  # default 30

async def _heartbeat_loop(websocket: WebSocket):
    """Send periodic pings to detect dead connections."""
    try:
        while True:
            await asyncio.sleep(HEARTBEAT_SEC)
            await websocket.send_json({"type": "heartbeat"})
    except (WebSocketDisconnect, RuntimeError):
        pass
```

Launch as a background task in each endpoint:

```python
heartbeat_task = asyncio.create_task(_heartbeat_loop(websocket))
try:
    while True:
        data = await websocket.receive_text()
        # ...
except WebSocketDisconnect:
    pass
finally:
    heartbeat_task.cancel()
    await manager.disconnect(channel, conn)
```

---

## Config Addition

Add to `Settings` in `config.py`:

```python
websocket_heartbeat_sec: int = 30     # server heartbeat interval
websocket_max_connections: int = 500   # max total WS connections
```

---

## Register WebSocket Router

In `src/prism/api/app.py`:

```python
from prism.api.websocket import ws_router, manager

def create_app() -> FastAPI:
    app = FastAPI(lifespan=lifespan, ...)
    app.add_middleware(RateLimitMiddleware)
    app.include_router(router)
    app.include_router(ws_router)    # WebSocket routes
    return app

@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    await manager.close_all()        # close all WS on shutdown
    await close_async_engine()
```

---

## Acceptance Criteria

| # | Criterion | Verification |
|---|-----------|--------------|
| 1 | `ws://host/ws/stories` connects without auth | Connect with `websocat`, verify accepted |
| 2 | `ws://host/ws/briefings/5?api_key=xxx` connects with valid key | Connect, verify accepted |
| 3 | Missing api_key closes with 4001 | Connect without key, verify close code 4001 |
| 4 | Invalid api_key closes with 4003 | Connect with bad key, verify close code 4003 |
| 5 | User ID mismatch closes with 4003 | User 5's key connecting to `/ws/briefings/6`, verify 4003 |
| 6 | Client ping receives pong | Send "ping", verify `{"type": "pong"}` received |
| 7 | Server heartbeat arrives every 30s | Connect, wait 35s, verify heartbeat received |
| 8 | Broadcast delivers to all channel subscribers | Connect 3 clients to stories, broadcast, verify all 3 receive |
| 9 | `send_to_user` delivers only to correct user | 2 users on briefings, send to user 5, verify only user 5 receives |
| 10 | Dead connections cleaned up on broadcast failure | Kill client, broadcast, verify no error and connection removed |
| 11 | `close_all` sends 1001 to all connections | Connect 5 clients, call close_all, verify all receive 1001 |
| 12 | `connection_count` property is accurate | Connect 3, disconnect 1, verify count=2 |
| 13 | WebSocket paths excluded from rate limiter | Verified in 04_03 |

---

## Testing Strategy

### Unit Tests

```python
@pytest.mark.asyncio
async def test_connect_and_broadcast():
    """Message reaches all clients on a channel."""
    mgr = ConnectionManager()
    ws1, ws2 = MockWebSocket(), MockWebSocket()
    await mgr.connect("test", ws1)
    await mgr.connect("test", ws2)
    await mgr.broadcast("test", {"type": "hello"})
    assert ws1.sent == [{"type": "hello"}]
    assert ws2.sent == [{"type": "hello"}]

@pytest.mark.asyncio
async def test_send_to_user():
    """Message reaches only the targeted user."""
    mgr = ConnectionManager()
    ws1, ws2 = MockWebSocket(), MockWebSocket()
    await mgr.connect("ch", ws1, user_id=5)
    await mgr.connect("ch", ws2, user_id=6)
    await mgr.send_to_user("ch", 5, {"type": "hello"})
    assert ws1.sent == [{"type": "hello"}]
    assert ws2.sent == []

@pytest.mark.asyncio
async def test_dead_connection_cleanup():
    """Dead connections removed on broadcast."""
    mgr = ConnectionManager()
    ws_dead = MockWebSocket(raise_on_send=True)
    ws_alive = MockWebSocket()
    await mgr.connect("ch", ws_dead)
    await mgr.connect("ch", ws_alive)
    await mgr.broadcast("ch", {"type": "test"})
    assert mgr.connection_count == 1
```

### Integration Tests

```python
def test_ws_stories_connects(client):
    """Public stories WebSocket connects."""
    with client.websocket_connect("/ws/stories") as ws:
        ws.send_text("ping")
        data = ws.receive_json()
        assert data["type"] == "pong"

def test_ws_briefings_auth_required(client):
    """Briefings WebSocket rejects without API key."""
    with pytest.raises(WebSocketDisconnect) as exc:
        with client.websocket_connect("/ws/briefings/5"):
            pass
    assert exc.value.code == 4001
```

---

## Files Changed

| File | Change |
|------|--------|
| `src/prism/api/websocket.py` | New: ConnectionManager + 3 WS endpoints + auth |
| `src/prism/api/app.py` | Register ws_router, close_all in lifespan |
| `src/prism/config.py` | Add `websocket_heartbeat_sec`, `websocket_max_connections` |
| `tests/test_websocket.py` | New test file |
