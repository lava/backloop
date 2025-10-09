"""Test helper implementing a lightweight review manager."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Optional, Union

from backloop.event_manager import EventManager
from backloop.models import Comment, ReviewApproved
from backloop.review_session import ReviewSession
from backloop.services.mcp_service import McpService
from backloop.services.review_service import ReviewService


@dataclass
class PendingComment:
    """Wrapper returned when a comment is dequeued for processing."""

    review_id: str
    comment: Comment


class ReviewManager:
    """Coordinates review sessions, comment queues, and event distribution."""

    def __init__(
        self, loop: Optional[asyncio.AbstractEventLoop] = None
    ) -> None:
        # Use the provided loop or get the running loop (preferred for pytest-asyncio)
        try:
            self.loop = loop or asyncio.get_running_loop()
        except RuntimeError:
            # Fallback for when no loop is running (non-async contexts)
            self.loop = asyncio.get_event_loop()

        self.event_manager = EventManager()
        self.review_service = ReviewService(self.event_manager)
        self.mcp_service = McpService(
            self.review_service, self.event_manager, self.loop
        )
        self._review_approved = self.mcp_service.review_approved

        # Optional dependencies used by certain tests/scripts
        self.file_watcher = None
        self._server: Optional[asyncio.AbstractServer] = None

        # Start background listeners to keep live reviews fresh
        self.review_service.start_event_listener()

    def create_review_session(
        self,
        *,
        commit: Optional[str] = None,
        range: Optional[str] = None,
        since: Optional[str] = None,
        title: Optional[str] = None,
    ) -> ReviewSession:
        return self.review_service.create_review_session(
            commit=commit, range=range, since=since, title=title
        )

    def get_review_session(self, review_id: str) -> Optional[ReviewSession]:
        return self.review_service.get_review_session(review_id)

    def get_most_recent_review(self) -> Optional[ReviewSession]:
        return self.review_service.get_most_recent_review()

    def remove_review_session(self, review_id: str) -> bool:
        return self.review_service.remove_review_session(review_id)

    def add_comment_to_queue(self, review_id: str, comment: Comment) -> None:
        self.mcp_service.add_comment_to_queue(comment)

    async def await_comments(self) -> Union[PendingComment, ReviewApproved]:
        result = await self.mcp_service.await_comments()
        if isinstance(result, ReviewApproved):
            return result
        return PendingComment(review_id=result.review_id, comment=result)

    def approve_review(self, review_id: str) -> None:
        self.mcp_service.approve_review(review_id)

    def shutdown(self) -> None:
        self.review_service.stop_event_listener()
        if self.file_watcher:
            self.file_watcher.stop()
        if self._server:
            self._server.close()
            # Note: we can't wait for closure in sync shutdown
            self._server = None


__all__ = ["PendingComment", "ReviewManager"]
