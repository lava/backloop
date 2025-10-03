"""Unit tests for data models."""

import pytest
from pydantic import ValidationError

from backloop.models import (
    CommentStatus,
    LineType,
    DiffLine,
    DiffChunk,
    DiffFile,
    GitDiff,
    Comment,
    CommentRequest,
    FileEditRequest,
    ReviewApproved,
)


class TestEnums:
    """Test enum definitions."""

    def test_comment_status_values(self) -> None:
        """Test CommentStatus enum values."""
        assert CommentStatus.PENDING.value == "pending"
        assert CommentStatus.IN_PROGRESS.value == "in_progress"
        assert CommentStatus.RESOLVED.value == "resolved"

    def test_line_type_values(self) -> None:
        """Test LineType enum values."""
        assert LineType.ADDITION.value == "addition"
        assert LineType.DELETION.value == "deletion"
        assert LineType.CONTEXT.value == "context"


class TestDiffLine:
    """Test DiffLine model."""

    def test_create_addition_line(self) -> None:
        """Test creating an addition line."""
        line = DiffLine(
            type=LineType.ADDITION,
            oldNum=None,
            newNum=5,
            content="new line",
        )

        assert line.type == LineType.ADDITION
        assert line.oldNum is None
        assert line.newNum == 5
        assert line.content == "new line"

    def test_create_deletion_line(self) -> None:
        """Test creating a deletion line."""
        line = DiffLine(
            type=LineType.DELETION,
            oldNum=5,
            newNum=None,
            content="deleted line",
        )

        assert line.type == LineType.DELETION
        assert line.oldNum == 5
        assert line.newNum is None
        assert line.content == "deleted line"

    def test_create_context_line(self) -> None:
        """Test creating a context line."""
        line = DiffLine(
            type=LineType.CONTEXT,
            oldNum=5,
            newNum=6,
            content="context line",
        )

        assert line.type == LineType.CONTEXT
        assert line.oldNum == 5
        assert line.newNum == 6
        assert line.content == "context line"

    def test_field_alias_serialization(self) -> None:
        """Test that field aliases work for serialization."""
        line = DiffLine(
            type=LineType.ADDITION,
            oldNum=None,
            newNum=5,
            content="new line",
        )

        data = line.model_dump(by_alias=True)
        assert "oldNum" in data
        assert "newNum" in data

    def test_field_alias_deserialization(self) -> None:
        """Test that field aliases work for deserialization."""
        # Using old_num/new_num
        line1 = DiffLine(
            type=LineType.ADDITION,
            old_num=None,
            new_num=5,
            content="new line",
        )
        assert line1.newNum == 5

        # Using oldNum/newNum
        line2 = DiffLine.model_validate(
            {
                "type": "addition",
                "oldNum": None,
                "newNum": 5,
                "content": "new line",
            }
        )
        assert line2.newNum == 5


class TestDiffChunk:
    """Test DiffChunk model."""

    def test_create_chunk(self) -> None:
        """Test creating a diff chunk."""
        lines = [
            DiffLine(type=LineType.CONTEXT, oldNum=1, newNum=1, content="line 1"),
            DiffLine(type=LineType.DELETION, oldNum=2, newNum=None, content="old"),
            DiffLine(type=LineType.ADDITION, oldNum=None, newNum=2, content="new"),
        ]

        chunk = DiffChunk(
            old_start=1,
            old_lines=2,
            new_start=1,
            new_lines=2,
            lines=lines,
        )

        assert chunk.old_start == 1
        assert chunk.old_lines == 2
        assert chunk.new_start == 1
        assert chunk.new_lines == 2
        assert len(chunk.lines) == 3

    def test_chunk_validation(self) -> None:
        """Test that chunk validates required fields."""
        with pytest.raises(ValidationError):
            DiffChunk(old_start=1)  # type: ignore[call-arg]  # Missing required fields intentionally


