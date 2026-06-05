# 04_05 — Agent-to-WebSocket Bridge & Graceful Shutdown

**Parent:** 04 Async FastAPI + WebSocket
**Depends on:** 04_04 (ConnectionManager and channels)

---

## Objective

Connect the synchronous APScheduler agent cycles to the async WebSocket
broadcast system. When an agent completes work (new story analyzed, briefing
generated, perception computed), the event is pushed to connected WebSocket
clients in real-time. Also implement graceful shutdown that cleanly closes
all connections.

---

## Problem

Agent cycles run in APScheduler **threads** (synchronous). WebSocket
broadcast runs on the **asyncio event loop**. Calling `await` from a
thread raises `RuntimeError`. Calling sync from the event loop blocks it.

```
APScheduler thread                 asyncio event loop
  analysis_cycle()                   ConnectionManager.broadcast()
  ← sync, cannot await ─────X────→ ← async, must await
```

---

## Solution: Thread-Safe Event Queue

Use `asyncio.Queue` as a bridge. Threads put events; an async consumer
task broadcasts them.

```
APScheduler thread          Queue              Async consumer task
      |                      |                        |
      |-- put_nowait(event)->|                        |
      |                      |------ await get() ---->|
      |                      |                        |-- broadcast()
      |                      |                        |       |
      |                      |                        |       v
      |                      |                        |   WS clients
```

---

## Implementation

### File: `src/prism/api/events.py`

```python
"""Thread-safe bridge between sync agent cycles and async WebSocket broadcasts."""

import asyncio
import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class PipelineEvent:
    """An event emitted by an agent cycle for WebSocket broadcast."""
    channel: str              # "stories", "briefings:5", "perception"
    data: dict[str, Any]      # JSON-serializable payload
    user_id: int | None = None  # for per-user delivery (briefings)


# Module-level queue — shared between threads and async tasks
_queue: asyncio.Queue[PipelineEvent] | None = None
_consumer_task: asyncio.Task | None = None


def _get_queue() -> asyncio.Queue[PipelineEvent]:
    """Get the event queue, creating if needed."""
    global _queue
    if _queue is None:
        _queue = asyncio.Queue(maxsize=1000)
    return _queue


def publish_event(event: PipelineEvent) -> None:
    """Publish an event from any thread (sync-safe).

    Called by agent cycles after completing work. Non-blocking:
    drops the event if the queue is full (degraded, not fatal).
    """
    queue = _get_queue()
    try:
        queue.put_nowait(event)
        logger.debug("Event published: channel=%s", event.channel)
    except asyncio.QueueFull:
        logger.warning("Event queue full — dropping event: %s", event.channel)


async def start_consumer() -> None:
    """Start the async consumer that reads events and broadcasts.

    Called once during FastAPI startup.
    """
    global _consumer_task
    _consumer_task = asyncio.create_task(_consume_events())
    logger.info("WebSocket event consumer started")


async def stop_consumer() -> None:
    """Stop the consumer task (called on shutdown)."""
    global _consumer_task
    if _consumer_task is not None:
        _consumer_task.cancel()
        try:
            await _consumer_task
        except asyncio.CancelledError:
            pass
        _consumer_task = None
        logger.info("WebSocket event consumer stopped")


async def _consume_events() -> None:
    """Read events from queue and broadcast via ConnectionManager."""
    from prism.api.websocket import manager

    queue = _get_queue()

    while True:
        try:
            event = await queue.get()

            if event.user_id is not None:
                # Per-user delivery (briefings)
                await manager.send_to_user(
                    event.channel, event.user_id, event.data
                )
            else:
                # Broadcast to all on channel
                await manager.broadcast(event.channel, event.data)

            queue.task_done()

        except asyncio.CancelledError:
            break
        except Exception:
            logger.exception("Error broadcasting event")
```

### Event Publishing from Agents

Add `publish_event` calls at the end of each agent cycle.

#### A_AI — After Analyzing a Cluster

In `src/prism/agents/a_ai.py`, after setting `cluster.status = ANALYZED`:

