"""Unit tests for CommentService."""

from pathlib import Path
import json
import pytest

from backloop.comment_service import CommentService
from backloop.models import CommentRequest, CommentStatus


class TestCommentService:
    """Test suite for CommentService."""

    def test_init_with_storage_path(self, temp_storage_dir: Path) -> None:
        """Test CommentService initialization with a specific storage path."""
        storage_path = temp_storage_dir / "comments.json"
        service = CommentService(str(storage_path))
        assert service.storage_path == storage_path

    def test_init_loads_empty_when_file_not_exists(
        self, temp_storage_dir: Path
    ) -> None:
        """Test that initialization works when storage file doesn't exist."""
        storage_path = temp_storage_dir / "comments.json"
        service = CommentService(str(storage_path))
        assert len(service.get_comments()) == 0

    def test_add_comment(self, temp_storage_dir: Path) -> None:
        """Test adding a comment."""
        storage_path = temp_storage_dir / "comments.json"
        service = CommentService(str(storage_path))

        request = CommentRequest(
            file_path="test.txt",
            line_number=10,
            side="right",
            content="This is a test comment",
            author="Test User",
        )

        comment, queue_position = service.add_comment(request)

        assert comment.file_path == "test.txt"
        assert comment.line_number == 10
        assert comment.side == "right"
        assert comment.content == "This is a test comment"
        assert comment.author == "Test User"
        assert comment.status == CommentStatus.PENDING
        assert queue_position == 1
        assert comment.queue_position == 1
        assert comment.id is not None

    def test_add_multiple_comments_queue_positions(
        self, temp_storage_dir: Path
    ) -> None:
        """Test that queue positions are assigned correctly."""
        storage_path = temp_storage_dir / "comments.json"
        service = CommentService(str(storage_path))

        # Add three comments
        for i in range(1, 4):
            request = CommentRequest(
                file_path=f"file{i}.txt",
                line_number=i,
                side="right",
                content=f"Comment {i}",
            )
            _, queue_position = service.add_comment(request)
            assert queue_position == i

    def test_get_comments_all(self, temp_storage_dir: Path) -> None:
        """Test getting all comments."""
        storage_path = temp_storage_dir / "comments.json"
        service = CommentService(str(storage_path))

        # Add multiple comments
        for i in range(3):
            request = CommentRequest(
                file_path=f"file{i}.txt",
                line_number=i,
                side="right",
                content=f"Comment {i}",
            )
            service.add_comment(request)

        comments = service.get_comments()
        assert len(comments) == 3

    def test_get_comments_filtered_by_file(self, temp_storage_dir: Path) -> None:
        """Test getting comments filtered by file path."""
        storage_path = temp_storage_dir / "comments.json"
        service = CommentService(str(storage_path))

        # Add comments to different files
        for i in range(3):
            request = CommentRequest(
                file_path="file1.txt" if i < 2 else "file2.txt",
                line_number=i,
                side="right",
                content=f"Comment {i}",
            )
            service.add_comment(request)

        # Get comments for file1.txt only
        comments = service.get_comments(file_path="file1.txt")
        assert len(comments) == 2
        for comment in comments:
            assert comment.file_path == "file1.txt"

    def test_get_comment_by_id(self, temp_storage_dir: Path) -> None:
        """Test getting a specific comment by ID."""
        storage_path = temp_storage_dir / "comments.json"
        service = CommentService(str(storage_path))

        request = CommentRequest(
            file_path="test.txt",
            line_number=10,
            side="right",
            content="Test comment",
        )
        comment, _ = service.add_comment(request)

        retrieved = service.get_comment(comment.id)
        assert retrieved is not None
        assert retrieved.id == comment.id
        assert retrieved.content == "Test comment"

    def test_get_comment_nonexistent(self, temp_storage_dir: Path) -> None:
        """Test getting a non-existent comment returns None."""
        storage_path = temp_storage_dir / "comments.json"
        service = CommentService(str(storage_path))

        comment = service.get_comment("nonexistent-id")
        assert comment is None

    def test_update_comment(self, temp_storage_dir: Path) -> None:
        """Test updating a comment's content."""
        storage_path = temp_storage_dir / "comments.json"
        service = CommentService(str(storage_path))

        request = CommentRequest(
            file_path="test.txt",
            line_number=10,
            side="right",
            content="Original content",
        )
        comment, _ = service.add_comment(request)
        original_timestamp = comment.timestamp

        updated = service.update_comment(comment.id, "Updated content")
        assert updated is not None
        assert updated.content == "Updated content"
        # Timestamp should be updated (greater than or equal to original)
        assert updated.timestamp >= original_timestamp

    def test_update_nonexistent_comment(self, temp_storage_dir: Path) -> None:
        """Test updating a non-existent comment returns None."""
        storage_path = temp_storage_dir / "comments.json"
        service = CommentService(str(storage_path))

        result = service.update_comment("nonexistent-id", "New content")
        assert result is None

    def test_delete_comment(self, temp_storage_dir: Path) -> None:
        """Test deleting a comment."""
        storage_path = temp_storage_dir / "comments.json"
        service = CommentService(str(storage_path))

        request = CommentRequest(
            file_path="test.txt",
            line_number=10,
            side="right",
            content="Test comment",
        )
        comment, _ = service.add_comment(request)

        success = service.delete_comment(comment.id)
        assert success is True

        # Verify comment is gone
        retrieved = service.get_comment(comment.id)
        assert retrieved is None

    def test_delete_comment_removes_from_queue(self, temp_storage_dir: Path) -> None:
        """Test that deleting a comment removes it from the queue."""
        storage_path = temp_storage_dir / "comments.json"
        service = CommentService(str(storage_path))

        # Add two comments
        request1 = CommentRequest(
            file_path="test.txt", line_number=1, side="right", content="Comment 1"
        )
        comment1, _ = service.add_comment(request1)

        request2 = CommentRequest(
            file_path="test.txt", line_number=2, side="right", content="Comment 2"
        )
        comment2, _ = service.add_comment(request2)

        # Delete first comment
        service.delete_comment(comment1.id)

        # Check queue
        queue_status = service.get_queue_status()
        assert comment1.id not in queue_status
        assert comment2.id in queue_status

    def test_delete_nonexistent_comment(self, temp_storage_dir: Path) -> None:
        """Test deleting a non-existent comment returns False."""
        storage_path = temp_storage_dir / "comments.json"
        service = CommentService(str(storage_path))

        success = service.delete_comment("nonexistent-id")
        assert success is False

    def test_get_queue_status(self, temp_storage_dir: Path) -> None:
        """Test getting queue status."""
        storage_path = temp_storage_dir / "comments.json"
        service = CommentService(str(storage_path))

        # Add multiple comments
        comment_ids = []
        for i in range(3):
            request = CommentRequest(
                file_path=f"file{i}.txt",
                line_number=i,
                side="right",
                content=f"Comment {i}",
            )
            comment, _ = service.add_comment(request)
            comment_ids.append(comment.id)

        queue_status = service.get_queue_status()
        assert len(queue_status) == 3
        for i, comment_id in enumerate(comment_ids):
            assert queue_status[comment_id] == i + 1

    def test_get_queue_length(self, temp_storage_dir: Path) -> None:
        """Test getting queue length."""
        storage_path = temp_storage_dir / "comments.json"
        service = CommentService(str(storage_path))

        assert service.get_queue_length() == 0

        # Add comments
        for i in range(3):
            request = CommentRequest(
                file_path=f"file{i}.txt",
                line_number=i,
                side="right",
                content=f"Comment {i}",
            )
            service.add_comment(request)

        assert service.get_queue_length() == 3

    def test_update_comment_status(self, temp_storage_dir: Path) -> None:
        """Test updating a comment's status."""
        storage_path = temp_storage_dir / "comments.json"
        service = CommentService(str(storage_path))

        request = CommentRequest(
            file_path="test.txt",
            line_number=10,
            side="right",
            content="Test comment",
        )
        comment, _ = service.add_comment(request)

        # Update to in_progress
        updated = service.update_comment_status(comment.id, CommentStatus.IN_PROGRESS)
        assert updated is not None
        assert updated.status == CommentStatus.IN_PROGRESS

        # Update to resolved
        updated = service.update_comment_status(comment.id, CommentStatus.RESOLVED)
        assert updated is not None
        assert updated.status == CommentStatus.RESOLVED
        assert updated.queue_position is None

    def test_update_status_nonexistent_comment(self, temp_storage_dir: Path) -> None:
        """Test updating status of non-existent comment returns None."""
        storage_path = temp_storage_dir / "comments.json"
        service = CommentService(str(storage_path))

        result = service.update_comment_status(
            "nonexistent-id", CommentStatus.RESOLVED
        )
        assert result is None

    def test_remove_comment_from_queue(self, temp_storage_dir: Path) -> None:
        """Test removing a comment from the queue."""
        storage_path = temp_storage_dir / "comments.json"
        service = CommentService(str(storage_path))

        # Add comments
        comment_ids = []
        for i in range(3):
            request = CommentRequest(
                file_path=f"file{i}.txt",
                line_number=i,
                side="right",
                content=f"Comment {i}",
            )
            comment, _ = service.add_comment(request)
            comment_ids.append(comment.id)

        # Remove middle comment
        success = service.remove_comment_from_queue(comment_ids[1])
        assert success is True

        # Check queue positions are updated
        queue_status = service.get_queue_status()
        assert comment_ids[1] not in queue_status
        assert queue_status[comment_ids[0]] == 1
        assert queue_status[comment_ids[2]] == 2

    def test_remove_comment_not_in_queue(self, temp_storage_dir: Path) -> None:
        """Test removing a comment not in queue returns False."""
        storage_path = temp_storage_dir / "comments.json"
        service = CommentService(str(storage_path))

        success = service.remove_comment_from_queue("nonexistent-id")
        assert success is False

    def test_persistence_across_instances(self, temp_storage_dir: Path) -> None:
        """Test that comments persist across service instances."""
        storage_path = temp_storage_dir / "comments.json"

        # Create first instance and add comments
        service1 = CommentService(str(storage_path))
        request = CommentRequest(
            file_path="test.txt",
            line_number=10,
            side="right",
            content="Persistent comment",
        )
        comment, _ = service1.add_comment(request)
        comment_id = comment.id

        # Create second instance
        service2 = CommentService(str(storage_path))

        # Verify comment exists in new instance
        retrieved = service2.get_comment(comment_id)
        assert retrieved is not None
        assert retrieved.content == "Persistent comment"

    def test_load_comments_handles_corrupted_file(
        self, temp_storage_dir: Path
    ) -> None:
        """Test that corrupted storage file is handled gracefully."""
        storage_path = temp_storage_dir / "comments.json"

        # Write corrupted JSON
        storage_path.write_text("{ invalid json }")

        # Should not raise, should start fresh
        service = CommentService(str(storage_path))
        assert len(service.get_comments()) == 0

    def test_rebuild_queue_from_loaded_comments(self, temp_storage_dir: Path) -> None:
        """Test that queue is rebuilt correctly when loading comments."""
        storage_path = temp_storage_dir / "comments.json"

        # Create service and add comments
        service1 = CommentService(str(storage_path))
        comment_ids = []
        for i in range(3):
            request = CommentRequest(
                file_path=f"file{i}.txt",
                line_number=i,
                side="right",
                content=f"Comment {i}",
            )
            comment, _ = service1.add_comment(request)
            comment_ids.append(comment.id)

        # Create new service instance (loads from file)
        service2 = CommentService(str(storage_path))

        # Verify queue is rebuilt correctly
        queue_status = service2.get_queue_status()
        assert len(queue_status) == 3
        for i, comment_id in enumerate(comment_ids):
            assert queue_status[comment_id] == i + 1

    def test_rebuild_queue_excludes_resolved_comments(
        self, temp_storage_dir: Path
    ) -> None:
        """Test that resolved comments are excluded when rebuilding queue."""
        storage_path = temp_storage_dir / "comments.json"

        # Create service and add comments
        service1 = CommentService(str(storage_path))
        comment_ids = []
        for i in range(3):
            request = CommentRequest(
                file_path=f"file{i}.txt",
                line_number=i,
                side="right",
                content=f"Comment {i}",
            )
            comment, _ = service1.add_comment(request)
            comment_ids.append(comment.id)

        # Mark middle comment as resolved
        service1.update_comment_status(comment_ids[1], CommentStatus.RESOLVED)

        # Create new service instance
        service2 = CommentService(str(storage_path))

        # Verify resolved comment is not in queue
        queue_status = service2.get_queue_status()
        assert len(queue_status) == 2
        assert comment_ids[1] not in queue_status
        assert comment_ids[0] in queue_status
        assert comment_ids[2] in queue_status

    def test_comments_sorted_by_timestamp(self, temp_storage_dir: Path) -> None:
        """Test that get_comments returns comments sorted by timestamp."""
        storage_path = temp_storage_dir / "comments.json"
        service = CommentService(str(storage_path))

        comment_ids = []
        for i in range(3):
            request = CommentRequest(
                file_path=f"file{i}.txt",
                line_number=i,
                side="right",
                content=f"Comment {i}",
            )
            comment, _ = service.add_comment(request)
            comment_ids.append(comment.id)

        comments = service.get_comments()
        assert len(comments) == 3

        # Verify they're in timestamp order
        for i in range(len(comments) - 1):
            assert comments[i].timestamp <= comments[i + 1].timestamp
