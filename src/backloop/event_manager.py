import asyncio
import time
from typing import Dict, List, Any, Set
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import uuid


class EventType(Enum):
    """Types of server-side events."""

    COMMENT_DEQUEUED = "comment_dequeued"
    COMMENT_RESOLVED = "comment_resolved"
    FILE_CHANGED = "file_changed"
    FILE_REMOVED = "file_removed"
    REVIEW_APPROVED = "review_approved"
    REVIEW_UPDATED = "review_updated"


@dataclass
class Event:
    """Represents a server-side event."""

    id: str
    type: EventType
    data: Dict[str, Any]
    timestamp: float
    review_id: str | None = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert event to dictionary for JSON serialization."""
        return {
            "id": self.id,
            "type": self.type.value,
            "data": self.data,
            "timestamp": self.timestamp,
            "review_id": self.review_id,
        }


@dataclass
class EventSubscriber:
    """Represents a subscriber waiting for events."""

    id: str
    event: asyncio.Event
    events: List[Event] = field(default_factory=list)
    last_event_id: str | None = None
    created_at: float = field(default_factory=time.time)
    review_id: str | None = None


class EventManager:
    """Manages server-side events and long-polling subscriptions."""

    def __init__(self, event_ttl: float = 60.0) -> None:
        """Initialize the event manager.

        Args:
            event_ttl: Time-to-live for events in seconds (default 60s)
        """
        self._events: List[Event] = []
        self._subscribers: Dict[str, EventSubscriber] = {}
        self._event_ttl = event_ttl
        self._lock = asyncio.Lock()

    async def emit_event(
        self, event_type: EventType, data: Dict[str, Any], review_id: str | None = None
    ) -> Event:
        """Emit a new event and notify subscribers.

        Args:
            event_type: Type of the event
            data: Event data
            review_id: Optional review ID this event is associated with

        Returns:
            The created event
        """
        async with self._lock:
            # Create the event
            event = Event(
                id=str(uuid.uuid4()),
                type=event_type,
                data=data,
                timestamp=time.time(),
                review_id=review_id,
            )

            # Add to event history
            self._events.append(event)

            # Clean up old events
            self._cleanup_old_events()

            # Notify subscribers
            for subscriber in list(self._subscribers.values()):
                if subscriber.review_id is None or subscriber.review_id == review_id:
                    subscriber.events.append(event)
                    subscriber.event.set()

            return event

    async def subscribe(
        self, last_event_id: str | None = None, review_id: str | None = None
    ) -> EventSubscriber:
        """Subscribe to events.

        Args:
            last_event_id: ID of the last event the client received (for catch-up)

        Returns:
            A new subscriber
        """
        async with self._lock:
            subscriber = EventSubscriber(
                id=str(uuid.uuid4()),
                event=asyncio.Event(),
                last_event_id=last_event_id,
                review_id=review_id,
            )

            # If last_event_id is provided, catch up on missed events
            if last_event_id:
                found_last = False
                for event in self._events:
                    if subscriber.review_id is not None and event.review_id != subscriber.review_id:
                        continue
                    if found_last:
                        subscriber.events.append(event)
                    elif event.id == last_event_id:
                        found_last = True

            self._subscribers[subscriber.id] = subscriber
            return subscriber

    async def unsubscribe(self, subscriber_id: str) -> None:
        """Unsubscribe from events.

        Args:
            subscriber_id: ID of the subscriber to remove
        """
        async with self._lock:
            self._subscribers.pop(subscriber_id, None)

    async def wait_for_events(
        self, subscriber: EventSubscriber, timeout: float = 30.0
    ) -> List[Event]:
        """Wait for events for a subscriber.

        Args:
            subscriber: The subscriber to wait for
            timeout: Maximum time to wait in seconds

        Returns:
            List of events (may be empty if timeout)
        """
        # If there are already events, return them immediately
        if subscriber.events:
            events = subscriber.events[:]
            subscriber.events.clear()
            if events:
                subscriber.last_event_id = events[-1].id
            return events

        # Wait for new events with timeout
        try:
            await asyncio.wait_for(subscriber.event.wait(), timeout=timeout)
        except asyncio.TimeoutError:
            # Timeout is normal for long-polling
            pass

        # Clear the event flag
        subscriber.event.clear()

        # Return any events that were added
        events = subscriber.events[:]
        subscriber.events.clear()
        if events:
            subscriber.last_event_id = events[-1].id

        return events

    def _cleanup_old_events(self) -> None:
        """Remove events older than TTL."""
        current_time = time.time()
        self._events = [
            event
            for event in self._events
            if current_time - event.timestamp < self._event_ttl
        ]

    async def cleanup_stale_subscribers(self, max_age: float = 120.0) -> None:
        """Remove subscribers that have been inactive for too long.

        Args:
            max_age: Maximum age in seconds before a subscriber is considered stale
        """
        async with self._lock:
            current_time = time.time()
            stale_ids = [
                sub_id
                for sub_id, sub in self._subscribers.items()
                if current_time - sub.created_at > max_age
            ]
            for sub_id in stale_ids:
                del self._subscribers[sub_id]