```python
from prism.api.events import PipelineEvent, publish_event

# After analysis completes for a cluster:
publish_event(PipelineEvent(
    channel="stories",
    data={
        "type": "story",
        "cluster_id": cluster.id,
        "headline": cluster.headline,
        "resonance_score": cluster.resonance_score,
        "categories": cluster.categories,
        "article_count": cluster.article_count,
        "first_seen": cluster.first_seen.isoformat(),
    },
))
```

#### W_AI — After Generating a Briefing

In `src/prism/agents/w_ai.py`, after briefing is committed:

```python
publish_event(PipelineEvent(
    channel=f"briefings:{user.id}",
    user_id=user.id,
    data={
        "type": "briefing",
        "briefing_id": briefing.id,
        "story_count": briefing.story_count,
        "has_audio": bool(briefing.audio_path),
        "created_at": briefing.created_at.isoformat(),
    },
))
```

#### R_AI — After Computing Perception Snapshots

In `src/prism/agents/r_ai.py`, after storing a `PerceptionSnapshot`:

```python
publish_event(PipelineEvent(
    channel="perception",
    data={
        "type": "perception",
        "keyword_id": snapshot.keyword_id,
        "keyword": keyword.keyword,
        "perception": snapshot.perception,
        "salience": snapshot.salience,
        "valence": snapshot.valence,
        "momentum": snapshot.momentum,
        "cluster_count": snapshot.cluster_count,
        "source_count": snapshot.source_count,
        "computed_at": snapshot.computed_at.isoformat(),
    },
))
```

---

## Queue Sizing

`maxsize=1000` — if 1000 events accumulate without being consumed (e.g., no
WebSocket clients connected), new events are dropped with a warning log.

**Typical throughput:**
- A_AI: ~50 stories/cycle × 12 cycles/day = ~600 events/day
- R_AI: ~10 keywords × 48 scans/day = ~480 events/day
- W_AI: ~100 users × 1 briefing/day = ~100 events/day
- Peak: ~1,180 events/day, ~0.01 events/second — queue never fills

---

## App Lifecycle Integration

Update `src/prism/api/app.py`:

```python
from prism.api.events import start_consumer, stop_consumer
from prism.api.websocket import manager
from prism.db import close_async_engine

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    await start_consumer()
    yield
    # Shutdown
    await stop_consumer()
    await manager.close_all(code=1001, reason="Server shutting down")
    await close_async_engine()
```

---

## Graceful Shutdown Sequence

```
1. SIGTERM received
   └─→ uvicorn begins shutdown

2. FastAPI lifespan __aexit__ runs:
   a. stop_consumer()
      └─→ Cancel consumer task, drain remaining events
   b. manager.close_all(code=1001)
      └─→ Send 1001 "Going Away" to all WebSocket clients
      └─→ Clients see onclose event, can auto-reconnect
   c. close_async_engine()
      └─→ Dispose async DB connections

3. uvicorn completes:
   └─→ Wait for in-flight HTTP requests (graceful_timeout, default 30s)
   └─→ Close listening socket
   └─→ Process exits

4. APScheduler shutdown (in main.py, unchanged):
   └─→ scheduler.shutdown(wait=False)
```

**Docker integration:** `docker-compose.prod.yml` already sends SIGTERM with
a 30-second grace period (`stop_grace_period: 30s`). This is sufficient for
the shutdown sequence above.

---

## Frontend Reconnection

When clients receive close code 1001 (server shutdown), they should
auto-reconnect with exponential backoff:

```typescript
// In frontend WebSocket hook
function useWebSocket(url: string) {
  const [ws, setWs] = useState<WebSocket | null>(null)
  const reconnectDelay = useRef(1000) // start at 1s

  function connect() {
    const socket = new WebSocket(url)

    socket.onclose = (event) => {
      if (event.code === 1001 || event.code === 1006) {
        // Server shutdown or abnormal close — reconnect
        setTimeout(() => {
          reconnectDelay.current = Math.min(reconnectDelay.current * 2, 30000)
          connect()
        }, reconnectDelay.current)
      }
    }

    socket.onopen = () => {
      reconnectDelay.current = 1000 // reset on successful connect
    }

    setWs(socket)
  }

  useEffect(() => { connect(); return () => ws?.close() }, [])
  return ws
}
```

