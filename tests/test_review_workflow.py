"""Integration tests for the complete review workflow."""

import asyncio
from pathlib import Path
import pytest

from backloop.review_manager import ReviewManager, PendingComment
from backloop.models import CommentRequest, CommentStatus, ReviewApproved
from backloop.event_manager import EventType


class TestReviewWorkflow:
    """Test complete review workflows from start to finish."""

    async def test_create_review_session(self, git_repo_with_commits: Path) -> None:
        """Test creating a review session."""
        loop = asyncio.get_event_loop()
        manager = ReviewManager(loop=loop)

        # Create a review session for the latest commit
        review = manager.create_review_session(commit="HEAD")

        assert review is not None
        assert review.id is not None
        assert review.diff is not None
        assert len(review.diff.files) > 0

    async def test_review_session_retrieval(
        self, git_repo_with_commits: Path
    ) -> None:
        """Test retrieving a review session by ID."""
        loop = asyncio.get_event_loop()
        manager = ReviewManager(loop=loop)

        # Create a review
        review = manager.create_review_session(commit="HEAD")
        review_id = review.id

        # Retrieve it
        retrieved = manager.get_review_session(review_id)

        assert retrieved is not None
        assert retrieved.id == review_id

    async def test_get_most_recent_review(self, git_repo_with_commits: Path) -> None:
        """Test getting the most recently created review."""
        loop = asyncio.get_event_loop()
        manager = ReviewManager(loop=loop)

        # Create multiple reviews
        review1 = manager.create_review_session(commit="HEAD")
        await asyncio.sleep(0.01)  # Ensure different timestamps
        review2 = manager.create_review_session(commit="HEAD")

        # Get most recent
        recent = manager.get_most_recent_review()

        assert recent is not None
        assert recent.id == review2.id

    async def test_add_comment_to_review(self, git_repo_with_commits: Path) -> None:
        """Test adding comments to a review session."""
        loop = asyncio.get_event_loop()
        manager = ReviewManager(loop=loop)

        # Create review
        review = manager.create_review_session(commit="HEAD")

        # Add comment
        request = CommentRequest(
            file_path="file1.txt",
            line_number=1,
            side="right",
            content="This needs improvement",
        )
        comment, position = review.comment_service.add_comment(request)

        assert comment is not None
        assert position == 1
        assert comment.status == CommentStatus.PENDING

    async def test_comment_queue_workflow(self, git_repo_with_commits: Path) -> None:
        """Test the comment queue workflow."""
        loop = asyncio.get_event_loop()
        manager = ReviewManager(loop=loop)

        # Create review
        review = manager.create_review_session(commit="HEAD")

        # Add multiple comments
        for i in range(3):
            request = CommentRequest(
                file_path="file1.txt",
                line_number=i + 1,
                side="right",
                content=f"Comment {i + 1}",
            )
            review.comment_service.add_comment(request)

        # Check queue length
        assert review.comment_service.get_queue_length() == 3

        # Get queue status
        queue_status = review.comment_service.get_queue_status()
        assert len(queue_status) == 3

    async def test_await_comments_returns_comments(
        self, git_repo_with_commits: Path
    ) -> None:
        """Test that await_comments returns pending comments."""
        loop = asyncio.get_event_loop()
        manager = ReviewManager(loop=loop)

        # Create review
        review = manager.create_review_session(commit="HEAD")

        # Add a comment
        request = CommentRequest(
            file_path="file1.txt",
            line_number=1,
            side="right",
            content="Test comment",
        )
        comment, _ = review.comment_service.add_comment(request)

        # Add to manager's queue
        manager.add_comment_to_queue(review.id, comment)

        # Wait for comment (should return immediately)
        result = await asyncio.wait_for(manager.await_comments(), timeout=2.0)

        # Result should be the queued comment wrapper (not ReviewApproved)
        assert isinstance(result, PendingComment)
        assert result.review_id == review.id
        assert result.comment.content == "Test comment"

    async def test_comment_status_transitions(
        self, git_repo_with_commits: Path
    ) -> None:
        """Test comment status transitions through the workflow."""
        loop = asyncio.get_event_loop()
        manager = ReviewManager(loop=loop)

        # Create review
        review = manager.create_review_session(commit="HEAD")

        # Add comment (starts as PENDING)
        request = CommentRequest(
            file_path="file1.txt",
            line_number=1,
            side="right",
            content="Test comment",
        )
        comment, _ = review.comment_service.add_comment(request)
        assert comment.status == CommentStatus.PENDING

        # Add to queue and dequeue (should transition to IN_PROGRESS)
        manager.add_comment_to_queue(review.id, comment)
        await asyncio.wait_for(manager.await_comments(), timeout=2.0)

        # Check status changed to IN_PROGRESS
        updated_comment = review.comment_service.get_comment(comment.id)
        assert updated_comment is not None
        assert updated_comment.status == CommentStatus.IN_PROGRESS

        # Mark as resolved
        review.comment_service.update_comment_status(
            comment.id, CommentStatus.RESOLVED
        )
        resolved_comment = review.comment_service.get_comment(comment.id)
        assert resolved_comment is not None
        assert resolved_comment.status == CommentStatus.RESOLVED
        assert resolved_comment.queue_position is None

    async def test_multiple_reviews_isolation(
        self, git_repo_with_commits: Path
    ) -> None:
        """Test that multiple reviews are isolated from each other."""
        loop = asyncio.get_event_loop()
        manager = ReviewManager(loop=loop)

        # Create two reviews
        review1 = manager.create_review_session(commit="HEAD")
        review2 = manager.create_review_session(commit="HEAD~1")

        # Add comments to each
        request1 = CommentRequest(
            file_path="file1.txt", line_number=1, side="right", content="Review 1 comment"
        )
        review1.comment_service.add_comment(request1)

        request2 = CommentRequest(
            file_path="file2.txt", line_number=2, side="right", content="Review 2 comment"
        )
        review2.comment_service.add_comment(request2)

        # Verify isolation
        review1_comments = review1.comment_service.get_comments()
        review2_comments = review2.comment_service.get_comments()

        assert len(review1_comments) == 1
        assert len(review2_comments) == 1
        assert review1_comments[0].content == "Review 1 comment"
        assert review2_comments[0].content == "Review 2 comment"

    async def test_event_emission_on_comment_dequeue(
        self, git_repo_with_commits: Path
    ) -> None:
        """Test that events are emitted when comments are dequeued."""
        loop = asyncio.get_event_loop()
        manager = ReviewManager(loop=loop)

        # Subscribe to events
        subscriber = await manager.event_manager.subscribe()

        # Create review and add comment
        review = manager.create_review_session(commit="HEAD")
        request = CommentRequest(
            file_path="file1.txt",
            line_number=1,
            side="right",
            content="Test comment",
        )
        comment, _ = review.comment_service.add_comment(request)

        # Add to queue and dequeue
        manager.add_comment_to_queue(review.id, comment)
        await asyncio.wait_for(manager.await_comments(), timeout=2.0)

        # Check that event was emitted
        events = await asyncio.wait_for(
            manager.event_manager.wait_for_events(subscriber, timeout=1.0), timeout=2.0
        )

        # Should have at least one event
        assert len(events) >= 1

        # Find comment dequeued event
        dequeued_events = [
            e for e in events if e.type.value == "comment_dequeued"
        ]
        assert len(dequeued_events) > 0
        assert dequeued_events[0].data["comment_id"] == comment.id

    async def test_event_scoping_per_review(
        self, git_repo_with_commits: Path
    ) -> None:
        """Ensure subscribers only receive events for their review when scoped."""
        loop = asyncio.get_event_loop()
        manager = ReviewManager(loop=loop)

        review1 = manager.create_review_session(commit="HEAD")
        review2 = manager.create_review_session(commit="HEAD")

        all_subscriber = await manager.event_manager.subscribe()
        review2_subscriber = await manager.event_manager.subscribe(
            review_id=review2.id
        )

        await manager.event_manager.emit_event(
            EventType.REVIEW_UPDATED, {"review": review1.id}, review_id=review1.id
        )
        await manager.event_manager.emit_event(
            EventType.REVIEW_UPDATED, {"review": review2.id}, review_id=review2.id
        )

        all_events = await manager.event_manager.wait_for_events(
            all_subscriber, timeout=1.0
        )
        scoped_events = await manager.event_manager.wait_for_events(
            review2_subscriber, timeout=1.0
        )

        assert len(all_events) == 2
        assert {event.review_id for event in all_events} == {review1.id, review2.id}

        assert len(scoped_events) == 1
        assert scoped_events[0].review_id == review2.id
        assert scoped_events[0].data["review"] == review2.id

    async def test_await_comments_returns_review_approved_when_no_pending(
        self, git_repo_with_commits: Path
    ) -> None:
        """Return ReviewApproved when latest review is approved and queue is empty."""
        loop = asyncio.get_event_loop()
        manager = ReviewManager(loop=loop)

        review = manager.create_review_session(commit="HEAD")
        manager._review_approved[review.id] = True

        result = await asyncio.wait_for(manager.await_comments(), timeout=1.0)

        assert isinstance(result, ReviewApproved)
        assert result.review_id == review.id

        if manager.file_watcher:
            manager.file_watcher.stop()

    async def test_live_diff_workflow(self, git_repo_with_commits: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test creating a review session for live changes."""
        # Change to the git repo directory so GitService picks it up
        monkeypatch.chdir(git_repo_with_commits)

        loop = asyncio.get_event_loop()
        manager = ReviewManager(loop=loop)

        # Make a change in the working directory
        test_file = git_repo_with_commits / "file1.txt"
        original_content = test_file.read_text()
        test_file.write_text(original_content + "new line\n")

        # Create live review
        review = manager.create_review_session(since="HEAD")

        assert review is not None
        assert review.diff is not None
        assert review.diff.message is not None and "Live changes" in review.diff.message

        # Should show the modified file
        modified_files = [f for f in review.diff.files if f.path == "file1.txt"]
        assert len(modified_files) > 0

    async def test_range_diff_workflow(self, git_repo_with_commits: Path) -> None:
        """Test creating a review session for a commit range."""
        loop = asyncio.get_event_loop()
        manager = ReviewManager(loop=loop)

        # Create range review
        review = manager.create_review_session(range="HEAD~1..HEAD")

        assert review is not None
        assert review.diff is not None
        assert review.diff.message is not None and "Range:" in review.diff.message

    async def test_remove_review_session(self, git_repo_with_commits: Path) -> None:
        """Test removing a review session."""
        loop = asyncio.get_event_loop()
        manager = ReviewManager(loop=loop)

        # Create review
        review = manager.create_review_session(commit="HEAD")
        review_id = review.id

        # Verify it exists
        assert manager.get_review_session(review_id) is not None

        # Remove it
        success = manager.remove_review_session(review_id)
        assert success is True

        # Verify it's gone
        assert manager.get_review_session(review_id) is None

    async def test_remove_nonexistent_review(self, git_repo_with_commits: Path) -> None:
        """Test removing a non-existent review session."""
        loop = asyncio.get_event_loop()
        manager = ReviewManager(loop=loop)

        success = manager.remove_review_session("nonexistent-id")
        assert success is False

    async def test_get_most_recent_review_empty(self) -> None:
        """Test getting most recent review when no reviews exist."""
        loop = asyncio.get_event_loop()
        manager = ReviewManager(loop=loop)

        recent = manager.get_most_recent_review()
        assert recent is None

    async def test_comment_persistence_in_review(
        self, git_repo_with_commits: Path, temp_storage_dir: Path
    ) -> None:
        """Test that comments persist within a review session."""
        loop = asyncio.get_event_loop()
        manager = ReviewManager(loop=loop)

        # Create review with custom storage
        review = manager.create_review_session(commit="HEAD")

        # Add comments
        comment_ids = []
        for i in range(3):
            request = CommentRequest(
                file_path="file1.txt",
                line_number=i + 1,
                side="right",
                content=f"Comment {i + 1}",
            )
            comment, _ = review.comment_service.add_comment(request)
            comment_ids.append(comment.id)

        # Retrieve all comments
        comments = review.comment_service.get_comments()
        assert len(comments) == 3

        # Verify all comment IDs are present
        retrieved_ids = [c.id for c in comments]
        for comment_id in comment_ids:
            assert comment_id in retrieved_ids

    async def test_concurrent_comment_additions(
        self, git_repo_with_commits: Path
    ) -> None:
        """Test adding multiple comments concurrently."""
        loop = asyncio.get_event_loop()
        manager = ReviewManager(loop=loop)

        review = manager.create_review_session(commit="HEAD")

        # Add comments concurrently (though service itself isn't async)
        async def add_comment(i: int) -> None:
            request = CommentRequest(
                file_path="file1.txt",
                line_number=i,
                side="right",
                content=f"Concurrent comment {i}",
            )
            review.comment_service.add_comment(request)

        # Add 5 comments concurrently
        await asyncio.gather(*[add_comment(i) for i in range(5)])

        # Verify all were added
        comments = review.comment_service.get_comments()
        assert len(comments) == 5
