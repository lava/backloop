import asyncio
from typing import Dict

from backloop.review_session import ReviewSession
from backloop.event_manager import EventManager, EventType


class ReviewService:
    """Manages the lifecycle of review sessions and their live updates."""

    def __init__(self, event_manager: EventManager) -> None:
        """Initialize the review service."""
        self.active_reviews: Dict[str, ReviewSession] = {}
        self._event_manager = event_manager
        self._event_listener_task: asyncio.Task | None = None

    def create_review_session(
        self,
        commit: str | None = None,
        range: str | None = None,
        since: str | None = None,
    ) -> ReviewSession:
        """Create a new review session and store it."""
        review_session = ReviewSession(commit=commit, range=range, since=since)
        self.active_reviews[review_session.id] = review_session
        return review_session

    def get_review_session(self, review_id: str) -> ReviewSession | None:
        """Get a review session by ID."""
        return self.active_reviews.get(review_id)

    def get_most_recent_review(self) -> ReviewSession | None:
        """Get the most recently created review session."""
        if not self.active_reviews:
            return None
        return max(self.active_reviews.values(), key=lambda r: r.created_at)

    def remove_review_session(self, review_id: str) -> bool:
        """Remove a review session."""
        if review_id in self.active_reviews:
            del self.active_reviews[review_id]
            return True
        return False

    async def _event_listener(self) -> None:
        """Listen for events and update review sessions accordingly."""
        subscriber = await self._event_manager.subscribe()
        try:
            while True:
                events = await self._event_manager.wait_for_events(subscriber)
                for event in events:
                    if event.type == EventType.FILE_CHANGED:
                        print(f"[DEBUG] File changed event detected: {event.data}")
                        for review in self.active_reviews.values():
                            if review.is_live:
                                print(f"[DEBUG] Refreshing diff for live review: {review.id}")
                                review.refresh_diff()
                                # Notify clients that the review has been updated
                                await self._event_manager.emit_event(
                                    EventType.REVIEW_UPDATED,
                                    {"review_id": review.id},
                                    review_id=review.id,
                                )
        finally:
            await self._event_manager.unsubscribe(subscriber.id)

    def start_event_listener(self) -> None:
        """Start the background task for listening to events."""
        if self._event_listener_task is None:
            self._event_listener_task = asyncio.create_task(self._event_listener())

    def stop_event_listener(self) -> None:
        """Stop the background event listener task."""
        if self._event_listener_task:
            self._event_listener_task.cancel()
            self._event_listener_task = None