class TestDiffFile:
    """Test DiffFile model."""

    def test_create_simple_file(self) -> None:
        """Test creating a simple diff file."""
        file = DiffFile(
            path="test.txt",
            additions=5,
            deletions=2,
            chunks=[],
        )

        assert file.path == "test.txt"
        assert file.old_path is None
        assert file.additions == 5
        assert file.deletions == 2
        assert file.is_binary is False
        assert file.is_renamed is False
        assert file.status is None

    def test_create_renamed_file(self) -> None:
        """Test creating a renamed file."""
        file = DiffFile(
            path="new_name.txt",
            old_path="old_name.txt",
            additions=0,
            deletions=0,
            chunks=[],
            is_renamed=True,
            status="renamed",
        )

        assert file.path == "new_name.txt"
        assert file.old_path == "old_name.txt"
        assert file.is_renamed is True
        assert file.status == "renamed"

    def test_create_binary_file(self) -> None:
        """Test creating a binary file."""
        file = DiffFile(
            path="image.png",
            additions=0,
            deletions=0,
            chunks=[],
            is_binary=True,
        )

        assert file.is_binary is True

    def test_file_with_status(self) -> None:
        """Test file with different statuses."""
        added_file = DiffFile(
            path="new.txt",
            additions=10,
            deletions=0,
            chunks=[],
            status="added",
        )
        assert added_file.status == "added"

        deleted_file = DiffFile(
            path="deleted.txt",
            additions=0,
            deletions=10,
            chunks=[],
            status="deleted",
        )
        assert deleted_file.status == "deleted"


class TestGitDiff:
    """Test GitDiff model."""

    def test_create_commit_diff(self) -> None:
        """Test creating a commit diff."""
        files = [
            DiffFile(path="file1.txt", additions=5, deletions=2, chunks=[]),
            DiffFile(path="file2.txt", additions=3, deletions=1, chunks=[]),
        ]

        diff = GitDiff(
            files=files,
            commit_hash="abc123",
            author="Test User",
            message="Test commit",
        )

        assert len(diff.files) == 2
        assert diff.commit_hash == "abc123"
        assert diff.author == "Test User"
        assert diff.message == "Test commit"

    def test_create_range_diff(self) -> None:
        """Test creating a range diff (no commit info)."""
        diff = GitDiff(
            files=[],
            commit_hash=None,
            author=None,
            message="Range: main..feature",
        )

        assert diff.commit_hash is None
        assert diff.author is None
        assert diff.message is not None and "Range:" in diff.message


class TestComment:
    """Test Comment model."""

    def test_create_comment(self) -> None:
        """Test creating a comment."""
        comment = Comment(
            id="comment-1",
            file_path="test.txt",
            line_number=10,
            side="right",
            content="Test comment",
            author="Test User",
            timestamp="2024-01-01T12:00:00",
        )

        assert comment.id == "comment-1"
        assert comment.file_path == "test.txt"
        assert comment.line_number == 10
        assert comment.side == "right"
        assert comment.content == "Test comment"
        assert comment.author == "Test User"
        assert comment.timestamp == "2024-01-01T12:00:00"
        assert comment.queue_position is None
        assert comment.status == CommentStatus.PENDING

    def test_comment_with_queue_position(self) -> None:
        """Test comment with queue position."""
        comment = Comment(
            id="comment-1",
            file_path="test.txt",
            line_number=10,
            side="right",
            content="Test comment",
            timestamp="2024-01-01T12:00:00",
            queue_position=1,
        )

        assert comment.queue_position == 1

    def test_comment_with_status(self) -> None:
        """Test comment with different statuses."""
        comment = Comment(
            id="comment-1",
            file_path="test.txt",
            line_number=10,
            side="right",
            content="Test comment",
            timestamp="2024-01-01T12:00:00",
            status=CommentStatus.IN_PROGRESS,
        )

        assert comment.status == CommentStatus.IN_PROGRESS

    def test_comment_default_author(self) -> None:
        """Test that default author is 'User'."""
        comment = Comment(
            id="comment-1",
            file_path="test.txt",
            line_number=10,
            side="right",
            content="Test comment",
            timestamp="2024-01-01T12:00:00",
        )

        assert comment.author == "User"


