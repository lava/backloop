import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Tuple

from backloop.models import Comment, CommentRequest, CommentStatus
from backloop.utils.state_dir import get_state_dir


class CommentService:
    """Service for managing comments on diff lines."""

    def __init__(
        self,
        storage_path: str | None = None,
        *,
        default_review_id: str | None = None,
    ) -> None:
        """Initialize with optional storage path and default review context."""
        if storage_path:
            self.storage_path = Path(storage_path)
        else:
            self.storage_path = get_state_dir() / "backloop_comments.json"
        self._default_review_id = default_review_id or "default"
        self._comments: Dict[str, Comment] = self._load_comments()
        self._comment_queue: List[str] = (
            self._rebuild_queue()
        )  # Rebuild queue from loaded comments

    def set_default_review_id(self, review_id: str) -> None:
        """Update the default review identifier used when callers omit it."""
        self._default_review_id = review_id

    def add_comment(
        self, request: CommentRequest, review_id: str | None = None
    ) -> Tuple[Comment, int]:
        """Add a new comment and return it with its queue position."""
        comment_id = str(uuid.uuid4())

        resolved_review_id = review_id or self._default_review_id
        if not resolved_review_id:
            raise ValueError("A review_id must be provided to add a comment")

        # Add to queue and get position (1-indexed for user display)
        self._comment_queue.append(comment_id)
        queue_position = len(self._comment_queue)

        comment = Comment(
            id=comment_id,
            review_id=resolved_review_id,
            file_path=request.file_path,
            line_number=request.line_number,
            side=request.side,
            content=request.content,
            author=request.author,
            timestamp=datetime.now().isoformat(),
            queue_position=queue_position,
        )

        self._comments[comment_id] = comment
        self._save_comments()
        return comment, queue_position

    def get_comments(self, file_path: str | None = None) -> List[Comment]:
        """Get all comments, optionally filtered by file path."""
        comments = list(self._comments.values())
        if file_path:
            comments = [c for c in comments if c.file_path == file_path]
        return sorted(comments, key=lambda c: c.timestamp)

    def get_comment(self, comment_id: str) -> Comment | None:
        """Get a specific comment by ID."""
        return self._comments.get(comment_id)

    def update_comment(self, comment_id: str, content: str) -> Comment | None:
        """Update a comment's content."""
        comment = self._comments.get(comment_id)
        if comment:
            comment.content = content
            comment.timestamp = datetime.now().isoformat()
            self._save_comments()
        return comment

    def delete_comment(self, comment_id: str) -> bool:
        """Delete a comment."""
        if comment_id in self._comments:
            del self._comments[comment_id]
            # Remove from queue if present
            if comment_id in self._comment_queue:
                self._comment_queue.remove(comment_id)
                # Recalculate positions for remaining comments
                self._update_queue_positions()
            self._save_comments()
            return True
        return False

    def get_queue_status(self) -> Dict[str, int]:
        """Get the current queue status with comment IDs and their positions."""
        return {
            comment_id: position + 1
            for position, comment_id in enumerate(self._comment_queue)
        }

    def get_queue_length(self) -> int:
        """Get the current length of the comment queue."""
        return len(self._comment_queue)

    def update_comment_status(
        self, comment_id: str, status: CommentStatus, reply_message: str | None = None
    ) -> Comment | None:
        """Update a comment's status and optionally add a reply message."""
        comment = self._comments.get(comment_id)
        if comment:
            comment.status = status
            if status == CommentStatus.RESOLVED:
                comment.queue_position = None
            if reply_message is not None:
                comment.reply_message = reply_message
            self._save_comments()
        return comment

    def remove_comment_from_queue(self, comment_id: str) -> bool:
        """Remove a comment from the queue and return True if it was removed."""
        if comment_id in self._comment_queue:
            self._comment_queue.remove(comment_id)
            comment = self._comments.get(comment_id)
            if comment:
                comment.queue_position = None
            # Update positions for remaining comments
            self._update_queue_positions()
            self._save_comments()
            return True
        return False

    def _update_queue_positions(self) -> None:
        """Update queue positions for all comments in the queue."""
        for position, comment_id in enumerate(self._comment_queue):
            comment = self._comments.get(comment_id)
            if comment:
                comment.queue_position = position + 1

    def _rebuild_queue(self) -> List[str]:
        """Rebuild the queue from loaded comments that are not resolved."""
        queued_comments = [
            (comment.id, comment.queue_position or 0)
            for comment in self._comments.values()
            if comment.status != CommentStatus.RESOLVED
            and comment.queue_position is not None
        ]
        queued_comments.sort(key=lambda x: x[1])
        return [comment_id for comment_id, _ in queued_comments]

    def _load_comments(self) -> Dict[str, Comment]:
        """Load comments from storage."""
        if not self.storage_path.exists():
            return {}

        try:
            with open(self.storage_path, "r") as f:
                data = json.load(f)
                return {
                    comment_id: Comment(**comment_data)
                    for comment_id, comment_data in data.items()
                }
        except (json.JSONDecodeError, KeyError, TypeError):
            # If file is corrupted, start fresh
            return {}

    def _save_comments(self) -> None:
        """Save comments to storage."""
        # Ensure parent directory exists
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)

        # Convert comments to serializable format
        data = {
            comment_id: comment.model_dump()
            for comment_id, comment in self._comments.items()
        }

        with open(self.storage_path, "w") as f:
            json.dump(data, f, indent=2)