---

## Acceptance Criteria

| # | Criterion | Verification |
|---|-----------|--------------|
| 1 | A_AI analysis pushes story event to `/ws/stories` | Connect WS, run analysis cycle, verify event received |
| 2 | W_AI briefing pushes event to `/ws/briefings/{id}` | Connect WS, trigger briefing, verify event received |
| 3 | R_AI scan pushes perception event to `/ws/perception` | Connect WS, run perception cycle, verify event received |
| 4 | Events are JSON with correct `type` field | Parse received message, verify schema |
| 5 | Per-user briefing event reaches only that user | User 5 and 6 connected, briefing for 5, verify only 5 receives |
| 6 | `publish_event` is non-blocking from agent thread | Time the call, verify <1ms |
| 7 | Queue full drops event with warning (no crash) | Fill queue to 1000, publish 1001st, verify warning log |
| 8 | Consumer stops cleanly on shutdown | Send SIGTERM, verify no error logs |
| 9 | All WS clients receive 1001 on shutdown | Connect 3 clients, send SIGTERM, verify all get 1001 |
| 10 | Agent cycles work without WS clients | Run analysis with 0 WS connections, verify no error |
| 11 | Consumer handles broadcast errors gracefully | Kill client mid-broadcast, verify consumer continues |
| 12 | Frontend auto-reconnects after 1001 | Restart server, verify client reconnects within 5s |

---

## Testing Strategy

### Unit Tests

```python
def test_publish_event_non_blocking():
    """publish_event returns immediately."""
    import time
    start = time.monotonic()
    publish_event(PipelineEvent(channel="test", data={"type": "test"}))
    elapsed = time.monotonic() - start
    assert elapsed < 0.01  # <10ms

def test_publish_event_drops_when_full():
    """Events dropped when queue is full."""
    queue = _get_queue()
    for _ in range(1000):
        queue.put_nowait(PipelineEvent(channel="x", data={}))
    # 1001st should not raise
    publish_event(PipelineEvent(channel="x", data={}))
    assert queue.qsize() == 1000

@pytest.mark.asyncio
async def test_consumer_broadcasts(mock_manager):
    """Consumer reads from queue and calls broadcast."""
    queue = _get_queue()
    await queue.put(PipelineEvent(
        channel="stories",
        data={"type": "story", "cluster_id": 1}
    ))
    # Start consumer, let it process one event, then cancel
    task = asyncio.create_task(_consume_events())
    await asyncio.sleep(0.1)
    task.cancel()
    mock_manager.broadcast.assert_called_once_with(
        "stories", {"type": "story", "cluster_id": 1}
    )

@pytest.mark.asyncio
async def test_consumer_routes_user_events(mock_manager):
    """Per-user events use send_to_user."""
    queue = _get_queue()
    await queue.put(PipelineEvent(
        channel="briefings:5",
        user_id=5,
        data={"type": "briefing", "briefing_id": 42}
    ))
    task = asyncio.create_task(_consume_events())
    await asyncio.sleep(0.1)
    task.cancel()
    mock_manager.send_to_user.assert_called_once_with(
        "briefings:5", 5, {"type": "briefing", "briefing_id": 42}
    )
```

### Integration Test

```python
def test_analysis_pushes_ws_event(client, populated_db):
    """Full integration: run analysis cycle, verify WS event arrives."""
    with client.websocket_connect("/ws/stories") as ws:
        # Trigger analysis in background thread
        import threading
        t = threading.Thread(target=analysis_cycle)
        t.start()
        t.join(timeout=30)

        # Check for story event
        data = ws.receive_json(timeout=5)
        assert data["type"] == "story"
        assert "cluster_id" in data
```

---

## Files Changed

| File | Change |
|------|--------|
| `src/prism/api/events.py` | New: event queue, publisher, consumer |
| `src/prism/api/app.py` | Start/stop consumer in lifespan |
| `src/prism/agents/a_ai.py` | Add `publish_event` after analysis |
| `src/prism/agents/w_ai.py` | Add `publish_event` after briefing |
| `src/prism/agents/r_ai.py` | Add `publish_event` after perception |
| `tests/test_events.py` | New test file |
