import asyncio
from typing import Dict, Union
from datetime import datetime

from backloop.models import Comment, ReviewApproved, CommentStatus
from backloop.config import settings
from backloop.event_manager import EventManager, EventType
from backloop.services.review_service import ReviewService


class McpService:
    """Manages MCP server interactions, like comment queuing and approvals."""

    def __init__(self, review_service: ReviewService, event_manager: EventManager, loop: asyncio.AbstractEventLoop | None = None) -> None:
        """Initialize the MCP service."""
        self._review_service = review_service
        self._event_manager = event_manager
        self._event_loop = loop
        self._pending_comments: asyncio.Queue[Comment] = asyncio.Queue()
        self._review_approved: Dict[str, bool] = {}

    @property
    def review_approved(self) -> Dict[str, bool]:
        """Expose review approval state for coordination with other services."""
        return self._review_approved

    def add_comment_to_queue(self, comment: Comment) -> None:
        """Add a comment to the pending queue for the MCP server."""
        if settings.debug:
            print(f"[DEBUG] Adding comment to MCP queue: {comment.id}")

        def enqueue() -> None:
            self._pending_comments.put_nowait(comment)

        if self._event_loop:
            self._event_loop.call_soon_threadsafe(enqueue)
        else:
            enqueue()

    def approve_review(self, review_id: str) -> None:
        """Mark a review as approved."""
        if settings.debug:
            print(f"[DEBUG] Marking review {review_id} as approved in MCP service")
        self._review_approved[review_id] = True

    async def await_comments(self) -> Union[Comment, ReviewApproved]:
        """Wait for a comment to be posted or for a review to be approved."""
        if settings.debug:
            print("[DEBUG] MCP service awaiting comments...")

        current_review = self._review_service.get_most_recent_review()
        current_review_id = current_review.id if current_review else None

        while True:
            # Check if any approved review has no pending comments
            if not self._pending_comments.empty():
                # Prioritize draining the queue
                pass
            else:
                # Only return approved if it matches the current review
                if current_review_id and self._review_approved.get(current_review_id):
                    # Clear the approval flag
                    del self._review_approved[current_review_id]
                    return ReviewApproved(review_id=current_review_id, timestamp=datetime.now().isoformat())

            try:
                comment = await asyncio.wait_for(self._pending_comments.get(), timeout=1.0)
                if settings.debug:
                    print(f"[DEBUG] Dequeued comment {comment.id} for processing")

                review_session = self._review_service.get_review_session(comment.review_id)
                if review_session:
                    review_session.comment_service.update_comment_status(
                        comment.id, CommentStatus.IN_PROGRESS
                    )
                    # This might be redundant if the agent resolves it, but good for UI
                    await self._event_manager.emit_event(
                        EventType.COMMENT_DEQUEUED,
                        {"comment_id": comment.id, "status": CommentStatus.IN_PROGRESS.value},
                        review_id=comment.review_id,
                    )
                return comment

            except asyncio.TimeoutError:
                continue
