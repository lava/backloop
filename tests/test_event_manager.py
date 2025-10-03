"""Unit tests for EventManager."""

import asyncio
import time
import pytest

from backloop.event_manager import EventManager, EventType, Event


class TestEventManager:
    """Test suite for EventManager."""

    def test_init(self) -> None:
        """Test EventManager initialization."""
        manager = EventManager()
        assert manager._events == []
        assert manager._subscribers == {}
        assert manager._event_ttl == 60.0

    def test_init_with_custom_ttl(self) -> None:
        """Test EventManager initialization with custom TTL."""
        manager = EventManager(event_ttl=120.0)
        assert manager._event_ttl == 120.0

    async def test_emit_event(self) -> None:
        """Test emitting an event."""
        manager = EventManager()

        event = await manager.emit_event(
            EventType.COMMENT_DEQUEUED,
            {"comment_id": "123"},
            review_id="review-1",
        )

        assert isinstance(event, Event)
        assert event.type == EventType.COMMENT_DEQUEUED
        assert event.data == {"comment_id": "123"}
        assert event.review_id == "review-1"
        assert event.id is not None
        assert event.timestamp > 0

    async def test_emit_event_adds_to_history(self) -> None:
        """Test that emitted events are added to history."""
        manager = EventManager()

        await manager.emit_event(
            EventType.COMMENT_DEQUEUED,
            {"comment_id": "123"},
        )

        assert len(manager._events) == 1

    async def test_subscribe(self) -> None:
        """Test subscribing to events."""
        manager = EventManager()

        subscriber = await manager.subscribe()

        assert subscriber.id is not None
        assert subscriber.event is not None
        assert subscriber.events == []
        assert subscriber.last_event_id is None

    async def test_subscribe_with_catchup(self) -> None:
        """Test subscribing with catch-up from last event ID."""
        manager = EventManager()

        # Emit some events
        event1 = await manager.emit_event(
            EventType.COMMENT_DEQUEUED, {"comment_id": "1"}
        )
        event2 = await manager.emit_event(
            EventType.COMMENT_DEQUEUED, {"comment_id": "2"}
        )
        event3 = await manager.emit_event(
            EventType.COMMENT_DEQUEUED, {"comment_id": "3"}
        )

        # Subscribe from event1
        subscriber = await manager.subscribe(last_event_id=event1.id)

        # Should have event2 and event3 in queue
        assert len(subscriber.events) == 2
        assert subscriber.events[0].id == event2.id
        assert subscriber.events[1].id == event3.id

    async def test_unsubscribe(self) -> None:
        """Test unsubscribing from events."""
        manager = EventManager()

        subscriber = await manager.subscribe()
        subscriber_id = subscriber.id

        assert subscriber_id in manager._subscribers

        await manager.unsubscribe(subscriber_id)

        assert subscriber_id not in manager._subscribers

    async def test_unsubscribe_nonexistent(self) -> None:
        """Test unsubscribing a non-existent subscriber doesn't raise."""
        manager = EventManager()

        # Should not raise
        await manager.unsubscribe("nonexistent-id")

    async def test_wait_for_events_immediate(self) -> None:
        """Test wait_for_events returns immediately if events are queued."""
        manager = EventManager()

        # Subscribe and add an event to the subscriber's queue
        subscriber = await manager.subscribe()
        await manager.emit_event(EventType.COMMENT_DEQUEUED, {"comment_id": "123"})

        # Should return immediately
        start = time.time()
        events = await manager.wait_for_events(subscriber, timeout=10.0)
        elapsed = time.time() - start

        assert len(events) == 1
        assert elapsed < 1.0  # Should be nearly instant
        assert events[0].data == {"comment_id": "123"}

    async def test_wait_for_events_timeout(self) -> None:
        """Test wait_for_events times out if no events."""
        manager = EventManager()

        subscriber = await manager.subscribe()

        # Should timeout after specified duration
        start = time.time()
        events = await manager.wait_for_events(subscriber, timeout=0.5)
        elapsed = time.time() - start

        assert len(events) == 0
        assert 0.4 < elapsed < 0.7  # Allow some tolerance

    async def test_wait_for_events_updates_last_event_id(self) -> None:
        """Test that wait_for_events updates last_event_id."""
        manager = EventManager()

        subscriber = await manager.subscribe()
        event = await manager.emit_event(
            EventType.COMMENT_DEQUEUED, {"comment_id": "123"}
        )

        events = await manager.wait_for_events(subscriber, timeout=1.0)

        assert subscriber.last_event_id == event.id

    async def test_emit_event_notifies_subscribers(self) -> None:
        """Test that emitting an event notifies all subscribers."""
        manager = EventManager()

        # Create multiple subscribers
        sub1 = await manager.subscribe()
        sub2 = await manager.subscribe()

        # Emit event
        await manager.emit_event(EventType.COMMENT_DEQUEUED, {"comment_id": "123"})

        # Both subscribers should have the event
        assert len(sub1.events) == 1
        assert len(sub2.events) == 1

    async def test_wait_for_events_clears_queue(self) -> None:
        """Test that wait_for_events clears the event queue."""
        manager = EventManager()

        subscriber = await manager.subscribe()
        await manager.emit_event(EventType.COMMENT_DEQUEUED, {"comment_id": "1"})
        await manager.emit_event(EventType.COMMENT_DEQUEUED, {"comment_id": "2"})

        # First call should return both events
        events = await manager.wait_for_events(subscriber, timeout=1.0)
        assert len(events) == 2

        # Queue should be cleared
        assert len(subscriber.events) == 0

    async def test_wait_for_events_concurrent(self) -> None:
        """Test concurrent wait_for_events from multiple subscribers."""
        manager = EventManager()

        sub1 = await manager.subscribe()
        sub2 = await manager.subscribe()

        # Start both waiting
        task1 = asyncio.create_task(manager.wait_for_events(sub1, timeout=5.0))
        task2 = asyncio.create_task(manager.wait_for_events(sub2, timeout=5.0))

        # Give them time to start waiting
        await asyncio.sleep(0.1)

        # Emit event
        event = await manager.emit_event(
            EventType.COMMENT_DEQUEUED, {"comment_id": "123"}
        )

        # Both should receive the event
        events1 = await task1
        events2 = await task2

        assert len(events1) == 1
        assert len(events2) == 1
        assert events1[0].id == event.id
        assert events2[0].id == event.id

    async def test_cleanup_old_events(self) -> None:
        """Test that old events are cleaned up."""
        manager = EventManager(event_ttl=0.5)

        # Emit an event
        event1 = await manager.emit_event(
            EventType.COMMENT_DEQUEUED, {"comment_id": "1"}
        )

        assert len(manager._events) == 1

        # Wait for TTL to expire
        await asyncio.sleep(0.6)

        # Emit another event to trigger cleanup
        event2 = await manager.emit_event(
            EventType.COMMENT_DEQUEUED, {"comment_id": "2"}
        )

        # Old event should be cleaned up
        assert len(manager._events) == 1
        assert manager._events[0].id == event2.id

    async def test_cleanup_stale_subscribers(self) -> None:
        """Test cleanup of stale subscribers."""
        manager = EventManager()

        # Create a subscriber
        sub = await manager.subscribe()

        # Manually set old creation time
        sub.created_at = time.time() - 200.0

        assert len(manager._subscribers) == 1

        # Cleanup with max_age=120
        await manager.cleanup_stale_subscribers(max_age=120.0)

        # Stale subscriber should be removed
        assert len(manager._subscribers) == 0

    async def test_cleanup_stale_subscribers_keeps_active(self) -> None:
        """Test that cleanup keeps active subscribers."""
        manager = EventManager()

        # Create subscribers
        old_sub = await manager.subscribe()
        new_sub = await manager.subscribe()

        # Make one old
        old_sub.created_at = time.time() - 200.0

        # Cleanup
        await manager.cleanup_stale_subscribers(max_age=120.0)

        # Only new subscriber should remain
        assert len(manager._subscribers) == 1
        assert new_sub.id in manager._subscribers

    async def test_event_to_dict(self) -> None:
        """Test Event.to_dict() serialization."""
        manager = EventManager()

        event = await manager.emit_event(
            EventType.FILE_CHANGED,
            {"file_path": "test.txt"},
            review_id="review-1",
        )

        event_dict = event.to_dict()

        assert event_dict["id"] == event.id
        assert event_dict["type"] == "file_changed"
        assert event_dict["data"] == {"file_path": "test.txt"}
        assert event_dict["review_id"] == "review-1"
        assert event_dict["timestamp"] == event.timestamp

    async def test_multiple_event_types(self) -> None:
        """Test handling multiple event types."""
        manager = EventManager()

        subscriber = await manager.subscribe()

        # Emit different event types
        await manager.emit_event(EventType.COMMENT_DEQUEUED, {"comment_id": "1"})
        await manager.emit_event(EventType.FILE_CHANGED, {"file_path": "test.txt"})
        await manager.emit_event(EventType.REVIEW_APPROVED, {"review_id": "r1"})

        events = await manager.wait_for_events(subscriber, timeout=1.0)

        assert len(events) == 3
        assert events[0].type == EventType.COMMENT_DEQUEUED
        assert events[1].type == EventType.FILE_CHANGED
        assert events[2].type == EventType.REVIEW_APPROVED

    async def test_subscribe_adds_to_subscribers_dict(self) -> None:
        """Test that subscribe adds subscriber to the manager's dict."""
        manager = EventManager()

        assert len(manager._subscribers) == 0

        sub1 = await manager.subscribe()
        assert len(manager._subscribers) == 1
        assert sub1.id in manager._subscribers

        sub2 = await manager.subscribe()
        assert len(manager._subscribers) == 2
        assert sub2.id in manager._subscribers