class TestCommentRequest:
    """Test CommentRequest model."""

    def test_create_comment_request(self) -> None:
        """Test creating a comment request."""
        request = CommentRequest(
            file_path="test.txt",
            line_number=10,
            side="right",
            content="New comment",
            author="Test User",
        )

        assert request.file_path == "test.txt"
        assert request.line_number == 10
        assert request.side == "right"
        assert request.content == "New comment"
        assert request.author == "Test User"

    def test_comment_request_default_author(self) -> None:
        """Test default author in comment request."""
        request = CommentRequest(
            file_path="test.txt",
            line_number=10,
            side="right",
            content="New comment",
        )

        assert request.author == "User"

    def test_comment_request_validation(self) -> None:
        """Test that comment request validates required fields."""
        with pytest.raises(ValidationError):
            CommentRequest(file_path="test.txt", line_number=10)  # type: ignore[call-arg]  # Missing fields intentionally


class TestFileEditRequest:
    """Test FileEditRequest model."""

    def test_create_file_edit_request(self) -> None:
        """Test creating a file edit request."""
        patch = """--- a/test.txt
+++ b/test.txt
@@ -1,1 +1,1 @@
-old line
+new line
"""
        request = FileEditRequest(
            filename="test.txt",
            patch=patch,
        )

        assert request.filename == "test.txt"
        assert request.patch == patch

    def test_file_edit_request_validation(self) -> None:
        """Test that file edit request validates required fields."""
        with pytest.raises(ValidationError):
            FileEditRequest(filename="test.txt")  # type: ignore[call-arg]  # Missing patch intentionally


class TestReviewApproved:
    """Test ReviewApproved model."""

    def test_create_review_approved(self) -> None:
        """Test creating a review approved event."""
        approved = ReviewApproved(
            review_id="review-1",
            timestamp="2024-01-01T12:00:00",
        )

        assert approved.review_id == "review-1"
        assert approved.timestamp == "2024-01-01T12:00:00"

    def test_review_approved_validation(self) -> None:
        """Test that review approved validates required fields."""
        with pytest.raises(ValidationError):
            ReviewApproved(review_id="review-1")  # type: ignore[call-arg]  # Missing timestamp intentionally


class TestModelSerialization:
    """Test model serialization/deserialization."""

    def test_comment_serialization(self) -> None:
        """Test comment can be serialized and deserialized."""
        comment = Comment(
            id="comment-1",
            file_path="test.txt",
            line_number=10,
            side="right",
            content="Test comment",
            timestamp="2024-01-01T12:00:00",
            queue_position=1,
            status=CommentStatus.PENDING,
        )

        # Serialize
        data = comment.model_dump()

        # Deserialize
        comment2 = Comment(**data)

        assert comment2.id == comment.id
        assert comment2.content == comment.content
        assert comment2.status == comment.status

    def test_diff_file_serialization(self) -> None:
        """Test diff file can be serialized with nested chunks."""
        chunk = DiffChunk(
            old_start=1,
            old_lines=1,
            new_start=1,
            new_lines=1,
            lines=[
                DiffLine(type=LineType.CONTEXT, oldNum=1, newNum=1, content="test")
            ],
        )

        file = DiffFile(
            path="test.txt",
            additions=1,
            deletions=0,
            chunks=[chunk],
        )

        # Serialize
        data = file.model_dump()

        # Deserialize
        file2 = DiffFile(**data)

        assert file2.path == file.path
        assert len(file2.chunks) == 1
        assert len(file2.chunks[0].lines) == 1

    def test_git_diff_serialization(self) -> None:
        """Test complete GitDiff can be serialized."""
        diff = GitDiff(
            files=[
                DiffFile(path="test.txt", additions=1, deletions=0, chunks=[])
            ],
            commit_hash="abc123",
            author="Test User",
            message="Test commit",
        )

        # Serialize
        data = diff.model_dump()

        # Deserialize
        diff2 = GitDiff(**data)

        assert diff2.commit_hash == diff.commit_hash
        assert len(diff2.files) == 1
